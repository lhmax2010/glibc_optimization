"""One-round root lifecycle: no real SDB calls."""
import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_authorized_g4_20260910 as auth


class AuthorizedRootTests(unittest.TestCase):
    def instance(self):
        obj = object.__new__(auth.AuthorizedG4)
        obj.addr, obj.serial = "192.0.2.1", "192.0.2.1:26101"
        obj.receipt = {"verdict": "STOP", "root_authorization": {}}
        obj.elevation_attempted = False
        obj.save = mock.Mock()
        obj.run = mock.Mock(return_value=(0, ""))
        obj.remote = mock.Mock()
        return obj

    def test_identity_and_nonroot_before_on_then_full_gate(self):
        obj = self.instance()
        obj.remote.side_effect = ["6-rpi4", "armv7l",
            "BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l",
            "uid=5001(owner) gid=5001(owner)", "uid=0(root) gid=0(root)"]
        with mock.patch.object(auth.G4Resume, "check", return_value={"full": "PASS"}) as gate:
            self.assertEqual(obj.check(), {"full": "PASS"})
        gate.assert_called_once()
        self.assertEqual([c.args[0] for c in obj.run.call_args_list], ["AUTH_CONNECT", "AUTH_ROOT_ON"])
        self.assertTrue(obj.elevation_attempted)

    def test_identity_or_unexpected_uid_never_elevates(self):
        prefixes = [["other"], ["rpi4", "aarch64"], ["rpi4", "armv7l", "BUILD_ID=other"],
            ["rpi4", "armv7l", "BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l", "uid=0(root)"]]
        for values in prefixes:
            with self.subTest(values=values):
                obj = self.instance()
                obj.remote.side_effect = values
                with self.assertRaises(ValueError):
                    obj.check()
                self.assertFalse(obj.elevation_attempted)
                self.assertEqual(obj.run.call_count, 1)

    def test_parent_failure_still_drops_root_after_cleanup(self):
        for rc in (0, 1):
            with self.subTest(rc=rc):
                obj = self.instance()
                def parent():
                    obj.elevation_attempted = True
                    obj.receipt["cleanup"] = "PASS"
                    return rc
                obj.remote.return_value = "uid=5001(owner) gid=5001(owner)"
                with mock.patch.object(auth.G4Resume, "execute", side_effect=parent), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(obj.execute(), rc)
                self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")
                self.assertEqual(obj.run.call_args.args[1][-2:], ["root", "off"])

    def test_unexpected_parent_exception_still_restores(self):
        obj = self.instance()
        obj.elevation_attempted = True
        obj.remote.return_value = "uid=5001(owner)"
        with mock.patch.object(auth.G4Resume, "execute", side_effect=RuntimeError("failure")), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "failure"):
                obj.execute()
        self.assertEqual(obj.receipt["root_authorization"]["root_off"], "PASS_NONROOT")

    def test_off_retry_bounded_and_failure_is_stop(self):
        for values, attempts, rc in ((["uid=0(root)", "uid=5001(owner)"], 2, 0),
                                    (["uid=0(root)", "uid=0(root)"], 2, 1),
                                    ([ValueError("transport"), "garbage"], 2, 1)):
            with self.subTest(values=values):
                obj = self.instance()
                obj.elevation_attempted = True
                obj.remote.side_effect = values
                with mock.patch.object(auth.G4Resume, "execute", return_value=0), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(obj.execute(), rc)
                self.assertEqual(obj.run.call_count, attempts)
                if rc:
                    self.assertEqual(obj.receipt["verdict"], "STOP")

    def test_no_elevation_attempt_no_root_off(self):
        obj = self.instance()
        with mock.patch.object(auth.G4Resume, "execute", return_value=1):
            self.assertEqual(obj.execute(), 1)
        obj.run.assert_not_called()

    def test_recording_error_does_not_prevent_off_retry(self):
        obj = self.instance()
        obj.remote.side_effect = ["uid=0(root)", "uid=5001(owner)"]
        obj.save.side_effect = OSError("fixture disk full")
        with contextlib.redirect_stdout(io.StringIO()) as log:
            self.assertTrue(obj.restore_nonroot())
        self.assertEqual(obj.run.call_count, 2)
        self.assertIn("FAIL_AUTH_RECORDING", log.getvalue())
        self.assertIn("recording_error", obj.receipt["root_authorization"])

    def test_connect_failure_prevents_identity_and_elevation(self):
        obj = self.instance()
        obj.run.return_value = (0, "failed to connect")
        with self.assertRaisesRegex(ValueError, "connection failed"):
            obj.check()
        obj.remote.assert_not_called()
        self.assertFalse(obj.elevation_attempted)

    def test_failed_on_never_enters_full_gate_but_off_still_runs(self):
        obj = self.instance()
        obj.remote.side_effect = ["rpi4", "armv7l",
            "BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l",
            "uid=5001(owner)", "uid=5001(owner)", "uid=5001(owner)"]
        with mock.patch.object(auth.G4Resume, "check") as full:
            with self.assertRaisesRegex(ValueError, "did not produce UID=0"):
                obj.check()
        full.assert_not_called()
        self.assertTrue(obj.restore_nonroot())
        self.assertEqual([c.args[0] for c in obj.run.call_args_list],
                         ["AUTH_CONNECT", "AUTH_ROOT_ON", "AUTH_ROOT_OFF_1"])


if __name__ == "__main__":
    unittest.main()
