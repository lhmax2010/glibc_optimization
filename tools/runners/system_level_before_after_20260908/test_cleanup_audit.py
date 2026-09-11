"""Delayed cleanup audit control boundaries; all board and Git calls are mocked."""
import contextlib
import hashlib
import io
import json
import pathlib
import re
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
    import audit_cleanup_20260911 as audit
    import sdb_request

HEAD = "a" * 40
BOOT = "12345678-1234-1234-1234-123456789abc"
DMESG = "[0.0] explicit host fixture boot\n"
ZRAM = "4096 74 4096 0 0 0\n"
STABILITY = "remote_path\tsize\tmtime_epoch\tsha256\n"
INVENTORY = ["glibc 2.40-1.6.armv7l", "systemd 255-1.1.armv7l"]
SESSIONS = """COLLECTOR_PID=9000
  PID PPID TT LSTART ETIME COMMAND
    1    0 ? fixture 01:00 /sbin/init
  498    1 ? fixture 01:00 enlightenment
 9000    1 pts/2 fixture 00:01 sh -c collector
 9001 9000 pts/2 fixture 00:00 ps -ww
"""
PERMISSION = "DMESG_READ_RC=1\ndmesg: read kernel buffer failed: Operation not permitted\nNEEDS_ROOT"
TARGET_STAT = "498 (enlightenment) " + " ".join(["S"] + ["0"] * 18 + ["700"])


