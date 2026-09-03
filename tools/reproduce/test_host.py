#!/usr/bin/env python3
"""Host tests for the Demo acceptance and link workflow helpers."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVALUATOR = HERE / "evaluate_acceptance.py"
BANDS = HERE / "acceptance_bands.json"
STABILITY = HERE / "stability_monitor.py"


class ReproduceTests(unittest.TestCase):
    def _run_delivery_identity_clone(self, branch: str, include_delivery_tag: bool) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clone = root / "clone"
            subprocess.run(
                ["git", "clone", "--no-tags", "--single-branch", "--branch", "main", str(REPO), str(clone)],
                check=True, capture_output=True,
            )
            if branch == "demo":
                subprocess.run(["git", "branch", "-m", "demo"], cwd=clone, check=True)
            if include_delivery_tag:
                subprocess.run(["git", "tag", "demo-v2"], cwd=clone, check=True)

            command_dir = root / "bin"
            command_dir.mkdir()
            for command in ("bash", "cmp", "cp", "dirname", "find", "git", "grep", "mktemp", "python3", "sed", "tr"):
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

    def test_board_entrypoint_help_is_host_only(self) -> None:
        result = subprocess.run(
            ["bash", str(HERE / "reproduce.sh"), "board", "--help"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--ip <address>", result.stdout)

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

    def test_public_evidence_passes_v3_and_reports_unobserved_registration(self) -> None:
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
            self.assertEqual(json.loads((root / "acceptance.json").read_text())["outcome"], "PASS")

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
        self.assertEqual(manifest["schema"], "glibc-memopt-demo.deliverables.v2")
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
        self.assertIn("SKIPPED\tgbs-build\tgbs is not installed", result.stdout)

    def test_delivery_identity_marks_main_report_only(self) -> None:
        refs = json.loads((HERE / "delivery_refs.json").read_text(encoding="utf-8"))
        self.assertEqual(refs["branch_refs"]["main"], {"mode": "report_only", "ref": "demo-v2"})
        self.assertEqual(refs["branch_refs"]["demo"], {"mode": "required", "ref": "demo-v2"})

    def test_main_clone_without_delivery_tag_is_report_only_and_passes(self) -> None:
        result = self._run_delivery_identity_clone("main", include_delivery_tag=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(
            "REPORT_ONLY\tdelivery-identity\tthis is not the delivery snapshot; "
            "checkout demo-v2 (reference unavailable in this clone)",
            result.stdout,
        )
        self.assertIn("OVERALL\tPASS", result.stdout)

    def test_delivery_snapshot_required_identity_passes(self) -> None:
        result = self._run_delivery_identity_clone("demo", include_delivery_tag=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn("REPORT_ONLY\tdelivery-identity", result.stdout)
        self.assertIn("PASS\tclean-environment", result.stdout)
        self.assertIn("OVERALL\tPASS", result.stdout)

    def test_acceptance_v3_separates_determinism_validity_and_direction(self) -> None:
        bands = json.loads(BANDS.read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()
