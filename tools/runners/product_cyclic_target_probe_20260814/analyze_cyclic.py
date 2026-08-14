#!/usr/bin/env python3
import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DERIVED = ROOT / "derived"
DERIVED.mkdir(exist_ok=True)
PUBLIC_ALIAS = {
    "ChannelLoader": "ServiceH[ServiceK]",
    "WebRuntime": "ServiceE",
}


def read_tsv(path):
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_tsv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def actual_stage(elapsed):
    if elapsed < 60:
        return "P0"
    if elapsed < 540:
        return f"R{int((elapsed - 60) // 60) + 1}"
    return "P1"


start_ns = int((RAW / "start_ns.txt").read_text(encoding="utf-8").strip())
rows = read_tsv(RAW / "timeseries.tsv")
numeric = (
    "sample", "epoch_ns", "pid", "glibc_heap_pd_kb", "other_anon_pd_kb",
    "file_backed_pd_kb", "total_pd_kb", "minflt", "majflt",
    "MemAvailable_kb", "zram_used_kb",
)
for row in rows:
    for key in numeric:
        row[key] = int(row[key])
    row["elapsed_s"] = (row["epoch_ns"] - start_ns) / 1_000_000_000
    row["actual_stage"] = actual_stage(row["elapsed_s"])

keys = read_tsv(RAW / "key_timeline.tsv")
for row in keys:
    row["actual_epoch_ns"] = int(row["actual_epoch_ns"])
    row["elapsed_s"] = (row["actual_epoch_ns"] - start_ns) / 1_000_000_000

service_a = sorted((row for row in rows if row["target"] == "ServiceA"), key=lambda row: row["epoch_ns"])
p0 = [row for row in service_a if row["actual_stage"] == "P0"]
p0_baseline_g = p0[-1]["glibc_heap_pd_kb"]
p0_baseline_o = p0[-1]["other_anon_pd_kb"]

# A public, alias-only time series. The nominal sample is retained, but all
# phase analysis uses actual_elapsed_s because catch-up samples are intentional.
series_fields = [
    "sample", "actual_stage", "timestamp", "actual_elapsed_s", "pid",
    "glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb",
    "minflt", "majflt", "MemAvailable_kb", "zram_used_kb",
]
series_rows = []
for row in service_a:
    series_rows.append({
        "sample": row["sample"],
        "actual_stage": row["actual_stage"],
        "timestamp": row["timestamp"],
        "actual_elapsed_s": f'{row["elapsed_s"]:.6f}',
        "pid": row["pid"],
        "glibc_heap_pd_kb": row["glibc_heap_pd_kb"],
        "other_anon_pd_kb": row["other_anon_pd_kb"],
        "file_backed_pd_kb": row["file_backed_pd_kb"],
        "minflt": row["minflt"],
        "majflt": row["majflt"],
        "MemAvailable_kb": row["MemAvailable_kb"],
        "zram_used_kb": row["zram_used_kb"],
    })
write_tsv(DERIVED / "serviceA_timeseries.tsv", series_fields, series_rows)

