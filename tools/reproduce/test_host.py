#!/usr/bin/env python3
"""Host tests for the Demo acceptance and link workflow helpers."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
import zipfile
import csv
import fcntl
import importlib.util
from unittest.mock import patch
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVALUATOR = HERE / "evaluate_acceptance.py"
BANDS = HERE / "acceptance_bands.json"
STABILITY = HERE / "stability_monitor.py"
STARTUP_CONTEXTS = ("self-clear", "unexported-only", "self-delete", "preset-marker", "preset-empty-marker")
REJECTION_FUNCTIONS = (
    ("exec",), ("exit",), ("exec", "exit"), ("builtin",),
    ("builtin", "exec", "exit"),
    ("builtin", "readonly", "exec", "exit", "command", "declare", "compgen", "set", "export", ":"),
)
REJECTION_CONTEXTS = (*STARTUP_CONTEXTS, "self-delete-preset-marker")
STARTUP_REJECTION_CHECKS = len(STARTUP_CONTEXTS) + len(REJECTION_FUNCTIONS) * len(REJECTION_CONTEXTS) + 2


class ReproduceTests(unittest.TestCase):
    def test_current_tree_private_endpoints_and_scanner_regressions(self) -> None:
        # A hard host-test gate; not tied to optional GBS/RPM or a delivery tag.
        # Keep the existing entrypoint/provenance bytes unchanged.
        result = subprocess.run([sys.executable, str(REPO / 'tools/privacy/scan_endpoints.py'),
                                 '--repo-root', str(REPO), '--json'],
                                cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['count'], 0)
        tests = subprocess.run([sys.executable, '-m', 'unittest', 'tools.privacy.test_endpoints'],
                               cwd=REPO, capture_output=True, text=True)
        self.assertEqual(tests.returncode, 0, tests.stdout + tests.stderr)

    def _install_unexpected_command_stubs(
        self,
        directory: Path,
        commands: tuple[str, ...],
        marker: Path,
    ) -> None:
        """Make optional tools discoverable without borrowing host packages."""
        for command in commands:
            stub = directory / command
            stub.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' {command!r} >> {str(marker)!r}\n"
                "exit 97\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

    def _clone_current_head(self, source: Path, destination: Path) -> str:
        source_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=source, check=True,
            text=True, capture_output=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "clone", "--no-tags", "--no-checkout", str(source), str(destination)],
            check=True, capture_output=True,
        )
        # Fetch the exact source commit so this fixture also works when source
        # HEAD is detached and is not named by any local branch.
        subprocess.run(
            ["git", "fetch", "--quiet", "--no-tags", str(source), source_head],
            cwd=destination, check=True, capture_output=True,
        )
        return source_head

    def _materialize_repository_shape(self, root: Path, shape: str) -> Path:
        if shape == "tag":
            seed = root / "tag-seed"
            source_head = self._clone_current_head(REPO, seed)
            subprocess.run(
                ["git", "checkout", "--quiet", "-B", "main", source_head],
                cwd=seed, check=True,
            )
            subprocess.run(
                ["git", "tag", "fixture-delivery-tag", source_head], cwd=seed, check=True,
            )
            checkout = root / "tag"
            subprocess.run(
                ["git", "clone", "--quiet", "--branch", "fixture-delivery-tag", str(seed), str(checkout)],
                check=True, capture_output=True,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "branch", "--show-current"], cwd=checkout, check=True,
                    text=True, capture_output=True,
                ).stdout.strip(),
                "",
            )
            return checkout

        checkout = root / shape
        source_head = self._clone_current_head(REPO, checkout)
        subprocess.run(
            ["git", "checkout", "--quiet", "-B", shape, source_head],
            cwd=checkout, check=True,
        )
        return checkout

    def _run_delivery_identity_clone(
        self,
        branch: str,
        include_delivery_tag: bool,
        source_repo: Path = REPO,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clone = root / "clone"
            source_head = self._clone_current_head(source_repo, clone)
            subprocess.run(
                ["git", "checkout", "--quiet", "-B", branch, source_head],
                cwd=clone, check=True,
            )
            if include_delivery_tag:
                refs = json.loads(
                    (clone / "tools/reproduce/delivery_refs.json").read_text(encoding="utf-8")
                )
                delivery_ref = refs["branch_refs"][branch]["ref"]
                subprocess.run(
                    ["git", "tag", delivery_ref, source_head], cwd=clone, check=True,
                )

            command_dir = root / "bin"
            command_dir.mkdir()
            for command in (HERE / "verify_commands.txt").read_text().split():
                executable = shutil.which(command)
                self.assertIsNotNone(executable, command)
                (command_dir / command).symlink_to(executable)
            env = {**os.environ, "PATH": str(command_dir), "REPRODUCE_SKIP_TESTS": "1"}
            env.pop("REPRODUCE_EXPECTED_SHA", None)
            return subprocess.run(
                ["bash", "tools/reproduce/reproduce.sh", "verify"],
                cwd=clone, env=env, text=True, capture_output=True, check=False,
            )

    def test_verify_entrypoint_passes(self) -> None:
        env = os.environ.copy()
        env["REPRODUCE_ALLOW_DIRTY"] = "1"
        env["REPRODUCE_SKIP_TESTS"] = "1"
        env["REPRODUCE_EXPECTED_SHA"] = "HEAD"
        result = subprocess.run(
            ["bash", str(HERE / "reproduce.sh"), "verify"],
            cwd=REPO, env=env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("OVERALL\tPASS", result.stdout)
        self.assertIn("REGISTERED/NOT-EVALUATED\tstability-monitor", result.stdout)
        self.assertIn("INFO\ttemplate-entry-links\ttemplates rendered at repository root", result.stdout)

    def test_predelivery_check_help_lists_all_hq_clone_shapes(self) -> None:
        result = subprocess.run(
            ["bash", str(HERE / "predelivery_check.sh"), "--help"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git clone --branch demo <url>", result.stdout)
        self.assertIn("git clone --branch <delivery-tag> <url>", result.stdout)
        self.assertIn("git clone <url>  (must check out main)", result.stdout)
        self.assertIn("3 clone shapes x 6 environment profiles = 18", result.stdout)
        self.assertIn("present-gbs+absent-rpm", result.stdout)
        self.assertIn("minimal-whitelist", result.stdout)
        self.assertIn("broken-tools", result.stdout)
        self.assertIn("startup-injection", result.stdout)

    def test_default_host_test_dependency_audit_covers_inventory(self) -> None:
        entrypoint = (HERE / "reproduce.sh").read_text(encoding="utf-8")
        start = entrypoint.index("host_tests()\n")
        end = entrypoint.index("\n)\n", start)
        modules = re.findall(r"^\s+(tools/\S+\.py)(?:\s+\\)?$", entrypoint[start:end], re.MULTILINE)
        self.assertEqual(len(modules), 13, modules)
        documentation = (HERE / "README.md").read_text(encoding="utf-8")
        for module in modules:
            with self.subTest(module=module):
                self.assertIn(f"`{module}`", documentation)

    def test_board_entrypoint_help_is_host_only(self) -> None:
        result = subprocess.run(
            ["bash", str(HERE / "reproduce.sh"), "board", "--help"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--ip <address>", result.stdout)
        self.assertIn("default SHA source is the GBS build", result.stdout)

    def test_default_verify_never_invokes_available_gbs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            marker = root / "gbs-was-run"
            fake_gbs = fake_bin / "gbs"
            fake_gbs.write_text(
                f"#!/bin/sh\nprintf invoked > {marker}\nexit 42\n", encoding="utf-8",
            )
            fake_gbs.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "REPRODUCE_ALLOW_DIRTY": "1",
                "REPRODUCE_SKIP_TESTS": "1",
                "REPRODUCE_EXPECTED_SHA": "HEAD",
            }
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "verify"], cwd=REPO, env=env,
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(marker.exists(), result.stdout)
            self.assertIn("SKIPPED\tgbs-build\treal GBS build is excluded", result.stdout)
            self.assertIn("OVERALL\tPASS", result.stdout)

    def test_explicit_gbs_environment_failure_is_not_evaluated_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, env = self._gbs_artifact_fixture(root)
            fake_bin = root / "bin"
            fake_gbs = fake_bin / "gbs"
            fake_gbs.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$2\" >> \"$FAKE_GBS_LOG\"\n"
                "while IFS= read -r line; do\n"
                "  case \"$line\" in buildroot=*) printf '%s\\n' \"$line\" >> \"$FAKE_GBS_LOG\";; esac\n"
                "done < \"$2\"\n"
                "echo fixture-gbs-failure\nexit 42\n",
                encoding="utf-8",
            )
            fake_gbs.chmod(0o755)
            unexpected_tools = root / "unexpected-rpm-tool-invocation"
            self._install_unexpected_command_stubs(
                fake_bin, ("rpm", "rpm2cpio", "cpio"), unexpected_tools,
            )
            env = {
                **env,
                "GLIBC_MEMOPT_GBS_LOCK": str(root / "gbs.lock"),
                "FAKE_GBS_LOG": str(root / "gbs.log"),
            }
            results = [
                subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--lock-timeout", "1"],
                    cwd=REPO, env=env, text=True, capture_output=True, check=False,
                )
                for _ in range(2)
            ]
            for result in results:
                self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("NOT-EVALUATED\tgbs-build-unknown\tgbs build returned RC=42", result.stdout)
                self.assertIn("OVERALL\tFAIL", result.stdout)
            rows = (root / "gbs.log").read_text(encoding="utf-8").splitlines()
            configs = rows[0::2]
            buildroots = rows[1::2]
            self.assertEqual(len(configs), 2)
            self.assertNotEqual(configs[0], configs[1])
            self.assertTrue(all("/tmp/glibc-memopt-gbs-" in item for item in configs))
            self.assertNotEqual(buildroots[0], buildroots[1])
            self.assertFalse(unexpected_tools.exists())

    def test_explicit_gbs_occupied_lock_is_not_evaluated_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_gbs = fake_bin / "gbs"
            fake_gbs.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
            fake_gbs.chmod(0o755)
            unexpected_tools = root / "unexpected-rpm-tool-invocation"
            self._install_unexpected_command_stubs(
                fake_bin, ("rpm", "rpm2cpio", "cpio"), unexpected_tools,
            )
            lock_path = root / "gbs.lock"
            with lock_path.open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                env = {
                    **os.environ,
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                    "GLIBC_MEMOPT_GBS_LOCK": str(lock_path),
                }
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--lock-timeout", "0"],
                    cwd=REPO, env=env, text=True, capture_output=True, check=False,
                )
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("WAITING\tgbs-build-lock", result.stdout)
            self.assertIn("NOT-EVALUATED\tgbs-build-environment", result.stdout)
            self.assertIn("OVERALL\tFAIL", result.stdout)
            self.assertIn("remained occupied", result.stdout)
            self.assertFalse(unexpected_tools.exists())

    def _gbs_artifact_fixture(self, root: Path) -> tuple[Path, dict]:
        """Exercise the CLI, extraction and hash gates with no host RPM dependency."""
        repo = root / "repo"
        for name in ("packaging/glibc-memopt-tools.spec", "config/gbs_llvm.conf", "config/gbs.conf",
                     "tools/reproduce/reproduce.sh", "tools/reproduce/check_gbs_package.py",
                     "tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py",
                     "tools/reproduce/deliverables_manifest.json", "tools/alloc_bench/alloc_bench.c",
                     "tools/gst_loop_decode/gst_loop_decode.c", "tools/reclaim_probe/reclaim_probe.c"):
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, target)
        manifest_path = repo / "tools/reproduce/deliverables_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for item in manifest["artifacts"]:
            if item["name"].endswith(".armv7l"):
                installed = item["name"].removesuffix(".armv7l")
                item["gbs_build_sha256"] = hashlib.sha256(("fixture-" + installed).encode()).hexdigest()
        manifest["gbs_build"]["rpm_sha256"] = hashlib.sha256(b"fixture-rpm").hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        (repo / ".gitignore").write_text("__pycache__/\n")
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "clean build fixture"], cwd=repo, check=True, capture_output=True)
        commands = root / "bin"
        commands.mkdir()
        for command in ("bash", "dirname", "python3", "git"):
            (commands / command).symlink_to(shutil.which(command))
        stub = '''import os, pathlib, re, sys
name = pathlib.Path(sys.argv[0]).name
fault = os.environ.get("FIXTURE_GBS_FAULT", "")
names = ("alloc_bench", "gst_loop_decode", "reclaim_probe")
if name == "gbs":
    import json
    proof_path = pathlib.Path(sys.argv[2]).parent / "execution_provenance.json"
    proof = json.loads(proof_path.read_text())
    assert proof["dirty"] is False and proof["workflow_commit"]
    if fault == "proof-rewrite":
        proof["python_version"] = "rewritten"
        proof_path.write_text(json.dumps(proof))
    elif fault == "proof-truncate":
        proof_path.write_bytes(b"{")
    elif fault == "proof-delete":
        proof_path.unlink()
    elif fault == "proof-symlink":
        replacement = proof_path.with_suffix(".copy")
        replacement.write_bytes(proof_path.read_bytes())
        proof_path.unlink()
        proof_path.symlink_to(replacement)
    if fault == "source-error":
        print("tools/alloc_bench/alloc_bench.c:12:3: error: expected expression")
        sys.exit(1)
    if fault == "missing-header":
        print("tools/alloc_bench/alloc_bench.c:12:3: fatal error: 'missing.h' file not found")
        sys.exit(1)
    sys.stdout.buffer.write(b"fixture raw stdout\\r\\n")
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(b"fixture raw stderr\\n")
    config = pathlib.Path(sys.argv[2]).read_text()
    buildroot = pathlib.Path(re.search(r"^buildroot=(.+)$", config, re.M).group(1))
    if fault != "missing-rpm":
        rpm = buildroot / "local/repos/tizen_unified_standard/armv7l/RPMS/glibc-memopt-tools-1.0.0-1.armv7l.rpm"
        rpm.parent.mkdir(parents=True)
        rpm.write_bytes(b"fixture-rpm")
elif name == "rpm":
    if fault == "broken-rpm":
        print("rpm shared library unavailable", file=sys.stderr)
        sys.exit(127)
    if "-qpl" in sys.argv:
        print("\\n".join("/usr/bin/" + n for n in names))
    else:
        print("glibc-memopt-tools-1.0.0-1\\narmv7l")
elif name == "rpm2cpio":
    if fault == "broken-rpm2cpio":
        sys.exit(42)
    sys.stdout.buffer.write(b"fixture-stream")
elif name == "cpio":
    sys.stdin.buffer.read()
    if fault == "broken-cpio":
        sys.exit(42)
    target = pathlib.Path("usr/bin")
    target.mkdir(parents=True)
    for n in names:
        if fault == "missing-" + n:
            continue
        payload = "drift" if fault == "sha-drift" else "fixture-" + n
        (target / n).write_bytes(payload.encode())
'''
        for name in ("gbs", "rpm", "rpm2cpio", "cpio"):
            target = commands / name
            target.write_text(f"#!{sys.executable}\n" + stub)
            target.chmod(0o755)
        return repo, {**os.environ, "PATH": str(commands), "GLIBC_MEMOPT_GBS_LOCK": str(root / "lock")}

    def test_build_time_proof_attacks_are_hard_failures(self) -> None:
        for fault in ("proof-rewrite", "proof-truncate", "proof-delete", "proof-symlink"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, env = self._gbs_artifact_fixture(root)
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo),
                     "--output-dir", str(root / "bundle")],
                    env={**env, "FIXTURE_GBS_FAULT": fault}, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("proof rewritten during build", result.stdout)
                self.assertNotIn("OVERALL\tPASS", result.stdout)
                self.assertFalse((root / "bundle/gbs_build_summary.json").exists())

    def test_output_proof_attacks_fail_checker_and_publisher(self) -> None:
        # Deterministic fault injection at the copy boundary, without timing races.
        for phase in ("checker", "publisher"):
            for attack in ("rewrite", "truncate", "delete", "symlink"):
                with self.subTest(phase=phase, attack=attack), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    repo, env = self._gbs_artifact_fixture(root)
                    module_path = repo / "tools/reproduce/check_gbs_package.py"
                    if phase == "publisher":
                        module_path = repo / "tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py"
                    spec = importlib.util.spec_from_file_location("copy_fault_fixture", module_path)
                    module = importlib.util.module_from_spec(spec)
                    # The publisher imports its own committed fixture checker.
                    with patch.dict(sys.modules), patch.object(sys, "path", list(sys.path)):
                        sys.modules.pop("check_gbs_package", None)
                        spec.loader.exec_module(module)
                    bundle = root / "bundle"
                    output = bundle if phase == "checker" else root / "public"
                    argv = [str(module_path), "--repo-root", str(repo), "--build", "--output-dir", str(output)]
                    if phase == "publisher":
                        built = subprocess.run(["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo),
                                                "--output-dir", str(bundle)], env=env, text=True, capture_output=True)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        log = root / "run.log"
                        log.write_text(built.stdout)
                        argv = [str(module_path), "--bundle", str(bundle), "--log", str(log), "--output", str(output)]
                    original = shutil.copyfile

                    def rewrite_copy(source, destination, *args, **kwargs):
                        result = original(source, destination, *args, **kwargs)
                        target = Path(destination)
                        if target == output / "execution_provenance.json":
                            if attack == "rewrite":
                                target.write_bytes(target.read_bytes() + b" ")
                            elif attack == "truncate":
                                target.write_bytes(b"{")
                            elif attack == "delete":
                                target.unlink()
                            else:
                                target.unlink()
                                target.symlink_to(source)
                        return result

                    with patch.dict(os.environ, env, clear=True), patch.object(sys, "argv", argv), \
                            patch.object(module.shutil, "copyfile", side_effect=rewrite_copy), patch("builtins.print") as printed:
                        if phase == "checker":
                            self.assertEqual(module.main(), 1)
                            self.assertFalse((output / "gbs_build_summary.json").exists())
                        else:
                            with self.assertRaisesRegex(ValueError, "published proof rewritten"):
                                module.main()
                        self.assertTrue(any("proof" in str(call) for call in printed.call_args_list) or phase == "publisher")

    def test_skip_worktree_build_input_mutation_is_rejected(self) -> None:
        for relative in ("config/gbs_llvm.conf", "config/gbs.conf",
                         "tools/reproduce/deliverables_manifest.json", "packaging/glibc-memopt-tools.spec"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, env = self._gbs_artifact_fixture(root)
                subprocess.run(["git", "update-index", "--skip-worktree", relative], cwd=repo, check=True)
                target = repo / relative
                target.write_bytes(target.read_bytes() + b"\n")  # Still syntactically valid.
                self.assertEqual(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo), b"")
                result = subprocess.run(["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo),
                                         "--output-dir", str(root / "bundle")], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("snapshot/commit bytes mismatch: " + relative, result.stdout)
                self.assertNotIn("INFO\tgbs-command", result.stdout)

    def test_missing_header_needs_manual_judgment_and_priority_is_explicit(self) -> None:
        spec = importlib.util.spec_from_file_location("classify_fixture", HERE / "check_gbs_package.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        header = "tools/a.c:12:3: fatal error: 'missing.h' file not found"
        with self.assertRaisesRegex(module.GbsCauseUnknown, "unknown cause: missing header; manual second judgment"):
            module.classify_gbs_failure(1, header)
        with self.assertRaisesRegex(module.GbsEnvironmentUnavailable, "environment diagnostic: No space left"):
            module.classify_gbs_failure(1, header + "\nNo space left on device")
        with self.assertRaisesRegex(ValueError, "source compilation defect"):
            module.classify_gbs_failure(1, "tools/a.c:12:3: error: expected expression")

    def test_exported_command_and_target_functions_cannot_bypass_preflight(self) -> None:
        for target in ("dirname", "python3", "awk"):
            with self.subTest(target=target):
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "verify"],
                    env={**os.environ, "BASH_FUNC_command%%": '() { printf "/usr/bin/%s\\n" "$2"; }',
                         "BASH_FUNC_" + target + "%%": "() { :; }"},
                    text=True, capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("BASH_FUNC_command", result.stderr)
                self.assertIn("BASH_FUNC_" + target, result.stderr)
                self.assertNotIn("MODE\thost verify", result.stdout)

    def test_startup_self_clearing_unexported_functions_fail_before_mode(self) -> None:
        for variant in STARTUP_CONTEXTS:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                init = Path(directory) / "init.sh"
                called = Path(directory) / "spoof-called"
                body = ("python3() { printf called >> " + shlex.quote(str(called)) + "; };\n"
                        "cmp() { printf called >> " + shlex.quote(str(called)) + "; }\n")
                if variant == "self-delete":
                    body += shlex.quote(sys.executable) + " -c 'import os; os.unlink(os.environ[\"BASH_ENV\"])'\n"
                body += "unset BASH_ENV ENV\n"
                init.write_text(body)
                env = {**os.environ, "REPRODUCE_ALLOW_DIRTY": "1", "REPRODUCE_SKIP_TESTS": "1"}
                argv = ["bash", str(HERE / "reproduce.sh"), "verify"]
                if variant == "unexported-only":
                    argv = ["bash", "--noprofile", "--norc", "-c", body + '\n. "$0" verify', str(HERE / "reproduce.sh")]
                elif variant.startswith("preset-"):
                    env["REPRODUCE_SANITIZED_ENTRYPOINT"] = "fixture" if variant == "preset-marker" else ""
                else:
                    env["BASH_ENV"] = str(init)
                result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=30)
                self._assert_explicit_injection_rejection(result)
                self.assertFalse(called.exists(), "spoofed command was invoked")
                self.assertNotIn("missing default-verify command", result.stderr)
                if variant == "self-delete":
                    self.assertFalse(init.exists())

    def test_bootstrap_cannot_fall_through_to_unclean_workflow_body(self) -> None:
        for functions in REJECTION_FUNCTIONS:
            for context in REJECTION_CONTEXTS:
                with self.subTest(functions=functions, context=context), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    init, called = root / "init.sh", root / "spoof-called"
                    body = "\n".join(name + "() { printf '%s\\n' " + shlex.quote(name) + " >> " +
                                     shlex.quote(str(called)) + "; }" for name in (*functions, "python3", "cmp")) + "\n"
                    if context.startswith("self-delete"):
                        body += shlex.quote(sys.executable) + " -c 'import os; os.unlink(os.environ[\"BASH_ENV\"])'\n"
                    body += "unset BASH_ENV ENV\n"
                    init.write_text(body)
                    env = {**os.environ, "REPRODUCE_ALLOW_DIRTY": "1", "REPRODUCE_SKIP_TESTS": "1"}
                    argv = ["bash", str(HERE / "reproduce.sh"), "verify"]
                    if context == "unexported-only":
                        argv = ["bash", "--noprofile", "--norc", "-c", body + '\n. "$0" verify', str(HERE / "reproduce.sh")]
                    else:
                        env["BASH_ENV"] = str(init)
                    if "preset" in context:
                        env["REPRODUCE_SANITIZED_ENTRYPOINT"] = "" if context == "preset-empty-marker" else "fixture"
                    result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=10)
                    self._assert_explicit_injection_rejection(result)
                    self.assertFalse(called.exists(), "spoofed command was invoked")
                    if context.startswith("self-delete"):
                        self.assertFalse(init.exists())

    def _assert_explicit_injection_rejection(self, result: subprocess.CompletedProcess) -> None:
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 2, output)
        self.assertTrue(output.strip(), "silent rejection is an automation false success")
        self.assertIn("FAIL\truntime-injection\t", output)
        self.assertNotIn("MODE\thost verify", output)
        self.assertNotIn("OVERALL\tPASS", output)

    def test_unavailable_function_enumeration_fails_closed(self) -> None:
        for disabled in ("builtin", "declare"):
            with self.subTest(disabled=disabled), tempfile.TemporaryDirectory() as directory:
                called = Path(directory) / "spoof-called"
                body = "enable -n " + disabled + "; python3() { printf called >> " + shlex.quote(str(called)) + "; }; "
                result = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-c",
                     body + '. "$0" verify', str(HERE / "reproduce.sh")],
                    env={**os.environ, "REPRODUCE_ALLOW_DIRTY": "1", "REPRODUCE_SKIP_TESTS": "1"},
                    text=True, capture_output=True, timeout=10,
                )
                self._assert_explicit_injection_rejection(result)
                self.assertIn("enumeration", result.stderr)
                self.assertFalse(called.exists())

    def test_unrelated_module_function_has_actionable_clean_process_workaround(self) -> None:
        env = {**os.environ, "BASH_FUNC_module%%": "() { :; }", "REPRODUCE_ALLOW_DIRTY": "1", "REPRODUCE_SKIP_TESTS": "1"}
        rejected = subprocess.run(["bash", str(HERE / "reproduce.sh"), "verify"], env=env,
                                  text=True, capture_output=True, timeout=10)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("runtime-injection", rejected.stderr)
        self.assertIn("module", rejected.stderr)
        self.assertNotIn("missing default-verify command", rejected.stderr)
        # Same environment semantics as the documented env -i command. Using a
        # subprocess environment avoids making env an extra verify prerequisite.
        clean = {name: env[name] for name in ("PATH", "HOME", "REPRODUCE_ALLOW_DIRTY", "REPRODUCE_SKIP_TESTS") if name in env}
        # This is an environment-cleaning test, not the separate delivery-ref
        # test. It must also run before a future delivery tag has been created.
        clean["REPRODUCE_EXPECTED_SHA"] = "HEAD"
        accepted = subprocess.run(["bash", "--noprofile", "--norc", "-p", str(HERE / "reproduce.sh"), "verify"],
                                  env=clean, text=True, capture_output=True, timeout=30)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn("MODE\thost verify", accepted.stdout)
        self.assertIn("OVERALL\tPASS", accepted.stdout)

    def test_recursive_entrypoint_is_refused_before_any_child_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            # A nonempty marker must stop even with no commands available.
            result = subprocess.run(
                [shutil.which("bash"), str(HERE / "reproduce.sh"), "verify"],
                env={**os.environ, "PATH": directory, "REPRODUCE_ACTIVE_ENTRYPOINT": "fixture-parent"},
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("runtime-recursion", result.stderr)
            self.assertIn("OVERALL\tFAIL", result.stderr)
            self.assertNotIn("python-runtime", result.stdout)
            # An accidental python3 -> entrypoint link is detected by file
            # identity before invocation; system Python only diagnoses refusal.
            (Path(directory) / "python3").symlink_to(HERE / "reproduce.sh")
            env = {**os.environ, "PATH": directory}
            env.pop("REPRODUCE_ACTIVE_ENTRYPOINT", None)
            recursive = subprocess.run(
                [shutil.which("bash"), str(HERE / "reproduce.sh"), "verify"],
                env=env, capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(recursive.returncode, 2)
            self.assertEqual(recursive.stderr.count("runtime-recursion"), 1)

    def test_explicit_gbs_success_persists_rpm_and_all_elf_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, env = self._gbs_artifact_fixture(root)
            output = root / "bundle"
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(output)],
                env=env, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OVERALL\tPASS", result.stdout)
            record = json.loads((output / "gbs_build_summary.json").read_text())
            self.assertEqual(len(record["elf_sha256"]), 3)
            for name, expected in record["elf_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)
            self.assertEqual(record["rpm"]["sha256"], record["rpm"]["recorded_sha256"])
            self.assertTrue((output / "glibc-memopt-tools-1.0.0-1.armv7l.rpm").is_file())
            self.assertIsNone(record["buildroot_residue"])
            provenance = json.loads((output / "execution_provenance.json").read_text())
            self.assertFalse(provenance["dirty"])
            self.assertEqual(provenance["git_status_porcelain"], "")
            self.assertEqual(provenance["schema"], "glibc-memopt-gbs-execution.v2")
            self.assertEqual(record["gbs_log_sha256"], hashlib.sha256((output / "gbs.log").read_bytes()).hexdigest())
            self.assertEqual((output / "gbs.log").read_bytes(), b"fixture raw stdout\r\nfixture raw stderr\n")
            self.assertEqual(len(provenance["committed_file_sha256"]), 6)
            for path, expected in provenance["committed_file_sha256"].items():
                contents = subprocess.check_output(["git", "show", provenance["workflow_commit"] + ":" + path], cwd=repo)
                self.assertEqual(hashlib.sha256(contents).hexdigest(), expected)
            for field, path in (("entrypoint_sha256", "tools/reproduce/reproduce.sh"),
                                ("checker_sha256", "tools/reproduce/check_gbs_package.py")):
                committed = subprocess.check_output(["git", "show", provenance["workflow_commit"] + ":" + path], cwd=repo)
                self.assertEqual(hashlib.sha256(committed).hexdigest(), provenance[field])
                self.assertEqual(record[field], provenance[field])
            self.assertLessEqual(provenance["captured_utc"], record["finished_utc"])

    def test_gbs_provenance_dirty_execution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, env = self._gbs_artifact_fixture(root)
            (repo / "uncommitted-note").write_text("dirty")
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(root / "bundle")],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("dirty execution snapshot", result.stdout)
            self.assertIn("FAIL\tgbs-dirty-snapshot", result.stdout)
            self.assertNotIn("INFO\tgbs-command", result.stdout)
            self.assertFalse((root / "bundle").exists())

    def test_historical_v8_gbs_execution_proof_matches_its_recorded_git_objects(self) -> None:
        archive = REPO / "data/raw/demo_v7_delivery_20260907/gbs"
        proof_path = archive / "execution_provenance.json"
        proof = json.loads(proof_path.read_text())
        record = json.loads((archive / "build_summary.json").read_text())
        self.assertEqual(proof["schema"], "glibc-memopt-gbs-execution.v1")
        self.assertIs(proof["dirty"], False)
        self.assertEqual(proof["git_status_porcelain"], "")
        self.assertEqual(record["provenance_sha256"], hashlib.sha256(proof_path.read_bytes()).hexdigest())
        self.assertEqual(record["workflow_commit"], proof["workflow_commit"])
        self.assertEqual(record["verdict"], "PASS")
        for field, relative in (("entrypoint_sha256", "tools/reproduce/reproduce.sh"),
                                ("checker_sha256", "tools/reproduce/check_gbs_package.py")):
            committed = subprocess.check_output(["git", "show", proof["workflow_commit"] + ":" + relative], cwd=REPO)
            digest = hashlib.sha256(committed).hexdigest()
            self.assertEqual(proof[field], digest, field)
            self.assertEqual(record[field], digest, field)
            # Immutable v8 evidence binds its execution commit, not v9 bytes.
            # Do not introduce a dependency on fetching a historical demo tag.
        self.assertLessEqual(record["started_utc"], proof["captured_utc"])
        self.assertLessEqual(proof["captured_utc"], record["finished_utc"])
        self.assertRegex(proof["python_version"], r"^3\.\d+\.\d+$")
        self.assertIn("superseded", (archive / "README.md").read_text())

    def test_historical_v9_public_execution_proof_matches_execution_commit(self) -> None:
        self._check_public_execution_proof("demo_v9_delivery_20260907", current=False)

    def test_historical_v10_public_execution_proof_matches_execution_commit(self) -> None:
        self._check_public_execution_proof("demo_v10_delivery_20260908", current=False)

    def test_historical_v11_public_execution_proof_matches_execution_commit(self) -> None:
        self._check_public_execution_proof("demo_v11_delivery_20260908", current=False)

    def test_candidate_v12_public_execution_proof_matches_commit_and_current_files(self) -> None:
        self._check_public_execution_proof("demo_v12_delivery_20260911", current=True)

    def _check_public_execution_proof(self, directory: str, *, current: bool) -> None:
        archive = REPO / "data/raw" / directory / "gbs"
        proof_path = archive / "execution_provenance.json"
        proof = json.loads(proof_path.read_text())
        record = json.loads((archive / "build_summary.json").read_text())
        self.assertEqual(proof["schema"], "glibc-memopt-gbs-execution.v2")
        self.assertIs(proof["dirty"], False)
        self.assertEqual(proof["git_status_porcelain"], "")
        self.assertEqual(record["workflow_commit"], proof["workflow_commit"])
        self.assertEqual(record["provenance_sha256"], hashlib.sha256(proof_path.read_bytes()).hexdigest())
        self.assertRegex(record["gbs_log_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(record["verdict"], "PASS")
        expected_paths = {"tools/reproduce/reproduce.sh", "tools/reproduce/check_gbs_package.py",
                          "config/gbs_llvm.conf", "config/gbs.conf", "tools/reproduce/deliverables_manifest.json"}
        specs = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", proof["workflow_commit"],
                                         "packaging"], cwd=REPO).decode().splitlines()
        expected_paths.update(path for path in specs if Path(path).parent == Path("packaging") and path.endswith(".spec"))
        self.assertEqual(set(proof["committed_file_sha256"]), expected_paths)
        for path, digest in proof["committed_file_sha256"].items():
            with self.subTest(path=path):
                commits = (proof["workflow_commit"], "HEAD") if current else (proof["workflow_commit"],)
                for commit in commits:
                    committed = subprocess.check_output(["git", "show", commit + ":" + path], cwd=REPO)
                    self.assertEqual(hashlib.sha256(committed).hexdigest(), digest)
                if current:
                    self.assertEqual(hashlib.sha256((REPO / path).read_bytes()).hexdigest(), digest)
        for field, path in (("entrypoint_sha256", "tools/reproduce/reproduce.sh"),
                            ("checker_sha256", "tools/reproduce/check_gbs_package.py")):
            self.assertEqual(proof[field], proof["committed_file_sha256"][path])
            self.assertEqual(record[field], proof[field])
        manifest = json.loads((HERE / "deliverables_manifest.json").read_text())
        self.assertEqual(record["elf_sha256"], {item["name"]: item["gbs_build_sha256"]
                                              for item in manifest["artifacts"] if item["gbs_build_sha256"]})
        self.assertLessEqual(record["started_utc"], proof["captured_utc"])
        self.assertLessEqual(proof["captured_utc"], record["finished_utc"])

    def test_publisher_copies_execution_bytes_and_rejects_missing_dirty_or_mismatched_provenance(self) -> None:
        for fault in ("none", "missing", "hash", "checker-hash", "commit-hash", "dirty-record", "dirty-current", "changed-head", "raw-log", "raw-log-delete", "raw-log-symlink"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, env = self._gbs_artifact_fixture(root)
                bundle = root / "bundle"
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(bundle)],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                log = root / "run.log"
                log.write_text(result.stdout)
                proof_path = bundle / "execution_provenance.json"
                if fault == "missing":
                    proof_path.unlink()
                elif fault.startswith("raw-log"):
                    raw = bundle / "gbs.log"
                    if fault == "raw-log":
                        raw.write_bytes(b"tampered")
                    elif fault == "raw-log-delete":
                        raw.unlink()
                    else:
                        backup = root / "log-copy"
                        backup.write_bytes(raw.read_bytes())
                        raw.unlink()
                        raw.symlink_to(backup)
                elif fault in ("hash", "checker-hash", "commit-hash", "dirty-record"):
                    proof = json.loads(proof_path.read_text())
                    field = "dirty" if fault == "dirty-record" else "checker_sha256" if fault == "checker-hash" else "entrypoint_sha256"
                    proof[field] = True if fault == "dirty-record" else "0" * 64
                    proof_path.write_text(json.dumps(proof))
                    if fault == "commit-hash":
                        # Even an internally consistent forged summary must fail git-object binding.
                        summary_path = bundle / "gbs_build_summary.json"
                        summary = json.loads(summary_path.read_text())
                        summary["entrypoint_sha256"] = proof["entrypoint_sha256"]
                        summary["provenance_sha256"] = hashlib.sha256(proof_path.read_bytes()).hexdigest()
                        summary_path.write_text(json.dumps(summary))
                elif fault == "dirty-current":
                    (repo / "new-file").write_text("uncommitted")
                elif fault == "changed-head":
                    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                                    "commit", "--allow-empty", "-qm", "later HEAD"], cwd=repo, check=True)
                output = root / "public"
                published = subprocess.run(
                    [sys.executable, str(repo / "tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py"),
                     "--bundle", str(bundle), "--log", str(log), "--output", str(output)],
                    env=env, capture_output=True, text=True,
                )
                if fault == "none":
                    self.assertEqual(published.returncode, 0, published.stderr)
                    self.assertEqual((output / "execution_provenance.json").read_bytes(), proof_path.read_bytes())
                    self.assertEqual((output / "build_summary.json").read_bytes(), (bundle / "gbs_build_summary.json").read_bytes())
                else:
                    self.assertNotEqual(published.returncode, 0, published.stdout)
                    self.assertFalse(output.exists())

    def test_gbs_environment_errors_differ_from_source_defects(self) -> None:
        for fault in ("lock-unwritable", "broken-rpm", "broken-rpm2cpio", "broken-cpio", "source-error", "missing-header"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, env = self._gbs_artifact_fixture(root)
                if fault == "lock-unwritable":
                    (root / "lock").mkdir()  # Cannot open as a file, even when tests run as root.
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(root / "bundle")],
                    env={**env, "FIXTURE_GBS_FAULT": fault}, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1 if fault == "source-error" else 2, result.stdout + result.stderr)
                label = ("source compilation defect" if fault == "source-error" else
                         "NOT-EVALUATED\tgbs-build-unknown" if fault == "missing-header" else
                         "NOT-EVALUATED\tgbs-build-environment")
                self.assertIn(label, result.stdout)
                self.assertNotIn("OVERALL\tPASS", result.stdout)

    def test_whitelist_rejects_shell_functions_and_aliases(self) -> None:
        for command in ("awk", "dirname", "python3"):
            for kind in ("function", "alias"):
                with self.subTest(command=command, kind=kind), tempfile.TemporaryDirectory() as directory:
                    init = Path(directory) / "init.sh"
                    init.write_text(f"{command}() {{ :; }}\n" if kind == "function" else
                                    f"shopt -s expand_aliases\nalias {command}='echo spoof'\n")
                    result = subprocess.run(
                        ["bash", str(HERE / "reproduce.sh"), "verify"],
                        env={**os.environ, "BASH_ENV": str(init)}, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("runtime-injection", result.stderr)
                    self.assertIn("BASH_ENV", result.stderr)
                    self.assertNotIn("missing default-verify command", result.stderr)
                    self.assertNotIn("MODE\thost verify", result.stdout)

    def test_explicit_gbs_missing_command_is_not_evaluated_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, env = self._gbs_artifact_fixture(root)
            (root / "bin/gbs").unlink()
            output = root / "bundle"
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(output)],
                env=env, text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("NOT-EVALUATED\tgbs-build-environment\tgbs is not installed", result.stdout)
            self.assertIn("OVERALL\tFAIL", result.stdout)
            self.assertFalse(output.exists())

    def test_explicit_gbs_missing_artifacts_or_hash_drift_never_pass(self) -> None:
        for fault in ("missing-rpm", "missing-alloc_bench", "missing-gst_loop_decode",
                      "missing-reclaim_probe", "sha-drift"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repo, env = self._gbs_artifact_fixture(root)
                output = root / "bundle"
                result = subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--repo-root", str(repo), "--output-dir", str(output)],
                    env={**env, "FIXTURE_GBS_FAULT": fault}, text=True, capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("FAIL\tgbs-package-artifact", result.stdout)
                self.assertIn("OVERALL\tFAIL", result.stdout)
                self.assertNotIn("OVERALL\tPASS", result.stdout)
                self.assertFalse(output.exists())

    def test_gbs_root_owned_cleanup_is_report_only(self) -> None:
        spec = importlib.util.spec_from_file_location("checker", HERE / "check_gbs_package.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        record = {}
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "generated-buildroot"
            workspace.mkdir()
            with patch.object(module.tempfile, "mkdtemp", return_value=str(workspace)), \
                    patch.object(module.shutil, "rmtree", side_effect=PermissionError("root-owned EPERM")), \
                    patch("builtins.print") as printed:
                with module.build_workspace(record):
                    pass
                self.assertEqual(record["buildroot_residue"], str(workspace))
                self.assertIn("REPORT_ONLY\tgbs-buildroot-residue", printed.call_args.args[0])

    def test_verify_whitelist_excludes_unlisted_host_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rogue = root / "rogue-host-tool"
            rogue.write_text("#!/bin/sh\nexit 0\n")
            rogue.chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(HERE / "make_verify_path.py"), "--profile", "minimal-whitelist", "--output", str(root / "bin")],
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]},
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name for p in (root / "bin").iterdir()},
                             set((HERE / "verify_commands.txt").read_text().split()))

    def test_static_spec_defect_stays_hard_without_optional_rpmspec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, env = self._gbs_artifact_fixture(root)
            spec = repo / "packaging/glibc-memopt-tools.spec"
            spec.write_text(spec.read_text().replace("%{_bindir}/reclaim_probe", ""))
            result = subprocess.run(
                [sys.executable, str(HERE / "check_gbs_package.py"), "--repo-root", str(repo)],
                env=env, text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL\tgbs-package-contract", result.stdout)

    def test_build_command_records_distinguish_historical_and_replay(self) -> None:
        manifest = json.loads((HERE / "deliverables_manifest.json").read_text())
        record = json.loads((REPO / "data/raw/gbs_package_20260903/build_summary.json").read_text())
        expected = "gbs -c <unique-temporary-config> build -A armv7l --overwrite -c " + manifest["gbs_build"]["source_commit"]
        self.assertEqual(manifest["gbs_build"]["command"], expected)
        self.assertEqual(record["normalized_checker_command"], expected)
        self.assertEqual(record["replay_command"], manifest["gbs_build"]["replay_command"])
        self.assertIn("not the current replay command", record["command_role"])

    def test_broken_optional_rpmspec_does_not_fail_static_or_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands = Path(directory) / "bin"
            subprocess.run([sys.executable, str(HERE / "make_verify_path.py"),
                            "--profile", "broken-tools", "--output", str(commands)], check=True, capture_output=True)
            marker = Path(directory) / "gbs-invoked"
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "verify"], cwd=REPO,
                env={**os.environ, "PATH": str(commands), "PREDELIVERY_OPTIONAL_TOOL_MARKER": str(marker),
                     "REPRODUCE_ALLOW_DIRTY": "1", "REPRODUCE_SKIP_TESTS": "1", "REPRODUCE_EXPECTED_SHA": "HEAD"},
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("SKIPPED\tgbs-spec-syntax\trpmspec -P RC=42", result.stdout)
            self.assertIn("OVERALL\tPASS", result.stdout)
            self.assertFalse(marker.exists())

    def test_old_python_preflight_fails_with_actionable_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands = Path(directory)
            python = commands / "python3"
            python.write_text(
                f"#!{sys.executable}\nimport sys\n"
                "sys.version_info = (3, 9, 0)\nsys.version = '3.9.0 fixture'\n"
                "assert sys.argv[1] == '-c'\nexec(sys.argv[2])\n"
            )
            python.chmod(0o755)
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "verify"],
                env={**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]},
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Python >=3.10 required", result.stderr)
            self.assertIn("OVERALL\tFAIL", result.stderr)
            self.assertNotIn("MODE\thost verify", result.stdout)

    def test_missing_required_userland_command_is_named_by_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands = Path(directory) / "bin"
            subprocess.run([sys.executable, str(HERE / "make_verify_path.py"),
                            "--profile", "minimal-whitelist", "--output", str(commands)], check=True, capture_output=True)
            (commands / "awk").unlink()
            result = subprocess.run(
                ["bash", str(HERE / "reproduce.sh"), "verify"],
                env={**os.environ, "PATH": str(commands)}, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("missing default-verify command: awk", result.stderr)
            self.assertIn("OVERALL\tFAIL", result.stdout)

    def test_stability_snapshot_remote_body_hashes_nonempty_directory(self) -> None:
        workflow = (HERE / "board_workflow.sh").read_text(encoding="utf-8")
        line = next(
            row.strip()
            for row in workflow.splitlines()
            if row.strip().startswith("body='d=/opt/usr/share/crash/livedump;")
        )
        self.assertTrue(line.endswith("'"), line)
        remote_body = line[len("body='") : -1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "alloc_bench.armv7l_42_fixture.zip"
            archive.write_bytes(b"fixture-livedump\n")
            remote_body = remote_body.replace("/opt/usr/share/crash/livedump", str(root))
            result = subprocess.run(
                ["sh", "-c", remote_body], text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            fields = result.stdout.rstrip("\n").split("\t")
            self.assertEqual(len(fields), 4, result.stdout)
            self.assertEqual(fields[0], str(archive))
            self.assertEqual(fields[1], str(archive.stat().st_size))
            self.assertEqual(fields[3], hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_remote_commands_do_not_consume_cleanup_list_stdin(self) -> None:
        workflow = (HERE / "board_workflow.sh").read_text(encoding="utf-8")
        start = workflow.index("run_remote()\n")
        end = workflow.index("\nsnapshot_stability()", start)
        run_remote = workflow[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mock_bin = root / "bin"
            mock_bin.mkdir()
            mock_sdb = mock_bin / "sdb"
            mock_sdb.write_text(
                "#!/bin/sh\n"
                "IFS= read -r stolen || true\n"
                "echo RC=0\n"
                "echo DONE_CLEAN\n",
                encoding="utf-8",
            )
            mock_sdb.chmod(0o755)
            cleanup_list = root / "cleanup.txt"
            cleanup_list.write_text("first\nsecond\n", encoding="utf-8")
            script = root / "exercise.sh"
            script.write_text(
                "#!/bin/sh\nset -eu\n"
                f"serial=mock\noutput={root}\n"
                + run_remote
                + f"\n: > {root}/seen\n"
                + f"while IFS= read -r item; do run_remote CLEAN true {root}/$item.log; echo \"$item\" >> {root}/seen; done < {cleanup_list}\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["sh", str(script)],
                env={**os.environ, "PATH": f"{mock_bin}:{os.environ['PATH']}"},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((root / "seen").read_text(encoding="utf-8"), "first\nsecond\n")

    def test_logged_command_preserves_failure_status(self) -> None:
        workflow = (HERE / "board_workflow.sh").read_text(encoding="utf-8")
        start = workflow.index("run_logged()\n")
        end = workflow.index("\nprepare_artifacts ||", start)
        run_logged = workflow[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "command.log"
            script = root / "exercise.sh"
            script.write_text(
                "#!/bin/sh\nset -u\n"
                + run_logged
                + f"\nrun_logged {log} sh -c 'printf failed-output; exit 7'\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["sh", str(script)], text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 7, result.stderr + result.stdout)
            self.assertEqual(result.stdout, "failed-output")
            self.assertEqual(log.read_text(encoding="utf-8"), "failed-output")

    def test_s4_stability_failure_stops_before_gst(self) -> None:
        workflow = (HERE / "board_workflow.sh").read_text(encoding="utf-8")
        classification = workflow.index("classify_and_clean s4")
        guard = workflow.index('[ "$s4_stability_rc" -eq 0 ] || die "S4 stability gate"')
        gst_start = workflow.index('snapshot_stability "$output/gst/stability_before.tsv"')
        self.assertLess(classification, guard)
        self.assertLess(guard, gst_start)

    def test_expected_s4_alert_is_expected_after_archive_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before, after, post = root / "before.tsv", root / "after.tsv", root / "post.tsv"
            header = "remote_path\tsize\tmtime_epoch\tsha256\n"
            remote = "/opt/usr/share/crash/livedump/alloc_bench.armv7l_42_fixture.zip"
            before.write_text(header)
            after.write_text(header + f"{remote}\t123\t1\t{'a' * 64}\n")
            post.write_text(header)
            archive_dir = root / "archives"; archive_dir.mkdir()
            with zipfile.ZipFile(archive_dir / Path(remote).name, "w") as archive:
                prefix = "alloc_bench.armv7l_42_fixture"
                archive.writestr(f"{prefix}/{prefix}.dump_reason", "Exceeded parameter: cpu.relative\n")
                archive.writestr(f"{prefix}/{prefix}.info.json", json.dumps({"exe_file_path": "/opt/usr/glibc_memopt/s4_retention_20260901/alloc_bench.armv7l", "threads": {"pid": 42}}))
            pull = root / "pull/A/mixed/rep1"; pull.mkdir(parents=True)
            (pull / "pid.txt").write_text("42\n")
            result = subprocess.run(
                ["python3", str(STABILITY), "classify", "--before", str(before), "--after", str(after), "--post-clean", str(post), "--archive-dir", str(archive_dir), "--pull", str(root / "pull"), "--workload", "s4", "--bands", str(BANDS), "--output", str(root / "result.json"), "--clean-list", str(root / "clean.txt")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads((root / "result.json").read_text())
            self.assertEqual(payload["alerts"][0]["verdict"], "EXPECTED")
            self.assertEqual((root / "clean.txt").read_text(), remote + "\n")

    def test_public_evidence_passes_v4_and_reports_unobserved_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = subprocess.run(
                ["python3", str(REPO / "tools/runners/s4_retention_20260901/analyze_s4.py"), "--replay-public", str(REPO / "data/raw/s4_retention_20260901"), "--output", str(root / "s4")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            result = subprocess.run(
                ["python3", str(EVALUATOR), "--bands", str(BANDS), "--s4-summary", str(root / "s4/acceptance_input.json"), "--gst-derived", str(REPO / "data/raw/gst_trim_cost_20260901"), "--output", str(root / "acceptance.json")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("REGISTERED/NOT-EVALUATED", result.stdout)
            self.assertIn("REPORT_ONLY", result.stdout)
            self.assertIn("OVERALL PASS", result.stdout)
            acceptance = json.loads((root / "acceptance.json").read_text())
            self.assertEqual(acceptance["schema"], "glibc-memopt-demo.acceptance-result.v4")
            self.assertEqual(acceptance["outcome"], "PASS")

    def test_previous_gbs_a_observations_pass_v4_common_bands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = subprocess.run(
                ["python3", str(REPO / "tools/runners/s4_retention_20260901/analyze_s4.py"), "--replay-public", str(REPO / "data/raw/s4_retention_20260901"), "--output", str(root / "s4")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            path = root / "s4/acceptance_input.json"
            payload = json.loads(path.read_text())
            payload["a_anchor_reclaim_pct"] = {"mixed": 55.243785, "medium-only": 50.535918}
            path.write_text(json.dumps(payload))
            result = subprocess.run(
                ["python3", str(EVALUATOR), "--bands", str(BANDS), "--s4-summary", str(path), "--gst-derived", str(REPO / "data/raw/gst_trim_cost_20260901")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("S4 A mixed reclaim", result.stdout)
            self.assertIn("OVERALL PASS", result.stdout)

    def test_out_of_band_s4_value_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = subprocess.run(
                ["python3", str(REPO / "tools/runners/s4_retention_20260901/analyze_s4.py"), "--replay-public", str(REPO / "data/raw/s4_retention_20260901"), "--output", str(root / "s4")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            path = root / "s4/acceptance_input.json"
            payload = json.loads(path.read_text())
            payload["b_reclaim_pct_repeat_median"]["mixed"] = 50
            path.write_text(json.dumps(payload))
            result = subprocess.run(
                ["python3", str(EVALUATOR), "--bands", str(BANDS), "--s4-summary", str(path), "--gst-derived", str(REPO / "data/raw/gst_trim_cost_20260901")],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("OVERALL FAIL", result.stdout)

    def test_gst_visible_direction_is_report_only_when_rule_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gst = root / "gst"; gst.mkdir()
            source = REPO / "data/raw/gst_trim_cost_20260901"
            for name in ("cycles.tsv", "repetitions.tsv", "comparison.json", "health.json"):
                (gst / name).write_bytes((source / name).read_bytes())
            with (gst / "cycles.tsv").open(newline="", encoding="utf-8") as stream:
                cycles = list(csv.DictReader(stream, delimiter="\t"))
                fields = list(cycles[0])
            for row in cycles:
                if row["arm"] == "trim-at-loop-release" and row["primary_business_sample"] == "1":
                    row["business_elapsed_ms"] = str(float(row["business_elapsed_ms"]) + 100.0)
            with (gst / "cycles.tsv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
                writer.writeheader(); writer.writerows(cycles)
            with (gst / "repetitions.tsv").open(newline="", encoding="utf-8") as stream:
                reps = list(csv.DictReader(stream, delimiter="\t")); rep_fields = list(reps[0])
            for row in reps:
                if row["arm"] == "trim-at-loop-release":
                    row["business_p99_ms"] = f"{float(row['business_p99_ms']) + 100.0:.6f}"
            with (gst / "repetitions.tsv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rep_fields, delimiter="\t", lineterminator="\n")
                writer.writeheader(); writer.writerows(reps)
            comparison = json.loads((gst / "comparison.json").read_text())
            comparison["trim_p99_median_ms"] += 100.0
            comparison["delta_p99_ms"] += 100.0
            comparison["business_cost_visible"] = True
            (gst / "comparison.json").write_text(json.dumps(comparison))
            replay = subprocess.run(
                ["python3", str(REPO / "tools/runners/s4_retention_20260901/analyze_s4.py"), "--replay-public", str(REPO / "data/raw/s4_retention_20260901"), "--output", str(root / "s4")],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            result = subprocess.run(
                ["python3", str(EVALUATOR), "--bands", str(BANDS), "--s4-summary", str(root / "s4/acceptance_input.json"), "--gst-derived", str(gst)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("REPORT_ONLY", result.stdout)
            self.assertIn("visible=true", result.stdout)

    def test_build_chains_pin_paths_and_manifest_reproducible_hashes(self) -> None:
        alloc = (REPO / "tools/alloc_bench/Makefile").read_text()
        probe = (REPO / "tools/reclaim_probe/Makefile").read_text()
        gst = (REPO / "tools/runners/gst_trim_cost_20260901/build_armv7l.sh").read_text()
        self.assertIn("-fdebug-prefix-map=$(CURDIR)=.", alloc)
        self.assertIn("ARMV7L_BUILD_DIR ?= .build/armv7l", alloc)
        self.assertIn("-fdebug-prefix-map=$(CURDIR)=.", probe)
        self.assertIn(".build/armv7l/gst_loop_decode", gst)
        self.assertIn('"-fdebug-prefix-map=$repo=."', gst)
        manifest = json.loads((HERE / "deliverables_manifest.json").read_text())
        artifacts = {item["name"]: item for item in manifest["artifacts"]}
        self.assertEqual(manifest["schema"], "glibc-memopt-demo.deliverables.v3")
        self.assertEqual(manifest["gbs_build"]["status"], "held_out_validation_pass")
        self.assertEqual(manifest["board_rebaseline"]["decision"], "H-V")
        self.assertEqual(
            manifest["board_rebaseline"]["status"],
            "calibration_with_independent_gbs_held_out_pass",
        )
        heldout = manifest["board_rebaseline"]["held_out_validation"]
        self.assertEqual(heldout["verdict"], "PASS")
        self.assertEqual((heldout["passed_cells"], heldout["total_cells"]), (4, 4))
        self.assertFalse(heldout["included_in_calibration_samples"])
        self.assertEqual(len(artifacts), 4)
        for name in ("alloc_bench.armv7l", "gst_loop_decode.armv7l", "reclaim_probe.armv7l"):
            self.assertRegex(artifacts[name]["reproducible_build_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(artifacts[name]["gbs_build_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            artifacts["small_320x240.mp4"]["delivery"],
            "由交付方随交付邮件提供获取位置,收到后按本清单 SHA-256 核对",
        )
        self.assertNotIn("channel", manifest)
        self.assertNotIn("owner", manifest)

    def test_gbs_spec_static_contract_without_gbs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HERE / "check_gbs_package.py"), "--repo-root", str(REPO)],
            env={**os.environ, "PATH": ""}, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("PASS\tgbs-spec-static", result.stdout)
        self.assertIn("SKIPPED\tgbs-build\treal GBS build is excluded", result.stdout)

    def test_changes_document_commit_ids_resolve(self) -> None:
        document = (REPO / "docs/changes_since_demo_v2.md").read_text(encoding="utf-8")
        commits = sorted(set(re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", document)))
        self.assertTrue(commits)
        for commit in commits:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=REPO,
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, f"unresolvable commit {commit}: {result.stderr}")

    def test_delivery_closure_has_no_unqualified_preregistration_or_stale_b2_round(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True,
        )
        preregistration_violations: list[str] = []
        stale_b2: list[str] = []
        stale_round = "tizen_native_evidence_" + "20260905"
        preregistration_term = "预" + "登记"
        for raw_name in result.stdout.split(b"\0"):
            if not raw_name:
                continue
            relative = raw_name.decode("utf-8")
            data = (REPO / relative).read_bytes()
            if b"\0" in data:
                continue
            document = data.decode("utf-8", errors="replace")
            if stale_round in document:
                stale_b2.append(relative)
            for line_number, line in enumerate(document.splitlines(), 1):
                if preregistration_term in line and not any(
                    qualifier in line for qualifier in ("不称", "不得称", "降级")
                ):
                    preregistration_violations.append(f"{relative}:{line_number}:{line}")
        self.assertEqual(stale_b2, [])
        self.assertEqual(preregistration_violations, [])

    def test_delivery_identity_marks_main_report_only(self) -> None:
        refs = json.loads((HERE / "delivery_refs.json").read_text(encoding="utf-8"))
        self.assertEqual(refs["branch_refs"]["main"], {"mode": "report_only", "ref": "demo-v11"})
        self.assertEqual(refs["branch_refs"]["demo"], {"mode": "required", "ref": "demo-v11"})

    def test_main_clone_without_delivery_tag_is_report_only_and_passes(self) -> None:
        result = self._run_delivery_identity_clone("main", include_delivery_tag=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertRegex(
            result.stdout,
            r"REPORT_ONLY\tdelivery-identity\tthis is not the delivery snapshot; "
            r"checkout demo-v[0-9]+ \(reference unavailable in this clone\)",
        )
        self.assertIn("OVERALL\tPASS", result.stdout)

    def test_delivery_snapshot_required_identity_passes(self) -> None:
        result = self._run_delivery_identity_clone("demo", include_delivery_tag=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn("REPORT_ONLY\tdelivery-identity", result.stdout)
        self.assertIn("PASS\tclean-environment", result.stdout)
        self.assertIn("OVERALL\tPASS", result.stdout)

    def test_delivery_identity_fixture_accepts_all_source_head_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for shape in ("main", "demo", "tag"):
                source_repo = self._materialize_repository_shape(root, shape)
                with self.subTest(source_shape=shape, identity="main"):
                    report_only = self._run_delivery_identity_clone(
                        "main", include_delivery_tag=False, source_repo=source_repo,
                    )
                    self.assertEqual(
                        report_only.returncode, 0, report_only.stderr + report_only.stdout,
                    )
                    self.assertIn("REPORT_ONLY\tdelivery-identity", report_only.stdout)
                    self.assertIn("OVERALL\tPASS", report_only.stdout)
                with self.subTest(source_shape=shape, identity="demo"):
                    required = self._run_delivery_identity_clone(
                        "demo", include_delivery_tag=True, source_repo=source_repo,
                    )
                    self.assertEqual(required.returncode, 0, required.stderr + required.stdout)
                    self.assertNotIn("REPORT_ONLY\tdelivery-identity", required.stdout)
                    self.assertIn("PASS\tclean-environment", required.stdout)
                    self.assertIn("OVERALL\tPASS", required.stdout)

    def test_acceptance_v4_separates_determinism_validity_and_direction(self) -> None:
        bands = json.loads(BANDS.read_text(encoding="utf-8"))
        self.assertEqual(bands["schema"], "glibc-memopt-demo.acceptance.v4")
        self.assertEqual(set(bands["deterministic_items"]), {"released_payload_bytes"})
        self.assertEqual(
            set(bands["validity_gates"]),
            {"reclaimed_bytes_page_alignment", "next_cycle_majflt", "zram_deltas", "dmesg_oom_lmk_matches"},
        )
        gst = bands["tolerance_bands"]["gst_business_p99"]
        self.assertEqual(gst["acceptance"], "REPORT_ONLY")
        self.assertNotIn("expected_direction", gst)
        b = bands["tolerance_bands"]["s4_b_reclaim_pct_repeat_median"]
        self.assertEqual(b["center_pct_by_profile"], {"medium-only": 84.446566, "mixed": 81.661264})
        a = bands["tolerance_bands"]["s4_a_anchor_reclaim_pct"]
        self.assertEqual(a["center_pct_by_profile"], {"medium-only": 50.669791, "mixed": 52.794499})
        self.assertEqual(a["plus_minus_pp_by_profile"], {"medium-only": 4.918088, "mixed": 4.304705})
        self.assertEqual(a["classification"], "calibration band")
        self.assertIn("passed 4/4 held-out cells", a["independent_gbs_validation"])


if __name__ == "__main__":
    unittest.main()
