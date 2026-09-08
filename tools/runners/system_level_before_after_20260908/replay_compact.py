#!/usr/bin/env python3
"""Replay the public parsed-point transcription using frozen derivation functions.

This does not replace raw source/health validation performed on board pulls.
Numbers come from parsed proc/reclaim_probe/memps points, not rounded summaries.
"""
import argparse
import json
import pathlib
from collect_cell import ANALYSIS

HERE = pathlib.Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text())


def derive_rows(source):
    expected = [(cell["id"], cycle) for cell in CONTRACT["cells"] for cycle in range(1, cell["cycles"] + 1)]
    if [(entry["id"], entry["cycle"]) for entry in source["points"]] != expected:
        raise ValueError("compact source requires exact complete contract order/coverage")
    cells = {cell["id"]: cell for cell in CONTRACT["cells"]}
    rows = []
    for entry in source["points"]:
        cell = cells[entry["id"]]
        metric = entry["metric"]
        ANALYSIS.require(metric["cycle"] == entry["cycle"], "metric cycle mismatch")
        row = {key: cell[key] for key in ("id", "group", "profile", "arm", "rep")}
        row.update(cycle=entry["cycle"], **ANALYSIS.derive(entry["pre"], entry["post"]),
                   trim_elapsed_ms=metric["trim_elapsed_ns"] / 1e6,
                   next_cycle_minflt=metric["next_cycle_minflt"], next_cycle_majflt=metric["next_cycle_majflt"],
                   business_elapsed_ms=metric.get("business_elapsed_ms"),
                   released_payload_bytes=metric.get("released_payload_bytes"))
        if cell["group"] == "G4":
            row["idle_120s_minflt"] = entry["idle_post"]["minflt"] - entry["idle_pre"]["minflt"]
            row["idle_120s_majflt"] = entry["idle_post"]["majflt"] - entry["idle_pre"]["majflt"]
        else:
            row["idle_120s_minflt"] = row["idle_120s_majflt"] = None
        rows.append(row)
    return ANALYSIS.pair_controls(rows)


def replay(source, gst_cycles, output):
    rows = derive_rows(source)
    summary = ANALYSIS.summarize(rows)
    repetitions, arms, comparison = ANALYSIS.GST.derive_cycle_summaries(ANALYSIS.GST.read_cycle_table(gst_cycles))
    output.mkdir(parents=True, exist_ok=True)
    ANALYSIS.write_tsv(output / "cycles.tsv", rows)
    ANALYSIS.write_tsv(output / "summary.tsv", summary)
    ANALYSIS.GST.write_tsv(output / "gst_repetitions.tsv", repetitions)
    ANALYSIS.GST.write_tsv(output / "gst_arms.tsv", arms)
    (output / "gst_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    return len(rows), len(summary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--points", required=True, type=pathlib.Path)
    p.add_argument("--gst-cycles", required=True, type=pathlib.Path)
    p.add_argument("--output-dir", required=True, type=pathlib.Path)
    a = p.parse_args()
    count, groups = replay(json.loads(a.points.read_text()), a.gst_cycles, a.output_dir)
    print(f"PASS system-before-after compact replay cells=21 cycles={count} group_arms={groups}")


if __name__ == "__main__":
    main()
