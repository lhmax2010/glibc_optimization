#!/usr/bin/env python3
"""Frozen absolute-memory derivation. No smoothing, clamping or imputed samples."""
import argparse
import csv
import types
import json
import math
import pathlib
import re
import statistics
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
# The existing analyzer is a CLI script with an unguarded argparse footer.
# Execute only its unchanged definitions, never the CLI. This reuses its parsing
# and nearest-rank logic, instead of maintaining a second statistical implementation.
_gst_path = HERE.parent / "gst_trim_cost_20260901/analyze_gst_trim_cost.py"
_gst_source = _gst_path.read_text()
_marker = "\nparser = argparse.ArgumentParser("
if _gst_source.count(_marker) != 1:
    raise ValueError("gst analyzer definition boundary drift")
GST = types.ModuleType("gst_source")
exec(compile(_gst_source.split(_marker)[0], str(_gst_path), "exec"), GST.__dict__)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def kib_fields(text, names):
    result = {}
    for name in names:
        matches = re.findall(r"^" + re.escape(name) + r":\s+(\d+) kB$", text, re.M)
        require(len(matches) == 1, "missing/duplicate kB field " + name)
        result[name] = int(matches[0])
    return result


def proc_stat(text):
    pid = int(text.split(" (", 1)[0])
    fields = text.rsplit(")", 1)[1].split()
    return {"pid": pid, "starttime": int(fields[19]),
            "minflt": int(fields[7]), "majflt": int(fields[9])}


