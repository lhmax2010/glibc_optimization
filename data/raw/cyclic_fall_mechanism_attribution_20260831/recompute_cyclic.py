#!/usr/bin/env python3
"""Public, independent cyclic fall attribution from only the raw TSV inputs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


INT_FIELDS = {
    "sample",
    "epoch_ns",
    "pid",
    "glibc_heap_pd_kb",
    "other_anon_pd_kb",
    "file_backed_pd_kb",
    "total_pd_kb",
    "minflt",
    "majflt",
    "MemAvailable_kb",
    "zram_used_kb",
    "zram_orig_bytes",
    "zram_compr_bytes",
    "zram_mem_used_bytes",
}


def load_tsv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    for row in rows:
        for field in INT_FIELDS.intersection(row):
            value = row[field]
            row[field] = None if value in {"", "NA"} else int(str(value))
    return rows


def round_plan(key_path: Path) -> tuple[list[tuple[str, int]], int]:
    with key_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    offsets: dict[str, int] = {}
    start_estimates: list[int] = []
    for row in rows:
        offsets.setdefault(row["round"], int(row["target_offset_s"]))
        start_estimates.append(
            int(row["actual_epoch_ns"])
            - int(row["target_offset_s"]) * 1_000_000_000
            - round(float(row["lateness_ms"]) * 1_000_000)
        )
    ordered_estimates = sorted(start_estimates)
    middle = len(ordered_estimates) // 2
    if len(ordered_estimates) % 2:
        start_ns = ordered_estimates[middle]
    else:
        start_ns = (ordered_estimates[middle - 1] + ordered_estimates[middle]) // 2
    return sorted(offsets.items(), key=lambda item: int(item[0][1:])), start_ns


def delta(later: dict[str, object], earlier: dict[str, object], field: str) -> int:
    return int(later[field]) - int(earlier[field])


def timestamp_to_second(value: object) -> str:
    main, fractional_and_zone = str(value).split(",", 1)
    return main + fractional_and_zone[-5:]


def unique_sample_rows(rows: list[dict[str, object]], preferred_target: str) -> list[dict[str, object]]:
    selected = [row for row in rows if row["target"] == preferred_target]
    assert len(selected) == len({row["sample"] for row in rows}), "one row per sample expected"
    return sorted(selected, key=lambda row: int(row["epoch_ns"]))


def select_round(
    rows: list[dict[str, object]], start_ns: int, end_ns: int
) -> list[dict[str, object]]:
    before = [row for row in rows if int(row["epoch_ns"]) < start_ns]
    assert before, "round needs a preceding boundary sample"
    boundary = before[-1]
    body = [row for row in rows if start_ns <= int(row["epoch_ns"]) < end_ns]
    assert body, "round contains no samples"
    return [boundary, *body]


def first_max(rows: list[dict[str, object]], field: str) -> tuple[int, dict[str, object]]:
    index = max(range(len(rows)), key=lambda item: int(rows[item][field]))
    return index, rows[index]


def first_min(rows: list[dict[str, object]], field: str) -> tuple[int, dict[str, object]]:
    index = min(range(len(rows)), key=lambda item: int(rows[item][field]))
    return index, rows[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeseries", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = load_tsv(args.timeseries)
    assert rows, "empty timeseries"
    expected = {
        "sample", "stage", "timestamp", "epoch_ns", "target", "comm", "pid",
        "glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb", "total_pd_kb",
        "minflt", "majflt", "MemAvailable_kb", "zram_used_kb", "zram_orig_bytes",
        "zram_compr_bytes", "zram_mem_used_bytes",
    }
    assert set(rows[0]) == expected, "unexpected cyclic schema"

    missing_rows = sum(any(value is None for value in row.values()) for row in rows)
    targets = sorted({str(row["target"]) for row in rows})
    samples = sorted({int(row["sample"]) for row in rows})
    assert samples == list(range(samples[-1] + 1)), "sample sequence has gaps"
    assert all(sum(row["target"] == target for row in rows) == len(samples) for target in targets)
    system_fields = {
        "stage",
        "timestamp",
        "epoch_ns",
        "MemAvailable_kb",
        "zram_used_kb",
        "zram_orig_bytes",
        "zram_compr_bytes",
        "zram_mem_used_bytes",
    }
    system_counter_mismatch_samples = []
    for sample in samples:
        sample_rows = [row for row in rows if row["sample"] == sample]
        reference = sample_rows[0]
        if any(
            any(row[field] != reference[field] for field in system_fields)
            for row in sample_rows[1:]
        ):
            system_counter_mismatch_samples.append(sample)
    assert not system_counter_mismatch_samples, "system counters differ within a sample"

    offsets, start_ns = round_plan(args.keys)
    per_target = {
        target: sorted(
            [row for row in rows if row["target"] == target],
            key=lambda row: int(row["epoch_ns"]),
        )
        for target in targets
    }

    output_rows: list[dict[str, object]] = []
    for target in targets:
        for round_index, (round_name, offset_s) in enumerate(offsets):
            next_offset_s = offsets[round_index + 1][1] if round_index + 1 < len(offsets) else offset_s + 60
            window = select_round(
                per_target[target],
                start_ns + offset_s * 1_000_000_000,
                start_ns + next_offset_s * 1_000_000_000,
            )
            peak_index, peak = first_max(window, "glibc_heap_pd_kb")
            valley_rel_index, valley = first_min(window[peak_index:], "glibc_heap_pd_kb")
            valley_index = peak_index + valley_rel_index
            start = window[0]
            end = window[-1]
            excursion = int(peak["glibc_heap_pd_kb"]) - int(start["glibc_heap_pd_kb"])
            if excursion > 0:
                low_cut = int(start["glibc_heap_pd_kb"]) + excursion * 0.10
                high_cut = int(start["glibc_heap_pd_kb"]) + excursion * 0.90
                first_low = next(
                    index
                    for index, row in enumerate(window[: peak_index + 1])
                    if int(row["glibc_heap_pd_kb"]) >= low_cut
                )
                rise_start_index = max(0, first_low - 1)
                high_index = next(
                    index
                    for index, row in enumerate(window[: peak_index + 1])
                    if int(row["glibc_heap_pd_kb"]) >= high_cut
                )
            else:
                rise_start_index = 0
                high_index = 0
            rise_start = window[rise_start_index]
            high = window[high_index]
            output_rows.append(
                {
                    "target": target,
                    "round": round_name,
                    "window_samples_including_boundary": len(window),
                    "pid": start["pid"],
                    "start_sample": start["sample"],
                    "peak_sample": peak["sample"],
                    "valley_sample": valley["sample"],
                    "end_sample": end["sample"],
                    "start_glibc_pd_kb": start["glibc_heap_pd_kb"],
                    "peak_glibc_pd_kb": peak["glibc_heap_pd_kb"],
                    "valley_glibc_pd_kb": valley["glibc_heap_pd_kb"],
                    "end_glibc_pd_kb": end["glibc_heap_pd_kb"],
                    "peak_to_valley_kb": delta(peak, valley, "glibc_heap_pd_kb"),
                    "zram_orig_peak_to_valley_bytes": delta(valley, peak, "zram_orig_bytes"),
                    "zram_used_peak_to_valley_kb": delta(valley, peak, "zram_used_kb"),
                    "minflt_start_to_peak": delta(peak, start, "minflt"),
                    "majflt_start_to_peak": delta(peak, start, "majflt"),
                    "minflt_rise_10_to_90": delta(high, rise_start, "minflt"),
                    "majflt_rise_10_to_90": delta(high, rise_start, "majflt"),
                    "minflt_peak_to_valley": delta(valley, peak, "minflt"),
                    "majflt_peak_to_valley": delta(valley, peak, "majflt"),
                    "minflt_round": delta(end, start, "minflt"),
                    "majflt_round": delta(end, start, "majflt"),
                    "peak_index": peak_index,
                    "valley_index": valley_index,
                    "rise_start_index": rise_start_index,
                    "high_index": high_index,
                }
            )

    system_rows = unique_sample_rows(rows, targets[0])
    intervals = [
        (int(right["epoch_ns"]) - int(left["epoch_ns"])) / 1_000_000_000
        for left, right in zip(system_rows, system_rows[1:])
    ]
    orig_steps = [delta(right, left, "zram_orig_bytes") for left, right in zip(system_rows, system_rows[1:])]
    used_steps = [delta(right, left, "zram_used_kb") for left, right in zip(system_rows, system_rows[1:])]
    pid_sets = {
        target: sorted({int(row["pid"]) for row in per_target[target] if row["pid"] is not None})
        for target in targets
    }
    pid_changes = {
        target: sum(
            left["pid"] != right["pid"]
            for left, right in zip(per_target[target], per_target[target][1:])
            if left["pid"] is not None and right["pid"] is not None
        )
        for target in targets
    }
    target_counters = {
        target: {
            "minflt_first": per_target[target][0]["minflt"],
            "minflt_last": per_target[target][-1]["minflt"],
            "minflt_delta": delta(per_target[target][-1], per_target[target][0], "minflt"),
            "majflt_first": per_target[target][0]["majflt"],
            "majflt_last": per_target[target][-1]["majflt"],
            "majflt_delta": delta(per_target[target][-1], per_target[target][0], "majflt"),
            "glibc_pd_distinct_values": len(
                {int(row["glibc_heap_pd_kb"]) for row in per_target[target]}
            ),
        }
        for target in targets
    }
    orig_step_events = [
        {
            "from_sample": left["sample"],
            "to_sample": right["sample"],
            "from_timestamp": timestamp_to_second(left["timestamp"]),
            "to_timestamp": timestamp_to_second(right["timestamp"]),
            "delta_bytes": delta(right, left, "zram_orig_bytes"),
        }
        for left, right in zip(system_rows, system_rows[1:])
        if delta(right, left, "zram_orig_bytes") != 0
    ]
    used_step_events = [
        {
            "from_sample": left["sample"],
            "to_sample": right["sample"],
            "from_timestamp": timestamp_to_second(left["timestamp"]),
            "to_timestamp": timestamp_to_second(right["timestamp"]),
            "delta_kb": delta(right, left, "zram_used_kb"),
        }
        for left, right in zip(system_rows, system_rows[1:])
        if delta(right, left, "zram_used_kb") != 0
    ]
    summary = {
        "source": str(args.timeseries),
        "rows": len(rows),
        "targets": targets,
        "samples": len(samples),
        "missing_rows": missing_rows,
        "system_counter_mismatch_samples": system_counter_mismatch_samples,
        "pid_sets": pid_sets,
        "pid_changes": pid_changes,
        "target_counters": target_counters,
        "sample_interval_s": {
            "min": round(min(intervals), 6),
            "median": round(statistics.median(intervals), 6),
            "max": round(max(intervals), 6),
            "gt_1_1_s": sum(value > 1.1 for value in intervals),
            "gt_2_s": sum(value > 2.0 for value in intervals),
            "gt_3_s": sum(value > 3.0 for value in intervals),
        },
        "zram": {
            "orig_first_bytes": system_rows[0]["zram_orig_bytes"],
            "orig_last_bytes": system_rows[-1]["zram_orig_bytes"],
            "orig_total_delta_bytes": delta(system_rows[-1], system_rows[0], "zram_orig_bytes"),
            "orig_min_bytes": min(int(row["zram_orig_bytes"]) for row in system_rows),
            "orig_max_bytes": max(int(row["zram_orig_bytes"]) for row in system_rows),
            "orig_positive_steps": [value for value in orig_steps if value > 0],
            "orig_negative_steps": [value for value in orig_steps if value < 0],
            "orig_step_events": orig_step_events,
            "used_first_kb": system_rows[0]["zram_used_kb"],
            "used_last_kb": system_rows[-1]["zram_used_kb"],
            "used_total_delta_kb": delta(system_rows[-1], system_rows[0], "zram_used_kb"),
            "used_positive_steps": [value for value in used_steps if value > 0],
            "used_negative_steps": [value for value in used_steps if value < 0],
            "used_step_events": used_step_events,
        },
    }

    args.output.mkdir(parents=True, exist_ok=True)
    table_path = args.output / "cyclic_rounds.tsv"
    with table_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    comparison_rows = []
    for row in [item for item in output_rows if item["target"] == "ServiceA"]:
        nominal = [
            item
            for item in per_target["ServiceA"]
            if item["stage"] == row["round"]
        ]
        comparison_rows.append(
            {
                "round": row["round"],
                "wall_clock_round_minflt_delta": row["minflt_round"],
                "boundary_to_peak_minflt_delta": row["minflt_start_to_peak"],
                "rise_10_to_90_minflt_delta": row["minflt_rise_10_to_90"],
                "nominal_stage_minflt_delta": delta(nominal[-1], nominal[0], "minflt"),
                "wall_round_majflt_delta": row["majflt_round"],
                "rise_10_to_90_majflt_delta": row["majflt_rise_10_to_90"],
                "nominal_stage_majflt_delta": delta(nominal[-1], nominal[0], "majflt"),
            }
        )
    with (args.output / "serviceA_fault_boundary_comparison.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(comparison_rows[0]),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(comparison_rows)
    (args.output / "cyclic_quality.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    service_a = [row for row in output_rows if row["target"] == "ServiceA"]
    print("ServiceA")
    for row in service_a:
        print(
            row["round"],
            f"P-V={row['peak_to_valley_kb']}kB",
            f"zorig={row['zram_orig_peak_to_valley_bytes']}B",
            f"zused={row['zram_used_peak_to_valley_kb']}kB",
            f"minflt_rise={row['minflt_start_to_peak']}",
            f"majflt_fall={row['majflt_peak_to_valley']}",
        )
    print("median_P-V_kB", statistics.median(int(row["peak_to_valley_kb"]) for row in service_a))
    print("zram_total", summary["zram"]["orig_total_delta_bytes"], summary["zram"]["used_total_delta_kb"])
    print("missing_rows", missing_rows, "pid_changes", pid_changes)


if __name__ == "__main__":
    main()
