#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from .analyze_heldout import adjudicate


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


class HeldoutContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))

    def rows(self, values: list[float]) -> list[dict[str, object]]:
        return [dict(item, reclaim_pct_of_pretrim=value) for item, value in zip(self.contract["order"], values)]

    def test_four_of_four_inside_closed_bands_passes(self) -> None:
        result = adjudicate(self.rows([48.489794, 55.587879, 57.099204, 45.751703]), self.contract)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["passed_cells"], 4)
        self.assertTrue(result["exclude_from_calibration_samples"])

    def test_any_outside_band_fails_without_changing_bands(self) -> None:
        result = adjudicate(self.rows([48.489793, 50.0, 52.0, 50.0]), self.contract)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["passed_cells"], 3)
        self.assertEqual(self.contract["calibration_bands"]["mixed"]["lower_pct"], 48.489794)

    def test_order_runner_and_alert_registration_are_identical(self) -> None:
        order = self.contract["order"]
        self.assertEqual([(row["profile"], row["rep"]) for row in order], [("mixed", 1), ("medium-only", 1), ("mixed", 2), ("medium-only", 2)])
        remote = (HERE / "run_heldout_remote.sh").read_text(encoding="utf-8")
        calls = [line.split()[1:4] for line in remote.splitlines() if line.startswith("run_cell ")]
        self.assertEqual(calls, [[str(row["order"]), row["profile"], str(row["rep"])] for row in order])
        windows = self.contract["stability_monitor"]["expected_alerts"][0]["registered_windows"]
        expected = [f"{row['order']:02d}_gbs_{row['profile']}_rep{row['rep']}" for row in order]
        self.assertEqual(windows, expected)
        self.assertEqual(self.contract["stability_monitor"]["expected_alerts"][0]["max_count_total"], 4)

    def test_manifest_sha_and_contract_sha_agree(self) -> None:
        manifest = json.loads((HERE.parents[1] / "reproduce/deliverables_manifest.json").read_text(encoding="utf-8"))
        artifact = next(item for item in manifest["artifacts"] if item["name"] == "alloc_bench.armv7l")
        self.assertEqual(self.contract["artifact"]["sha256"], artifact["gbs_build_sha256"])

    def test_public_replay_matches_frozen_derivatives_byte_for_byte(self) -> None:
        public = REPO / "data/raw/gbs_heldout_validation_20260904"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "python3", str(HERE / "analyze_heldout.py"), "--replay",
                    str(public / "heldout_cells.tsv"), "--output", directory,
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("verdict=PASS passed=4/4", result.stdout)
            for name in ("heldout_cells.tsv", "decision.json"):
                self.assertEqual((Path(directory) / name).read_bytes(), (public / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
