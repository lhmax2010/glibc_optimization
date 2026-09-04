#!/usr/bin/env python3
"""Evaluate S4/gst derivatives against the shared Demo acceptance contract."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def add(results: list[dict[str, object]], status: str, item: str, observed: object, expected: object) -> None:
    results.append({"status": status, "item": item, "observed": observed, "expected": expected})


def in_band(value: float, center: float, radius: float) -> bool:
    return center - radius <= value <= center + radius


def nearest_rank(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(1, math.ceil(quantile * len(ordered))) - 1]


def evaluate_s4(summary: dict[str, object], bands: dict[str, object], results: list[dict[str, object]]) -> None:
    tolerance = bands["tolerance_bands"]
    anchor_band = tolerance["s4_a_anchor_reclaim_pct"]
    for profile, value in summary["a_anchor_reclaim_pct"].items():
        center = float(anchor_band["center_pct_by_profile"][profile])
        radius = float(anchor_band["plus_minus_pp_by_profile"][profile])
        passed = in_band(float(value), center, radius)
        add(
            results,
            "PASS" if passed else "FAIL",
            f"S4 A {profile} reclaim",
            f"{value}%",
            f"{center:.6f}% ±{radius:.6f} pp",
        )
    b_band = tolerance["s4_b_reclaim_pct_repeat_median"]
    for profile, value in summary["b_reclaim_pct_repeat_median"].items():
        center = float(b_band["center_pct_by_profile"][profile])
        passed = in_band(float(value), center, float(b_band["plus_minus_pp"]))
        add(results, "PASS" if passed else "FAIL", f"S4 B {profile} three-repeat median", f"{value}%", f"{center:.6f}% ±5 pp")
    a_limit = float(tolerance["s4_a_anchor_trim_single_call_ms"]["max_exclusive_ms"])
    b_limit = float(tolerance["release_point_trim_single_call_ms"]["max_exclusive_ms"])
    a_time = float(summary["a_anchor_trim_max_ms"])
    b_time = float(summary["b_release_point_trim_max_ms"])
    add(results, "PASS" if a_time < a_limit else "FAIL", "S4 A anchor trim max", f"{a_time} ms", f"<{a_limit:g} ms (not hook cost)")
    add(results, "PASS" if b_time < b_limit else "FAIL", "S4 B release-point trim max", f"{b_time} ms", f"<{b_limit:g} ms")

    expected_payload = bands["deterministic_items"]["released_payload_bytes"]["expected_by_profile_cycle"]
    add(results, "PASS" if summary["released_payload_bytes"] == expected_payload else "FAIL", "S4 released payload bytes", summary["released_payload_bytes"], expected_payload)
    reference = bands["banded_references"]["s4_b_trim_reclaimed_kb_per_cycle"]
    observed_reclaim = summary["trim_reclaimed_kb_by_profile_rep_cycle"]
    published_reclaim = reference["published_by_profile_rep_cycle"]
    radius = int(reference["plus_minus_kb"])
    reclaim_in_band = all(
        abs(int(value) - int(published_reclaim[profile][rep][cycle])) <= radius
        for profile, repetitions in observed_reclaim.items()
        for rep, values in repetitions.items()
        for cycle, value in enumerate(values)
    )
    add(results, "PASS" if reclaim_in_band else "FAIL", "S4 per-cycle reclaimed KiB banded reference", observed_reclaim, f"published ±{radius} KiB")
    aligned = int(summary["reclaimed_4k_aligned_count"])
    aligned_total = int(summary["reclaimed_4k_aligned_total"])
    add(results, "PASS" if aligned == aligned_total else "FAIL", "S4 reclaimed bytes page alignment", f"{aligned}/{aligned_total}", "all 4096-byte aligned")
    majflt = int(summary["next_cycle_majflt_max"])
    add(results, "PASS" if majflt == 0 else "FAIL", "S4 next-cycle majflt", majflt, 0)
    zram = summary["zram_deltas"]
    add(results, "PASS" if all(int(value) == 0 for value in zram.values()) else "FAIL", "S4 zram deltas", zram, "all zero")
    oom = int(summary["dmesg_oom_lmk_matches"])
    add(results, "PASS" if oom == 0 else "FAIL", "S4 dmesg OOM/LMK", oom, 0)


def evaluate_gst(gst: Path, bands: dict[str, object], results: list[dict[str, object]]) -> None:
    comparison = json.loads((gst / "comparison.json").read_text(encoding="utf-8"))
    cycles = rows(gst / "cycles.tsv")
    repetitions = rows(gst / "repetitions.tsv")
    health = json.loads((gst / "health.json").read_text(encoding="utf-8"))
    trim = [row for row in cycles if row["arm"] == "trim-at-loop-release"]
    primary = [row for row in cycles if row["primary_business_sample"] == "1"]
    limit = float(bands["tolerance_bands"]["release_point_trim_single_call_ms"]["max_exclusive_ms"])
    maximum = max(float(row["trim_elapsed_ms"]) for row in trim)
    add(results, "PASS" if maximum < limit else "FAIL", "gst release-point trim max", f"{maximum} ms", f"<{limit:g} ms")
    p99_by_arm: dict[str, list[float]] = {"none": [], "trim-at-loop-release": []}
    rule_valid = comparison.get("percentile_method") == bands["tolerance_bands"]["gst_business_p99"]["percentile_method"]
    for row in repetitions:
        arm, rep = row["arm"], row["rep"]
        values = [
            float(item["business_elapsed_ms"])
            for item in cycles
            if item["arm"] == arm and item["rep"] == rep and item["primary_business_sample"] == "1"
        ]
        computed = nearest_rank(values, 0.99)
        rule_valid = rule_valid and math.isclose(computed, float(row["business_p99_ms"]), abs_tol=5e-7)
        p99_by_arm[arm].append(computed)
    none_median = statistics.median(p99_by_arm["none"])
    trim_median = statistics.median(p99_by_arm["trim-at-loop-release"])
    delta = trim_median - none_median
    dispersion = max(p99_by_arm["none"]) - min(p99_by_arm["none"])
    visible = delta > dispersion
    rule_valid = rule_valid and all((
        math.isclose(delta, float(comparison["delta_p99_ms"]), abs_tol=5e-7),
        math.isclose(dispersion, float(comparison["none_p99_repeat_dispersion_ms"]), abs_tol=5e-7),
        visible is bool(comparison["business_cost_visible"]),
    ))
    add(
        results,
        "PASS" if rule_valid else "FAIL",
        "gst fixed-contract p99 rule execution",
        f"method={comparison.get('percentile_method')} delta={delta:.6f} dispersion={dispersion:.6f}",
        "nearest-rank; repeat medians; none max-minus-min; strict > comparison",
    )
    add(
        results,
        "REPORT_ONLY",
        "gst fixed-contract p99 direction",
        f"visible={str(visible).lower()} delta={comparison['delta_p99_ms']} dispersion={comparison['none_p99_repeat_dispersion_ms']}",
        "report outcome; never an acceptance failure",
    )
    majflt = max(int(row["cycle_majflt"]) for row in primary)
    add(results, "PASS" if majflt == 0 else "FAIL", "gst primary-cycle majflt", majflt, 0)
    zram_fields = (
        "zram_original_data_size_delta",
        "zram_compressed_data_size_delta",
        "zram_mem_used_total_delta",
    )
    zram = {field: int(health[field]) for field in zram_fields}
    add(results, "PASS" if all(value == 0 for value in zram.values()) else "FAIL", "gst zram deltas", zram, "all zero")
    oom = len(health["oom_lmk_matches"])
    add(results, "PASS" if oom == 0 else "FAIL", "gst dmesg OOM/LMK", oom, 0)


def evaluate_stability(paths: list[Path], bands: dict[str, object], results: list[dict[str, object]]) -> None:
    registration = bands["stability_monitor"]["expected_alerts"][0]
    add(
        results,
        "REGISTERED/NOT-EVALUATED",
        f"stability registration {registration['id']}",
        f"max={registration['max_count_total']} trigger={registration['trigger_reason_contains']}",
        "known-alert waiver: record/archive/exact cleanup/recheck only when observed",
    )
    if not paths:
        return
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for alert in payload.get("alerts", []):
            status = alert["verdict"]
            if status not in ("EXPECTED", "FAIL", "REPORT_ONLY"):
                status = "FAIL"
            add(results, status, f"stability alert {alert.get('remote_path', 'unknown')}", alert.get("reason", ""), alert.get("explanation", "v2 classification"))
        post_count = int(payload.get("expected_paths_present_after_cleanup", 0))
        add(results, "PASS" if post_count == 0 else "FAIL", f"expected-alert cleanup recheck ({path.name})", post_count, 0)


def print_table(results: list[dict[str, object]]) -> None:
    widths = [max(len(str(row[key])) for row in results + [{"status": "STATUS", "item": "ITEM", "observed": "OBSERVED", "expected": "EXPECTED"}]) for key in ("status", "item", "observed", "expected")]
    print(" | ".join(value.ljust(width) for value, width in zip(("STATUS", "ITEM", "OBSERVED", "EXPECTED"), widths)))
    print("-+-".join("-" * width for width in widths))
    for row in results:
        print(" | ".join(str(row[key]).ljust(width) for key, width in zip(("status", "item", "observed", "expected"), widths)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bands", required=True, type=Path)
    parser.add_argument("--s4-summary", required=True, type=Path)
    parser.add_argument("--gst-derived", required=True, type=Path)
    parser.add_argument("--stability", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    bands = json.loads(args.bands.read_text(encoding="utf-8"))
    summary = json.loads(args.s4_summary.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    evaluate_s4(summary, bands, results)
    evaluate_gst(args.gst_derived, bands, results)
    evaluate_stability(args.stability, bands, results)
    print_table(results)
    outcome = "FAIL" if any(row["status"] == "FAIL" for row in results) else "PASS"
    payload = {"schema": "glibc-memopt-demo.acceptance-result.v4", "outcome": outcome, "results": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OVERALL {outcome}")
    return 1 if outcome == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
