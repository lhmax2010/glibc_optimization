#!/usr/bin/env python3
"""Diff and classify stability-monitor artifacts for the v2 known-alert waiver."""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


ALLOWED_PREFIX = "/opt/usr/share/crash/livedump/"


def snapshot(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if tuple(reader.fieldnames or ()) != ("remote_path", "size", "mtime_epoch", "sha256"):
            raise ValueError(f"bad snapshot header: {path}")
        result = {}
        for row in reader:
            remote = row["remote_path"]
            if not remote.startswith(ALLOWED_PREFIX) or PurePosixPath(remote).parent.as_posix() != ALLOWED_PREFIX.rstrip("/"):
                raise ValueError(f"unsafe stability path: {remote}")
            if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", PurePosixPath(remote).name):
                raise ValueError(f"unsafe stability basename: {remote}")
            if remote in result:
                raise ValueError(f"duplicate stability path: {remote}")
            result[remote] = row
        return result


def new_paths(before: Path, after: Path) -> list[str]:
    old, new = snapshot(before), snapshot(after)
    return sorted(set(new) - set(old))


def zip_member(archive: zipfile.ZipFile, basename: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if PurePosixPath(name).name == basename
        or PurePosixPath(name).name.endswith(f".{basename}")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {basename} in {archive.filename}, got {matches}")
    return matches[0]


def inspect_archive(path: Path) -> tuple[str, dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"corrupt archive member: {path}:{bad}")
        reason = archive.read(zip_member(archive, "dump_reason")).decode("utf-8", errors="replace")
        info = json.loads(archive.read(zip_member(archive, "info.json")).decode("utf-8"))
    return reason, info


def pid_windows(pull: Path | None, workload: str) -> dict[int, str]:
    if pull is None:
        return {}
    mapping: dict[int, str] = {}
    if workload == "s4":
        for profile in ("mixed", "medium-only"):
            path = pull / "A" / profile / "rep1/pid.txt"
            if path.is_file():
                mapping[int(path.read_text().strip())] = f"A/{profile}/rep1"
        for profile in ("mixed", "medium-only"):
            for trim_at, reps in (("valley", (1, 2, 3)), ("none", (1,))):
                for rep in reps:
                    path = pull / "B" / profile / trim_at / f"rep{rep}/pid.txt"
                    if path.is_file():
                        mapping[int(path.read_text().strip())] = f"B/{profile}/{trim_at}/rep{rep}"
    elif workload == "gst":
        cells = pull / "cells"
        if cells.is_dir():
            for path in cells.glob("*/pid.txt"):
                mapping[int(path.read_text().strip())] = f"gst/{path.parent.name}"
    elif workload == "a-anchor":
        cells = pull / "cells"
        if cells.is_dir():
            for path in cells.glob("*/pid.txt"):
                mapping[int(path.read_text().strip())] = path.parent.name
    return mapping


def classify(args: argparse.Namespace) -> int:
    bands = json.loads(args.bands.read_text(encoding="utf-8"))
    registration = bands["stability_monitor"]["expected_alerts"][0]
    after_rows = snapshot(args.after)
    paths = new_paths(args.before, args.after)
    post_rows = snapshot(args.post_clean) if args.post_clean else None
    windows = pid_windows(args.pull, args.workload)
    alerts = []
    expected_candidates = []
    for remote in paths:
        archive_path = args.archive_dir / PurePosixPath(remote).name
        archived = archive_path.is_file()
        reason, info = inspect_archive(archive_path) if archived else ("", {})
        executable = str(info.get("exe_file_path", ""))
        pid_raw = info.get("threads", {}).get("pid") if isinstance(info.get("threads"), dict) else None
        pid = int(pid_raw) if isinstance(pid_raw, int) or (isinstance(pid_raw, str) and pid_raw.isdigit()) else None
        window = windows.get(pid, "unmapped")
        binary = PurePosixPath(executable).name if executable else ""
        expected_shape = (
            args.workload in ("s4", "a-anchor")
            and archived
            and binary == registration["binary_basename"]
            and registration["trigger_reason_contains"] in reason
            and window in registration["registered_windows"]
        )
        executable_prefix = registration.get("executable_prefix", f"/opt/usr/glibc_memopt/{args.workload}")
        attributable = bool(pid in windows or executable.startswith(executable_prefix))
        item = {
            "remote_path": remote,
            "size": int(after_rows[remote]["size"]),
            "sha256": after_rows[remote]["sha256"],
            "archive_present": archived,
            "reason": reason.strip(),
            "executable": executable,
            "pid": pid,
            "window": window,
            "attributable": attributable,
            "expected_shape": expected_shape,
        }
        alerts.append(item)
        if expected_shape:
            expected_candidates.append(item)

    per_window_limit = int(registration.get("max_count_per_window", registration["max_count_total"]))
    expected_by_window = {
        window: sum(item["window"] == window for item in expected_candidates)
        for window in {item["window"] for item in expected_candidates}
    }
    over_limit = (
        len(expected_candidates) > int(registration["max_count_total"])
        or any(count > per_window_limit for count in expected_by_window.values())
    )
    clean_paths = []
    for item in alerts:
        if item["expected_shape"] and not over_limit:
            present_after = post_rows is not None and item["remote_path"] in post_rows
            item["verdict"] = "FAIL" if present_after else "EXPECTED"
            item["explanation"] = (
                "matched registered reason/window/owner/count but remained after cleanup"
                if present_after else
                "known-alert waiver matched reason/window/owner/count; archived and absent after cleanup; root cause not proven"
                if post_rows is not None else
                "matched registered reason/window/owner/count; cleanup pending"
            )
            clean_paths.append(item["remote_path"])
        elif item["expected_shape"] and over_limit:
            item["verdict"] = "FAIL"
            item["explanation"] = (
                f"expected-alert count exceeds registered maximum: total={len(expected_candidates)}/"
                f"{registration['max_count_total']} per_window={expected_by_window.get(item['window'], 0)}/"
                f"{per_window_limit}"
            )
            clean_paths.append(item["remote_path"])
        elif item["attributable"]:
            item["verdict"] = "FAIL"
            item["explanation"] = "attributable alert is not covered by preregistration"
            clean_paths.append(item["remote_path"])
        else:
            item["verdict"] = "REPORT_ONLY"
            item["explanation"] = "foreign or unattributed alert; left untouched"

    present_expected = 0
    if post_rows is not None:
        present_expected = sum(item["remote_path"] in post_rows for item in expected_candidates)
    payload = {
        "schema": "glibc-memopt-demo.stability-monitor.v2",
        "workload": args.workload,
        "before_count": len(snapshot(args.before)),
        "after_count": len(after_rows),
        "new_count": len(paths),
        "expected_match_count": len(expected_candidates),
        "expected_paths_present_after_cleanup": present_expected,
        "alerts": alerts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.clean_list:
        args.clean_list.write_text("".join(f"{path}\n" for path in clean_paths), encoding="utf-8")
    for item in alerts:
        print(f"{item['verdict']}\t{item['remote_path']}\t{item['window']}")
    if not alerts:
        print(f"REGISTERED/NOT-EVALUATED\t{args.workload}\tno-new-alert")
    return 1 if any(item["verdict"] == "FAIL" for item in alerts) or present_expected else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    diff = sub.add_parser("diff")
    diff.add_argument("--before", required=True, type=Path)
    diff.add_argument("--after", required=True, type=Path)
    diff.add_argument("--output", required=True, type=Path)
    classify_parser = sub.add_parser("classify")
    classify_parser.add_argument("--before", required=True, type=Path)
    classify_parser.add_argument("--after", required=True, type=Path)
    classify_parser.add_argument("--post-clean", type=Path)
    classify_parser.add_argument("--archive-dir", required=True, type=Path)
    classify_parser.add_argument("--pull", type=Path)
    classify_parser.add_argument("--workload", required=True, choices=("s4", "gst", "a-anchor"))
    classify_parser.add_argument("--bands", required=True, type=Path)
    classify_parser.add_argument("--output", required=True, type=Path)
    classify_parser.add_argument("--clean-list", type=Path)
    args = parser.parse_args()
    if args.command == "diff":
        paths = new_paths(args.before, args.after)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("".join(f"{path}\n" for path in paths), encoding="utf-8")
        print(f"new_alerts={len(paths)}")
        return 0
    return classify(args)


if __name__ == "__main__":
    raise SystemExit(main())
