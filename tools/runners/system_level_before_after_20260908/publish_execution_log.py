#!/usr/bin/env python3
"""Publish a terminal execution's selected original logs, including STOP runs.

This is a log transcription only, not measurement analysis or a completion claim.
Only CR removal, board-address replacement and host-home replacement are applied.
Unselected XML, archives, media and full time series remain local.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import pathlib
import re
import tempfile


ROOT_NAMES = frozenset((
    "sdb_version", "connect", "devices", "UNAME_R", "UNAME_M", "OS_RELEASE",
    "GLIBC", "MEMINFO", "UID", "GOVERNORS", "WORKDIR", "PROCESSES", "TCP",
    "SPACE", "MEMPS", "GDB_STATE", "UPTIME", "HEALTH_READONLY", "PACKAGES_BEFORE",
    "TARGET_STAT", "PREPARE_WORK", "EXECUTABLE_MODE", "RECOVER_CONTROLLER",
    "RESTORE_GOVERNORS", "OWN_PROCESS_ABSENT", "OWN_HELPER_ABSENT", "WORK_OWNER",
    "WORKDIR_REMOVE", "WORKDIR_ABSENT", "FINAL_REVIEW",
))
ROOT_PREFIXES = ("SHA_", "CELL_", "GDB_", "ROUND_", "ALERT_CLEAN_")
CELL_PATTERN = re.compile(r"(?:G[123]_(?:trim|none)_r[123]|G4_trim_r[123])")
CELL_FILES = frozenset((
    "exit_status.txt", "governor_before.txt", "governor_run.txt", "governor_after.txt",
    "zram_before.txt", "zram_after.txt", "stability_before.tsv", "stability_after.tsv",
    "dmesg_increment.txt", "alert_attribution.json", "external_sampler_meta.txt",
    "pid.txt", "controller_identity.txt", "debugger_identity.txt", "sampler_identity.txt",
    "start_ns.txt", "end_ns.txt",
    "injection_start_ns.txt", "injection_end_ns.txt", "idle_start_ns.txt", "idle_end_ns.txt",
    "idle_stat_start.txt", "idle_stat_end.txt",
    "m7.gdb", "gdb_m7.txt", "gdb_m7.txt.stderr", "gdb_trim.txt", "gdb_trim.txt.stderr", "controller.log",
))
ROUND_FILES = frozenset((
    "dmesg_before.txt", "dmesg_after.txt", "dmesg_increment.txt", "zram_before.txt",
    "zram_after.txt", "stability_before.tsv", "stability_after.tsv", "alert_attribution.json",
))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_symlink(path):
    """Check every existing path component without resolving symlinks away."""
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlink rejected in execution-log path")


def terminal_receipt(data):
    receipt = json.loads(data.decode("utf-8"))
    if receipt.get("verdict") not in ("PASS_COMPLETE_MATRIX", "STOP"):
        raise ValueError("execution has no supported terminal verdict")
    end = receipt.get("end_utc")
    if not isinstance(end, str) or not end:
        raise ValueError("execution is still active or missing end_utc")
    try:
        stamp = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("execution has invalid end_utc") from error
    if stamp.tzinfo is None:
        raise ValueError("execution end_utc must include a timezone")
    cleanup = receipt.get("cleanup")
    if cleanup not in ("PASS", "FAIL", "NO_BOARD_FILES_CREATED", "VERIFIED_WORK_ABSENT"):
        raise ValueError("cleanup is not terminal; refusing active-run publication")
    return receipt


def select_files(run):
    selected = []

    def include(path, required=False):
        no_symlink(path)
        if path.exists():
            if not path.is_file():
                raise ValueError("selected execution log is not a regular file")
            selected.append(path)
        elif required:
            raise ValueError("required execution log missing: " + path.name)

    include(run / "execution.json", required=True)
    # A failure before the first transport command can legitimately have no
    # commands.json; do not manufacture an empty command record in that case.
    include(run / "commands.json")
    for path in sorted(run.glob("*.txt")):
        if path.stem in ROOT_NAMES or path.stem.startswith(ROOT_PREFIXES):
            include(path)
    raw = run / "raw"
    no_symlink(raw)
    if raw.exists():
        if not raw.is_dir():
            raise ValueError("raw execution-log input is not a directory")
        for directory in sorted(raw.iterdir()):
            if CELL_PATTERN.fullmatch(directory.name):
                names = CELL_FILES
            elif directory.name == "round_health":
                names = ROUND_FILES
            else:
                continue
            no_symlink(directory)
            if not directory.is_dir():
                raise ValueError("selected raw log group is not a directory")
            for name in sorted(names):
                include(directory / name)
    return sorted(selected, key=lambda path: path.relative_to(run).as_posix())


def render_public(original, board_address, host_home):
    text = original.decode("utf-8")  # No lossy replacement or silent byte edits.
    edits = []
    for old, new, label in (("\r", "", "CR_REMOVED"),
                            (board_address, "<TEST_BOARD_IP>", "BOARD_ADDRESS_REPLACED"),
                            (host_home, "<USER_HOME>", "HOST_HOME_REPLACED")):
        if old in text:
            edits.append(label)
            text = text.replace(old, new)
    return text.encode("utf-8"), edits


def publish(run, output, board_address, host_home):
    board_address = str(ipaddress.IPv4Address(board_address))
    host_home = host_home.rstrip("/")
    if not host_home.startswith("/") or host_home in ("", "/") or any(char in host_home for char in ("\n", "\r", "\0")):
        raise ValueError("host-home must be a non-root absolute home path")
    run, output = pathlib.Path(run).absolute(), pathlib.Path(output).absolute()
    if ".." in run.parts or ".." in output.parts:
        raise ValueError("parent traversal is not accepted for log publication")
    no_symlink(run)
    no_symlink(output)
    if not run.is_dir():
        raise ValueError("run directory missing")
    if output.exists():
        raise ValueError("refuse to overwrite existing execution-log publication")
    # Do not let a mistaken output path mutate the original run under audit.
    if output == run or run in output.parents:
        raise ValueError("publication must be outside the original run directory")
    files = select_files(run)
    snapshots = {path.relative_to(run).as_posix(): path.read_bytes() for path in files}
    receipt = terminal_receipt(snapshots["execution.json"])
    manifest = {
        "schema": "system-before-after.execution-log-publication.v1",
        "scope": "Original log transcription only; no measurement derivation. Full originals remain local and are available on request.",
        "verdict": receipt["verdict"], "cleanup": receipt["cleanup"], "execution_end_utc": receipt["end_utc"],
        "editing": "Only CR removal, board address -> <TEST_BOARD_IP>, host home -> <USER_HOME>; board runtime paths retained.",
        "commands_record_present": "commands.json" in snapshots,
        "files": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".execution-log-publication-", dir=output.parent) as temporary:
        staged = pathlib.Path(temporary) / "publication"
        staged.mkdir()
        for relative, original in snapshots.items():
            public, edits = render_public(original, board_address, host_home)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(public)
            manifest["files"].append({"path": relative, "original_sha256": sha(original),
                                      "public_sha256": sha(public), "edits": edits})
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        # Refuse changes after the terminal snapshot was read, before publishing.
        for relative, original in snapshots.items():
            source = run / relative
            no_symlink(source)
            if source.read_bytes() != original:
                raise ValueError("execution log changed during publication: " + relative)
        no_symlink(output)
        if output.exists():
            raise ValueError("refuse to overwrite existing execution-log publication")
        staged.rename(output)
    print("PASS terminal execution-log publication verdict=" + receipt["verdict"] + " cleanup=" + receipt["cleanup"])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    parser.add_argument("--board-address", required=True)
    parser.add_argument("--host-home", required=True)
    args = parser.parse_args()
    try:
        publish(args.run, args.output_dir, args.board_address, args.host_home)
    except (ValueError, OSError) as error:
        message = str(error).replace(args.board_address, "<TEST_BOARD_IP>").replace(args.host_home, "<USER_HOME>")
        print("FAIL execution-log publication: " + message)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
