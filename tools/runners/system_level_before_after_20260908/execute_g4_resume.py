#!/usr/bin/env python3
"""Post-reboot G4-only continuation. Accepted G1/G2/G3 cannot be scheduled here."""
import argparse
import json
import pathlib
import re
import shlex

from close_approved_sessions import foreign_sessions  # parser only; never close_command
from execute_contract import Executor, CONTRACT, ANALYSIS, ROOT, GDB_NAMES, STABILITY, git
from publish_measurement import digest, verified_manifest
from publish_stopped_measurement import completed_contract
from sdb_request import residue_batches


def accepted_prefix(run):
    receipt_path = run / "execution.json"
    receipt = json.loads(receipt_path.read_text())
    partial = completed_contract(receipt)
    # Bind the accepted set to the already-published compact evidence, not a
    # caller's new declaration. The original STOP/failed G4 remains untouched.
    published = json.loads((ROOT / "data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json").read_text())
    if receipt != published["execution"]:
        raise ValueError("accepted-prefix execution differs from published receipt")
    for cell in partial["cells"]:
        name = cell["id"]
        proof = verified_manifest(run, run / "raw", name)
        if proof != published["pull_manifests"][name]:
            raise ValueError("accepted-prefix pull differs from published proof: " + name)
    rows = ANALYSIS.analyze(run / "raw", partial)
    if len(rows) != 330:
        raise ValueError("accepted-prefix requires 18 cells / 330 release pairs")
    return {"execution_sha256": digest(receipt_path), "executor_commit": receipt["executor_commit"],
            "completed_cells": receipt["completed_cells"], "verdict": "PRESERVED_ACCEPTED_PREFIX",
            "scope": "previous boot; no execution or modification of these 18 cells"}


