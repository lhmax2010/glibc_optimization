#!/usr/bin/env python3
"""Archive completed G4 observations under STOP; never publish a complete Demo matrix."""
import argparse
import json
import pathlib
import tempfile

from execute_contract import CONTRACT, ANALYSIS
from publish_measurement import verified_manifest, digest
from publish_execution_log import no_symlink, terminal_receipt


def publish(run, output):
    run, output = pathlib.Path(run).absolute(), pathlib.Path(output).absolute()
    for path in (run, output):
        no_symlink(path)
        if ".." in path.parts:
            raise ValueError("parent traversal rejected")
    if output.exists() or output == run or run in output.parents or output in run.parents:
        raise ValueError("observation output must be new and disjoint from the run")
    receipt_bytes = (run / "execution.json").read_bytes()
    receipt = terminal_receipt(receipt_bytes)
    cells = [c for c in CONTRACT["cells"] if c["group"] == "G4"]
    if (receipt["verdict"] != "STOP" or receipt["completed_cells"] != [c["id"] for c in cells] or
            receipt.get("root_authorization", {}).get("root_off") != "PASS_NONROOT"):
        raise ValueError("requires stopped, non-root-restored, three-observed-G4 receipt")
    proofs = {c["id"]: verified_manifest(run, run / "raw", c["id"]) for c in cells}
    rows = ANALYSIS.analyze(run / "raw", {**CONTRACT, "cells": cells})
    evidence = {"schema": "system-before-after.g4-observations-under-stop.v1",
        "verdict": "STOP_NOT_ACCEPTED_FOR_DEMO", "scope": "three observed cells, NOT successful round or complete matrix",
        "execution_sha256": digest(run / "execution.json"), "execution": receipt,
        "pull_manifests": proofs, "points": [], "cell_health": {}}
    xml_sources = {}
    for cell in cells:
        name = cell["id"]
        path = run / "raw" / name
        evidence["cell_health"][name] = json.loads((path / "cell.json").read_text())
        metric = json.loads((path / "metrics.json").read_text())[0]
        point = {"id": name, "metric": metric}
        for phase in ("pre", "post"):
            point[phase] = ANALYSIS.read_point(path / "points" / ("01_" + phase))
        for phase, filename in (("idle_pre", "idle_stat_start.txt"), ("idle_post", "idle_stat_end.txt")):
            point[phase] = ANALYSIS.proc_stat((path / filename).read_text())
        evidence["points"].append(point)
        xml_sources[name] = (path / "malloc_info_pre.xml").read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".g4-stop-observations-", dir=output.parent) as directory:
        staged = pathlib.Path(directory) / "observations"
        (staged / "xml").mkdir(parents=True)
        ANALYSIS.write_tsv(staged / "g4_cycles.tsv", rows)
        ANALYSIS.write_tsv(staged / "g4_summary.tsv", ANALYSIS.summarize(rows))
        for name in ("g4_cycles.tsv", "g4_summary.tsv"):
            if (staged / name).read_bytes() != (run / "derived" / name).read_bytes():
                raise ValueError("G4 observation derivation mismatch: " + name)
        for name, content in xml_sources.items():
            (staged / "xml" / (name + ".xml")).write_bytes(content)
        (staged / "g4_points.json").write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
        if (run / "execution.json").read_bytes() != receipt_bytes:
            raise ValueError("execution changed during observation publication")
        for cell in cells:
            if verified_manifest(run, run / "raw", cell["id"]) != proofs[cell["id"]]:
                raise ValueError("source proof changed during publication")
        staged.rename(output)
    print("PASS G4 observations archived cells=3 cmp=2 ROUND=STOP NOT_DEMO")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()
    publish(args.run, args.output_dir)


if __name__ == "__main__":
    main()
