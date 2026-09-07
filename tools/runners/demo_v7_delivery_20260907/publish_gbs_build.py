#!/usr/bin/env python3
"""Archive a successful explicit GBS workflow without publishing binary artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / "tools/reproduce"))
from check_gbs_package import checked_bytes, read_provenance, validate_provenance


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads((args.bundle / "gbs_build_summary.json").read_text())
    provenance_path = args.bundle / "execution_provenance.json"
    provenance = read_provenance(provenance_path, record["provenance_sha256"], "publication proof rewritten")
    validate_provenance(REPO, provenance)
    if sha(provenance_path) != record["provenance_sha256"]:
        raise ValueError("execution provenance differs from checker summary")
    # Verify the raw, combined GBS stdout/stderr, not the filtered wrapper log.
    # Public summary carries its checker-generated digest; raw log stays local.
    checked_bytes(args.bundle / "gbs.log", record["gbs_log_sha256"], "publication GBS log rewritten")
    for field in ("workflow_commit", "entrypoint_sha256", "checker_sha256"):
        if record[field] != provenance[field]:
            raise ValueError(f"summary/provenance mismatch: {field}")
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
    args.output.mkdir(parents=True, exist_ok=False)
    # The publisher never synthesizes or rewrites execution fingerprints.
    shutil.copyfile(args.bundle / "gbs_build_summary.json", args.output / "build_summary.json")
    shutil.copyfile(provenance_path, args.output / provenance_path.name)
    persisted = read_provenance(args.output / provenance_path.name, record["provenance_sha256"],
                                "published proof rewritten")
    validate_provenance(REPO, persisted)
    checked_bytes(args.bundle / "gbs.log", record["gbs_log_sha256"], "publication GBS log rewritten")
    public_lines = []
    for line in args.log.read_text().splitlines():
        if line.startswith(("PASS\t", "REPORT_ONLY\t", "INFO\t", "OVERALL\t", "MODE\t")):
            public_lines.append(line.replace(str(REPO), "<HOST_REPO>"))
    (args.output / "workflow_summary.tsv").write_text("\n".join(public_lines) + "\n")
    print("PASS public-gbs-build-summary clean-execution-provenance persisted-rpm three-elf-sha")


if __name__ == "__main__":
    main()
