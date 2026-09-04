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
                "52.79% / 50.67%",
                "52.794499% ±4.304705 pp",
                "50.669791% ±4.918088 pp",
                "80.18%–85.45%",
                "1.233269 ms",
                "1.218361 ms",
                "6212 KiB（6.07 MiB）",
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
                "272 / 4 / 4 KiB",
                "5.84 MiB rest",
                "119.806876910/119.856460299 s",
                "8 / 16 / 16 / 20 / 16 KiB",
                "120.122271759–120.142672892 s",
                "6019572 B",
                "3324 → 3288 KiB",
                "2200–7976 KiB",
                "15/15",
                "产品启用必须连续通过四道硬门",
                "同目标/同相位实测收益 ≥ 事前固定阈值",
                "守护进程碎片化驻留的实测收益很小",
                "估算器不可用作启用门",
                "S4 A v4",
                "Tizen 原生 B/B2",
                "GBS held-out 4/4",
                "49.492012%",
                "51.806724%",
                "54.266910%",
                "49.656064%",
                "gbs-heldout-contract-20260904",
                "L2 当前默认 GBS",
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
            "s4-report": REPO / "docs/s4_reference_and_retention_trim_20260901.md",
            "status": REPO / "docs/glibc_memopt_program_status_report_zh.md",
            "demo-en": REPO / "tools/report/demo_README.md",
            "demo-zh": REPO / "tools/report/demo_README.zh-CN.md",
        }
        documents = {name: path.read_text(encoding="utf-8") for name, path in surfaces.items()}
        documents["report"] = (REPO / "docs/demo_report.html").read_text(encoding="utf-8")
        for name, document in documents.items():
            self.assertIn("1.233269 ms", document, name)
            self.assertIn("1.218361 ms", document, name)
            self.assertNotIn("合并中位", document, name)
            self.assertNotIn("merged median", document.lower(), name)
        for name in ("narrative", "package", "guide", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertIn("<TEST_IMAGE_B>", document, name)
            self.assertIn("glibc-2.40-2.8", document, name)
        for name in ("narrative", "package", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertTrue("四道硬门" in document or "four hard gates" in document, name)
            self.assertTrue("事前固定阈值" in document or "precommitted threshold" in document, name)
        for name in ("package", "guide", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertIn("0.555556 ms", document, name)
            self.assertIn("91.8%", document, name)
            self.assertIn("+359", document, name)
        for name in ("narrative", "package", "guide", "status", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertIn("52.794499", document, name)
            self.assertIn("50.669791", document, name)
        a2_report = (REPO / "docs/a_anchor_replication_20260904.md").read_text(encoding="utf-8")
        self.assertIn("52.794499", a2_report)
        self.assertIn("50.669791", a2_report)
        for name in ("report", "package", "guide", "status", "demo-en", "demo-zh"):
            document = documents[name]
            self.assertTrue("held-out" in document, name)
            self.assertTrue("calibration" in document.lower() or "校准" in document, name)

    def test_native_evidence_customer_surfaces_match(self) -> None:
        surfaces = (
            REPO / "docs/tizen_native_evidence_20260904.md",
            REPO / "docs/demo_narrative_20260901.md",
            REPO / "docs/demo_reproduction_guide_20260901.md",
            REPO / "tools/report/demo_README.md",
            REPO / "tools/report/demo_README.zh-CN.md",
        )
        for path in surfaces:
            document = path.read_text(encoding="utf-8")
            for expected in ("5.84 MiB", "272", "4", "1/5", "0/1", "119.806876910", "119.856460299"):
                self.assertIn(expected, document, path.name)
            for expected in ("5/5", "6019572", "36 KiB", "120.122271759", "15/15"):
                self.assertIn(expected, document, path.name)

    def test_gbs_delivery_surfaces_share_status_and_manifest(self) -> None:
        for path in (
            REPO / "README.md",
            REPO / "docs/demo_reproduction_guide_20260901.md",
            REPO / "tools/report/demo_README.md",
            REPO / "tools/report/demo_README.zh-CN.md",
        ):
            document = path.read_text(encoding="utf-8")
            self.assertIn("gbs_llvm.conf", document, path.name)
            self.assertTrue("held-out" in document, path.name)
            self.assertTrue(
                "default HQ L2 path" in document
                or "default L2 path" in document
                or "当前 HQ 默认路径" in document
                or "L2 默认路径" in document,
                path.name,
            )
            self.assertIn("4/4", document, path.name)

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
