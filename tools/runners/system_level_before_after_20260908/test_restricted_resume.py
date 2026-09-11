"""Restricted continuation: no SDB contact; exact-PID cleanup is mocked only."""
import base64
import contextlib
import hashlib
import io
import json
import pathlib
import shlex
import sys
import types
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    import test_single_cleanup as fixtures
    import audit_restricted_resume_20260911 as restricted
    import single_request as wire


def proc_stat(pid=12345, ticks=7000):
    return "%d (sh) " % pid + " ".join(["S"] + ["0"] * 18 + [str(ticks)])


class RestrictedContinuation(fixtures.SingleCleanup):
    def setUp(self):
        super().setUp()
        self.previous = self.root / "previous"
        self.previous.mkdir()
        self.predecessor = {"verdict": "STOP", "reason": "process table missing PID 1",
                            "id_final": "uid=5001(owner)"}
        (self.previous / "audit.json").write_text(json.dumps(self.predecessor))
        ops = {"UNAME_R": (["uname", "-r"], "6-fixture-rpi4"),
               "UNAME_M": (["uname", "-m"], "armv7l"),
               "OS_RELEASE": (["cat", "/etc/os-release"], "BUILD_ID=" + restricted.CONTRACT["identity"]["build_id"]),
               "GLIBC": (["rpm", "-q", "glibc"], restricted.CONTRACT["identity"]["glibc"]),
               "MEMINFO": (["cat", "/proc/meminfo"], "MemTotal: 8117408 kB"),
               "BOOT_START": (["cat", fixtures.single.BOOT], fixtures.BOOT),
               "DMESG_START": (["dmesg"], fixtures.DMESG.rstrip()),
               "ZRAM_START": (["cat", "/sys/block/zram0/mm_stat"], fixtures.ZRAM.rstrip())}
        self.cached = {name: (wire.request(argv), (0, value)) for name, (argv, value) in ops.items()}
        self.helper_map = {}

    def instance(self, token=None):
        self.count += 1
        args = types.SimpleNamespace(ip="192.0.2.1", pm_authorization=token,
                                    output_dir=self.root / ("restricted-%d" % self.count))
        with mock.patch.object(restricted, "previous_checks", return_value=(self.predecessor, self.cached.copy())), \
             mock.patch.object(restricted, "known_helpers", return_value=self.helper_map.copy()), \
             mock.patch.object(restricted, "PREVIOUS", self.previous):
            return restricted.RestrictedResume(args)

    def exercise(self, **kwargs):
        with mock.patch.object(restricted, "SOURCE", self.source):
            return super().exercise(**kwargs)

    def test_reuses_eight_successful_checks_and_finishes_2570_paths_once_before_one_root_round(self):
        obj, rc, events, state, output = self.exercise(count=2570, token=restricted.TOKEN)
        self.assertEqual(rc, 0, output)
        labels = [label for label, _ in events]
        self.assertEqual(set(obj.receipt["reused_nonroot_checks"]), set(restricted.REUSE))
        for name in restricted.REUSE:
            self.assertNotIn("NONROOT_" + name, labels)
        delayed = {"PS_START", "PS_END", "TARGET_STAT", "ALERTS_START", "ALERTS_END"}
        self.assertEqual(set(obj.pending), delayed)
        for name in delayed:
            self.assertNotIn("NONROOT_" + name, labels)
            self.assertEqual(labels.count("ROOT_" + name), 1)
        path_labels = [name for name in labels if name.startswith("NONROOT_PATH_")]
        self.assertEqual(path_labels, ["NONROOT_PATH_%04d" % n for n in range(2570)])
        self.assertLess(labels.index("NONROOT_PATH_2569"), labels.index("ROOT_ON"))
        self.assertEqual((state["root_on"], state["root_off"], state["uid"]), (1, 1, 5001))
        self.assertEqual(obj.receipt["processes_terminated"], 0)
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")

    def test_foreign_sessions_benchmarks_and_sdb_clients_are_report_only_never_signalled(self):
        extra = ("26799 1 pts/0 sh sh -l\n27105 1 ? gst_loop_decode /foreign/gst_loop_decode\n"
                 "27106 1 ? gdb /usr/bin/gdb /foreign/app\n")
        table = fixtures.PS_TABLE + extra
        tcp = "0: 00000000:65F5 00000000:0000 01\n1: 00000000:65F5 00000000:0000 01"
        obj, rc, events, state, output = self.exercise(token=restricted.TOKEN,
            overrides={("ROOT", "PS_START"): (0, table), ("ROOT", "PS_END"): (0, table),
                       ("NONROOT", "TCP4"): (0, tcp)})
        self.assertEqual(rc, 0, output)
        self.assertEqual(obj.receipt["other_sdb_connections"]["established_count"], 2)
        self.assertTrue(all(row["verdict"].startswith("REPORT_ONLY") for rows in
                            obj.receipt["process_observations"].values() for row in rows))
        self.assertFalse(any("_PID_" in label for label, _ in events))
        self.assertEqual(obj.receipt["processes_terminated"], 0)

    def test_cached_operation_substitution_and_unapproved_root_token_are_rejected(self):
        obj = self.instance(restricted.TOKEN)
        with mock.patch.object(obj, "run") as send:
            with self.assertRaisesRegex(ValueError, "substitute reused operation"):
                obj.op("UNAME_R", ["uname", "-a"])
            send.assert_not_called()
        for token in (None, fixtures.single.TOKEN):
            with self.subTest(token=token):
                obj, rc, events, state, output = self.exercise(token=token)
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 0)
                self.assertTrue((obj.out / "permission_denied.json").is_file())

    def test_registered_incomplete_categories_are_exact_and_no_extra_nonroot_probe_occurs(self):
        obj = self.instance(restricted.TOKEN)
        for label, argv in (("PS_START", restricted.PS), ("PS_END", restricted.PS),
                            ("TARGET_STAT", ["cat", "/proc/498/stat"]),
                            ("ALERTS_START", ["ls", "-A", "--", restricted.CRASH])):
            with self.subTest(label=label), mock.patch.object(obj, "run") as run:
                self.assertIsNone(obj.op(label, argv))
                run.assert_not_called()
                self.assertEqual(obj.pending[label]["argv"], argv)
        for label, argv in (("PS_START", ["ps"]), ("TARGET_STAT", ["cat", "/proc/499/stat"]),
                            ("ALERTS_END", ["ls", "-A", "--", "/tmp"])):
            with self.subTest(label=label), mock.patch.object(obj, "run") as run:
                with self.assertRaises(ValueError):
                    obj.op(label, argv)
                run.assert_not_called()

    def test_incomplete_root_view_target_loss_and_root_replay_fault_all_drop_root(self):
        for table in (fixtures.PS_TABLE.replace("1 0 ? init /sbin/init\n", ""),
                      fixtures.PS_TABLE.replace("498 1 ? enlightenment /usr/bin/enlightenment\n", ""),
                      fixtures.PS_TABLE + "1 0 ? init /sbin/init\n"):
            with self.subTest(table=table):
                obj, rc, events, state, output = self.exercise(token=restricted.TOKEN,
                    overrides={("ROOT", "PS_START"): (0, table)})
                self.assertEqual(rc, 1, output)
                self.assertEqual((state["root_on"], state["root_off"], state["uid"]), (1, 1, 5001))
                self.assertFalse(any("_PID_" in label for label, _ in events))
        obj, rc, _, state, output = self.exercise(token=restricted.TOKEN, fail_labels={"ROOT_PS_START"})
        self.assertEqual(rc, 1, output)
        self.assertEqual((state["root_off"], state["uid"]), (1, 5001))

    def test_root_on_failure_and_bounded_root_off_failure_cannot_succeed(self):
        for options in ({"root_on_fails": True}, {"off_failures": 2}):
            with self.subTest(options=options):
                obj, rc, _, state, output = self.exercise(token=restricted.TOKEN, **options)
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 1)
                self.assertEqual(state["root_off"], 2 if options.get("off_failures") else 1)
                self.assertEqual(obj.receipt["root_authorization"]["root_off"], "FAIL" if options.get("off_failures") else "PASS_NONROOT")
        obj, rc, _, state, output = self.exercise(token=restricted.TOKEN, off_failures=1)
        self.assertEqual(rc, 0, output)
        self.assertEqual((state["root_off"], state["uid"]), (2, 5001))

    def test_scope_cannot_signal_or_read_arbitrary_process_and_requires_root_context(self):
        obj = self.instance(restricted.TOKEN)
        obj.phase = "ROOT"
        obj.pending = {"PS_START": {"argv": restricted.PS, "reason": "PM incomplete view", "directory": None}}
        for argv in (["cat", "/proc/12345/stat"], ["kill", "-TERM", "--", "12345"],
                     ["kill", "-KILL", "--", "12345"]):
            with self.subTest(argv=argv), mock.patch.object(obj, "run") as run:
                with self.assertRaises(ValueError):
                    obj.op("UNAUTHORIZED", argv, False, scope="PS_START")
                run.assert_not_called()
        with self.assertRaisesRegex(ValueError, "authorized root context"):
            obj.inspect_processes("PS_START", fixtures.PS_TABLE)

    def own_process_case(self, *, initial=None, recheck=None, terminate_rc=0, still_present=False,
                         metadata_failure=None):
        obj = self.instance(restricted.TOKEN)
        obj.phase = "ROOT"
        obj.receipt["root_authorization"] = {"id_after_on": "uid=0(root)"}
        obj.pending = {"PS_START": {"argv": restricted.PS, "reason": "PM incomplete view", "directory": None}}
        obj.helpers = {12345: {"starttime": 7000, "exe": ("/bin/sh", "/usr/bin/sh"), "script": "run_cell_remote.sh"}}
        values = {"STAT": proc_stat(), "EXE": "/bin/sh", "CWD": restricted.WORK,
                  "CMDLINE": base64.b64encode(("/bin/sh\0" + restricted.WORK + "/run_cell_remote.sh\0G4_trim_r1\0").encode()).decode()}
        values.update(initial or {})
        table = fixtures.PS_TABLE + "12345 1 ? sh /bin/sh " + restricted.WORK + "/run_cell_remote.sh G4_trim_r1\n"
        events = []

        def run(label, argv, timeout=20):
            self.assertEqual(argv[:4], ["sdb", "-s", obj.serial, "shell"])
            body = argv[-1]
            self.assertLessEqual(len(body.encode("utf-8")), 200)
            operation = shlex.split(body[len("LC_ALL=C "):-len(wire.SUFFIX)])
            self.assertIn(operation[0], {"cat", "readlink", "base64", "kill", "stat"})
            events.append((label, operation))
            part = label.split("_PID_12345_", 1)[1]
            code = 0
            if part == metadata_failure:
                code, payload = 1, "fixture metadata: Permission denied"
            elif part in values:
                payload = values[part]
            elif part.startswith("RECHECK_"):
                name = part[8:]
                payload = (recheck or {}).get(name, values[name])
            elif part == "TERM":
                self.assertEqual(operation, ["kill", "-TERM", "--", "12345"])
                persisted = json.loads((obj.out / "audit.json").read_text())
                record = persisted["process_observations"]["PS_START"][0]
                self.assertTrue(record["identity_match"])
                self.assertEqual(set(record["metadata"]), {"STAT", "EXE", "CMDLINE", "CWD"})
                code, payload = terminate_rc, "fixture TERM"
            elif part == "ABSENT":
                code, payload = (0, "directory") if still_present else (1, "stat: /proc/12345: No such file or directory")
            else:
                self.fail("unexpected process operation " + part)
            return 97, payload + "\nRC=%d\n%s\n" % (code, "DONE" if code == 0 else "FAIL")

        error = None
        with mock.patch.object(obj, "run", side_effect=run), mock.patch.object(restricted.time, "sleep"):
            try:
                obj.inspect_processes("PS_START", table)
            except ValueError as caught:
                error = caught
        return obj, error, events

    def test_own_process_metadata_and_rechecks_precede_only_exact_term_and_absence_proof(self):
        obj, error, events = self.own_process_case()
        self.assertIsNone(error)
        self.assertEqual([label.split("_PID_12345_", 1)[1] for label, _ in events],
                         ["STAT", "EXE", "CMDLINE", "CWD", "RECHECK_STAT", "RECHECK_EXE", "RECHECK_CMDLINE", "TERM", "ABSENT"])
        self.assertEqual(obj.receipt["processes_terminated"], 1)
        self.assertEqual(obj.receipt["process_observations"]["PS_START"][0]["verdict"], "ARCHIVED_TERM_VERIFIED_ABSENT")

    def test_pid_reuse_executable_or_cmdline_identity_mismatch_is_report_only_no_term(self):
        cases = [{"STAT": proc_stat(ticks=7001)}, {"STAT": proc_stat(pid=54321)}, {"EXE": "/usr/bin/foreign"},
                 {"CMDLINE": base64.b64encode(b"/bin/sh\0/foreign/program.sh\0").decode()}]
        for initial in cases:
            with self.subTest(initial=initial):
                obj, error, events = self.own_process_case(initial=initial)
                self.assertIsNone(error)
                self.assertFalse(any(operation[0] == "kill" for _, operation in events))
                self.assertEqual(obj.receipt["processes_terminated"], 0)
                self.assertFalse(obj.receipt["process_observations"]["PS_START"][0]["identity_match"])

    def test_reused_pid_is_reported_before_reading_exe_cmdline_or_cwd(self):
        for changed in (proc_stat(ticks=7001), proc_stat(pid=54321)):
            with self.subTest(changed=changed):
                obj, error, events = self.own_process_case(initial={"STAT": changed}, metadata_failure="EXE")
                self.assertIsNone(error)
                self.assertEqual([label.split("_PID_12345_", 1)[1] for label, _ in events], ["STAT"])
                self.assertEqual(obj.receipt["processes_terminated"], 0)
                self.assertFalse(obj.receipt["process_observations"]["PS_START"][0]["identity_match"])

    def test_known_helper_mapping_matches_frozen_controller_sampler_and_gdb_scripts(self):
        filenames = ("controller_identity.txt", "sampler_identity.txt", "debugger_identity.txt")
        expected = []
        for i, cell in enumerate(self.prior["completed_cells"]):
            for j, filename in enumerate(filenames):
                pid, tick = 10000 + i * 10 + j, 20000 + i * 10 + j
                (self.source / "raw" / cell / filename).write_text("%d %d\n" % (pid, tick))
                expected.append((pid, tick, j))
        mapping = restricted.known_helpers(self.source)
        self.assertEqual(len(mapping), 9)
        scripts = ("run_cell_remote.sh", "sample_smaps_1s.sh", "g4_m7.py")
        source = (HERE / "run_cell_remote.sh").read_text()
        self.assertIn('sh "$work/sample_smaps_1s.sh"', source)
        self.assertIn('-x "$work/g4_m7.py"', source)
        for pid, tick, kind in expected:
            with self.subTest(pid=pid):
                self.assertEqual(mapping[pid]["starttime"], tick)
                self.assertEqual(mapping[pid]["script"], scripts[kind])
                if kind == 2:
                    self.assertEqual(mapping[pid]["exe"], ("/usr/bin/gdb",))
                else:
                    self.assertIn("/bin/sh", mapping[pid]["exe"])
                    self.assertIn("/usr/bin/sh", mapping[pid]["exe"])

    def test_owned_script_must_be_exact_same_argument_not_cross_argument_or_substring(self):
        commands = [["/bin/sh", "/foreign/run_cell_remote.sh", restricted.WORK + "/unrelated-data"],
                    ["/bin/sh", restricted.WORK + "/not_run_cell_remote.sh.backup"],
                    ["/bin/sh", restricted.WORK + "/unrelated.sh", "run_cell_remote.sh"]]
        for command in commands:
            with self.subTest(command=command):
                encoded = base64.b64encode(("\0".join(command) + "\0").encode()).decode()
                obj, error, events = self.own_process_case(initial={"CMDLINE": encoded})
                self.assertIsNone(error)
                self.assertFalse(any(operation[0] == "kill" for _, operation in events))
                self.assertFalse(obj.receipt["process_observations"]["PS_START"][0]["identity_match"])

    def test_recheck_pid_starttime_exe_or_cmdline_change_stops_before_signal(self):
        for changed in ({"STAT": proc_stat(ticks=7001)}, {"STAT": proc_stat(pid=54321)},
                        {"EXE": "/bin/different"}, {"CMDLINE": "Y2hhbmdlZA=="}):
            with self.subTest(changed=changed):
                obj, error, events = self.own_process_case(recheck=changed)
                self.assertRegex(str(error), "identity changed before TERM")
                self.assertFalse(any(operation[0] == "kill" for _, operation in events))

    def test_metadata_failure_term_failure_or_unproven_absence_never_reports_cleanup_success(self):
        for options in ({"metadata_failure": "STAT"}, {"metadata_failure": "CMDLINE"},
                        {"terminate_rc": 1}, {"still_present": True}):
            with self.subTest(options=options):
                obj, error, events = self.own_process_case(**options)
                self.assertIsNotNone(error)
                self.assertNotIn("PS_START", obj.inspected)
                record = obj.receipt["process_observations"]["PS_START"][0]
                self.assertNotEqual(record["verdict"], "ARCHIVED_TERM_VERIFIED_ABSENT")
                if "metadata_failure" in options:
                    self.assertFalse(any(operation[0] == "kill" for _, operation in events))

    def test_disposition_health_is_read_only_after_nonroot_restoration_and_failure_stops(self):
        for changed, failure in ((False, False), (True, False), (True, True)):
            with self.subTest(changed=changed, failure=failure):
                obj = self.instance(restricted.TOKEN)
                obj.phase = "ROOT"
                obj.receipt["verdict"] = "PASS_READONLY_CLEANUP"
                obj.receipt["root_authorization"] = {"root_off": "NOT-EVALUATED"}
                obj.receipt["processes_terminated"] = int(changed)
                operations = []

                def restored(this):
                    self.assertIs(this, obj)
                    this.receipt["root_authorization"]["root_off"] = "PASS_NONROOT"

                def health(label, argv, defer=True):
                    self.assertEqual(obj.phase, "NONROOT")
                    self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")
                    operations.append(argv)
                    self.assertFalse(defer)
                    if label == "POST_DISPOSITION_DMESG":
                        return fixtures.DMESG + ("[1.0] oom-kill\n" if failure else "")
                    self.assertEqual(label, "POST_DISPOSITION_ZRAM")
                    return fixtures.ZRAM

                with mock.patch.object(fixtures.single.SingleAudit, "drop_root", autospec=True, side_effect=restored), \
                     mock.patch.object(obj, "ok", side_effect=health), mock.patch.object(restricted, "SOURCE", self.source):
                    obj.drop_root()
                self.assertEqual(len(operations), 2 if changed else 0)
                if failure:
                    self.assertEqual(obj.receipt["verdict"], "STOP")
                    self.assertIn("post-disposition health", obj.receipt["reason"])
                elif changed:
                    self.assertEqual(obj.receipt["post_disposition_health"], "PASS")

    def test_predecessor_manifest_and_exact_stop_identity_are_required(self):
        commands = []
        for label, (body, (rc, value)) in self.cached.items():
            name = "NONROOT_" + label
            (self.previous / (name + ".txt")).write_text(value + "\nRC=0\nDONE\n")
            commands.append({"label": name, "argv": ["sdb", "shell", body]})
        (self.previous / "commands.json").write_text(json.dumps(commands))
        (self.previous / "NONROOT_PS_START.txt").write_text("PID PPID TT COMMAND COMMAND\n5001 1 pts/0 sh sh\nRC=0\nDONE\n")
        files = [p for p in self.previous.iterdir() if p.is_file()]
        manifest = {"files": [{"path": p.name, "public_sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
        (self.previous / "manifest.json").write_text(json.dumps(manifest))
        receipt, checks = restricted.previous_checks(self.previous)
        self.assertEqual(receipt, self.predecessor)
        self.assertEqual(checks, self.cached)
        (self.previous / "NONROOT_UNAME_R.txt").write_text("changed\nRC=0\nDONE\n")
        with self.assertRaisesRegex(ValueError, "evidence hash mismatch"):
            restricted.previous_checks(self.previous)


# Reuse fixture helpers, not unrelated inherited tests (old modules stay intact).
for _name in dir(fixtures.SingleCleanup):
    if _name.startswith("test_") and _name not in RestrictedContinuation.__dict__:
        setattr(RestrictedContinuation, _name, None)


if __name__ == "__main__":
    unittest.main()
