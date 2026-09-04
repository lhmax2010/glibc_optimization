#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path


def read_tsv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def m7(path):
    root = ET.parse(path).getroot()
    heaps = root.findall("heap")
    def total(kind):
        return sum(int(node.attrib["size"]) for node in root.findall(f"total[@type='{kind}']"))
    unsorted = sum(int(node.attrib["size"]) for heap in heaps for node in heap.findall("unsorted"))
    return {"arenas": len(heaps), "fast_bytes": total("fast"), "rest_bytes": total("rest"), "unsorted_bytes": unsorted}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", required=True, type=Path)
    ap.add_argument("--t1-pull", type=Path, help="optional recorded partial T1 pull")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cells = read_tsv(args.pull / "cells.tsv")
    sample_rows = read_tsv(args.pull / "samples.tsv")
    if args.t1_pull:
        cells = read_tsv(args.t1_pull / "cells.tsv") + cells
        sample_rows = read_tsv(args.t1_pull / "samples.tsv") + sample_rows
    ids = [row["cell"] for row in cells]
    if ids != ["T1_1", "T2_E1", "T2_E2", "T2_E3"]:
        raise SystemExit(f"unexpected completed-cell sequence: {ids}")
    derived = []
    for row in cells:
        item = dict(row)
        for key in ("project_pre_kb", "project_post_kb", "memps_pre_heap_kb", "memps_post_heap_kb",
                    "minflt_pre", "minflt_post", "majflt_pre", "majflt_post"):
            item[key] = int(item[key])
        item["project_reclaimed_kb"] = item["project_pre_kb"] - item["project_post_kb"]
        item["memps_reclaimed_kb"] = item["memps_pre_heap_kb"] - item["memps_post_heap_kb"]
        item["minflt_delta"] = item["minflt_post"] - item["minflt_pre"]
        item["majflt_delta"] = item["majflt_post"] - item["majflt_pre"]
        item["injection_ms"] = float(item["injection_ms"])
        if row["group"] == "T2":
            item.update({f"m7_{k}": v for k, v in m7(args.pull / f"malloc_info_{row['cell']}.xml").items()})
        derived.append(item)
    t1 = [r for r in derived if r["group"] == "T1"]
    t2 = [r for r in derived if r["group"] == "T2"]
    sample_by_label = {row["label"]: row for row in sample_rows}
    t2_pre_ns = [int(sample_by_label[f"T2_E{i}_pre"]["epoch_ns"]) for i in range(1, 4)]
    t2_intervals = [(b - a) / 1_000_000_000 for a, b in zip(t2_pre_ns, t2_pre_ns[1:])]
    summary = {
        "schema": "glibc-memopt.tizen-native-evidence.summary.v1",
        "completion": {
            "t1_completed": 1,
            "t1_preregistered": 5,
            "t1_stop": "pipeline EOS at 60.100233983 s before T1_2",
            "t2_baseline_completed": 3,
            "t2_baseline_preregistered": 3,
            "t2_release_phase_completed": 0,
            "t2_release_phase_preregistered": 1,
            "t2_release_phase_stop": "attach-panel-gallery was no longer running at the first terminate command"
        },
        "cells": derived,
        "t1": {
            "reclaimed_kb": [r["project_reclaimed_kb"] for r in t1],
            "injection_ms_median": statistics.median(r["injection_ms"] for r in t1),
            "memps_same_direction_count": sum((r["project_reclaimed_kb"] > 0) == (r["memps_reclaimed_kb"] > 0) for r in t1),
        },
        "t2": {
            "reclaimed_kb": [r["project_reclaimed_kb"] for r in t2],
            "injection_ms_median": statistics.median(r["injection_ms"] for r in t2),
            "memps_same_direction_count": sum((r["project_reclaimed_kb"] > 0) == (r["memps_reclaimed_kb"] > 0) for r in t2),
            "pre_sample_intervals_s": t2_intervals,
            "minimum_interval_requirement_s": 120,
            "interval_requirement_met": all(value >= 120 for value in t2_intervals),
        },
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    keys = ["group", "cell", "pid", "project_pre_kb", "project_post_kb", "project_reclaimed_kb",
            "memps_pre_heap_kb", "memps_post_heap_kb", "memps_reclaimed_kb", "trim_ret",
            "injection_ms", "minflt_delta", "majflt_delta", "m7_arenas", "m7_fast_bytes",
            "m7_rest_bytes", "m7_unsorted_bytes", "buffers_pre", "buffers_post"]
    with (args.output / "cells_derived.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=keys, delimiter="\t", extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in derived:
            writer.writerow(row)
    with (args.output / "cells_raw.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cells[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(cells)
    print(f"PARSE_OK cells={len(derived)} t1={len(t1)} t2={len(t2)}")


if __name__ == "__main__":
    main()
