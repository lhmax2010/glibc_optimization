"""Additional GDB helper fault paths; execute only with a synthetic gdb module."""
import contextlib
import io
import os
import pathlib
import sys
import types
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
SOURCE = (HERE / "g4_m7.py").read_text()
OUTPUT = "/opt/usr/glibc_memopt/system_level_before_after_20260908/G4_trim_r1/malloc_info_pre.xml"


class BadPointer:
    def __int__(self):
        raise RuntimeError("fixture unavailable pointer conversion")


class M7ExtraSafety(unittest.TestCase):
    def invoke(self, *, action="m7", failure=None):
        calls = []
        def evaluate(expression):
            calls.append(expression)
            if "fopen(" in expression:
                return BadPointer() if failure == "pointer" else 4096
            return 0
        def execute(command):
            calls.append(command)
            if "malloc_trim" in command and failure == "trim_call":
                raise RuntimeError("fixture trim call failure")
        def read_text(path, *args, **kwargs):
            if failure == "stat_read" and path.name == "stat":
                raise OSError("fixture proc-stat unreadable")
            if path.name == "comm":
                return "enlightenment\n"
            if failure == "stat_short":
                return "505 (enlightenment) S 0\n"
            tick = "101" if failure == "tick" else "100"
            return "505 (enlightenment) " + " ".join(["0"] * 19 + [tick])
        fake = types.SimpleNamespace(parse_and_eval=evaluate, execute=execute,
            selected_inferior=lambda: types.SimpleNamespace(pid=506 if failure == "pid" else 505))
        env = {"GLIBC_MEMOPT_M7_PATH": OUTPUT, "GLIBC_MEMOPT_TARGET_PID": "505",
               "GLIBC_MEMOPT_TARGET_TICK": "100", "GLIBC_MEMOPT_ACTION": action}
        if failure == "env":
            env.pop("GLIBC_MEMOPT_TARGET_TICK")
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"gdb": fake}), mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(pathlib.Path, "exists", return_value=False), \
             mock.patch.object(pathlib.Path, "is_symlink", return_value=False), \
             mock.patch.object(pathlib.Path, "read_text", read_text), contextlib.redirect_stdout(out):
            exec(compile(SOURCE, str(HERE / "g4_m7.py"), "exec"), {})
        return calls, out.getvalue()

    def test_unconvertible_fopen_pointer_still_detaches_and_fails(self):
        calls, out = self.invoke(failure="pointer")
        self.assertEqual(calls[-2:], ["detach", "quit 1"])
        self.assertEqual(sum("fopen(" in c for c in calls), 1)
        self.assertFalse(any("malloc_info(" in c or "fclose(" in c for c in calls))
        self.assertIn("unavailable pointer conversion", out)
        self.assertIn("FAIL_M7", out)

    def test_missing_environment_or_unreadable_malformed_stat_never_calls_inferior(self):
        for failure in ("env", "stat_read", "stat_short"):
            with self.subTest(failure=failure):
                calls, out = self.invoke(failure=failure)
                self.assertEqual(calls, ["detach", "quit 1"])
                self.assertIn("FAIL_M7", out)

    def test_trim_rechecks_attached_pid_and_start_tick_before_call(self):
        for failure in ("pid", "tick", "stat_read", "stat_short", "env"):
            with self.subTest(failure=failure):
                calls, out = self.invoke(action="trim", failure=failure)
                self.assertEqual(calls, ["detach", "quit 1"])
                self.assertIn("FAIL_TRIM", out)

    def test_trim_success_and_error_both_detach_without_retry(self):
        for failure, rc in ((None, 0), ("trim_call", 1)):
            with self.subTest(failure=failure):
                calls, out = self.invoke(action="trim", failure=failure)
                self.assertEqual(calls, ["call (int)malloc_trim(0)", "detach", "quit " + str(rc)])
                self.assertIn("DONE_TRIM RC=0" if not rc else "FAIL_TRIM", out)


if __name__ == "__main__":
    unittest.main()
