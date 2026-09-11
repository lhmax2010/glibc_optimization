"""Single-operation cleanup transport and privilege gates; host fixtures only."""
import base64
import contextlib
import hashlib
import io
import json
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    import single_request as wire
    import audit_single_cleanup_20260911 as single
    import analyze_single_cleanup_stop as stopped

HEAD = "a" * 40
BOOT = "12345678-1234-1234-1234-123456789abc"
DMESG = "[0.0] host fixture boot\n"
ZRAM = "0 0 0 0 0 0\n"
INVENTORY = ["glibc 2.40-1.6.armv7l", "systemd 255-1.1.armv7l"]
TARGET_STAT = "498 (enlightenment) " + " ".join(["S"] + ["0"] * 18 + ["700"])
PS_TABLE = ("PID PPID TT COMMAND COMMAND\n1 0 ? init /sbin/init\n"
            "498 1 ? enlightenment /usr/bin/enlightenment\n"
            "9000 1 pts/2 sh sh -c " + wire.request(single.PS) + "\n"
            "9001 9000 pts/2 ps " + shlex.join(single.PS) + "\n")


class SingleCleanup(unittest.TestCase):
    def test_observed_nonroot_ps_rc_zero_is_incomplete_not_an_occupancy_pass(self):
        evidence = single.ROOT / 'data/raw/system_level_before_after_20260908/cleanup_single_20260911'
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no board access in replay')):
            result = json.loads(stopped.analyze(evidence))
        self.assertEqual(result, json.loads((evidence/'host_replay.json').read_text()))
        self.assertEqual(result['ps_remote_rc'], 0)
        self.assertFalse(result['pid_1_visible'])
        self.assertFalse(result['prior_target_visible'])
        self.assertEqual(result['verdict'], 'STOP_NOT_CLEANUP_PASS')
        self.assertEqual(result['root_rounds'], 0)
        self.assertEqual(result['accepted_cells_rerun'], 0)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="single-cleanup-host-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.source = self.root / "immutable-source"
        health = self.source / "raw/round_health"
        health.mkdir(parents=True)
        (health / "dmesg_before.txt").write_text(DMESG)
        (health / "zram_before.txt").write_text(ZRAM)
        self.prior = {"preflight": {"boot_id": BOOT, "enlightenment_pid": 498}, "target_starttime": 700,
                      "completed_cells": ["G4_trim_r1", "G4_trim_r2", "G4_trim_r3"],
                      "root_authorization": {"root_off": "PASS_NONROOT"}}
        (self.source / "execution.json").write_text(json.dumps(self.prior))
        for i, cell in enumerate(self.prior["completed_cells"]):
            directory = self.source / "raw" / cell
            directory.mkdir()
            (directory / "start_ns.txt").write_text(str((100 + i * 100) * 10**9 + 500_000_000))
            (directory / "end_ns.txt").write_text(str((105 + i * 100) * 10**9 + 500_000_000))
        self.alert_bytes = self.archive_bytes(pid=999)
        self.count = 0

    @staticmethod
    def archive_bytes(pid=498, executable="/usr/bin/enlightenment"):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("dump_reason", "cpu.relative host fixture")
            archive.writestr("info.json", json.dumps({"exe_file_path": executable, "threads": {"pid": pid}}))
        return stream.getvalue()

    def instance(self, token=None):
        self.count += 1
        return single.SingleAudit(types.SimpleNamespace(ip="192.0.2.1", pm_authorization=token,
            output_dir=self.root / ("output-%d" % self.count)))

    def test_complete_request_ascii_and_utf8_200_201_boundaries(self):
        self.assertEqual(wire.check_body("x" * 200), 200)
        with self.assertRaisesRegex(ValueError, "201 > 200.*NOT SENT"):
            wire.check_body("x" * 201)
        for token in ("a", "中", "é", "🙂"):
            with self.subTest(token=token):
                path = "/" + token
                initial = wire.request(["cat", path])
                path += "x" * (200 - len(initial.encode("utf-8")))
                exact = wire.request(["cat", path])
                self.assertEqual(len(exact.encode("utf-8")), 200)
                self.assertTrue(exact.endswith(wire.SUFFIX))
                self.assertGreater(len(exact.encode("utf-8")), len(shlex.join(["cat", path]).encode("utf-8")))
                with self.assertRaisesRegex(ValueError, "201 > 200.*NOT SENT"):
                    wire.request(["cat", path + "x"])
        with self.assertRaisesRegex(ValueError, "NUL"):
            wire.check_body("x\0y")

    def test_dispatch_rejects_oversize_before_subprocess_and_transport_mutations(self):
        obj = self.instance()
        vectors = [["sdb", "-s", obj.serial, "shell", "x" * 201],
                   ["sdb", "shell", "cat", "/fixture"], ["sdb", "shell"],
                   ["sdb", "push", "/fixture", "/board"], ["sdb", "pull", "/board", "/fixture"],
                   ["sdb", "install", "/fixture.rpm"], ["not-sdb", "version"]]
        for argv in vectors:
            with self.subTest(argv=argv[:3]), mock.patch.object(subprocess, "run") as transport:
                with self.assertRaises(ValueError):
                    obj.run("BAD", argv)
                transport.assert_not_called()
        self.assertEqual(obj.commands, [])
        exact = "x" * 200
        with mock.patch.object(subprocess, "run", return_value=types.SimpleNamespace(returncode=97, stdout="fixture")) as transport, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(obj.run("EXACT", ["sdb", "shell", exact]), (97, "fixture"))
            transport.assert_called_once()

    def test_one_operation_quotes_metacharacters_and_cannot_launch_second_command(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional literal-argument integration needs executable sh")
        for arg in ("space name", "single'quote", 'double"quote', "$(printf INJECTED)",
                    "`printf INJECTED`", "semi; printf INJECTED", "x|printf INJECTED", "中文"):
            with self.subTest(arg=arg):
                prelude = "cat() { printf '%s\\n' \"$1\"; }\n"
                result = subprocess.run([shell, "-c", prelude + wire.request(["cat", arg])], text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(wire.parse(result.stdout), (0, arg))
        for argv in ([], ["sh", "-c", "id"], ["bash"], ["python3"], ["eval", "id"],
                     ["cat", "x\ny"], ["cat", "x\ry"], ["cat", "x\0y"], ["cat", None]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                wire.request(argv)

    def test_remote_proof_is_mandatory_and_independent_of_host_rc(self):
        obj = self.instance()
        for host_rc, stdout, expected in ((97, "payload\n\nRC=0\nDONE\n", (0, "payload")),
                                          (0, "denied\nRC=1\nFAIL\n", (1, "denied"))):
            with self.subTest(host_rc=host_rc), mock.patch.object(subprocess, "run",
                return_value=types.SimpleNamespace(returncode=host_rc, stdout=stdout)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(obj.op("PROOF", ["id"], False), expected)
        bad = ["", "host success", "RC=0\n", "RC=0\nFAIL\n", "RC=1\nDONE\n", "RC=256\nFAIL\n",
               "RC=00\nDONE\n", "RC=0\nRC=0\nDONE\n", "RC=0\nDONE\nHOST_TIMEOUT\n"]
        for stdout in bad:
            with self.subTest(stdout=stdout), mock.patch.object(subprocess, "run",
                return_value=types.SimpleNamespace(returncode=0, stdout=stdout)), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, "proof"):
                    obj.op("MISSING", ["id"], False)

    def test_permission_and_absence_are_exact_not_arbitrary_failure(self):
        for text in ("cat: denied: Permission denied", "ls: denied: Operation not permitted",
                     "a: Permission denied\nb: Operation not permitted"):
            self.assertTrue(wire.permission(1, text))
            self.assertFalse(wire.permission(0, text))
        for text in ("", "permission denied", "failure Permission denied", "rpm: Input/output error",
                     "one readable line\ncat: denied: Permission denied"):
            self.assertFalse(wire.permission(1, text))
        self.assertTrue(wire.absent(1, "stat: fixture: No such file or directory"))
        self.assertTrue(wire.absent_listing(2, "ls: fixture: No such file or directory"))
        self.assertFalse(wire.absent_listing(1, "ls: fixture: No such file or directory"))
        self.assertFalse(wire.absent(2, "stat: fixture: No such file or directory"))
        for rc, text in ((0, "stat: fixture: No such file or directory"),
                         (2, "stat: fixture: No such file or directory"),
                         (1, "stat: fixture: Permission denied"), (1, "No such file or directory"),
                         (1, "first\nstat: fixture: No such file or directory")):
            self.assertFalse(wire.absent(rc, text))

    def test_path_bounds_reject_traversal_quotes_controls_and_root(self):
        for path in ("/", "relative", "/tmp/../x", "/tmp/x y", "/tmp/x'y", "/tmp/x;id", "/tmp/$(id)",
                     "/tmp/x\ny", "/tmp/x\0y"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                single.stat_op(path)
        self.assertEqual(single.stat_op("/fixture/normal-+_@.name")[-1], "/fixture/normal-+_@.name")

    def exercise(self, *, count=3, denied=(), overrides=None, token=None, fail_labels=(),
                 off_failures=0, root_on_fails=False, local_error=None, dirty=False, pushed=HEAD):
        obj = self.instance(token)
        paths = ["/fixture/package/%04d" % i for i in range(count)]
        events, state = [], {"uid": 5001, "root_on": 0, "root_off": 0}
        overrides = overrides or {}
        denied = set(denied)

        def respond(label, phase):
            if (phase, label) in overrides:
                return overrides[phase, label]
            if phase == "NONROOT" and label in denied:
                return 1, "operation: host fixture: Permission denied"
            if label.startswith("ID_"):
                return 0, "uid=%d(fixture) gid=100(users)" % state["uid"]
            if label == "UNAME_R":
                return 0, "6-fixture-rpi4"
            if label == "UNAME_M":
                return 0, "armv7l"
            if label == "OS_RELEASE":
                return 0, "BUILD_ID=" + single.CONTRACT["identity"]["build_id"]
            if label == "GLIBC":
                return 0, single.CONTRACT["identity"]["glibc"]
            if label == "MEMINFO":
                return 0, "MemTotal: 8117408 kB"
            if label.startswith("BOOT_"):
                return 0, BOOT
            if label.startswith("PS_"):
                return 0, PS_TABLE
            if label.startswith("DMESG_"):
                return 0, DMESG.rstrip()
            if label.startswith("ZRAM_"):
                return 0, ZRAM.rstrip()
            if label.startswith("ALERTS_") and label.endswith("_STAT"):
                return 0, "regular file|%d|101|0:0" % len(self.alert_bytes)
            if label.startswith("ALERTS_") and label.endswith("_SHA"):
                return 0, hashlib.sha256(self.alert_bytes).hexdigest() + "  " + single.CRASH + "/fixture.zip"
            if label.startswith("ALERTS_") and label.endswith("_B64"):
                return 0, base64.encodebytes(self.alert_bytes).decode()
            if label.startswith("ALERTS_"):
                return 0, ""
            if label == "TARGET_STAT":
                return 0, TARGET_STAT
            if label.startswith("GOV_"):
                return 0, "schedutil"
            if label in ("DF_ROOT", "DF_OPTUSR", "DATE", "UPTIME", "SWAPS"):
                return 0, "host fixture read-only sample"
            if label.startswith("TCP"):
                return 0, "sl local_address rem_address st"
            if label.startswith("TOP_") and "_SUSPECT_" in label:
                return 0, "regular file|10|1000|0:0"
            if label.startswith("TOP_"):
                return 0, ""
            if label == "PACKAGES":
                return 0, "\n".join(INVENTORY)
            if label.startswith("ABSENT_"):
                return 1, "package %s is not installed" % label[7:]
            if label.endswith("_OWNER"):
                return 0, "glibc-2.40-1.6.armv7l"
            if label.startswith("PATH_") and label in denied and phase == "ROOT":
                return 0, "regular file|1|1000|0:0"
            if label in ("WORK_PARENT", "WORK") or label.startswith("PATH_"):
                return 1, "stat: fixture path: No such file or directory"
            self.fail("unhandled single-operation fixture: " + phase + " " + label)

        def transport(_obj, label, argv, timeout=20):
            self.assertIs(_obj, obj)
            events.append((label, list(argv)))
            # Preserve dispatch accounting without 2570 O(n^2) log rewrites;
            # the separate real Gate.run tests check subprocess/proof behavior.
            obj.commands.append({"label": label, "argv": list(argv)})
            if argv[-2:] == ["root", "on"]:
                state["root_on"] += 1
                saved = obj.out / "permission_denied.json"
                self.assertTrue(saved.is_file(), "root-on before denied list persisted")
                self.assertEqual(json.loads(saved.read_text()), obj.pending)
                state["permission_sha256"] = hashlib.sha256(saved.read_bytes()).hexdigest()
                state["uid"] = 0
                if root_on_fails:
                    raise OSError("fixture root-on transport/log failure after elevation")
                return 0, "fixture root-on"
            if argv[-2:] == ["root", "off"]:
                state["root_off"] += 1
                state["uid"] = 0 if state["root_off"] <= off_failures else 5001
                return 0, "fixture root-off"
            if label in fail_labels:
                raise OSError("injected fixture transport/log failure: " + label)
            if argv == ["sdb", "version"]:
                return 0, "fixture sdb"
            if argv[:2] == ["sdb", "connect"]:
                return 0, "connected fixture"
            self.assertEqual(argv[-2], "shell")
            self.assertLessEqual(len(argv[-1].encode("utf-8")), 200)
            self.assertTrue(argv[-1].endswith(wire.SUFFIX))
            operation = shlex.split(argv[-1][len("LC_ALL=C "):-len(wire.SUFFIX)])
            self.assertIn(operation[0], {"id", "uname", "cat", "rpm", "stat", "ps", "df", "ls", "dmesg", "date", "uptime", "sha256sum", "base64"})
            self.assertNotIn("-e", operation)
            self.assertNotIn("-U", operation)
            self.assertNotIn("malloc_trim", " ".join(operation))
            self.assertNotIn("malloc_info", " ".join(operation))
            self.assertNotIn("run_cell_remote", " ".join(operation))
            phase, logical = label.split("_", 1)
            rc, payload = respond(logical, phase)
            return 97, payload + "\n\nRC=%d\n%s\n" % (rc, "DONE" if rc == 0 else "FAIL")

        def fake_git(*args):
            if args == ("rev-parse", "HEAD"):
                return HEAD
            if args == ("status", "--porcelain"):
                return " M fixture" if dirty else ""
            if args == ("ls-remote", "origin", "refs/heads/main"):
                return pushed + " refs/heads/main"
            self.fail("unexpected Git request: " + repr(args))

        with mock.patch.object(single, "SOURCE", self.source), \
             mock.patch.object(single, "git", side_effect=fake_git), \
             mock.patch.object(single, "sources", side_effect=local_error, return_value=(self.prior, paths, INVENTORY)), \
             mock.patch.object(single.Gate, "run", autospec=True, side_effect=transport), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            rc = obj.execute()
        if "permission_sha256" in state:
            self.assertEqual(hashlib.sha256((obj.out / "permission_denied.json").read_bytes()).hexdigest(), state["permission_sha256"])
        for key in ("measurement_cells_run", "board_files_pushed", "packages_changed", "governor_writes", "processes_terminated"):
            self.assertEqual(obj.receipt[key], 0)
        return obj, rc, events, state, output.getvalue()

    def test_all_2570_paths_individually_read_once_without_batching_or_omission(self):
        obj, rc, events, state, output = self.exercise(count=2570)
        self.assertEqual(rc, 0, output)
        rows = [(label, shlex.split(argv[-1][len("LC_ALL=C "):-len(wire.SUFFIX)]))
                for label, argv in events if label.startswith("NONROOT_PATH_")]
        self.assertEqual(len(rows), 2570)
        self.assertEqual([label for label, _ in rows], ["NONROOT_PATH_%04d" % n for n in range(2570)])
        self.assertEqual([op[-1] for _, op in rows], ["/fixture/package/%04d" % n for n in range(2570)])
        self.assertTrue(all(op == single.stat_op(op[-1]) for _, op in rows))
        self.assertEqual(obj.receipt["residue_inventory"]["total_paths"], 2570)
        self.assertEqual((state["root_on"], state["root_off"]), (0, 0))
        self.assertEqual(json.loads((obj.out / "permission_denied.json").read_text()), {})

    def test_nonroot_completes_before_one_root_round_replays_only_denied_items(self):
        denied = {"DMESG_START", "DMESG_END", "PATH_0001"}
        obj, rc, events, state, output = self.exercise(denied=denied, token=single.TOKEN)
        self.assertEqual(rc, 0, output)
        labels = [label for label, _ in events]
        onset = labels.index("ROOT_ON")
        self.assertLess(labels.index("NONROOT_PATH_0002"), onset)
        self.assertLess(labels.index("NONROOT_ALERTS_END"), onset)
        root_reads = [label[5:] for label in labels if label.startswith("ROOT_") and label not in
                      ("ROOT_ON", "ROOT_OFF_1", "ROOT_ID_ROOT", "ROOT_ID_OFF_1")]
        self.assertEqual(set(root_reads), denied)
        self.assertEqual(len(root_reads), len(denied))
        self.assertEqual(set(obj.pending), denied)
        self.assertEqual((state["root_on"], state["root_off"], state["uid"]), (1, 1, 5001))
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")

    def test_permission_without_token_records_whole_list_but_never_elevates(self):
        obj, rc, events, state, output = self.exercise(denied={"DMESG_START", "DMESG_END"})
        self.assertEqual(rc, 1, output)
        self.assertEqual(set(json.loads((obj.out / "permission_denied.json").read_text())), {"DMESG_START", "DMESG_END"})
        self.assertTrue(any(label == "NONROOT_ALERTS_END" for label, _ in events))
        self.assertEqual(state["root_on"], 0)

    def test_nonpermission_failure_does_not_trigger_root(self):
        obj, rc, _, state, output = self.exercise(token=single.TOKEN,
            overrides={("NONROOT", "DMESG_START"): (1, "dmesg: Input/output error")})
        self.assertEqual(rc, 1, output)
        self.assertEqual(state["root_on"], 0)
        self.assertNotIn("DMESG_START", obj.pending)

    def test_root_off_runs_after_root_on_or_replay_fault_and_is_bounded(self):
        for options in ({"root_on_fails": True}, {"fail_labels": {"ROOT_DMESG_START"}},
                        {"overrides": {("ROOT", "ID_ROOT"): (0, "uid=5001(fixture)")}},
                        {"off_failures": 2}):
            with self.subTest(options=options):
                obj, rc, _, state, output = self.exercise(denied={"DMESG_START"}, token=single.TOKEN, **options)
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 1)
                self.assertEqual(state["root_off"], 2 if options.get("off_failures") else 1)
                self.assertEqual(obj.receipt["root_authorization"]["root_off"], "FAIL" if options.get("off_failures") else "PASS_NONROOT")
        obj, rc, _, state, output = self.exercise(denied={"DMESG_START"}, token=single.TOKEN, off_failures=1)
        self.assertEqual(rc, 0, output)
        self.assertEqual(state["root_off"], 2)
        self.assertEqual(state["uid"], 5001)

    def test_local_dirty_unpushed_or_oversize_failure_never_connects(self):
        for settings in ({"dirty": True}, {"pushed": "b" * 40},
                         {"local_error": ValueError("LOCAL_STOP request body 201 > 200 bytes; NOT SENT")}):
            with self.subTest(settings=settings):
                obj, rc, events, _, output = self.exercise(**settings)
                self.assertEqual(rc, 1, output)
                self.assertEqual(events, [])

    def test_initial_identity_foreign_load_and_session_gates_never_elevate(self):
        cases = [("ID_BEFORE", "uid=0(root)"), ("UNAME_R", "wrong-board"), ("UNAME_M", "aarch64"),
                 ("OS_RELEASE", "BUILD_ID=other"), ("GLIBC", "glibc-2.41-1.1.armv7l"),
                 ("MEMINFO", "MemTotal: 1 kB"),
                 ("PS_START", PS_TABLE + "111 1 pts/1 sh sh -l\n"),
                 ("PS_START", PS_TABLE + "111 1 ? alloc_bench alloc_bench\n")]
        for label, text in cases:
            with self.subTest(label=label):
                obj, rc, _, state, output = self.exercise(denied={"DMESG_START"}, token=single.TOKEN,
                    overrides={("NONROOT", label): (0, text)})
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 0)

    def test_root_rejects_unregistered_operation_and_changed_registered_argv(self):
        obj = self.instance(single.TOKEN)
        obj.phase = "ROOT"
        obj.pending = {"ONE": {"argv": ["cat", "/fixture/one"], "reason": "denied", "directory": None}}
        for label, op in (("TWO", ["cat", "/fixture/two"]), ("ONE", ["cat", "/fixture/two"]),
                          ("TWO", ["rpm", "-qa"])):
            with self.subTest(label=label, op=op), mock.patch.object(subprocess, "run") as transport:
                with self.assertRaisesRegex(ValueError, "outside"):
                    obj.op(label, op, False)
                transport.assert_not_called()

    def test_known_boot_environment_health_or_inventory_failure_stops_before_root(self):
        cases = [("BOOT_END", "other-boot"), ("TARGET_STAT", TARGET_STAT[:-3] + "701"),
                 ("GOV_2", "performance"), ("PACKAGES", "\n".join(INVENTORY + ["new 1.0-1.armv7l"])),
                 ("DMESG_END", DMESG + "[1.0] oom-kill\n"), ("ZRAM_END", "1 0 0"),
                 ("TCP4", "0: 00000000:65F5 00000000:0000 01\n1: 00000000:65F5 00000000:0000 01"),
                 ("WORK", "directory|4096|1000|0:0")]
        for label, payload in cases:
            with self.subTest(label=label):
                obj, rc, events, state, output = self.exercise(denied={"DMESG_START"}, token=single.TOKEN,
                    overrides={("NONROOT", label): (0, payload)})
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 0, output)

    def test_known_single_health_failure_is_not_hidden_by_other_unreadable_stream(self):
        cases = [({"DMESG_START"}, "ZRAM_START", "1 0 0"),
                 ({"ZRAM_START"}, "DMESG_START", DMESG + "[1.0] Out of memory\n")]
        for denied, label, payload in cases:
            with self.subTest(label=label):
                obj, rc, _, state, output = self.exercise(denied=denied, token=single.TOKEN,
                    overrides={("NONROOT", label): (0, payload)})
                self.assertEqual(rc, 1, output)
                self.assertEqual(state["root_on"], 0, output)

    def test_readable_alert_children_are_attempted_as_nonroot_not_duplicated_as_root(self):
        obj, rc, events, state, output = self.exercise(denied={"DMESG_START"}, token=single.TOKEN,
            overrides={("NONROOT", "ALERTS_START"): (0, "fixture.zip")})
        self.assertEqual(rc, 0, output)
        labels = [label for label, _ in events]
        self.assertIn("NONROOT_ALERTS_START_0000_STAT", labels)
        self.assertIn("NONROOT_ALERTS_START_0000_SHA", labels)
        self.assertIn("NONROOT_ALERTS_START_0000_B64", labels)
        self.assertNotIn("ROOT_ALERTS_START_0000_STAT", labels)
        self.assertNotIn("ROOT_ALERTS_START_0000_SHA", labels)
        self.assertNotIn("ROOT_ALERTS_START_0000_B64", labels)
        if "ROOT_ON" in labels:
            self.assertLess(labels.index("NONROOT_ALERTS_START_0000_SHA"), labels.index("ROOT_ON"))

    def test_root_listing_new_project_suspect_is_recorded_but_never_passed_or_deleted(self):
        obj, rc, events, state, output = self.exercise(denied={"TOP_TMP"}, token=single.TOKEN,
            overrides={("ROOT", "TOP_TMP"): (0, "alloc_bench.old")})
        self.assertEqual(rc, 1, output)
        self.assertEqual(state["root_on"], 1)
        self.assertEqual((state["root_off"], state["uid"]), (1, 5001))
        self.assertEqual(obj.receipt["top_level_suspects"][0]["path"], "/tmp/alloc_bench.old")
        self.assertTrue(any(label == "ROOT_TOP_TMP_SUSPECT_0000" for label, _ in events))

    def test_root_scope_allows_only_named_direct_child_read_operations(self):
        obj = self.instance(single.TOKEN)
        obj.phase = "ROOT"
        obj.pending = {"DIR": {"argv": ["ls", "-A", "--", "/fixture"], "reason": "denied", "directory": "/fixture"}}
        for operation in (single.stat_op("/fixture/child"), ["sha256sum", "--", "/fixture/child"],
                          ["base64", "--", "/fixture/child"]):
            with self.subTest(operation=operation), mock.patch.object(obj, "run", return_value=(0, "payload\nRC=0\nDONE\n")) as run:
                self.assertEqual(obj.op("CHILD", operation, False, scope="DIR"), (0, "payload"))
                run.assert_called_once()
        bad = [("CHILD", single.stat_op("/elsewhere/child"), "DIR"),
               ("CHILD", single.stat_op("/fixture/nested/child"), "DIR"),
               ("CHILD", ["rm", "--", "/fixture/child"], "DIR"),
               ("CHILD", ["rpm", "-e", "/fixture/child"], "DIR"),
               ("ID_ROOT", ["rm", "--", "/fixture/child"], None),
               ("ID_OFF_1", ["cat", "/fixture/child"], None)]
        for label, op, scope in bad:
            with self.subTest(label=label, op=op), mock.patch.object(obj, "run") as run:
                with self.assertRaises(ValueError):
                    obj.op(label, op, False, scope=scope)
                run.assert_not_called()

    def test_single_base64_read_frames_actual_zip_bytes_without_board_temporary_file(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional base64 framing integration needs executable sh")
        encoded = base64.encodebytes(self.alert_bytes).decode()
        program = "base64() { printf '%%s' %s; }\n" % shlex.quote(encoded)
        body = wire.request(["base64", "--", "/fixture.zip"])
        self.assertLessEqual(len(body.encode()), 200)
        result = subprocess.run([shell, "-c", program + body], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        rc, payload = wire.parse(result.stdout)
        self.assertEqual(rc, 0)
        decoded = base64.b64decode("".join(payload.splitlines()), validate=True)
        self.assertEqual(decoded, self.alert_bytes)

    def alert_case(self, *, stamp=101, pid=498, executable="/usr/bin/enlightenment",
                   corruption=None, recheck=None, removal_failure=False, verify_present=False,
                   completed_sweep=True):
        obj = self.instance(single.TOKEN)
        obj.phase = "ROOT"
        scope = "ALERTS_START"
        name = "fixture.zip"
        path = single.CRASH + "/" + name
        obj.pending = {scope: {"argv": ["ls", "-A", "--", single.CRASH],
            "reason": "ls: Permission denied", "directory": single.CRASH}}
        if completed_sweep:
            obj.receipt["nonroot_sweep_completed_utc"] = "host fixture completed"
        data = self.archive_bytes(pid, executable)
        stat = "regular file|%d|%d|0:0" % (len(data), stamp)
        sha = hashlib.sha256(data).hexdigest() + "  " + path
        b64 = base64.encodebytes(data).decode()
        if corruption == "size":
            stat = "regular file|%d|%d|0:0" % (len(data) + 1, stamp)
        if corruption == "symlink":
            stat = stat.replace("regular file", "symbolic link")
        if corruption == "sha":
            sha = "0" * 64 + "  " + path
        if corruption == "base64":
            b64 = "@@@@"
        events = []

        def run(label, argv, timeout=20):
            self.assertEqual(argv[:4], ["sdb", "-s", obj.serial, "shell"])
            body = argv[-1]
            self.assertLessEqual(len(body.encode()), 200)
            op = shlex.split(body[len("LC_ALL=C "):-len(wire.SUFFIX)])
            self.assertEqual(op[-1], path)
            events.append((label, op))
            code = 0
            if label.endswith("_RECHECK_STAT"):
                payload = stat + "changed" if recheck == "stat" else stat
            elif label.endswith("_RECHECK_SHA"):
                payload = "0" * 64 + "  " + path if recheck == "sha" else sha
            elif label.endswith("_REMOVE"):
                self.assertEqual(op, ["rm", "--", path])
                archive = obj.out / "livedump" / scope / name
                self.assertEqual(archive.read_bytes(), data)
                persisted = json.loads((obj.out / "audit.json").read_text())
                self.assertTrue(persisted["alerts_" + scope][0]["attributable"])
                code, payload = (1, "rm: Permission denied") if removal_failure else (0, "")
            elif label.endswith("_VERIFY"):
                code, payload = (0, stat) if verify_present else (1, "stat: fixture: No such file or directory")
            elif label.endswith("_STAT"):
                payload = stat
            elif label.endswith("_SHA"):
                payload = sha
            elif label.endswith("_B64"):
                payload = b64
            else:
                self.fail("unexpected archive operation " + label)
            return 97, payload + "\nRC=%d\n%s\n" % (code, "DONE" if code == 0 else "FAIL")

        caught = None
        with mock.patch.object(single, "SOURCE", self.source), mock.patch.object(obj, "run", side_effect=run), \
             mock.patch.object(single.STABILITY, "inspect_archive", wraps=single.STABILITY.inspect_archive) as inspect:
            try:
                obj.archive_alerts(scope, [name])
                obj.classify_alerts(scope, [name], self.prior)
            except ValueError as error:
                caught = error
        return obj, caught, events, inspect

    def test_attributable_zip_is_archived_before_single_rechecks_remove_verify_and_health_stop(self):
        obj, error, events, inspect = self.alert_case()
        self.assertRegex(str(error), "new alert; no health waiver")
        inspect.assert_called_once()
        self.assertEqual([label.rsplit("_", 1)[-1] for label, _ in events],
                         ["STAT", "SHA", "B64", "STAT", "SHA", "REMOVE", "VERIFY"])
        self.assertEqual(sum(op[0] == "rm" for _, op in events), 1)
        self.assertTrue(obj.receipt["alerts_ALERTS_START"][0]["archived_then_removed_verified"])

    def test_foreign_zip_retained_and_board_second_boundary_preserved_with_stop(self):
        for settings in ({"pid": 999}, {"stamp": 106}, {"executable": "/usr/bin/foreign"},
                         {"stamp": 100}, {"stamp": 105}):
            with self.subTest(settings=settings):
                obj, error, events, inspect = self.alert_case(**settings)
                self.assertEqual(len(events), 3)
                self.assertFalse(any(op[0] == "rm" for _, op in events))
                inspect.assert_called_once()
                if settings.get("stamp") in (100, 105):
                    self.assertRegex(str(error), "new alert; no health waiver")
                    self.assertTrue(obj.receipt["alerts_ALERTS_START"][0]["ambiguous"])
                else:
                    self.assertIsNone(error)
                    self.assertEqual(obj.receipt["alerts_ALERTS_START"][0]["verdict"], "REPORT_ONLY_UNATTRIBUTED_LEFT_UNTOUCHED")

    def test_archive_base64_size_sha_and_symlink_gates_precede_inspection_or_delete(self):
        for corruption in ("size", "sha", "base64", "symlink"):
            with self.subTest(corruption=corruption):
                obj, error, events, inspect = self.alert_case(corruption=corruption)
                self.assertIsNotNone(error)
                self.assertEqual(len(events), 3)
                inspect.assert_not_called()
                self.assertFalse(any(op[0] == "rm" for _, op in events))

    def test_archive_changed_after_pull_remove_failure_or_presence_prevents_success(self):
        for settings in ({"recheck": "stat"}, {"recheck": "sha"},
                         {"removal_failure": True}, {"verify_present": True}, {"completed_sweep": False}):
            with self.subTest(settings=settings):
                obj, error, events, inspect = self.alert_case(**settings)
                self.assertIsNotNone(error)
                inspect.assert_called_once()
                removed = any(op[0] == "rm" for _, op in events)
                self.assertEqual(removed, bool(settings.get("removal_failure") or settings.get("verify_present")))
                self.assertNotIn("archived_then_removed_verified", obj.receipt["alerts_ALERTS_START"][0])

    def test_published_2570_paths_and_all_possible_single_reads_fit_hard_budget(self):
        published = single.SOURCE
        paths = sorted(set(single.original_body("GDB_INSTALLED_PATHS",
            (published / "GDB_INSTALLED_PATHS.txt").read_text()).splitlines()))
        self.assertEqual(len(paths), 2570)
        for path in paths:
            for argv in (single.stat_op(path), ["rpm", "-qf", "--", path], ["sha256sum", "--", path]):
                with self.subTest(path=path, executable=argv[0]):
                    self.assertLessEqual(len(wire.request(argv).encode("utf-8")), 200)


if __name__ == "__main__":
    unittest.main()
