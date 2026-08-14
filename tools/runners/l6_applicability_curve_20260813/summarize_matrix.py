#!/usr/bin/env python3
import csv
import json
import re
import statistics
import sys
from pathlib import Path


def median(values):
    return statistics.median(values)


def run_metadata(path):
    data = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value
    return data


def derive(result, meta, cell, rep):
    memory = result["memory"]
    mi = memory["malloc_info_stats"]
    faults = memory["faults"]
    pre = memory["glibc_heap_pd_kb_pretrim"]
    post = memory["glibc_heap_pd_kb_posttrim"]
    reclaimed = pre - post
    released_bytes = result["idle_released_bytes"]
    theoretical_kb = result["theoretical_release_kb"]
    return {
        "cell": cell,
        "rep": rep,
        "profile": result["profile"],
        "release_pct": result["idle_release_pct"],
        "live_set": result["live_set_per_thread"],
        "release_order": result["release_order"],
        "exit": int(meta["EXIT"]),
        "memavailable_pre_kb": int(meta["MemAvailable_pre_kB"]),
        "released_objects": result["idle_released_objects"],
        "released_payload_kb": released_bytes / 1024.0,
        "theoretical_release_kb": theoretical_kb,
        "glibc_pd_pretrim_kb": pre,
        "glibc_pd_posttrim_kb": post,
        "a_ceiling_kb": reclaimed,
        "reclaim_pct_of_pretrim": reclaimed * 100.0 / pre if pre else 0.0,
        "return_pct_of_payload": reclaimed * 1024.0 * 100.0 / released_bytes
        if released_bytes else 0.0,
        "theoretical_to_reclaimed_ratio": theoretical_kb / reclaimed
        if reclaimed else 0.0,
        "mi_measure_fast_b": mi["measure"]["fast_bytes"],
        "mi_measure_rest_b": mi["measure"]["rest_bytes"],
        "mi_measure_unsorted_b": mi["measure"]["unsorted_bytes"],
        "mi_release_fast_b": mi["release"]["fast_bytes"],
        "mi_release_rest_b": mi["release"]["rest_bytes"],
        "mi_release_unsorted_b": mi["release"]["unsorted_bytes"],
        "mi_posttrim_fast_b": mi["posttrim"]["fast_bytes"],
        "mi_posttrim_rest_b": mi["posttrim"]["rest_bytes"],
        "mi_posttrim_unsorted_b": mi["posttrim"]["unsorted_bytes"],
        "mi_idle_fast_b": mi["idle"]["fast_bytes"],
        "mi_idle_rest_b": mi["idle"]["rest_bytes"],
        "mi_idle_unsorted_b": mi["idle"]["unsorted_bytes"],
        "mi_release_rest_delta_b": mi["release"]["rest_bytes"]
        - mi["measure"]["rest_bytes"],
        "mi_release_unsorted_delta_b": mi["release"]["unsorted_bytes"]
        - mi["measure"]["unsorted_bytes"],
        "arena_measure": mi["measure"]["arena_count"],
        "arena_release": mi["release"]["arena_count"],
        "arena_posttrim": mi["posttrim"]["arena_count"],
        "arena_idle": mi["idle"]["arena_count"],
        "throughput_ops_s": result["throughput_ops_per_s"],
        "p99_ns": result["latency_ns"]["p99"],
        "trim_ret": result["idle_trim_ret"],
        "trim_elapsed_ms": memory["trim_elapsed_ns"] / 1_000_000.0,
        "posttrim_minflt": faults["minflt_postrefault"]
        - faults["minflt_posttrim"],
        "posttrim_majflt": faults["majflt_postrefault"]
        - faults["majflt_posttrim"],
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: summarize_matrix.py RESULTS_DIR OUTPUT_DIR")
    results = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for result_path in sorted(results.glob("*/rep*/result.json")):
        cell = result_path.parents[1].name
        match = re.fullmatch(r"rep(\d+)", result_path.parent.name)
        if not match:
            continue
        result = json.loads(result_path.read_text())
        meta = run_metadata(result_path.with_name("run.txt"))
        rows.append(derive(result, meta, cell, int(match.group(1))))
    if not rows:
        raise SystemExit("no result JSON files found")

    fields = list(rows[0])
    with (output / "runs.tsv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    cell_rows = []
    for cell in dict.fromkeys(row["cell"] for row in rows):
        group = [row for row in rows if row["cell"] == cell]
        item = {
            "cell": cell,
            "profile": group[0]["profile"],
            "release_pct": group[0]["release_pct"],
            "live_set": group[0]["live_set"],
            "release_order": group[0]["release_order"],
            "valid_n": len(group),
        }
        for field in fields:
            if field in item or field in {
                "cell", "rep", "profile", "release_pct", "live_set",
                "release_order", "exit"
            }:
                continue
            item[field] = median([row[field] for row in group])
        item["exit"] = max(row["exit"] for row in group)
        cell_rows.append(item)

    cell_fields = list(cell_rows[0])
    with (output / "cells_median.tsv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, cell_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(cell_rows)

    print(f"RUNS={len(rows)} CELLS={len(cell_rows)}")


if __name__ == "__main__":
    main()
