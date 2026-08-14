#!/usr/bin/env python3
import csv
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path("<WORKSPACE>/board_results/product_plateau_probe_20260814")
RAW = ROOT / "raw"
DERIVED = ROOT / "derived"
DERIVED.mkdir(exist_ok=True)
STAGES = ["P0", "R1", "R2", "R3", "R4", "R5", "P1", "R6", "P2"]
ROUNDS = ["R1", "R2", "R3", "R4", "R5", "R6"]


def parse_time(value):
    return datetime.fromisoformat(value.replace(",", "."))


rows = []
with (RAW / "timeseries.tsv").open(newline="") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        row["sample"] = int(row["sample"])
        row["time"] = parse_time(row["timestamp"])
        for key in ("MemAvailable_kb", "zram_used_kb"):
            row[key] = int(row[key])
        if row["pid"] != "NA":
            row["pid"] = int(row["pid"])
            for key in (
                "glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb",
                "total_pd_kb", "minflt", "majflt",
            ):
                row[key] = int(row[key])
        rows.append(row)

targets = []
with (RAW / "targets.tsv").open(newline="") as stream:
    targets = list(csv.DictReader(stream, delimiter="\t"))
target_order = [row["target"] for row in targets]

by_target_stage = defaultdict(list)
by_target = defaultdict(list)
for row in rows:
    by_target_stage[(row["target"], row["stage"])].append(row)
    by_target[row["target"]].append(row)

stage_fields = [
    "target", "stage", "samples", "pid_set",
    "glibc_start_kb", "glibc_peak_kb", "glibc_end_kb",
    "other_start_kb", "other_peak_kb", "other_end_kb",
    "file_start_kb", "file_peak_kb", "file_end_kb",
]
stage_records = []
for target in target_order:
    for stage in STAGES:
        group = [row for row in by_target_stage[(target, stage)] if row["pid"] != "NA"]
        if not group:
            continue
        stage_records.append({
            "target": target,
            "stage": stage,
            "samples": len(group),
            "pid_set": ",".join(str(pid) for pid in sorted({row["pid"] for row in group})),
            "glibc_start_kb": group[0]["glibc_heap_pd_kb"],
            "glibc_peak_kb": max(row["glibc_heap_pd_kb"] for row in group),
            "glibc_end_kb": group[-1]["glibc_heap_pd_kb"],
            "other_start_kb": group[0]["other_anon_pd_kb"],
            "other_peak_kb": max(row["other_anon_pd_kb"] for row in group),
            "other_end_kb": group[-1]["other_anon_pd_kb"],
            "file_start_kb": group[0]["file_backed_pd_kb"],
            "file_peak_kb": max(row["file_backed_pd_kb"] for row in group),
            "file_end_kb": group[-1]["file_backed_pd_kb"],
        })
