#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/tizen_native_evidence_20260905"
sys.path.insert(0, str(ROOT / "tools/analysis"))
from trimmable_estimator import estimate_xml  # noqa: E402


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class NativeEvidenceB2HostTest(unittest.TestCase):
    def test_scripts_and_contract(self) -> None:
        for script in RUNNER.glob("*.sh"):
            subprocess.run(["sh", "-n", str(script)], check=True)
        contract = json.loads((RUNNER / "preregistered_contract.json").read_text())
        self.assertEqual(contract["t1_prime"]["cells"], 5)
        self.assertEqual(contract["t1_prime"]["minimum_injection_start_interval_seconds"], 120.0)
        self.assertEqual(contract["e4_prime"]["app_id"], "setting-myaccount-efl")

    def test_published_t1_and_interval_derivations(self) -> None:
        rows = read_tsv(RAW / "cells_derived.tsv")
        t1 = rows[:5]
        self.assertEqual([row["cell"] for row in t1], [f"T1_{i}" for i in range(1, 6)])
        self.assertEqual([int(row["reclaimed_kb"]) for row in t1], [8, 16, 16, 20, 16])
        self.assertEqual(statistics.median(float(row["injection_ms"]) for row in t1), 1041.132032)
        self.assertTrue(all(row["memps_exact_match"] == "true" for row in t1))
        self.assertTrue(all(int(row["buffers_post"]) > int(row["buffers_pre"]) for row in t1))
        intervals = read_tsv(RAW / "intervals.tsv")[1:]
        values = [int(row["interval_ns"]) for row in intervals]
        self.assertEqual(min(values), 120_122_271_759)
        self.assertEqual(max(values), 120_142_672_892)
        self.assertTrue(all(value >= 120_000_000_000 for value in values))

    def test_e4_xml_and_estimator_replay(self) -> None:
        root = ET.parse(RAW / "malloc_info_E4_PRIME.xml").getroot()
        rest = next(item for item in root.findall("total") if item.attrib["type"] == "rest")
        self.assertEqual(int(rest.attrib["size"]), 6_019_572)
        estimate = estimate_xml(RAW / "malloc_info_E4_PRIME.xml")
        published = json.loads((RAW / "estimator_E4_PRIME.json").read_text())
        self.assertEqual(estimate["total"], published["total"])
        self.assertEqual(estimate["total"]["lower_bytes"], 2_252_800)
        self.assertEqual(estimate["total"]["upper_bytes"], 8_167_424)
        e4 = read_tsv(RAW / "cells_derived.tsv")[-1]
        self.assertEqual(int(e4["reclaimed_kb"]), 36)

    def test_gdb_helper_fixed_failure_paths(self) -> None:
        source = (RUNNER / "manage_gdb_official_snapshot.sh").read_text()
        self.assertNotIn("print \\\\$4", source)
        self.assertIn('done; exit 0', source)
        self.assertIn("root-space budget would be violated", source)
        self.assertIn("GDB_ABSENT_BASELINE", source)
        self.assertIn("stop instead of removing them later", source)


if __name__ == "__main__":
    unittest.main()
