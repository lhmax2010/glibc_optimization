#!/usr/bin/env python3
"""Publish compact, explicitly edited read-only STOP evidence; never board writes."""
import argparse
import hashlib
import json
import pathlib

FILES = ["sdb_version", "connect", "devices", "UNAME_R", "UNAME_M", "OS_RELEASE",
         "GLIBC", "MEMINFO", "UID", "GOVERNORS", "WORKDIR", "SPACE", "MEMPS", "GDB_STATE", "UPTIME"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", required=True, type=pathlib.Path)
    p.add_argument("--output", required=True, type=pathlib.Path)
    p.add_argument("--ip", required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    evidence = []
    hashes = {}
    for name in FILES:
        file = a.raw / "preflight" / (name + ".txt")
        payload = file.read_bytes()
        hashes[file.relative_to(a.raw).as_posix()] = hashlib.sha256(payload).hexdigest()
        text = payload.decode().replace("\r", "").replace(a.ip, "<TEST_BOARD_IP>")
        evidence.append("=== " + name + " ===\n" + text.rstrip() + "\n")
    (a.output / "preflight_raw.txt").write_text("\n".join(evidence))
    file = a.raw / "occupancy_followup/INTERACTIVE_SESSIONS.txt"
    payload = file.read_bytes()
    hashes[file.relative_to(a.raw).as_posix()] = hashlib.sha256(payload).hexdigest()
    text = payload.decode().replace("\r", "").replace(a.ip, "<TEST_BOARD_IP>")
    # Keep both complete /proc records, plus exact ps rows and the command's own RC/DONE.
    # The omitted general ps listing remains local; this is explicitly an excerpt.
    section = text.split("UID        PID", 1)[0]
    ps_rows = [line for line in text.splitlines() if line.startswith("root") and
               len(line.split()) > 1 and line.split()[1] in ("26799", "27105")]
    marks = [line for line in text.splitlines() if line in ("RC=0", "DONE_INTERACTIVE_SESSIONS")]
    if len(ps_rows) != 2 or marks != ["RC=0", "DONE_INTERACTIVE_SESSIONS"]:
        raise ValueError("occupancy excerpt shape/source marker mismatch")
    (a.output / "occupancy_excerpt.txt").write_text(section + "\n=== ps -ef: two relevant original rows ===\n" +
                                                   "\n".join(ps_rows + marks) + "\n")
    receipt = json.loads((a.raw / "contract_push_receipt.json").read_text())
    receipt.pop("boot_id")  # Ephemeral host identity unnecessary for public timing proof.
    automatic = json.loads((a.raw / "preflight/verdict.json").read_text())
    timeline = {"contract_push": receipt, "automatic_checks_original": automatic,
                "manual_occupancy_review": {"verdict": "STOP_OCCUPANCY_UNRESOLVED",
                  "reason": "two pre-existing interactive sh -l sessions on pts/0 and pts/1; ownership unresolved; idle is not exclusive-use proof",
                  "pids": [26799, 27105], "no_active_test_workload_observed": True,
                  "not_a_claim_of_confirmed_third_party_activity": True},
                "executed_experiment_cells": 0, "board_files_pushed": 0, "packages_installed": 0,
                "governor_changes": 0, "trim_injections": 0,
                "stages_2_and_3": "NOT_EXECUTED_STOP_GATE", "effective_delivery_tag": "demo-v11",
                "source_raw_sha256": hashes,
                "editing_note": "address mapped; CRLF normalized; proc evidence exact excerpts; public receipt omits ephemeral boot_id; full originals retained locally"}
    (a.output / "stop_evidence.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False) + "\n")
    for subdir in ("preflight", "occupancy_followup"):
        text = (a.raw / subdir / "commands.json").read_text().replace(a.ip, "<TEST_BOARD_IP>")
        (a.output / (subdir + "_commands.json")).write_text(text)
    print("PASS published read-only STOP evidence; measurement cells=0; demo-v11 retained")


if __name__ == "__main__":
    main()
