#!/usr/bin/env python3
"""Validate and compact the 2026-09-04 Tizen native evidence B2 run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS / "analysis"))
from trimmable_estimator import EstimatorError, estimate_xml  # noqa: E402


class AnalysisError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AnalysisError(message)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    require(bool(rows), f"empty TSV: {path}")
    return rows


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_idle_log(path: Path) -> list[dict[str, int]]:
    pattern = re.compile(r"^(\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$")
    rows = []
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        match = pattern.fullmatch(raw.rstrip("\r"))
        if match:
            values = list(map(int, match.groups()))
            rows.append(dict(zip(
                ("sample", "epoch_ns", "pid", "starttime_ticks", "glibc_heap_pd_kb",
                 "other_anon_pd_kb", "total_pd_kb"), values
            )))
    require([row["sample"] for row in rows] == list(range(61)), "idle samples are not 0..60")
    require(len({(r["pid"], r["starttime_ticks"]) for r in rows}) == 1, "idle PID changed")
    return rows


def parse_m7(path: Path) -> dict[str, int]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise AnalysisError(f"bad malloc_info XML: {exc}") from exc
    require(root.tag == "malloc", "malloc_info root is not <malloc>")
    totals = {item.attrib["type"]: item for item in root.findall("total")}
    require("fast" in totals and "rest" in totals, "malloc_info missing top-level totals")
    return {
        "arena_count": len(root.findall("heap")),
        "fast_bytes": int(totals["fast"].attrib["size"]),
        "rest_bytes": int(totals["rest"].attrib["size"]),
        "unsorted_bytes": sum(
            int(item.attrib["total"]) for item in root.findall("./heap/sizes/unsorted")
        ),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(pull: Path, idle_log: Path, output: Path) -> dict:
    cells = read_tsv(pull / "formal_cells.tsv")
    require([row["cell"] for row in cells] ==
            ["T1_1", "T1_2", "T1_3", "T1_4", "T1_5", "E4_PRIME"],
            "unexpected formal cell sequence")
    derived = []
    for row in cells:
        pre = int(row["project_pre_kb"])
        post = int(row["project_post_kb"])
        memps_pre = int(row["memps_pre_heap_kb"])
        memps_post = int(row["memps_post_heap_kb"])
        require((pre, post) == (memps_pre, memps_post), f"memps mismatch: {row['cell']}")
        require(int(row["trim_return"]) in (0, 1), f"bad trim return: {row['cell']}")
        if row["group"] == "T1":
            require(int(row["buffers_post"]) > int(row["buffers_pre"]), f"buffers stalled: {row['cell']}")
            require(row["process_exit_code"] == "0" and row["error_lines"] == "0",
                    f"pipeline unhealthy: {row['cell']}")
        derived.append({
            "group": row["group"],
            "cell": row["cell"],
            "pid": int(row["pid"]),
            "starttime_ticks": int(row["starttime_ticks"]),
            "project_pre_kb": pre,
            "project_post_kb": post,
            "memps_pre_heap_kb": memps_pre,
            "memps_post_heap_kb": memps_post,
            "memps_exact_match": "true",
            "reclaimed_kb": pre - post,
            "trim_return": int(row["trim_return"]),
            "injection_ms": row["injection_ms"],
            "minflt_delta": int(row["minflt_post"]) - int(row["minflt_pre"]),
            "majflt_delta": int(row["majflt_post"]) - int(row["majflt_pre"]),
            "buffers_pre": row["buffers_pre"],
            "buffers_post": row["buffers_post"],
            "process_exit_code": row["process_exit_code"],
            "error_lines": row["error_lines"],
        })

    intervals = read_tsv(pull / "formal_intervals.tsv")
    require([row["cell"] for row in intervals] == [f"T1_{i}" for i in range(1, 6)],
            "unexpected interval sequence")
    interval_values = []
    for index, row in enumerate(intervals):
        if index == 0:
            require(row["pass"] == "NA", "first interval must be NA")
            continue
        value = int(row["interval_ns"])
        require(value >= 120_000_000_000 and row["pass"] == "true",
                f"interval below 120 s: {row['cell']}")
        interval_values.append(value)

    app_rows = read_tsv(pull / "formal_app_cycles.tsv")
    require([int(row["cycle"]) for row in app_rows] == list(range(1, 6)),
            "unexpected app cycle sequence")
    for row in app_rows:
        require(row["app_id"] == "setting-myaccount-efl", "app ID changed")
        require(row["launch_rc"] == "0" and row["alive_after_30s"] == "true",
                f"app launch/alive failed: {row['cycle']}")
        require(row["terminate_rc"] == "0" and row["absent_after_2s"] == "true",
                f"app terminate failed: {row['cycle']}")

    recon_rows = read_tsv(pull / "recon_gst_sequence.tsv")
    require(len(recon_rows) == 5, "GST recon did not have five cells")
    for row in recon_rows:
        require(float(row["duration_s"]) >= 60.0, "GST recon cell under 60 s")
        require(int(row["buffer_messages"]) > 0 and row["exit_code"] == "0" and row["error_lines"] == "0",
                "GST recon cell failed")
    recon_span_ns = int(recon_rows[-1]["end_ns"]) - int(recon_rows[0]["start_ns"])
    require(recon_span_ns >= 300_000_000_000, "GST recon span under five minutes")

    idle_rows = parse_idle_log(idle_log)
    m7 = parse_m7(pull / "malloc_info_E4_PRIME.xml")
    try:
        estimate = estimate_xml(pull / "malloc_info_E4_PRIME.xml")
    except EstimatorError as exc:
        raise AnalysisError(str(exc)) from exc

    health = pull / "health"
    before_zram = health.joinpath("zram_before.txt").read_text().split()
    after_zram = health.joinpath("zram_after.txt").read_text().split()
    require(len(before_zram) >= 3 and len(before_zram) == len(after_zram), "bad zram snapshots")
    zram_delta = [int(after_zram[i]) - int(before_zram[i]) for i in range(3)]
    require(zram_delta == [0, 0, 0], "zram validity gate failed")
    dmesg_before = health / "dmesg_before.txt"
    dmesg_after = health / "dmesg_after.txt"
    dmesg_equal = dmesg_before.read_bytes() == dmesg_after.read_bytes()
    require(dmesg_equal, "dmesg changed")
    stability_before = set(health.joinpath("stability_before.tsv").read_text().splitlines())
    stability_after = set(health.joinpath("stability_after.tsv").read_text().splitlines())
    new_stability = sorted(stability_after - stability_before)
    require(not new_stability, "new stability-monitor livedump")
    governors = health.joinpath("governor_after.txt").read_text().splitlines()
    require(governors == ["schedutil"] * 4, "governor restoration failed")
    require(health.joinpath("controller_exit.txt").read_text().strip() == "controller_rc=0",
            "controller exit was not zero")

    output.mkdir(parents=True, exist_ok=True)
    derived_fields = list(derived[0])
    write_tsv(output / "cells_derived.tsv", derived_fields, derived)
    write_tsv(output / "intervals.tsv", list(intervals[0]), intervals)
    write_tsv(output / "app_cycles.tsv", list(app_rows[0]), app_rows)
    write_tsv(output / "recon_gst_sequence.tsv", list(recon_rows[0]), recon_rows)
    write_tsv(output / "enlightenment_idle.tsv", list(idle_rows[0]), idle_rows)
    write_tsv(output / "m7.tsv", ["cell", *m7], [{"cell": "E4_PRIME", **m7}])
    shutil.copyfile(pull / "malloc_info_E4_PRIME.xml", output / "malloc_info_E4_PRIME.xml")
    estimate["source"] = "malloc_info_E4_PRIME.xml"
    with (output / "estimator_E4_PRIME.json").open("w", encoding="utf-8") as handle:
        json.dump(estimate, handle, indent=2, sort_keys=True)
        handle.write("\n")

    t1 = derived[:5]
    e4 = derived[5]
    summary = {
        "schema": "glibc-memopt.tizen-native-evidence-b2.summary.v2",
        "completion": {
            "t1_prime_completed": 5,
            "t1_prime_fixed_contract": 5,
            "e4_app_cycles_completed": 5,
            "e4_app_cycles_fixed_contract": 5,
            "e4_prime_completed": 1,
            "e4_prime_fixed_contract": 1,
        },
        "reconnaissance": {
            "enlightenment_idle_samples": len(idle_rows),
            "enlightenment_idle_glibc_heap_pd_min_kb": min(r["glibc_heap_pd_kb"] for r in idle_rows),
            "enlightenment_idle_glibc_heap_pd_max_kb": max(r["glibc_heap_pd_kb"] for r in idle_rows),
            "gst_sequence_cells": len(recon_rows),
            "gst_sequence_span_s": round(recon_span_ns / 1e9, 9),
            "app_id": "setting-myaccount-efl",
        },
        "t1_prime": {
            "reclaimed_kb": [r["reclaimed_kb"] for r in t1],
            "injection_ms": [float(r["injection_ms"]) for r in t1],
            "injection_ms_median": statistics.median(float(r["injection_ms"]) for r in t1),
            "interval_s": [round(value / 1e9, 9) for value in interval_values],
            "interval_min_s": round(min(interval_values) / 1e9, 9),
            "interval_max_s": round(max(interval_values) / 1e9, 9),
            "memps_exact_match_count": sum(r["memps_exact_match"] == "true" for r in t1),
            "majflt_delta": [r["majflt_delta"] for r in t1],
        },
        "e4_prime": {
            "app_cycles": 5,
            "m7": m7,
            "project_pre_kb": e4["project_pre_kb"],
            "project_post_kb": e4["project_post_kb"],
            "reclaimed_kb": e4["reclaimed_kb"],
            "memps_exact_match": True,
            "trim_return": e4["trim_return"],
            "injection_ms": float(e4["injection_ms"]),
            "minflt_delta": e4["minflt_delta"],
            "majflt_delta": e4["majflt_delta"],
            "estimator_lower_bytes": estimate["total"]["lower_bytes"],
            "estimator_upper_bytes": estimate["total"]["upper_bytes"],
        },
        "health": {
            "zram_original_compressed_used_delta": zram_delta,
            "dmesg_before_after_sha256": file_sha256(dmesg_before),
            "dmesg_exactly_equal": dmesg_equal,
            "stability_monitor_new_livedumps": len(new_stability),
            "governor_final_schedutil_cores": governors.count("schedutil"),
            "controller_exit_code": 0,
        },
    }
    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pull", type=Path, required=True)
    parser.add_argument("--idle-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = analyze(args.pull, args.idle_log, args.output)
    except (AnalysisError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
