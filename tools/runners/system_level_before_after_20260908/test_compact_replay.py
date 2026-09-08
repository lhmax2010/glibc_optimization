"""Host-only compact input/replay gates; no board commands or new measurements."""
import copy
import contextlib
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_compact as replay
import publish_measurement as publisher


class CompactReplay(unittest.TestCase):
    DERIVED = ("cycles.tsv", "summary.tsv", "gst_repetitions.tsv", "gst_arms.tsv", "gst_comparison.json")

    def source(self):
        entries = []
        for cell in replay.CONTRACT["cells"]:
            for cycle in range(1, cell["cycles"] + 1):
                pre = dict(pid=4, starttime=9, start_ns=100, end_ns=200, VmRSS=8231,
                    heap_kib=4096, other_kib=2048, total_pd_kib=6152, MemAvailable=10240,
                    MemFree=1024, Cached=2048, memps_heap_pdata_kib=4096, memps_all_pdata_kib=6152,
                    minflt=100, majflt=0, zram=[0, 0, 0])
                post = {**pre, "start_ns": 300, "end_ns": 400, "VmRSS": 4097, "heap_kib": 2048,
                        "MemAvailable": 12288 if cell["arm"] == "none" else 11264}
                entry = {"id": cell["id"], "cycle": cycle, "pre": pre, "post": post,
                    "metric": {"cycle": cycle, "trim_elapsed_ns": 1000001 if cell["arm"] == "trim" else 0,
                        "next_cycle_minflt": 7 if cycle < cell["cycles"] else None,
                        "next_cycle_majflt": 0 if cycle < cell["cycles"] else None},
                    "idle_pre": {"minflt": 1, "majflt": 0}, "idle_post": {"minflt": 2, "majflt": 0}}
                entries.append(entry)
        return {"points": entries}

    def test_exact_full_matrix_reuses_unrounded_frozen_point_derivation(self):
        source = self.source()
        rows = replay.derive_rows(source)
        self.assertEqual(len(rows), 333)
        expected = replay.ANALYSIS.derive(source["points"][0]["pre"], source["points"][0]["post"])
        for key, value in expected.items():
            self.assertEqual(rows[0][key], value)
        self.assertNotEqual(rows[0]["rss_drop_pct"], round(rows[0]["rss_drop_pct"], 6))
        trim = next(row for row in rows if row["group"] == "G1" and row["arm"] == "trim")
        self.assertEqual(trim["memavailable_net_kib"], -1024)
        self.assertEqual(trim["trim_elapsed_ms"], 1.000001)
        daemon = rows[-1]
        self.assertEqual(daemon["idle_120s_minflt"], 1)
        self.assertIsNone(daemon["memavailable_net_mb"])
        self.assertEqual(len(replay.ANALYSIS.summarize(rows)), 7)

    def test_missing_duplicate_reordered_or_mismatched_cycles_rejected(self):
        for mode in ("missing", "duplicate", "reorder", "metric"):
            source = self.source()
            if mode == "missing": source["points"].pop()
            elif mode == "duplicate": source["points"][1] = source["points"][0]
            elif mode == "reorder": source["points"].reverse()
            else: source["points"][0]["metric"]["cycle"] = 9
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                replay.derive_rows(source)

    def test_point_identity_fault_zram_validation_not_bypassed(self):
        for key, value in (("pid", 5), ("majflt", 1), ("zram", [1, 0, 0])):
            source = self.source()
            source["points"][0]["post"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                replay.derive_rows(source)

    def test_incomplete_or_unclean_receipt_cannot_publish(self):
        for verdict, cleanup in (("STOP", "PASS"), ("PASS_COMPLETE_MATRIX", "FAIL")):
            with self.subTest(verdict=verdict, cleanup=cleanup), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                (root / "execution.json").write_text(json.dumps({"verdict": verdict, "cleanup": cleanup}))
                output = root / "public"
                with mock.patch.object(publisher.ANALYSIS, "analyze") as analyze:
                    with self.assertRaisesRegex(ValueError, "must not publish"):
                        publisher.publish(root, output)
                    analyze.assert_not_called()
                self.assertFalse(output.exists())

    @staticmethod
    def stat(point):
        fields = ["S"] + ["0"] * 49
        fields[7], fields[9], fields[19] = str(point["minflt"]), str(point["majflt"]), str(point["starttime"])
        return "%d (explicit-host-fixture) %s\n" % (point["pid"], " ".join(fields))

    def write_point(self, directory, point):
        directory.mkdir(parents=True)
        classes = {"glibc-heap": point["heap_kib"], "other-anon": point["other_kib"],
                   "file-backed": point["total_pd_kib"] - point["heap_kib"] - point["other_kib"]}
        profile = {"pid": point["pid"], "classes": {name: {"private_dirty_bytes": value * 1024}
                   for name, value in classes.items()}, "total": {"private_dirty_bytes": point["total_pd_kib"] * 1024}}
        files = {"meta.json": json.dumps({key: point[key] for key in ("start_ns", "end_ns")}),
            "stat.txt": self.stat(point), "stat_check.txt": self.stat(point),
            "status.txt": "VmRSS: %d kB\n" % point["VmRSS"],
            "profile.json": json.dumps(profile),
            "meminfo.txt": "".join("%s: %d kB\n" % (key, point[key]) for key in ("MemAvailable", "MemFree", "Cached")),
            "zram.txt": " ".join(map(str, point["zram"])) + "\n",
            "memps.txt": "P(DATA) OBJECT NAME\n0 0 0 %d 0 0 1000-2000 [heap]\n0 0 0 %d 0 0 3000-4000 [anon]\n" %
                (point["memps_heap_pdata_kib"], point["memps_all_pdata_kib"] - point["memps_heap_pdata_kib"])}
        for name, value in files.items():
            (directory / name).write_text(value)

    def frozen_fixture(self, root):
        """Build clearly labelled artificial raw input, never repository evidence.

        Run the actual frozen analyzer, actual point parser and actual GST parser
        on it.  This is an integration fixture, not fabricated board observations.
        """
        raw = root / "raw"
        source = self.source()
        for cell in replay.CONTRACT["cells"]:
            path = raw / cell["id"]
            path.mkdir(parents=True)
            entries = [entry for entry in source["points"] if entry["id"] == cell["id"]]
            metrics, program = [], []
            for entry in entries:
                metric = entry["metric"]
                if cell["group"] in ("G1", "G2"):
                    metric["released_payload_bytes"] = 4096
                elif cell["group"] == "G3":
                    metric["business_elapsed_ms"] = 1.234567
                    arm = "none" if cell["arm"] == "none" else "trim-at-loop-release"
                    program.append("CYCLE_METRIC cycle=%d business_elapsed_ns=1234567 minflt=7 majflt=0" % entry["cycle"])
                    program.append("TRIM_METRIC cycle=%d arm=%s return=%d elapsed_ns=%d" %
                                   (entry["cycle"], arm, -1 if cell["arm"] == "none" else 1, metric["trim_elapsed_ns"]))
                metrics.append(metric)
                for phase in ("pre", "post"):
                    self.write_point(path / "points" / ("%02d_%s" % (entry["cycle"], phase)), entry[phase])
            for when in ("before", "after"):
                (path / ("dmesg_" + when + ".txt")).write_text("[0.0] explicit host fixture only\n")
                (path / ("stability_" + when + ".tsv")).write_text("remote_path\tsize\tmtime_epoch\tsha256\n")
            (path / "external_1s.tsv").write_text("sample\ttimestamp\tepoch_ns\telapsed_s\tpid\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\n"
                "0\tHOST_FIXTURE_ONLY\t1\t0\t4\t4096\t2048\t8\t6152\t100\t0\n"
                "1\tHOST_FIXTURE_ONLY\t1000000001\t1\t4\t4096\t2048\t8\t6152\t100\t0\n")
            (path / "external_sampler_meta.txt").write_text("RC=0\nDONE_EXTERNAL_SAMPLER\nsamples=2\ndeadline_overruns=0\n")
            meta = {"fixture_not_board_evidence": True, "pid": 4, "exit_code": 0,
                    "first_pre_ns": entries[0]["pre"]["start_ns"], "last_post_ns": entries[-1]["post"]["end_ns"],
                    "health": {"oom_lmk_new": 0, "attributable_alerts_new": 0, "zram_pre": [0, 0, 0], "zram_post": [0, 0, 0]}}
            if cell["group"] in ("G1", "G2"):
                result = {"mode": "cyclic", "profile": cell["profile"], "threads": 4, "seed": 20260814,
                    "live_set_per_thread": 512, "idle_release_pct": 50, "release_order": "high",
                    "cycles": 2, "cycle_rise_s": 3.4, "cycle_peak_s": 4.7, "release_duration_s": 19.7,
                    "cycle_valley_s": 20.0, "trim_at": "valley" if cell["arm"] == "trim" else "none", "cycle_data": []}
                for metric in metrics:
                    result["cycle_data"].append({"cycle": metric["cycle"], "trim_elapsed_ns": metric["trim_elapsed_ns"],
                        "released_payload_bytes": metric["released_payload_bytes"], "faults": {"rise_majflt": 0,
                        "next_cycle_minflt": metric["next_cycle_minflt"], "next_cycle_majflt": metric["next_cycle_majflt"]},
                        "malloc_info_paths": {"fixture": "fixture.xml"}})
                (path / "xml").mkdir()
                (path / "xml/fixture.xml").write_text('<malloc version="1"/>\n')
                (path / "result.json").write_text(json.dumps(result))
            elif cell["group"] == "G3":
                (path / "program_stdout.txt").write_text("\n".join(program) + "\n")
            else:
                start = cell["rep"] * 200_000_000_000
                meta.update(injection_start_ns=start, injection_end_ns=start + metrics[0]["trim_elapsed_ns"],
                            idle_start_ns=start + 10_000_000, idle_end_ns=start + 120_010_000_000)
                (path / "malloc_info_pre.xml").write_text('<malloc version="1"/>\n')
                (path / "gdb_trim.txt").write_text("HOST FIXTURE ONLY\n$1 = 1\n")
                for phase in ("pre", "post"):
                    entry = entries[0]
                    point = {"pid": 4, "starttime": 9, **entry["idle_" + phase]}
                    (path / ("idle_stat_" + ("start" if phase == "pre" else "end") + ".txt")).write_text(self.stat(point))
            (path / "cell.json").write_text(json.dumps(meta))
            (path / "metrics.json").write_text(json.dumps(metrics))
            (path / "fixture_original.txt").write_text("HOST_FIXTURE_ONLY original pull member\n")
            manifest = {file.relative_to(raw).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
                        for file in path.rglob("*") if file.is_file() and file.name not in ("cell.json", "metrics.json")}
            # Identity-only archive fixture: deliberately NOT a real tarball,
            # never a board artifact and never passed to a tar extraction path.
            archive = root / (cell["id"] + ".tar.gz")
            archive.write_bytes(b"HOST_FIXTURE_ONLY archive identity, not a tarball\n" + cell["id"].encode() + b"\n")
            (root / (cell["id"] + ".integrity.json")).write_text(json.dumps({"verdict": "PASS", "files": manifest,
                        "fixture_not_board_evidence": True, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}))
        (root / "execution.json").write_text(json.dumps({"verdict": "PASS_COMPLETE_MATRIX", "cleanup": "PASS",
            "fixture_not_board_evidence": True, "completed_cells": [cell["id"] for cell in replay.CONTRACT["cells"]]}))
        rows = replay.ANALYSIS.analyze(raw, replay.CONTRACT)
        repetitions, arms, comparison = replay.ANALYSIS.gst_summaries(raw, rows)
        derived = root / "derived"
        derived.mkdir()
        replay.ANALYSIS.write_tsv(derived / "cycles.tsv", rows)
        replay.ANALYSIS.write_tsv(derived / "summary.tsv", replay.ANALYSIS.summarize(rows))
        replay.ANALYSIS.GST.write_tsv(derived / "gst_repetitions.tsv", repetitions)
        replay.ANALYSIS.GST.write_tsv(derived / "gst_arms.tsv", arms)
        (derived / "gst_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
        return source, rows

    def test_complete_publisher_and_replay_match_all_five_frozen_outputs(self):
        with tempfile.TemporaryDirectory(prefix="compact-fixture-only-") as directory:
            root = pathlib.Path(directory)
            source, expected_rows = self.frozen_fixture(root)
            output = root / "public-fixture"
            original = replay.ANALYSIS.GST.derive_cycle_summaries
            with mock.patch.object(replay.ANALYSIS.GST, "derive_cycle_summaries", wraps=original) as derive, \
                 contextlib.redirect_stdout(io.StringIO()) as log:
                publisher.publish(root, output)
                # The publisher captures input at the canonical function boundary,
                # and both publication/replay still call that unchanged function.
                self.assertGreaterEqual(derive.call_count, 2)
                canonical = copy.deepcopy(derive.call_args_list[0].args[0])
            self.assertIs(replay.ANALYSIS.GST.derive_cycle_summaries, original)
            self.assertEqual(len(canonical), 306)
            self.assertIn("cmp=5 cells=21 cycles=333", log.getvalue())
            expected_gst = root / "canonical_fixture.tsv"
            replay.ANALYSIS.GST.write_tsv(expected_gst, canonical)
            self.assertEqual((output / "gst_cycles.tsv").read_bytes(), expected_gst.read_bytes())
            serialized = json.loads((output / "point_source.json").read_text())
            self.assertEqual(len(serialized["points"]), 333)
            self.assertEqual(serialized["points"][0]["pre"], source["points"][0]["pre"])
            self.assertEqual(replay.derive_rows(serialized), expected_rows)
            self.assertNotEqual(expected_rows[0]["rss_drop_pct"], round(expected_rows[0]["rss_drop_pct"], 6))
            point = root / "raw/G1_none_r1/points/01_pre"
            self.assertEqual(serialized["points"][0]["raw_point_sha256"]["pre"],
                             {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in point.iterdir()})
            rebuilt = root / "rebuilt-fixture"
            self.assertEqual(replay.replay(serialized, output / "gst_cycles.tsv", rebuilt), (333, 7))
            for name in self.DERIVED:
                with self.subTest(file=name):
                    self.assertEqual((root / "derived" / name).read_bytes(), (output / name).read_bytes())
                    self.assertEqual((root / "derived" / name).read_bytes(), (rebuilt / name).read_bytes())

    def test_publisher_missing_raw_cell_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="missing-cell-fixture-") as directory:
            root = pathlib.Path(directory)
            (root / "execution.json").write_text(json.dumps({"verdict": "PASS_COMPLETE_MATRIX", "cleanup": "PASS"}))
            output = root / "public-fixture"
            with self.assertRaises(FileNotFoundError):
                publisher.publish(root, output)
            self.assertFalse(output.exists())

    def test_publisher_restores_canonical_gst_function_if_statistics_fail(self):
        with tempfile.TemporaryDirectory(prefix="compact-failure-fixture-") as directory:
            root = pathlib.Path(directory)
            self.frozen_fixture(root)
            output = root / "public-fixture"
            with mock.patch.object(replay.ANALYSIS.GST, "derive_cycle_summaries", side_effect=ValueError("fixture statistic failure")) as original:
                with self.assertRaisesRegex(ValueError, "fixture statistic failure"):
                    publisher.publish(root, output)
                self.assertIs(replay.ANALYSIS.GST.derive_cycle_summaries, original)
            self.assertFalse(output.exists())

    def test_each_derived_byte_mismatch_leaves_no_partial_publication(self):
        with tempfile.TemporaryDirectory(prefix="compact-atomic-fixture-") as directory:
            root = pathlib.Path(directory)
            self.frozen_fixture(root)
            output = root / "public-fixture"
            for name in self.DERIVED:
                with self.subTest(file=name):
                    path = root / "derived" / name
                    original = path.read_bytes()
                    path.write_bytes(original + b"HOST_FIXTURE_MISMATCH_ONLY\n")
                    try:
                        with self.assertRaisesRegex(ValueError, "compact/full derivation byte mismatch"):
                            publisher.publish(root, output)
                        self.assertFalse(output.exists())
                        self.assertEqual(list(root.glob(".system-publication-*")), [])
                    finally:
                        path.write_bytes(original)

    def test_publisher_never_overwrites_existing_public_directory(self):
        with tempfile.TemporaryDirectory(prefix="compact-existing-fixture-") as directory:
            root = pathlib.Path(directory)
            output = root / "existing-fixture"
            output.mkdir()
            sentinel = output / "preserve.txt"
            sentinel.write_text("existing fixture content\n")
            with mock.patch.object(publisher, "publish_to_staging") as staged:
                with self.assertRaisesRegex(ValueError, "refuse to overwrite"):
                    publisher.publish(root, output)
                staged.assert_not_called()
            self.assertEqual(sentinel.read_text(), "existing fixture content\n")

    def test_pull_identity_binding_rejects_tamper_missing_symlink_and_unregistered_point(self):
        with tempfile.TemporaryDirectory(prefix="compact-binding-fixture-") as directory:
            root = pathlib.Path(directory)
            self.frozen_fixture(root)
            name = "G1_none_r1"
            manifest_path = root / (name + ".integrity.json")
            baseline_manifest = json.loads(manifest_path.read_text())
            original = root / "raw" / name / "fixture_original.txt"
            original_bytes = original.read_bytes()
            point = root / "raw" / name / "points/01_pre/meta.json"
            point_bytes = point.read_bytes()
            archive = root / (name + ".tar.gz")
            archive_bytes = archive.read_bytes()
            external = root / "outside_original_fixture.txt"
            external.write_bytes(original_bytes)
            external_archive = root / "outside_archive_fixture.txt"
            external_archive.write_bytes(archive_bytes)
            point_parent = point.parent
            relocated_point = root / "outside_point_fixture"
            for mutation in ("bad_verdict", "original_tamper", "original_missing", "original_symlink",
                             "point_format_tamper", "point_parent_symlink", "point_unregistered",
                             "archive_tamper", "archive_missing", "archive_symlink",
                             "unsafe_parent_path", "other_cell_path", "absolute_path"):
                with self.subTest(mutation=mutation):
                    manifest = copy.deepcopy(baseline_manifest)
                    output = root / ("public_fixture_" + mutation)
                    if mutation == "bad_verdict":
                        manifest["verdict"] = "FAIL"
                    elif mutation == "original_tamper":
                        original.write_bytes(original_bytes + b"FIXTURE_CHANGED\n")
                    elif mutation == "original_missing":
                        original.unlink()
                    elif mutation == "original_symlink":
                        original.unlink()
                        original.symlink_to(external)
                    elif mutation == "point_format_tamper":
                        # Parsed numbers are identical and five derived files
                        # still agree: only the raw-byte binding can reject this.
                        point.write_text(json.dumps(json.loads(point_bytes), indent=2) + "\n")
                    elif mutation == "point_unregistered":
                        del manifest["files"][name + "/points/01_pre/meta.json"]
                    elif mutation == "point_parent_symlink":
                        point_parent.rename(relocated_point)
                        point_parent.symlink_to(relocated_point, target_is_directory=True)
                    elif mutation == "archive_tamper":
                        archive.write_bytes(archive_bytes + b"FIXTURE_CHANGED\n")
                    elif mutation == "archive_missing":
                        archive.unlink()
                    elif mutation == "archive_symlink":
                        archive.unlink()
                        archive.symlink_to(external_archive)
                    else:
                        unsafe = {"unsafe_parent_path": name + "/../outside_original_fixture.txt",
                                  "other_cell_path": "G2_none_r1/fixture_original.txt",
                                  "absolute_path": str(external)}[mutation]
                        manifest["files"][unsafe] = hashlib.sha256(original_bytes).hexdigest()
                    manifest_path.write_text(json.dumps(manifest))
                    try:
                        with self.assertRaises((ValueError, OSError)):
                            publisher.publish(root, output)
                        self.assertFalse(output.exists())
                        self.assertEqual(list(root.glob(".system-publication-*")), [])
                    finally:
                        if original.is_symlink():
                            original.unlink()
                        if point_parent.is_symlink():
                            point_parent.unlink()
                            relocated_point.rename(point_parent)
                        if archive.is_symlink():
                            archive.unlink()
                        original.write_bytes(original_bytes)
                        point.write_bytes(point_bytes)
                        archive.write_bytes(archive_bytes)
                        manifest_path.write_text(json.dumps(baseline_manifest))
            # The successful full publication test deliberately leaves host
            # generated cell.json / metrics.json outside the pull manifest.
            self.assertNotIn(name + "/cell.json", baseline_manifest["files"])
            self.assertNotIn(name + "/metrics.json", baseline_manifest["files"])


if __name__ == "__main__":
    unittest.main()