def read_point(path):
    meta = json.loads((path / "meta.json").read_text())
    stat = proc_stat((path / "stat.txt").read_text())
    end = proc_stat((path / "stat_check.txt").read_text())
    require((stat["pid"], stat["starttime"]) == (end["pid"], end["starttime"]),
            "process changed during capture")
    require(end["majflt"] == stat["majflt"] and end["minflt"] >= stat["minflt"], "capture-end faults")
    require(meta["end_ns"] >= meta["start_ns"], "negative capture interval")
    profile = json.loads((path / "profile.json").read_text())
    require(profile["pid"] == stat["pid"], "profile PID mismatch")
    classes = profile["classes"]
    total = profile["total"]["private_dirty_bytes"]
    require(sum(c["private_dirty_bytes"] for c in classes.values()) == total, "PD buckets != total")
    require(all(c["private_dirty_bytes"] >= 0 and c["private_dirty_bytes"] % 4096 == 0
                for c in classes.values()), "invalid page-sized PD buckets")
    result = {**stat, **meta}
    result.update(kib_fields((path / "status.txt").read_text(), ["VmRSS"]))
    result.update(kib_fields((path / "meminfo.txt").read_text(), ["MemAvailable", "MemFree", "Cached"]))
    result.update(heap_kib=classes["glibc-heap"]["private_dirty_bytes"] // 1024,
                  other_kib=classes["other-anon"]["private_dirty_bytes"] // 1024,
                  total_pd_kib=total // 1024)
    zram = [int(x) for x in (path / "zram.txt").read_text().split()]
    require(len(zram) >= 3 and all(x >= 0 for x in zram), "invalid zram counters")
    result["zram"] = zram[:3]
    memps = (path / "memps.txt").read_text()
    require("P(DATA)" in memps and "OBJECT NAME" in memps, "memps format missing")
    memps_heap = 0
    memps_total = 0
    mappings = 0
    for line in memps.splitlines():
        cols = line.split()
        if len(cols) >= 7 and all(x.isdigit() for x in cols[:6]) and re.fullmatch(r"[0-9a-f]+-[0-9a-f]+", cols[6]):
            mappings += 1
            memps_total += int(cols[3])
            if cols[-1] == "[heap]":
                memps_heap += int(cols[3])
    require(mappings > 0, "memps has no mappings")
    result.update(memps_heap_pdata_kib=memps_heap, memps_all_pdata_kib=memps_total)
    return result


def validate_sources(path, cell, meta, metrics):
    """Require actual inputs, not self-asserted completion/counts from a controller."""
    before = (path / "dmesg_before.txt").read_text().splitlines()
    after = (path / "dmesg_after.txt").read_text().splitlines()
    increment, method = GST.dmesg_increment(before, after)
    require(method == "prefix", "dmesg ring lost history: cannot validate increment")
    require(not any(re.search(r"out of memory|oom[-_ ]kill|killed process|lowmemorykiller|low memory killer", l, re.I)
                    for l in increment), "raw dmesg OOM/LMK")
    for name in ("stability_before.tsv", "stability_after.tsv"):
        require((path / name).is_file(), "missing stability snapshot")
    external, _ = GST.read_external(path / "external_1s.tsv", path / "external_sampler_meta.txt")
    require(all(int(r["pid"]) == meta["pid"] for r in external), "external PID drift")
    require(int(external[0]["epoch_ns"]) <= meta["first_pre_ns"] and
            int(external[-1]["epoch_ns"]) >= meta["last_post_ns"], "external series does not cover release windows")
    if cell["group"] in ("G1", "G2"):
        raw = json.loads((path / "result.json").read_text())
        expected = {"mode": "cyclic", "profile": cell["profile"], "threads": 4, "seed": 20260814,
                    "live_set_per_thread": 512, "idle_release_pct": 50, "release_order": "high",
                    "cycles": 2, "cycle_rise_s": 3.4, "cycle_peak_s": 4.7,
                    "release_duration_s": 19.7, "cycle_valley_s": 20.0,
                    "trim_at": "valley" if cell["arm"] == "trim" else "none"}
        require(all(raw[k] == v for k, v in expected.items()), "alloc frozen configuration drift")
        require(len(raw["cycle_data"]) == 2, "alloc source cycles")
        for m, r in zip(metrics, raw["cycle_data"]):
            require(m["cycle"] == r["cycle"] and m["trim_elapsed_ns"] == r["trim_elapsed_ns"] and
                    m["released_payload_bytes"] == r["released_payload_bytes"] > 0, "alloc source metrics mismatch")
            require(r["faults"]["rise_majflt"] == 0, "alloc rise majflt")
            for key in ("next_cycle_minflt", "next_cycle_majflt"):
                require(m[key] == (r["faults"][key] if r["cycle"] < 2 else None), "alloc source next faults")
            for stage, remote in r["malloc_info_paths"].items():
                xml = path / "xml" / pathlib.Path(remote).name
                require(ET.parse(xml).getroot().tag == "malloc", "invalid phase XML")
    elif cell["group"] == "G3":
        arm = "trim-at-loop-release" if cell["arm"] == "trim" else "none"
        cycles, trims = GST.parse_program(path / "program_stdout.txt", arm)
        for m in metrics:
            n = m["cycle"]
            require(m["business_elapsed_ms"] == cycles[n]["business_elapsed_ns"] / 1e6,
                    "missing/mismatched gst business wall")
            require(m["trim_elapsed_ns"] == trims[n]["elapsed_ns"], "gst trim source mismatch")
            require(n == 1 or cycles[n]["majflt"] == 0, "gst warm cycle majflt")
            for key, source in (("next_cycle_minflt", "minflt"), ("next_cycle_majflt", "majflt")):
                require(m[key] == (cycles[n + 1][source] if n < 51 else None), "gst source next faults")
    else:
        require(ET.parse(path / "malloc_info_pre.xml").getroot().tag == "malloc", "G4 missing M7 XML")
        require(re.search(r"\$\d+ = [01]", (path / "gdb_trim.txt").read_text()), "G4 trim result missing")
        require(meta["injection_end_ns"] > meta["injection_start_ns"], "G4 injection time")
        require(metrics[0]["trim_elapsed_ns"] == meta["injection_end_ns"] - meta["injection_start_ns"], "G4 timing mismatch")
        start = proc_stat((path / "idle_stat_start.txt").read_text())
        end = proc_stat((path / "idle_stat_end.txt").read_text())
        require((start["pid"], start["starttime"]) == (end["pid"], end["starttime"]) and
                start["pid"] == meta["pid"], "G4 idle identity")
        require(meta["idle_end_ns"] - meta["idle_start_ns"] >= 120000000000, "G4 idle window short")
        require(end["majflt"] == start["majflt"] and end["minflt"] >= start["minflt"], "G4 idle faults")


def derive(before, after):
    require((before["pid"], before["starttime"]) == (after["pid"], after["starttime"]),
            "pre/post process identity mismatch")
    require(after["start_ns"] >= before["end_ns"], "pre/post capture order invalid")
    require(before["VmRSS"] > 0 and before["heap_kib"] > 0, "zero percentage denominator")
    require(after["majflt"] == before["majflt"], "majflt validity gate")
    require(after["minflt"] >= before["minflt"], "nonmonotonic minflt")
    require(before["zram"] == after["zram"], "zram validity gate")
    out = {"pid": before["pid"], "starttime": before["starttime"]}
    for label, key in (("rss", "VmRSS"), ("heap", "heap_kib")):
        drop = before[key] - after[key]
        out.update({label + "_pre_kib": before[key], label + "_post_kib": after[key],
                    label + "_drop_kib": drop, label + "_drop_mib": drop / 1024,
                    label + "_drop_mb": drop * 1024 / 1000000,
                    label + "_drop_pct": 100 * drop / before[key]})
    for key in ("other_kib", "total_pd_kib", "MemAvailable", "MemFree", "Cached",
                "memps_heap_pdata_kib", "memps_all_pdata_kib"):
        out[key + "_pre"] = before[key]
        out[key + "_post"] = after[key]
    delta = after["MemAvailable"] - before["MemAvailable"]
    out.update(memavailable_delta_kib=delta, memavailable_delta_mib=delta / 1024,
               memavailable_delta_mb=delta * 1024 / 1000000,
               capture_minflt=after["minflt"] - before["minflt"], capture_majflt=0,
               pre_capture_ms=(before["end_ns"] - before["start_ns"]) / 1e6,
               post_capture_ms=(after["end_ns"] - after["start_ns"]) / 1e6)
    return out


def pair_controls(rows):
    index = {(r["group"], r["arm"], r["rep"], r["cycle"]): r for r in rows}
    require(len(index) == len(rows), "duplicate cell/cycle")
    for r in rows:
        r["memavailable_net_kib"] = None
        r["memavailable_net_mib"] = None
        r["memavailable_net_mb"] = None
        if r["arm"] == "trim" and r["group"] != "G4":
            control = index.get((r["group"], "none", r["rep"], r["cycle"]))
            require(control is not None, "missing matched none control")
            net = r["memavailable_delta_kib"] - control["memavailable_delta_kib"]
            r.update(memavailable_net_kib=net, memavailable_net_mib=net / 1024,
                     memavailable_net_mb=net * 1024 / 1000000)
    return rows


def summarize(rows):
    keys = sorted({(r["group"], r["arm"]) for r in rows})
    metrics = ["rss_pre_kib", "rss_post_kib", "rss_drop_mb", "rss_drop_mib", "rss_drop_pct",
               "heap_pre_kib", "heap_post_kib", "heap_drop_mb", "heap_drop_mib", "heap_drop_pct",
               "memavailable_delta_mb", "memavailable_net_mb", "trim_elapsed_ms"]
    result = []
    for group, arm in keys:
        selected = [r for r in rows if (r["group"], r["arm"], r["cycle"]) == (group, arm, 1)]
        require(sorted(r["rep"] for r in selected) == [1, 2, 3], "summary requires three repetitions")
        row = {"group": group, "arm": arm, "cycle": 1, "repetitions": 3}
        for key in metrics:
            values = [r[key] for r in selected if r[key] is not None]
            require(len(values) in (0, 3), "partially missing summary metric")
            row[key + "_median"] = statistics.median(values) if values else None
            row[key + "_range"] = max(values) - min(values) if values else None
        result.append(row)
    return result


def analyze(root, contract):
    rows = []
    g4_previous = None
    for cell in contract["cells"]:
        path = root / cell["id"]
        meta = json.loads((path / "cell.json").read_text())
        require(meta["exit_code"] == 0, "incomplete cell " + cell["id"])
        health = meta["health"]
        require(health["oom_lmk_new"] == 0 and health["attributable_alerts_new"] == 0,
                "health hard failure " + cell["id"])
        require(health["zram_pre"] == health["zram_post"], "cell zram change")
        metrics = json.loads((path / "metrics.json").read_text())
        require([r["cycle"] for r in metrics] == list(range(1, cell["cycles"] + 1)), "cycle coverage")
        validate_sources(path, cell, meta, metrics)
        for metric in metrics:
            n = metric["cycle"]
            before = read_point(path / "points" / ("%02d_pre" % n))
            after = read_point(path / "points" / ("%02d_post" % n))
            require(before["pid"] == meta["pid"], "cell PID mismatch")
            require(metric["trim_elapsed_ns"] >= 0, "negative trim duration")
            require((cell["arm"] == "none" and metric["trim_elapsed_ns"] == 0) or
                    (cell["arm"] == "trim" and metric["trim_elapsed_ns"] > 0), "trim/none sentinel")
            require(metric["next_cycle_majflt"] in (None, 0), "next cycle majflt")
            if n < cell["cycles"]:
                require(metric["next_cycle_minflt"] is not None and metric["next_cycle_minflt"] >= 0 and metric["next_cycle_majflt"] == 0,
                        "missing next-cycle costs")
            else:
                require(metric["next_cycle_minflt"] is None and metric["next_cycle_majflt"] is None,
                        "last cycle costs must be NA")
            row = {k: cell[k] for k in ("id", "group", "profile", "arm", "rep")}
            row.update(cycle=n, **derive(before, after), trim_elapsed_ms=metric["trim_elapsed_ns"] / 1e6,
                       next_cycle_minflt=metric["next_cycle_minflt"], next_cycle_majflt=metric["next_cycle_majflt"],
                       business_elapsed_ms=metric.get("business_elapsed_ms"),
                       released_payload_bytes=metric.get("released_payload_bytes"))
            if cell["group"] == "G4":
                identity = (before["pid"], before["starttime"])
                if g4_previous:
                    require(identity == g4_previous[0], "G4 identity changed across repetitions")
                    require(meta["injection_start_ns"] - g4_previous[1] >= 120000000000, "G4 injection interval short")
                g4_previous = (identity, meta["injection_start_ns"])
                idle_pre = proc_stat((path / "idle_stat_start.txt").read_text())
                idle_post = proc_stat((path / "idle_stat_end.txt").read_text())
                row["idle_120s_minflt"] = idle_post["minflt"] - idle_pre["minflt"]
                row["idle_120s_majflt"] = idle_post["majflt"] - idle_pre["majflt"]
            else:
                row["idle_120s_minflt"] = row["idle_120s_majflt"] = None
            rows.append(row)
    return pair_controls(rows)


def gst_summaries(root, rows):
    gst_rows = []
    for order, arm, rep in GST.CELLS:
        local_arm = "none" if arm == "none" else "trim"
        path = root / ("G3_%s_r%d" % (local_arm, rep))
        cycles, trims = GST.parse_program(path / "program_stdout.txt", arm)
        external, overruns = GST.read_external(path / "external_1s.tsv", path / "external_sampler_meta.txt")
        for r in rows:
            if (r["group"], r["arm"], r["rep"]) != ("G3", local_arm, rep):
                continue
            n = r["cycle"]
            gst_rows.append(dict(order=order, arm=arm, rep=rep, cycle=n,
                primary_business_sample=int(n in GST.PRIMARY_CYCLES),
                business_elapsed_ms=round(r["business_elapsed_ms"], 6), trim_return=trims[n]["return"],
                trim_elapsed_ms=round(r["trim_elapsed_ms"], 6), glibc_pd_pre_kb=r["heap_pre_kib"],
                glibc_pd_post_kb=r["heap_post_kib"], glibc_pd_reclaimed_kb=r["heap_drop_kib"],
                reclaim_pct_of_pre=round(r["heap_drop_pct"], 6), cycle_minflt=cycles[n]["minflt"],
                cycle_majflt=cycles[n]["majflt"], capture_minflt=r["capture_minflt"],
                capture_majflt=r["capture_majflt"], external_samples=len(external),
                external_overruns=overruns, exit_code=0))
    return GST.derive_cycle_summaries(gst_rows)


def write_tsv(path, rows):
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            require(all(not isinstance(x, float) or math.isfinite(x) for x in row.values()), "nonfinite result")
            writer.writerow({k: "NA" if v is None else format(v, ".6f") if isinstance(v, float) else v
                             for k, v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    a = parser.parse_args()
    contract = json.loads((HERE / "contract.json").read_text())
    rows = analyze(a.raw, contract)
    summary = summarize(rows)
    repetitions, arms, comparison = gst_summaries(a.raw, rows)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(a.output_dir / "cycles.tsv", rows)
    write_tsv(a.output_dir / "summary.tsv", summary)
    GST.write_tsv(a.output_dir / "gst_repetitions.tsv", repetitions)
    GST.write_tsv(a.output_dir / "gst_arms.tsv", arms)
    (a.output_dir / "gst_comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print("PASS complete_matrix cells=%d cycles=%d" % (len(contract["cells"]), len(rows)))


if __name__ == "__main__":
    main()
