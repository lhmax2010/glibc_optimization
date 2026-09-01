#!/usr/bin/env python3
"""Recompute ServiceA bucket-migration and fall-edge evidence from raw TSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


INTEGER_FIELDS = {
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows: list[dict[str, Any]] = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty TSV: {path}")
    for row in rows:
        for field in INTEGER_FIELDS.intersection(row):
            require(row[field] not in {"", "NA"}, f"missing {field} in {path}")
            row[field] = int(row[field])
    return rows


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), f"no rows for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def planned_start_ns(key_rows: list[dict[str, Any]]) -> tuple[int, int]:
    estimates = sorted(
        int(row["actual_epoch_ns"])
        - int(row["target_offset_s"]) * 1_000_000_000
        - round(float(row["lateness_ms"]) * 1_000_000)
        for row in key_rows
    )
    middle = len(estimates) // 2
    if len(estimates) % 2:
        median_ns = estimates[middle]
    else:
        median_ns = (estimates[middle - 1] + estimates[middle]) // 2
    return median_ns, estimates[-1] - estimates[0]


def source_definition(analyzer_path: Path) -> dict[str, Any]:
    lines = analyzer_path.read_text(encoding="utf-8").splitlines()
    needles = {
        "fall_index": "fall_index = next(",
        "valley": "valley = min(sequence[fall_index:]",
        "peak_band": "peak_seconds = fall[\"elapsed_s\"] - high_entry[\"elapsed_s\"]",
        "fall_edge": "fall_seconds = valley[\"elapsed_s\"] - fall[\"elapsed_s\"]",
    }
    result: dict[str, Any] = {"sha256": sha256(analyzer_path)}
    for name, needle in needles.items():
        matches = [index + 1 for index, line in enumerate(lines) if needle in line]
        require(len(matches) == 1, f"definition {name} not uniquely found")
        result[f"{name}_line"] = matches[0]
        result[f"{name}_source"] = lines[matches[0] - 1].strip()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeseries", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    parser.add_argument("--published-analyzer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    all_rows = read_tsv(args.timeseries)
    keys = read_tsv(args.keys)
    service_a = sorted(
        (row for row in all_rows if row["target"] == "ServiceA"),
        key=lambda row: row["epoch_ns"],
    )
    require(len(service_a) == 660, "ServiceA must have 660 samples")
    require(
        [row["sample"] for row in service_a] == list(range(660)),
        "ServiceA sample sequence is not contiguous",
    )
    require(
        len({row["pid"] for row in service_a}) == 1,
        "ServiceA PID changed",
    )

    large_steps: list[dict[str, Any]] = []
    for previous, current in zip(service_a, service_a[1:]):
        glibc_delta = current["glibc_heap_pd_kb"] - previous["glibc_heap_pd_kb"]
        if abs(glibc_delta) < 100:
            continue
        other_delta = current["other_anon_pd_kb"] - previous["other_anon_pd_kb"]
        total_delta = current["total_pd_kb"] - previous["total_pd_kb"]
        opposite = glibc_delta * other_delta < 0
        magnitude_ratio = abs(other_delta) / abs(glibc_delta)
        large_steps.append(
            {
                "from_sample": previous["sample"],
                "to_sample": current["sample"],
                "glibc_delta_kb": glibc_delta,
                "other_anon_delta_kb": other_delta,
                "total_pd_delta_kb": total_delta,
                "opposite_direction": int(opposite),
                "other_to_glibc_abs_ratio": f"{magnitude_ratio:.6f}",
                "near_equal_within_20pct": int(opposite and 0.8 <= magnitude_ratio <= 1.2),
                "near_equal_within_50pct": int(opposite and 0.5 <= magnitude_ratio <= 1.5),
                "release_total_pd_fell": int(glibc_delta < 0 and total_delta < 0),
            }
        )

    start_ns, start_estimate_spread_ns = planned_start_ns(keys)
    for row in service_a:
        row["elapsed_s"] = (row["epoch_ns"] - start_ns) / 1_000_000_000

    fall_rows: list[dict[str, Any]] = []
    for round_number in range(1, 9):
        round_name = f"R{round_number}"
        round_start_s = round_number * 60
        round_end_s = round_start_s + 60
        body = [
            row
            for row in service_a
            if round_start_s <= row["elapsed_s"] < round_end_s
        ]
        boundary_rows = [row for row in service_a if row["elapsed_s"] < round_start_s]
        require(bool(body) and bool(boundary_rows), f"incomplete {round_name} window")
        sequence = [boundary_rows[-1], *body]
        peak = max(body, key=lambda row: row["glibc_heap_pd_kb"])
        peak_index = sequence.index(peak)
        excursion = peak["glibc_heap_pd_kb"] - sequence[0]["glibc_heap_pd_kb"]
        high_cut = sequence[0]["glibc_heap_pd_kb"] + 0.90 * excursion
        fall_index = next(
            (
                index
                for index in range(peak_index + 1, len(sequence))
                if sequence[index]["glibc_heap_pd_kb"] < high_cut
            ),
            len(sequence) - 1,
        )
        fall_start = sequence[fall_index]
        valley = min(
            sequence[fall_index:],
            key=lambda row: row["glibc_heap_pd_kb"],
        )
        total_release_kb = peak["glibc_heap_pd_kb"] - valley["glibc_heap_pd_kb"]
        require(total_release_kb > 0, f"{round_name} has no peak-to-valley release")
        release_before_fall_start_kb = (
            peak["glibc_heap_pd_kb"] - fall_start["glibc_heap_pd_kb"]
        )
        valley_band_ceiling_kb = valley["glibc_heap_pd_kb"] + 0.05 * total_release_kb
        valley_band_entry = next(
            row
            for row in sequence[peak_index:]
            if row["glibc_heap_pd_kb"] <= valley_band_ceiling_kb
        )
        fall_rows.append(
            {
                "round": round_name,
                "peak_sample": peak["sample"],
                "peak_glibc_kb": peak["glibc_heap_pd_kb"],
                "fall_start_sample": fall_start["sample"],
                "fall_start_glibc_kb": fall_start["glibc_heap_pd_kb"],
                "valley_sample": valley["sample"],
                "valley_glibc_kb": valley["glibc_heap_pd_kb"],
                "total_release_kb": total_release_kb,
                "release_before_fall_start_kb": release_before_fall_start_kb,
                "release_before_fall_start_pct": f"{100 * release_before_fall_start_kb / total_release_kb:.6f}",
                "published_fall_edge_s": f"{valley['elapsed_s'] - fall_start['elapsed_s']:.6f}",
                "valley_5pct_band_ceiling_kb": f"{valley_band_ceiling_kb:.3f}",
                "valley_band_entry_sample": valley_band_entry["sample"],
                "valley_band_entry_glibc_kb": valley_band_entry["glibc_heap_pd_kb"],
                "valley_band_entry_delay_upper_s": f"{valley_band_entry['elapsed_s'] - peak['elapsed_s']:.6f}",
            }
        )

    opposite_steps = [row for row in large_steps if row["opposite_direction"]]
    release_steps = [row for row in large_steps if row["glibc_delta_kb"] < 0]
    fall_edges = [float(row["published_fall_edge_s"]) for row in fall_rows]
    valley_band_delays = [
        float(row["valley_band_entry_delay_upper_s"]) for row in fall_rows
    ]
    summary = {
        "inputs": {
            "timeseries_sha256": sha256(args.timeseries),
            "keys_sha256": sha256(args.keys),
            "published_analyzer": source_definition(args.published_analyzer),
        },
        "quality": {
            "serviceA_rows": len(service_a),
            "serviceA_pid_count": len({row["pid"] for row in service_a}),
            "planned_start_estimate_spread_ns": start_estimate_spread_ns,
        },
        "F2": {
            "large_step_threshold_kb": 100,
            "large_step_count": len(large_steps),
            "growth_step_count": sum(row["glibc_delta_kb"] > 0 for row in large_steps),
            "release_step_count": len(release_steps),
            "opposite_direction_count": len(opposite_steps),
            "opposite_direction_abs_ratios": [
                float(row["other_to_glibc_abs_ratio"]) for row in opposite_steps
            ],
            "near_equal_within_20pct_count": sum(
                row["near_equal_within_20pct"] for row in large_steps
            ),
            "near_equal_within_50pct_count": sum(
                row["near_equal_within_50pct"] for row in large_steps
            ),
            "release_steps_with_total_pd_fall": sum(
                row["release_total_pd_fell"] for row in release_steps
            ),
        },
        "F3": {
            "published_fall_edge_min_s": round(min(fall_edges), 6),
            "published_fall_edge_max_s": round(max(fall_edges), 6),
            "published_fall_edge_median_s": round(statistics.median(fall_edges), 6),
            "valley_band_entry_delay_definition": "observed peak to first sample <= valley + 5% * (peak - valley)",
            "valley_band_entry_delay_is_sampling_upper_bound": True,
            "valley_band_entry_delay_min_s": round(min(valley_band_delays), 6),
            "valley_band_entry_delay_max_s": round(max(valley_band_delays), 6),
            "valley_band_entry_delay_median_s": round(
                statistics.median(valley_band_delays), 6
            ),
        },
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_tsv(args.output / "serviceA_large_steps.tsv", large_steps)
    write_tsv(args.output / "serviceA_fall_recheck.tsv", fall_rows)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
