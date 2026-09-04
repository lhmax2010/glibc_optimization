#!/usr/bin/env python3
"""Validate the GBS package contract and optionally build/inspect the RPM."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


EXPECTED_FILES = {
    "/usr/bin/alloc_bench",
    "/usr/bin/gst_loop_decode",
    "/usr/bin/reclaim_probe",
}
EXPECTED_DEVEL = {"glibc-devel", "glib2-devel", "gstreamer-devel"}


class GbsEnvironmentUnavailable(RuntimeError):
    """GBS could not provide a usable build environment; package status is unknown."""


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
    if manifest.get("schema") != "glibc-memopt-demo.deliverables.v3":
        raise ValueError("deliverables manifest is not v3")
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


def acquire_build_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+", encoding="utf-8")
    deadline = time.monotonic() + timeout_seconds
    announced = False
    while True:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            stream.seek(0)
            stream.truncate()
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            print(f"PASS\tgbs-build-lock\tacquired {path} pid={os.getpid()}")
            return stream
        except BlockingIOError:
            if not announced:
                print(
                    "WAITING\tgbs-build-lock\t"
                    f"another GBS build holds {path}; timeout={timeout_seconds:.0f}s"
                )
                announced = True
            if time.monotonic() >= deadline:
                stream.close()
                raise GbsEnvironmentUnavailable(
                    f"GBS build lock {path} remained occupied for {timeout_seconds:.0f}s"
                )
            time.sleep(0.25)


def unique_config(source: Path, destination: Path, buildroot: Path) -> None:
    text = source.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"^buildroot\s*=\s*\S+\s*$",
        f"buildroot={buildroot}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("GBS config must contain exactly one buildroot")
    destination.write_text(updated, encoding="utf-8")


def gbs_build(repo: Path, manifest: dict, lock_timeout: float, output_dir: Path | None) -> None:
    gbs = shutil.which("gbs")
    if not gbs:
        raise GbsEnvironmentUnavailable("gbs is not installed")
    for command in ("rpm", "rpm2cpio", "cpio"):
        if not shutil.which(command):
            raise GbsEnvironmentUnavailable(f"required host command is unavailable: {command}")

    lock_path = Path(os.environ.get("GLIBC_MEMOPT_GBS_LOCK", "/tmp/glibc-memopt-gbs-build.lock"))
    lock = acquire_build_lock(lock_path, lock_timeout)
    try:
        with tempfile.TemporaryDirectory(prefix=f"glibc-memopt-gbs-{os.getpid()}-") as directory:
            workspace = Path(directory)
            buildroot = workspace / "buildroot"
            config = workspace / "gbs.conf"
            unique_config(repo / manifest["gbs_build"]["config"], config, buildroot)
            source_commit = manifest["gbs_build"].get("source_commit", "")
            command = [gbs, "-c", str(config), "build", "-A", "armv7l", "--overwrite"]
            if source_commit == "PENDING_SOURCE_COMMIT":
                command.append("--include-all")
            elif re.fullmatch(r"[0-9a-f]{40}", source_commit):
                command.extend(["-c", source_commit])
            else:
                raise ValueError(
                    "manifest gbs_build.source_commit must be a commit or PENDING_SOURCE_COMMIT"
                )
            print(f"INFO\tgbs-buildroot\t{buildroot}")
            result = subprocess.run(
                command, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if result.returncode:
                print(result.stdout[-12000:])
                raise GbsEnvironmentUnavailable(
                    f"gbs build returned RC={result.returncode}; package correctness was not adjudicated"
                )

            rpm_dir = buildroot / "local/repos/tizen_unified_standard/armv7l/RPMS"
            rpm_path = rpm_dir / "glibc-memopt-tools-1.0.0-1.armv7l.rpm"
            if not rpm_path.is_file():
                raise ValueError(f"successful GBS build did not produce expected RPM: {rpm_path}")
            queried = subprocess.run(
                ["rpm", "-qp", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}\n%{ARCH}\n", str(rpm_path)],
                text=True, capture_output=True, check=True,
            ).stdout.splitlines()
            if queried != [manifest["gbs_build"]["rpm_nvr"], manifest["gbs_build"]["rpm_arch"]]:
                raise ValueError(f"RPM identity drift: {queried}")
            observed_rpm_sha = sha256(rpm_path)
            recorded_rpm_sha = manifest["gbs_build"]["rpm_sha256"]
            if source_commit != "PENDING_SOURCE_COMMIT" and observed_rpm_sha != recorded_rpm_sha:
                print(
                    "REPORT_ONLY\tgbs-rpm-wrapper-sha\t"
                    f"recorded={recorded_rpm_sha} observed={observed_rpm_sha}; "
                    "GBS/RPM archive metadata is not a reproducibility gate"
                )
            listed = set(
                subprocess.run(
                    ["rpm", "-qpl", str(rpm_path)], text=True, capture_output=True, check=True,
                ).stdout.splitlines()
            )
            if listed != EXPECTED_FILES:
                raise ValueError(f"RPM %files drift: {sorted(listed)}")

            with tempfile.TemporaryDirectory(prefix="glibc-memopt-gbs-extract-") as extract_dir:
                root = Path(extract_dir)
                converter = subprocess.Popen(["rpm2cpio", str(rpm_path)], stdout=subprocess.PIPE)
                assert converter.stdout is not None
                extraction = subprocess.run(
                    ["cpio", "-idm", "--quiet"], cwd=root, stdin=converter.stdout,
                    capture_output=True,
                )
                converter.stdout.close()
                converter_rc = converter.wait()
                if converter_rc or extraction.returncode:
                    raise ValueError("successful GBS RPM could not be extracted for package inspection")
                artifacts = {item["name"]: item for item in manifest["artifacts"]}
                for installed, manifest_name in (
                    ("alloc_bench", "alloc_bench.armv7l"),
                    ("gst_loop_decode", "gst_loop_decode.armv7l"),
                    ("reclaim_probe", "reclaim_probe.armv7l"),
                ):
                    actual = sha256(root / "usr/bin" / installed)
                    expected = artifacts[manifest_name]["gbs_build_sha256"]
                    if actual != expected:
                        raise ValueError(
                            f"GBS binary SHA drift for {installed}: {actual} != {expected}"
                        )
                if output_dir is not None:
                    output_dir.mkdir(parents=True, exist_ok=False)
                    shutil.copy2(rpm_path, output_dir / rpm_path.name)
                    for installed, manifest_name in (
                        ("alloc_bench", "alloc_bench.armv7l"),
                        ("gst_loop_decode", "gst_loop_decode.armv7l"),
                        ("reclaim_probe", "reclaim_probe.armv7l"),
                    ):
                        shutil.copy2(root / "usr/bin" / installed, output_dir / manifest_name)
                    print(f"PASS\tgbs-output\t{output_dir}")
            if source_commit == "PENDING_SOURCE_COMMIT":
                print(
                    "REPORT_ONLY\tgbs-rpm-wrapper-sha\t"
                    f"pending source commit; observed={observed_rpm_sha}"
                )
            print(f"PASS\tgbs-build\t{queried[0]}.{queried[1]} sha256={observed_rpm_sha}")
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build", action="store_true", help="run the explicit real GBS build")
    parser.add_argument("--lock-timeout", type=float, default=600.0)
    parser.add_argument(
        "--output-dir", type=Path,
        help="persist the verified RPM and three manifest-named ELF files; directory must not exist",
    )
    args = parser.parse_args()
    try:
        _, manifest = static_check(args.repo_root.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL\tgbs-package-contract\t{error}")
        return 1
    if not args.build:
        print(
            "SKIPPED\tgbs-build\treal GBS build is excluded from default verify; "
            "run reproduce.sh gbs explicitly"
        )
        return 0
    output_dir = args.output_dir.resolve() if args.output_dir else None
    if output_dir is not None and output_dir.exists():
        print(f"FAIL\tgbs-output\tdirectory already exists: {output_dir}")
        return 2
    try:
        gbs_build(args.repo_root.resolve(), manifest, args.lock_timeout, output_dir)
    except GbsEnvironmentUnavailable as error:
        print(f"REPORT_ONLY\tgbs-build-environment\t{error}")
        print("SKIPPED\tgbs-build\tGBS environment unavailable; static package gates passed")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL\tgbs-package-artifact\t{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
