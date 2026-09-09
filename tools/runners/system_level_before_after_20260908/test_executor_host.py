"""No-board regression coverage for the host contract executor.

Every SDB transport, package command and board cleanup is mocked.  Test-created
archives and receipts live only in TemporaryDirectory; no measurement is made.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import sys
import tarfile
import tempfile
import time
import types
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    spec = importlib.util.spec_from_file_location("system_executor_host_under_test", HERE / "execute_contract.py")
    executor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(executor)


class ExecutorHost(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="system-host-executor-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.occupancy = self.root / "occupancy.json"
        self.occupancy.write_text(json.dumps({"verdict": "PASS_PM_OCCUPANCY_CLOSED"}))
        self.contract_receipt = self.root / "contract_receipt.json"
        self.contract_receipt.write_text(json.dumps({"tag_object": "a" * 40,
            "epoch_ns": time.time_ns() - 601_000_000_000,
            "origin_verified_utc": "2026-09-08T00:00:00+00:00"}))
        self.asset = self.root / "fixture-asset"
        self.asset.write_bytes(b"fixture-only\n")
        self.instance = self.make_executor("output")

    def make_executor(self, name):
        args = types.SimpleNamespace(ip="192.0.2.1", output_dir=self.root / name,
                                     occupancy_receipt=self.occupancy, contract_receipt=self.contract_receipt, alloc=self.asset,
                                     gst=self.asset, probe=self.asset, media=self.asset,
                                     gdb_cache=self.root / "package-cache")
        with mock.patch.object(executor, "git", return_value="a" * 40):
            return executor.Executor(args)

    def test_remote_requires_remote_markers_not_host_exit_status(self):
        cases = [
            (0, "transport returned success only\n", False),
            (0, "WRAPPER_RC_PROBE=1\nFAIL_REMOTE_PROBE\n", False),
            (0, "WRAPPER_RC_PROBE=0\nDONE_REMOTE_OTHER\n", False),
            (0, "WRAPPER_RC_PROBE=0\nWRAPPER_RC_PROBE=0\nDONE_REMOTE_PROBE\n", False),
            (0, "WRAPPER_RC_PROBE=0\nDONE_REMOTE_PROBE\nFAIL_REMOTE_PROBE\n", False),
            (0, "RC=0\nDONE_PROBE\n", False),
            (97, "payload\r\nWRAPPER_RC_PROBE=0\r\nDONE_REMOTE_PROBE\r\n", True),
            (0, "payload\nWRAPPER_RC_PROBE=0\nDONE_REMOTE_PROBE\n", True),
        ]
        for host_rc, output, valid in cases:
            with self.subTest(host_rc=host_rc, output=output):
                # Gate.run normally removes CR; the transport double matches its
                # normalized return contract, while preserving hostile host RC.
                with mock.patch.object(self.instance, "run", return_value=(host_rc, output.replace("\r", ""))) as run:
                    if valid:
                        self.assertEqual(self.instance.remote("PROBE", "read-only-fixture"), "payload")
                    else:
                        with self.assertRaisesRegex(ValueError, "remote RC/DONE gate failed"):
                            self.instance.remote("PROBE", "read-only-fixture")
                    self.assertEqual(run.call_count, 1)
                    self.assertIn("rc=$?", run.call_args.args[1][-1])

    def test_remote_preserves_inner_controller_markers_without_confusing_framing(self):
        output = "RC=0\nDONE_CELL_G1_none_r1\nWRAPPER_RC_CELL_G1_none_r1=0\nDONE_REMOTE_CELL_G1_none_r1\n"
        with mock.patch.object(self.instance, "run", return_value=(0, output)):
            self.assertEqual(self.instance.remote("CELL_G1_none_r1", "fixture"), "RC=0\nDONE_CELL_G1_none_r1")

    def test_push_local_hash_failure_never_calls_transport(self):
        with mock.patch.object(self.instance, "run") as run, mock.patch.object(self.instance, "remote") as remote:
            with self.assertRaisesRegex(ValueError, "local asset hash mismatch"):
                self.instance.push(self.asset, "alloc_bench_observer.armv7l", "0" * 64)
            run.assert_not_called()
            remote.assert_not_called()

    def test_push_remote_hash_failure_stops_even_after_host_success(self):
        digest = executor.sha(self.asset)
        with mock.patch.object(self.instance, "run", return_value=(0, "success")), \
             mock.patch.object(self.instance, "remote", return_value="0" * 64 + "  file"):
            with self.assertRaisesRegex(ValueError, "remote asset hash mismatch"):
                self.instance.push(self.asset, "alloc_bench_observer.armv7l", digest)

    def test_push_accepts_matching_remote_hash_even_if_sdb_host_status_is_bad(self):
        digest = executor.sha(self.asset)
        with mock.patch.object(self.instance, "run", return_value=(97, "unreliable host status")), \
             mock.patch.object(self.instance, "remote", return_value=digest + "  file"):
            self.instance.push(self.asset, "alloc_bench_observer.armv7l", digest)

    def test_archive_rejects_escape_symlink_hardlink_and_special_members(self):
        cell = "G1_none_r1"
        cases = [("/absolute", tarfile.REGTYPE), ("../escaped", tarfile.REGTYPE),
                 (cell + "/../../escaped", tarfile.REGTYPE), ("G2_none_r1/file", tarfile.REGTYPE),
                 (cell + "/symbolic", tarfile.SYMTYPE), (cell + "/hard", tarfile.LNKTYPE),
                 (cell + "/fifo", tarfile.FIFOTYPE), (cell + "/device", tarfile.CHRTYPE)]
        for name, kind in cases:
            with self.subTest(name=name, kind=kind):
                member = tarfile.TarInfo(name)
                member.type = kind
                archive = types.SimpleNamespace(getmembers=lambda: [member])
                with self.assertRaisesRegex(ValueError, "unsafe archive|unexpected archive"):
                    executor.checked_members(archive, cell)
        directory, regular = tarfile.TarInfo(cell), tarfile.TarInfo(cell + "/data.txt")
        directory.type = tarfile.DIRTYPE
        members = [directory, regular]
        self.assertEqual(executor.checked_members(types.SimpleNamespace(getmembers=lambda: members), cell), members)

    def tar_bytes(self, cell, files):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            directory = tarfile.TarInfo(cell)
            directory.type = tarfile.DIRTYPE
            directory.mode = 0o755
            archive.addfile(directory)
            for name, content in files.items():
                member = tarfile.TarInfo(cell + "/" + name)
                member.size = len(content)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(content))
        return stream.getvalue()

    def mock_pull(self, instance, failure="none"):
        cell = "G1_none_r1"
        files = {"data.txt": b"raw original\n"}
        payload = self.tar_bytes(cell, files)
        digest = hashlib.sha256(payload).hexdigest()
        manifest = "\n".join(hashlib.sha256(data).hexdigest() + "  " + cell + "/" + name for name, data in files.items())
        if failure == "file_hash":
            manifest = "0" * 64 + "  " + cell + "/data.txt"
        elif failure == "missing_file":
            manifest += "\n" + "1" * 64 + "  " + cell + "/missing.txt"
        labels = []

        def remote(label, command):
            labels.append(label)
            if label == "WORK_OWNER":
                return "OWNED"
            if label.startswith("MANIFEST_"):
                return manifest
            if label.startswith("TAR_SHA_"):
                return ("0" * 64 if failure == "archive_hash" else digest) + "  archive.tar.gz"
            return ""

        def run(label, argv, timeout=20):
            labels.append(label)
            if label.startswith("PULL_") and failure != "missing_archive":
                pathlib.Path(argv[-1]).write_bytes(payload)
            return (0, "transport status is not evidence")

        return cell, labels, remote, run

    def test_pull_verifies_archive_and_exact_per_file_set(self):
        cell, labels, remote, run = self.mock_pull(self.instance)
        with mock.patch.object(self.instance, "remote", side_effect=remote), mock.patch.object(self.instance, "run", side_effect=run):
            self.instance.pull_cell(cell)
        self.assertEqual(self.instance.verified_cells, {cell})
        proof = json.loads((self.instance.out / (cell + ".integrity.json")).read_text())
        self.assertEqual(proof["verdict"], "PASS")
        self.assertEqual((self.instance.raw / cell / "data.txt").read_bytes(), b"raw original\n")
        self.assertFalse(any("REMOVE" in label or "CLEAN" in label for label in labels))

    def test_failed_pull_keeps_board_original_even_when_cleanup_runs(self):
        for failure in ("archive_hash", "file_hash", "missing_file", "missing_archive"):
            with self.subTest(failure=failure):
                instance = self.make_executor("pull_" + failure)
                cell, labels, remote, run = self.mock_pull(instance, failure)
                instance.created = True
                instance.active_cell = cell
                with mock.patch.object(instance, "remote", side_effect=remote), mock.patch.object(instance, "run", side_effect=run):
                    with self.assertRaisesRegex(ValueError, "integrity failure|per-file pulled hash mismatch"):
                        instance.pull_cell(cell)
                    self.assertNotIn(cell, instance.verified_cells)
                    self.assertEqual(instance.cleanup(), "FAIL")
                self.assertNotIn("WORKDIR_REMOVE", labels)
                self.assertIn("RESTORE_GOVERNORS", labels)
                self.assertTrue(instance.receipt["cleanup_problems"])

    def test_existing_gdb_is_not_uninstalled(self):
        labels = []

        def remote(label, command):
            labels.append(label)
            if label == "PACKAGES_BEFORE":
                return "gdb 16.3-1.1.armv7l 12345\n"
            if label == "WORK_OWNER":
                return "OWNED"
            return ""

        self.instance.created = True
        with mock.patch.object(self.instance, "remote", side_effect=remote), mock.patch.object(self.instance, "push") as push:
            self.instance.install_gdb()
            self.assertFalse(self.instance.install_attempted)
            self.assertEqual(self.instance.cleanup(), "PASS")
            push.assert_not_called()
        self.assertIn("GDB_EXISTING", labels)
        self.assertNotIn("GDB_REMOVE", labels)

    def test_partial_existing_dependency_set_is_not_overwritten_or_removed(self):
        labels = []

        def remote(label, command):
            labels.append(label)
            if label == "WORK_OWNER":
                return "OWNED"
            return "libgmp 4.2.1-1.6.armv7l 12345\n" if label == "PACKAGES_BEFORE" else ""

        self.instance.created = True
        with mock.patch.object(self.instance, "remote", side_effect=remote), mock.patch.object(self.instance, "push") as push:
            with self.assertRaisesRegex(ValueError, "partial/pre-existing"):
                self.instance.install_gdb()
            self.assertEqual(self.instance.cleanup(), "PASS")
            push.assert_not_called()
        self.assertNotIn("GDB_INSTALL", labels)
        self.assertNotIn("GDB_REMOVE", labels)

    def test_partial_new_install_failure_still_rolls_back_this_round_packages(self):
        labels = []
        commands = {}

        def remote(label, command):
            labels.append(label)
            commands[label] = command
            if label == "WORK_OWNER":
                return "OWNED"
            if label == "PACKAGES_BEFORE":
                return "\n".join("package %s is not installed" % name for name in executor.GDB_NAMES)
            if label == "GDB_SPACE":
                return "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/root 3000000 10000 2990000 1% /\n"
            if label == "GDB_INSTALL":
                raise ValueError("fixture: installation failed after partial installation")
            return ""

        self.instance.created = True
        with mock.patch.object(self.instance, "remote", side_effect=remote), mock.patch.object(self.instance, "push") as push:
            with self.assertRaisesRegex(ValueError, "partial installation"):
                self.instance.install_gdb()
            self.assertTrue(self.instance.install_attempted)
            self.assertEqual(push.call_count, 6)
            self.assertEqual(self.instance.cleanup(), "PASS")
        self.assertIn("GDB_REMOVE", labels)
        for name in executor.GDB_NAMES:
            self.assertIn(name, commands["GDB_REMOVE"])
        self.assertIn("rpm -e --test", commands["GDB_REMOVE"])

    def test_insufficient_root_budget_never_installs(self):
        def remote(label, command):
            if label == "PACKAGES_BEFORE":
                return "all absent"
            if label == "GDB_SPACE":
                return "/dev/root 100000 10000 90000 10% /\n"
            self.fail("unexpected board mutation: " + label)

        with mock.patch.object(self.instance, "remote", side_effect=remote), mock.patch.object(self.instance, "push") as push:
            with self.assertRaisesRegex(ValueError, "budget failure"):
                self.instance.install_gdb()
            self.assertFalse(self.instance.install_attempted)
            push.assert_not_called()

    def test_ambiguous_work_owner_prevents_destructive_cleanup(self):
        self.instance.created = True
        with mock.patch.object(self.instance, "remote", side_effect=ValueError("missing owner proof")) as remote:
            self.assertEqual(self.instance.cleanup(), "FAIL")
        self.assertEqual([call.args[0] for call in remote.call_args_list], ["WORK_OWNER", "RESTORE_GOVERNORS"])
        self.assertIn("ambiguous work creation; preserved", self.instance.receipt["cleanup_problems"][0])

    def test_workdir_absence_does_not_skip_governor_or_package_recovery(self):
        self.instance.created = True
        self.instance.install_attempted = True
        labels = []

        def remote(label, command):
            labels.append(label)
            return "ABSENT" if label == "WORK_OWNER" else ""

        with mock.patch.object(self.instance, "remote", side_effect=remote):
            self.assertEqual(self.instance.cleanup(), "PASS")
        self.assertIn("RESTORE_GOVERNORS", labels)
        self.assertIn("OWN_HELPER_ABSENT", labels)
        self.assertIn("GDB_REMOVE", labels)
        self.assertNotIn("WORKDIR_REMOVE", labels)

    def test_helper_or_package_cleanup_failure_prevents_workdir_deletion(self):
        for failure in ("OWN_HELPER_ABSENT", "GDB_REMOVE"):
            with self.subTest(failure=failure):
                instance = self.make_executor("cleanup_" + failure)
                instance.created = True
                instance.install_attempted = failure == "GDB_REMOVE"
                labels = []

                def remote(label, command):
                    labels.append(label)
                    if label == "WORK_OWNER":
                        return "OWNED"
                    if label == failure:
                        raise ValueError("fixture cleanup failure")
                    return ""

                with mock.patch.object(instance, "remote", side_effect=remote):
                    self.assertEqual(instance.cleanup(), "FAIL")
                self.assertIn("RESTORE_GOVERNORS", labels)
                self.assertNotIn("WORKDIR_REMOVE", labels)
                self.assertTrue(instance.receipt["cleanup_problems"])

    def exercise_matrix(self, failure_phase=None, failure_index=4):
        instance = self.instance
        ordered = [cell["id"] for cell in executor.CONTRACT["cells"]]
        calls = []
        collected = []

        def remote(label, command):
            calls.append(label)
            if label.startswith("ROUND_"):
                if label.endswith("_DMESG"):
                    return "[0.0] fixture boot\n[1.0] fixture idle"
                if label.endswith("_ZRAM"):
                    return "0 0 0 0 0 0 0"
                if label.endswith("_ALERTS"):
                    return "remote_path\tsize\tmtime_epoch\tsha256"
                self.fail("unknown round snapshot request: " + label)
            if label == "TARGET_STAT":
                fields = ["S"] + ["0"] * 30
                fields[19] = "700"
                return "505 (enlightenment) " + " ".join(fields)
            if label == "PREPARE_WORK" and failure_phase == "prepare":
                raise ValueError("fixture lost success framing after mkdir")
            if label.startswith("CELL_") and failure_phase == "cell" and label == "CELL_" + ordered[failure_index]:
                raise ValueError("fixture cell failed")
            return ""

        def pull(cell):
            if failure_phase == "pull" and cell == ordered[failure_index]:
                raise ValueError("fixture pull failed")
            instance.verified_cells.add(cell)

        def collect(path, cell):
            collected.append(cell["id"])
            if failure_phase == "collect" and cell["id"] == ordered[failure_index]:
                raise ValueError("fixture collect failed")

        def validate(raw, cells):
            if failure_phase == "validate" and cells[-1]["id"] == ordered[failure_index]:
                raise ValueError("fixture health failed")

        def frozen_bytes(argv, **kwargs):
            self.assertEqual(argv[:2], ["git", "show"])
            relative = argv[2].split(":", 1)[1]
            return (executor.ROOT / relative).read_bytes()

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(executor, "git", return_value=""))
            stack.enter_context(mock.patch.object(executor.subprocess, "check_output", side_effect=frozen_bytes))
            analyze = stack.enter_context(mock.patch.object(executor.subprocess, "run"))
            stack.enter_context(mock.patch.object(instance, "check", return_value={"enlightenment_pid": 505}))
            stack.enter_context(mock.patch.object(instance, "remote", side_effect=remote))
            stack.enter_context(mock.patch.object(instance, "push"))
            stack.enter_context(mock.patch.object(instance, "install_gdb"))
            stack.enter_context(mock.patch.object(instance, "pull_cell", side_effect=pull))
            stack.enter_context(mock.patch.object(instance, "alerts"))
            stack.enter_context(mock.patch.object(executor, "collect", side_effect=collect))
            stack.enter_context(mock.patch.object(executor, "validate_completed", side_effect=validate))
            cleanup = stack.enter_context(mock.patch.object(instance, "cleanup", return_value="PASS"))
            transcript = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result = instance.execute()
            cleanup.assert_called_once()
            if failure_phase is None:
                analyze.assert_called_once()
                self.assertEqual(result, 0, transcript.getvalue())
                self.assertEqual(instance.receipt["verdict"], "PASS_COMPLETE_MATRIX")
                self.assertEqual(instance.receipt["completed_cells"], ordered)
                self.assertEqual(collected, ordered)
                self.assertIsNone(instance.active_cell)
                expected = ordered
            else:
                analyze.assert_not_called()
                self.assertEqual(result, 1, transcript.getvalue())
                self.assertEqual(instance.receipt["verdict"], "STOP")
                if failure_phase == "prepare":
                    self.assertEqual(instance.receipt["completed_cells"], [])
                    self.assertIsNone(instance.active_cell)
                    self.assertTrue(instance.created, "creation intent lost after ambiguous transport failure")
                    expected = []
                else:
                    self.assertEqual(instance.receipt["completed_cells"], ordered[:failure_index])
                    self.assertEqual(instance.active_cell, ordered[failure_index])
                    expected = ordered[:failure_index + 1]
        self.assertEqual([label[5:] for label in calls if label.startswith("CELL_")], expected)
        saved = json.loads((instance.out / "execution.json").read_text())
        self.assertEqual(saved["cleanup"], "PASS")
        return saved

    def test_all_21_cells_execute_in_exact_frozen_order(self):
        self.assertEqual(len(executor.CONTRACT["cells"]), 21)
        self.exercise_matrix()

    def test_any_cell_failure_stops_later_cells_and_runs_cleanup(self):
        self.exercise_matrix("cell")

    def test_any_collect_failure_stops_later_cells_and_runs_cleanup(self):
        self.exercise_matrix("collect")

    def test_any_pull_failure_stops_later_cells_and_runs_cleanup(self):
        self.exercise_matrix("pull")

    def test_any_frozen_validation_failure_stops_later_cells_and_runs_cleanup(self):
        self.exercise_matrix("validate")

    def test_ambiguous_prepare_response_records_creation_intent_and_runs_cleanup(self):
        self.exercise_matrix("prepare")

    def test_validate_completed_defers_only_exact_missing_none_join(self):
        trim = next(cell for cell in executor.CONTRACT["cells"] if cell["id"] == "G1_trim_r2")
        none = next(cell for cell in executor.CONTRACT["cells"] if cell["id"] == "G1_none_r2")
        with mock.patch.object(executor.ANALYSIS, "analyze", side_effect=ValueError("missing matched none control")) as analyze:
            self.assertIsNone(executor.validate_completed(self.instance.raw, [trim]))
            self.assertEqual(analyze.call_args.args[1]["cells"], [trim])
            with self.assertRaisesRegex(ValueError, "missing matched none control"):
                executor.validate_completed(self.instance.raw, [trim, none])
        for error in (ValueError("health hard failure"), ValueError("G4 injection interval short"),
                      ValueError("missing matched none control: altered message"), FileNotFoundError("source missing")):
            with self.subTest(error=str(error)), mock.patch.object(executor.ANALYSIS, "analyze", side_effect=error):
                with self.assertRaises(type(error)):
                    executor.validate_completed(self.instance.raw, [trim])

    def round_health_fixture(self, *, before="[0.0] boot\n[1.0] idle\n", after=None,
                             zram_before="0 0 0 0 0 0\n", zram_after="0 0 0 0 0 0\n"):
        path = self.instance.raw / "round_health"
        path.mkdir(exist_ok=True)
        (path / "dmesg_before.txt").write_text(before)
        (path / "dmesg_after.txt").write_text(before if after is None else after)
        (path / "zram_before.txt").write_text(zram_before)
        (path / "zram_after.txt").write_text(zram_after)
        for when in ("before", "after"):
            (path / ("stability_" + when + ".tsv")).write_text("remote_path\tsize\tmtime_epoch\tsha256\n")
        return path

    def test_round_health_healthy_prefix_and_zero_zram_delta_pass(self):
        self.round_health_fixture(after="[0.0] boot\n[1.0] idle\n[2.0] ordinary kernel event\n")
        self.instance.validate_round_health()
        self.assertEqual(self.instance.receipt["round_health"], {
            "oom_lmk_new": 0, "zram_three_delta": [0, 0, 0],
            "stability_before": 0, "stability_after": 0, "attributable_alerts_new": 0})

    def test_round_health_empty_short_negative_changed_or_invalid_zram_fails(self):
        for before, after in (("", ""), ("0 0", "0 0"), ("0 0 0", "1 0 0"),
                              ("0 0 0", "0 1 0"), ("0 0 0", "0 0 1"),
                              ("-1 0 0", "-1 0 0"), ("not-a-counter", "0 0 0")):
            with self.subTest(before=before, after=after):
                self.round_health_fixture(zram_before=before, zram_after=after)
                with self.assertRaises(ValueError):
                    self.instance.validate_round_health()
                self.assertNotIn("round_health", self.instance.receipt)

    def test_round_health_new_oom_or_lmk_fails_but_historical_event_is_retained(self):
        for message in ("Out of memory", "oom-kill", "Killed process 123", "lowmemorykiller", "low memory killer"):
            with self.subTest(message=message):
                self.round_health_fixture(after="[0.0] boot\n[1.0] idle\n[2.0] " + message + "\n")
                with self.assertRaisesRegex(ValueError, "round OOM/LMK hard failure"):
                    self.instance.validate_round_health()
        self.round_health_fixture(before="[0.0] historical Out of memory\n[1.0] idle\n")
        self.instance.validate_round_health()
        self.assertEqual(self.instance.receipt["round_health"]["oom_lmk_new"], 0)

    def test_round_health_lost_dmesg_history_cannot_pass(self):
        self.round_health_fixture(after="[5.0] replacement ring contents\n")
        with self.assertRaisesRegex(ValueError, "round dmesg history lost"):
            self.instance.validate_round_health()

    def test_round_health_records_stability_counts_and_attribution_without_waiver(self):
        path = self.round_health_fixture()
        row = "/opt/usr/share/crash/livedump/fixture.zip\t123\t100\t" + "a" * 64 + "\n"
        with (path / "stability_after.tsv").open("a") as stream:
            stream.write(row)
        self.instance.owned_alerts = [{"remote_path": "/opt/usr/share/crash/livedump/fixture.zip"}]
        self.instance.validate_round_health()
        health = self.instance.receipt["round_health"]
        self.assertEqual((health["stability_before"], health["stability_after"]), (0, 1))
        self.assertEqual(health["attributable_alerts_new"], 1)
        # execute() owns the verdict transition; this method must retain rather
        # than waive the count before that mandatory transition.
        source = (HERE / "execute_contract.py").read_text()
        self.assertRegex(source, r'if self\.owned_alerts:\s+self\.receipt\["verdict"\] = "STOP"')


if __name__ == "__main__":
    unittest.main()
