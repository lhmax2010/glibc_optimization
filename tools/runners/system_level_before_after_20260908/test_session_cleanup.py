"""No SDB; exercise exact-PID refusal and successful TERM with private proc fixtures."""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import close_approved_sessions as cleanup


class SessionCleanup(unittest.TestCase):
    def test_only_explicit_collector_and_children_excluded(self):
        text = "COLLECTOR_PID=10\n10 1 pts/0 sh -c ps\n11 10 pts/0 sh -c ps\n13 11 pts/0 ps\n12 1 pts/1 sh -l\n"
        self.assertEqual(cleanup.foreign_sessions(text), ["12 1 pts/1 sh -l"])
        with self.assertRaises(ValueError):
            cleanup.foreign_sessions("10 1 pts/0 sh -c ps")

    def run_case(self, *, ticks="60331272", cmd=b"/bin/sh\0-l\0", tty="/dev/pts/0", absent=False):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            proc = root / "proc/26799"
            if not absent:
                (proc / "fd").mkdir(parents=True)
                fields = ["0"] * 20
                fields[0], fields[19] = "S", ticks
                (proc / "stat").write_text("26799 (sh) " + " ".join(fields))
                (proc / "cmdline").write_bytes(cmd)
                (proc / "fd/0").symlink_to(tty)
            command = cleanup.close_command(*cleanup.APPROVED[0]).replace("/proc/", str(root / "proc") + "/")
            # A mock signal only removes the private fixture, never a host PID.
            command = 'kill() { echo MOCK_SIGNAL "$*"; rm -r "' + str(proc) + '"; };\n' + command
            return subprocess.run(["sh", "-c", command], capture_output=True, text=True, timeout=5)

    def test_matching_identity_terminates_and_verifies(self):
        p = self.run_case()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("MOCK_SIGNAL -TERM 26799", p.stdout)
        self.assertIn("VERIFIED_ABSENT", p.stdout)

    def test_reused_pid_wrong_command_or_tty_never_signalled(self):
        for kwargs in ({"ticks": "2"}, {"cmd": b"someone-else\0"}, {"tty": "/dev/pts/9"}):
            with self.subTest(kwargs=kwargs):
                p = self.run_case(**kwargs)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("FAIL_", p.stdout)
                self.assertNotIn("MOCK_SIGNAL", p.stdout)

    def test_already_absent_is_explicit_no_signal(self):
        p = self.run_case(absent=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("ALREADY_ABSENT", p.stdout)
        self.assertNotIn("MOCK_SIGNAL", p.stdout)


if __name__ == "__main__":
    unittest.main()