class CleanupControl(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cleanup-audit-host-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / "immutable-source"
        health = self.source / "raw/round_health"
        health.mkdir(parents=True)
        (health / "dmesg_before.txt").write_text(DMESG)
        (health / "zram_before.txt").write_text(ZRAM)
        (health / "stability_before.tsv").write_text(STABILITY)
        self.prior = {"preflight": {"boot_id": BOOT, "enlightenment_pid": 498}, "target_starttime": 700,
                      "completed_cells": ["G4_trim_r1", "G4_trim_r2", "G4_trim_r3"],
                      "root_authorization": {"root_off": "PASS_NONROOT"}}
        (self.source / "execution.json").write_text(json.dumps(self.prior))
        self.counter = 0

    def exercise(self, *, overrides=None, permission=False, token=None, local_error=None,
                 dirty=False, pushed=HEAD, off_fails=False):
        self.counter += 1
        args = types.SimpleNamespace(ip="192.0.2.1", output_dir=self.root / ("audit-%d" % self.counter),
                                     pm_authorization=token)
        obj = audit.CleanupAudit(args)
        overridden = overrides or {}
        state = {"uid": 5001, "off_calls": 0}
        sent = []

        def response(label):
            if label in overridden:
                return overridden[label]
            if label.endswith("UNAME_R"):
                return "6-fixture-rpi4"
            if label.endswith("UNAME_M"):
                return "armv7l"
            if label.endswith("OS_RELEASE"):
                return "BUILD_ID=" + audit.CONTRACT["identity"]["build_id"]
            if label.endswith("GLIBC"):
                return audit.CONTRACT["identity"]["glibc"]
            if label.endswith("MEMINFO"):
                return "MemTotal: 8117408 kB"
            if label in ("ID_BEFORE", "ID_FINAL", "AUTH_ID_AFTER_ON") or label.startswith("AUTH_ID_AFTER_OFF_"):
                return "uid=%d(fixture) gid=100(users)" % state["uid"]
            if label == "READ_ACCESS":
                return PERMISSION if permission else "PASS_READ_ACCESS"
            if label == "ROOT_READ_ACCESS":
                return "PASS_READ_ACCESS"
            if label in ("BOOT_ID", "BOOT_ID_FINAL"):
                return BOOT
            if label == "SESSIONS":
                return SESSIONS
            if label == "PROCESS_NAMES":
                return "PID COMMAND\n1 systemd\n498 enlightenment\n9000 sh\n9001 ps"
            if label == "TARGET_STAT":
                return TARGET_STAT
            if label == "TCP":
                return "sl local_address rem_address st\n0: 00000000:65F5 00000000:0000 01"
            if label == "GOVERNORS":
                return "\n".join(["schedutil"] * 4)
            if label == "SPACE":
                return "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/fixture 3000000 1000000 2000000 33% /"
            if label == "UPTIME":
                return "explicit host fixture uptime"
            if label == "WORKDIR":
                return ""
            if label == "WORKDIR_METADATA":
                return "/fixture/retained directory 4096 1000 fixture:fixture"
            if label.startswith("ROUND_"):
                if label.endswith("_DMESG"):
                    return DMESG
                if label.endswith("_ZRAM"):
                    return ZRAM
                if label.endswith("_ALERTS"):
                    return STABILITY
            if label == "PACKAGE_INVENTORY_CURRENT":
                return "\n".join(INVENTORY)
            if label == "PACKAGES_ABSENT":
                return "\n".join("package %s is not installed" % name for name in audit.GDB_NAMES)
            if label.startswith("PACKAGE_RESIDUE_"):
                return ""
            self.fail("unexpected board command in control fixture: " + label)

        def transport(argv, **kwargs):
            sent.append(list(argv))
            self.assertEqual(pathlib.Path(argv[0]).name, "sdb")
            if argv[-1] == "version":
                return types.SimpleNamespace(returncode=0, stdout="fixture sdb\n")
            if argv[1] == "connect":
                return types.SimpleNamespace(returncode=0, stdout=overridden.get("connect", "connected fixture\n"))
            if argv[-2:] == ["root", "on"]:
                state["uid"] = 0
                return types.SimpleNamespace(returncode=0, stdout="fixture root on\n")
            if argv[-2:] == ["root", "off"]:
                state["off_calls"] += 1
                state["uid"] = 0 if off_fails else 5001
                return types.SimpleNamespace(returncode=0, stdout="fixture root off\n")
            self.assertEqual(argv[-2], "shell")
            label = re.search(r"WRAPPER_RC_([A-Za-z0-9_.-]+)=%s", argv[-1]).group(1)
            value = response(label)
            code, payload = value if isinstance(value, tuple) else (0, value)
            marker = "DONE_REMOTE_" if code == 0 else "FAIL_REMOTE_"
            return types.SimpleNamespace(returncode=0,
                stdout=payload + "\nWRAPPER_RC_%s=%d\n%s%s\n" % (label, code, marker, label))

        def fake_git(*argv):
            if argv == ("rev-parse", "HEAD"):
                return HEAD
            if argv == ("status", "--porcelain"):
                return " M fixture" if dirty else ""
            if argv == ("ls-remote", "origin", "refs/heads/main"):
                return pushed + " refs/heads/main"
            self.fail("unexpected Git operation: " + repr(argv))

        batches = sdb_request.residue_batches(["/fixture/package-path"])
        with mock.patch.object(audit, "SOURCE", self.source), \
             mock.patch.object(audit, "git", side_effect=fake_git), \
             mock.patch.object(audit, "local_sources", side_effect=local_error,
                               return_value=(self.prior, batches, INVENTORY)), \
             mock.patch.object(subprocess, "run", side_effect=transport), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            rc = obj.execute()
        # This allowlist is enforced on every successful/failing fixture path.
        # Only root lifecycle mutations are authorized; every other request is a
        # read command, never measurement/push/install/delete/governor writes.
        for argv in sent:
            if "shell" not in argv:
                self.assertTrue(argv[-1] == "version" or argv[1] == "connect" or argv[-2:] in (["root", "on"], ["root", "off"]))
                continue
            body = argv[-1]
            self.assertNotRegex(body, r"\brpm\s+-(?:U|i|e)(?:\b|[a-zA-Z])")
            self.assertNotRegex(body, r"\b(?:reboot|poweroff|kill|chmod|mkdir|rmdir|rm)\b")
            self.assertNotIn("malloc_trim(", body)
            self.assertNotIn("malloc_info(", body)
            self.assertNotIn("run_cell_remote.sh G", body)
            self.assertNotRegex(body, r">\s*[^;\n]*scaling_governor")
            self.assertLessEqual(sdb_request.check_request(body), sdb_request.MAX_SERVICE_BYTES)
        return obj, rc, sent, state, output.getvalue()

    def test_nonroot_read_access_passes_without_any_elevation(self):
        obj, rc, sent, state, text = self.exercise()
        self.assertEqual(rc, 0, text)
        self.assertEqual(obj.receipt["verdict"], "PASS_READONLY_CLEANUP")
        self.assertEqual(obj.receipt["root_elevation"], "NOT_NEEDED")
        self.assertFalse(any(argv[-2:] == ["root", "on"] for argv in sent))
        self.assertEqual(state["off_calls"], 0)
        self.assertTrue(obj.receipt["id_final"].startswith("uid=5001"))
        for key in ("measurement_cells_run", "board_files_pushed", "packages_changed", "governor_writes", "processes_terminated"):
            self.assertEqual(obj.receipt[key], 0)

    def test_only_permission_with_explicit_token_elevates_then_drops_root_last(self):
        obj, rc, sent, state, text = self.exercise(permission=True, token=audit.PM_TOKEN)
        self.assertEqual(rc, 0, text)
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")
        self.assertEqual((state["uid"], state["off_calls"]), (5001, 1))
        self.assertEqual(sum(argv[-2:] == ["root", "on"] for argv in sent), 1)
        self.assertEqual(sent[-2][-2:], ["root", "off"])
        self.assertIn("WRAPPER_RC_AUTH_ID_AFTER_OFF_1", sent[-1][-1])

    def test_permission_without_authorization_stops_and_never_elevates(self):
        obj, rc, sent, _, text = self.exercise(permission=True)
        self.assertEqual(rc, 1, text)
        self.assertIn("explicit one-round PM", obj.receipt["reason"])
        self.assertFalse(any(argv[-2:] == ["root", "on"] for argv in sent))

    def test_nonpermission_read_failures_do_not_authorize_root(self):
        for diagnostic in ("dmesg: not found", "dmesg: Input/output error", "dmesg: invalid option"):
            with self.subTest(diagnostic=diagnostic):
                body = "DMESG_READ_RC=127\n" + diagnostic + "\nACCESS_ERROR"
                obj, rc, sent, _, text = self.exercise(token=audit.PM_TOKEN, overrides={"READ_ACCESS": body})
                self.assertEqual(rc, 1, text)
                self.assertEqual(obj.receipt["verdict"], "STOP")
                self.assertFalse(any(argv[-2:] == ["root", "on"] for argv in sent))

    def test_identity_environment_boot_occupancy_governor_and_work_residue_stop(self):
        cases = [("PRE_UNAME_R", "not expected"), ("PRE_UNAME_M", "aarch64"),
                 ("PRE_OS_RELEASE", "BUILD_ID=other"), ("PRE_GLIBC", "glibc-2.41-1.1.armv7l"),
                 ("PRE_MEMINFO", "MemTotal: 100 kB"), ("BOOT_ID", "different boot"),
                 ("SESSIONS", SESSIONS + "27105 1 pts/1 fixture 00:30 /bin/sh -l\n"),
                 ("PROCESS_NAMES", "PID COMMAND\n1 systemd\n12345 alloc_bench"),
                 ("PROCESS_NAMES", ""), ("PROCESS_NAMES", "PID COMMAND\n498 enlightenment"),
                 ("PROCESS_NAMES", "1 systemd\n498 enlightenment"),
                 ("TARGET_STAT", TARGET_STAT.replace("498 (", "499 (")),
                 ("TARGET_STAT", TARGET_STAT[:-3] + "701"),
                 ("TCP", "0: 00000000:65F5 00000000:0000 01\n1: 00000000:65F5 00000000:0000 01"),
                 ("GOVERNORS", "performance\nschedutil\nschedutil\nschedutil"),
                 ("WORKDIR", "existing work requires review"), ("BOOT_ID_FINAL", "different boot")]
        for label, value in cases:
            with self.subTest(label=label):
                obj, rc, sent, _, text = self.exercise(overrides={label: value})
                self.assertEqual(rc, 1, text)
                self.assertEqual(obj.receipt["verdict"], "STOP")
                self.assertFalse(any(argv[-2:] == ["root", "on"] for argv in sent))

    def test_background_shell_sampler_is_detected_without_terminating_it(self):
        names = "PID COMMAND COMMAND\n1 systemd /sbin/init\n12345 sh sh /fixture/sample_smaps_1s.sh 498 /fixture/out\n"
        obj, rc, _, _, text = self.exercise(overrides={"PROCESS_NAMES": names})
        self.assertEqual(rc, 1, text)
        self.assertRegex(obj.receipt["reason"], "load|sampler/controller")

    def test_actual_access_probe_classifies_permission_not_arbitrary_dmesg_errors(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional access-probe shell integration requires executable sh")
        obj = object.__new__(audit.CleanupAudit)
        obj.remote = mock.Mock(return_value="PASS_READ_ACCESS")
        self.assertFalse(obj.access("FIXTURE"))
        source = obj.remote.call_args.args[1].replace("/opt/usr/share/crash/livedump", str(self.root / "no-crash-directory"))
        cases = [(0, "", "PASS_READ_ACCESS", False),
                 (1, "dmesg: Operation not permitted", "NEEDS_ROOT", True),
                 (1, "dmesg: Permission denied", "NEEDS_ROOT", True),
                 (127, "dmesg: not found", "ACCESS_ERROR", None),
                 (1, "dmesg: Input/output error", "ACCESS_ERROR", None),
                 (1, "dmesg: invalid option", "ACCESS_ERROR", None)]
        for rc, message, marker, expected in cases:
            with self.subTest(message=message):
                prelude = "dmesg() { printf '%%s\\n' %s; return %d; }\n" % (shlex.quote(message), rc)
                result = subprocess.run([shell, "-c", prelude + source], cwd=self.root, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines()[-1], marker)
                obj.remote.return_value = result.stdout
                if expected is None:
                    with self.assertRaises(ValueError):
                        obj.access("FIXTURE")
                else:
                    self.assertEqual(obj.access("FIXTURE"), expected)

    def test_actual_crash_access_stat_distinguishes_permission_unknown_and_absence(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional crash-access shell integration requires executable sh")
        obj = object.__new__(audit.CleanupAudit)
        obj.remote = mock.Mock(return_value="PASS_READ_ACCESS")
        obj.access("FIXTURE")
        source = obj.remote.call_args.args[1].replace("/opt/usr/share/crash/livedump", str(self.root))
        cases = [(0, "directory", "PASS_READ_ACCESS"),
                 (0, "symbolic link", "ACCESS_ERROR"),
                 (0, "regular file", "ACCESS_ERROR"),
                 (1, "stat: cannot stat path: No such file or directory", "PASS_READ_ACCESS"),
                 (1, "stat: cannot stat path: Permission denied", "NEEDS_ROOT"),
                 (1, "stat: cannot stat path: Operation not permitted", "NEEDS_ROOT"),
                 (1, "stat: Input/output error", "ACCESS_ERROR"),
                 (9, "stat: cannot stat path: No such file or directory", "ACCESS_ERROR"),
                 (127, "stat: not found", "ACCESS_ERROR")]
        for rc, message, marker in cases:
            with self.subTest(rc=rc, message=message):
                prelude = "dmesg() { :; }\nstat() { printf '%%s\\n' %s; return %d; }\n" % (shlex.quote(message), rc)
                result = subprocess.run([shell, "-c", prelude + source], cwd=self.root, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines()[-1], marker)
                obj.remote.return_value = result.stdout
                if marker == "ACCESS_ERROR":
                    with self.assertRaises(ValueError):
                        obj.access("FIXTURE")
                else:
                    self.assertEqual(obj.access("FIXTURE"), marker == "NEEDS_ROOT")

    def test_actual_round_snapshot_stat_only_explicit_enoent_yields_empty_alerts(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional round-snapshot shell integration requires executable sh")
        obj = object.__new__(audit.CleanupAudit)
        obj.raw = self.root / "round-fixture"
        obj.raw.mkdir()
        obj.remote = mock.Mock(side_effect=[DMESG, ZRAM, STABILITY])
        obj.round_snapshot("fixture")
        source = obj.remote.call_args.args[1].replace("/opt/usr/share/crash/livedump", str(self.root))
        cases = [(0, "directory", True), (0, "symbolic link", False),
                 (0, "regular file", False),
                 (1, "stat: cannot stat path: No such file or directory", True),
                 (1, "stat: cannot stat path: Permission denied", False),
                 (1, "stat: cannot stat path: Operation not permitted", False),
                 (1, "stat: Input/output error", False),
                 (9, "stat: cannot stat path: No such file or directory", False),
                 (127, "stat: not found", False)]
        for rc, message, success in cases:
            with self.subTest(rc=rc, message=message):
                prelude = "stat() { printf '%%s\\n' %s; return %d; }\nfind() { printf 'FIND_CALLED\\n' >&2; }\n" % (shlex.quote(message), rc)
                result = subprocess.run([shell, "-c", prelude + source], cwd=self.root, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
                if success:
                    self.assertEqual(result.stdout, STABILITY)
                self.assertEqual("FIND_CALLED" in result.stderr, rc == 0 and message == "directory")

    def alert_case(self, *, stamp=101, pid=498, executable="/usr/bin/enlightenment", corruption=None):
        """Real archive parser and local file hashes, transport/removal mocked."""
        self.counter += 1
        obj = audit.CleanupAudit(types.SimpleNamespace(ip="192.0.2.1",
            output_dir=self.root / ("alert-%d" % self.counter), pm_authorization=None))
        for index, cell in enumerate(self.prior["completed_cells"]):
            directory = self.source / "raw" / cell
            directory.mkdir(exist_ok=True)
            (directory / "start_ns.txt").write_text(str((100 + index * 100) * 10**9 + 500_000_000))
            (directory / "end_ns.txt").write_text(str((105 + index * 100) * 10**9 + 500_000_000))
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as zipped:
            zipped.writestr("dump_reason", "cpu.relative host fixture")
            zipped.writestr("info.json", json.dumps({"exe_file_path": executable, "threads": {"pid": pid}}))
        data = content.getvalue()
        remote = "/opt/usr/share/crash/livedump/host-fixture.zip"
        row = {"remote_path": remote, "size": str(len(data)), "mtime_epoch": str(stamp),
               "sha256": hashlib.sha256(data).hexdigest()}
        events = []

        def pull(label, argv):
            self.assertEqual(argv[:5], ["sdb", "-s", obj.serial, "pull", remote])
            target = pathlib.Path(argv[5])
            events.append("pull")
            if corruption == "deleted":
                return 0, "fixture did not create output"
            if corruption == "symlink":
                alternate = self.root / ("alternate-%d.zip" % self.counter)
                alternate.write_bytes(data)
                target.symlink_to(alternate)
            else:
                target.write_bytes(data[:-1] if corruption == "truncated" else
                                   bytes([data[0] ^ 1]) + data[1:] if corruption == "sha" else data)
            return 0, "fixture pull"

        def clean(label, command):
            events.append("clean")
            target = obj.out / "livedump/fixture/host-fixture.zip"
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), row["sha256"])
            persisted = json.loads((obj.out / "audit.json").read_text())
            self.assertTrue(persisted["alerts_fixture"][0]["attributable"])
            self.assertTrue(label.startswith("CLEAN_OWN_ALERT_fixture_"))
            self.assertIn("test ! -L " + remote, command)
            self.assertIn("sha256sum " + remote, command)
            self.assertIn(row["sha256"] + " && rm -- " + remote, command)
            self.assertIn("test ! -e " + remote, command)
            self.assertLess(command.index("sha256sum"), command.index("rm --"))
            return ""

        obj.run = mock.Mock(side_effect=pull)
        obj.remote = mock.Mock(side_effect=clean)
        caught = None
        with mock.patch.object(audit, "SOURCE", self.source), \
             mock.patch.object(audit.STABILITY, "inspect_archive", wraps=audit.STABILITY.inspect_archive) as inspect:
            try:
                obj.attribute_alerts({}, {remote: row}, self.prior, "fixture")
            except ValueError as error:
                caught = error
        return obj, caught, events, inspect

    def test_attributable_alert_is_archived_hash_verified_removed_then_hard_stop(self):
        obj, error, events, inspect = self.alert_case()
        self.assertRegex(str(error), "attributable new alert; archived/cleaned, no waiver")
        self.assertEqual(events, ["pull", "clean"])
        inspect.assert_called_once()
        row = obj.receipt["alerts_fixture"][0]
        self.assertTrue(row["in_original_g4_window"])
        self.assertTrue(row["archived_then_removed_verified"])
        self.assertEqual(row["verdict"], "FAIL")

    def test_outside_window_or_foreign_identity_alert_is_archived_never_deleted(self):
        for settings in ({"stamp": 106}, {"pid": 999}, {"executable": "/usr/bin/foreign-daemon"}):
            with self.subTest(settings=settings):
                obj, error, events, inspect = self.alert_case(**settings)
                self.assertIsNone(error)
                self.assertEqual(events, ["pull"])
                obj.remote.assert_not_called()
                inspect.assert_called_once()
                row = obj.receipt["alerts_fixture"][0]
                self.assertFalse(row["attributable"])
                self.assertEqual(row["verdict"], "REPORT_ONLY_UNATTRIBUTED_LEFT_UNTOUCHED")

    def test_board_clock_second_boundary_overlap_is_preserved_and_stops(self):
        for stamp in (100, 105):
            with self.subTest(stamp=stamp):
                obj, error, events, inspect = self.alert_case(stamp=stamp)
                self.assertRegex(str(error), "second-resolution window boundary")
                self.assertEqual(events, ["pull"])
                obj.remote.assert_not_called()
                inspect.assert_called_once()
                self.assertTrue(obj.receipt["alerts_fixture"][0]["mtime_boundary_ambiguous"])
                self.assertFalse(obj.receipt["alerts_fixture"][0]["attributable"])

    def test_missing_truncated_symlink_or_bad_sha_archive_never_reaches_delete(self):
        for corruption in ("sha", "truncated", "deleted", "symlink"):
            with self.subTest(corruption=corruption):
                obj, error, events, inspect = self.alert_case(corruption=corruption)
                self.assertRegex(str(error), "livedump pull integrity failure")
                self.assertEqual(events, ["pull"])
                obj.remote.assert_not_called()
                inspect.assert_not_called()

    def test_health_failure_after_elevation_still_restores_nonroot(self):
        obj, rc, sent, state, text = self.exercise(permission=True, token=audit.PM_TOKEN,
            overrides={"ROUND_AUDIT_END_DMESG": DMESG + "[1.0] Out of memory\n"})
        self.assertEqual(rc, 1, text)
        self.assertIn("OOM/LMK", obj.receipt["reason"])
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")
        self.assertEqual((state["uid"], state["off_calls"]), (5001, 1))
        self.assertEqual(sent[-2][-2:], ["root", "off"])

    def test_root_off_failure_is_bounded_and_prevents_pass(self):
        obj, rc, sent, state, text = self.exercise(permission=True, token=audit.PM_TOKEN, off_fails=True)
        self.assertEqual(rc, 1, text)
        self.assertEqual(state["off_calls"], 2)
        self.assertEqual(obj.receipt["verdict"], "STOP")
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "FAIL")

    def test_local_source_oversize_dirty_or_unpushed_gate_never_connects(self):
        for settings in ({"local_error": ValueError("SDB request rejected locally: oversized; not sent")},
                         {"dirty": True}, {"pushed": "b" * 40}):
            with self.subTest(settings=settings):
                obj, rc, sent, _, text = self.exercise(**settings)
                self.assertEqual(rc, 1, text)
                self.assertEqual(sent, [])
                self.assertEqual(obj.receipt["verdict"], "STOP")

    def test_connection_failure_never_probes_identity_or_root(self):
        obj, rc, sent, _, text = self.exercise(overrides={"connect": "HOST_TIMEOUT"})
        self.assertEqual(rc, 1, text)
        self.assertEqual(len(sent), 2)
        self.assertTrue(all("shell" not in argv for argv in sent))
        self.assertIn("connection failure", obj.receipt["reason"])

    def test_prior_raw_remote_markers_are_mandatory(self):
        good = "payload\r\nWRAPPER_RC_FIXTURE=0\r\nDONE_REMOTE_FIXTURE\r\n"
        self.assertEqual(audit.original_body("FIXTURE", good), "payload")
        for text in ("payload", good + "FAIL_REMOTE_FIXTURE\n", good + "WRAPPER_RC_FIXTURE=0\n",
                     good.replace("=0", "=1"), good.replace("DONE_REMOTE_FIXTURE", "DONE_REMOTE_OTHER")):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "RC/DONE failed"):
                audit.original_body("FIXTURE", text)

    def test_health_delta_preserves_history_and_rejects_every_hard_failure(self):
        self.assertEqual(audit.health_delta(DMESG, DMESG + "[1.0] normal\n", ZRAM, ZRAM), ["[1.0] normal"])
        self.assertEqual(audit.health_delta(DMESG, DMESG, ZRAM, ZRAM), [])
        for current in ("[1.0] replacement ring\n", DMESG + "[1.0] oom-kill\n",
                        DMESG + "[1.0] lowmemorykiller\n", DMESG + "[1.0] Killed process 123\n"):
            with self.subTest(current=current), self.assertRaises(ValueError):
                audit.health_delta(DMESG, current, ZRAM, ZRAM)
        for current in ("", "0 0", "-1 74 4096", "4096 75 4096", "bad counters"):
            with self.subTest(zram=current), self.assertRaises(ValueError):
                audit.health_delta(DMESG, DMESG, ZRAM, current)


if __name__ == "__main__":
    unittest.main()
