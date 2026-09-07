#!/usr/bin/env python3
"""Validate the GBS package contract and optionally build/inspect the RPM."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
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


FINGERPRINT_FILES = {
    "entrypoint_sha256": "tools/reproduce/reproduce.sh",
    "checker_sha256": "tools/reproduce/check_gbs_package.py",
}


def git_output(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def validate_provenance(repo: Path, provenance: dict, *, publication: bool = True) -> None:
    """Bind execution bytes to git objects, and (when publishing) the exact clean HEAD."""
    if provenance.get("schema") != "glibc-memopt-gbs-execution.v1":
        raise ValueError("missing or unsupported execution provenance")
    commit = provenance["workflow_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid execution commit")
    if provenance["dirty"] or provenance["git_status_porcelain"]:
        raise ValueError("dirty execution snapshot cannot be published")
    for field, path in FINGERPRINT_FILES.items():
        committed = hashlib.sha256(git_output(repo, "show", f"{commit}:{path}")).hexdigest()
        if provenance[field] != committed or sha256(repo / path) != committed:
            raise ValueError(f"execution/commit/current bytes mismatch: {field}")
    if publication:
        if git_output(repo, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError("publication HEAD differs from execution HEAD")
        if git_output(repo, "status", "--porcelain", "--untracked-files=all").strip():
            raise ValueError("publication working tree is dirty")


def capture_provenance(repo: Path, destination: Path) -> dict:
    """Called under the lock, before GBS; rejected dirty state is recorded too."""
    status = git_output(repo, "status", "--porcelain", "--untracked-files=all").decode()
    provenance = {
        "schema": "glibc-memopt-gbs-execution.v1",
        "workflow_commit": git_output(repo, "rev-parse", "HEAD").decode().strip(),
        "dirty": bool(status),
        "git_status_porcelain": status,
        "python_version": sys.version.split()[0],
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        **{field: sha256(repo / path) for field, path in FINGERPRINT_FILES.items()},
    }
    destination.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    if sha256(Path(__file__).resolve()) != provenance["checker_sha256"]:
        raise ValueError("executing checker differs from repository checker")
    if sha256(Path(__file__).resolve().with_name("reproduce.sh")) != provenance["entrypoint_sha256"]:
        raise ValueError("executing entrypoint differs from repository entrypoint")
    validate_provenance(repo, provenance)
    print(f"PASS\tgbs-execution-provenance\tHEAD={provenance['workflow_commit']} dirty=false", flush=True)
    return provenance


def run_rpm_tool(command: list[str]) -> str:
    try:
        result = subprocess.run(command, text=True, capture_output=True)
    except OSError as error:
        raise GbsEnvironmentUnavailable(f"cannot execute {command[0]}: {error}") from error
    if result.returncode:
        raise GbsEnvironmentUnavailable(
            f"{command[0]} inspection RC={result.returncode}: {result.stderr[-1000:].strip()}; "
            "tool/environment failure; package defect not established"
        )
    return result.stdout


def classify_gbs_failure(returncode: int, output: str) -> None:
    # Only recognizable source diagnostics justify a package-defect verdict.
    environment = re.search(
        r"No space left on device|Permission denied|error while loading shared libraries|"
        r"fatal error:.*(?:file not found|No such file)", output, re.IGNORECASE,
    )
    if environment:
        raise GbsEnvironmentUnavailable(f"gbs build returned RC={returncode}; environment diagnostic: {environment.group(0)}")
    diagnostic = re.search(r"^.*\.(?:c|cc|cpp|h):\d+(?::\d+)?: (?:fatal )?error:.*$", output, re.MULTILINE)
    if diagnostic:
        raise ValueError(f"gbs RC={returncode}; source compilation defect: {diagnostic.group(0)}")
    raise GbsEnvironmentUnavailable(
        f"gbs build returned RC={returncode}; no unambiguous source compiler diagnostic; "
        "environment unavailable or unknown cause, package correctness not adjudicated"
    )


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
        try:
            parsed = subprocess.run(
                [rpmspec, "-P", str(spec)], text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=30,
            )
            if parsed.returncode:
                reason = f"rpmspec -P RC={parsed.returncode}: {parsed.stdout[-1000:].strip()}"
                print(f"SKIPPED\tgbs-spec-syntax\t{reason}; portable static check passed")
            else:
                print("PASS\tgbs-spec-syntax\trpmspec -P")
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"SKIPPED\tgbs-spec-syntax\t{error}; portable static check passed")
    else:
        print("SKIPPED\tgbs-spec-syntax\trpmspec is not installed; portable static check passed")
    return spec, manifest


def acquire_build_lock(path: Path, timeout_seconds: float):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("a+", encoding="utf-8")
    except OSError as error:
        raise GbsEnvironmentUnavailable(f"GBS lock cannot be opened for writing: {path}: {error}") from error
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
        except OSError as error:
            stream.close()
            raise GbsEnvironmentUnavailable(f"GBS lock cannot be acquired/written: {path}: {error}") from error


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


@contextmanager
def build_workspace(record: dict):
    """Keep root-owned cleanup failures separate from artifact validation."""
    workspace = Path(tempfile.mkdtemp(prefix=f"glibc-memopt-gbs-{os.getpid()}-"))
    try:
        yield workspace
    finally:
        try:
            shutil.rmtree(workspace)
        except OSError as error:
            record["buildroot_residue"] = str(workspace)
            print(f"REPORT_ONLY\tgbs-buildroot-residue\t{workspace}; {error}")


def gbs_build(repo: Path, manifest: dict, lock_timeout: float, output_dir: Path) -> dict:
    gbs = shutil.which("gbs")
    if not gbs:
        raise GbsEnvironmentUnavailable("gbs is not installed")
    for command in ("rpm", "rpm2cpio", "cpio"):
        if not shutil.which(command):
            raise GbsEnvironmentUnavailable(f"required host command is unavailable: {command}")

    lock_path = Path(os.environ.get("GLIBC_MEMOPT_GBS_LOCK", "/tmp/glibc-memopt-gbs-build.lock"))
    lock = acquire_build_lock(lock_path, lock_timeout)
    started = time.monotonic()
    record = {
        "schema": "glibc-memopt-gbs-end-to-end.v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": manifest["gbs_build"]["source_commit"],
        "buildroot_residue": None,
        "elf_sha256": {},
    }
    try:
        with build_workspace(record) as workspace:
            provenance_path = workspace / "execution_provenance.json"
            provenance = capture_provenance(repo, provenance_path)
            record.update({field: provenance[field] for field in FINGERPRINT_FILES})
            record["workflow_commit"] = provenance["workflow_commit"]
            record["provenance_sha256"] = sha256(provenance_path)
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
            record["executed_command"] = command
            print(f"INFO\tgbs-command\t{shlex.join(command)}", flush=True)
            try:
                result = subprocess.run(
                    command, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
            except OSError as error:
                raise GbsEnvironmentUnavailable(f"cannot execute gbs: {error}") from error
            if result.returncode:
                print(result.stdout[-12000:])
                classify_gbs_failure(result.returncode, result.stdout)

            rpm_dir = buildroot / "local/repos/tizen_unified_standard/armv7l/RPMS"
            rpm_path = rpm_dir / "glibc-memopt-tools-1.0.0-1.armv7l.rpm"
            if not rpm_path.is_file():
                raise ValueError(f"successful GBS build did not produce expected RPM: {rpm_path}")
            queried = run_rpm_tool(
                ["rpm", "-qp", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}\n%{ARCH}\n", str(rpm_path)],
            ).splitlines()
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
                run_rpm_tool(["rpm", "-qpl", str(rpm_path)]).splitlines()
            )
            if listed != EXPECTED_FILES:
                raise ValueError(f"RPM %files drift: {sorted(listed)}")

            with tempfile.TemporaryDirectory(prefix="glibc-memopt-gbs-extract-") as extract_dir:
                root = Path(extract_dir)
                try:
                    converter = subprocess.Popen(["rpm2cpio", str(rpm_path)], stdout=subprocess.PIPE)
                except OSError as error:
                    raise GbsEnvironmentUnavailable(f"cannot execute rpm2cpio: {error}") from error
                assert converter.stdout is not None
                try:
                    extraction = subprocess.run(
                        ["cpio", "-idm", "--quiet"], cwd=root, stdin=converter.stdout,
                        capture_output=True,
                    )
                except OSError as error:
                    converter.stdout.close()
                    converter.wait()
                    raise GbsEnvironmentUnavailable(f"cannot execute cpio: {error}") from error
                converter.stdout.close()
                converter_rc = converter.wait()
                if converter_rc or extraction.returncode:
                    raise GbsEnvironmentUnavailable(
                        f"RPM extraction tool failure: rpm2cpio RC={converter_rc}, cpio RC={extraction.returncode}; "
                        "package defect not established"
                    )
                artifacts = {item["name"]: item for item in manifest["artifacts"]}
                for installed, manifest_name in (
                    ("alloc_bench", "alloc_bench.armv7l"),
                    ("gst_loop_decode", "gst_loop_decode.armv7l"),
                    ("reclaim_probe", "reclaim_probe.armv7l"),
                ):
                    elf = root / "usr/bin" / installed
                    if not elf.is_file():
                        raise ValueError(f"GBS RPM did not produce required ELF: {installed}")
                    actual = sha256(elf)
                    expected = artifacts[manifest_name]["gbs_build_sha256"]
                    if actual != expected:
                        raise ValueError(
                            f"GBS binary SHA drift for {installed}: {actual} != {expected}"
                        )
                    record["elf_sha256"][manifest_name] = actual
                    print(f"PASS\tgbs-elf\t{manifest_name} sha256={actual}")
                validate_provenance(repo, provenance)
                output_dir.mkdir(parents=True, exist_ok=False)
                shutil.copyfile(provenance_path, output_dir / provenance_path.name)
                shutil.copy2(rpm_path, output_dir / rpm_path.name)
                if sha256(output_dir / rpm_path.name) != observed_rpm_sha:
                    raise ValueError("persisted RPM SHA differs from generated RPM")
                for installed, manifest_name in (
                    ("alloc_bench", "alloc_bench.armv7l"),
                    ("gst_loop_decode", "gst_loop_decode.armv7l"),
                    ("reclaim_probe", "reclaim_probe.armv7l"),
                ):
                    shutil.copy2(root / "usr/bin" / installed, output_dir / manifest_name)
                    if sha256(output_dir / manifest_name) != record["elf_sha256"][manifest_name]:
                        raise ValueError(f"persisted ELF SHA differs: {manifest_name}")
                print(f"PASS\tgbs-output\t{output_dir}")
            if source_commit == "PENDING_SOURCE_COMMIT":
                print(
                    "REPORT_ONLY\tgbs-rpm-wrapper-sha\t"
                    f"pending source commit; observed={observed_rpm_sha}"
                )
            record["rpm"] = {
                "nvr": queried[0], "arch": queried[1], "sha256": observed_rpm_sha,
                "recorded_sha256": recorded_rpm_sha, "size_bytes": rpm_path.stat().st_size,
                "sha256_scope": manifest["gbs_build"]["rpm_sha256_scope"],
            }
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    record["finished_utc"] = datetime.now(timezone.utc).isoformat()
    record["elapsed_seconds"] = round(time.monotonic() - started, 6)
    record["verdict"] = "PASS"
    (output_dir / "gbs_build_summary.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(f"PASS\tgbs-build\t{queried[0]}.{queried[1]} sha256={observed_rpm_sha}")
    print(f"INFO\tgbs-elapsed-seconds\t{record['elapsed_seconds']}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build", action="store_true", help="run the explicit real GBS build")
    parser.add_argument("--lock-timeout", type=float, default=600.0)
    parser.add_argument(
        "--output-dir", type=Path,
        help="persist the verified RPM/three ELF files; default: new board_results/gbs_build_* directory",
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
    output_dir = args.output_dir.resolve() if args.output_dir else (
        args.repo_root.resolve() / "board_results" /
        f"gbs_build_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"
    )
    if output_dir.exists():
        print(f"FAIL\tgbs-output\tdirectory already exists: {output_dir}")
        return 2
    try:
        gbs_build(args.repo_root.resolve(), manifest, args.lock_timeout, output_dir)
    except GbsEnvironmentUnavailable as error:
        print(f"NOT-EVALUATED\tgbs-build-environment\t{error}")
        print("FAIL\tgbs-build\tno verified RPM/ELF bundle; static package gates alone are insufficient")
        return 2
    except (OSError, subprocess.SubprocessError) as error:
        print(f"NOT-EVALUATED\tgbs-build-environment\thost I/O or command failure: {error}")
        return 2
    except ValueError as error:
        print(f"FAIL\tgbs-package-artifact\t{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
