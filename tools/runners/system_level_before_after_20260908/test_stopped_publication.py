"""Host-only guard tests; synthetic receipts are not board results."""
import copy
import contextlib
import csv
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import publish_stopped_measurement as publisher
import test_compact_replay as compact_fixture


class StoppedPublication(unittest.TestCase):
    def receipt(self):
        return {"verdict": "STOP", "cleanup": "PASS", "end_utc": "HOST_FIXTURE_ONLY",
                "active_cell": "G4_trim_r1", "completed_cells": [c["id"] for c in publisher.CONTRACT["cells"] if c["group"] != "G4"]}

    def test_only_complete_paired_prefix_is_selected_without_changing_contract(self):
        before = copy.deepcopy(publisher.CONTRACT)
        subset = publisher.completed_contract(self.receipt())
        self.assertEqual(len(subset["cells"]), 18)
        self.assertEqual(sum(c["cycles"] for c in subset["cells"]), 330)
        self.assertEqual(before, publisher.CONTRACT)

    def test_partial_incomplete_cleanup_or_false_full_pass_is_rejected(self):
        for key, value in (("verdict", "PASS_COMPLETE_MATRIX"), ("cleanup", "FAIL"),
                           ("end_utc", None), ("active_cell", "G4_trim_r2"), ("completed_cells", [])):
            receipt = self.receipt()
            receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                publisher.completed_contract(receipt)

    def test_full_temp_fixture_archives_only_18_cells_and_330_pairs_without_g4_fill(self):
        # All files are explicit HOST_FIXTURE_ONLY input in a private temp tree.
        # The actual frozen analyzer and archive/manifest verifier run; no board
        # commands and no mock acceptance or fabricated repository evidence.
        with tempfile.TemporaryDirectory(prefix="stopped-prefix-host-fixture-") as directory:
            root = pathlib.Path(directory)
            compact_fixture.CompactReplay().frozen_fixture(root)
            receipt = {**self.receipt(), "fixture_not_board_evidence": True}
            (root / "execution.json").write_text(json.dumps(receipt))

            # Replace the generator's successful G4 r1 with a genuinely partial
            # fixture.  Other generated G4 directories deliberately remain, so
            # the test also proves they cannot be silently included or imputed.
            failed = root / "raw/G4_trim_r1"
            failed.rename(root / "unused_complete_g4_fixture")
            failed.mkdir()
            (failed / "gdb_m7.txt.stderr").write_text("HOST_FIXTURE_ONLY: M7 command failure\n")
            (failed / "malloc_info_pre.xml").write_bytes(b"")
            (failed / "exit_status.txt").write_text("bench_rc=NA\ncontroller_rc=1\n")
            manifest = {"verdict": "PASS", "fixture_not_board_evidence": True,
                "archive_sha256": hashlib.sha256((root / "G4_trim_r1.tar.gz").read_bytes()).hexdigest(),
                "files": {file.relative_to(root / "raw").as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
                          for file in failed.iterdir()}}
            (root / "G4_trim_r1.integrity.json").write_text(json.dumps(manifest))

            output = root / "public_stopped_fixture"
            with contextlib.redirect_stdout(io.StringIO()) as log:
                publisher.publish(root, output)
            self.assertIn("cells=18 release_pairs=330; matrix=STOP; no Demo summaries", log.getvalue())
            self.assertNotIn("PASS_COMPLETE_MATRIX", log.getvalue())
            self.assertEqual({file.name for file in output.iterdir()}, {"completed_points.json", "completed_cycles.tsv"})
            self.assertFalse((output / "summary.tsv").exists())
            self.assertFalse((output / "gst_comparison.json").exists())

            source = json.loads((output / "completed_points.json").read_text())
            self.assertEqual(source["verdict"], "STOP_INCOMPLETE_MATRIX")
            self.assertEqual(source["execution"]["verdict"], "STOP")
            self.assertEqual(len(source["points"]), 330)
            expected_cells = receipt["completed_cells"]
            self.assertEqual(list(source["cell_health"]), expected_cells)
            self.assertEqual(list(source["pull_manifests"]), expected_cells)
            self.assertFalse(any(point["id"].startswith("G4_") for point in source["points"]))
            self.assertEqual(source["failed_cell_manifest"], manifest)
            zero = source["failed_cell_files"]["G4_trim_r1/malloc_info_pre.xml"]
            self.assertEqual(zero, {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()})
            self.assertEqual(source["points"][0]["pre"], publisher.ANALYSIS.read_point(root / "raw/G1_none_r1/points/01_pre"))

            with (output / "completed_cycles.tsv").open(newline="") as stream:
                cycles = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual(len(cycles), 330)
            self.assertEqual({row["group"] for row in cycles}, {"G1", "G2", "G3"})
            self.assertEqual(list(dict.fromkeys(row["id"] for row in cycles)), expected_cells)
            expected = root / "frozen_partial_fixture.tsv"
            publisher.ANALYSIS.write_tsv(expected, publisher.ANALYSIS.analyze(root / "raw", publisher.completed_contract(receipt)))
            self.assertEqual((output / "completed_cycles.tsv").read_bytes(), expected.read_bytes())
            before = {file.name: file.read_bytes() for file in output.iterdir()}
            self.assertTrue(all(b"PASS_COMPLETE_MATRIX" not in data for data in before.values()))
            with self.assertRaisesRegex(ValueError, "refuse to overwrite"):
                publisher.publish(root, output)
            self.assertEqual({file.name: file.read_bytes() for file in output.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
