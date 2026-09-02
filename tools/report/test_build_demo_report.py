#!/usr/bin/env python3
"""Host-only tests for the deterministic offline Demo report builder."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUILDER = HERE / "build_demo_report.py"


class DemoReportTests(unittest.TestCase):
    def build(self, output: Path, source: str = "TEST-COMMIT") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(BUILDER), "--repo-root", str(REPO), "--output", str(output), "--source-commit", source],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_report_is_deterministic_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.html", root / "second.html"
            one, two = self.build(first), self.build(second)
            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertEqual(two.returncode, 0, two.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            document = first.read_text(encoding="utf-8")
            self.assertIn("<svg", document)
            self.assertNotIn("<script", document.lower())
            self.assertNotIn("https://", document)
            self.assertNotIn("http://", document)
            self.assertNotIn("<img", document.lower())
            self.assertIn("TEST-COMMIT", document)

    def test_headline_contract_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.html"
            result = self.build(output)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = output.read_text(encoding="utf-8")
            for expected in (
                "51.07% / 50.39%",
                "80.18%–85.45%",
                "+6.229 ms &lt; 6.784 ms",
                "未检出可见代价",
                "EXPECTED",
                "同 seed 不钉 arena 指派",
            ):
                self.assertIn(expected, document)

    def test_checked_in_report_matches_rebuild(self) -> None:
        checked_in = REPO / "docs/demo_report.html"
        marker = REPO / "tools/report/source_commit.txt"
        if not checked_in.is_file() or not marker.is_file():
            self.skipTest("generated report/source marker not checked in yet")
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "demo_report.html"
            result = subprocess.run(
                ["python3", str(BUILDER), "--repo-root", str(REPO), "--output", str(rebuilt)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(checked_in.read_bytes(), rebuilt.read_bytes())


if __name__ == "__main__":
    unittest.main()
