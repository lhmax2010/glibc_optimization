#!/usr/bin/env python3
"""Host-only regression tests for the S4 validator and sampler."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_s4.py"
SAMPLER = HERE / "sample_smaps_1s.sh"
REPO_ROOT = HERE.parents[2]
PUBLIC_EVIDENCE = REPO_ROOT / "data/raw/s4_retention_20260901"


def write_external(path: Path) -> None:
    fields = (
        "sample", "timestamp", "epoch_ns", "elapsed_s", "pid", "glibc_heap_pd_kb",
        "other_anon_pd_kb", "file_backed_pd_kb", "total_pd_kb", "minflt", "majflt",
    )
    rows = [
        dict(zip(fields, (0, "fixture", 1, 0.0, 42, 100, 10, 5, 115, 10, 0))),
        dict(zip(fields, (1, "fixture", 2, 1.0, 42, 200, 10, 5, 215, 20, 0))),
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_common(cell: Path, xml_suffixes: tuple[str, ...]) -> None:
    (cell / "xml").mkdir(parents=True)
    for suffix in xml_suffixes:
        (cell / f"xml/malloc_info_fixture{suffix}").write_text("<malloc version='1'></malloc>\n", encoding="utf-8")
    (cell / "exit_status.txt").write_text("bench_rc=0\nsampler_rc=0\n", encoding="utf-8")
    (cell / "external_sampler_meta.txt").write_text(
        "samples=2\ndeadline_overruns=0\nRC=0\nDONE_EXTERNAL_SAMPLER\n", encoding="utf-8"
    )
    write_external(cell / "external_1s.tsv")


def write_integrity(root: Path) -> None:
    manifest = root / "board_manifest.sha256"
    sizes = root / "board_file_sizes.tsv"
    files = sorted(
        (path for path in root.rglob("*") if path.is_file() and path not in {manifest, sizes}),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    manifest.write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  ./{path.relative_to(root).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )
    size_files = sorted(
        (path for path in root.rglob("*") if path.is_file() and path != sizes),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    sizes.write_text(
        "".join(f"{path.stat().st_size}\t./{path.relative_to(root).as_posix()}\n" for path in size_files),
        encoding="utf-8",
    )


def make_fixture(root: Path) -> None:
    for profile in ("mixed", "medium-only"):
        cell = root / "A" / profile / "rep1"
        make_common(cell, ("_measure.xml", "_release.xml", "_posttrim.xml", "_idle.xml"))
        memory = {
            "glibc_heap_pd_kb_pretrim": 1000,
            "glibc_heap_pd_kb_posttrim": 500,
            "trim_elapsed_ns": 1_000_000,
            "post_trim_elapsed_ns": 2_000_000,
            "faults": {
                "minflt_pretrim": 10, "majflt_pretrim": 0,
                "minflt_posttrim": 11, "majflt_posttrim": 0,
                "minflt_postrefault": 21, "majflt_postrefault": 0,
            },
        }
        result = {
            "mode": "duration",
            "profile": profile if profile == "mixed" else "external:/fixture/medium_1k_16k.hist",
            "threads": 4, "seed": 20260813,
            "warmup_s": 5.0, "duration_s": 20.0, "idle_s": 15.0,
            "post_trim_ops_per_thread": 4096,
            "live_set_per_thread": 4096, "idle_release_pct": 50, "release_order": "high",
            "idle_trim": True, "idle_trim_ret": 1, "idle_released_bytes": 512000,
            "memory": memory,
        }
        (cell / "result.json").write_text(json.dumps(result), encoding="utf-8")

    for profile in ("mixed", "medium-only"):
        for trim_at, reps in (("valley", (1, 2, 3)), ("none", (1,))):
            for rep in reps:
                cell = root / "B" / profile / trim_at / f"rep{rep}"
                make_common(
                    cell,
                    tuple(
                        f"_cycle{cycle:02d}_{phase}.xml"
                        for cycle in (1, 2)
                        for phase in ("peak", "fall_mid", "valley", "posttrim")
                    ),
                )
                cycles = []
                for cycle in (1, 2):
                    reclaimed = 100 if trim_at == "valley" else 0
                    cycles.append(
                        {
                            "cycle": cycle,
                            "released_payload_bytes": 102400,
                            "peak_valley_glibc_heap_kb": 0,
                            "trim_return": 1 if trim_at == "valley" else -1,
                            "trim_elapsed_ns": 1_000_000 if trim_at == "valley" else 0,
                            "heap": {
                                "peak": {"glibc_heap_pd_kb": 500},
                                "valley": {"glibc_heap_pd_kb": 500},
                                "trim_pre": {"glibc_heap_pd_kb": 500},
                                "trim_post": {"glibc_heap_pd_kb": 500 - reclaimed},
                            },
                            "malloc_info_stats": {
                                "valley": {"rest_bytes": 1000, "unsorted_bytes": 800},
                                "posttrim": {"rest_bytes": 1000, "unsorted_bytes": 800},
                            },
                            "faults": {"next_cycle_minflt": 7 if cycle == 1 else 0, "next_cycle_majflt": 0},
                        }
                    )
                result = {
                    "mode": "cyclic", "profile": profile, "threads": 4, "seed": 20260814,
                    "live_set_per_thread": 512, "idle_release_pct": 50, "release_order": "high",
                    "cycles": 2, "cycle_rise_s": 3.4, "cycle_peak_s": 4.7,
                    "release_duration_s": 19.7, "cycle_valley_s": 20.0,
                    "trim_at": trim_at, "cycle_data": cycles,
                }
                (cell / "result.json").write_text(json.dumps(result), encoding="utf-8")
                (cell / "command.txt").write_text("CMD=alloc_bench --touch-full --warmup 0\n", encoding="utf-8")

    (root / "dmesg_before.txt").write_text("old\n", encoding="utf-8")
    (root / "dmesg_after.txt").write_text("old\nnew benign\n", encoding="utf-8")
    (root / "zram_mm_stat_before.txt").write_text("100 50 60 0 0\n", encoding="utf-8")
    (root / "zram_mm_stat_after.txt").write_text("120 55 64 0 0\n", encoding="utf-8")
    (root / "governor_after.txt").write_text("\n".join(f"cpu{i}=schedutil" for i in range(4)) + "\n")
    write_integrity(root)


class AnalyzerTests(unittest.TestCase):
    def run_analyzer(self, pull: Path, output: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(ANALYZER), "--pull", str(pull), "--output", str(output)],
            text=True, capture_output=True, check=False, env=env,
        )

    def run_replay(self, public: Path, output: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(ANALYZER), "--replay-public", str(public), "--output", str(output)],
            text=True, capture_output=True, check=False, env=env,
        )

    def test_public_replay_emits_acceptance_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "replay"
            result = self.run_replay(PUBLIC_EVIDENCE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                "replayed A=2 cells B=8 cells B_cycles=16\n"
                "A anchors mixed=51.074077% medium-only=50.387886%\n"
                "B repeat-medians mixed=81.661264% medium-only=84.446566%\n"
                "deterministic payload_sets=4 aligned=12/12 majflt_max=0 zram=0,0,0 oom_lmk=0\n",
            )
            summary = json.loads((output / "acceptance_input.json").read_text())
            self.assertEqual(summary["released_payload_bytes"]["mixed"], [5742256, 6566672])
            self.assertEqual(summary["b_reclaim_pct_repeat_median"]["medium-only"], 84.446566)

    def test_complete_matrix_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("A=2 cells B=8 cells B_cycles=16", result.stdout)
            with (root / "out/b_cells.tsv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual(len(rows), 8)

    def test_malformed_xml_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            (root / "pull/A/mixed/rep1/xml/malloc_info_fixture_measure.xml").write_text("<bad>", encoding="utf-8")
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)

    def test_missing_xml_phase_is_rejected_even_when_count_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            xml_dir = root / "pull/A/mixed/rep1/xml"
            (xml_dir / "malloc_info_fixture_idle.xml").unlink()
            (xml_dir / "malloc_info_fixture_duplicate.xml").write_text(
                "<malloc version='1'></malloc>\n", encoding="utf-8"
            )
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing/duplicate XML phase", result.stderr)

    def test_corrupt_file_is_rejected_by_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            path = root / "pull/A/mixed/rep1/result.json"
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manifest hash mismatch", result.stderr)

    def test_sampler_metadata_count_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            meta = root / "pull/A/mixed/rep1/external_sampler_meta.txt"
            meta.write_text(meta.read_text().replace("samples=2", "samples=999"), encoding="utf-8")
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("metadata/TSV count mismatch", result.stderr)

    def test_trim_sentinel_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_fixture(root / "pull")
            path = root / "pull/B/mixed/valley/rep1/result.json"
            result_json = json.loads(path.read_text(encoding="utf-8"))
            result_json["cycle_data"][0]["trim_return"] = -1
            result_json["cycle_data"][0]["trim_elapsed_ns"] = 0
            path.write_text(json.dumps(result_json), encoding="utf-8")
            write_integrity(root / "pull")
            result = self.run_analyzer(root / "pull", root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("valley trim sentinel mismatch", result.stderr)


class SamplerTests(unittest.TestCase):
    def run_sampler(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PROC_ROOT"] = str(root / "proc")
        return subprocess.run(
            ["sh", str(SAMPLER), "42", str(root / "samples.tsv"), str(root / "meta.txt")],
            text=True, capture_output=True, env=env, check=False, timeout=5,
        )

    def test_zero_samples_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "proc").mkdir()
            result = self.run_sampler(root)
            self.assertEqual(result.returncode, 7)
            self.assertIn("failure_reason=zero-samples", (root / "meta.txt").read_text())

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
                "a00000-a01000 rw-p 00000000 00:00 0 [heap]\nPrivate_Dirty: 4 kB\n", encoding="utf-8"
            )
            env = os.environ.copy()
            env["PROC_ROOT"] = str(root / "proc")
            process = subprocess.Popen(
                ["sh", str(SAMPLER), "42", str(root / "samples.tsv"), str(root / "meta.txt")],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if (root / "samples.tsv").exists() and len((root / "samples.tsv").read_text().splitlines()) > 1:
                    break
                time.sleep(0.01)
            else:
                process.kill()
                self.fail("sampler emitted no row")
            (proc / "smaps").unlink(); (proc / "stat").unlink(); proc.rmdir()
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertIn("DONE_EXTERNAL_SAMPLER", (root / "meta.txt").read_text())


if __name__ == "__main__":
    unittest.main()
