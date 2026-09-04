#!/usr/bin/env python3
"""Host tests for the Demo acceptance and link workflow helpers."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import csv
import fcntl
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVALUATOR = HERE / "evaluate_acceptance.py"
BANDS = HERE / "acceptance_bands.json"
STABILITY = HERE / "stability_monitor.py"


class ReproduceTests(unittest.TestCase):
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
            for command in ("bash", "cmp", "cp", "dirname", "find", "git", "grep", "ln", "mkdir", "mktemp", "python3", "sed", "tr"):
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
        self.assertIn("3 clone shapes x 4 optional-tool PATH profiles = 12", result.stdout)
        self.assertIn("present-gbs+absent-rpm", result.stdout)
        self.assertIn("minimal-git-python", result.stdout)

    def test_default_host_test_dependency_audit_covers_inventory(self) -> None:
        entrypoint = (HERE / "reproduce.sh").read_text(encoding="utf-8")
        start = entrypoint.index("host_tests()\n")
        end = entrypoint.index("\n}\n", start)
        modules = re.findall(r"^\s+(tools/\S+\.py)(?:\s+\\)?$", entrypoint[start:end], re.MULTILINE)
        self.assertEqual(len(modules), 11, modules)
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

    def test_explicit_gbs_environment_failure_is_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
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
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "GLIBC_MEMOPT_GBS_LOCK": str(root / "gbs.lock"),
                "FAKE_GBS_LOG": str(root / "gbs.log"),
            }
            results = [
                subprocess.run(
                    ["bash", str(HERE / "reproduce.sh"), "gbs", "--lock-timeout", "1"],
                    cwd=REPO, env=env, text=True, capture_output=True, check=False,
                )
                for _ in range(2)
            ]
            for result in results:
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("REPORT_ONLY\tgbs-build-environment\tgbs build returned RC=42", result.stdout)
                self.assertIn("SKIPPED\tgbs-build\tGBS environment unavailable", result.stdout)
                self.assertIn("OVERALL\tPASS", result.stdout)
            rows = (root / "gbs.log").read_text(encoding="utf-8").splitlines()
            configs = rows[0::2]
            buildroots = rows[1::2]
            self.assertEqual(len(configs), 2)
            self.assertNotEqual(configs[0], configs[1])
            self.assertTrue(all("/tmp/glibc-memopt-gbs-" in item for item in configs))
            self.assertNotEqual(buildroots[0], buildroots[1])
            self.assertFalse(unexpected_tools.exists())

    def test_explicit_gbs_reports_occupied_lock_without_failing_package(self) -> None:
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
                    [sys.executable, str(HERE / "check_gbs_package.py"), "--repo-root", str(REPO),
                     "--build", "--lock-timeout", "0"],
                    cwd=REPO, env=env, text=True, capture_output=True, check=False,
                )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("WAITING\tgbs-build-lock", result.stdout)
            self.assertIn("REPORT_ONLY\tgbs-build-environment", result.stdout)
            self.assertIn("remained occupied", result.stdout)
            self.assertFalse(unexpected_tools.exists())

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
        self.assertEqual(refs["branch_refs"]["main"], {"mode": "report_only", "ref": "demo-v6"})
        self.assertEqual(refs["branch_refs"]["demo"], {"mode": "required", "ref": "demo-v6"})

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
