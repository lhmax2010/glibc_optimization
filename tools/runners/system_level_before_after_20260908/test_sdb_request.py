"""Byte-bounded SDB requests. No test invokes SDB or connects to a board."""
import contextlib
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
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys, "path", [str(HERE), *sys.path]):
    import sdb_request as request
    import preflight
    import execute_contract as executor
    import execute_g4_resume as resume

ROOT = HERE.parents[2]


def batch_paths(command):
    """Decode the producer's argument list without evaluating shell text."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";")
    lexer.whitespace_split = True
    tokens = list(lexer)
    if tokens[:3] != ["for", "p", "in"]:
        raise AssertionError("unexpected residue command prefix")
    if ";" not in tokens[3:]:
        raise AssertionError("unexpected residue command boundary")
    return tokens[3:tokens.index(";", 3)]


class RequestByteBudget(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdb-byte-budget-host-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.gate = preflight.Gate("192.0.2.1", self.root)

    def test_ascii_budget_counts_shell_prefix_and_accepts_exact_limit(self):
        body = "x" * (request.MAX_SERVICE_BYTES - len("shell:"))
        self.assertEqual(request.check_request(body), request.MAX_SERVICE_BYTES)
        with self.assertRaisesRegex(ValueError, "3501 bytes > 3500; not sent"):
            request.check_request(body + "x")
        self.assertEqual(request.check_request(""), 6)

    def test_utf8_uses_bytes_not_codepoints_at_boundary(self):
        for token in ("中", "é", "🙂"):
            with self.subTest(token=token):
                count, remainder = divmod(request.MAX_SERVICE_BYTES - 6, len(token.encode("utf-8")))
                body = token * count + "x" * remainder
                self.assertLess(len(body) + 6, request.MAX_SERVICE_BYTES)
                self.assertEqual(request.check_request(body), request.MAX_SERVICE_BYTES)
                with self.assertRaisesRegex(ValueError, "rejected locally"):
                    request.check_request(body + "x")

    def test_wrapping_overhead_is_included_before_send(self):
        for label in ("X", "PACKAGE_RESIDUE_0000", "PACKAGE_RESIDUE_10000"):
            with self.subTest(label=label):
                overhead = len(("shell:" + request.framed(label, "")).encode("utf-8"))
                command = ": #" + "x" * (request.MAX_SERVICE_BYTES - overhead - 3)
                self.assertLess(request.check_request(command), request.MAX_SERVICE_BYTES)
                self.assertEqual(request.check_request(request.framed(label, command)), request.MAX_SERVICE_BYTES)
                with self.assertRaisesRegex(ValueError, "not sent"):
                    request.check_request(request.framed(label, command + "x"))

    def test_invalid_marker_labels_never_construct_shell_requests(self):
        for label in ("", "name;exit", "name\n", "$(id)", "空白", "a b", "'quoted'"):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "invalid remote marker label"):
                request.framed(label, "true")

    def test_gate_oversize_and_split_argument_requests_never_call_subprocess(self):
        oversized = "x" * request.MAX_SERVICE_BYTES
        vectors = [
            ["sdb", "shell", oversized],
            ["/fixture/bin/sdb", "-s", "192.0.2.1:26101", "shell", oversized],
            ["sdb", "shell", "echo", "split request"],
            ["sdb", "shell"],
        ]
        for argv in vectors:
            with self.subTest(argv_prefix=argv[:3]), mock.patch.object(preflight.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    self.gate.run("HOST_FIXTURE", argv)
                run.assert_not_called()
        self.assertEqual(self.gate.commands, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_gate_exact_limit_reaches_only_mocked_transport(self):
        body = "x" * (request.MAX_SERVICE_BYTES - 6)
        result = types.SimpleNamespace(returncode=97, stdout="fixture transport output\n")
        with mock.patch.object(preflight.subprocess, "run", return_value=result) as run:
            self.assertEqual(self.gate.run("EXACT", ["sdb", "shell", body]), (97, result.stdout))
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][-1], body)
        self.assertEqual(self.gate.commands[0]["host_rc"], 97)

    def test_executor_remote_checks_complete_framed_request_and_remote_markers(self):
        obj = object.__new__(executor.Executor)
        preflight.Gate.__init__(obj, "192.0.2.1", self.root)
        obj.timeout = 30
        label = "WRAPPED"
        overhead = len(("shell:" + request.framed(label, "")).encode("utf-8"))
        command = ": #" + "x" * (request.MAX_SERVICE_BYTES - overhead - 3)
        response = types.SimpleNamespace(returncode=97,
            stdout="fixture payload\nWRAPPER_RC_WRAPPED=0\nDONE_REMOTE_WRAPPED\n")
        with mock.patch.object(preflight.subprocess, "run", return_value=response) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(obj.remote(label, command), "fixture payload")
            self.assertEqual(run.call_args.args[0][-1], request.framed(label, command))
            self.assertEqual(request.check_request(run.call_args.args[0][-1]), request.MAX_SERVICE_BYTES)
        for extra in ("x", "中"):
            with self.subTest(extra=extra), mock.patch.object(preflight.subprocess, "run") as run, \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, "not sent"):
                    obj.remote(label, command + extra)
                run.assert_not_called()
        with mock.patch.object(preflight.subprocess, "run",
                               return_value=types.SimpleNamespace(returncode=0, stdout="host success only\n")):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "RC/DONE gate"):
                obj.remote(label, "true")

    def test_residue_batching_preserves_utf8_paths_order_and_label_offsets(self):
        paths = ["/fixture/目录/%04d_" % n + "é" * 80 for n in range(80)]
        batches = request.residue_batches(paths)
        self.assertGreater(len(batches), 1)
        flattened, offset = [], 0
        for label, command in batches:
            selected = batch_paths(command)
            self.assertEqual(label, "PACKAGE_RESIDUE_%04d" % offset)
            self.assertLessEqual(request.check_request(request.framed(label, command)), request.MAX_SERVICE_BYTES)
            flattened.extend(selected)
            offset += len(selected)
        self.assertEqual(flattened, paths)

    def test_single_path_exact_limit_and_next_byte_rejected(self):
        label = "PACKAGE_RESIDUE_0000"
        overhead = request.check_request(request.framed(label, request.residue_command(["/x"])))
        exact = "/x" + "a" * (request.MAX_SERVICE_BYTES - overhead)
        batches = request.residue_batches([exact])
        self.assertEqual(len(batches), 1)
        self.assertEqual(request.check_request(request.framed(*batches[0])), request.MAX_SERVICE_BYTES)
        with self.assertRaisesRegex(ValueError, "not sent"):
            request.residue_batches([exact + "a"])

    def test_late_invalid_or_oversize_path_refuses_entire_batch_list_before_send(self):
        prefix = ["/fixture/%03d_" % n + "a" * 100 for n in range(70)]
        for bad in ("/" + "b" * request.MAX_SERVICE_BYTES, "/invalid\nname", "../escape"):
            with self.subTest(bad=bad[:35]):
                send = mock.Mock()
                with self.assertRaises(ValueError):
                    for label, command in request.residue_batches(prefix + [bad]):
                        send(label, command)
                send.assert_not_called()

    def test_cleanup_preflights_all_paths_before_any_residue_request(self):
        obj = object.__new__(resume.G4Resume)
        obj.created = True
        obj.receipt = {}
        obj.packages_before = ["glibc 2.40-1.6.armv7l"]
        obj.package_paths = ["/fixture/good"] * 500 + ["/" + "x" * request.MAX_SERVICE_BYTES]
        with mock.patch.object(resume.Executor, "cleanup", return_value="PASS"), \
             mock.patch.object(obj, "inventory", return_value=obj.packages_before), \
             mock.patch.object(obj, "remote") as remote, \
             mock.patch.object(obj, "round_snapshot") as snapshot:
            self.assertEqual(obj.cleanup(), "FAIL")
            remote.assert_not_called()
            snapshot.assert_not_called()
        self.assertTrue(any("not sent" in reason for reason in obj.receipt["cleanup_problems"]))

    def test_invalid_package_paths_and_empty_command_are_rejected(self):
        for path in ("relative", "/", "/tmp/../escape", "/tmp/a\nline", "/tmp/a\rline",
                     "/tmp/tab\tname", "/tmp/nul\0name"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                request.residue_command([path])
        with self.assertRaisesRegex(ValueError, "empty residue batch"):
            request.residue_command([])
        self.assertEqual(request.residue_batches([]), [])

    def test_special_quote_paths_are_literal_with_no_shell_reinterpretation(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional literal-path shell integration requires executable sh")
        files = [self.root / name for name in ("space name", "single'quote", 'double"quote',
                 "$(printf INJECTED)", "`printf INJECTED`", "semi;colon", "中文路径", "back\\slash")]
        for path in files:
            path.write_text("host fixture only\n")
        paths = [str(path) for path in files]
        command = request.residue_command(paths)
        self.assertEqual(batch_paths(command), paths)
        # Real shell execution is confined to this private temp tree. stat is
        # a shell double, and the source command is read-only against fixtures.
        program = 'stat() { printf "regular file\\n"; }\n' + request.framed("QUOTES", command)
        result = subprocess.run([shell, "-c", program], cwd=self.root, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "".join(path + "\tregular file\n" for path in paths)
        expected += "\nWRAPPER_RC_QUOTES=0\nDONE_REMOTE_QUOTES\n"
        self.assertEqual(result.stdout, expected)

    def test_unsearchable_parent_is_reported_not_silently_absent(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("optional deterministic permission-injection fixture requires executable sh")
        blocked = self.root / "permission-denied-parent"
        blocked.mkdir()
        path = str(blocked / "nested" / "missing-file")
        command = request.residue_command([path])
        # Deterministic stat double, including genuine POSIX-style errno text:
        # root CI users cannot reliably create EACCES with directory mode bits.
        # The producer itself must distinguish EACCES from explicit ENOENT.
        prelude = r'''
diagnostic=$1
stat_rc=$2
stat() {
    printf 'stat: cannot stat %s: %s\n' "$3" "$diagnostic" >&2
    return "$stat_rc"
}
'''
        for diagnostic, stat_rc, absent in (
            ("Permission denied", "1", False),
            ("Operation not permitted", "1", False),
            ("No such file or directory", "1", True),
            ("No such file or directory", "9", False),
            ("unexpected stat implementation failure", "1", False),
        ):
            with self.subTest(diagnostic=diagnostic, stat_rc=stat_rc):
                result = subprocess.run([shell, "-c", prelude + request.framed("PERMISSION", command),
                                         "permission-fixture", diagnostic, stat_rc],
                                        cwd=self.root, text=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, timeout=5)
                # Framing intentionally prints the board RC; callers never use
                # the shell's last-echo exit status as proof of success.
                self.assertEqual(result.returncode, 0, result.stderr)
                if not absent:
                    self.assertIn("STAT_ERROR", result.stdout)
                    self.assertIn(path, result.stdout)
                    self.assertIn(diagnostic, result.stdout)
                    self.assertIn("WRAPPER_RC_PERMISSION=1", result.stdout)
                    self.assertIn("FAIL_REMOTE_PERMISSION", result.stdout)
                    self.assertNotIn("DONE_REMOTE_PERMISSION", result.stdout)
                else:
                    self.assertIn("WRAPPER_RC_PERMISSION=0", result.stdout)
                    self.assertIn("DONE_REMOTE_PERMISSION", result.stdout)

    def test_published_11800_byte_failure_is_split_without_omission(self):
        recorded = ROOT / "data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/commands.json"
        commands = json.loads(recorded.read_text())
        item = next(row for row in commands if row["label"] == "PACKAGE_RESIDUE_0000")
        original = item["argv"][-1]
        self.assertEqual(len(original.encode("utf-8")), 11800)
        self.assertTrue(original.startswith("( for p in "))
        paths = batch_paths(original[2:])
        self.assertEqual(len(paths), 200)
        with self.assertRaisesRegex(ValueError, "not sent"):
            request.check_request(original)
        batches = request.residue_batches(paths)
        self.assertGreater(len(batches), 1)
        self.assertEqual([path for _, command in batches for path in batch_paths(command)], paths)
        for label, command in batches:
            with self.subTest(label=label):
                self.assertLessEqual(request.check_request(request.framed(label, command)), request.MAX_SERVICE_BYTES)


if __name__ == "__main__":
    unittest.main()
