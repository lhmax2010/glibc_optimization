import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a = load("analyze_system_level")
b = load("build_observer")


class FrozenDerivation(unittest.TestCase):
    def point(self):
        return dict(pid=4, starttime=9, start_ns=100, end_ns=200, VmRSS=8192, heap_kib=4096,
                    other_kib=2048, total_pd_kib=6152, MemAvailable=10240, MemFree=1024,
                    Cached=2048, memps_heap_pdata_kib=4096, memps_all_pdata_kib=6152,
                    minflt=100, majflt=0, zram=[0, 0, 0])

    def pair(self):
        pre = self.point()
        post = {**pre, "start_ns": 300, "end_ns": 400, "VmRSS": 4096, "heap_kib": 2048,
                "MemAvailable": 12288}
        return pre, post

    def test_absolute_units_and_denominators(self):
        out = a.derive(*self.pair())
        self.assertEqual(out["rss_drop_mib"], 4)
        self.assertEqual(out["rss_drop_mb"], 4.194304)
        self.assertEqual(out["rss_drop_pct"], 50)
        self.assertEqual(out["heap_drop_pct"], 50)
        self.assertEqual(out["memavailable_delta_kib"], 2048)

    def test_negative_effect_not_clamped(self):
        pre, post = self.pair()
        post["VmRSS"] = 16384
        self.assertEqual(a.derive(pre, post)["rss_drop_pct"], -100)

    def test_bad_identity_time_zram_faults_rejected(self):
        for key, val in (("pid", 5), ("starttime", 10), ("start_ns", 0),
                         ("zram", [1, 0, 0]), ("majflt", 1), ("minflt", 0)):
            pre, post = self.pair()
            post[key] = val
            with self.subTest(key=key), self.assertRaises(ValueError):
                a.derive(pre, post)

    def test_none_pairing_and_g4_na(self):
        rows = [dict(group="G1", arm="none", rep=1, cycle=1, memavailable_delta_kib=600),
                dict(group="G1", arm="trim", rep=1, cycle=1, memavailable_delta_kib=400),
                dict(group="G4", arm="trim", rep=1, cycle=1, memavailable_delta_kib=400)]
        out = a.pair_controls(rows)
        self.assertEqual(out[1]["memavailable_net_kib"], -200)
        self.assertIsNone(out[2]["memavailable_net_kib"])
        with self.assertRaises(ValueError):
            a.pair_controls([out[1]])

    def test_first_cycle_three_rep_median_and_range(self):
        rows = []
        for rep, delta in enumerate([100, 200, 900], 1):
            row = dict(group="G1", arm="none", rep=rep, cycle=1, **a.derive(*self.pair()),
                       memavailable_net_mb=None, trim_elapsed_ms=0)
            row["rss_drop_mb"] = delta
            rows.append(row)
        result = a.summarize(rows)[0]
        self.assertEqual(result["rss_drop_mb_median"], 200)
        self.assertEqual(result["rss_drop_mb_range"], 800)
        with self.assertRaises(ValueError):
            a.summarize(rows[:2])

    def test_contract_matrix_frozen_parameters(self):
        contract = json.loads((HERE / "contract.json").read_text())
        self.assertEqual(len(contract["cells"]), 21)
        self.assertEqual(sum(c["cycles"] for c in contract["cells"]), 333)
        self.assertEqual(contract["minimum_push_to_connect_seconds"], 600)
        for group in ("G1", "G2", "G3"):
            for arm in ("trim", "none"):
                self.assertEqual(sorted(c["rep"] for c in contract["cells"] if
                                        (c["group"], c["arm"]) == (group, arm)), [1, 2, 3])

    def test_read_point_uses_real_profile_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            fields = ["S"] + ["0"] * 49
            fields[7], fields[9], fields[19] = "100", "0", "9"
            stat = "4 (sample) " + " ".join(fields)
            files = {"stat.txt": stat, "stat_check.txt": stat,
                     "status.txt": "VmRSS: 8192 kB\n", "meminfo.txt": "MemAvailable: 100 kB\nMemFree: 40 kB\nCached: 20 kB\n",
                     "zram.txt": "0 0 0 0 0 0 0\n",
                     "memps.txt": "P(DATA) OBJECT NAME\n0 0 0 4 4 0 1000-2000 [heap]\n"}
            for name, text in files.items():
                (root / name).write_text(text)
            (root / "meta.json").write_text(json.dumps(dict(start_ns=1, end_ns=2)))
            profile = {"pid": 4, "classes": {name: {"private_dirty_bytes": 4096} for name in
                       ("glibc-heap", "other-anon", "file-backed")}, "total": {"private_dirty_bytes": 12288}}
            (root / "profile.json").write_text(json.dumps(profile))
            self.assertEqual(a.read_point(root)["heap_kib"], 4)
            profile["total"]["private_dirty_bytes"] = 0
            (root / "profile.json").write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "buckets"):
                a.read_point(root)

    def test_missing_source_evidence_cannot_complete_matrix(self):
        c = json.loads((HERE / "contract.json").read_text())["cells"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / c["id"]
            path.mkdir()
            (path / "cell.json").write_text(json.dumps({"exit_code": 0, "pid": 4, "health": {
                "oom_lmk_new": 0, "attributable_alerts_new": 0, "zram_pre": [0]*3, "zram_post": [0]*3}}))
            (path / "metrics.json").write_text(json.dumps([{"cycle": 1}, {"cycle": 2}]))
            with self.assertRaises(FileNotFoundError):
                a.analyze(root, {"cells": [c]})

    def test_gst_source_metrics_not_optional(self):
        c = dict(group="G3", arm="none", cycles=51)
        metrics = [dict(cycle=n, trim_elapsed_ns=0, next_cycle_minflt=0 if n < 51 else None,
                        next_cycle_majflt=0 if n < 51 else None, business_elapsed_ms=1.0)
                   for n in range(1, 52)]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            for filename in ("dmesg_before.txt", "dmesg_after.txt", "stability_before.tsv", "stability_after.tsv"):
                (path / filename).write_text("")
            (path / "program_stdout.txt").write_text("\n".join(
                "CYCLE_METRIC cycle=%d business_elapsed_ns=1000000 minflt=0 majflt=0\n"
                "TRIM_METRIC cycle=%d arm=none return=-1 elapsed_ns=0" % (n, n) for n in range(1, 52)))
            external = [dict(pid="4", epoch_ns="1"), dict(pid="4", epoch_ns="100")]
            with mock.patch.object(a.GST, "read_external", return_value=(external, 0)):
                a.validate_sources(path, c, dict(pid=4, first_pre_ns=2, last_post_ns=99), metrics)
                del metrics[0]["business_elapsed_ms"]
                with self.assertRaises(KeyError):
                    a.validate_sources(path, c, dict(pid=4, first_pre_ns=2, last_post_ns=99), metrics)

    def test_instrumentation_preserves_source_and_timer(self):
        source = (HERE.parents[2] / "tools/alloc_bench/alloc_bench.c").read_text()
        generated = b.instrument(source)
        original_timer = "uint64_t start = now_ns();\n    result->trim_return = malloc_trim(0);\n    result->trim_elapsed_ns = now_ns() - start;"
        self.assertIn(original_timer, generated)
        self.assertEqual(generated.count("system_measure_gate(cycle, 0)"), 1)
        self.assertEqual(generated.count("system_measure_gate(cycle, 1)"), 2)
        with self.assertRaises(ValueError):
            b.instrument(generated)


if __name__ == "__main__":
    unittest.main()