# Edge definitions use the observed excursion in each wall-clock round:
# rise start is the last point at or below 10% of the excursion, peak-band
# entry is the first point at or above 90%, fall start is the first subsequent
# point below 90%, and valley is the first minimum after fall start.
shape_rows = []
peak_valley_rows = []
edge_triplets = []
valley_rows = []
for round_number in range(1, 9):
    round_name = f"R{round_number}"
    base = round_number * 60
    end = base + 60
    current = [row for row in service_a if base <= row["elapsed_s"] < end]
    before = [row for row in service_a if row["elapsed_s"] < base][-1]
    sequence = [before] + current
    peak = max(current, key=lambda row: row["glibc_heap_pd_kb"])
    peak_index = sequence.index(peak)
    excursion = peak["glibc_heap_pd_kb"] - before["glibc_heap_pd_kb"]
    low = before["glibc_heap_pd_kb"] + 0.10 * excursion
    high = before["glibc_heap_pd_kb"] + 0.90 * excursion

    high_index = next(
        (index for index, row in enumerate(sequence[:peak_index + 1]) if row["glibc_heap_pd_kb"] >= high),
        peak_index,
    )
    rise_index = 0
    for index in range(high_index - 1, -1, -1):
        if sequence[index]["glibc_heap_pd_kb"] <= low:
            rise_index = index
            break
    fall_index = next(
        (index for index in range(peak_index + 1, len(sequence)) if sequence[index]["glibc_heap_pd_kb"] < high),
        len(sequence) - 1,
    )
    valley = min(sequence[fall_index:], key=lambda row: row["glibc_heap_pd_kb"])
    valley_index = sequence.index(valley)
    rise = sequence[rise_index]
    high_entry = sequence[high_index]
    fall = sequence[fall_index]

    prior_key = max((key for key in keys if key["elapsed_s"] <= peak["elapsed_s"]), key=lambda key: key["elapsed_s"])
    rise_seconds = high_entry["elapsed_s"] - rise["elapsed_s"]
    peak_seconds = fall["elapsed_s"] - high_entry["elapsed_s"]
    fall_seconds = valley["elapsed_s"] - fall["elapsed_s"]
    edge_triplets.append((rise_seconds, peak_seconds, fall_seconds))

    shape_rows.append({
        "round": round_name,
        "samples": len(current),
        "start_elapsed_s": f'{before["elapsed_s"]:.6f}',
        "start_glibc_kb": before["glibc_heap_pd_kb"],
        "rise_start_elapsed_s": f'{rise["elapsed_s"]:.6f}',
        "rise_start_glibc_kb": rise["glibc_heap_pd_kb"],
        "peak_elapsed_s": f'{peak["elapsed_s"]:.6f}',
        "peak_timestamp": peak["timestamp"],
        "peak_glibc_kb": peak["glibc_heap_pd_kb"],
        "peak_after_key": prior_key["key_name"],
        "peak_after_key_s": f'{peak["elapsed_s"] - prior_key["elapsed_s"]:.6f}',
        "fall_start_elapsed_s": f'{fall["elapsed_s"]:.6f}',
        "fall_start_glibc_kb": fall["glibc_heap_pd_kb"],
        "valley_elapsed_s": f'{valley["elapsed_s"]:.6f}',
        "valley_timestamp": valley["timestamp"],
        "valley_glibc_kb": valley["glibc_heap_pd_kb"],
        "round_last_glibc_kb": current[-1]["glibc_heap_pd_kb"],
        "rise_edge_s": f"{rise_seconds:.6f}",
        "peak_band_s": f"{peak_seconds:.6f}",
        "fall_edge_s": f"{fall_seconds:.6f}",
    })

    glibc_values = [row["glibc_heap_pd_kb"] for row in current]
    other_values = [row["other_anon_pd_kb"] for row in current]
    peak_valley_rows.append({
        "round": round_name,
        "glibc_peak_kb": peak["glibc_heap_pd_kb"],
        "glibc_valley_kb": valley["glibc_heap_pd_kb"],
        "glibc_peak_to_valley_kb": peak["glibc_heap_pd_kb"] - valley["glibc_heap_pd_kb"],
        "glibc_own_range_kb": max(glibc_values) - min(glibc_values),
        "other_at_glibc_peak_kb": peak["other_anon_pd_kb"],
        "other_at_glibc_valley_kb": valley["other_anon_pd_kb"],
        "other_peak_to_valley_change_kb": valley["other_anon_pd_kb"] - peak["other_anon_pd_kb"],
        "other_own_range_kb": max(other_values) - min(other_values),
    })
    valley_rows.append({
        "round": round_name,
        "valley_elapsed_s": f'{valley["elapsed_s"]:.6f}',
        "valley_glibc_kb": valley["glibc_heap_pd_kb"],
        "delta_from_p0_kb": valley["glibc_heap_pd_kb"] - p0_baseline_g,
        "delta_from_p0_pct": f'{100.0 * (valley["glibc_heap_pd_kb"] - p0_baseline_g) / p0_baseline_g:.3f}',
        "valley_other_anon_kb": valley["other_anon_pd_kb"],
        "other_delta_from_p0_kb": valley["other_anon_pd_kb"] - p0_baseline_o,
    })

write_tsv(DERIVED / "serviceA_cycle_shape.tsv", list(shape_rows[0]), shape_rows)
write_tsv(DERIVED / "serviceA_peak_valley.tsv", list(peak_valley_rows[0]), peak_valley_rows)
write_tsv(DERIVED / "serviceA_valley_trend.tsv", list(valley_rows[0]), valley_rows)

edge_summary = [{
    "metric": "median",
    "rise_edge_s": f"{statistics.median(item[0] for item in edge_triplets):.6f}",
    "peak_band_s": f"{statistics.median(item[1] for item in edge_triplets):.6f}",
    "fall_edge_s": f"{statistics.median(item[2] for item in edge_triplets):.6f}",
    "p0_baseline_glibc_kb": p0_baseline_g,
    "p0_baseline_other_anon_kb": p0_baseline_o,
}]
write_tsv(DERIVED / "serviceA_edge_medians.tsv", list(edge_summary[0]), edge_summary)

