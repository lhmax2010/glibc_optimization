#!/usr/bin/env python3
"""Archive this round's completed G1/G2/G3 evidence, never a full-matrix PASS.

The frozen analyzer validates the completed, control-paired prefix. No G4 values,
three-repeat headline summaries, or Demo conclusions are filled in.
"""
import argparse
import json
import pathlib
import tempfile
from collect_cell import ANALYSIS
from publish_measurement import digest, verified_manifest
from replay_compact import CONTRACT


def completed_contract(receipt):
    cells = [cell for cell in CONTRACT["cells"] if cell["group"] != "G4"]
    if (receipt.get("verdict") != "STOP" or receipt.get("cleanup") != "PASS"
            or not receipt.get("end_utc") or receipt.get("active_cell") != "G4_trim_r1"
            or receipt.get("completed_cells") != [cell["id"] for cell in cells]):
        raise ValueError("requires the recorded STOP after the complete G1/G2/G3 prefix")
    return {**CONTRACT, "cells": cells}


def publish(run, output):
    if output.exists():
        raise ValueError("refuse to overwrite stopped-round evidence")
    receipt = json.loads((run / "execution.json").read_text())
    partial = completed_contract(receipt)
    raw = run / "raw"
    manifests = {cell["id"]: verified_manifest(run, raw, cell["id"]) for cell in partial["cells"]}
    failed = verified_manifest(run, raw, "G4_trim_r1")
    rows = ANALYSIS.analyze(raw, partial)
    source = {"schema": "system-before-after.completed-prefix.v1", "verdict": "STOP_INCOMPLETE_MATRIX",
              "scope": "18 completed cells only; G4 incomplete; not Demo headline evidence",
              "contract_tag": CONTRACT["contract_tag"], "execution": receipt,
              "points": [], "cell_health": {}, "pull_manifests": manifests,
              "failed_cell_manifest": failed, "failed_cell_files": {}}
    for relative, expected in failed["files"].items():
        source["failed_cell_files"][relative] = {"bytes": (raw / relative).stat().st_size, "sha256": expected}
    for cell in partial["cells"]:
        path = raw / cell["id"]
        source["cell_health"][cell["id"]] = json.loads((path / "cell.json").read_text())
        for metric in json.loads((path / "metrics.json").read_text()):
            entry = {"id": cell["id"], "cycle": metric["cycle"], "metric": metric, "raw_point_sha256": {}}
            for phase in ("pre", "post"):
                point = path / "points" / ("%02d_%s" % (metric["cycle"], phase))
                entry[phase] = ANALYSIS.read_point(point)
                entry["raw_point_sha256"][phase] = {p.name: digest(p) for p in sorted(point.iterdir()) if p.is_file()}
            source["points"].append(entry)
    if len(rows) != 330 or len(source["points"]) != 330:
        raise ValueError("completed-prefix release coverage mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stopped-publication-", dir=output.parent) as directory:
        staged = pathlib.Path(directory) / "publication"
        staged.mkdir()
        (staged / "completed_points.json").write_text(json.dumps(source, indent=2, allow_nan=False) + "\n")
        ANALYSIS.write_tsv(staged / "completed_cycles.tsv", rows)
        staged.rename(output)
    print("PASS stopped-prefix archive cells=18 release_pairs=330; matrix=STOP; no Demo summaries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    args = parser.parse_args()
    publish(args.run, args.output_dir)


if __name__ == "__main__":
    main()
