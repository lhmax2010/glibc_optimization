#!/usr/bin/env python3
"""Validate and summarize the pulled S4 board artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path


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
        require(path not in manifest_files, f"duplicate manifest path: {path}")
        require(path.is_file(), f"manifest file missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest == fields[0], f"manifest hash mismatch: {path}")
        manifest_files.add(path)
    require(
        manifest_files == actual_files - {manifest_path, sizes_path},
        "manifest file set does not match pulled files",
    )

    size_files: set[Path] = set()
    for line in sizes_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 1)
        require(len(fields) == 2 and fields[0].isdigit(), f"bad size row: {line}")
        path = safe_manifest_path(root, fields[1])
        require(path not in size_files, f"duplicate size path: {path}")
        require(path.is_file() and path.stat().st_size == int(fields[0]), f"size mismatch: {path}")
        size_files.add(path)
    require(size_files == actual_files - {sizes_path}, "size file set does not match pulled files")


def read_exit(path: Path) -> tuple[int, int]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    require(values.get("bench_rc") == "0", f"bench did not exit 0: {path}")
    require(values.get("sampler_rc") == "0", f"sampler did not exit 0: {path}")
    return int(values["bench_rc"]), int(values["sampler_rc"])


def read_external(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty external sequence: {path}")
    integers = (
        "sample", "epoch_ns", "pid", "glibc_heap_pd_kb", "other_anon_pd_kb",
        "file_backed_pd_kb", "total_pd_kb", "minflt", "majflt",
    )
    for row in rows:
        row["elapsed_s"] = float(row["elapsed_s"])
        for key in integers:
            row[key] = int(row[key])
    require([row["sample"] for row in rows] == list(range(len(rows))), f"sample gap: {path}")
    require(all(a["elapsed_s"] < b["elapsed_s"] for a, b in zip(rows, rows[1:])), f"time reversal: {path}")
    require(len({row["pid"] for row in rows}) == 1, f"PID changed: {path}")
    return rows


def median(values: list[float | int]) -> float:
    return float(statistics.median(values))


def load_cell(path: Path, expected_suffixes: tuple[str, ...]) -> tuple[dict[str, object], list[dict[str, object]]]:
    read_exit(path / "exit_status.txt")
    with (path / "result.json").open(encoding="utf-8") as stream:
        result = json.load(stream)
    samples = read_external(path / "external_1s.tsv")
    meta_lines = (path / "external_sampler_meta.txt").read_text(encoding="utf-8").splitlines()
    require(meta_lines.count("RC=0") == 1, f"sampler RC marker is not exact/unique: {path}")
    require(meta_lines.count("DONE_EXTERNAL_SAMPLER") == 1, f"sampler DONE marker is not exact/unique: {path}")
    require(not any(line.startswith("FAIL_") for line in meta_lines), f"sampler FAIL marker present: {path}")
    sample_fields = [line.split("=", 1)[1] for line in meta_lines if line.startswith("samples=")]
    require(len(sample_fields) == 1 and sample_fields[0].isdigit(), f"bad sampler sample count: {path}")
    require(int(sample_fields[0]) == len(samples), f"sampler metadata/TSV count mismatch: {path}")
    xml_paths = sorted((path / "xml").glob("*.xml"))
    require(len(xml_paths) == len(expected_suffixes), f"expected {len(expected_suffixes)} malloc_info XML files: {path}")
    for suffix in expected_suffixes:
        require(sum(xml_path.name.endswith(suffix) for xml_path in xml_paths) == 1, f"missing/duplicate XML phase {suffix}: {path}")
    for xml_path in xml_paths:
        ET.parse(xml_path)
    return result, samples


def dmesg_increment(before: list[str], after: list[str]) -> tuple[list[str], str]:
    if after[: len(before)] == before:
        return after[len(before) :], "prefix"
    before_set = set(before)
    return [line for line in after if line not in before_set], "set-difference-fallback"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty public table: {path}")
    return rows


def replay_public(public: Path, output: Path) -> None:
    """Validate public S4 derivatives and emit workflow acceptance inputs."""
    a_rows = read_tsv(public / "a_cells.tsv")
    b_cell_rows = read_tsv(public / "b_cells.tsv")
    b_cycle_rows = read_tsv(public / "b_cycles.tsv")
    external_rows = read_tsv(public / "external_summary.tsv")
    health = json.loads((public / "health.json").read_text(encoding="utf-8"))
    require(len(a_rows) == 2, f"A cell count mismatch: {len(a_rows)}")
    require(len(b_cell_rows) == 8, f"B cell count mismatch: {len(b_cell_rows)}")
    require(len(b_cycle_rows) == 16, f"B cycle count mismatch: {len(b_cycle_rows)}")
    require(len(external_rows) == 10, f"external summary count mismatch: {len(external_rows)}")
    require({row["profile"] for row in a_rows} == {"mixed", "medium-only"}, "A profile set mismatch")
    expected_cells = {
        (profile, trim_at, str(rep))
        for profile in ("mixed", "medium-only")
        for trim_at, reps in (("valley", (1, 2, 3)), ("none", (1,)))
        for rep in reps
    }
    actual_cells = {(row["profile"], row["trim_at"], row["rep"]) for row in b_cell_rows}
    require(actual_cells == expected_cells, "B public cell set mismatch")
    require(all(int(row["exit_code"]) == 0 for row in a_rows + b_cell_rows), "non-zero public exit code")

    payloads: dict[tuple[str, int], set[int]] = {}
    trim_rows: list[dict[str, str]] = []
    for row in b_cycle_rows:
        profile, cycle = row["profile"], int(row["cycle"])
        require(profile in ("mixed", "medium-only") and cycle in (1, 2), "bad B profile/cycle")
        payloads.setdefault((profile, cycle), set()).add(int(row["released_payload_bytes"]))
        reclaimed_kb = int(row["trim_reclaimed_kb"])
        released = int(row["released_payload_bytes"])
        require(released > 0, "zero released payload")
        expected_pct = round(reclaimed_kb * 1024 * 100 / released, 6)
        require(float(row["trim_reclaim_pct_of_released"]) == expected_pct, "B reclaim percentage mismatch")
        if row["trim_at"] == "valley":
            require(int(row["trim_return"]) in (0, 1) and float(row["trim_elapsed_ms"]) > 0, "bad trim row")
            trim_rows.append(row)
        else:
            require(int(row["trim_return"]) == -1 and reclaimed_kb == 0, "bad none row")
    require(all(len(values) == 1 for values in payloads.values()), "released payload drift in public table")
    require(len(trim_rows) == 12, f"trim cycle count mismatch: {len(trim_rows)}")

    profile_medians: dict[str, float] = {}
    for profile in ("mixed", "medium-only"):
        repetition_values = [
            float(row["trim_reclaim_pct_of_released_median"])
            for row in b_cell_rows
            if row["profile"] == profile and row["trim_at"] == "valley"
        ]
        require(len(repetition_values) == 3, f"{profile} repetition count mismatch")
        profile_medians[profile] = round(statistics.median(repetition_values), 6)

    summary = {
        "schema": "s4-public-replay.v1",
        "a_anchor_reclaim_pct": {row["profile"]: float(row["reclaim_pct_of_pretrim"]) for row in a_rows},
        "a_anchor_trim_max_ms": max(float(row["trim_elapsed_ms"]) for row in a_rows),
        "b_reclaim_pct_repeat_median": profile_medians,
        "b_release_point_trim_max_ms": max(float(row["trim_elapsed_ms"]) for row in trim_rows),
        "released_payload_bytes": {
            profile: [next(iter(payloads[(profile, cycle)])) for cycle in (1, 2)]
            for profile in ("mixed", "medium-only")
        },
        "reclaimed_4k_aligned_count": sum(
            (int(row["trim_reclaimed_kb"]) * 1024) % 4096 == 0 for row in trim_rows
        ),
        "reclaimed_4k_aligned_total": len(trim_rows),
        "next_cycle_majflt_max": max(int(row["next_cycle_majflt"]) for row in b_cycle_rows),
        "zram_deltas": {
            "original_data_size": int(health["zram_original_data_size_delta"]),
            "compressed_data_size": int(health["zram_compressed_data_size_delta"]),
            "mem_used_total": int(health["zram_mem_used_total_delta"]),
        },
        "dmesg_oom_lmk_matches": len(health["oom_lmk_matches"]),
        "governor_restored_schedutil_count": int(health["governor_restored_schedutil_count"]),
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "acceptance_input.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    anchors = summary["a_anchor_reclaim_pct"]
    medians = summary["b_reclaim_pct_repeat_median"]
    print(f"replayed A={len(a_rows)} cells B={len(b_cell_rows)} cells B_cycles={len(b_cycle_rows)}")
    print(f"A anchors mixed={anchors['mixed']:.6f}% medium-only={anchors['medium-only']:.6f}%")
    print(f"B repeat-medians mixed={medians['mixed']:.6f}% medium-only={medians['medium-only']:.6f}%")
    zram = summary["zram_deltas"]
    print(
        f"deterministic payload_sets={len(payloads)} aligned={summary['reclaimed_4k_aligned_count']}/{summary['reclaimed_4k_aligned_total']} "
        f"majflt_max={summary['next_cycle_majflt_max']} "
        f"zram={zram['original_data_size']},{zram['compressed_data_size']},{zram['mem_used_total']} "
        f"oom_lmk={summary['dmesg_oom_lmk_matches']}"
    )


parser = argparse.ArgumentParser()
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--pull", type=Path)
mode.add_argument("--replay-public", type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
if args.replay_public is not None:
    replay_public(args.replay_public, args.output)
    raise SystemExit(0)
pull = args.pull
output = args.output
validate_pull_integrity(pull)
output.mkdir(parents=True, exist_ok=True)

a_rows: list[dict[str, object]] = []
b_cycle_rows: list[dict[str, object]] = []
b_cell_rows: list[dict[str, object]] = []
external_rows: list[dict[str, object]] = []
historical = {"mixed": 53.55, "medium-only": 50.60}

for profile in ("mixed", "medium-only"):
    cell = pull / "A" / profile / "rep1"
    result, samples = load_cell(cell, ("_measure.xml", "_release.xml", "_posttrim.xml", "_idle.xml"))
    require(result.get("mode") == "duration", f"A mode mismatch: {cell}")
    require(result.get("threads") == 4 and result.get("seed") == 20260813, f"A frozen args mismatch: {cell}")
    require(result.get("warmup_s") == 5.0 and result.get("duration_s") == 20.0, f"A warmup/duration mismatch: {cell}")
    require(result.get("idle_s") == 15.0 and result.get("post_trim_ops_per_thread") == 4096, f"A idle/refault mismatch: {cell}")
    require(result.get("live_set_per_thread") == 4096, f"A live set mismatch: {cell}")
    require(result.get("idle_release_pct") == 50 and result.get("release_order") == "high", f"A release args mismatch: {cell}")
    require(result.get("idle_trim") is True, f"A trim missing: {cell}")
    if profile == "mixed":
        require(result.get("profile") == "mixed", f"A mixed profile mismatch: {cell}")
    else:
        require(str(result.get("profile", "")).endswith("/medium_1k_16k.hist"), f"A medium profile mismatch: {cell}")
    memory = result["memory"]
    pre = int(memory["glibc_heap_pd_kb_pretrim"])
    post = int(memory["glibc_heap_pd_kb_posttrim"])
    reclaimed = pre - post
    released = int(result["idle_released_bytes"])
    require(result["idle_trim_ret"] in (0, 1), f"A trim sentinel mismatch: {cell}")
    require(int(memory["trim_elapsed_ns"]) > 0 and reclaimed >= 0, f"A trim result mismatch: {cell}")
    require(released > 0, f"A released payload is zero: {cell}")
    faults = memory["faults"]
    a_rows.append(
        {
            "profile": profile,
            "rep": 1,
            "pretrim_glibc_pd_kb": pre,
            "posttrim_glibc_pd_kb": post,
            "reclaimed_kb": reclaimed,
            "reclaim_pct_of_pretrim": round(reclaimed * 100 / pre, 6),
            "reclaim_pct_of_released": round(reclaimed * 1024 * 100 / released, 6),
            "release_pct": result["idle_release_pct"],
            "mechanism_expected_pct_of_pretrim": 49.0,
            "distance_from_expected_pp": round(reclaimed * 100 / pre - 49.0, 6),
            "historical_incomparable_pct": historical[profile],
            "trim_return": result["idle_trim_ret"],
            "trim_elapsed_ms": round(int(memory["trim_elapsed_ns"]) / 1e6, 6),
            "posttrim_refault_elapsed_ms": round(int(memory["post_trim_elapsed_ns"]) / 1e6, 6),
            "trim_minflt": int(faults["minflt_posttrim"]) - int(faults["minflt_pretrim"]),
            "trim_majflt": int(faults["majflt_posttrim"]) - int(faults["majflt_pretrim"]),
            "refault_minflt": int(faults["minflt_postrefault"]) - int(faults["minflt_posttrim"]),
            "refault_majflt": int(faults["majflt_postrefault"]) - int(faults["majflt_posttrim"]),
            "released_payload_bytes": released,
            "external_samples": len(samples),
            "external_minflt_delta": int(samples[-1]["minflt"]) - int(samples[0]["minflt"]),
            "external_majflt_delta": int(samples[-1]["majflt"]) - int(samples[0]["majflt"]),
            "exit_code": 0,
        }
    )
    external_rows.append(
        {
            "group": "A", "profile": profile, "trim_at": "idle-trim", "rep": 1,
            "samples": len(samples), "overruns": next(
                line.split("=", 1)[1] for line in (cell / "external_sampler_meta.txt").read_text().splitlines()
                if line.startswith("deadline_overruns=")
            ),
            "pid_count": len({row["pid"] for row in samples}),
            "minflt_delta": int(samples[-1]["minflt"]) - int(samples[0]["minflt"]),
            "majflt_delta": int(samples[-1]["majflt"]) - int(samples[0]["majflt"]),
        }
    )

for profile in ("mixed", "medium-only"):
    for trim_at, reps in (("valley", (1, 2, 3)), ("none", (1,))):
        for rep in reps:
            cell = pull / "B" / profile / trim_at / f"rep{rep}"
            result, samples = load_cell(
                cell,
                tuple(
                    f"_cycle{cycle:02d}_{phase}.xml"
                    for cycle in (1, 2)
                    for phase in ("peak", "fall_mid", "valley", "posttrim")
                ),
            )
            require(result.get("mode") == "cyclic" and result.get("cycles") == 2, f"B mode/cycles mismatch: {cell}")
            require(result.get("profile") == profile and result.get("threads") == 4, f"B profile/threads mismatch: {cell}")
            require(result.get("seed") == 20260814 and result.get("live_set_per_thread") == 512, f"B seed/live mismatch: {cell}")
            require(result.get("idle_release_pct") == 50 and result.get("release_order") == "high", f"B release mismatch: {cell}")
            require(result.get("trim_at") == trim_at, f"B trim_at mismatch: {cell}")
            require(result.get("cycle_rise_s") == 3.4 and result.get("cycle_peak_s") == 4.7, f"B rise/peak mismatch: {cell}")
            require(result.get("release_duration_s") == 19.7 and result.get("cycle_valley_s") == 20.0, f"B release/valley mismatch: {cell}")
            command = (cell / "command.txt").read_text(encoding="utf-8")
            require("--touch-full" in command and "--warmup 0" in command, f"B touch/warmup command mismatch: {cell}")
            cycles = sorted(result.get("cycle_data", []), key=lambda item: item["cycle"])
            require([item["cycle"] for item in cycles] == [1, 2], f"B cycle set mismatch: {cell}")
            cell_rows = []
            for item in cycles:
                heap = item["heap"]
                stats = item["malloc_info_stats"]
                pre = int(heap["trim_pre"]["glibc_heap_pd_kb"])
                post = int(heap["trim_post"]["glibc_heap_pd_kb"])
                reclaim = pre - post
                released = int(item["released_payload_bytes"])
                if trim_at == "valley":
                    require(item["trim_return"] in (0, 1), f"B valley trim sentinel mismatch: {cell}")
                    require(int(item["trim_elapsed_ns"]) > 0 and reclaim >= 0, f"B valley trim result mismatch: {cell}")
                else:
                    require(item["trim_return"] == -1, f"B none trim sentinel mismatch: {cell}")
                    require(int(item["trim_elapsed_ns"]) == 0 and reclaim == 0, f"B none trim result mismatch: {cell}")
                    require(stats["valley"] == stats["posttrim"], f"B none M7 pre/post mismatch: {cell}")
                require(released > 0, f"B released payload is zero: {cell}")
                row = {
                    "profile": profile,
                    "trim_at": trim_at,
                    "rep": rep,
                    "cycle": item["cycle"],
                    "released_payload_bytes": released,
                    "peak_glibc_pd_kb": heap["peak"]["glibc_heap_pd_kb"],
                    "valley_glibc_pd_kb": heap["valley"]["glibc_heap_pd_kb"],
                    "peak_minus_valley_glibc_pd_kb": item["peak_valley_glibc_heap_kb"],
                    "trim_pre_glibc_pd_kb": pre,
                    "trim_post_glibc_pd_kb": post,
                    "trim_reclaimed_kb": reclaim,
                    "trim_reclaim_pct_of_released": round(reclaim * 1024 * 100 / released, 6),
                    "m7_rest_pre_bytes": stats["valley"]["rest_bytes"],
                    "m7_rest_post_bytes": stats["posttrim"]["rest_bytes"],
                    "m7_unsorted_pre_bytes": stats["valley"]["unsorted_bytes"],
                    "m7_unsorted_post_bytes": stats["posttrim"]["unsorted_bytes"],
                    "trim_return": item["trim_return"],
                    "trim_elapsed_ms": round(int(item["trim_elapsed_ns"]) / 1e6, 6),
                    "next_cycle_minflt": item["faults"]["next_cycle_minflt"],
                    "next_cycle_majflt": item["faults"]["next_cycle_majflt"],
                    "exit_code": 0,
                }
                b_cycle_rows.append(row)
                cell_rows.append(row)
            first = cell_rows[0]
            b_cell_rows.append(
                {
                    "profile": profile,
                    "trim_at": trim_at,
                    "rep": rep,
                    "cycles": 2,
                    "released_payload_median_bytes": round(median([row["released_payload_bytes"] for row in cell_rows])),
                    "trim_reclaimed_median_kb": round(median([row["trim_reclaimed_kb"] for row in cell_rows]), 3),
                    "trim_reclaim_pct_of_released_median": round(median([row["trim_reclaim_pct_of_released"] for row in cell_rows]), 6),
                    "m7_rest_pre_median_bytes": round(median([row["m7_rest_pre_bytes"] for row in cell_rows])),
                    "m7_rest_post_median_bytes": round(median([row["m7_rest_post_bytes"] for row in cell_rows])),
                    "m7_unsorted_pre_median_bytes": round(median([row["m7_unsorted_pre_bytes"] for row in cell_rows])),
                    "m7_unsorted_post_median_bytes": round(median([row["m7_unsorted_post_bytes"] for row in cell_rows])),
                    "trim_elapsed_median_ms": round(median([row["trim_elapsed_ms"] for row in cell_rows]), 6),
                    "cycle1_next_minflt": first["next_cycle_minflt"],
                    "cycle1_next_majflt": first["next_cycle_majflt"],
                    "external_samples": len(samples),
                    "external_minflt_delta": int(samples[-1]["minflt"]) - int(samples[0]["minflt"]),
                    "external_majflt_delta": int(samples[-1]["majflt"]) - int(samples[0]["majflt"]),
                    "exit_code": 0,
                }
            )
            external_rows.append(
                {
                    "group": "B", "profile": profile, "trim_at": trim_at, "rep": rep,
                    "samples": len(samples), "overruns": next(
                        line.split("=", 1)[1] for line in (cell / "external_sampler_meta.txt").read_text().splitlines()
                        if line.startswith("deadline_overruns=")
                    ),
                    "pid_count": len({row["pid"] for row in samples}),
                    "minflt_delta": int(samples[-1]["minflt"]) - int(samples[0]["minflt"]),
                    "majflt_delta": int(samples[-1]["majflt"]) - int(samples[0]["majflt"]),
                }
            )

before = (pull / "dmesg_before.txt").read_text(encoding="utf-8", errors="replace").splitlines()
after = (pull / "dmesg_after.txt").read_text(encoding="utf-8", errors="replace").splitlines()
increment, method = dmesg_increment(before, after)
(output / "dmesg_increment.txt").write_text("\n".join(increment) + ("\n" if increment else ""), encoding="utf-8")
bad_terms = ("out of memory", "oom", "lowmemory", "low memory", "lmk", "killed process")
bad_lines = [line for line in increment if any(term in line.lower() for term in bad_terms)]

z_before = [int(value) for value in (pull / "zram_mm_stat_before.txt").read_text().split()]
z_after = [int(value) for value in (pull / "zram_mm_stat_after.txt").read_text().split()]
require(len(z_before) >= 3 and len(z_after) >= 3, "short zram mm_stat")
health = {
    "dmesg_increment_method": method,
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
}
require(not bad_lines, "OOM/LMK evidence found in dmesg increment")
require(health["governor_restored_schedutil_count"] == 4, "governor was not restored on all four cores")

write_tsv(output / "a_cells.tsv", a_rows)
write_tsv(output / "b_cycles.tsv", b_cycle_rows)
write_tsv(output / "b_cells.tsv", b_cell_rows)
write_tsv(output / "external_summary.tsv", external_rows)
with (output / "health.json").open("w", encoding="utf-8") as stream:
    json.dump(health, stream, indent=2, sort_keys=True)
    stream.write("\n")

print(f"validated A={len(a_rows)} cells B={len(b_cell_rows)} cells B_cycles={len(b_cycle_rows)}")
