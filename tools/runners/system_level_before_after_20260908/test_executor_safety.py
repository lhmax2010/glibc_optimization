"""Host-only fault injection against the actual board executor source.

Only this process's TemporaryDirectory and fixture child shells are touched.
No SDB command is used; /proc, /sys and board work paths are rewritten before
an executable fragment is passed to the shell.  kill/wait are stubs except in
the self-signal test, which signals only that fixture shell's own $$.
"""
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
BOARD_WORK = "/opt/usr/glibc_memopt/system_level_before_after_20260908"
CONTROLLER = HERE / "run_cell_remote.sh"
CAPTURE = HERE / "capture_point.sh"


def function(name):
    """Extract a named production function, failing on a moved/ambiguous anchor."""
    text = CONTROLLER.read_text()
    pattern = r"^" + re.escape(name) + r"\(\)\n\{\n.*?^\}\n"
    found = re.findall(pattern, text, re.M | re.S)
    if len(found) != 1:
        raise AssertionError("production function anchor changed: " + name)
    return found[0]


class ExecutorSafety(unittest.TestCase):
    def setUp(self):
        self.shell = shutil.which("sh")
        if not self.shell:
            self.skipTest("executor shell fixtures require an executable sh")
        self.temp = tempfile.TemporaryDirectory(prefix="system-executor-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.out = self.work / "G4_trim_r1"
        self.out.mkdir()
        self.proc = self.root / "proc"
        self.sys = self.root / "sys"
        self.crash = self.root / "livedump"
        self.crash.mkdir()
        self.clock = self.root / "clock"
        self.clock.write_text("0\n")

    def dependencies(self, *names):
        missing = [name for name in names if not shutil.which(name)]
        if missing:
            self.skipTest("optional shell fixture tools unavailable: " + ", ".join(missing))

    def rewrite(self, source):
        source = source.replace(BOARD_WORK, str(self.work))
        source = source.replace("/opt/usr/share/crash/livedump", str(self.crash))
        source = re.sub(r"(?<![A-Za-z0-9_$])/proc/", str(self.proc) + "/", source)
        source = re.sub(r"(?<![A-Za-z0-9_$])/sys/", str(self.sys) + "/", source)
        # Refuse to run a fragment if a future source edit introduced an
        # unredirected protected host/board path.
        protected = source.replace(str(self.proc) + "/", "<PROC>/").replace(str(self.sys) + "/", "<SYS>/")
        for prefix in ("/proc/", "/sys/", "/opt/usr/"):
            if re.search(r"(?<![A-Za-z0-9_$])" + re.escape(prefix), protected):
                raise AssertionError("unredirected execution path: " + prefix)
        return source

    def run_shell(self, source, *args, timeout=5):
        prelude = "\n".join("%s=%s" % (name, shlex.quote(str(path))) for name, path in (
            ("work", self.work), ("out", self.out), ("fake_proc", self.proc),
            ("clock", self.clock), ("calls", self.root / "calls")))
        return subprocess.run([self.shell, "-c", prelude + "\n" + self.rewrite(source),
                               "executor-fixture", *map(str, args)],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, cwd=self.root,
                              env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C"})

    def call_lines(self):
        path = self.root / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def test_snapshot_each_pipeline_component_failure_propagates(self):
        # These are command doubles, not tests of the host's find/stat tools.
        # The function under test is extracted byte-for-byte from the runner.
        doubles = r'''
find() { [ "$failure" != find ] || return 31; printf '%s\n' "$work/archive.zip"; }
sort() { [ "$failure" != sort ] || return 32; printf '%s\n' "$work/archive.zip"; }
stat() {
    case "$failure:$2" in stat_size:%s|stat_time:%Y) return 33;; esac
    printf '%s\n' 123
}
sha256sum() { [ "$failure" != sha256sum ] || return 34; printf '%064d %s\n' 0 "$1"; }
rm() { [ "$failure" != rm ] || return 35; return 0; }
'''
        for failure in ("none", "find", "sort", "stat_size", "stat_time", "sha256sum", "rm"):
            with self.subTest(failure=failure):
                p = self.run_shell(function("snapshot") + doubles +
                                   "\nfailure=$1\nsnapshot \"$out/snapshot.tsv\"\n", failure)
                self.assertEqual(p.returncode == 0, failure == "none", p.stdout)
                if failure == "none":
                    text = (self.out / "snapshot.tsv").read_text()
                    self.assertEqual(len(text.splitlines()), 2)
                    self.assertIn("remote_path\tsize\tmtime_epoch\tsha256\n", text)

    def capture_validation(self, relative):
        self.dependencies("mkdir")
        source = CAPTURE.read_text().split('log="$out/capture_commands.txt"', 1)
        self.assertEqual(len(source), 2, "capture validation boundary changed")
        return self.run_shell(source[0] + "printf 'VALIDATED\n'\n", "4", str(self.work) + "/" + relative)

    def test_capture_all_contract_cells_accept_only_their_cycle_range(self):
        contract = json.loads((HERE / "contract.json").read_text())
        for cell in contract["cells"]:
            for n in {1, cell["cycles"]}:
                for phase in ("pre", "post"):
                    with self.subTest(cell=cell["id"], cycle=n, phase=phase):
                        p = self.capture_validation("%s/points/%02d_%s" % (cell["id"], n, phase))
                        self.assertEqual(p.returncode, 0, p.stdout)
                        self.assertIn("VALIDATED", p.stdout)

    def test_capture_rejects_cell_phase_traversal_and_extra_components(self):
        invalid = ("G4_none_r1/points/01_pre", "G1_trim_r4/points/01_pre",
                   "G1_trim_r1/points/00_pre", "G1_trim_r1/points/03_pre",
                   "G4_trim_r1/points/02_pre", "G3_trim_r1/points/52_pre",
                   "G3_trim_r1/points/01_wrong", "G3_trim_r1/points/1_pre",
                   "G1_trim_r1/../escaped/points/01_pre",
                   "G1_trim_r1/points/../01_pre", "G1_trim_r1/points//01_pre",
                   "G1_trim_r1/points/01_pre/extra", "../work/G1_trim_r1/points/01_pre")
        for relative in invalid:
            with self.subTest(path=relative):
                p = self.capture_validation(relative)
                self.assertEqual(p.returncode, 2, p.stdout)
                self.assertNotIn("VALIDATED", p.stdout)
        self.assertFalse((self.work / "escaped").exists())

    def test_capture_rejects_symlink_at_every_output_ancestor(self):
        for level in ("cell", "points", "point"):
            with self.subTest(level=level):
                cell = self.work / {"cell": "G1_trim_r1", "points": "G1_trim_r2", "point": "G1_trim_r3"}[level]
                destination = self.root / ("outside_" + level)
                destination.mkdir()
                if level == "cell":
                    cell.symlink_to(destination, target_is_directory=True)
                elif level == "points":
                    cell.mkdir()
                    (cell / "points").symlink_to(destination, target_is_directory=True)
                else:
                    (cell / "points").mkdir(parents=True)
                    (cell / "points/01_pre").symlink_to(destination, target_is_directory=True)
                p = self.capture_validation(cell.name + "/points/01_pre")
                self.assertEqual(p.returncode, 2, p.stdout)
                self.assertIn("FAIL_POINT_SYMLINK", p.stdout)
                self.assertEqual(list(destination.iterdir()), [])

    def test_full_capture_records_order_and_fails_on_each_missing_source(self):
        self.dependencies("mkdir", "cat", "date")
        pid_dir = self.proc / "4"
        pid_dir.mkdir(parents=True)
        zram = self.sys / "block/zram0/mm_stat"
        zram.parent.mkdir(parents=True)
        files = {"stat": (pid_dir / "stat", "4 (fixture) S 0 0 0\n"),
                 "status": (pid_dir / "status", "VmRSS: 8192 kB\n"),
                 "meminfo": (self.proc / "meminfo", "MemAvailable: 100 kB\n"),
                 "zram": (zram, "0 0 0 0 0 0 0\n")}
        expected_rc = {"none": 0, "stat": 4, "status": 5, "profile": 6,
                       "meminfo": 7, "zram": 8, "memps": 9}
        for failure, expected in expected_rc.items():
            with self.subTest(failure=failure):
                self.work = self.root / ("capture_" + failure)
                self.work.mkdir()
                for path, content in files.values():
                    path.write_text(content)
                if failure in files:
                    files[failure][0].unlink()
                probe = self.work / "reclaim_probe.armv7l"
                probe.write_text("#!/bin/sh\n" + ("exit 6\n" if failure == "profile" else
                                               "printf '%s\\n' '{\"pid\":4}'\n"))
                probe.chmod(0o755)
                memps = "memps() { return 9; }\n" if failure == "memps" else "memps() { printf 'P(DATA) OBJECT NAME\\n'; }\n"
                point = self.work / "G1_trim_r1/points/01_pre"
                p = self.run_shell(memps + CAPTURE.read_text(), "4", point)
                self.assertEqual(p.returncode, expected, p.stdout)
                log = (point / "capture_commands.txt").read_text()
                if expected == 0:
                    self.assertIn("RC=0\nDONE_CAPTURE_POINT", p.stdout)
                    self.assertEqual(re.findall(r"^DONE_(.+)$", log, re.M), [
                        "stat.txt", "status.txt", "profile.json", "meminfo.txt", "zram.txt", "memps.txt", "stat_check.txt"])
                    meta = json.loads((point / "meta.json").read_text())
                    self.assertGreaterEqual(meta["end_ns"], meta["start_ns"])
                else:
                    self.assertNotIn("DONE_CAPTURE_POINT", p.stdout)
                    self.assertIn("FAIL_", log)
                    self.assertFalse((point / "meta.json").exists())

    def test_stop_owned_pid_reuse_or_unknown_identity_never_signals(self):
        doubles = r'''
kill() { printf 'kill %s\n' "$*" >>"$calls"; return 0; }
identity_of() { printf '%s\n' actual_start; }
wait() { printf 'wait %s\n' "$*" >>"$calls"; return 0; }
'''
        for recorded in ("old_start", ""):
            with self.subTest(recorded=recorded):
                (self.root / "calls").write_text("")
                p = self.run_shell(function("stop_owned") + doubles + '\nstop_owned 999 "$1"\n', recorded)
                self.assertEqual(p.returncode, 1, p.stdout)
                self.assertEqual(self.call_lines(), ["kill -0 999"])

    def test_stop_owned_verified_process_is_stopped_and_reaped(self):
        doubles = r'''
alive=1
kill() {
    printf 'kill %s\n' "$*" >>"$calls"
    if [ "$1" = -0 ]; then [ "$alive" -eq 1 ]; else alive=0; fi
}
identity_of() { printf '%s\n' expected; }
date() { printf '%s\n' 100; }
wait() { printf 'wait %s\n' "$*" >>"$calls"; return 0; }
'''
        p = self.run_shell(function("stop_owned") + doubles + "\nstop_owned 999 expected\n")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("kill -TERM 999", self.call_lines())
        self.assertNotIn("kill -KILL 999", self.call_lines())
        self.assertIn("wait 999", self.call_lines())

    def test_stop_owned_unresponsive_process_escalates_boundedly_and_fails(self):
        doubles = r'''
kill() { printf 'kill %s\n' "$*" >>"$calls"; return 0; }
identity_of() { printf '%s\n' expected; }
mark() { printf '%s\n' "$*"; }
wait() { printf 'UNSAFE_WAIT\n'; return 0; }
'''
        p = self.run_shell(function("stop_owned") + self.fast_clock() + doubles + "\nstop_owned 999 expected\n")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("FAIL_OWN_PROCESS_STILL_PRESENT", p.stdout)
        self.assertNotIn("UNSAFE_WAIT", p.stdout)
        self.assertIn("kill -TERM 999", self.call_lines())
        self.assertIn("kill -KILL 999", self.call_lines())

    def test_stop_sampler_unlinks_only_owned_proxy_and_requires_success(self):
        self.dependencies("readlink", "rm")
        target = self.proc / "505"
        target.mkdir(parents=True)
        sentinel = target / "smaps"
        sentinel.write_text("preserved\n")
        proxy = self.out / "proc/505"
        proxy.parent.mkdir()
        for child_rc in (0, 6):
            with self.subTest(child_rc=child_rc):
                proxy.symlink_to(target, target_is_directory=True)
                p = self.run_shell(function("stop_sampler") + r'''
bench_pid=505
sampler_pid=999
sampler_start=expected
date() { printf '%s\n' 100; }
kill() { return 1; }
wait() { return "$1_rc"; }
stop_sampler
'''.replace('"$1_rc"', str(child_rc)))
                self.assertEqual(p.returncode == 0, child_rc == 0, p.stdout)
                self.assertFalse(proxy.is_symlink())
                self.assertEqual(sentinel.read_text(), "preserved\n")

    @staticmethod
    def fast_clock():
        return r'''
date() { read tick <"$clock"; printf '%s\n' "$((tick + 1000))" >"$clock"; printf '%s\n' "$tick"; }
sleep() { return 0; }
'''

    def test_wait_child_timeout_or_pid_drift_never_waits_unbounded(self):
        for identity in ("expected", "reused"):
            with self.subTest(identity=identity):
                script = (function("wait_child") + self.fast_clock() + r'''
kill() { return 0; }
identity_of() { printf '%s\n' "$1_identity"; }
wait() { printf 'UNSAFE_WAIT\n'; return 0; }
''').replace('"$1_identity"', shlex.quote(identity))
                p = self.run_shell(script + "\nwait_child 999 expected 30\n")
                self.assertEqual(p.returncode, 1, p.stdout)
                self.assertNotIn("UNSAFE_WAIT", p.stdout)

    def test_wait_child_preserves_finished_child_exit_code(self):
        p = self.run_shell(function("wait_child") + """
date() { printf '%s\\n' 100; }
kill() { return 1; }
wait() { return 23; }
wait_child 999 expected 30
""")
        self.assertEqual(p.returncode, 23, p.stdout)

    def governors(self):
        paths = []
        for cpu in range(4):
            path = self.sys / ("devices/system/cpu/cpu%d/cpufreq/scaling_governor" % cpu)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("performance\n")
            paths.append(path)
        return paths

    def finish_fixture(self):
        self.dependencies("cat", "grep")
        return function("finish") + r'''
cell=G4_trim_r1
changed=1
bench_pid=505
bench_start=daemon_start
bench_rc=0
debugger_pid=999
debugger_start=debugger_start
sampler_pid=
mark() { printf '%s\n' "$*"; }
stop_owned() {
    printf 'stop %s\n' "$*" >>"$calls"
    for n in 0 1 2 3; do
        [ "$(cat "/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor")" = schedutil ] || return 77
    done
    return 0
}
stop_sampler() { printf 'stop_sampler\n' >>"$calls"; return 0; }
record() { record_rc=0; return 0; }
snapshot() { return 0; }
date() { printf '%s\n' 123456789; }
'''

    def test_finish_preserves_failure_restores_first_and_never_stops_daemon(self):
        paths = self.governors()
        script = self.finish_fixture() + r'''
kill() { printf 'kill %s\n' "$*" >>"$calls"; return 0; }
(exit 23)
finish
'''
        p = self.run_shell(script)
        self.assertEqual(p.returncode, 23, p.stdout)
        self.assertIn("RC=23", p.stdout)
        self.assertIn("FAIL_CELL_G4_trim_r1", p.stdout)
        self.assertNotIn("DONE_CELL", p.stdout)
        self.assertEqual(self.call_lines(), ["stop 999 debugger_start", "stop_sampler"])
        self.assertTrue(all(path.read_text() == "schedutil\n" for path in paths))
        self.assertIn("controller_rc=23", (self.out / "exit_status.txt").read_text())

    def test_finish_restore_failure_is_not_success(self):
        paths = self.governors()
        paths[1].unlink()
        paths[1].mkdir()  # A private unwritable-as-file fixture, even under root.
        script = self.finish_fixture() + "\ndebugger_pid=\ntrue\nfinish\n"
        p = self.run_shell(script)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("FAIL_CELL_G4_trim_r1", p.stdout)
        self.assertNotIn("DONE_CELL", p.stdout)

    def test_finish_signals_restore_governors_and_preserve_signal_failure(self):
        paths = self.governors()
        source = CONTROLLER.read_text()
        trap_lines = re.findall(r"^trap (?:finish EXIT|'exit \d+' (?:HUP|INT|TERM))$", source, re.M)
        self.assertEqual(len(trap_lines), 4, "production trap anchors changed")
        for signal, expected in (("HUP", 129), ("INT", 130), ("TERM", 143)):
            with self.subTest(signal=signal):
                for path in paths:
                    path.write_text("performance\n")
                script = (self.finish_fixture() + "\ndebugger_pid=\nbench_pid=\n" +
                          "\n".join(trap_lines) + '\nkill -"$1" "$$"\nprintf UNSAFE_CONTINUED\n')
                p = self.run_shell(script, signal)
                self.assertEqual(p.returncode, expected, p.stdout)
                self.assertIn("FAIL_CELL_G4_trim_r1", p.stdout)
                self.assertNotIn("UNSAFE_CONTINUED", p.stdout)
                self.assertTrue(all(path.read_text() == "schedutil\n" for path in paths))

    def test_g4_identity_refusal_prevents_any_gdb_call(self):
        self.dependencies("cat")
        target = self.proc / "505"
        target.mkdir(parents=True)
        doubles = r'''
bench_pid=505
bench_start=expected
identity_of() { printf '%s\n' "$test_identity"; }
gdb() { printf 'UNSAFE_GDB\n' >>"$calls"; }
'''
        for comm, identity in (("other-process", "expected"), ("enlightenment", "reused"),
                               ("enlightenment", "")):
            with self.subTest(comm=comm, identity=identity):
                (target / "comm").write_text(comm + "\n")
                p = self.run_shell(function("assert_target") + function("run_gdb") + doubles +
                                   '\ntest_identity=$1\nrun_gdb gdb.txt -ex detach\n', identity)
                self.assertEqual(p.returncode, 1, p.stdout)
                self.assertEqual(self.call_lines(), [])

    def test_g4_null_file_guard_precedes_malloc_info_and_fclose(self):
        # Generate the actual GDB command file with the actual production shell
        # fragment, then inspect its control flow.  This does not emulate ptrace.
        source = CONTROLLER.read_text()
        start = source.index('        printf \'%s\\n\' "set \\$fp=')
        end = source.index('\n        run_gdb gdb_m7.txt', start)
        p = self.run_shell(source[start:end])
        self.assertEqual(p.returncode, 0, p.stdout)
        commands = (self.out / "m7.gdb").read_text().splitlines()
        self.assertTrue(commands[0].startswith("set $fp=(void*)fopen("))
        self.assertEqual(commands[1:7], ["if $fp == 0", "echo FAIL_NULL_FILE\\n", "detach", "quit 1", "end",
                                       "set $mrc=(int)malloc_info(0,$fp)"])
        self.assertEqual(commands[7], "set $crc=(int)fclose($fp)")
        self.assertEqual(commands[8:], ["if $mrc != 0 || $crc != 0", "echo FAIL_M7_RETURN\\n", "detach",
                                        "quit 1", "end", "detach", "quit 0"])

    def test_run_gdb_timeout_retains_owned_debugger_for_finish(self):
        script = function("run_gdb") + r'''
bench_pid=505
debugger_pid=
assert_target() { return 0; }
gdb() { return 0; }
identity_of() { printf '%s\n' debugger_identity; }
wait_child() { wait "$1"; return 1; }
mark() { printf '%s\n' "$*"; }
run_gdb gdb.txt -ex detach
status=$?
printf 'status=%s debugger_pid=%s debugger_start=%s\n' "$status" "$debugger_pid" "$debugger_start"
exit "$status"
'''
        p = self.run_shell(script)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("FAIL_GDB", p.stdout)
        self.assertRegex(p.stdout, r"status=1 debugger_pid=\d+ debugger_start=debugger_identity")

    def test_cover_post_requires_real_covering_sample_and_rejects_dead_sampler(self):
        self.dependencies("cat", "sed", "awk")
        point = self.out / "points/51_post"
        point.mkdir(parents=True)
        (point / "meta.json").write_text('{"start_ns":10,"end_ns":20}\n')
        prefix = function("cover_post") + self.fast_clock() + "\ncycle=51\nsampler_pid=999\n"
        for epoch, alive, expected in ((21, False, 0), (19, False, 1), (19, True, 1)):
            with self.subTest(epoch=epoch, alive=alive):
                (self.out / "external_1s.tsv").write_text("sample\ttimestamp\tepoch_ns\n0\tfixture\t%d\n" % epoch)
                script = prefix + "\nkill() { return %d; }\ncover_post\n" % (0 if alive else 1)
                p = self.run_shell(script)
                self.assertEqual(p.returncode, expected, p.stdout)


if __name__ == "__main__":
    unittest.main()
