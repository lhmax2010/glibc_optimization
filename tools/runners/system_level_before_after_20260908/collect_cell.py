#!/usr/bin/env python3
"""Host-side transcription with source validation, including raw health evidence."""
import argparse
import csv
import importlib.util
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("system_analysis", HERE / "analyze_system_level.py")
ANALYSIS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ANALYSIS)


def snapshots(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    return {r["remote_path"]: r for r in rows}


def collect(path, cell):
    pid = int((path / "pid.txt").read_text())
    status = dict(line.split("=", 1) for line in (path / "exit_status.txt").read_text().splitlines())
    ANALYSIS.require(status == {"bench_rc": "0", "controller_rc": "0"}, "cell exit failure")
    before = (path / "dmesg_before.txt").read_text().splitlines()
    after = (path / "dmesg_after.txt").read_text().splitlines()
    lines, method = ANALYSIS.GST.dmesg_increment(before, after)
    ANALYSIS.require(method == "prefix", "dmesg history lost")
    bad = [l for l in lines if re.search(r"out of memory|oom[-_ ]kill|killed process|lowmemorykiller|low memory killer", l, re.I)]
    (path / "dmesg_increment.txt").write_text("\n".join(lines) + "\n")
    zpre = [int(x) for x in (path / "zram_before.txt").read_text().split()[:3]]
    zpost = [int(x) for x in (path / "zram_after.txt").read_text().split()[:3]]
    ANALYSIS.require(len(zpre) == len(zpost) == 3 and min(zpre + zpost) >= 0,
                     "zram snapshots require three nonnegative counters")
    start, end = snapshots(path / "stability_before.tsv"), snapshots(path / "stability_after.tsv")
    changed = [name for name in end if name not in start or end[name] != start[name]]
    # Classifications must be produced from pulled archives by the executor. No
    # default empty list when a new/changed archive exists.
    attributed = json.loads((path / "alert_attribution.json").read_text()) if changed else []
    ANALYSIS.require(sorted(r["remote_path"] for r in attributed) == sorted(changed), "unattributed alert")
    own = [r for r in attributed if r["attributable_to_this_round"]]
    health = {"oom_lmk_new": len(bad), "attributable_alerts_new": len(own), "zram_pre": zpre, "zram_post": zpost,
              "stability_count_pre": len(start), "stability_count_post": len(end), "changed_archives": changed}
    first = json.loads((path / "points/01_pre/meta.json").read_text())
    last = json.loads((path / "points" / ("%02d_post" % cell["cycles"]) / "meta.json").read_text())
    meta = {"pid": pid, "exit_code": 0, "health": health, "first_pre_ns": first["start_ns"], "last_post_ns": last["end_ns"]}
    metrics = []
    if cell["group"] in ("G1", "G2"):
        raw = json.loads((path / "result.json").read_text())
        for r in raw["cycle_data"]:
            metrics.append({"cycle": r["cycle"], "trim_elapsed_ns": r["trim_elapsed_ns"],
                            "released_payload_bytes": r["released_payload_bytes"],
                            "next_cycle_minflt": r["faults"]["next_cycle_minflt"] if r["cycle"] < 2 else None,
                            "next_cycle_majflt": r["faults"]["next_cycle_majflt"] if r["cycle"] < 2 else None})
    elif cell["group"] == "G3":
        cycles, trims = ANALYSIS.GST.parse_program(path / "program_stdout.txt", "none" if cell["arm"] == "none" else "trim-at-loop-release")
        for n in range(1, 52):
            metrics.append({"cycle": n, "trim_elapsed_ns": trims[n]["elapsed_ns"],
                            "business_elapsed_ms": cycles[n]["business_elapsed_ns"] / 1e6,
                            "next_cycle_minflt": cycles[n+1]["minflt"] if n < 51 else None,
                            "next_cycle_majflt": cycles[n+1]["majflt"] if n < 51 else None})
    else:
        for name in ("injection_start_ns", "injection_end_ns", "idle_start_ns", "idle_end_ns"):
            meta[name] = int((path / (name + ".txt")).read_text())
        metrics.append({"cycle": 1, "trim_elapsed_ns": meta["injection_end_ns"] - meta["injection_start_ns"],
                        "next_cycle_minflt": None, "next_cycle_majflt": None})
    (path / "cell.json").write_text(json.dumps(meta, indent=2) + "\n")
    (path / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    ANALYSIS.require(not bad and not own and zpre == zpost, "health hard failure")
    ANALYSIS.validate_sources(path, cell, meta, metrics)
    for m in metrics:
        n = m["cycle"]
        pre = ANALYSIS.read_point(path / "points" / ("%02d_pre" % n))
        post = ANALYSIS.read_point(path / "points" / ("%02d_post" % n))
        ANALYSIS.derive(pre, post)
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cell", required=True)
    p.add_argument("--raw", type=pathlib.Path, required=True)
    a = p.parse_args()
    contract = json.loads((HERE / "contract.json").read_text())
    cell = next(c for c in contract["cells"] if c["id"] == a.cell)
    print(json.dumps(collect(a.raw, cell), indent=2))


if __name__ == "__main__":
    main()
