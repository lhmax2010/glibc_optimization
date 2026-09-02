#!/usr/bin/env python3
"""Host tests for the Demo acceptance and link workflow helpers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVALUATOR = HERE / "evaluate_acceptance.py"
BANDS = HERE / "acceptance_bands.json"
STABILITY = HERE / "stability_monitor.py"


class ReproduceTests(unittest.TestCase):
    def test_verify_entrypoint_passes(self) -> None:
        env = os.environ.copy()
        env["REPRODUCE_ALLOW_DIRTY"] = "1"
        env["REPRODUCE_SKIP_TESTS"] = "1"
        result = subprocess.run(
            ["bash", str(HERE / "reproduce.sh"), "verify"],
            cwd=REPO, env=env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("OVERALL\tPASS", result.stdout)
        self.assertIn("EXPECTED\tstability-monitor", result.stdout)

    def test_board_entrypoint_help_is_host_only(self) -> None:
        result = subprocess.run(
            ["bash", str(HERE / "reproduce.sh"), "board", "--help"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--ip <address>", result.stdout)

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
                archive.writestr("dump_reason", "Exceeded parameter: cpu.relative\n")
                archive.writestr("info.json", json.dumps({"exe_file_path": "/opt/usr/glibc_memopt/s4_retention_20260901/alloc_bench.armv7l", "threads": {"pid": 42}}))
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

    def test_public_evidence_passes_v2_and_prints_expected_registration(self) -> None:
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
            self.assertIn("EXPECTED", result.stdout)
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


if __name__ == "__main__":
    unittest.main()
