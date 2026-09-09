"""STOP publication tests with explicit synthetic host-only raw files."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import publish_g4_observations as publisher
import test_compact_replay as fixture


class G4StopPublication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="g4-stop-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.run = self.root / "run"
        self.run.mkdir()
        fixture.CompactReplay().frozen_fixture(self.run)
        self.output = self.root / "public"
        self.cells = [c for c in publisher.CONTRACT["cells"] if c["group"] == "G4"]
        self.receipt = {"verdict": "STOP", "cleanup": "FAIL", "end_utc": "2026-09-09T00:00:00+00:00",
                        "completed_cells": [c["id"] for c in self.cells],
                        "root_authorization": {"root_off": "PASS_NONROOT"}, "fixture_only": True}
        self.save()
        rows = publisher.ANALYSIS.analyze(self.run / "raw", {**publisher.CONTRACT, "cells": self.cells})
        publisher.ANALYSIS.write_tsv(self.run / "derived/g4_cycles.tsv", rows)
        publisher.ANALYSIS.write_tsv(self.run / "derived/g4_summary.tsv", publisher.ANALYSIS.summarize(rows))

    def save(self):
        (self.run / "execution.json").write_text(json.dumps(self.receipt))

    def test_stopped_observations_not_complete_demo_and_two_derivations_match(self):
        before = (self.run / "execution.json").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as log:
            publisher.publish(self.run, self.output)
        source = json.loads((self.output / "g4_points.json").read_text())
        self.assertEqual(source["verdict"], "STOP_NOT_ACCEPTED_FOR_DEMO")
        self.assertEqual(len(source["points"]), 3)
        self.assertEqual(source["execution"], self.receipt)
        self.assertEqual((self.run / "execution.json").read_bytes(), before)
        for name in ("g4_cycles.tsv", "g4_summary.tsv"):
            self.assertEqual((self.run / "derived" / name).read_bytes(), (self.output / name).read_bytes())
        self.assertIn("ROUND=STOP NOT_DEMO", log.getvalue())

    def test_active_root_or_incomplete_cells_refused(self):
        for change in ({"verdict": "PASS_G4_ONLY"}, {"completed_cells": ["G4_trim_r1"]},
                       {"root_authorization": {"root_off": "NOT-EVALUATED"}}):
            saved = dict(self.receipt)
            self.receipt.update(change)
            self.save()
            with self.subTest(change=change), self.assertRaises(ValueError):
                publisher.publish(self.run, self.output)
            self.assertFalse(self.output.exists())
            self.receipt = saved

    def test_source_or_derived_tampering_refused(self):
        for path in (self.run / "raw/G4_trim_r1/malloc_info_pre.xml", self.run / "derived/g4_cycles.tsv"):
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                publisher.publish(self.run, self.output)
            self.assertFalse(self.output.exists())
            path.write_bytes(original)

    def test_destination_boundary_and_symlink_refused(self):
        for output in (self.run, self.run / "new", self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                publisher.publish(self.run, output)
        self.output.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "symlink"):
            publisher.publish(self.run, self.output)


if __name__ == "__main__":
    unittest.main()
