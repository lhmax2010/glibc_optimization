#!/usr/bin/env python3
"""Host-only regression tests for the GStreamer trim-cost validator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_gst_trim_cost.py"
CELLS = (
    (1, "none", 1),
    (2, "trim-at-loop-release", 1),
    (3, "trim-at-loop-release", 2),
    (4, "none", 2),
    (5, "none", 3),
    (6, "trim-at-loop-release", 3),
)


def write_integrity(root: Path) -> None:
    manifest = root / "board_manifest.sha256"
    sizes = root / "board_file_sizes.tsv"
    files = sorted((path for path in root.rglob("*") if path.is_file() and path not in {manifest, sizes}), key=lambda path: path.relative_to(root).as_posix())
    manifest.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  ./{path.relative_to(root).as_posix()}\n" for path in files), encoding="utf-8")
    files_with_manifest = sorted((path for path in root.rglob("*") if path.is_file() and path != sizes), key=lambda path: path.relative_to(root).as_posix())
    sizes.write_text("".join(f"{path.stat().st_size}\t./{path.relative_to(root).as_posix()}\n" for path in files_with_manifest), encoding="utf-8")


def profile(pid: int, pd_kb: int) -> str:
    return json.dumps({
        "schema": "reclaim_probe.v1",
        "command": "profile",
        "pid": pid,
        "classes": {"glibc-heap": {"private_dirty_bytes": pd_kb * 1024}},
    }) + "\n"


def make_fixture(root: Path, trim_extra_ns: int = 4_000_000, legacy_capture_majflt: bool = False) -> None:
    (root / "cells").mkdir(parents=True)
    for order, arm, rep in CELLS:
        cell = root / "cells" / f"{order:02d}_{arm}_rep{rep}"
        cell.mkdir()
        pid = 1000 + order
        (cell / "pid.txt").write_text(f"{pid}\n")
        (cell / "command.txt").write_text(
            f"order={order}\narm={arm}\nrep={rep}\ncycles=51\nplay_seconds=20\nnull_seconds=1\n",
            encoding="utf-8",
        )
        (cell / "exit_status.txt").write_text("bench_rc=0\nsampler_rc=0\n")
        lines = []
        for cycle in range(1, 52):
            base_ns = 20_000_000_000 + rep * 1_000_000 + cycle * 1000
            if arm == "trim-at-loop-release" and cycle >= 2:
                base_ns += trim_extra_ns
            lines.append(f"CYCLE_METRIC cycle={cycle} business_elapsed_ns={base_ns} minflt=20 majflt=0")
            elapsed = 1_200_000 if arm != "none" else 0
            result = 1 if arm != "none" else -1
            lines.append(f"TRIM_METRIC cycle={cycle} arm={arm} return={result} elapsed_ns={elapsed}")
            pre = 2800
            post = 1400 if arm != "none" else 2800
            for phase, value in (("pre", pre), ("post", post)):
                stem = cell / f"cycle_{cycle:02d}_{phase}"
                stem.with_suffix(".json").write_text(profile(pid, value), encoding="utf-8")
                stem.with_suffix(".txt").write_text(
                    f"cycle={cycle}\nphase={phase}\npid={pid}\nminflt={100 + cycle}\n"
                    f"majflt={'S0' if legacy_capture_majflt else '0'}\nRC=0\nDONE_CAPTURE_{phase}\n",
                    encoding="utf-8",
                )
        (cell / "program_stdout.txt").write_text("\n".join(lines) + "\n")
        (cell / "external_1s.tsv").write_text(
            "sample\ttimestamp\tepoch_ns\telapsed_s\tpid\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\n"
            f"0\tfixture\t1\t0.0\t{pid}\t1\t1\t1\t3\t10\t0\n"
            f"1\tfixture\t2\t1.0\t{pid}\t1\t1\t1\t3\t20\t0\n",
            encoding="utf-8",
        )
        (cell / "external_sampler_meta.txt").write_text("samples=2\ndeadline_overruns=0\nRC=0\nDONE_EXTERNAL_SAMPLER\n")
    (root / "dmesg_before.txt").write_text("old\n")
    (root / "dmesg_after.txt").write_text("old\nbenign\n")
    (root / "zram_mm_stat_before.txt").write_text("100 50 60 0 0\n")
    (root / "zram_mm_stat_after.txt").write_text("100 50 60 0 0\n")
    (root / "governor_after.txt").write_text("\n".join(f"cpu{i}=schedutil" for i in range(4)) + "\n")
    write_integrity(root)


class AnalyzerTests(unittest.TestCase):
    def run_analyzer(self, pull: Path, output: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy(); env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(["python3", str(ANALYZER), "--pull", str(pull), "--output", str(output)], text=True, capture_output=True, check=False, env=env)

    def test_complete_matrix_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("cells=6 cycles=306 primary=300", result.stdout)
            comparison = json.loads((root / "out/comparison.json").read_text())
            self.assertTrue(comparison["business_cost_visible"])

    def test_none_sentinel_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            path = root / "pull/cells/01_none_rep1/program_stdout.txt"
            path.write_text(path.read_text().replace("return=-1 elapsed_ns=0", "return=1 elapsed_ns=1", 1))
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("none sentinel mismatch", result.stderr)

    def test_known_posix_dollar10_capture_defect_is_explicitly_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull", legacy_capture_majflt=True)
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            health = json.loads((root / "out/health.json").read_text())
            self.assertEqual(health["capture_majflt_legacy_s0_pairs"], 306)
            self.assertEqual(health["capture_majflt_status"], "unavailable-posix-dollar10-defect")

    def test_unexpected_capture_majflt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            path = root / "pull/cells/01_none_rep1/cycle_01_pre.txt"
            path.write_text(path.read_text().replace("majflt=0", "majflt=bad"))
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid capture majflt", result.stderr)

    def test_invalid_independent_external_majflt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull", legacy_capture_majflt=True)
            path = root / "pull/cells/01_none_rep1/external_1s.tsv"
            path.write_text(path.read_text().replace("\t20\t0\n", "\t20\tbad\n"))
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid external majflt", result.stderr)

    def test_missing_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            path = root / "pull/cells/02_trim-at-loop-release_rep1/program_stdout.txt"
            path.write_text("\n".join(line for line in path.read_text().splitlines() if "cycle=51 " not in line) + "\n")
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("incomplete cycle/trim metrics", result.stderr)

    def test_manifest_corruption_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            path = root / "pull/cells/03_trim-at-loop-release_rep2/command.txt"
            path.write_text(path.read_text() + "tampered=1\n")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest hash mismatch", result.stderr)

    def test_health_gate_rejects_oom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_fixture(root / "pull")
            (root / "pull/dmesg_after.txt").write_text("old\nOut of memory: fixture\n")
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("OOM/LMK", result.stderr)


if __name__ == "__main__":
    unittest.main()
