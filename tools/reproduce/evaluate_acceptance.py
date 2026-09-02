#!/usr/bin/env python3
"""Evaluate S4/gst derivatives against the shared Demo acceptance contract."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def add(results: list[dict[str, object]], status: str, item: str, observed: object, expected: object) -> None:
    results.append({"status": status, "item": item, "observed": observed, "expected": expected})


def in_band(value: float, center: float, radius: float) -> bool:
    return center - radius <= value <= center + radius


def evaluate_s4(summary: dict[str, object], bands: dict[str, object], results: list[dict[str, object]]) -> None:
    tolerance = bands["tolerance_bands"]
    anchor_band = tolerance["s4_a_anchor_reclaim_pct"]
    for profile, value in summary["a_anchor_reclaim_pct"].items():
        passed = in_band(float(value), float(anchor_band["center_pct"]), float(anchor_band["plus_minus_pp"]))
        add(results, "PASS" if passed else "FAIL", f"S4 A {profile} reclaim", f"{value}%", "49% ±4 pp")
    b_band = tolerance["s4_b_reclaim_pct_repeat_median"]
    for profile, value in summary["b_reclaim_pct_repeat_median"].items():
        passed = in_band(float(value), float(b_band["center_pct"]), float(b_band["plus_minus_pp"]))
        add(results, "PASS" if passed else "FAIL", f"S4 B {profile} three-repeat median", f"{value}%", "80% ±5 pp")
    a_limit = float(tolerance["s4_a_anchor_trim_single_call_ms"]["max_exclusive_ms"])
    b_limit = float(tolerance["release_point_trim_single_call_ms"]["max_exclusive_ms"])
    a_time = float(summary["a_anchor_trim_max_ms"])
    b_time = float(summary["b_release_point_trim_max_ms"])
    add(results, "PASS" if a_time < a_limit else "FAIL", "S4 A anchor trim max", f"{a_time} ms", f"<{a_limit:g} ms (not hook cost)")
    add(results, "PASS" if b_time < b_limit else "FAIL", "S4 B release-point trim max", f"{b_time} ms", f"<{b_limit:g} ms")

    expected_payload = {"mixed": [5742256, 6566672], "medium-only": [6288384, 6293504]}
    add(results, "PASS" if summary["released_payload_bytes"] == expected_payload else "FAIL", "S4 released payload bytes", summary["released_payload_bytes"], expected_payload)
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
    health = json.loads((gst / "health.json").read_text(encoding="utf-8"))
    trim = [row for row in cycles if row["arm"] == "trim-at-loop-release"]
    primary = [row for row in cycles if row["primary_business_sample"] == "1"]
    limit = float(bands["tolerance_bands"]["release_point_trim_single_call_ms"]["max_exclusive_ms"])
    maximum = max(float(row["trim_elapsed_ms"]) for row in trim)
    add(results, "PASS" if maximum < limit else "FAIL", "gst release-point trim max", f"{maximum} ms", f"<{limit:g} ms")
    visible = bool(comparison["business_cost_visible"])
    add(
        results,
        "PASS" if not visible else "FAIL",
        "gst preregistered p99 direction",
        f"visible={str(visible).lower()} delta={comparison['delta_p99_ms']} dispersion={comparison['none_p99_repeat_dispersion_ms']}",
        "not-visible (delta <= none dispersion)",
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
        "EXPECTED",
        f"stability registration {registration['id']}",
        f"max={registration['max_count_total']} trigger={registration['trigger_reason_contains']}",
        "record/archive/exact cleanup/recheck when observed",
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
    payload = {"schema": "glibc-memopt-demo.acceptance-result.v2", "outcome": outcome, "results": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OVERALL {outcome}")
    return 1 if outcome == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
