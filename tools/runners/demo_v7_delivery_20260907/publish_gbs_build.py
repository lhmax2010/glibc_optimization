#!/usr/bin/env python3
"""Archive a successful explicit GBS workflow without publishing binary artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads((args.bundle / "gbs_build_summary.json").read_text())
    manifest = json.loads((REPO / "tools/reproduce/deliverables_manifest.json").read_text())
    if record["verdict"] != "PASS" or "OVERALL\tPASS" not in args.log.read_text():
        raise ValueError("cannot archive an unsuccessful build as PASS")
    expected = {item["name"]: item["gbs_build_sha256"] for item in manifest["artifacts"] if item["gbs_build_sha256"]}
    if record["elf_sha256"] != expected:
        raise ValueError("recorded ELF identities do not match manifest")
    for name, value in expected.items():
        if sha(args.bundle / name) != value:
            raise ValueError(f"persisted ELF mismatch: {name}")
    rpm = args.bundle / (record["rpm"]["nvr"] + "." + record["rpm"]["arch"] + ".rpm")
    if sha(rpm) != record["rpm"]["sha256"]:
        raise ValueError("persisted RPM differs from generated RPM")
    record["checker_sha256"] = sha(REPO / "tools/reproduce/check_gbs_package.py")
    record["entrypoint_sha256"] = sha(REPO / "tools/reproduce/reproduce.sh")
    record["scope"] = "host build only; no board connection or new measurement"
    record["raw_archive"] = "board_results/demo_v7_delivery_20260907/ (local, available on request)"
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "build_summary.json").write_text(json.dumps(record, indent=2) + "\n")
    public_lines = []
    for line in args.log.read_text().splitlines():
        if line.startswith(("PASS\t", "REPORT_ONLY\t", "INFO\t", "OVERALL\t", "MODE\t")):
            public_lines.append(line.replace(str(REPO), "<HOST_REPO>"))
    (args.output / "workflow_summary.tsv").write_text("\n".join(public_lines) + "\n")
    print("PASS public-gbs-build-summary persisted-rpm three-elf-sha")


if __name__ == "__main__":
    main()
