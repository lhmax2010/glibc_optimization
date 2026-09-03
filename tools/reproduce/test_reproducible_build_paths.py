#!/usr/bin/env python3
"""Build ARM deliverables from two source paths and require byte-identical ELF files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_sources(destination: Path) -> None:
    for relative in (
        "tools/alloc_bench",
        "tools/reclaim_probe",
        "tools/gst_loop_decode",
        "tools/runners/gst_trim_cost_20260901/build_armv7l.sh",
    ):
        source = REPO / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("*.host*", "*.armv7l", ".build", "__pycache__"))
        else:
            shutil.copy2(source, target)


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def build(root: Path, toolchain: Path, gst_sysroot: Path) -> dict[str, Path]:
    copy_sources(root)
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = "1788364800"
    run(
        ["make", "-C", "tools/alloc_bench", "armv7l", f"ARMV7L_ROOT={toolchain}"],
        cwd=root,
        env=environment,
    )
    run(
        ["make", "-C", "tools/reclaim_probe", "armv7l", f"ARMV7L_ROOT={toolchain}"],
        cwd=root,
        env=environment,
    )
    gst_output = root / "out/gst_loop_decode.armv7l"
    environment.update({
        "TOOLCHAIN_ROOT": str(toolchain),
        "GST_SYSROOT": str(gst_sysroot),
    })
    run(
        ["sh", "tools/runners/gst_trim_cost_20260901/build_armv7l.sh", str(gst_output)],
        cwd=root,
        env=environment,
    )
    return {
        "alloc_bench.armv7l": root / "tools/alloc_bench/alloc_bench.armv7l",
        "reclaim_probe.armv7l": root / "tools/reclaim_probe/reclaim_probe.armv7l",
        "gst_loop_decode.armv7l": gst_output,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain-root", type=Path, default=os.environ.get("DEMO_TOOLCHAIN_ROOT"))
    parser.add_argument("--gst-sysroot", type=Path, default=os.environ.get("DEMO_GST_SYSROOT"))
    args = parser.parse_args()
    if args.toolchain_root is None or args.gst_sysroot is None:
        parser.error("set --toolchain-root/DEMO_TOOLCHAIN_ROOT and --gst-sysroot/DEMO_GST_SYSROOT")
    with tempfile.TemporaryDirectory(prefix="glibc-memopt-build-path-a-") as first_dir, tempfile.TemporaryDirectory(prefix="glibc-memopt-build-path-b-") as second_dir:
        first = build(Path(first_dir) / "checkout", args.toolchain_root.resolve(), args.gst_sysroot.resolve())
        second = build(Path(second_dir) / "checkout", args.toolchain_root.resolve(), args.gst_sysroot.resolve())
        manifest = json.loads((REPO / "tools/reproduce/deliverables_manifest.json").read_text(encoding="utf-8"))
        expected = {item["name"]: item.get("reproducible_build_sha256") for item in manifest["artifacts"]}
        failed = False
        for name in first:
            first_sha, second_sha = digest(first[name]), digest(second[name])
            matches = first_sha == second_sha == expected[name]
            status = "PASS" if matches else "FAIL"
            print(f"{status}\t{name}\tpath-a={first_sha}\tpath-b={second_sha}\tmanifest={expected[name]}")
            failed = failed or not matches
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