# Stage summaries for ServiceA and both controls, based on wall-clock phase.
stage_order = ["P0"] + [f"R{i}" for i in range(1, 9)] + ["P1"]
stage_rows = []
for target in ("ServiceA", "ServiceB", "ChannelLoader", "WebRuntime"):
    target_rows = [row for row in rows if row["target"] == target]
    for stage in stage_order:
        group = [row for row in target_rows if row["actual_stage"] == stage]
        stage_rows.append({
            "target": PUBLIC_ALIAS.get(target, target),
            "stage": stage,
            "samples": len(group),
            "glibc_start_kb": group[0]["glibc_heap_pd_kb"],
            "glibc_peak_kb": max(row["glibc_heap_pd_kb"] for row in group),
            "glibc_min_kb": min(row["glibc_heap_pd_kb"] for row in group),
            "glibc_end_kb": group[-1]["glibc_heap_pd_kb"],
            "other_start_kb": group[0]["other_anon_pd_kb"],
            "other_peak_kb": max(row["other_anon_pd_kb"] for row in group),
            "other_min_kb": min(row["other_anon_pd_kb"] for row in group),
            "other_end_kb": group[-1]["other_anon_pd_kb"],
            "file_start_kb": group[0]["file_backed_pd_kb"],
            "file_peak_kb": max(row["file_backed_pd_kb"] for row in group),
            "file_min_kb": min(row["file_backed_pd_kb"] for row in group),
            "file_end_kb": group[-1]["file_backed_pd_kb"],
        })
write_tsv(DERIVED / "target_stage_summary.tsv", list(stage_rows[0]), stage_rows)

# PID segments and timing quality.
pid_counts = defaultdict(int)
for row in rows:
    pid_counts[(row["target"], row["pid"])] += 1
pid_rows = [
    {"target": PUBLIC_ALIAS.get(target, target), "pid": pid, "rows": count}
    for (target, pid), count in sorted(pid_counts.items())
]
write_tsv(DERIVED / "pid_segments.tsv", ["target", "pid", "rows"], pid_rows)

sample_times = []
for sample in range(660):
    sample_times.append(next(row["epoch_ns"] for row in rows if row["sample"] == sample))
intervals = [(right - left) / 1_000_000_000 for left, right in zip(sample_times, sample_times[1:])]
quality_rows = [{
    "samples": len(sample_times),
    "target_rows": len(rows),
    "interval_min_s": f"{min(intervals):.6f}",
    "interval_median_s": f"{statistics.median(intervals):.6f}",
    "interval_max_s": f"{max(intervals):.6f}",
    "interval_gt_1_1_s": sum(value > 1.1 for value in intervals),
    "interval_gt_2_s": sum(value > 2 for value in intervals),
    "interval_gt_3_s": sum(value > 3 for value in intervals),
    "catchup_interval_lt_0_9_s": sum(value < 0.9 for value in intervals),
    "key_rows": len(keys),
    "key_lateness_min_ms": f'{min(float(row["lateness_ms"]) for row in keys):.3f}',
    "key_lateness_median_ms": f'{statistics.median(float(row["lateness_ms"]) for row in keys):.3f}',
    "key_lateness_max_ms": f'{max(float(row["lateness_ms"]) for row in keys):.3f}',
    "MemAvailable_min_kb": min(row["MemAvailable_kb"] for row in rows),
    "MemAvailable_max_kb": max(row["MemAvailable_kb"] for row in rows),
    "zram_used_min_kb": min(row["zram_used_kb"] for row in rows),
    "zram_used_max_kb": max(row["zram_used_kb"] for row in rows),
}]
write_tsv(DERIVED / "quality.tsv", list(quality_rows[0]), quality_rows)

key_rows = [{
    "round": row["round"],
    "sequence": row["sequence"],
    "actual_elapsed_s": f'{row["elapsed_s"]:.6f}',
    "actual_timestamp": row["actual_timestamp"],
    "key": row["key"],
    "key_name": row["key_name"],
    "vk_exit": row["vk_exit"],
    "lateness_ms": row["lateness_ms"],
} for row in keys]
write_tsv(DERIVED / "key_timeline_alias.tsv", list(key_rows[0]), key_rows)

print("ANALYSIS_DONE")
