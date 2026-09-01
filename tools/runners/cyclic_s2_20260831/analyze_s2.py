#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--pull", type=Path, required=True, help="pulled board work directory")
parser.add_argument("--output", type=Path, required=True, help="derived output directory")
args = parser.parse_args()
PULL = args.pull
DERIVED = args.output
DERIVED.mkdir(parents=True, exist_ok=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_external(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    integer_fields = (
        "sample",
        "epoch_ns",
        "pid",
        "glibc_heap_pd_kb",
        "other_anon_pd_kb",
        "file_backed_pd_kb",
        "total_pd_kb",
        "minflt",
        "majflt",
    )
    for row in rows:
        row["elapsed_s"] = float(row["elapsed_s"])
        for field in integer_fields:
            row[field] = int(row[field])
    require(rows, f"empty external sequence: {path}")
    require(
        [row["sample"] for row in rows] == list(range(len(rows))),
        f"non-contiguous sample indices: {path}",
    )
    require(
        all(left["elapsed_s"] < right["elapsed_s"] for left, right in zip(rows, rows[1:])),
        f"non-monotonic elapsed_s: {path}",
    )
    require(len({row["pid"] for row in rows}) == 1, f"PID changed: {path}")
    return rows


def median(values):
    return statistics.median(values)


internal_rows = []
external_rows = []
summaries = {}

for profile in ("mixed", "medium-only"):
    with (PULL / profile / "result.json").open() as stream:
        result = json.load(stream)
    cycle_data = result.get("cycle_data")
    require(isinstance(cycle_data, list), f"missing cycle_data: {profile}")
    require(len(cycle_data) == 8, f"expected 8 cycles: {profile}")
    cycle_numbers = [item.get("cycle") for item in cycle_data]
    require(set(cycle_numbers) == set(range(1, 9)), f"cycles must be exactly 1..8: {profile}")
    require(len(cycle_numbers) == len(set(cycle_numbers)), f"duplicate cycles: {profile}")
    cycle_data = sorted(cycle_data, key=lambda item: item["cycle"])
    samples = read_external(PULL / profile / "external_1s.tsv")
    period = (
        result["cycle_rise_s"]
        + result["cycle_peak_s"]
        + result["release_duration_s"]
        + result["cycle_valley_s"]
    )
    profile_external = []

    for item in cycle_data:
        cycle = item["cycle"]
        cycle_start = (cycle - 1) * period
        peak_start = cycle_start + result["cycle_rise_s"]
        peak_end = peak_start + result["cycle_peak_s"]
        valley_start = peak_end + result["release_duration_s"]
        cycle_end = cycle_start + period
        cycle_samples = [row for row in samples if cycle_start <= row["elapsed_s"] < cycle_end]
        peak_samples = [row for row in cycle_samples if peak_start <= row["elapsed_s"] < peak_end]
        valley_samples = [row for row in cycle_samples if valley_start <= row["elapsed_s"] < cycle_end]
        if not cycle_samples or not peak_samples or not valley_samples:
            raise RuntimeError(f"incomplete external window for {profile} cycle {cycle}")

        external_peak = max(row["glibc_heap_pd_kb"] for row in peak_samples)
        external_valley = min(row["glibc_heap_pd_kb"] for row in valley_samples)
        external_other_peak = max(row["other_anon_pd_kb"] for row in peak_samples)
        external_other_valley = min(row["other_anon_pd_kb"] for row in valley_samples)
        start_value = cycle_samples[0]["glibc_heap_pd_kb"]
        excursion = external_peak - start_value
        rise_detected = None
        peak_band_min = None
        fall_detected = False
        fall_s = None
        if excursion > 0:
            low = start_value + 0.10 * excursion
            high = start_value + 0.90 * excursion
            before_low = cycle_samples[0]
            high_row = None
            for row in cycle_samples:
                if row["elapsed_s"] >= peak_end:
                    break
                if row["glibc_heap_pd_kb"] < low:
                    before_low = row
                if high_row is None and row["glibc_heap_pd_kb"] >= high:
                    high_row = row
            if high_row is not None:
                rise_detected = high_row["elapsed_s"] - before_low["elapsed_s"]
                fall_row = next(
                    (
                        row
                        for row in cycle_samples
                        if row["elapsed_s"] > high_row["elapsed_s"]
                        and row["glibc_heap_pd_kb"] < high
                    ),
                    None,
                )
                if fall_row is None:
                    peak_band_min = cycle_samples[-1]["elapsed_s"] - high_row["elapsed_s"]
                else:
                    fall_detected = True
                    peak_band_min = fall_row["elapsed_s"] - high_row["elapsed_s"]
                    later = [row for row in cycle_samples if row["elapsed_s"] >= fall_row["elapsed_s"]]
                    valley_row = min(later, key=lambda row: row["glibc_heap_pd_kb"])
                    fall_s = valley_row["elapsed_s"] - fall_row["elapsed_s"]

        heap = item["heap"]
        faults = item["faults"]
        internal_rows.append(
            {
                "profile": profile,
                "cycle": cycle,
                "internal_start_kb": heap["start"]["glibc_heap_pd_kb"],
                "internal_peak_kb": heap["peak"]["glibc_heap_pd_kb"],
                "internal_fall_mid_kb": heap["fall_mid"]["glibc_heap_pd_kb"],
                "internal_valley_kb": heap["valley"]["glibc_heap_pd_kb"],
                "internal_peak_minus_valley_kb": item["peak_valley_glibc_heap_kb"],
                "rise_elapsed_s": round(item["rise_elapsed_ns"] / 1e9, 6),
                "release_elapsed_s": round(item["release_elapsed_ns"] / 1e9, 6),
                "released_payload_bytes": item["released_payload_bytes"],
                "m7_rest_delta_bytes": item["m7_rest_delta_bytes"],
                "m7_unsorted_delta_bytes": item["m7_unsorted_delta_bytes"],
                "rise_minflt": faults["rise_minflt"],
                "rise_majflt": faults["rise_majflt"],
                "next_cycle_minflt": faults["next_cycle_minflt"],
                "next_cycle_majflt": faults["next_cycle_majflt"],
            }
        )
        row = {
            "profile": profile,
            "cycle": cycle,
            "samples": len(cycle_samples),
            "scheduled_start_s": round(cycle_start, 3),
            "external_start_kb": start_value,
            "external_peak_window_max_kb": external_peak,
            "external_valley_window_min_kb": external_valley,
            "external_peak_minus_valley_kb": external_peak - external_valley,
            "external_other_peak_window_max_kb": external_other_peak,
            "external_other_valley_window_min_kb": external_other_valley,
            "signal_rise_s": None if rise_detected is None else round(rise_detected, 6),
            "signal_peak_band_s_min": None if peak_band_min is None else round(peak_band_min, 6),
            "signal_peak_band_censored": not fall_detected,
            "signal_fall_s": None if fall_s is None else round(fall_s, 6),
            "fall_observed": fall_detected,
        }
        external_rows.append(row)
        profile_external.append(row)

    profile_internal = [row for row in internal_rows if row["profile"] == profile]
    summaries[profile] = {
        "internal_peak_minus_valley_median_kb": median(
            [row["internal_peak_minus_valley_kb"] for row in profile_internal]
        ),
        "external_peak_minus_valley_median_kb": median(
            [row["external_peak_minus_valley_kb"] for row in profile_external]
        ),
        "internal_rise_median_s": round(
            median([item["rise_elapsed_ns"] / 1e9 for item in cycle_data]), 6
        ),
        "internal_release_median_s": round(
            median([item["release_elapsed_ns"] / 1e9 for item in cycle_data]), 6
        ),
        "released_payload_median_bytes": median(
            [row["released_payload_bytes"] for row in profile_internal]
        ),
        "m7_rest_delta_median_bytes": median(
            [row["m7_rest_delta_bytes"] for row in profile_internal]
        ),
        "m7_unsorted_delta_median_bytes": median(
            [row["m7_unsorted_delta_bytes"] for row in profile_internal]
        ),
        "internal_valley_cycle1_kb": profile_internal[0]["internal_valley_kb"],
        "internal_valley_cycle8_kb": profile_internal[-1]["internal_valley_kb"],
        "internal_valley_cycle1_to_8_kb": (
            profile_internal[-1]["internal_valley_kb"]
            - profile_internal[0]["internal_valley_kb"]
        ),
        "external_valley_cycle1_kb": profile_external[0]["external_valley_window_min_kb"],
        "external_valley_cycle8_kb": profile_external[-1]["external_valley_window_min_kb"],
        "external_valley_cycle1_to_8_kb": (
            profile_external[-1]["external_valley_window_min_kb"]
            - profile_external[0]["external_valley_window_min_kb"]
        ),
        "external_samples": len(samples),
        "external_minflt_delta": samples[-1]["minflt"] - samples[0]["minflt"],
        "external_majflt_delta": samples[-1]["majflt"] - samples[0]["majflt"],
        "internal_rise_minflt_sum": sum(row["rise_minflt"] for row in profile_internal),
        "internal_rise_majflt_sum": sum(row["rise_majflt"] for row in profile_internal),
        "signal_falls_observed": sum(row["fall_observed"] for row in profile_external),
    }


def write_tsv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


write_tsv(DERIVED / "internal_cycles.tsv", internal_rows)
write_tsv(DERIVED / "external_cycles.tsv", external_rows)
with (DERIVED / "summary.json").open("w") as stream:
    json.dump(summaries, stream, indent=2, sort_keys=True)
    stream.write("\n")
