#!/usr/bin/env python3
"""SDB orchestration of the unchanged tagged contract; never retry a cell."""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import secrets
import shlex
import subprocess
import sys
import tarfile
import time
from preflight import Gate, TAG, git, utc
from collect_cell import ANALYSIS, collect

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = json.loads((HERE / "contract.json").read_text())
WORK = CONTRACT["workdir"]
GDB_NAMES = ("libgmp", "gdbm", "libpython3_141_0", "python3-base", "python3", "gdb")
spec = importlib.util.spec_from_file_location("stability", ROOT / "tools/reproduce/stability_monitor.py")
STABILITY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(STABILITY)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_members(archive, cell):
    members = archive.getmembers()
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != cell:
            raise ValueError("unsafe archive path")
        if not (member.isfile() or member.isdir()):
            raise ValueError("unexpected archive link/special member")
    return members


def validate_completed(raw, completed):
    """All frozen gates; ONLY the final missing-none join can be deferred."""
    ids = {(c["group"], c["arm"], c["rep"]) for c in completed}
    unpaired = any(c["arm"] == "trim" and c["group"] != "G4" and
                   (c["group"], "none", c["rep"]) not in ids for c in completed)
    try:
        return ANALYSIS.analyze(raw, {**CONTRACT, "cells": completed})
    except ValueError as error:
        # Exact error occurs ONLY at return pair_controls(rows), after every
        # frozen source/health/identity/fault/cycle gate has completed.
        if unpaired and str(error) == "missing matched none control":
            return None
        raise


