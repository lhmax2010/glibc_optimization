#!/usr/bin/env python3
"""Validate the GBS spec and, when GBS is installed, build and inspect the RPM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


EXPECTED_FILES = {
    "/usr/bin/alloc_bench",
    "/usr/bin/gst_loop_decode",
    "/usr/bin/reclaim_probe",
}
EXPECTED_DEVEL = {"glibc-devel", "glib2-devel", "gstreamer-devel"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def static_check(repo: Path) -> tuple[Path, dict]:
    spec = repo / "packaging/glibc-memopt-tools.spec"
    text = spec.read_text(encoding="utf-8")
    for tag, value in (("Name", "glibc-memopt-tools"), ("Version", "1.0.0")):
        match = re.search(rf"^{tag}:\s*(\S+)\s*$", text, re.MULTILINE)
        if not match or match.group(1) != value:
            raise ValueError(f"bad or missing {tag}: expected {value}")
    for section in ("%prep", "%build", "%install", "%files"):
        if not re.search(rf"^{re.escape(section)}\s*$", text, re.MULTILINE):
            raise ValueError(f"missing {section}")
    devel = set(re.findall(r"^BuildRequires:\s+(\S+-devel)\s*$", text, re.MULTILINE))
    if devel != EXPECTED_DEVEL:
        raise ValueError(f"-devel BuildRequires drift: {sorted(devel)}")
    files_body = text.split("%files", 1)[1].split("%changelog", 1)[0]
    files = {line.strip().replace("%{_bindir}", "/usr/bin") for line in files_body.splitlines() if line.strip()}
    if files != EXPECTED_FILES:
        raise ValueError(f"%files drift: {sorted(files)}")
    for source in (
        "tools/alloc_bench/alloc_bench.c",
        "tools/gst_loop_decode/gst_loop_decode.c",
        "tools/reclaim_probe/reclaim_probe.c",
    ):
        if source not in text or not (repo / source).is_file():
            raise ValueError(f"missing build source: {source}")
    manifest = json.loads((repo / "tools/reproduce/deliverables_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "glibc-memopt-demo.deliverables.v2":
        raise ValueError("deliverables manifest is not v2")
    print("PASS\tgbs-spec-static\tname/version/BuildRequires/%files")
    rpmspec = shutil.which("rpmspec")
    if rpmspec:
        parsed = subprocess.run(
            [rpmspec, "-P", str(spec)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if parsed.returncode:
            print(parsed.stdout[-4000:])
            raise ValueError(f"rpmspec syntax check failed with RC={parsed.returncode}")
        print("PASS\tgbs-spec-syntax\trpmspec -P")
    else:
        print("SKIPPED\tgbs-spec-syntax\trpmspec is not installed; portable static check passed")
    return spec, manifest


def gbs_build(repo: Path, manifest: dict) -> None:
    gbs = shutil.which("gbs")
    if not gbs:
        print("SKIPPED\tgbs-build\tgbs is not installed; static spec/%files check passed")
        return
    config = repo / manifest["gbs_build"]["config"]
    source_commit = manifest["gbs_build"].get("source_commit", "")
    command = [gbs, "-c", str(config), "build", "-A", "armv7l", "--overwrite"]
    if source_commit == "PENDING_SOURCE_COMMIT":
        command.append("--include-all")
    elif re.fullmatch(r"[0-9a-f]{40}", source_commit):
        command.extend(["-c", source_commit])
    else:
        raise ValueError("manifest gbs_build.source_commit must be a commit or PENDING_SOURCE_COMMIT")
    result = subprocess.run(command, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        print(result.stdout[-12000:])
        raise RuntimeError(f"GBS build failed with RC={result.returncode}")

    match = re.search(r"^buildroot\s*=\s*(\S+)\s*$", config.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError("GBS config lacks buildroot")
    rpm_dir = Path(match.group(1)) / "local/repos/tizen_unified_standard/armv7l/RPMS"
    rpm_path = rpm_dir / "glibc-memopt-tools-1.0.0-1.armv7l.rpm"
    if not rpm_path.is_file():
        raise FileNotFoundError(rpm_path)
    queried = subprocess.run(
        ["rpm", "-qp", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}\n%{ARCH}\n", str(rpm_path)],
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    if queried != [manifest["gbs_build"]["rpm_nvr"], manifest["gbs_build"]["rpm_arch"]]:
        raise ValueError(f"RPM identity drift: {queried}")
    if source_commit != "PENDING_SOURCE_COMMIT" and sha256(rpm_path) != manifest["gbs_build"]["rpm_sha256"]:
        raise ValueError("RPM SHA-256 drift")
    listed = set(subprocess.run(["rpm", "-qpl", str(rpm_path)], text=True, capture_output=True, check=True).stdout.splitlines())
    if listed != EXPECTED_FILES:
        raise ValueError(f"RPM %files drift: {sorted(listed)}")

    with tempfile.TemporaryDirectory(prefix="glibc-memopt-gbs-extract-") as directory:
        root = Path(directory)
        converter = subprocess.Popen(["rpm2cpio", str(rpm_path)], stdout=subprocess.PIPE)
        assert converter.stdout is not None
        extraction = subprocess.run(["cpio", "-idm", "--quiet"], cwd=root, stdin=converter.stdout, capture_output=True)
        converter.stdout.close()
        converter_rc = converter.wait()
        if converter_rc or extraction.returncode:
            raise RuntimeError("failed to extract GBS RPM")
        artifacts = {item["name"]: item for item in manifest["artifacts"]}
        for installed, manifest_name in (
            ("alloc_bench", "alloc_bench.armv7l"),
            ("gst_loop_decode", "gst_loop_decode.armv7l"),
            ("reclaim_probe", "reclaim_probe.armv7l"),
        ):
            actual = sha256(root / "usr/bin" / installed)
            expected = artifacts[manifest_name]["gbs_build_sha256"]
            if actual != expected:
                raise ValueError(f"GBS binary SHA drift for {installed}: {actual} != {expected}")
    if source_commit == "PENDING_SOURCE_COMMIT":
        print(f"REPORT_ONLY\tgbs-rpm-sha\tpending source commit; observed={sha256(rpm_path)}")
    print(f"PASS\tgbs-build\t{queried[0]}.{queried[1]} sha256={sha256(rpm_path)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    _, manifest = static_check(args.repo_root.resolve())
    gbs_build(args.repo_root.resolve(), manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
