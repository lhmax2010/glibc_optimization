#!/usr/bin/env python3
"""Publish already measured GBS retry2 gst compact evidence after full pull verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
FILES = ("cycles.tsv", "repetitions.tsv", "arm_summary.tsv", "comparison.json", "health.json", "external_summary.tsv")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pull = args.workflow / "gst/board_pull"
    archived = args.workflow / "gst/derived"
    with tempfile.TemporaryDirectory(prefix="glibc-gst-publication-") as temporary:
        rebuilt = Path(temporary) / "derived"
        subprocess.run([
            sys.executable, str(REPO / "tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py"),
            "--pull", str(pull), "--output", str(rebuilt),
        ], check=True)
        for name in FILES:
            if (rebuilt / name).read_bytes() != (archived / name).read_bytes():
                raise ValueError(f"archived derivative differs from verified raw pull: {name}")
        manifest = json.loads((REPO / "tools/reproduce/deliverables_manifest.json").read_text())
        hashes = {}
        for item in manifest["artifacts"]:
            if item["name"] == "alloc_bench.armv7l":
                continue
            actual = digest(pull / item["name"])
            expected = item.get("gbs_build_sha256") or item["frozen_sha256"]
            if actual != expected:
                raise ValueError(f"archived asset identity mismatch: {item['name']}")
            hashes[item["name"]] = actual
        args.output.mkdir(parents=True, exist_ok=False)
        for name in FILES:
            shutil.copy2(rebuilt / name, args.output / name)
        publication = {
            "schema": "glibc-memopt-gst-retry2-publication.v1",
            "measured_date": "2026-09-03", "publication_date": "2026-09-07",
            "source_archive": "board_results/gbs_rebaseline_20260903/workflow_retry2/",
            "source_archive_availability": "complete raw files retained locally; available on request",
            "raw_manifest_sha256": digest(pull / "board_manifest.sha256"),
            "raw_sizes_sha256": digest(pull / "board_file_sizes.tsv"),
            "asset_sha256": hashes,
            "compact_sha256": {name: digest(args.output / name) for name in FILES},
            "checks": "full pull manifest/size verification; all six derivatives byte-identical to archived output",
            "scope": "existing retry2 gst cells only; no new measurement and no held-out claim for gst/reclaim_probe",
        }
        (args.output / "publication.json").write_text(json.dumps(publication, indent=2) + "\n")
    print("PASS gst-retry2-publication full-pull-integrity archived-cmp asset-sha")


if __name__ == "__main__":
    main()
