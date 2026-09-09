"""Execute the actual GDB Python helper with an inferior-call double, no ptrace."""
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


class M7Safety(unittest.TestCase):
    def invoke(self, failure="none", path=OUTPUT, pid="505", tick="100"):
        calls = []
        def evaluate(expression):
            calls.append(expression)
            if "fopen(" in expression:
                if failure == "fopen_error":
                    raise RuntimeError("fopen error")
                return 0 if failure == "null" else 4096
            if "malloc_info(" in expression:
                if failure == "m7_error":
                    raise RuntimeError("inferior malloc_info error")
                return 1 if failure == "m7_return" else 0
            if "fclose(" in expression:
                if failure == "close_error":
                    raise RuntimeError("inferior fclose error")
                return 1 if failure == "close_return" else 0
            raise AssertionError("unexpected inferior call")
        def execute(command):
            calls.append(command)
            if command == "detach" and failure == "detach":
                raise RuntimeError("detach error")
        def read_text(file, *args, **kwargs):
            if file.name == "comm":
                return "other\n" if failure == "comm" else "enlightenment\n"
            return "505 (enlightenment) " + " ".join(["0"] * 19 + ["101" if failure == "tick" else "100"])
        fake = types.SimpleNamespace(parse_and_eval=evaluate, execute=execute,
            selected_inferior=lambda: types.SimpleNamespace(pid=506 if failure == "pid" else 505))
        output = io.StringIO()
        with mock.patch.dict(sys.modules, {"gdb": fake}), mock.patch.dict(os.environ, {
                "GLIBC_MEMOPT_M7_PATH": path, "GLIBC_MEMOPT_TARGET_PID": pid,
                "GLIBC_MEMOPT_TARGET_TICK": tick}), \
             mock.patch.object(pathlib.Path, "exists", return_value=failure == "exists"), \
             mock.patch.object(pathlib.Path, "is_symlink", return_value=failure == "symlink"), \
             mock.patch.object(pathlib.Path, "read_text", read_text), contextlib.redirect_stdout(output):
            exec(compile(SOURCE, str(HERE / "g4_m7.py"), "exec"), {})
        return calls, output.getvalue()

    def test_success_closes_once_detaches_and_reports(self):
        calls, out = self.invoke()
        self.assertEqual(calls[-2:], ["detach", "quit 0"])
        self.assertEqual(sum("fopen(" in c for c in calls), 1)
        self.assertEqual(sum("fclose(" in c for c in calls), 1)
        self.assertIn("DONE_M7 RC=0", out)
        self.assertFalse(any("$" in c for c in calls))

    def test_null_and_open_error_never_use_or_close_null(self):
        for failure in ("null", "fopen_error"):
            with self.subTest(failure=failure):
                calls, out = self.invoke(failure)
                self.assertEqual(calls[-2:], ["detach", "quit 1"])
                self.assertFalse(any("malloc_info(" in c or "fclose(" in c for c in calls))
                self.assertIn("FAIL_M7", out)

    def test_m7_and_close_errors_close_exactly_once_and_fail(self):
        for failure in ("m7_error", "m7_return", "close_error", "close_return", "detach"):
            with self.subTest(failure=failure):
                calls, out = self.invoke(failure)
                self.assertEqual(calls[-1], "quit 1")
                self.assertEqual(sum("fclose(" in c for c in calls), 1)
                self.assertIn("detach", calls)
                self.assertNotIn("DONE_M7 RC=0", out)

    def test_pid_path_and_symlink_gate_precedes_inferior_calls(self):
        cases = [(f, OUTPUT, "505", "100") for f in ("exists", "symlink", "comm", "pid", "tick")]
        cases += [("none", p, "505", "100") for p in ("/tmp/escape", OUTPUT + "/extra",
                    OUTPUT.replace("G4_trim_r1", "G1_trim_r1"), OUTPUT.replace("G4_trim_r1", "../G4_trim_r1"))]
        cases += [("none", OUTPUT, p, "100") for p in ("0", "-1", "0505", "505;bad")]
        cases += [("none", OUTPUT, "505", "")]
        for failure, path, pid, tick in cases:
            with self.subTest(failure=failure, path=path, pid=pid, tick=tick):
                calls, out = self.invoke(failure, path, pid, tick)
                self.assertEqual(calls, ["detach", "quit 1"])
                self.assertIn("FAIL_M7", out)


if __name__ == "__main__":
    unittest.main()