class G4Resume(Executor):
    success_verdict = "PASS_G4_ONLY"

    def selected_cells(self):
        cells = [c for c in CONTRACT["cells"] if c["group"] == "G4"]
        if [c["id"] for c in cells] != ["G4_trim_r1", "G4_trim_r2", "G4_trim_r3"]:
            raise ValueError("G4-only schedule mismatch")
        return cells

    def asset_paths(self):
        return {"reclaim_probe.armv7l": self.args.probe}

    def local_authority(self):
        self.receipt["accepted_prefix"] = accepted_prefix(self.args.accepted_run)
        self.receipt["authority"] = {"approved_by": "PM", "date": "2026-09-08",
            "scope": "post-reboot G4-only; previous exact-PID termination authorization NOT reused",
            "reboot": "PM reports manual reboot on 2026-09-08; fresh checks define current restoration",
            "uninstall_warnings": "record warnings/residue; package inventory must match before"}
        refs = git("ls-remote", "origin", "refs/heads/main").split()
        if len(refs) != 2 or refs[0] != self.receipt["executor_commit"]:
            raise ValueError("G4 executor must be pushed on origin/main before board connection")

    def check(self):
        result = super().check()
        boot = self.remote("POSTREBOOT_BOOT_ID", "cat /proc/sys/kernel/random/boot_id")
        if not re.fullmatch(r"[a-f0-9-]{36}", boot):
            raise ValueError("invalid post-reboot boot identity")
        ps = self.remote("POSTREBOOT_SESSIONS", 'printf "COLLECTOR_PID=%s\\n" "$$"; ps -ww -eo pid,ppid,tty,lstart,etime,args')
        if not re.search(r"\bPID\s+PPID\s+TT", ps) or not re.search(r"^\s*1\s+", ps, re.M):
            raise ValueError("interactive-session snapshot missing process table")
        sessions = foreign_sessions(ps)
        if sessions:
            raise ValueError("occupied/unknown interactive sessions; no clearing authorized: " + repr(sessions))
        self.round_snapshot("postreboot")
        self.packages_before = self.inventory("PACKAGE_INVENTORY_BEFORE")
        result.update(boot_id=boot, interactive_sessions=[], hygiene="PASS_FRESH_POSTREBOOT")
        self.receipt["preflight"] = result
        self.save()
        return result

    def inventory(self, label):
        text = self.remote(label, "LC_ALL=C rpm -qa --queryformat '%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\\n'")
        rows = text.splitlines()
        if not rows or any(not re.fullmatch(r"[A-Za-z0-9_+.-]+ [A-Za-z0-9_+~:.-]+-[A-Za-z0-9_+~.-]+\.[A-Za-z0-9_]+", r) for r in rows):
            raise ValueError("invalid full RPM inventory: " + label)
        return sorted(rows)

    def install_gdb(self):
        super().install_gdb()
        self.remote("GDB_PYTHON_CAPABILITY", "gdb -nx -nh -batch -ex 'python import sys; print(\"DONE_GDB_PYTHON \" + sys.version)' ")
        if self.install_attempted:
            text = self.remote("GDB_INSTALLED_PATHS", "rpm -ql " + " ".join(GDB_NAMES))
            self.package_paths = sorted(set(text.splitlines()))
            if not self.package_paths or any(not p.startswith("/") or "\n" in p for p in self.package_paths):
                raise ValueError("invalid installed package file inventory")

    def complete_analysis(self):
        rows = ANALYSIS.analyze(self.raw, {**CONTRACT, "cells": self.selected_cells()})
        output = self.out / "derived"
        output.mkdir()
        ANALYSIS.write_tsv(output / "g4_cycles.tsv", rows)
        ANALYSIS.write_tsv(output / "g4_summary.tsv", ANALYSIS.summarize(rows))
        # Recheck preservation after execution; never write to the accepted run.
        if accepted_prefix(self.args.accepted_run) != self.receipt["accepted_prefix"]:
            raise ValueError("accepted-prefix changed during G4 continuation")

    def cleanup(self):
        status = super().cleanup()
        if not self.created:
            return status
        try:
            after = self.inventory("PACKAGE_INVENTORY_AFTER")
            before = self.packages_before
            self.receipt["package_inventory"] = {"before_count": len(before), "after_count": len(after),
                "added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after))}
            if after != before:
                raise ValueError("package inventory not restored")
            residual = []
            paths = getattr(self, "package_paths", [])
            for label, command in residue_batches(paths):
                text = self.remote(label, command)
                residual.extend(text.splitlines())
            self.receipt["package_residue_observations"] = residual
            self.receipt["package_warning_policy"] = "PM: warning text and remaining/shared paths recorded, inventory restored; nonblocking"
            self.round_snapshot("after_cleanup")
            self.alerts("round_health", after_name="after_cleanup")
            health = self.raw / "round_health"
            before = (health / "dmesg_before.txt").read_text().splitlines()
            after = (health / "dmesg_after_cleanup.txt").read_text().splitlines()
            increment, method = ANALYSIS.GST.dmesg_increment(before, after)
            if method != "prefix" or any(re.search(r"out of memory|oom[-_ ]kill|killed process|lowmemorykiller|low memory killer", line, re.I) for line in increment):
                raise ValueError("post-cleanup dmesg health failure")
            zram = [[int(x) for x in (health / ("zram_" + when + ".txt")).read_text().split()[:3]]
                    for when in ("before", "after_cleanup")]
            if any(len(r) != 3 or min(r) < 0 for r in zram) or zram[0] != zram[1]:
                raise ValueError("post-cleanup zram health failure")
            boot = self.remote("POST_CLEANUP_BOOT_ID", "cat /proc/sys/kernel/random/boot_id")
            if boot != self.receipt["preflight"]["boot_id"]:
                raise ValueError("board boot changed during continuation")
            self.receipt["post_cleanup_health"] = {"oom_lmk_new": 0, "zram_three_delta": [0, 0, 0],
                "stability_count": len(STABILITY.snapshot(health / "stability_after_cleanup.tsv")),
                "attributable_alerts_new": len(self.owned_alerts), "boot_id_unchanged": True}
            if self.owned_alerts:
                # Newly attributable uninstall-time artifacts are still archived
                # before exact-hash removal; they remain a hard failure.
                for row in self.owned_alerts:
                    remote = shlex.quote(row["remote_path"])
                    self.remote("POST_CLEAN_ALERT_" + pathlib.PurePosixPath(row["remote_path"]).name,
                        f'if [ -e {remote} ]; then hash=$(sha256sum {remote}) || exit 1; '
                        f'test "${{hash%% *}}" = {row["sha256"]} && rm -- {remote} && test ! -e {remote}; fi')
                raise ValueError("attributable new stability-monitor alert including cleanup")
        except Exception as error:
            self.receipt.setdefault("cleanup_problems", []).append(str(error))
            status = "FAIL"
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--preflight-only", action="store_true", help="fresh read-only gate; no pushes or package changes")
    for name in ("output-dir", "accepted-run", "contract-receipt", "probe", "gdb-cache"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(args.accepted_run.resolve()):
        parser.error("new output must not be inside the accepted run")
    return G4Resume(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
