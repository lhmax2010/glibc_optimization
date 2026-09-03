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
                "1.233269 ms",
                "+6.229 ms &lt; 6.784 ms",
                "margin 0.556 ms",
                "阈值 91.8%",
                "+359 minflt/循环",
                "未检出；margin",
                "REGISTERED/NOT-EVALUATED",
                "同 seed 不钉 arena 指派",
                "68.169197%",
                "release-ratio 标签",
                "plateau/cyclic 标签",
                "ServiceD",
                "&lt;TEST_IMAGE_B&gt;/glibc-2.40-2.8",
            ):
                self.assertIn(expected, document)

    def test_record_source_commit_uses_git_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, marker = root / "report.html", root / "source_commit.txt"
            result = subprocess.run(
                ["python3", str(BUILDER), "--repo-root", str(REPO), "--output", str(output),
                 "--record-source-commit", "--marker-output", str(marker)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            head = subprocess.run(
                ["git", "-C", str(REPO), "rev-parse", "HEAD"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertEqual(marker.read_text(encoding="utf-8"), head + "\n")
            self.assertIn(head, output.read_text(encoding="utf-8"))

    def test_customer_surfaces_share_headline_contract(self) -> None:
        surfaces = {
            "narrative": REPO / "docs/demo_narrative_20260901.md",
            "package": REPO / "docs/demo_package_20260902.md",
            "guide": REPO / "docs/demo_reproduction_guide_20260901.md",
            "demo-en": REPO / "tools/report/demo_README.md",
            "demo-zh": REPO / "tools/report/demo_README.zh-CN.md",
        }
        documents = {name: path.read_text(encoding="utf-8") for name, path in surfaces.items()}
        for name, document in documents.items():
            self.assertIn("1.233269 ms", document, name)
            self.assertIn("<TEST_IMAGE_B>", document, name)
            self.assertIn("glibc-2.40-2.8", document, name)
        for name in ("package", "guide", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertIn("0.555556 ms", document, name)
            self.assertIn("91.8%", document, name)
            self.assertIn("+359", document, name)

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
