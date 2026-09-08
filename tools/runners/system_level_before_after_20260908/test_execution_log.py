"""Host-only execution-log publisher tests; all inputs are explicit fixtures."""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("execution_log_publisher_test", HERE / "publish_execution_log.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ExecutionLog(unittest.TestCase):
    ADDRESS = "192.0.2.9"
    HOME = "/home/host_fixture_only"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="execution-log-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.output = self.root / "public-fixture"
        self.receipt = {"verdict": "PASS_COMPLETE_MATRIX", "cleanup": "PASS",
                        "end_utc": "2026-09-08T08:00:00+00:00", "fixture_not_board_evidence": True}
        self.write("execution.json", json.dumps(self.receipt))
        self.write("commands.json", json.dumps([{"argv": ["sdb", self.ADDRESS, self.HOME + "/fixture"], "host_rc": 0}]))

    def write(self, relative, text):
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        return path

    def publish(self):
        with contextlib.redirect_stdout(io.StringIO()) as log:
            manifest = publisher.publish(self.run, self.output, self.ADDRESS, self.HOME)
        return manifest, log.getvalue()

    def assert_atomic_refusal(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".execution-log-publication-*")), [])

    def test_pass_terminal_and_whitelist_selection(self):
        selected = ("UNAME_R.txt", "SHA_alloc_bench_observer.armv7l.txt", "CELL_G1_none_r1.txt",
                    "GDB_INSTALL.txt", "ROUND_BEFORE_DMESG.txt", "RESTORE_GOVERNORS.txt", "WORKDIR_ABSENT.txt",
                    "raw/G1_none_r1/exit_status.txt", "raw/G1_none_r1/governor_after.txt",
                    "raw/G1_none_r1/zram_before.txt", "raw/G1_none_r1/stability_after.tsv",
                    "raw/G1_none_r1/dmesg_increment.txt", "raw/G1_none_r1/alert_attribution.json",
                    "raw/G1_none_r1/external_sampler_meta.txt", "raw/G4_trim_r3/debugger_identity.txt",
                    "raw/G4_trim_r1/injection_start_ns.txt", "raw/G4_trim_r1/injection_end_ns.txt",
                    "raw/G4_trim_r1/idle_start_ns.txt", "raw/G4_trim_r1/idle_end_ns.txt",
                    "raw/G4_trim_r1/idle_stat_start.txt", "raw/G4_trim_r1/idle_stat_end.txt",
                    "raw/G4_trim_r1/m7.gdb", "raw/G4_trim_r1/gdb_m7.txt", "raw/G4_trim_r1/gdb_m7.txt.stderr",
                    "raw/round_health/dmesg_before.txt", "raw/round_health/dmesg_after.txt")
        excluded = ("MANIFEST_G1_none_r1.txt", "TAR_G1_none_r1.txt", "TAR_SHA_G1_none_r1.txt",
                    "PULL_G1_none_r1.txt", "PUSH_binary.txt", "ALERT_PULL_fixture.zip.txt",
                    "unrelated.txt", "media.mp4", "G1_none_r1.tar.gz",
                    "raw/G1_none_r1/result.json", "raw/G1_none_r1/xml/phase.xml",
                    "raw/G1_none_r1/external_1s.tsv", "raw/G1_none_r1/dmesg_before.txt",
                    "raw/unrelated/exit_status.txt")
        for name in (*selected, *excluded):
            self.write(name, "HOST_FIXTURE_ONLY\n")
        manifest, output = self.publish()
        expected = set(selected) | {"commands.json", "execution.json"}
        self.assertEqual({row["path"] for row in manifest["files"]}, expected)
        self.assertEqual({path.relative_to(self.output).as_posix() for path in self.output.rglob("*") if path.is_file()},
                         expected | {"manifest.json"})
        self.assertIn("verdict=PASS_COMPLETE_MATRIX cleanup=PASS", output)

    def test_stop_terminal_can_publish_without_claiming_measurement_completion(self):
        self.receipt.update(verdict="STOP", cleanup="FAIL", reason="fixture cell failed")
        self.write("execution.json", json.dumps(self.receipt))
        manifest, output = self.publish()
        self.assertEqual(manifest["verdict"], "STOP")
        self.assertEqual(manifest["cleanup"], "FAIL")
        self.assertIn("verdict=STOP cleanup=FAIL", output)
        self.assertNotIn("PASS_COMPLETE_MATRIX", (self.output / "execution.json").read_text())

    def test_early_terminal_stop_without_transport_record_is_not_fabricated(self):
        self.receipt.update(verdict="STOP", cleanup="NO_BOARD_FILES_CREATED")
        self.write("execution.json", json.dumps(self.receipt))
        (self.run / "commands.json").unlink()
        manifest, _ = self.publish()
        self.assertFalse(manifest["commands_record_present"])
        self.assertFalse((self.output / "commands.json").exists())

    def test_active_or_invalid_terminal_receipt_is_rejected(self):
        for change in ({"end_utc": None}, {"end_utc": ""}, {"end_utc": "invalid"},
                       {"end_utc": "2026-09-08T08:00:00"}, {"cleanup": "NOT-EVALUATED"},
                       {"cleanup": None}, {"verdict": "RUNNING"}):
            with self.subTest(change=change):
                self.write("execution.json", json.dumps({**self.receipt, **change}))
                with self.assertRaises(ValueError):
                    self.publish()
                self.assert_atomic_refusal()

    def test_only_allowed_redactions_and_exact_original_public_hashes(self):
        original = ("HOST_FIXTURE_ONLY board=" + self.ADDRESS + "\r\nlocal=" + self.HOME +
                    "/result\r\nboard=/opt/usr/glibc_memopt/work\r\nBUILD_ID=public-image\n").encode()
        self.write("CELL_G1_none_r1.txt", original)
        manifest, _ = self.publish()
        public = original.replace(b"\r", b"").replace(self.ADDRESS.encode(), b"<TEST_BOARD_IP>").replace(self.HOME.encode(), b"<USER_HOME>")
        self.assertEqual((self.output / "CELL_G1_none_r1.txt").read_bytes(), public)
        self.assertEqual((self.run / "CELL_G1_none_r1.txt").read_bytes(), original)
        row = next(row for row in manifest["files"] if row["path"] == "CELL_G1_none_r1.txt")
        self.assertEqual(row["original_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(row["public_sha256"], hashlib.sha256(public).hexdigest())
        self.assertEqual(row["edits"], ["CR_REMOVED", "BOARD_ADDRESS_REPLACED", "HOST_HOME_REPLACED"])
        all_public = b"\n".join(path.read_bytes() for path in self.output.rglob("*") if path.is_file())
        self.assertNotIn(self.ADDRESS.encode(), all_public)
        self.assertNotIn(self.HOME.encode(), all_public)
        self.assertIn(b"/opt/usr/glibc_memopt/work", all_public)

    def test_selected_file_or_parent_symlink_is_rejected(self):
        target = self.root / "outside_fixture.txt"
        target.write_text("HOST_FIXTURE_ONLY\n")
        link = self.run / "UNAME_R.txt"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.publish()
        self.assert_atomic_refusal()
        link.unlink()
        outside_dir = self.root / "outside_fixture_group"
        outside_dir.mkdir()
        (outside_dir / "exit_status.txt").write_text("HOST_FIXTURE_ONLY\n")
        (self.run / "raw").mkdir()
        (self.run / "raw/G1_none_r1").symlink_to(outside_dir, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.publish()
        self.assert_atomic_refusal()
        self.assertEqual(target.read_text(), "HOST_FIXTURE_ONLY\n")

    def test_unselected_media_symlink_is_not_traversed_or_copied(self):
        (self.run / "media.mp4").symlink_to(self.root / "missing_external_media")
        self.publish()
        self.assertFalse((self.output / "media.mp4").exists())

    def test_failure_after_first_written_log_leaves_no_partial_publication(self):
        original = publisher.render_public
        calls = 0

        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("fixture write/transform failure")
            return original(*args)

        with mock.patch.object(publisher, "render_public", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "fixture"):
                self.publish()
        self.assertEqual(calls, 2)
        self.assert_atomic_refusal()

    def test_non_utf8_log_fails_without_lossy_edits_or_partial_output(self):
        self.write("UNAME_R.txt", b"HOST_FIXTURE_ONLY\xff\n")
        with self.assertRaises(UnicodeDecodeError):
            self.publish()
        self.assert_atomic_refusal()

    def test_source_changed_during_publication_is_rejected(self):
        original = publisher.render_public
        mutated = False

        def mutate_source(*args):
            nonlocal mutated
            if not mutated:
                self.write("commands.json", "[]\n")
                mutated = True
            return original(*args)

        with mock.patch.object(publisher, "render_public", side_effect=mutate_source):
            with self.assertRaisesRegex(ValueError, "changed during publication"):
                self.publish()
        self.assert_atomic_refusal()

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "preserve.txt"
        sentinel.write_text("preserve fixture\n")
        with self.assertRaisesRegex(ValueError, "refuse to overwrite"):
            self.publish()
        self.assertEqual(sentinel.read_text(), "preserve fixture\n")
        self.assertEqual(list(self.output.iterdir()), [sentinel])

    def test_output_symlink_and_output_inside_run_are_rejected(self):
        self.output.symlink_to(self.root / "missing_target", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.publish()
        self.output.unlink()
        with self.assertRaisesRegex(ValueError, "outside the original run"):
            publisher.publish(self.run, self.run / "public-fixture", self.ADDRESS, self.HOME)
        self.assertFalse((self.run / "public-fixture").exists())

    def test_redaction_configuration_rejects_root_home_and_invalid_address(self):
        for address, home in ((self.ADDRESS, "/"), (self.ADDRESS, "relative"), ("not-an-ip", self.HOME)):
            with self.subTest(address=address, home=home), self.assertRaises(ValueError):
                publisher.publish(self.run, self.output, address, home)
        self.assert_atomic_refusal()


if __name__ == "__main__":
    unittest.main()
