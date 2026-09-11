import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    import publish_cleanup_audit as publisher


class CleanupPublication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cleanup-publication-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.out = self.root / "public"
        self.receipt = {"verdict": "STOP", "end_utc": "2026-09-11T00:00:00+00:00"}
        self.write()
        (self.run / "ID.txt").write_bytes(b"192.0.2.1 /fixture/home /opt/usr\r\nRC=0\r\n")

    def write(self):
        (self.run / "audit.json").write_text(json.dumps(self.receipt))

    def publish(self):
        with contextlib.redirect_stdout(io.StringIO()):
            publisher.publish(self.run, self.out, "192.0.2.1", "/fixture/home")

    def test_stop_publication_preserves_original_and_hashes_edits(self):
        before = (self.run / "ID.txt").read_bytes()
        self.publish()
        self.assertEqual((self.run / "ID.txt").read_bytes(), before)
        self.assertEqual((self.out / "ID.txt").read_bytes(), b"<TEST_BOARD_IP> <USER_HOME> /opt/usr\nRC=0\n")
        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(manifest["verdict"], "STOP")
        for row in manifest["files"]:
            self.assertEqual(row["original_sha256"], publisher.sha((self.run / row["path"]).read_bytes()))
            self.assertEqual(row["public_sha256"], publisher.sha((self.out / row["path"]).read_bytes()))

    def test_network_endpoints_redacted_in_raw_and_json_with_port_state_retained(self):
        line='0000000000000000FFFF0000010200C0:65F5 020200C0:ABCD 01'
        (self.run/'TCP.txt').write_text(line)
        self.receipt['connections']=[line]
        self.write()
        with contextlib.redirect_stdout(io.StringIO()):
            publisher.publish(self.run,self.out,'192.0.2.1','/fixture/home','192.0.2.2')
        self.assertEqual((self.out/'TCP.txt').read_text(),'<TEST_BOARD_IP>:65F5 <HOST_IP>:ABCD 01')
        self.assertEqual(json.loads((self.out/'audit.json').read_text())['connections'],
                         ['<TEST_BOARD_IP>:65F5 <HOST_IP>:ABCD 01'])
        self.assertEqual((self.run/'TCP.txt').read_text(),line)
        for row in json.loads((self.out/'manifest.json').read_text())['files']:
            self.assertEqual(row['original_sha256'],publisher.sha((self.run/row['path']).read_bytes()))
            self.assertEqual(row['public_sha256'],publisher.sha((self.out/row['path']).read_bytes()))

    def test_active_and_falsely_successful_root_receipts_rejected(self):
        for receipt in ({"verdict": "STOP"},
                        {**self.receipt, "root_authorization": {"root_off": "NOT-EVALUATED"}},
                        {**self.receipt, "verdict": "PASS_READONLY_CLEANUP"},
                        {**self.receipt, "verdict": "PASS_READONLY_CLEANUP", "root_authorization": {"root_off": "FAIL"}}):
            with self.subTest(receipt=receipt):
                self.receipt = receipt
                self.write()
                with self.assertRaises(ValueError):
                    self.publish()
                self.assertFalse(self.out.exists())

    def test_verified_nonroot_pass_can_be_archived(self):
        self.receipt.update(verdict="PASS_READONLY_CLEANUP", id_final="uid=5001(owner)")
        self.write()
        self.publish()
        self.assertEqual(json.loads((self.out / "audit.json").read_text())["verdict"], "PASS_READONLY_CLEANUP")

    def test_existing_overlap_and_symlink_outputs_rejected(self):
        for output in (self.run, self.run / "nested"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                publisher.publish(self.run, output, "192.0.2.1", "/fixture/home")
        self.out.symlink_to(self.run, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.publish()


if __name__ == "__main__":
    unittest.main()