class Executor(Gate):
    def __init__(self, args):
        args.output_dir.mkdir(parents=True, exist_ok=False)
        super().__init__(args.ip, args.output_dir)
        self.args = args
        self.raw = self.out / "raw"
        self.raw.mkdir()
        self.timeout = 30
        self.created = self.install_attempted = False
        self.completed, self.owned_alerts = [], []
        self.active_cell = None
        self.verified_cells = set()
        self.owner_token = secrets.token_hex(16)
        self.receipt = {"start_utc": utc(), "verdict": "STOP", "contract_tag": TAG,
                        "tag_object": git("rev-parse", TAG), "executor_commit": git("rev-parse", "HEAD"),
                        "completed_cells": [], "cleanup": "NOT-EVALUATED"}

    def run(self, label, argv, timeout=20):
        print("COMMAND", label, utc(), flush=True)
        return super().run(label, argv, timeout=max(timeout, self.timeout))

    def save(self):
        (self.out / "execution.json").write_text(json.dumps(self.receipt, indent=2) + "\n")

    def remote(self, label, command):
        # Inner controller has its own RC/DONE. Distinct outer framing avoids
        # counting those as transport success or rejecting two legitimate RCs.
        rc_marker, done = "WRAPPER_RC_" + label, "DONE_REMOTE_" + label
        body = "( " + command + " ); rc=$?; printf '\\n" + rc_marker + "=%s\\n' \"$rc\"; "
        body += "if [ \"$rc\" -eq 0 ]; then echo " + done + "; else echo FAIL_REMOTE_" + label + "; fi"
        _, output = self.run(label, ["sdb", "-s", self.serial, "shell", body])
        lines = output.splitlines()
        if lines.count(rc_marker + "=0") != 1 or lines.count(done) != 1 or "FAIL_REMOTE_" + label in lines:
            raise ValueError("remote RC/DONE gate failed: " + label)
        return "\n".join(line for line in lines if line not in (rc_marker + "=0", done)).strip()

    def push(self, path, name, expected=None):
        expected = expected or sha(path)
        if sha(path) != expected:
            raise ValueError("local asset hash mismatch: " + name)
        self.run("PUSH_" + name, ["sdb", "-s", self.serial, "push", str(path), WORK + "/" + name])
        actual = self.remote("SHA_" + name, "sha256sum " + shlex.quote(WORK + "/" + name)).split()[0]
        if actual != expected:
            raise ValueError("remote asset hash mismatch: " + name)

    def install_gdb(self):
        before = self.remote("PACKAGES_BEFORE", "for p in " + " ".join(GDB_NAMES) +
                             "; do rpm -q --queryformat '%{NAME} %{VERSION}-%{RELEASE}.%{ARCH} %{SIZE}\\n' \"$p\"; done; true")
        if "gdb 16.3-1.1.armv7l " in before:
            self.remote("GDB_EXISTING", "gdb --version")
            return
        if any(re.search(r"^" + re.escape(name) + r" ", before, re.M) for name in GDB_NAMES):
            raise ValueError("partial/pre-existing GDB dependency set; no overwrite permitted")
        space = self.remote("GDB_SPACE", "df -k /")
        rows = [line.split() for line in space.splitlines() if line.split() and line.split()[-1] == "/"]
        if len(rows) != 1 or int(rows[0][3]) * 1024 - 53010679 < CONTRACT["availability"]["root_after_gdb_install_min_bytes"]:
            raise ValueError("root-space GDB budget failure")
        source = (HERE.parent / "tizen_native_evidence_b2_20260904/manage_gdb_official_snapshot.sh").read_text()
        packages = re.findall(r"^        ([A-Za-z0-9_.-]+\.rpm)\) echo ([a-f0-9]{64})", source, re.M)
        if len(packages) != 6:
            raise ValueError("official six-package hash list missing")
        for name, expected in packages:
            self.push(self.args.gdb_cache / name, name, expected)
        argv = " ".join(shlex.quote(WORK + "/" + name) for name, _ in packages)
        self.remote("GDB_INSTALL_TEST", "rpm -Uvh --test " + argv)
        self.install_attempted = True
        self.timeout = 120
        self.remote("GDB_INSTALL", "rpm -Uvh " + argv)
        self.timeout = 30
        self.remote("GDB_VERIFY", "test \"$(rpm -q gdb)\" = gdb-16.3-1.1.armv7l && gdb --version && df -k /")

    def pull_cell(self, cell):
        remote = WORK + "/" + cell
        manifest = self.remote("MANIFEST_" + cell, f'cd {WORK} || exit 1\nfind {cell} -type f >{cell}.files || exit 1\nwhile IFS= read -r f; do sha256sum "$f" || exit 1; done <{cell}.files')
        self.remote("TAR_" + cell, f"cd {WORK} && tar --exclude=control.fifo --exclude=proc -czf {cell}.tar.gz {cell}")
        expected = self.remote("TAR_SHA_" + cell, "sha256sum " + remote + ".tar.gz").split()[0]
        archive = self.out / (cell + ".tar.gz")
        self.run("PULL_" + cell, ["sdb", "-s", self.serial, "pull", remote + ".tar.gz", str(archive)], timeout=120)
        if not archive.is_file() or sha(archive) != expected:
            raise ValueError("pulled archive integrity failure: " + cell)
        with tarfile.open(archive) as tar:
            tar.extractall(self.raw, members=checked_members(tar, cell))
        expected_files = {}
        for line in manifest.splitlines():
            digest, filename = line.split("  ", 1)
            path = pathlib.PurePosixPath(filename)
            if not re.fullmatch(r"[a-f0-9]{64}", digest) or ".." in path.parts or path.parts[0] != cell:
                raise ValueError("unsafe manifest")
            expected_files[filename] = digest
        actual_files = {p.relative_to(self.raw).as_posix(): sha(p) for p in (self.raw / cell).rglob("*") if p.is_file()}
        if not expected_files or actual_files != expected_files:
            raise ValueError("per-file pulled hash mismatch: " + cell)
        (self.out / (cell + ".integrity.json")).write_text(json.dumps({"archive_sha256": expected,
            "files": expected_files, "verdict": "PASS"}, indent=2) + "\n")
        self.verified_cells.add(cell)

    def alerts(self, cell):
        path = self.raw / cell
        before, after = STABILITY.snapshot(path / "stability_before.tsv"), STABILITY.snapshot(path / "stability_after.tsv")
        changed = [name for name in after if name not in before or after[name] != before[name]]
        rows = []
        own_pids = {int(p.read_text()) for p in self.raw.glob("*/pid.txt")}
        for name in ("controller_identity.txt", "debugger_identity.txt", "sampler_identity.txt"):
            own_pids.update(int(p.read_text().split()[0]) for p in self.raw.glob("*/" + name))
        archive_dir = self.out / "livedump"
        archive_dir.mkdir(exist_ok=True)
        for remote in changed:
            target = archive_dir / pathlib.PurePosixPath(remote).name
            self.run("ALERT_PULL_" + target.name, ["sdb", "-s", self.serial, "pull", remote, str(target)])
            if sha(target) != after[remote]["sha256"] or target.stat().st_size != int(after[remote]["size"]):
                raise ValueError("alert archive integrity failure")
            reason, info = STABILITY.inspect_archive(target)
            executable = str(info.get("exe_file_path", ""))
            pid = str(info.get("threads", {}).get("pid", ""))
            own = executable.startswith(WORK + "/") or (pid.isdigit() and int(pid) in own_pids)
            row = {"remote_path": remote, "sha256": sha(target), "reason": reason,
                   "executable": executable, "pid": pid, "attributable_to_this_round": own}
            rows.append(row)
            if own and row not in self.owned_alerts:
                self.owned_alerts.append(row)
        (path / "alert_attribution.json").write_text(json.dumps(rows, indent=2) + "\n")

    def round_snapshot(self, when):
        path = self.raw / "round_health"
        path.mkdir(exist_ok=True)
        for name, command in (("dmesg", "dmesg"), ("zram", "cat /sys/block/zram0/mm_stat")):
            output = self.remote("ROUND_" + when.upper() + "_" + name.upper(), command)
            (path / (name + "_" + when + ".txt")).write_text(output + "\n")
        output = self.remote("ROUND_" + when.upper() + "_ALERTS", '''printf 'remote_path\tsize\tmtime_epoch\tsha256\n'
for f in /opt/usr/share/crash/livedump/*.zip; do
[ -f "$f" ] || continue
size=$(stat -c %s "$f") || exit 1
stamp=$(stat -c %Y "$f") || exit 1
hash=$(sha256sum "$f") || exit 1
printf '%s\t%s\t%s\t%s\n' "$f" "$size" "$stamp" "${hash%% *}" || exit 1
done''')
        (path / ("stability_" + when + ".tsv")).write_text(output + "\n")

    def validate_round_health(self):
        path = self.raw / "round_health"
        before = (path / "dmesg_before.txt").read_text().splitlines()
        after = (path / "dmesg_after.txt").read_text().splitlines()
        increment, method = ANALYSIS.GST.dmesg_increment(before, after)
        if method != "prefix":
            raise ValueError("round dmesg history lost")
        if any(re.search(r"out of memory|oom[-_ ]kill|killed process|lowmemorykiller|low memory killer", line, re.I) for line in increment):
            raise ValueError("round OOM/LMK hard failure")
        zram = [[int(x) for x in (path / ("zram_" + when + ".txt")).read_text().split()[:3]] for when in ("before", "after")]
        if any(len(row) != 3 or min(row) < 0 for row in zram) or zram[0] != zram[1]:
            raise ValueError("round zram hard failure")
        self.receipt["round_health"] = {"oom_lmk_new": 0, "zram_three_delta": [0, 0, 0],
            "stability_before": len(STABILITY.snapshot(path / "stability_before.tsv")),
            "stability_after": len(STABILITY.snapshot(path / "stability_after.tsv")),
            "attributable_alerts_new": len(self.owned_alerts)}

    def cleanup(self):
        problems = []
        if not self.created:
            return "NO_BOARD_FILES_CREATED"
        try:
            state = self.remote("WORK_OWNER", f'if [ ! -e {WORK} ]; then echo ABSENT; else test ! -L {WORK} && test "$(cat {WORK}/owner_token.txt)" = {self.owner_token} && echo OWNED; fi')
            if state not in ("ABSENT", "OWNED"):
                raise ValueError("invalid work ownership response")
        except Exception as error:
            self.receipt["cleanup_problems"] = ["ambiguous work creation; preserved: " + str(error)]
            return "FAIL"
        if self.active_cell:
            cell = self.active_cell
            try:
                command = f'''pfile={WORK}/{cell}/controller_identity.txt
if [ -f "$pfile" ]; then
read p tick <"$pfile" || exit 1
case "$p:$tick" in *[!0-9:]*) exit 1;; esac
if [ -d /proc/$p ]; then
s=$(cat /proc/$p/stat) || exit 1; s=${{s##*) }}; set -- $s
[ "${{20}}" = "$tick" ] || exit 1
tr '\\000' ' ' </proc/$p/cmdline | grep -F '{WORK}/run_cell_remote.sh {cell}' >/dev/null || exit 1
kill -TERM "$p" || exit 1
n=0; while [ -d /proc/$p ] && [ "$n" -lt 100 ]; do sleep 0.1; n=$((n+1)); done
test ! -d /proc/$p || exit 1
fi
fi'''
                self.remote("RECOVER_CONTROLLER", command)
                if cell not in self.verified_cells:
                    self.pull_cell(cell)
                self.alerts(cell)
            except Exception as error:
                problems.append("cell recovery/archive: " + str(error))
        try:
            self.remote("RESTORE_GOVERNORS", 'for n in 0 1 2 3; do p=/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor; printf "%s\\n" schedutil >"$p" || exit 1; test "$(cat "$p")" = schedutil || exit 1; echo "$n schedutil"; done')
            self.remote("OWN_PROCESS_ABSENT", f'for p in /proc/[0-9]*; do e=$(readlink "$p/exe" 2>/dev/null) || continue; case "$e" in {WORK}/*) echo FAIL_OWN_PROCESS_$p; exit 1;; esac; done')
        except Exception as error:
            problems.append("governor/process recovery: " + str(error))
        try:
            self.remote("OWN_HELPER_ABSENT", f'''for p in /proc/[0-9]*; do
a=$(tr '\\000' '\\n' <"$p/cmdline" 2>/dev/null | sed -n '2p')
case "$a" in {WORK}/*.sh) echo FAIL_OWN_SCRIPT_$p; exit 1;; esac
done
for f in {WORK}/G*/debugger_identity.txt {WORK}/G*/sampler_identity.txt; do
test -f "$f" || continue
read p tick <"$f" || exit 1
case "$p:$tick" in *[!0-9:]*) exit 1;; esac
if [ -d /proc/$p ]; then
s=$(cat /proc/$p/stat) || exit 1; s=${{s##*) }}; set -- $s
if [ "${{20}}" = "$tick" ]; then echo FAIL_OWN_HELPER_$p; exit 1; fi
fi
done''')
        except Exception as error:
            problems.append("helper process recovery: " + str(error))
        if self.install_attempted:
            try:
                self.remote("GDB_REMOVE", "names=; for p in " + " ".join(reversed(GDB_NAMES)) +
                    '; do if rpm -q "$p" >/dev/null 2>&1; then names="$names $p"; fi; done; '
                    'if [ -n "$names" ]; then rpm -e --test $names && rpm -e $names || exit 1; fi; '
                    'for p in ' + " ".join(GDB_NAMES) + '; do if rpm -q "$p" >/dev/null 2>&1; then exit 1; fi; done')
            except Exception as error:
                problems.append("package removal: " + str(error))
        for row in self.owned_alerts:
            try:
                remote = shlex.quote(row["remote_path"])
                self.remote("ALERT_CLEAN_" + pathlib.PurePosixPath(row["remote_path"]).name,
                    f"test \"$(sha256sum {remote} | cut -d ' ' -f 1)\" = {row['sha256']} && rm -- {remote} && test ! -e {remote}")
            except Exception as error:
                problems.append("owned alert cleanup: " + str(error))
        if not problems:
            try:
                if state == "OWNED":
                    self.remote("WORKDIR_REMOVE", f'test -d {WORK} && test ! -L {WORK} && test "$(cat {WORK}/owner_token.txt)" = {self.owner_token} && rm -r -- {WORK} && test ! -e {WORK} && rmdir /opt/usr/glibc_memopt')
                else:
                    self.remote("WORKDIR_ABSENT", f"test ! -e {WORK}")
                self.remote("FINAL_REVIEW", "for n in 0 1 2 3; do cat /sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor || exit 1; done; df -k / /opt/usr; ps -ef")
            except Exception as error:
                problems.append("workdir removal: " + str(error))
        self.receipt["cleanup_problems"] = problems
        return "FAIL" if problems else "PASS"

    def execute(self):
        try:
            for filename in ("contract.json", "analyze_system_level.py"):
                relative = (HERE / filename).relative_to(ROOT).as_posix()
                if (HERE / filename).read_bytes() != subprocess.check_output(["git", "show", TAG + ":" + relative], cwd=ROOT):
                    raise ValueError("frozen contract/analyzer byte mismatch")
            if git("status", "--porcelain"):
                raise ValueError("executor must be committed in a clean snapshot before run")
            closure = json.loads(self.args.occupancy_receipt.read_text())
            if closure["verdict"] != "PASS_PM_OCCUPANCY_CLOSED":
                raise ValueError("PM occupancy closure receipt missing")
            pushed = json.loads(self.args.contract_receipt.read_text())
            if pushed["tag_object"] != self.receipt["tag_object"] or time.time_ns() - pushed["epoch_ns"] < 600000000000:
                raise ValueError("pushed contract identity/wait gate failed")
            self.receipt["contract_push_utc"] = pushed["origin_verified_utc"]
            self.receipt["push_to_run_seconds"] = (time.time_ns() - pushed["epoch_ns"]) / 1e9
            self.receipt["preflight"] = self.check()
            target = self.receipt["preflight"]["enlightenment_pid"]
            self.receipt["target_starttime"] = ANALYSIS.proc_stat(self.remote("TARGET_STAT", f"cat /proc/{target}/stat"))["starttime"]
            self.round_snapshot("before")
            self.created = True
            self.remote("PREPARE_WORK", f'test ! -e {WORK} && mkdir -p {WORK} && printf "%s\\n" {self.owner_token} >{WORK}/owner_token.txt')
            assets = {"alloc_bench_observer.armv7l": self.args.alloc,
                      "gst_loop_decode.armv7l": self.args.gst,
                      "reclaim_probe.armv7l": self.args.probe, "small_320x240.mp4": self.args.media}
            for name, path in assets.items():
                self.push(path, name, CONTRACT["assets"][name])
            for name in ("run_cell_remote.sh", "capture_point.sh"):
                self.push(HERE / name, name)
            self.push(HERE.parent / "s4_retention_20260901/sample_smaps_1s.sh", "sample_smaps_1s.sh")
            self.remote("EXECUTABLE_MODE", "chmod 755 " + " ".join(WORK + "/" + name for name in assets if name.endswith("armv7l")))
            self.install_gdb()
            for cell in CONTRACT["cells"]:
                name = cell["id"]
                self.active_cell = name
                self.receipt["active_cell"] = name
                self.save()
                self.timeout = 1500 if cell["group"] == "G3" else 360
                self.remote("CELL_" + name, f"sh {WORK}/run_cell_remote.sh {name} {self.receipt['preflight']['enlightenment_pid']} {self.receipt['target_starttime']}")
                self.timeout = 30
                self.pull_cell(name)
                self.alerts(name)
                collect(self.raw / name, cell)
                validate_completed(self.raw, self.completed + [cell])
                self.completed.append(cell)
                self.receipt["completed_cells"].append(name)
                self.active_cell = None
                self.save()
                print("PASS_CELL", name, flush=True)
            subprocess.run([sys.executable, str(HERE / "analyze_system_level.py"), "--raw", str(self.raw),
                            "--output-dir", str(self.out / "derived")], check=True)
            self.receipt["verdict"] = "PASS_COMPLETE_MATRIX"
        except Exception as error:
            self.receipt["reason"] = str(error).replace(self.addr, "<TEST_BOARD_IP>")
            print("STOP", self.receipt["reason"], flush=True)
        finally:
            self.timeout = 60
            if self.created:
                try:
                    self.round_snapshot("after")
                    self.alerts("round_health")
                    self.validate_round_health()
                    if self.owned_alerts:
                        self.receipt["verdict"] = "STOP"
                        self.receipt["reason"] = "attributable new stability-monitor alert"
                except Exception as error:
                    self.receipt["verdict"] = "STOP"
                    self.receipt["round_health_error"] = str(error)
            self.receipt["cleanup"] = self.cleanup()
            if self.receipt["cleanup"] == "FAIL":
                self.receipt["verdict"] = "STOP"
            self.receipt["end_utc"] = utc()
            self.save()
            print(json.dumps(self.receipt, indent=2), flush=True)
        return 0 if self.receipt["verdict"] == "PASS_COMPLETE_MATRIX" else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ip", required=True)
    for name in ("output-dir", "occupancy-receipt", "contract-receipt", "alloc", "gst", "probe", "media", "gdb-cache"):
        p.add_argument("--" + name, required=True, type=pathlib.Path)
    return Executor(p.parse_args()).execute()


if __name__ == "__main__":
    raise SystemExit(main())
