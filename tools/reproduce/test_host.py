#!/usr/bin/env python3
"""Host tests for the Demo acceptance and link workflow helpers."""

from __future__ import annotations

import json
import os
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
