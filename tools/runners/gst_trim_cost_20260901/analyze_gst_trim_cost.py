#!/usr/bin/env python3
"""Validate and summarize the frozen GStreamer trim-cost board artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path


CYCLES = 51
PRIMARY_CYCLES = tuple(range(2, 52))
CELLS = (
    (1, "none", 1),
    (2, "trim-at-loop-release", 1),
    (3, "trim-at-loop-release", 2),
    (4, "none", 2),
    (5, "none", 3),
    (6, "trim-at-loop-release", 3),
)
CYCLE_FIELDS = (
    "order",
    "arm",
    "rep",
    "cycle",
    "primary_business_sample",
    "business_elapsed_ms",
    "trim_return",
    "trim_elapsed_ms",
    "glibc_pd_pre_kb",
    "glibc_pd_post_kb",
    "glibc_pd_reclaimed_kb",
    "reclaim_pct_of_pre",
    "cycle_minflt",
    "cycle_majflt",
    "capture_minflt",
    "capture_majflt",
    "external_samples",
    "external_overruns",
    "exit_code",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    require(bool(rows), f"refusing to write empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def safe_manifest_path(root: Path, raw: str) -> Path:
    require(raw.startswith("./"), f"manifest path lacks ./ prefix: {raw}")
    relative = Path(raw[2:])
    require(not relative.is_absolute() and ".." not in relative.parts, f"unsafe manifest path: {raw}")
    return root / relative


def validate_pull_integrity(root: Path) -> None:
    manifest_path = root / "board_manifest.sha256"
    sizes_path = root / "board_file_sizes.tsv"
    require(manifest_path.is_file() and sizes_path.is_file(), "missing board manifest/size list")
    actual_files = {path for path in root.rglob("*") if path.is_file()}
    manifest_files: set[Path] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=1)
        require(len(fields) == 2 and re.fullmatch(r"[0-9a-f]{64}", fields[0]) is not None, f"bad manifest row: {line}")
        path = safe_manifest_path(root, fields[1].strip())
        require(path not in manifest_files and path.is_file(), f"missing/duplicate manifest path: {path}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == fields[0], f"manifest hash mismatch: {path}")
        manifest_files.add(path)
    require(manifest_files == actual_files - {manifest_path, sizes_path}, "manifest file set mismatch")
    size_files: set[Path] = set()
    for line in sizes_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 1)
        require(len(fields) == 2 and fields[0].isdigit(), f"bad size row: {line}")
        path = safe_manifest_path(root, fields[1])
        require(path not in size_files and path.is_file(), f"missing/duplicate size path: {path}")
        require(path.stat().st_size == int(fields[0]), f"size mismatch: {path}")
        size_files.add(path)
    require(size_files == actual_files - {sizes_path}, "size file set mismatch")


def nearest_rank(values: list[float], percentile: float) -> float:
    require(bool(values), "empty percentile input")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def read_external(path: Path, meta_path: Path) -> tuple[list[dict[str, str]], int]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty external series: {path}")
    require([int(row["sample"]) for row in rows] == list(range(len(rows))), f"external sample gap: {path}")
    require(len({row["pid"] for row in rows}) == 1, f"external PID changed: {path}")
    for field in ("minflt", "majflt"):
        values = [row[field] for row in rows]
        require(all(value.isdigit() for value in values), f"invalid external {field}: {path}")
        integers = [int(value) for value in values]
        require(integers == sorted(integers), f"non-monotonic external {field}: {path}")
    meta = read_kv(meta_path)
    require(meta.get("RC") == "0" and "DONE_EXTERNAL_SAMPLER" in meta_path.read_text(), f"sampler failed: {meta_path}")
    require(int(meta.get("samples", "-1")) == len(rows), f"sampler count mismatch: {meta_path}")
    overruns = int(meta.get("deadline_overruns", "-1"))
    require(overruns >= 0, f"invalid sampler overrun count: {meta_path}")
    return rows, overruns


def parse_program(path: Path, arm: str) -> tuple[dict[int, dict[str, int]], dict[int, dict[str, int | str]]]:
    cycle_re = re.compile(r"^CYCLE_METRIC cycle=(\d+) business_elapsed_ns=(\d+) minflt=(\d+) majflt=(\d+)$")
    trim_re = re.compile(r"^TRIM_METRIC cycle=(\d+) arm=([^ ]+) return=(-?\d+) elapsed_ns=(\d+)$")
    cycles: dict[int, dict[str, int]] = {}
    trims: dict[int, dict[str, int | str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = cycle_re.fullmatch(line)
        if match:
            cycle = int(match.group(1))
            require(cycle not in cycles, f"duplicate cycle metric: {path}:{cycle}")
            cycles[cycle] = {
                "business_elapsed_ns": int(match.group(2)),
                "minflt": int(match.group(3)),
                "majflt": int(match.group(4)),
            }
            continue
        match = trim_re.fullmatch(line)
        if match:
            cycle = int(match.group(1))
            require(cycle not in trims, f"duplicate trim metric: {path}:{cycle}")
            trims[cycle] = {"arm": match.group(2), "return": int(match.group(3)), "elapsed_ns": int(match.group(4))}
    expected = set(range(1, CYCLES + 1))
    require(set(cycles) == expected and set(trims) == expected, f"incomplete cycle/trim metrics: {path}")
    for cycle, metric in trims.items():
        require(metric["arm"] == arm, f"arm mismatch: {path}:{cycle}")
        if arm == "none":
            require(metric["return"] == -1 and metric["elapsed_ns"] == 0, f"none sentinel mismatch: {path}:{cycle}")
        else:
            require(metric["return"] in (0, 1) and int(metric["elapsed_ns"]) > 0, f"trim sentinel mismatch: {path}:{cycle}")
    return cycles, trims


def read_profile(path: Path, expected_pid: str) -> int:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    require(payload.get("schema") == "reclaim_probe.v1" and payload.get("command") == "profile", f"bad profile JSON: {path}")
    require(str(payload.get("pid")) == expected_pid, f"profile PID mismatch: {path}")
    value = payload.get("classes", {}).get("glibc-heap", {}).get("private_dirty_bytes")
    require(isinstance(value, int) and value >= 0 and value % 1024 == 0, f"bad glibc PD: {path}")
    return value // 1024


def dmesg_increment(before: list[str], after: list[str]) -> tuple[list[str], str]:
    if after[: len(before)] == before:
        return after[len(before) :], "prefix"
    before_set = set(before)
    return [line for line in after if line not in before_set], "set-difference-fallback"


def normalize_cycle_row(raw: dict[str, object]) -> dict[str, object]:
    require(tuple(raw) == CYCLE_FIELDS, f"unexpected cycles.tsv fields: {tuple(raw)}")
    integer_fields = (
        "order",
        "rep",
        "cycle",
        "primary_business_sample",
        "trim_return",
        "glibc_pd_pre_kb",
        "glibc_pd_post_kb",
        "glibc_pd_reclaimed_kb",
        "cycle_minflt",
        "cycle_majflt",
        "capture_minflt",
        "external_samples",
        "external_overruns",
        "exit_code",
    )
    float_fields = ("business_elapsed_ms", "trim_elapsed_ms", "reclaim_pct_of_pre")
    row: dict[str, object] = {"arm": str(raw["arm"])}
    try:
        row.update({field: int(raw[field]) for field in integer_fields})
        row.update({field: float(raw[field]) for field in float_fields})
        capture_majflt = str(raw["capture_majflt"])
        row["capture_majflt"] = capture_majflt if capture_majflt == "NA" else int(capture_majflt)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid cycles.tsv scalar: {raw}") from error
    require(
        all(math.isfinite(float(row[field])) for field in float_fields),
        f"non-finite cycles.tsv scalar: {raw}",
    )
    return {field: row[field] for field in CYCLE_FIELDS}


def read_cycle_table(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        require(tuple(reader.fieldnames or ()) == CYCLE_FIELDS, f"unexpected cycles.tsv header: {reader.fieldnames}")
        return [normalize_cycle_row(dict(row)) for row in reader]


def derive_cycle_summaries(
    raw_cycle_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    cycle_rows = [normalize_cycle_row(row) for row in raw_cycle_rows]
    require(len(cycle_rows) == len(CELLS) * CYCLES, f"cycle row count mismatch: {len(cycle_rows)}")
    expected_cells = {(order, arm, rep) for order, arm, rep in CELLS}
    actual_cells = {(int(row["order"]), str(row["arm"]), int(row["rep"])) for row in cycle_rows}
    require(actual_cells == expected_cells, f"cell set mismatch: {sorted(actual_cells)}")

    repetition_rows: list[dict[str, object]] = []
    for order, arm, rep in CELLS:
        rows = [
            row
            for row in cycle_rows
            if (int(row["order"]), str(row["arm"]), int(row["rep"])) == (order, arm, rep)
        ]
        rows.sort(key=lambda row: int(row["cycle"]))
        require([int(row["cycle"]) for row in rows] == list(range(1, CYCLES + 1)), f"cycle set mismatch: {order}/{arm}/{rep}")
        for row in rows:
            cycle = int(row["cycle"])
            require(int(row["primary_business_sample"]) == (1 if cycle in PRIMARY_CYCLES else 0), f"primary marker mismatch: {order}/{arm}/{rep}/{cycle}")
            require(float(row["business_elapsed_ms"]) >= 0, f"negative business time: {order}/{arm}/{rep}/{cycle}")
            require(int(row["glibc_pd_reclaimed_kb"]) == int(row["glibc_pd_pre_kb"]) - int(row["glibc_pd_post_kb"]), f"reclaim arithmetic mismatch: {order}/{arm}/{rep}/{cycle}")
            pre = int(row["glibc_pd_pre_kb"])
            expected_pct = round(int(row["glibc_pd_reclaimed_kb"]) * 100 / pre, 6) if pre else 0.0
            require(float(row["reclaim_pct_of_pre"]) == expected_pct, f"reclaim percentage mismatch: {order}/{arm}/{rep}/{cycle}")
            require(int(row["cycle_minflt"]) >= 0 and int(row["cycle_majflt"]) >= 0, f"negative faults: {order}/{arm}/{rep}/{cycle}")
            require(int(row["capture_minflt"]) >= 0, f"negative capture minflt: {order}/{arm}/{rep}/{cycle}")
            require(row["capture_majflt"] == "NA" or int(row["capture_majflt"]) >= 0, f"bad capture majflt: {order}/{arm}/{rep}/{cycle}")
            if arm == "none":
                require(int(row["trim_return"]) == -1 and float(row["trim_elapsed_ms"]) == 0.0, f"none trim sentinel mismatch: {order}/{rep}/{cycle}")
            else:
                require(int(row["trim_return"]) in (0, 1) and float(row["trim_elapsed_ms"]) > 0, f"trim metric mismatch: {order}/{rep}/{cycle}")

        for field in ("external_samples", "external_overruns", "exit_code"):
            require(len({int(row[field]) for row in rows}) == 1, f"non-constant {field}: {order}/{arm}/{rep}")
        external_samples = int(rows[0]["external_samples"])
        external_overruns = int(rows[0]["external_overruns"])
        exit_code = int(rows[0]["exit_code"])
        require(external_samples > 0 and external_overruns >= 0 and exit_code == 0, f"bad cell metadata: {order}/{arm}/{rep}")

        primary = [row for row in rows if int(row["primary_business_sample"]) == 1]
        require(len(primary) == 50, f"primary sample count mismatch: {order}/{arm}/{rep}")
        business = [float(row["business_elapsed_ms"]) for row in primary]
        trim_values = [float(row["trim_elapsed_ms"]) for row in rows if arm != "none"]
        reclaim = [float(row["glibc_pd_reclaimed_kb"]) for row in rows]
        reclaim_pct = [float(row["reclaim_pct_of_pre"]) for row in rows]
        repetition_rows.append({
            "order": order,
            "arm": arm,
            "rep": rep,
            "business_samples": len(business),
            "business_p50_ms": round(nearest_rank(business, 0.50), 6),
            "business_p95_ms": round(nearest_rank(business, 0.95), 6),
            "business_p99_ms": round(nearest_rank(business, 0.99), 6),
            "business_min_ms": round(min(business), 6),
            "business_max_ms": round(max(business), 6),
            "trim_calls": len(trim_values),
            "trim_p50_ms": round(nearest_rank(trim_values, 0.50), 6) if trim_values else 0.0,
            "trim_p95_ms": round(nearest_rank(trim_values, 0.95), 6) if trim_values else 0.0,
            "trim_p99_ms": round(nearest_rank(trim_values, 0.99), 6) if trim_values else 0.0,
            "trim_max_ms": round(max(trim_values), 6) if trim_values else 0.0,
            "reclaimed_median_kb": round(statistics.median(reclaim), 6),
            "reclaimed_min_kb": round(min(reclaim), 6),
            "reclaimed_max_kb": round(max(reclaim), 6),
            "reclaim_pct_of_pre_median": round(statistics.median(reclaim_pct), 6),
            "primary_minflt_sum": sum(int(row["cycle_minflt"]) for row in primary),
            "primary_majflt_sum": sum(int(row["cycle_majflt"]) for row in primary),
            "external_samples": external_samples,
            "external_overruns": external_overruns,
            "exit_code": exit_code,
        })

    arm_rows: list[dict[str, object]] = []
    for arm in ("none", "trim-at-loop-release"):
        rows = [row for row in repetition_rows if row["arm"] == arm]
        require(len(rows) == 3 and sorted(int(row["rep"]) for row in rows) == [1, 2, 3], f"repeat set mismatch: {arm}")
        summary: dict[str, object] = {"arm": arm, "repeats": 3}
        for metric in ("business_p50_ms", "business_p95_ms", "business_p99_ms"):
            values = [float(row[metric]) for row in rows]
            summary[f"{metric}_median"] = round(statistics.median(values), 6)
            summary[f"{metric}_range"] = round(max(values) - min(values), 6)
        for metric in ("trim_p50_ms", "trim_p95_ms", "trim_p99_ms", "trim_max_ms", "reclaimed_median_kb", "reclaim_pct_of_pre_median"):
            summary[f"{metric}_across_repeats"] = round(statistics.median(float(row[metric]) for row in rows), 6)
        summary["primary_minflt_sum_median"] = statistics.median(int(row["primary_minflt_sum"]) for row in rows)
        summary["primary_majflt_sum_max"] = max(int(row["primary_majflt_sum"]) for row in rows)
        arm_rows.append(summary)

    by_arm = {str(row["arm"]): row for row in arm_rows}
    none_p99 = float(by_arm["none"]["business_p99_ms_median"])
    trim_p99 = float(by_arm["trim-at-loop-release"]["business_p99_ms_median"])
    baseline_dispersion = float(by_arm["none"]["business_p99_ms_range"])
    delta_p99 = trim_p99 - none_p99
    comparison = {
        "decision_rule": "visible iff trim median-of-repeat p99 minus none median-of-repeat p99 is strictly greater than none repeat p99 max-minus-min",
        "primary_cycles": "2-51",
        "primary_samples_per_repeat": 50,
        "percentile_method": "nearest-rank",
        "none_p99_median_ms": round(none_p99, 6),
        "trim_p99_median_ms": round(trim_p99, 6),
        "delta_p99_ms": round(delta_p99, 6),
        "none_p99_repeat_dispersion_ms": round(baseline_dispersion, 6),
        "business_cost_visible": delta_p99 > baseline_dispersion,
    }
    return repetition_rows, arm_rows, comparison


def write_cycle_summaries(
    output: Path,
    repetition_rows: list[dict[str, object]],
    arm_rows: list[dict[str, object]],
    comparison: dict[str, object],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_tsv(output / "repetitions.tsv", repetition_rows)
    write_tsv(output / "arm_summary.tsv", arm_rows)
    with (output / "comparison.json").open("w", encoding="utf-8") as stream:
        json.dump(comparison, stream, indent=2, sort_keys=True)
        stream.write("\n")


def print_cycle_summary(prefix: str, repetition_rows: list[dict[str, object]], comparison: dict[str, object]) -> None:
    print(f"{prefix} cells={len(repetition_rows)} cycles={len(repetition_rows) * CYCLES} primary={len(repetition_rows) * 50}")
    print(
        f"delta_p99_ms={float(comparison['delta_p99_ms']):.6f} "
        f"none_dispersion_ms={float(comparison['none_p99_repeat_dispersion_ms']):.6f} "
        f"visible={str(comparison['business_cost_visible']).lower()}"
    )


parser = argparse.ArgumentParser()
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("--pull", type=Path)
source.add_argument("--replay-cycles", type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
output = args.output
if args.replay_cycles is not None:
    replay_rows = read_cycle_table(args.replay_cycles)
    replay_repetitions, replay_arms, replay_comparison = derive_cycle_summaries(replay_rows)
    write_cycle_summaries(output, replay_repetitions, replay_arms, replay_comparison)
    print_cycle_summary("replayed", replay_repetitions, replay_comparison)
    raise SystemExit(0)

pull = args.pull
require(pull is not None, "--pull is required in full validation mode")
validate_pull_integrity(pull)
output.mkdir(parents=True, exist_ok=True)

cycle_rows: list[dict[str, object]] = []
external_rows: list[dict[str, object]] = []
capture_majflt_numeric_pairs = 0
capture_majflt_legacy_s0_pairs = 0

for order, arm, rep in CELLS:
    cell_name = f"{order:02d}_{arm}_rep{rep}"
    cell = pull / "cells" / cell_name
    require(cell.is_dir(), f"missing cell: {cell}")
    command = read_kv(cell / "command.txt")
    require(command.get("order") == str(order) and command.get("arm") == arm and command.get("rep") == str(rep), f"cell metadata mismatch: {cell}")
    require(command.get("cycles") == "51" and command.get("play_seconds") == "20" and command.get("null_seconds") == "1", f"frozen parameters mismatch: {cell}")
    exits = read_kv(cell / "exit_status.txt")
    require(exits.get("bench_rc") == "0" and exits.get("sampler_rc") == "0", f"cell exit failed: {cell}")
    pid = (cell / "pid.txt").read_text().strip()
    require(pid.isdigit(), f"bad PID: {cell}")
    cycles, trims = parse_program(cell / "program_stdout.txt", arm)
    external, overruns = read_external(cell / "external_1s.tsv", cell / "external_sampler_meta.txt")
    external_rows.append({
        "order": order,
        "arm": arm,
        "rep": rep,
        "samples": len(external),
        "deadline_overruns": overruns,
        "minflt_delta": int(external[-1]["minflt"]) - int(external[0]["minflt"]),
        "majflt_delta": int(external[-1]["majflt"]) - int(external[0]["majflt"]),
    })
    for cycle in range(1, CYCLES + 1):
        pre = read_profile(cell / f"cycle_{cycle:02d}_pre.json", pid)
        post = read_profile(cell / f"cycle_{cycle:02d}_post.json", pid)
        pre_meta = read_kv(cell / f"cycle_{cycle:02d}_pre.txt")
        post_meta = read_kv(cell / f"cycle_{cycle:02d}_post.txt")
        require(pre_meta.get("RC") == "0" and post_meta.get("RC") == "0", f"capture RC failed: {cell}:{cycle}")
        require(pre_meta.get("pid") == pid and post_meta.get("pid") == pid, f"capture PID mismatch: {cell}:{cycle}")
        pre_capture_minflt = pre_meta.get("minflt", "")
        post_capture_minflt = post_meta.get("minflt", "")
        require(pre_capture_minflt.isdigit() and post_capture_minflt.isdigit(), f"invalid capture minflt: {cell}:{cycle}")
        require(int(post_capture_minflt) >= int(pre_capture_minflt), f"non-monotonic capture minflt: {cell}:{cycle}")
        pre_capture_majflt = pre_meta.get("majflt", "")
        post_capture_majflt = post_meta.get("majflt", "")
        if pre_capture_majflt.isdigit() and post_capture_majflt.isdigit():
            require(int(post_capture_majflt) >= int(pre_capture_majflt), f"non-monotonic capture majflt: {cell}:{cycle}")
            capture_majflt: object = int(post_capture_majflt) - int(pre_capture_majflt)
            capture_majflt_numeric_pairs += 1
        else:
            # The executed controller batch used "$10" instead of "${10}" in
            # POSIX sh, producing state-field "S" plus literal "0". Preserve
            # that data-quality defect explicitly; cycle getrusage and the
            # independent 1 s /proc series remain mandatory numeric sources.
            require(pre_capture_majflt == "S0" and post_capture_majflt == "S0", f"invalid capture majflt: {cell}:{cycle}")
            capture_majflt = "NA"
            capture_majflt_legacy_s0_pairs += 1
        cycle_metric = cycles[cycle]
        trim_metric = trims[cycle]
        row = {
            "order": order,
            "arm": arm,
            "rep": rep,
            "cycle": cycle,
            "primary_business_sample": 1 if cycle in PRIMARY_CYCLES else 0,
            "business_elapsed_ms": round(cycle_metric["business_elapsed_ns"] / 1e6, 6),
            "trim_return": trim_metric["return"],
            "trim_elapsed_ms": round(int(trim_metric["elapsed_ns"]) / 1e6, 6),
            "glibc_pd_pre_kb": pre,
            "glibc_pd_post_kb": post,
            "glibc_pd_reclaimed_kb": pre - post,
            "reclaim_pct_of_pre": round((pre - post) * 100 / pre, 6) if pre else 0.0,
            "cycle_minflt": cycle_metric["minflt"],
            "cycle_majflt": cycle_metric["majflt"],
            "capture_minflt": int(post_capture_minflt) - int(pre_capture_minflt),
            "capture_majflt": capture_majflt,
            "external_samples": len(external),
            "external_overruns": overruns,
            "exit_code": int(exits["bench_rc"]),
        }
        cycle_rows.append(row)
require(
    (capture_majflt_numeric_pairs == len(cycle_rows) and capture_majflt_legacy_s0_pairs == 0)
    or (capture_majflt_numeric_pairs == 0 and capture_majflt_legacy_s0_pairs == len(cycle_rows)),
    "mixed capture majflt encoding within one matrix",
)
cycle_rows = [normalize_cycle_row(row) for row in cycle_rows]
repetition_rows, arm_rows, comparison = derive_cycle_summaries(cycle_rows)

before = (pull / "dmesg_before.txt").read_text(encoding="utf-8", errors="replace").splitlines()
after = (pull / "dmesg_after.txt").read_text(encoding="utf-8", errors="replace").splitlines()
increment, increment_method = dmesg_increment(before, after)
(output / "dmesg_increment.txt").write_text("\n".join(increment) + ("\n" if increment else ""), encoding="utf-8")
bad_terms = ("out of memory", "oom", "lowmemory", "low memory", "lmk", "killed process")
bad_lines = [line for line in increment if any(term in line.lower() for term in bad_terms)]
z_before = [int(value) for value in (pull / "zram_mm_stat_before.txt").read_text().split()]
z_after = [int(value) for value in (pull / "zram_mm_stat_after.txt").read_text().split()]
require(len(z_before) >= 3 and len(z_after) >= 3, "short zram mm_stat")
health = {
    "dmesg_increment_method": increment_method,
    "dmesg_increment_lines": len(increment),
    "oom_lmk_matches": bad_lines,
    "zram_original_data_size_before": z_before[0],
    "zram_original_data_size_after": z_after[0],
    "zram_original_data_size_delta": z_after[0] - z_before[0],
    "zram_compressed_data_size_before": z_before[1],
    "zram_compressed_data_size_after": z_after[1],
    "zram_compressed_data_size_delta": z_after[1] - z_before[1],
    "zram_mem_used_total_before": z_before[2],
    "zram_mem_used_total_after": z_after[2],
    "zram_mem_used_total_delta": z_after[2] - z_before[2],
    "governor_restored_schedutil_count": (pull / "governor_after.txt").read_text().count("=schedutil"),
    "capture_majflt_numeric_pairs": capture_majflt_numeric_pairs,
    "capture_majflt_legacy_s0_pairs": capture_majflt_legacy_s0_pairs,
    "capture_majflt_status": "numeric" if capture_majflt_numeric_pairs else "unavailable-posix-dollar10-defect",
}
require(not bad_lines, "OOM/LMK evidence found in dmesg increment")
require(health["governor_restored_schedutil_count"] == 4, "governor restore failed")

write_tsv(output / "cycles.tsv", cycle_rows)
write_cycle_summaries(output, repetition_rows, arm_rows, comparison)
write_tsv(output / "external_summary.tsv", external_rows)
for name, payload in (("health.json", health),):
    with (output / name).open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")

print_cycle_summary("validated", repetition_rows, comparison)
