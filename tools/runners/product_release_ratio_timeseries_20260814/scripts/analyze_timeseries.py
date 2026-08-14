#!/usr/bin/env python3
import csv
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path("<WORKSPACE>/board_results/product_release_ratio_timeseries_20260814")
RAW = ROOT / "raw"
DERIVED = ROOT / "derived"
DERIVED.mkdir(exist_ok=True)


def parse_time(value):
    return datetime.fromisoformat(value.replace(",", "."))


def median_int(values):
    return int(round(statistics.median(values)))


baseline_by_pid = {}
baseline_by_comm = defaultdict(list)
with (RAW / "all_process_baseline.tsv").open(newline="") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        row["comm"] = row["comm"].strip()
        row["pid"] = int(row["pid"])
        for key in ("glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb", "total_pd_kb"):
            row[key] = int(row[key])
        baseline_by_pid[row["pid"]] = row
        baseline_by_comm[row["comm"]].append(row)

rows = []
with (RAW / "timeseries.tsv").open(newline="") as stream:
    for row in csv.DictReader(stream, delimiter="\t"):
        row["sample"] = int(row["sample"])
        row["time"] = parse_time(row["timestamp"])
        for key in ("MemAvailable_kb", "zram_used_kb"):
            row[key] = int(row[key])
        if row["pid"] != "NA":
            row["pid"] = int(row["pid"])
            for key in ("glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb", "total_pd_kb", "minflt", "majflt"):
                row[key] = int(row[key])
        rows.append(row)

start_time = rows[0]["time"]
by_target = defaultdict(list)
for row in rows:
    by_target[row["target"]].append(row)

