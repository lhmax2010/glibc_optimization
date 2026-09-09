"""G4-only continuation coverage. Every board/remote-Git operation is a double."""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import time
import types
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    spec = importlib.util.spec_from_file_location("g4_resume_under_test", HERE / "execute_g4_resume.py")
    resume = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resume)
BASE = sys.modules[resume.Executor.__module__]
G4_IDS = ["G4_trim_r1", "G4_trim_r2", "G4_trim_r3"]
HEAD = "a" * 40
BOOT = "12345678-1234-1234-1234-123456789abc"
INVENTORY = ["glibc 2.40-1.6.armv7l", "systemd 255-1.1.armv7l"]
SESSIONS = """COLLECTOR_PID=9000
  PID  PPID TT LSTART ETIME COMMAND
    1     0 ? fixture 01:00 /sbin/init
  505     1 ? fixture 01:00 enlightenment
 9000     1 pts/2 fixture 00:01 sh -c collector
 9001  9000 pts/2 fixture 00:00 ps -ww
"""


class G4ResumeSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="g4-resume-host-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.receipt = self.root / "contract.json"
        self.receipt.write_text(json.dumps({"tag_object": HEAD,
            "epoch_ns": time.time_ns() - 601_000_000_000,
            "origin_verified_utc": "2026-09-08T00:00:00+00:00"}))
        args = types.SimpleNamespace(ip="192.0.2.1", output_dir=self.root / "output",
            accepted_run=self.root / "preserved-accepted", contract_receipt=self.receipt,
            probe=self.root / "probe", gdb_cache=self.root / "cache")
        with mock.patch.object(BASE, "git", return_value=HEAD):
            self.instance = resume.G4Resume(args)
        self.instance.packages_before = INVENTORY.copy()

    def frozen_bytes(self, argv, **kwargs):
        self.assertEqual(argv[:2], ["git", "show"])
        relative = argv[2].split(":", 1)[1]
        return (BASE.ROOT / relative).read_bytes()

    def execute_with_doubles(self, *, failure_cell=None, authority_error=None,
                             pushed=HEAD):
        calls = []
        completed = []
        push_names = []
        instance = self.instance

        def remote(label, command):
            calls.append((label, command))
            if label == "TARGET_STAT":
                return "505 (enlightenment) " + " ".join(["S"] + ["0"] * 18 + ["700"])
            if label.startswith("ROUND_"):
                if label.endswith("_DMESG"):
                    return "[0.0] fixture boot\n[1.0] idle"
                if label.endswith("_ZRAM"):
                    return "0 0 0 0 0 0"
                if label.endswith("_ALERTS"):
                    return "remote_path\tsize\tmtime_epoch\tsha256"
                self.fail("unhandled health command: " + label)
            if label == "CELL_" + str(failure_cell):
                raise ValueError("fixture G4 controller failure")
            return ""

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(BASE, "git", return_value=""))
            stack.enter_context(mock.patch.object(BASE.subprocess, "check_output", side_effect=self.frozen_bytes))
            stack.enter_context(mock.patch.object(resume, "git", return_value=pushed + " refs/heads/main"))
            prefix = stack.enter_context(mock.patch.object(resume, "accepted_prefix",
                side_effect=authority_error, return_value={"verdict": "PRESERVED_ACCEPTED_PREFIX"}))
            check = stack.enter_context(mock.patch.object(instance, "check", return_value={"enlightenment_pid": 505}))
            stack.enter_context(mock.patch.object(instance, "remote", side_effect=remote))
            stack.enter_context(mock.patch.object(instance, "push", side_effect=lambda path, name, *a: push_names.append(name)))
            stack.enter_context(mock.patch.object(instance, "install_gdb"))
            stack.enter_context(mock.patch.object(instance, "pull_cell"))
            stack.enter_context(mock.patch.object(instance, "alerts"))
            stack.enter_context(mock.patch.object(BASE, "collect", side_effect=lambda path, cell: completed.append(cell["id"])))
            stack.enter_context(mock.patch.object(BASE, "validate_completed"))
            final_analysis = stack.enter_context(mock.patch.object(instance, "complete_analysis"))
            cleanup = stack.enter_context(mock.patch.object(instance, "cleanup", return_value="PASS"))
            text = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            rc = instance.execute()
            cleanup.assert_called_once()
            prefix.assert_called_once_with(instance.args.accepted_run)
            checks = check.call_count
            analyses = final_analysis.call_count
        return rc, calls, completed, push_names, checks, analyses, text.getvalue()

    def test_fixed_g4_schedule_and_probe_only_assets(self):
        self.assertEqual([c["id"] for c in self.instance.selected_cells()], G4_IDS)
        self.assertTrue(all(c["cycles"] == 1 for c in self.instance.selected_cells()))
        self.assertEqual(self.instance.asset_paths(), {"reclaim_probe.armv7l": self.instance.args.probe})
        self.assertFalse(hasattr(self.instance.args, "alloc"))
        self.assertFalse(hasattr(self.instance.args, "gst"))
        self.assertFalse(hasattr(self.instance.args, "media"))

    def test_changed_g4_schedule_fails_instead_of_running_other_cells(self):
        for cells in ([], list(reversed(resume.CONTRACT["cells"])),
                      resume.CONTRACT["cells"] + [resume.CONTRACT["cells"][-1]]):
            with self.subTest(ids=[c["id"] for c in cells]), \
                 mock.patch.object(resume, "CONTRACT", {**resume.CONTRACT, "cells": cells}):
                with self.assertRaisesRegex(ValueError, "G4-only schedule mismatch"):
                    self.instance.selected_cells()

    def test_accepted_prefix_refusal_prevents_all_board_activity(self):
        rc, calls, completed, pushed, checks, analyses, text = self.execute_with_doubles(
            authority_error=ValueError("fixture accepted-prefix integrity failure"))
        self.assertEqual(rc, 1, text)
        self.assertEqual((calls, completed, pushed, checks, analyses), ([], [], [], 0, 0))
        self.assertIn("accepted-prefix integrity failure", self.instance.receipt["reason"])

    def test_unpushed_executor_refusal_prevents_all_board_activity(self):
        rc, calls, completed, pushed, checks, analyses, text = self.execute_with_doubles(pushed="b" * 40)
        self.assertEqual(rc, 1, text)
        self.assertEqual((calls, completed, pushed, checks, analyses), ([], [], [], 0, 0))
        self.assertIn("pushed on origin/main", self.instance.receipt["reason"])

    def test_success_schedules_only_three_g4_cells_once(self):
        rc, calls, completed, pushed, checks, analyses, text = self.execute_with_doubles()
        self.assertEqual(rc, 0, text)
        self.assertEqual([label[5:] for label, _ in calls if label.startswith("CELL_")], G4_IDS)
        self.assertEqual(completed, G4_IDS)
        self.assertEqual((checks, analyses), (1, 1))
        self.assertEqual(self.instance.receipt["verdict"], "PASS_G4_ONLY")
        self.assertEqual(self.instance.receipt["completed_cells"], G4_IDS)
        self.assertEqual(pushed, ["reclaim_probe.armv7l", "run_cell_remote.sh", "capture_point.sh",
                                  "g4_m7.py", "sample_smaps_1s.sh"])
        self.assertFalse(any("G1_" in command or "G2_" in command or "G3_" in command
                             for label, command in calls if label.startswith("CELL_")))

    def test_preflight_only_never_pushes_installs_or_schedules_any_cell(self):
        self.instance.args.preflight_only = True
        rc, calls, completed, pushed, checks, analyses, text = self.execute_with_doubles()
        self.assertEqual(rc, 0, text)
        self.assertEqual((calls, completed, pushed, checks, analyses), ([], [], [], 1, 0))
        self.assertFalse(self.instance.created)
        self.assertFalse(self.instance.install_attempted)
        self.assertEqual(self.instance.receipt["verdict"], "PASS_READONLY_AVAILABILITY")

    def test_cli_refuses_output_inside_accepted_run_before_constructing_executor(self):
        accepted = self.root / "accepted"
        for output in (accepted, accepted / "nested"):
            argv = ["execute_g4_resume.py", "--ip", "192.0.2.1", "--output-dir", str(output),
                    "--accepted-run", str(accepted), "--contract-receipt", str(self.receipt),
                    "--probe", str(self.root / "probe"), "--gdb-cache", str(self.root / "cache")]
            with self.subTest(output=output), mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(resume, "G4Resume") as factory, \
                 contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit) as raised:
                    resume.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("must not be inside the accepted run", error.getvalue())
                factory.assert_not_called()

    def test_each_g4_failure_stops_without_retry_or_later_cells(self):
        # Fresh instances are required because output receipts are deliberately
        # single-use; each simulated run still touches only a private temp tree.
        for index, cell in enumerate(G4_IDS):
            with self.subTest(cell=cell):
                if index:
                    args = types.SimpleNamespace(**vars(self.instance.args))
                    args.output_dir = self.root / ("output-fail-" + str(index))
                    with mock.patch.object(BASE, "git", return_value=HEAD):
                        self.instance = resume.G4Resume(args)
                rc, calls, completed, _, checks, analyses, text = self.execute_with_doubles(failure_cell=cell)
                self.assertEqual(rc, 1, text)
                self.assertEqual([label[5:] for label, _ in calls if label.startswith("CELL_")], G4_IDS[:index + 1])
                self.assertEqual(completed, G4_IDS[:index])
                self.assertEqual((checks, analyses), (1, 0))
                self.assertEqual(self.instance.receipt["verdict"], "STOP")

    def fresh_check(self, *, boot=BOOT, sessions=SESSIONS):
        calls = []
        def remote(label, command):
            calls.append((label, command))
            if label == "POSTREBOOT_BOOT_ID":
                return boot
            if label == "POSTREBOOT_SESSIONS":
                return sessions
            self.fail("unexpected direct fresh-check operation: " + label)
        with mock.patch.object(resume.Executor, "check", return_value={"enlightenment_pid": 505}), \
             mock.patch.object(self.instance, "remote", side_effect=remote), \
             mock.patch.object(self.instance, "round_snapshot") as snapshot, \
             mock.patch.object(self.instance, "inventory", return_value=INVENTORY.copy()) as inventory:
            try:
                result = self.instance.check()
            except ValueError:
                snapshot.assert_not_called()
                inventory.assert_not_called()
                raise
            snapshot.assert_called_once_with("postreboot")
            inventory.assert_called_once_with("PACKAGE_INVENTORY_BEFORE")
        return result, calls

    def test_fresh_boot_and_only_collector_descendants_pass(self):
        result, calls = self.fresh_check()
        self.assertEqual(result["boot_id"], BOOT)
        self.assertEqual(result["interactive_sessions"], [])
        self.assertEqual(result["hygiene"], "PASS_FRESH_POSTREBOOT")
        self.assertEqual([label for label, _ in calls], ["POSTREBOOT_BOOT_ID", "POSTREBOOT_SESSIONS"])
        self.assertFalse(any("kill" in command or "CLOSE_" in label for label, command in calls))

    def test_invalid_boot_or_incomplete_process_table_fails_closed(self):
        for boot in ("", "not-a-boot-id"):
            with self.subTest(boot=boot), self.assertRaisesRegex(ValueError, "boot identity"):
                self.fresh_check(boot=boot)
        for sessions in ("", "COLLECTOR_PID=9000\n", SESSIONS.replace("COLLECTOR_PID=9000\n", ""),
                         SESSIONS.replace("    1     0 ? fixture 01:00 /sbin/init\n", "")):
            with self.subTest(sessions=sessions), self.assertRaises(ValueError):
                self.fresh_check(sessions=sessions)

    def test_old_authorized_pid_is_now_foreign_and_cannot_be_cleared(self):
        for pid in (26799, 27105, 12345):
            with self.subTest(pid=pid), self.assertRaisesRegex(ValueError, "no clearing authorized"):
                self.fresh_check(sessions=SESSIONS + "%d 1 pts/0 fixture 00:20 /bin/sh -l\n" % pid)

    def test_inventory_requires_successful_nonempty_valid_query(self):
        with mock.patch.object(self.instance, "remote", return_value="\n".join(reversed(INVENTORY))):
            self.assertEqual(self.instance.inventory("FIXTURE"), INVENTORY)
        for text in ("", "error: rpm database inaccessible", "gdb", "gdb 16.3-1.1.armv7l\nwarning: invalid"):
            with self.subTest(text=text), mock.patch.object(self.instance, "remote", return_value=text):
                with self.assertRaisesRegex(ValueError, "invalid full RPM inventory"):
                    self.instance.inventory("FIXTURE")
        with mock.patch.object(self.instance, "remote", side_effect=ValueError("rpm query RC gate")):
            with self.assertRaisesRegex(ValueError, "rpm query RC gate"):
                self.instance.inventory("FIXTURE")

    def test_cleanup_matches_inventory_and_records_nonblocking_shared_residue(self):
        self.instance.created = True
        self.instance.package_paths = ["/usr/share", "/usr/bin/gdb"]
        self.instance.receipt["preflight"] = {"boot_id": BOOT}
        health = self.instance.raw / "round_health"
        health.mkdir()
        for when in ("before", "after_cleanup"):
            (health / ("dmesg_" + when + ".txt")).write_text("[0.0] fixture boot\n")
            (health / ("zram_" + when + ".txt")).write_text("0 0 0\n")
            (health / ("stability_" + when + ".tsv")).write_text("remote_path\tsize\tmtime_epoch\tsha256\n")
        def remote(label, command):
            if label.startswith("PACKAGE_RESIDUE_"):
                return "/usr/share\tdirectory"
            if label == "POST_CLEANUP_BOOT_ID":
                return BOOT
            self.fail("unexpected cleanup command: " + label)
        with mock.patch.object(resume.Executor, "cleanup", return_value="PASS"), \
             mock.patch.object(self.instance, "inventory", return_value=INVENTORY.copy()), \
             mock.patch.object(self.instance, "remote", side_effect=remote), \
             mock.patch.object(self.instance, "round_snapshot") as snapshot, \
             mock.patch.object(self.instance, "alerts") as alerts:
            self.assertEqual(self.instance.cleanup(), "PASS")
            snapshot.assert_called_once_with("after_cleanup")
            alerts.assert_called_once_with("round_health", after_name="after_cleanup")
        self.assertEqual(self.instance.receipt["package_inventory"]["added"], [])
        self.assertEqual(self.instance.receipt["package_inventory"]["removed"], [])
        self.assertEqual(self.instance.receipt["package_residue_observations"], ["/usr/share\tdirectory"])
        self.assertIn("nonblocking", self.instance.receipt["package_warning_policy"])
        self.assertTrue(self.instance.receipt["post_cleanup_health"]["boot_id_unchanged"])

    def test_accepted_prefix_is_bound_to_published_receipt_and_every_manifest(self):
        run = self.instance.args.accepted_run
        run.mkdir()
        ids = [cell["id"] for cell in resume.CONTRACT["cells"] if cell["group"] != "G4"]
        receipt = {"verdict": "STOP", "cleanup": "PASS", "end_utc": "2026-09-08T08:16:11+00:00",
            "active_cell": "G4_trim_r1", "executor_commit": HEAD, "completed_cells": ids}
        receipt_path = run / "execution.json"
        receipt_path.write_text(json.dumps(receipt))
        published_path = self.root / "public-repo/data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json"
        published_path.parent.mkdir(parents=True)
        proofs = {name: {"verdict": "PASS", "files": {name + "/fixture": "b" * 64}} for name in ids}
        publication = {"execution": receipt, "pull_manifests": proofs}
        published_path.write_text(json.dumps(publication))
        before = receipt_path.read_bytes()
        public_before = published_path.read_bytes()
        with mock.patch.object(resume, "ROOT", self.root / "public-repo"), \
             mock.patch.object(resume, "verified_manifest", side_effect=lambda r, raw, name: proofs[name]) as verify, \
             mock.patch.object(resume.ANALYSIS, "analyze", return_value=[{}] * 330) as analyze:
            result = resume.accepted_prefix(run)
            self.assertEqual(result["completed_cells"], ids)
            self.assertEqual(result["verdict"], "PRESERVED_ACCEPTED_PREFIX")
            self.assertEqual([call.args[2] for call in verify.call_args_list], ids)
            self.assertEqual([c["id"] for c in analyze.call_args.args[1]["cells"]], ids)
        self.assertEqual(receipt_path.read_bytes(), before)
        self.assertEqual(published_path.read_bytes(), public_before)
        with mock.patch.object(resume, "ROOT", self.root / "public-repo"), \
             mock.patch.object(resume, "verified_manifest", return_value={"wrong": "proof"}), \
             mock.patch.object(resume.ANALYSIS, "analyze") as analyze:
            with self.assertRaisesRegex(ValueError, "pull differs from published proof"):
                resume.accepted_prefix(run)
            analyze.assert_not_called()
        publication["execution"] = {**receipt, "executor_commit": "c" * 40}
        published_path.write_text(json.dumps(publication))
        with mock.patch.object(resume, "ROOT", self.root / "public-repo"), \
             mock.patch.object(resume, "verified_manifest") as verify:
            with self.assertRaisesRegex(ValueError, "execution differs from published receipt"):
                resume.accepted_prefix(run)
            verify.assert_not_called()

    def test_cleanup_new_removed_package_or_query_error_cannot_pass(self):
        self.instance.created = True
        for after in (INVENTORY + ["gdb 16.3-1.1.armv7l"], INVENTORY[:-1]):
            with self.subTest(after=after), mock.patch.object(resume.Executor, "cleanup", return_value="PASS"), \
                 mock.patch.object(self.instance, "inventory", return_value=after):
                self.assertEqual(self.instance.cleanup(), "FAIL")
                self.assertIn("package inventory not restored", self.instance.receipt["cleanup_problems"])
        with mock.patch.object(resume.Executor, "cleanup", return_value="PASS"), \
             mock.patch.object(self.instance, "inventory", side_effect=ValueError("rpm query failure")):
            self.assertEqual(self.instance.cleanup(), "FAIL")
        self.assertIn("rpm query failure", self.instance.receipt["cleanup_problems"])

    def test_no_board_creation_means_no_cleanup_query(self):
        with mock.patch.object(resume.Executor, "cleanup", return_value="NO_BOARD_FILES_CREATED"), \
             mock.patch.object(self.instance, "inventory") as inventory, \
             mock.patch.object(self.instance, "remote") as remote:
            self.assertEqual(self.instance.cleanup(), "NO_BOARD_FILES_CREATED")
            inventory.assert_not_called()
            remote.assert_not_called()


if __name__ == "__main__":
    unittest.main()
