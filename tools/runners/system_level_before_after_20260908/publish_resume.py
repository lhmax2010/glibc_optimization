#!/usr/bin/env python3
"""Publish selected original resume evidence, edited only by the redaction map."""
import argparse
import hashlib
import json
import pathlib


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", type=pathlib.Path, required=True)
    p.add_argument("--output-dir", type=pathlib.Path, required=True)
    p.add_argument("--board-address", required=True)
    p.add_argument("--host-home", required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    selected = {
        "occupancy/closure.json", "occupancy/commands.json", "occupancy/PS_BEFORE.txt",
        "occupancy/PID_26799_SNAPSHOT.txt", "occupancy/PID_27105_SNAPSHOT.txt",
        "occupancy/CLOSE_26799.txt", "occupancy/CLOSE_27105.txt", "occupancy/VERIFY_ABSENT.txt",
        "occupancy/PS_AFTER.txt", "occupancy_recheck/PS_RECHECK.txt",
        "occupancy_recheck/commands.json", "occupancy_recheck/VERIFY_APPROVED_ABSENT.txt",
        "occupancy_recheck/closure.json", "occupancy_recheck/closure_corrected.json",
        "preflight/UNAME_R.txt", "preflight/UNAME_M.txt", "preflight/OS_RELEASE.txt",
        "preflight/GLIBC.txt", "preflight/MEMINFO.txt", "preflight/GOVERNORS.txt",
        "preflight/verdict.json", "preflight/commands.json", "host_tests_before_run.log", "verify_before_run.log"}
    receipt = []
    for relative in sorted(selected):
        source = a.raw / relative
        original = source.read_bytes()
        edited = original.decode().replace("\r\n", "\n").replace("\r", "\n")
        edited = edited.replace(a.board_address, "<TEST_BOARD_IP>").replace(a.host_home, "<USER_HOME>")
        target = a.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edited)
        receipt.append({"file": relative, "original_sha256": hashlib.sha256(original).hexdigest(),
                        "public_sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (a.output_dir / "publication.json").write_text(json.dumps({"edits": "CR normalization; board routing IP and host home mapped; board runtime paths retained", "files": receipt}, indent=2) + "\n")
    print("PASS published_resume_files=" + str(len(receipt)))


if __name__ == "__main__":
    main()
