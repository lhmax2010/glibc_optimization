#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from .analyze_a_anchor import adjudicate


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads((HERE / "preregistered_contract.json").read_text(encoding="utf-8"))

    def _decision(self, values: dict[tuple[str, str], list[float]]) -> str:
        return str(adjudicate(values, self.contract)["verdict"])

    def test_h_l_requires_low_ranges_separation_and_no_overlap(self) -> None:
        values = {
            ("frozen", "mixed"): [50.0, 50.1, 50.2], ("gbs", "mixed"): [53.0, 53.1, 53.2],
            ("frozen", "medium-only"): [49.0, 49.1, 49.2], ("gbs", "medium-only"): [52.0, 52.1, 52.2],
        }
        self.assertEqual(self._decision(values), "H-L")

    def test_h_v_wins_for_high_range_or_overlap(self) -> None:
        high_range = {
            ("frozen", "mixed"): [49.0, 51.0, 53.0], ("gbs", "mixed"): [55.0, 55.1, 55.2],
            ("frozen", "medium-only"): [49.0, 49.1, 49.2], ("gbs", "medium-only"): [52.0, 52.1, 52.2],
        }
        overlap = {
            ("frozen", "mixed"): [50.0, 50.1, 50.2], ("gbs", "mixed"): [50.15, 50.3, 50.4],
            ("frozen", "medium-only"): [49.0, 49.1, 49.2], ("gbs", "medium-only"): [52.0, 52.1, 52.2],
        }
        self.assertEqual(self._decision(high_range), "H-V")
        self.assertEqual(self._decision(overlap), "H-V")

    def test_edge_is_preserved_for_narrow_disjoint_small_shift(self) -> None:
        values = {
            ("frozen", "mixed"): [50.0, 50.1, 50.2], ("gbs", "mixed"): [51.0, 51.1, 51.2],
            ("frozen", "medium-only"): [49.0, 49.1, 49.2], ("gbs", "medium-only"): [50.0, 50.1, 50.2],
        }
        self.assertEqual(self._decision(values), "EDGE")

    def test_order_is_strictly_alternating_and_complete(self) -> None:
        order = self.contract["order"]
        self.assertEqual([row["order"] for row in order], list(range(1, 13)))
        self.assertEqual([row["elf"] for row in order], ["frozen", "gbs"] * 6)
        self.assertEqual(
            {(row["elf"], row["profile"], row["rep"]) for row in order},
            {(elf, profile, rep) for elf in ("frozen", "gbs") for profile in ("mixed", "medium-only") for rep in (1, 2, 3)},
        )
        remote = (HERE / "run_a_anchor_remote.sh").read_text(encoding="utf-8")
        calls = [
            line.split()[1:5]
            for line in remote.splitlines()
            if line.startswith("run_cell ")
        ]
        self.assertEqual(
            calls,
            [[str(row["order"]), row["elf"], row["profile"], str(row["rep"])] for row in order],
        )

    def test_alert_registration_matches_every_cell_once(self) -> None:
        registration = self.contract["stability_monitor"]["expected_alerts"][0]
        expected = {
            f"{row['order']:02d}_{row['elf']}_{row['profile']}_rep{row['rep']}"
            for row in self.contract["order"]
        }
        self.assertEqual(set(registration["registered_windows"]), expected)
        self.assertEqual(registration["max_count_per_window"], 1)
        self.assertEqual(registration["max_count_total"], 12)

    def test_over_limit_expected_alerts_fail_but_remain_cleanup_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = "remote_path\tsize\tmtime_epoch\tsha256\n"
            before, after = root / "before.tsv", root / "after.tsv"
            before.write_text(header, encoding="utf-8")
            archives = root / "archives"
            archives.mkdir()
            rows = []
            for suffix in ("one", "two"):
                basename = f"alloc_bench.armv7l_42_{suffix}.zip"
                remote = f"/opt/usr/share/crash/livedump/{basename}"
                rows.append(f"{remote}\t123\t1\t{'a' * 64}\n")
                with zipfile.ZipFile(archives / basename, "w") as archive:
                    prefix = basename.removesuffix(".zip")
                    archive.writestr(f"{prefix}/{prefix}.dump_reason", "Exceeded parameter: cpu.relative\n")
                    archive.writestr(
                        f"{prefix}/{prefix}.info.json",
                        json.dumps({
                            "exe_file_path": "/opt/usr/glibc_memopt/a_anchor_replication_20260904/bin/frozen/alloc_bench.armv7l",
                            "threads": {"pid": 42},
                        }),
                    )
            after.write_text(header + "".join(rows), encoding="utf-8")
            pull = root / "pull/cells/01_frozen_mixed_rep1"
            pull.mkdir(parents=True)
            (pull / "pid.txt").write_text("42\n", encoding="utf-8")
            output, clean = root / "result.json", root / "clean.txt"
            result = subprocess.run(
                [
                    "python3", str(REPO / "tools/reproduce/stability_monitor.py"), "classify",
                    "--before", str(before), "--after", str(after), "--archive-dir", str(archives),
                    "--pull", str(root / "pull"), "--workload", "a-anchor",
                    "--bands", str(HERE / "preregistered_contract.json"),
                    "--output", str(output), "--clean-list", str(clean),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([item["verdict"] for item in payload["alerts"]], ["FAIL", "FAIL"])
            self.assertEqual(len(clean.read_text(encoding="utf-8").splitlines()), 2)

    def test_public_replay_matches_frozen_derivatives_byte_for_byte(self) -> None:
        public = REPO / "data/raw/a_anchor_replication_20260904"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "python3", str(HERE / "analyze_a_anchor.py"),
                    "--replay", str(public / "a_cells.tsv"),
                    "--output", directory,
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("verdict=H-V", result.stdout)
            for name in ("group_summary.tsv", "decision.json"):
                self.assertEqual((Path(directory) / name).read_bytes(), (public / name).read_bytes(), name)

    def test_decision_acceptance_manifest_and_gbs_recheck_agree(self) -> None:
        public = REPO / "data/raw/a_anchor_replication_20260904"
        decision = json.loads((public / "decision.json").read_text(encoding="utf-8"))
        acceptance = json.loads((REPO / "tools/reproduce/acceptance_bands.json").read_text(encoding="utf-8"))
        manifest = json.loads((REPO / "tools/reproduce/deliverables_manifest.json").read_text(encoding="utf-8"))
        a_band = acceptance["tolerance_bands"]["s4_a_anchor_reclaim_pct"]
        for profile in ("mixed", "medium-only"):
            item = decision["candidate_bands"][profile]
            self.assertEqual(a_band["center_pct_by_profile"][profile], item["center_pct"])
            self.assertEqual(a_band["plus_minus_pp_by_profile"][profile], item["plus_minus_pp"])
            self.assertEqual(manifest["board_rebaseline"]["anchor_center_pct_by_profile"][profile], item["center_pct"])
            self.assertEqual(manifest["board_rebaseline"]["anchor_plus_minus_pp_by_profile"][profile], item["plus_minus_pp"])
        with (public / "gbs_v4_recheck.tsv").open(newline="", encoding="utf-8") as stream:
            recheck = list(csv.DictReader(stream, delimiter="\t"))
        self.assertFalse(any(row["status"] == "FAIL" for row in recheck))
        self.assertEqual(next(row for row in recheck if row["category"] == "overall")["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
