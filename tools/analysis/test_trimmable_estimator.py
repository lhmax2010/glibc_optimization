#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("trimmable_estimator.py")
VALIDATOR = Path(__file__).with_name("validate_trimmable_estimator.py")
SPEC = importlib.util.spec_from_file_location("trimmable_estimator", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class EstimatorTest(unittest.TestCase):
    def write_xml(self, directory: Path, body: str) -> Path:
        path = directory / "malloc.xml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_bounds_and_per_arena_totals(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_xml(
                Path(raw),
                """<malloc version='1'>
<heap nr='0'><sizes>
  <size from='4096' to='4096' total='4096' count='1'/>
  <size from='8192' to='12288' total='20480' count='2'/>
  <unsorted from='16384' to='16384' total='16384' count='1'/>
</sizes></heap>
<heap nr='1'><sizes><size from='1' to='4095' total='4095' count='1'/></sizes></heap>
</malloc>""",
            )
            result = MODULE.estimate_xml(path)
        self.assertEqual(result["page_size"], 4096)
        self.assertEqual(result["total"]["chunk_count"], 4)
        self.assertEqual(result["total"]["histogram_total_bytes"], 28671)
        # 4096-byte chunks have no guaranteed full page at unknown alignment;
        # each >=8192-byte chunk guarantees one and permits up to three.
        self.assertEqual(result["total"]["lower_bytes"], 8192)
        self.assertEqual(result["total"]["upper_bytes"], 28672)
        self.assertEqual(result["excluded_unsorted"]["lower_bytes"], 12288)
        self.assertEqual(result["excluded_unsorted"]["upper_bytes"], 16384)

    def test_rejects_inconsistent_histogram_total(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_xml(
                Path(raw),
                "<malloc><heap nr='0'><sizes>"
                "<size from='10' to='20' total='99' count='2'/>"
                "</sizes></heap></malloc>",
            )
            with self.assertRaisesRegex(MODULE.EstimatorError, "outside"):
                MODULE.estimate_xml(path)

    def test_cli_tsv_contains_total(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_xml(
                Path(raw),
                "<malloc><heap nr='0'><sizes>"
                "<size from='8192' to='8192' total='8192' count='1'/>"
                "</sizes></heap></malloc>",
            )
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--format", "tsv", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertIn("\tTOTAL\t1\t8192\t4096\t8192\t0\t0\n", completed.stdout)

    def test_validation_manifest_tracks_paired_and_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.write_xml(
                root,
                "<malloc><heap nr='0'><sizes>"
                "<size from='8192' to='8192' total='8192' count='1'/>"
                "</sizes></heap></malloc>",
            )
            cases = root / "cases.tsv"
            cases.write_text(
                "case\tsource_round\tprofile\tcell\tvalidation_status\txml\tmeasured_reclaimed_kb\n"
                "P\tS4\tmixed\tA\tpaired\tmalloc.xml\t4\n"
                "G\tgst\ttrim\tcycle1\txml_not_collected\t-\t-\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(VALIDATOR), str(cases)],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertIn("P\tS4\tmixed\tA\tpaired\tmalloc.xml\t1\t8192\t4096\t8192", completed.stdout)
        self.assertIn("\t4096\t0\t4096\ttrue\n", completed.stdout)
        self.assertIn("G\tgst\ttrim\tcycle1\txml_not_collected\t-", completed.stdout)


if __name__ == "__main__":
    unittest.main()
