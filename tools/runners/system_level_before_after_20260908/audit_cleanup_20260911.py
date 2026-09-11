#!/usr/bin/env python3
"""Delayed read-only cleanup audit: NO measurement, push or package change.

Optional root-on requires both a demonstrated read-permission need and the PM
token; bounded root-off runs last. Findings needing ownership review are kept
for exact metadata/archive-based disposition, not speculatively removed here.
Only already-archived, exactly hash-bound attributable livedumps may be removed.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shlex
import subprocess

from preflight import Gate, ROOT, TAG, git, utc
from execute_contract import Executor, CONTRACT, STABILITY, ANALYSIS, GDB_NAMES, WORK
from execute_g4_resume import G4Resume
from close_approved_sessions import foreign_sessions
from run_authorized_g4_20260910 import AuthorizedG4
from sdb_request import residue_batches, residue_command

SOURCE = ROOT / "data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution"
PM_TOKEN = "PM-G4-CLEANUP-20260910"


def original_body(label, text):
    marks = ["WRAPPER_RC_" + label + "=0", "DONE_REMOTE_" + label]
    lines = text.replace("\r", "").splitlines()
    if any(lines.count(m) != 1 for m in marks) or "FAIL_REMOTE_" + label in lines:
        raise ValueError("prior source RC/DONE failed: " + label)
    return "\n".join(line for line in lines if line not in marks).strip()


def local_sources():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    for row in manifest["files"]:
        path = SOURCE / row["path"]
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row["public_sha256"]:
            raise ValueError("prior source public hash mismatch: " + row["path"])
    receipt = json.loads((SOURCE / "execution.json").read_text())
    if (receipt["completed_cells"] != ["G4_trim_r1", "G4_trim_r2", "G4_trim_r3"] or
            receipt["root_authorization"]["root_off"] != "PASS_NONROOT"):
        raise ValueError("three completed G4 and non-root receipt required")
    for name in ("contract.json", "analyze_system_level.py"):
        rel = "tools/runners/system_level_before_after_20260908/" + name
        if subprocess.check_output(["git", "show", TAG + ":" + rel], cwd=ROOT) != (ROOT / rel).read_bytes():
            raise ValueError("frozen contract/analyzer changed")
    paths = original_body("GDB_INSTALLED_PATHS", (SOURCE / "GDB_INSTALLED_PATHS.txt").read_text()).splitlines()
    batches = residue_batches(sorted(set(paths)))
    if not batches:
        raise ValueError("empty prior package path inventory")
    inventory = sorted(original_body("PACKAGE_INVENTORY_BEFORE",
                        (SOURCE / "PACKAGE_INVENTORY_BEFORE.txt").read_text()).splitlines())
    return receipt, batches, inventory


def health_delta(old_dmesg, new_dmesg, old_zram, new_zram):
    increment, method = ANALYSIS.GST.dmesg_increment(old_dmesg.splitlines(), new_dmesg.splitlines())
    if method != "prefix":
        raise ValueError("delayed cleanup dmesg history lost; cannot bridge unobserved interval")
    if any(re.search(r"out of memory|oom[-_ ]kill|killed process|lowmemorykiller|low memory killer", line, re.I)
           for line in increment):
        raise ValueError("delayed cleanup OOM/LMK hard failure")
    zram = [[int(x) for x in text.split()[:3]] for text in (old_zram, new_zram)]
    if any(len(row) != 3 or min(row) < 0 for row in zram) or zram[0] != zram[1]:
        raise ValueError("delayed cleanup zram health failure")
    return increment


class CleanupAudit(Gate):
    remote = Executor.remote
    round_snapshot = Executor.round_snapshot
    inventory = G4Resume.inventory
    restore_nonroot = AuthorizedG4.restore_nonroot
    elevation_attempted = False

    def __init__(self, args):
        args.output_dir.mkdir(parents=True, exist_ok=False)
        super().__init__(args.ip, args.output_dir)
        self.args = args
        self.raw = self.out / "raw"
        self.raw.mkdir()
        self.receipt = {"schema": "system-before-after.delayed-cleanup.v1", "start_utc": utc(),
            "verdict": "STOP", "pm_decision_date": "2026-09-10", "approved_by": "PM",
            "scope": "read-only delayed cleanup, accepted 21 measured cells never rerun",
            "measurement_cells_run": 0, "board_files_pushed": 0, "packages_changed": 0,
            "governor_writes": 0, "processes_terminated": 0, "root_elevation": "NOT_NEEDED"}

    def save(self):
        (self.out / "audit.json").write_text(json.dumps(self.receipt, indent=2) + "\n")

    def run(self, label, argv, timeout=20):
        print("COMMAND", label, utc(), flush=True)
        return super().run(label, argv, timeout)

    def identity(self, prefix):
        if "rpi4" not in self.remote(prefix + "UNAME_R", "uname -r"):
            raise ValueError("kernel identity mismatch")
        if self.remote(prefix + "UNAME_M", "uname -m") != "armv7l":
            raise ValueError("architecture identity mismatch")
        release = self.remote(prefix + "OS_RELEASE", "cat /etc/os-release")
        if "BUILD_ID=" + CONTRACT["identity"]["build_id"] not in release.splitlines():
            raise ValueError("BUILD_ID mismatch")
        if self.remote(prefix + "GLIBC", "rpm -q glibc") != CONTRACT["identity"]["glibc"]:
            raise ValueError("glibc drift")
        memory = self.remote(prefix + "MEMINFO", "cat /proc/meminfo")
        found = re.search(r"^MemTotal:\s+(\d+) kB$", memory, re.M)
        if not found or not 8036234 <= int(found[1]) <= 8198582:
            raise ValueError("MemTotal drift")

    def access(self, label):
        text = self.remote(label, '''LC_ALL=C; export LC_ALL
result=PASS_READ_ACCESS
probe=$(dmesg 2>&1); code=$?
if [ "$code" -ne 0 ]; then
printf 'DMESG_READ_RC=%s\\n%s\\n' "$code" "$probe"
case "$probe" in *'Permission denied'*|*'Operation not permitted'*) result=NEEDS_ROOT;; *) result=ACCESS_ERROR;; esac
fi
d=/opt/usr/share/crash/livedump
kind=$(stat -c %F "$d" 2>&1); code=$?
if [ "$code" -eq 0 ]; then
if [ "$kind" != directory ]; then echo CRASH_DIRECTORY_BAD_TYPE; result=ACCESS_ERROR
elif [ ! -r "$d" ] || [ ! -x "$d" ]; then
echo CRASH_DIRECTORY_NOT_READABLE; if [ "$result" != ACCESS_ERROR ]; then result=NEEDS_ROOT; fi; fi
elif [ "$code" -eq 1 ]; then
case "$kind" in *': No such file or directory') :;;
*'Permission denied'*|*'Operation not permitted'*) printf '%s\\n' "$kind"; if [ "$result" != ACCESS_ERROR ]; then result=NEEDS_ROOT; fi;;
*) printf '%s\\n' "$kind"; result=ACCESS_ERROR;; esac
else printf '%s\\n' "$kind"; result=ACCESS_ERROR; fi
printf '%s\\n' "$result"''')
        if text.splitlines()[-1:] == ["PASS_READ_ACCESS"]:
            return False
        if text.splitlines()[-1:] != ["NEEDS_ROOT"]:
            raise ValueError("unrecognized read-access probe")
        return True

    def attribute_alerts(self, old, new, prior, when):
        rows = []
        for path in sorted(new):
            if path in old and new[path] == old[path]:
                continue
            directory = self.out / "livedump" / when
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / pathlib.PurePosixPath(path).name
            self.run("ALERT_PULL_" + when + "_" + target.name,
                     ["sdb", "-s", self.serial, "pull", path, str(target)])
            expected = new[path]
            if (not target.is_file() or target.is_symlink() or target.stat().st_size != int(expected["size"]) or
                    hashlib.sha256(target.read_bytes()).hexdigest() != expected["sha256"]):
                raise ValueError("livedump pull integrity failure")
            reason, info = STABILITY.inspect_archive(target)
            exe = str(info.get("exe_file_path", ""))
            pid = str(info.get("threads", {}).get("pid", ""))
            windows = []
            for cell in prior["completed_cells"]:
                base = SOURCE / "raw" / cell
                start = int((base / "start_ns.txt").read_text())
                end = int((base / "end_ns.txt").read_text())
                if start <= 0 or end <= start:
                    raise ValueError("invalid original board-clock window")
                windows.append((start, end))
            stamp = int(expected["mtime_epoch"])
            # All clocks here are BOARD clocks. A whole mtime second must fit
            # within a measured window for deletion; boundary overlap alone is
            # ambiguous and requires attribution, never an automatic erase.
            in_window = any(start <= stamp * 10**9 and (stamp + 1) * 10**9 <= end for start, end in windows)
            overlaps = any(stamp * 10**9 <= end and (stamp + 1) * 10**9 > start for start, end in windows)
            known_pids = {str(prior["preflight"]["enlightenment_pid"])}
            known_helpers = {}
            for cell in prior["completed_cells"]:
                for filename in ("controller_identity.txt", "debugger_identity.txt", "sampler_identity.txt"):
                    identity = SOURCE / "raw" / cell / filename
                    if identity.is_file():
                        helper_pid = identity.read_text().split()[0]
                        known_pids.add(helper_pid)
                        allowed = {"/usr/bin/gdb"} if filename == "debugger_identity.txt" else {
                            "/bin/sh", "/usr/bin/sh", "/bin/bash", "/usr/bin/bash"}
                        known_helpers.setdefault(helper_pid, set()).update(allowed)
            identity_match = pid in known_pids and (exe.startswith(WORK + "/") or exe in known_helpers.get(pid, set()) or
                (pid == str(prior["preflight"]["enlightenment_pid"]) and pathlib.PurePosixPath(exe).name == "enlightenment"))
            own = in_window and identity_match
            rows.append({"remote_path": path, **expected, "reason": reason, "executable": exe, "pid": pid,
                         "in_original_g4_window": in_window, "mtime_boundary_ambiguous": overlaps and not in_window and identity_match,
                         "attributable": own,
                         "verdict": "FAIL" if own else "REPORT_ONLY_UNATTRIBUTED_LEFT_UNTOUCHED"})
        self.receipt["alerts_" + when] = rows
        self.save()
        for index, row in enumerate(rows):
            if row["attributable"]:
                path = shlex.quote(row["remote_path"])
                self.remote("CLEAN_OWN_ALERT_" + when + "_%04d" % index,
                    f'test ! -L {path} && test -f {path} || exit 1; '
                    f'hash=$(sha256sum {path}) || exit 1; '
                    f'test "${{hash%% *}}" = {row["sha256"]} && rm -- {path} && test ! -e {path} && test ! -L {path}')
                row["archived_then_removed_verified"] = True
        if any(row["attributable"] for row in rows):
            raise ValueError("attributable new alert; archived/cleaned, no waiver")
        if any(row["mtime_boundary_ambiguous"] for row in rows):
            raise ValueError("same-identity alert overlaps second-resolution window boundary; archived, preserved for attribution")

    def collect(self, prior, batches, inventory):
        self.run("sdb_version", ["sdb", "version"])
        _, text = self.run("connect", ["sdb", "connect", self.addr])
        if re.search(r"failed|unable|cannot|error|HOST_TIMEOUT", text, re.I):
            raise ValueError("connection failure; no retry")
        self.identity("PRE_")
        before_id = self.remote("ID_BEFORE", "id")
        self.receipt["id_before"] = before_id
        if not re.match(r"uid=5001(?:\(|\s)", before_id):
            raise ValueError("unexpected initial session identity; no implicit root ownership")
        if self.access("READ_ACCESS"):
            if self.args.pm_authorization != PM_TOKEN:
                raise ValueError("read access needs explicit one-round PM root authorization")
            self.receipt["root_elevation"] = "NECESSARY_READ_PERMISSION"
            self.receipt["root_authorization"] = {"approved_by": "PM", "decision_date": "2026-09-10",
                "scope": "delayed G4 cleanup only", "id_before": before_id, "root_off": "NOT-EVALUATED"}
            self.elevation_attempted = True
            self.save()
            self.run("AUTH_ROOT_ON", ["sdb", "-s", self.serial, "root", "on"])
            after_id = self.remote("AUTH_ID_AFTER_ON", "id")
            self.receipt["root_authorization"]["id_after_on"] = after_id
            if not re.match(r"uid=0(?:\(|\s)", after_id):
                raise ValueError("root-on did not establish root")
            self.identity("ROOT_")
            if self.access("ROOT_READ_ACCESS"):
                raise ValueError("read permissions unavailable even after authorized elevation")
        boot = self.remote("BOOT_ID", "cat /proc/sys/kernel/random/boot_id")
        self.receipt["boot_id"] = boot
        if boot != prior["preflight"]["boot_id"]:
            raise ValueError("boot differs from completed G4; cannot bridge delayed cleanup")
        ps = self.remote("SESSIONS", 'printf "COLLECTOR_PID=%s\\n" "$$"; ps -ww -eo pid,ppid,tty,lstart,etime,args')
        if not re.search(r"^\s*1\s+", ps, re.M) or not re.search(r"\bPID\s+PPID\s+TT", ps):
            raise ValueError("incomplete process table")
        if foreign_sessions(ps):
            raise ValueError("foreign interactive session; no clearing authority")
        names = self.remote("PROCESS_NAMES", "ps -ww -eo pid,comm,args")
        if not re.search(r"^\s*1\s+", names, re.M) or not re.search(r"\bPID\s+COMMAND", names):
            raise ValueError("incomplete process-name/command table")
        for line in names.splitlines():
            cols = line.split(None, 2)
            if len(cols) < 2:
                continue
            if re.search(r"alloc_bench|gst_loop_decode|gst-launch|^gdb$|sample_smaps|run_cell_remote", cols[1]):
                raise ValueError("remaining/foreign load; metadata recorded, not terminated")
            if (len(cols) == 3 and
                    re.search(r"(?:sample_smaps[^ ]*\.sh|run_cell_remote\.sh|/sampler\.py)", cols[2])):
                raise ValueError("remaining/foreign sampler/controller; not terminated")
        target = self.remote("TARGET_STAT", "cat /proc/%d/stat" % prior["preflight"]["enlightenment_pid"])
        identity = ANALYSIS.proc_stat(target)
        if identity["pid"] != prior["preflight"]["enlightenment_pid"] or identity["starttime"] != prior["target_starttime"]:
            raise ValueError("enlightenment identity changed since completed G4")
        tcp = self.remote("TCP", "cat /proc/net/tcp /proc/net/tcp6")
        established = [line for line in tcp.splitlines() if len(line.split()) > 3 and
                       line.split()[1].upper().endswith(":65F5") and line.split()[3] == "01"]
        if len(established) > 1:
            raise ValueError("multiple established sdb clients")
        governors = self.remote("GOVERNORS", 'for n in 0 1 2 3; do cat /sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor || exit 1; done')
        if governors.splitlines() != ["schedutil"] * 4:
            raise ValueError("governors not four schedutil; read-only audit cannot change them")
        self.remote("SPACE", "df -k / /opt/usr")
        self.remote("UPTIME", "date -u && uptime && cat /proc/swaps")
        work = self.remote("WORKDIR", residue_command(["/opt/usr/glibc_memopt", WORK]))
        if work:
            self.remote("WORKDIR_METADATA", 'for p in /opt/usr/glibc_memopt ' + shlex.quote(WORK) +
                '; do if [ -e "$p" ] || [ -L "$p" ]; then stat -c "%n %F %s %Y %U:%G" "$p" && ls -la "$p" || exit 1; fi; done')
            raise ValueError("work residue needs ownership/metadata review; no speculative deletion")
        self.round_snapshot("audit_start")
        after = self.inventory("PACKAGE_INVENTORY_CURRENT")
        self.receipt["package_inventory"] = {"before_count": len(inventory), "current_count": len(after),
            "added": sorted(set(after) - set(inventory)), "removed": sorted(set(inventory) - set(after))}
        if inventory != after:
            raise ValueError("package inventory not restored")
        self.remote("PACKAGES_ABSENT", 'for p in ' + " ".join(GDB_NAMES) + '''; do
text=$(LC_ALL=C rpm -q "$p" 2>&1); code=$?
printf '%s\\n' "$text"
[ "$code" -eq 1 ] && [ "$text" = "package $p is not installed" ] || exit 1
done''')
        residues = []
        for label, command in batches:
            residues.extend(self.remote(label, command).splitlines())
        self.receipt["package_residue_observations"] = residues
        self.save()
        non_dirs = []
        for index, row in enumerate(residues):
            path, kind = row.split("\t", 1)
            command = ('p=' + shlex.quote(path) + '; stat -c "%n %F %s %Y %U:%G" "$p" || exit 1; '
                       'owner=$(LC_ALL=C rpm -qf --queryformat \'%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\\n\' "$p" 2>&1); code=$?; '
                       'printf "%s\\nOWNER_RC=%s\\n" "$owner" "$code"; '
                       '[ "$code" -eq 0 ] || { [ "$code" -eq 1 ] && [ "$owner" = "file $p is not owned by any package" ]; } || exit 1')
            metadata = self.remote("RESIDUE_META_%04d" % index, command)
            lines = metadata.splitlines()
            if lines[-1:] == ["OWNER_RC=0"]:
                owners = lines[1:-1]
                if not owners or any(owner not in after for owner in owners):
                    raise ValueError("residue owner not in verified package inventory")
            elif lines[-1:] != ["OWNER_RC=1"] or lines[1:-1] != ["file " + path + " is not owned by any package"]:
                raise ValueError("invalid residue ownership result")
            else:
                non_dirs.append({"path": path, "type": kind, "metadata": metadata})
        self.receipt["non_directory_residues"] = non_dirs
        self.round_snapshot("audit_end")
        health = self.raw / "round_health"
        for when in ("audit_start", "audit_end"):
            increment = health_delta((SOURCE / "raw/round_health/dmesg_before.txt").read_text(),
                (health / ("dmesg_" + when + ".txt")).read_text(),
                (SOURCE / "raw/round_health/zram_before.txt").read_text(),
                (health / ("zram_" + when + ".txt")).read_text())
            (health / ("dmesg_increment_" + when + ".txt")).write_text("\n".join(increment) + "\n")
            old = STABILITY.snapshot(SOURCE / "raw/round_health/stability_before.tsv")
            new = STABILITY.snapshot(health / ("stability_" + when + ".tsv"))
            self.receipt["stability_" + when] = {"prior_count": len(old), "current_count": len(new),
                "changed_paths": [p for p in new if p not in old or new[p] != old[p]]}
            self.attribute_alerts(old, new, prior, when)
        if non_dirs:
            raise ValueError("non-directory package residue needs exact ownership/disposition review")
        if self.remote("BOOT_ID_FINAL", "cat /proc/sys/kernel/random/boot_id") != boot:
            raise ValueError("boot changed during audit")
        self.receipt["health"] = {"oom_lmk_new": 0, "zram_three_delta": [0, 0, 0],
            "attributable_alerts_new": 0, "delayed_interval_dmesg_prefix": True, "boot_unchanged": True}
        self.receipt["verdict"] = "PASS_READONLY_CLEANUP"

    def execute(self):
        try:
            self.receipt["executor_commit"] = git("rev-parse", "HEAD")
            if git("status", "--porcelain"):
                raise ValueError("audit requires a clean committed snapshot")
            if git("ls-remote", "origin", "refs/heads/main").split()[0] != self.receipt["executor_commit"]:
                raise ValueError("audit must be pushed on main before connection")
            prior, batches, inventory = local_sources()
            self.receipt["source_execution_sha256"] = hashlib.sha256((SOURCE / "execution.json").read_bytes()).hexdigest()
            self.collect(prior, batches, inventory)
        except Exception as error:
            self.receipt["verdict"] = "STOP"
            self.receipt["reason"] = str(error).replace(self.addr, "<TEST_BOARD_IP>")
        finally:
            if self.elevation_attempted:
                if not self.restore_nonroot() or self.receipt["root_authorization"].get("recording_error"):
                    self.receipt["verdict"] = "STOP"
                    self.receipt["root_restore_error"] = "root-off/logging failed"
            elif self.commands and "id_before" in self.receipt:
                try:
                    self.receipt["id_final"] = self.remote("ID_FINAL", "id")
                    if not re.match(r"uid=5001(?:\(|\s)", self.receipt["id_final"]):
                        raise ValueError("final non-root identity mismatch")
                except Exception as error:
                    self.receipt["verdict"] = "STOP"
                    self.receipt["final_id_error"] = str(error).replace(self.addr, "<TEST_BOARD_IP>")
            self.receipt["end_utc"] = utc()
            self.save()
        print("FINAL_CLEANUP_AUDIT", json.dumps(self.receipt), flush=True)
        return 0 if self.receipt["verdict"] == "PASS_READONLY_CLEANUP" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--pm-authorization", choices=[PM_TOKEN])
    args = parser.parse_args()
    if args.output_dir.resolve() == ROOT or args.output_dir.resolve().is_relative_to(SOURCE):
        parser.error("audit output must be separate from immutable published inputs")
    return CleanupAudit(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