with (DERIVED / "stage_summary.tsv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=stage_fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(stage_records)

stage_lookup = {(row["target"], row["stage"]): row for row in stage_records}
round_fields = [
    "target", "p0_baseline_kb", "threshold_5pct_kb",
    *[f"{round_name}_glibc_peak_kb" for round_name in ROUNDS],
    *[f"{round_name}_other_peak_kb" for round_name in ROUNDS],
]
plateau_fields = [
    "target", "p0_baseline_kb", "threshold_5pct_kb", "max_round_rise_kb",
    "round_peaks_monotonic_nondecreasing", "first_plateau_pair",
    "platform_period_peak_kb", "platform_height_kb", "shape",
]
round_records = []
plateau_records = []
for target in target_order:
    p0 = stage_lookup[(target, "P0")]
    baseline = int(p0["glibc_end_kb"])
    threshold = baseline * 0.05
    glibc_peaks = [int(stage_lookup[(target, stage)]["glibc_peak_kb"]) for stage in ROUNDS]
    other_peaks = [int(stage_lookup[(target, stage)]["other_peak_kb"]) for stage in ROUNDS]
    round_record = {
        "target": target,
        "p0_baseline_kb": baseline,
        "threshold_5pct_kb": f"{threshold:.2f}",
    }
    round_record.update({f"{stage}_glibc_peak_kb": value for stage, value in zip(ROUNDS, glibc_peaks)})
    round_record.update({f"{stage}_other_peak_kb": value for stage, value in zip(ROUNDS, other_peaks)})
    round_records.append(round_record)

    max_rise = max(glibc_peaks) - baseline
    responded = max_rise >= threshold
    stable_pair_index = None
    if responded:
        first_response = next(i for i, value in enumerate(glibc_peaks) if value - baseline >= threshold)
        for i in range(max(1, first_response + 1), len(glibc_peaks)):
            if abs(glibc_peaks[i] - glibc_peaks[i - 1]) < threshold:
                stable_pair_index = i
                break
    monotonic = all(glibc_peaks[i] >= glibc_peaks[i - 1] for i in range(1, len(glibc_peaks)))
    if not responded:
        shape = "no-response"
        pair = "NA"
        pair_peak = "NA"
        height = "NA"
    elif stable_pair_index is not None:
        shape = "plateau"
        pair = f"{ROUNDS[stable_pair_index - 1]}-{ROUNDS[stable_pair_index]}"
        pair_peak_value = max(glibc_peaks[stable_pair_index - 1:])
        pair_peak = pair_peak_value
        height = pair_peak_value - baseline
    elif monotonic:
        shape = "cumulative"
        pair = "NA"
        pair_peak = "NA"
        height = "NA"
    else:
        shape = "unclassified-nonmonotonic"
        pair = "NA"
        pair_peak = "NA"
        height = "NA"
    plateau_records.append({
        "target": target,
        "p0_baseline_kb": baseline,
        "threshold_5pct_kb": f"{threshold:.2f}",
        "max_round_rise_kb": max_rise,
        "round_peaks_monotonic_nondecreasing": "yes" if monotonic else "no",
        "first_plateau_pair": pair,
        "platform_period_peak_kb": pair_peak,
        "platform_height_kb": height,
        "shape": shape,
    })

for filename, fields, records in (
    ("round_peaks.tsv", round_fields, round_records),
    ("plateau_analysis.tsv", plateau_fields, plateau_records),
):
    with (DERIVED / filename).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(records)

pid_changes = []
for target in target_order:
    last_pid = None
    for row in by_target[target]:
        if row["pid"] != last_pid:
            pid_changes.append({
                "target": target,
                "sample": row["sample"],
                "stage": row["stage"],
                "timestamp": row["timestamp"],
                "old_pid": "NA" if last_pid is None else last_pid,
                "new_pid": row["pid"],
            })
            last_pid = row["pid"]
with (DERIVED / "pid_changes.tsv").open("w", newline="") as stream:
    fields = list(pid_changes[0])
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(pid_changes)

keys = []
with (RAW / "key_timeline.tsv").open(newline="") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        row["lateness_ms"] = float(row["lateness_ms"])
        keys.append(row)
with (DERIVED / "key_lateness_by_round.tsv").open("w", newline="") as stream:
    fields = ["round", "keys", "min_ms", "median_ms", "max_ms"]
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    for round_name in ROUNDS:
        values = [row["lateness_ms"] for row in keys if row["round"] == round_name]
        writer.writerow({
            "round": round_name,
            "keys": len(values),
            "min_ms": f"{min(values):.3f}",
            "median_ms": f"{statistics.median(values):.3f}",
            "max_ms": f"{max(values):.3f}",
        })

anchor = by_target[target_order[0]]
deltas = [(anchor[i]["time"] - anchor[i - 1]["time"]).total_seconds() for i in range(1, len(anchor))]
with (DERIVED / "quality.txt").open("w") as stream:
    stream.write(f"data_rows={len(rows)}\n")
    stream.write(f"targets={len(by_target)}\n")
    stream.write(f"pid_na_rows={sum(row['pid'] == 'NA' for row in rows)}\n")
    stream.write(f"sample_delta_min_seconds={min(deltas):.6f}\n")
    stream.write(f"sample_delta_median_seconds={statistics.median(deltas):.6f}\n")
    stream.write(f"sample_delta_max_seconds={max(deltas):.6f}\n")
    stream.write(f"sample_deltas_gt_2_1_seconds={sum(value > 2.1 for value in deltas)}\n")
    stream.write(f"sample_deltas_gt_3_seconds={sum(value > 3 for value in deltas)}\n")
    stream.write(f"MemAvailable_min_kb={min(row['MemAvailable_kb'] for row in rows)}\n")
    stream.write(f"MemAvailable_max_kb={max(row['MemAvailable_kb'] for row in rows)}\n")
    stream.write(f"zram_used_min_kb={min(row['zram_used_kb'] for row in rows)}\n")
    stream.write(f"zram_used_max_kb={max(row['zram_used_kb'] for row in rows)}\n")
    stream.write(f"key_lateness_min_ms={min(row['lateness_ms'] for row in keys):.3f}\n")
    stream.write(f"key_lateness_median_ms={statistics.median(row['lateness_ms'] for row in keys):.3f}\n")
    stream.write(f"key_lateness_max_ms={max(row['lateness_ms'] for row in keys):.3f}\n")
