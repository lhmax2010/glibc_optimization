#!/usr/bin/env python3
"""One-round PM authorization wrapper, NOT a default root-on workflow."""
import argparse
import json
import pathlib
import re

from execute_g4_resume import G4Resume
from preflight import utc

AUTHORIZATION = "PM-G4-20260910"


class AuthorizedG4(G4Resume):
    elevation_attempted = False

    def check(self):
        # Never elevate a device on its IP alone. Full environment/hygiene gates
        # run again through the unchanged G4-only executor after elevation.
        _, connected = self.run("AUTH_CONNECT", ["sdb", "connect", self.addr])
        if re.search(r"failed|unable|cannot|error|HOST_TIMEOUT", connected, re.I):
            raise ValueError("board connection failed; no additional connection attempt")
        if "rpi4" not in self.remote("AUTH_UNAME_R", "uname -r"):
            raise ValueError("pre-elevation kernel identity mismatch")
        if self.remote("AUTH_UNAME_M", "uname -m") != "armv7l":
            raise ValueError("pre-elevation architecture mismatch")
        release = self.remote("AUTH_OS_RELEASE", "cat /etc/os-release")
        if "BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l" not in release.splitlines():
            raise ValueError("pre-elevation BUILD_ID mismatch")
        before = self.remote("AUTH_ID_BEFORE", "id")
        if not re.match(r"uid=5001(?:\(|\s)", before):
            raise ValueError("PM authorization expected rebooted UID=5001; observed " + before)
        self.receipt["root_authorization"] = {"approved_by": "PM", "decision_date": "2026-09-10",
            "scope": "this G4 continuation and cleanup only; no reboot; not a default harness behavior",
            "id_before": before, "start_utc": utc(), "root_off": "NOT-EVALUATED"}
        self.elevation_attempted = True
        self.save()
        self.run("AUTH_ROOT_ON", ["sdb", "-s", self.serial, "root", "on"])
        after = self.remote("AUTH_ID_AFTER_ON", "id")
        self.receipt["root_authorization"]["id_after_on"] = after
        self.save()
        if not re.match(r"uid=0(?:\(|\s)", after):
            raise ValueError("authorized root-on did not produce UID=0")
        return super().check()

    def restore_nonroot(self):
        record = self.receipt["root_authorization"]
        record["off_attempts"] = []
        # One initial attempt plus at most one retry, only for root-off. Never
        # retry a measurement, identity failure, root-on, or occupied gate.
        for attempt in (1, 2):
            item = {"attempt": attempt, "start_utc": utc()}
            record["off_attempts"].append(item)
            try:
                self.run("AUTH_ROOT_OFF_%d" % attempt, ["sdb", "-s", self.serial, "root", "off"])
                observed = self.remote("AUTH_ID_AFTER_OFF_%d" % attempt, "id")
                item["id"] = observed
                found = re.match(r"uid=(\d+)(?:\(|\s)", observed)
                if not found or int(found[1]) == 0:
                    raise ValueError("root-off did not verify a non-root session")
                record["root_off"] = "PASS_NONROOT"
                return True
            except Exception as error:
                item["error"] = str(error).replace(self.addr, "<TEST_BOARD_IP>")
            finally:
                item["end_utc"] = utc()
                try:
                    self.save()
                except Exception as error:
                    # Host log failure must not prevent root-off recovery.
                    # It still blocks a successful receipt.
                    record["recording_error"] = str(error).replace(self.addr, "<TEST_BOARD_IP>")
                    print("FAIL_AUTH_RECORDING", record["recording_error"], flush=True)
        record["root_off"] = "FAIL"
        return False

    def execute(self):
        rc = 1
        try:
            rc = super().execute()
        finally:
            # Parent has already finished its board cleanup on success/failure.
            # This is the last board operation, including when root-on failed.
            if self.elevation_attempted:
                self.timeout = 30
                if not self.restore_nonroot():
                    self.receipt["verdict"] = "STOP"
                    self.receipt["root_restore_error"] = "root-off failed after at most one retry"
                    rc = 1
                if self.receipt["root_authorization"].get("recording_error"):
                    self.receipt["verdict"] = "STOP"
                    rc = 1
                self.receipt["end_utc"] = utc()
                self.save()
                print("FINAL_AUTHORIZED_G4", json.dumps(self.receipt), flush=True)
        return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pm-authorization", choices=[AUTHORIZATION], required=True)
    parser.add_argument("--ip", required=True)
    for name in ("output-dir", "accepted-run", "contract-receipt", "probe", "gdb-cache"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(args.accepted_run.resolve()):
        parser.error("new output must not be inside the accepted run")
    return AuthorizedG4(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
