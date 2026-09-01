#!/usr/bin/env python3
"""Host-only table tests for phenotype classification branches."""

from __future__ import annotations

import unittest

import audit_phenotypes as subject


def row(
    target: str,
    pid: int | str,
    pd: int,
    *,
    zram_orig: int = 0,
    zram_used: int = 0,
    majflt: int = 0,
    stage: str = "P0",
) -> dict[str, object]:
    return {
        "target": target,
        "pid": pid,
        "stage": stage,
        "glibc_heap_pd_kb": pd,
        "zram_orig_bytes": zram_orig,
        "zram_used_kb": zram_used,
        "majflt": majflt,
    }


class ReleaseRatioTests(unittest.TestCase):
    def classify(self, rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        baselines = {
            (str(item["target"]), int(item["pid"])): 100
            for item in rows
            if item["pid"] != "NA"
        }
        return {
            str(item["target"]): item
            for item in subject.release_ratio_census(rows, baselines)
        }

    def test_all_strict_classes(self) -> None:
        rows = [
            row("a", 1, 100),
            row("a", 1, 80),
            row("b", 2, 100),
            row("b", 2, 120),
            row("c", 3, 100),
            row("c", 3, 100),
            row("n", 4, 100),
            row("n", 4, 105),
            row("u", 5, 100),
            row("u", 5, 80, zram_orig=1),
            row("dual", 6, 100),
            row("dual", 6, 230),
            row("dual", 6, 220),
            row("same_order", 7, 100),
            row("same_order", 7, 130),
            row("same_order", 7, 120),
            row("boundary", 8, 100),
            row("boundary", 8, 210),
            row("boundary", 8, 200),
        ]
        records = self.classify(rows)
        self.assertEqual(records["a"]["classification"], "a-self-reclaim")
        self.assertEqual(records["b"]["classification"], "b-retention")
        self.assertEqual(records["c"]["classification"], "c-byte-exact-no-response")
        self.assertEqual(records["n"]["classification"], "n-subthreshold")
        self.assertEqual(records["u"]["classification"], "u-confounded")
        self.assertEqual(records["dual"]["classification"], "a-self-reclaim+b-retention")
        self.assertEqual(records["dual"]["drawdown_to_retained_pct"], "8.333333")
        self.assertEqual(records["dual"]["same_order_automatic_fall"], "no")
        self.assertEqual(records["same_order"]["classification"], "a-self-reclaim")
        self.assertEqual(records["same_order"]["same_order_automatic_fall"], "yes")
        self.assertEqual(records["boundary"]["drawdown_to_retained_pct"], "10.000000")
        self.assertEqual(records["boundary"]["classification"], "a-self-reclaim")
        self.assertIn("automatic-reclaim capability is proven", records["dual"]["note"])

    def test_na_break_and_pid_restart_are_segmented(self) -> None:
        rows = [
            row("restart", 1, 100),
            row("restart", 1, 105),
            row("restart", "NA", 0),
            row("restart", 2, 100),
            row("restart", 2, 120),
        ]
        record = self.classify(rows)["restart"]
        self.assertEqual(record["classification"], "b-retention")
        self.assertEqual(record["pid_segments"], 2)
        self.assertIn("PID restart", str(record["note"]))

    def test_all_na_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "no valid segment"):
            subject.release_ratio_census([row("missing", "NA", 0)], {})


class PlateauTests(unittest.TestCase):
    def test_generic_coarse_branches(self) -> None:
        plateau = [
            row("a", 1, 100),
            row("a", 1, 130, stage="R1"),
            row("a", 1, 80, stage="R2"),
            row("b", 2, 100),
            row("b", 2, 110, stage="R1"),
            row("c", 3, 100),
            row("c", 3, 100, stage="R1"),
            row("n", 4, 100),
            row("n", 4, 102, stage="R1"),
            row("u", 5, 100),
            row("u", 5, 130, stage="R1"),
            row("u", 5, 80, zram_orig=1, stage="R2"),
        ]
        records = {
            str(item["target"]): item
            for item in subject.plateau_crosscheck(plateau, [])
        }
        self.assertEqual(records["a"]["classification"], "a-coarse-only")
        self.assertEqual(records["b"]["classification"], "b-coarse-only")
        self.assertEqual(records["c"]["classification"], "c-byte-exact-no-response")
        self.assertEqual(records["n"]["classification"], "n-subthreshold")
        self.assertEqual(records["u"]["classification"], "u-confounded-coarse")

    def test_service_notes_derive_numbers_from_input(self) -> None:
        plateau = [
            row("ServiceA", 1, 100),
            row("ServiceA", 1, 115, stage="R1"),
            row("ServiceH[ServiceK]", 2, 100),
            row("ServiceH[ServiceK]", 2, 123, stage="R1"),
        ]
        cyclic = [
            row("ServiceA", 10, 100),
            row("ServiceA", 10, 140),
            row("ServiceA", 10, 107),
            row("ChannelLoader", 11, 100),
            row("ChannelLoader", 11, 120),
        ]
        records = {
            str(item["target"]): item
            for item in subject.plateau_crosscheck(plateau, cyclic)
        }
        self.assertEqual(records["ServiceA"]["classification"], "a-self-reclaim+b-residual")
        self.assertIn("+7 kB", str(records["ServiceA"]["note"]))
        self.assertEqual(records["ServiceH[ServiceK]"]["classification"], "b-retention")
        self.assertIn("23 kB", str(records["ServiceH[ServiceK]"]["note"]))

    def test_cyclic_evidence_controls_generic_target(self) -> None:
        plateau = [row("ServiceB", 1, 100), row("ServiceB", 1, 130, stage="R1")]
        self_reclaim = [
            row("ServiceB", 2, 100),
            row("ServiceB", 2, 140),
            row("ServiceB", 2, 100),
        ]
        record = subject.plateau_crosscheck(plateau, self_reclaim)[0]
        self.assertEqual(record["classification"], "a-self-reclaim")

        unstable = [row("ServiceB", 2, 100), row("ServiceB", 2, 104), row("ServiceB", 2, 102)]
        record = subject.plateau_crosscheck(plateau, unstable)[0]
        self.assertEqual(record["classification"], "u-cross-probe-unstable")


if __name__ == "__main__":
    unittest.main()
