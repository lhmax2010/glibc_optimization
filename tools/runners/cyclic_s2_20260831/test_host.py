#!/usr/bin/env python3
"""Host-only regression tests for the published S2 harness."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_s2.py"
SAMPLER = HERE / "sample_smaps_1s.sh"


def cycle_item(cycle: int) -> dict[str, object]:
    value = 100 + cycle
    return {
        "cycle": cycle,
        "released_payload_bytes": cycle * 1000,
        "rise_elapsed_ns": 1_000_000_000,
        "release_elapsed_ns": 1_000_000_000,
        "peak_valley_glibc_heap_kb": 100,
        "m7_rest_delta_bytes": cycle,
        "m7_unsorted_delta_bytes": -cycle,
        "heap": {
            "start": {"glibc_heap_pd_kb": value},
            "peak": {"glibc_heap_pd_kb": value + 100},
            "fall_mid": {"glibc_heap_pd_kb": value + 50},
            "valley": {"glibc_heap_pd_kb": value},
        },
        "faults": {
            "rise_minflt": cycle,
            "rise_majflt": 0,
            "next_cycle_minflt": cycle + 1,
            "next_cycle_majflt": 0,
        },
    }


def write_fixture(root: Path, cycle_order: list[int] | None = None) -> None:
    order = cycle_order or list(range(1, 9))
    for profile in ("mixed", "medium-only"):
        profile_dir = root / profile
        profile_dir.mkdir(parents=True)
        result = {
            "cycle_rise_s": 1.0,
            "cycle_peak_s": 1.0,
            "release_duration_s": 1.0,
            "cycle_valley_s": 1.0,
            "cycle_data": [cycle_item(cycle) for cycle in order],
        }
        (profile_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
        fields = (
            "sample",
            "timestamp",
            "epoch_ns",
            "elapsed_s",
            "pid",
            "glibc_heap_pd_kb",
            "other_anon_pd_kb",
            "file_backed_pd_kb",
            "total_pd_kb",
            "minflt",
            "majflt",
        )
        rows = []
        for cycle in range(1, 9):
            base = (cycle - 1) * 4.0
            for offset, glibc in ((0.1, 100), (1.1, 200), (2.1, 120), (3.1, 100)):
                rows.append(
                    {
                        "sample": len(rows),
                        "timestamp": "fixture",
                        "epoch_ns": 1_000_000_000 + len(rows),
                        "elapsed_s": base + offset,
                        "pid": 42,
                        "glibc_heap_pd_kb": glibc + cycle,
                        "other_anon_pd_kb": 10,
                        "file_backed_pd_kb": 5,
                        "total_pd_kb": glibc + cycle + 15,
                        "minflt": len(rows),
                        "majflt": 0,
                    }
                )
        with (profile_dir / "external_1s.tsv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


class AnalyzerTests(unittest.TestCase):
    def run_analyzer(self, pull: Path, output: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(ANALYZER), "--pull", str(pull), "--output", str(output)],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_reversed_cycle_input_is_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root / "pull", list(range(8, 0, -1)))
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            with (root / "out/internal_cycles.tsv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            for profile in ("mixed", "medium-only"):
                cycles = [int(row["cycle"]) for row in rows if row["profile"] == profile]
                self.assertEqual(cycles, list(range(1, 9)))

    def test_duplicate_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root / "pull", [1, 2, 3, 4, 5, 6, 7, 7])
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cycles must be exactly 1..8", result.stderr)

    def test_pid_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root / "pull")
            path = root / "pull/mixed/external_1s.tsv"
            lines = path.read_text(encoding="utf-8").splitlines()
            fields = lines[-1].split("\t")
            fields[4] = "99"
            lines[-1] = "\t".join(fields)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PID changed", result.stderr)


class SamplerTests(unittest.TestCase):
    def run_sampler(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PROC_ROOT"] = str(root / "proc")
        return subprocess.run(
            ["sh", str(SAMPLER), "42", str(root / "samples.tsv"), str(root / "meta.txt")],
            text=True,
            capture_output=True,
            env=env,
            check=False,
            timeout=5,
        )

    def test_zero_samples_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "proc").mkdir()
            result = self.run_sampler(root)
            self.assertEqual(result.returncode, 7)
            self.assertIn("failure_reason=zero-samples", (root / "meta.txt").read_text())
            self.assertIn("FAIL_EXTERNAL_SAMPLER", (root / "meta.txt").read_text())

    def test_stat_read_failure_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc/42"
            proc.mkdir(parents=True)
            (proc / "smaps").write_text("invalid\n", encoding="utf-8")
            result = self.run_sampler(root)
            self.assertEqual(result.returncode, 4)
            self.assertIn("failure_reason=stat-read", (root / "meta.txt").read_text())

    def test_smaps_parse_failure_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc/42"
            proc.mkdir(parents=True)
            (proc / "stat").write_text("42 (fixture) S 0 0 0 0 0 0 5 0 7\n", encoding="utf-8")
            (proc / "smaps").write_text("invalid\n", encoding="utf-8")
            result = self.run_sampler(root)
            self.assertEqual(result.returncode, 6)
            self.assertIn("failure_reason=smaps-parse", (root / "meta.txt").read_text())

    def test_sample_then_target_exit_is_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc/42"
            proc.mkdir(parents=True)
            (proc / "stat").write_text("42 (fixture) S 0 0 0 0 0 0 5 0 7\n", encoding="utf-8")
            (proc / "smaps").write_text(
                "a00000-a01000 rw-p 00000000 00:00 0 [heap]\nPrivate_Dirty: 4 kB\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PROC_ROOT"] = str(root / "proc")
            process = subprocess.Popen(
                ["sh", str(SAMPLER), "42", str(root / "samples.tsv"), str(root / "meta.txt")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if (root / "samples.tsv").exists() and len((root / "samples.tsv").read_text().splitlines()) > 1:
                    break
                time.sleep(0.01)
            else:
                process.kill()
                self.fail("sampler did not emit its first row")
            (proc / "smaps").unlink()
            (proc / "stat").unlink()
            proc.rmdir()
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            meta = (root / "meta.txt").read_text()
            self.assertIn("samples=1", meta)
            self.assertIn("DONE_EXTERNAL_SAMPLER", meta)


if __name__ == "__main__":
    unittest.main()
