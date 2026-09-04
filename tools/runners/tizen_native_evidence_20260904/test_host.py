#!/usr/bin/env python3
import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ANALYZER = HERE / "analyze_native_evidence.py"
REMOTE = HERE / "run_native_evidence_remote.sh"
CONTRACT = HERE / "preregistered_contract.json"
PACKAGE_HELPER = HERE / "manage_gdb_official_snapshot.sh"
TRIM_HELPER = ROOT / "tools/reclaim_probe/trim_via_gdb.sh"


class NativeEvidenceTests(unittest.TestCase):
    def test_contract_and_shell_syntax(self):
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(data["t1"]["trim_repetitions"], 5)
        self.assertEqual(data["t2"]["baseline_repetitions"], 3)
        self.assertEqual(data["t2"]["minimum_trim_start_interval_seconds"], 120)
        subprocess.run(["sh", "-n", REMOTE], check=True)
        source = REMOTE.read_text(encoding="utf-8")
        self.assertIn("set $stream", source)
        self.assertNotIn("set $fp", source)

    def test_public_derivation_is_stable(self):
        public = ROOT / "data/raw/tizen_native_evidence_20260904"
        summary = json.loads((public / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["completion"]["t1_completed"], 1)
        self.assertEqual(summary["completion"]["t2_baseline_completed"], 3)
        self.assertEqual(summary["t2"]["reclaimed_kb"], [272, 4, 4])
        self.assertFalse(summary["t2"]["interval_requirement_met"])
        with (public / "cells_derived.tsv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual([row["cell"] for row in rows], ["T1_1", "T2_E1", "T2_E2", "T2_E3"])
        self.assertTrue(all(row["project_reclaimed_kb"] == row["memps_reclaimed_kb"] for row in rows))

    def test_official_snapshot_and_identity_are_pinned(self):
        package_source = PACKAGE_HELPER.read_text(encoding="utf-8")
        for expected in (
            "tizen-base-toolchain_20260813.050338",
            "gdb-16.3-1.1.armv7l.rpm",
            "95d713691a0628ed0cc7fdf61cbe896f439135e4bb0b8c5690c2ef5010530165",
            "installed_bytes=53010679",
            "required_after=1288490189",
        ):
            self.assertIn(expected, package_source)
        trim_source = TRIM_HELPER.read_text(encoding="utf-8")
        self.assertIn("tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l", trim_source)
        self.assertIn('IDENTITY_OK=RPI4_UNIFIED_TOOLCHAIN', trim_source)
        self.assertNotIn("IDENTITY_OK=RPI4_UNIFIED_DEV", trim_source)

    def test_analyzer_rejects_missing_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cells.tsv").write_text("group\tcell\nT2\tT2_E1\n", encoding="utf-8")
            (root / "samples.tsv").write_text("label\tepoch_ns\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", ANALYZER, "--pull", root, "--output", root / "out"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unexpected completed-cell sequence", result.stderr)


if __name__ == "__main__":
    unittest.main()