# Thirty-second summaries retain both central tendency and extrema.
summary_fields = [
    "bin", "start_timestamp", "target", "pid_set", "valid_samples",
    "glibc_median_kb", "glibc_min_kb", "glibc_max_kb",
    "other_anon_median_kb", "file_backed_median_kb",
    "MemAvailable_median_kb", "zram_used_median_kb",
]
with (DERIVED / "summary_30s.tsv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=summary_fields, delimiter="\t")
    writer.writeheader()
    bins = defaultdict(list)
    for row in rows:
        bin_no = int((row["time"] - start_time).total_seconds() // 30)
        bins[(bin_no, row["target"])].append(row)
    for (bin_no, target), group in sorted(bins.items()):
        valid = [row for row in group if row["pid"] != "NA"]
        if not valid:
            continue
        writer.writerow({
            "bin": bin_no,
            "start_timestamp": min(row["timestamp"] for row in group),
            "target": target,
            "pid_set": ",".join(str(pid) for pid in sorted({row["pid"] for row in valid})),
            "valid_samples": len(valid),
            "glibc_median_kb": median_int([row["glibc_heap_pd_kb"] for row in valid]),
            "glibc_min_kb": min(row["glibc_heap_pd_kb"] for row in valid),
            "glibc_max_kb": max(row["glibc_heap_pd_kb"] for row in valid),
            "other_anon_median_kb": median_int([row["other_anon_pd_kb"] for row in valid]),
            "file_backed_median_kb": median_int([row["file_backed_pd_kb"] for row in valid]),
            "MemAvailable_median_kb": median_int([row["MemAvailable_kb"] for row in valid]),
            "zram_used_median_kb": median_int([row["zram_used_kb"] for row in valid]),
        })


def contiguous_segments(target_rows):
    segments = []
    current = []
    current_pid = None
    for row in target_rows:
        pid = row["pid"]
        if pid == "NA":
            if current:
                segments.append(current)
                current = []
                current_pid = None
            continue
        if current_pid is not None and pid != current_pid:
            segments.append(current)
            current = []
        current.append(row)
        current_pid = pid
    if current:
        segments.append(current)
    return segments


actions = [
    (parse_time("2026-08-13T23:20:17.293697450-07:00"), "open ServiceK"),
    (parse_time("2026-08-13T23:20:42.783736194-07:00"), "close ServiceK"),
    (parse_time("2026-08-13T23:21:02.883407939-07:00"), "launch AppUIE (immediate exit)"),
    (parse_time("2026-08-13T23:21:38.052058347-07:00"), "close check: AppUIE already stopped"),
    (parse_time("2026-08-13T23:21:58.246287259-07:00"), "launch AppUIF (immediate exit)"),
    (parse_time("2026-08-13T23:22:33.644446501-07:00"), "close check: AppUIF already stopped"),
]


def nearest_action(timestamp):
    closest_time, closest_name = min(actions, key=lambda item: abs((timestamp - item[0]).total_seconds()))
    delta = (timestamp - closest_time).total_seconds()
    if abs(delta) <= 15:
        return closest_name, delta
    return "none within 15 s", math.nan


peak_rows = []
event_rows = []
pid_change_rows = []
for target, target_rows in by_target.items():
    last_pid = None
    for row in target_rows:
        if row["pid"] != last_pid:
            pid_change_rows.append({
                "target": target,
                "sample": row["sample"],
                "timestamp": row["timestamp"],
                "old_pid": "NA" if last_pid is None else last_pid,
                "new_pid": row["pid"],
            })
            last_pid = row["pid"]

    for segment_no, segment in enumerate(contiguous_segments(target_rows), 1):
        pid = segment[0]["pid"]
        source_baseline = baseline_by_pid.get(pid)
        baseline = source_baseline["glibc_heap_pd_kb"] if source_baseline else segment[0]["glibc_heap_pd_kb"]
        baseline_source = "S1" if source_baseline else "segment-first-sample"
        threshold = baseline * 0.10
        values = [row["glibc_heap_pd_kb"] for row in segment]

        # Each emitted event is the full peak-to-trough drawdown. Recovery resets
        # the peak search; this avoids counting every sample in one decline.
        events = []
        peak = segment[0]
        active = None
        for row in segment[1:]:
            value = row["glibc_heap_pd_kb"]
            if active is None:
                if value > peak["glibc_heap_pd_kb"]:
                    peak = row
                elif peak["glibc_heap_pd_kb"] - value >= threshold:
                    active = {"peak": peak, "trough": row}
            else:
                if value < active["trough"]["glibc_heap_pd_kb"]:
                    active["trough"] = row
                recovery = value - active["trough"]["glibc_heap_pd_kb"]
                if recovery >= threshold / 2:
                    events.append(active)
                    peak = row
                    active = None
        if active is not None:
            events.append(active)

        glibc_min = min(values)
        glibc_max = max(values)
        range_kb = glibc_max - glibc_min
        range_pct = (100.0 * range_kb / baseline) if baseline else math.nan
        if baseline and range_kb < threshold:
            shape = "flat"
        elif events:
            shape = "sawtooth"
        else:
            shape = "stair"

        peak_rows.append({
            "target": target,
            "segment": segment_no,
            "pid": pid,
            "segment_start": segment[0]["timestamp"],
            "segment_end": segment[-1]["timestamp"],
            "samples": len(segment),
            "baseline_kb": baseline,
            "baseline_source": baseline_source,
            "min_kb": glibc_min,
            "max_kb": glibc_max,
            "range_kb": range_kb,
            "range_pct_of_baseline": f"{range_pct:.2f}",
            "drop_events": len(events),
            "shape": shape,
        })
        for event_no, event in enumerate(events, 1):
            peak_row = event["peak"]
            trough_row = event["trough"]
            drop_kb = peak_row["glibc_heap_pd_kb"] - trough_row["glibc_heap_pd_kb"]
            action, delta = nearest_action(trough_row["time"])
            event_rows.append({
                "target": target,
                "segment": segment_no,
                "pid": pid,
                "event": event_no,
                "peak_timestamp": peak_row["timestamp"],
                "trough_timestamp": trough_row["timestamp"],
                "peak_kb": peak_row["glibc_heap_pd_kb"],
                "trough_kb": trough_row["glibc_heap_pd_kb"],
                "drop_kb": drop_kb,
                "drop_pct_of_baseline": f"{100.0 * drop_kb / baseline:.2f}" if baseline else "NA",
                "nearest_action_within_15s": action,
                "seconds_after_action": "NA" if math.isnan(delta) else f"{delta:.3f}",
            })

for filename, records in (
    ("peak_valley.tsv", peak_rows),
    ("drop_events.tsv", event_rows),
    ("pid_changes.tsv", pid_change_rows),
):
    path = DERIVED / filename
    fields = list(records[0]) if records else ["none"]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(records)

stable = by_target["AppProcD"]
deltas = [(stable[i]["time"] - stable[i - 1]["time"]).total_seconds() for i in range(1, len(stable))]
with (DERIVED / "quality.txt").open("w") as stream:
    stream.write(f"data_rows={len(rows)}\n")
    stream.write(f"targets={len(by_target)}\n")
    stream.write(f"pid_na_rows={sum(row['pid'] == 'NA' for row in rows)}\n")
    stream.write(f"sample_delta_min_seconds={min(deltas):.6f}\n")
    stream.write(f"sample_delta_median_seconds={statistics.median(deltas):.6f}\n")
    stream.write(f"sample_delta_max_seconds={max(deltas):.6f}\n")
    stream.write(f"sample_deltas_gt_2_1_seconds={sum(delta > 2.1 for delta in deltas)}\n")
    stream.write(f"MemAvailable_min_kb={min(row['MemAvailable_kb'] for row in rows)}\n")
    stream.write(f"MemAvailable_max_kb={max(row['MemAvailable_kb'] for row in rows)}\n")
    stream.write(f"zram_used_min_kb={min(row['zram_used_kb'] for row in rows)}\n")
    stream.write(f"zram_used_max_kb={max(row['zram_used_kb'] for row in rows)}\n")
