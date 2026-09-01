#!/usr/bin/env python3
"""Audit published shape definitions and classify product PD phenotypes.

The classifier works from the public, alias-only raw TSVs.  It intentionally
keeps strict no-response (byte-exact) separate from sub-threshold movement and
does not force swap-confounded traces into the a/b/c buckets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


INTEGER_FIELDS = {
    "sample",
    "epoch_ns",
    "pid",
    "glibc_heap_pd_kb",
    "other_anon_pd_kb",
    "file_backed_pd_kb",
    "total_pd_kb",
    "minflt",
    "majflt",
    "MemAvailable_kb",
    "zram_used_kb",
    "zram_orig_bytes",
    "zram_compr_bytes",
    "zram_mem_used_bytes",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows: list[dict[str, Any]] = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty TSV: {path}")
    for row in rows:
        for field in INTEGER_FIELDS.intersection(row):
            if row[field] not in {"", "NA"}:
                row[field] = int(row[field])
    return rows


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(bool(rows), f"no rows for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def group_by(rows: Iterable[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return dict(grouped)


def pid_segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_pid: int | None = None
    for row in rows:
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


def planned_start_ns(key_rows: list[dict[str, Any]]) -> int:
    estimates = sorted(
        int(row["actual_epoch_ns"])
        - int(row["target_offset_s"]) * 1_000_000_000
        - round(float(row["lateness_ms"]) * 1_000_000)
        for row in key_rows
    )
    require(bool(estimates), "no key rows for planned-start estimate")
    middle = len(estimates) // 2
    if len(estimates) % 2:
        return estimates[middle]
    return (estimates[middle - 1] + estimates[middle]) // 2


def add_actual_cyclic_stages(
    rows: list[dict[str, Any]], key_rows: list[dict[str, Any]]
) -> None:
    start_ns = planned_start_ns(key_rows)
    for row in rows:
        elapsed_s = (int(row["epoch_ns"]) - start_ns) / 1_000_000_000
        if elapsed_s < 60:
            actual_stage = "P0"
        elif elapsed_s < 540:
            actual_stage = f"R{int((elapsed_s - 60) // 60) + 1}"
        else:
            actual_stage = "P1"
        row["actual_stage"] = actual_stage


def largest_drawdown(rows: list[dict[str, Any]]) -> dict[str, Any]:
    require(bool(rows), "drawdown requested for empty sequence")
    peak = rows[0]
    best_peak = rows[0]
    best_trough = rows[0]
    best_drop = 0
    for row in rows[1:]:
        if row["glibc_heap_pd_kb"] > peak["glibc_heap_pd_kb"]:
            peak = row
        drop = peak["glibc_heap_pd_kb"] - row["glibc_heap_pd_kb"]
        if drop > best_drop:
            best_drop = drop
            best_peak = peak
            best_trough = row
    return {
        "drop_kb": best_drop,
        "peak": best_peak,
        "trough": best_trough,
        "zram_orig_delta_bytes": (
            best_trough["zram_orig_bytes"] - best_peak["zram_orig_bytes"]
        ),
        "zram_used_delta_kb": (
            best_trough["zram_used_kb"] - best_peak["zram_used_kb"]
        ),
        "majflt_delta": best_trough["majflt"] - best_peak["majflt"],
    }


def release_ratio_census(
    rows: list[dict[str, Any]], baselines: dict[tuple[str, int], int]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for target, target_rows in group_by(rows, "target").items():
        segments = pid_segments(target_rows)
        require(bool(segments), f"no valid segment for {target}")
        exact_constant = all(
            len({row["glibc_heap_pd_kb"] for row in segment}) == 1
            for segment in segments
        )
        segment_facts = []
        for segment in segments:
            segment_start = segment[0]["glibc_heap_pd_kb"]
            baseline_key = (target, segment[0]["pid"])
            baseline = baselines.get(baseline_key, segment_start)
            baseline_source = "S1" if baseline_key in baselines else "segment-first-sample"
            threshold = baseline * 0.10
            drawdown = largest_drawdown(segment)
            retained_height = segment[-1]["glibc_heap_pd_kb"] - segment_start
            material_fall = drawdown["drop_kb"] >= threshold
            swap_out_excluded = (
                drawdown["zram_orig_delta_bytes"] <= 0
                and drawdown["majflt_delta"] == 0
            )
            drawdown_to_retained_pct = (
                drawdown["drop_kb"] / retained_height * 100
                if retained_height > 0
                else None
            )
            same_order_automatic_fall = (
                material_fall
                and retained_height > 0
                and drawdown["drop_kb"] >= retained_height * 0.10
            )
            segment_facts.append(
                {
                    "pid": segment[0]["pid"],
                    "samples": len(segment),
                    "baseline_kb": baseline,
                    "baseline_source": baseline_source,
                    "segment_start_kb": segment_start,
                    "threshold_kb": threshold,
                    "end_kb": segment[-1]["glibc_heap_pd_kb"],
                    "retained_height_kb": retained_height,
                    "max_drawdown_kb": drawdown["drop_kb"],
                    "material_fall": material_fall,
                    "swap_out_excluded": swap_out_excluded,
                    "drawdown_to_retained_pct": drawdown_to_retained_pct,
                    "same_order_automatic_fall": same_order_automatic_fall,
                    **{
                        key: drawdown[key]
                        for key in (
                            "zram_orig_delta_bytes",
                            "zram_used_delta_kb",
                            "majflt_delta",
                        )
                    },
                }
            )

        self_reclaim = any(
            fact["material_fall"] and fact["swap_out_excluded"]
            for fact in segment_facts
        )
        retention = any(
            fact["retained_height_kb"] >= fact["threshold_kb"]
            and not fact["same_order_automatic_fall"]
            for fact in segment_facts
        )
        material_confounded = any(
            fact["material_fall"] and not fact["swap_out_excluded"]
            for fact in segment_facts
        )
        if self_reclaim and retention:
            classification = "a-self-reclaim+b-retention"
        elif self_reclaim:
            classification = "a-self-reclaim"
        elif retention:
            classification = "b-retention"
        elif exact_constant:
            classification = "c-byte-exact-no-response"
        elif material_confounded:
            classification = "u-confounded"
        else:
            classification = "n-subthreshold"

        decisive = max(
            segment_facts,
            key=lambda fact: max(
                fact["max_drawdown_kb"], max(0, fact["retained_height_kb"])
            ),
        )
        records.append(
            {
                "target": target,
                "classification": classification,
                "pid_segments": len(segments),
                "valid_samples": sum(len(segment) for segment in segments),
                "baseline_kb": decisive["baseline_kb"],
                "baseline_source": decisive["baseline_source"],
                "segment_start_kb": decisive["segment_start_kb"],
                "material_threshold_kb": f'{decisive["threshold_kb"]:.1f}',
                "retained_height_kb": decisive["retained_height_kb"],
                "max_drawdown_kb": decisive["max_drawdown_kb"],
                "drawdown_zram_orig_delta_bytes": decisive["zram_orig_delta_bytes"],
                "drawdown_zram_used_delta_kb": decisive["zram_used_delta_kb"],
                "drawdown_majflt_delta": decisive["majflt_delta"],
                "drawdown_to_retained_pct": (
                    "NA"
                    if decisive["drawdown_to_retained_pct"] is None
                    else f'{decisive["drawdown_to_retained_pct"]:.6f}'
                ),
                "same_order_automatic_fall": (
                    "yes" if decisive["same_order_automatic_fall"] else "no"
                ),
                "exact_constant": "yes" if exact_constant else "no",
                "note": (
                    "PID restart; classification uses within-PID segments only"
                    if len(segments) > 1
                    else (
                        "retained floor remains a candidate; automatic-reclaim "
                        "capability is proven for the drawdown component"
                        if self_reclaim and retention
                        else "NA"
                    )
                ),
            }
        )
    return records


def plateau_crosscheck(
    plateau_rows: list[dict[str, Any]], cyclic_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cyclic_alias = {
        "ServiceA": "ServiceA",
        "ServiceB": "ServiceB",
        "ChannelLoader": "ServiceH[ServiceK]",
        "WebRuntime": "ServiceE",
    }
    cyclic_by_alias = {
        cyclic_alias[target]: rows
        for target, rows in group_by(cyclic_rows, "target").items()
    }
    records: list[dict[str, Any]] = []
    for target, rows in group_by(plateau_rows, "target").items():
        valid = [row for row in rows if row["pid"] != "NA"]
        require(valid, f"no valid plateau rows for {target}")
        require(len({row["pid"] for row in valid}) == 1, f"plateau PID changed for {target}")
        p0 = [row for row in valid if row["stage"] == "P0"]
        require(p0, f"missing P0 for {target}")
        baseline = p0[-1]["glibc_heap_pd_kb"]
        threshold = baseline * 0.05
        values = [row["glibc_heap_pd_kb"] for row in valid]
        drawdown = largest_drawdown(valid)
        exact_constant = len(set(values)) == 1
        end_delta = values[-1] - baseline
        max_rise = max(values) - baseline
        plateau_material_fall = drawdown["drop_kb"] >= threshold
        plateau_swap_out_excluded = (
            drawdown["zram_orig_delta_bytes"] <= 0
            and drawdown["majflt_delta"] == 0
        )

        cyclic = cyclic_by_alias.get(target, [])
        cyclic_summary = "NA"
        cyclic_drawdown = "NA"
        cyclic_end_delta = "NA"
        cyclic_floor_start = "NA"
        cyclic_final_round_valley = "NA"
        cyclic_final_round_floor_delta = "NA"
        if cyclic:
            cvalues = [row["glibc_heap_pd_kb"] for row in cyclic]
            cdraw = largest_drawdown(cyclic)
            cyclic_drawdown = cdraw["drop_kb"]
            cyclic_end_delta = cvalues[-1] - cvalues[0]
            def stage_of(row: dict[str, Any]) -> Any:
                return row.get("actual_stage", row.get("stage"))

            p0_rows = [row for row in cyclic if stage_of(row) == "P0"]
            numbered_rounds = sorted(
                {
                    int(str(stage_of(row))[1:])
                    for row in cyclic
                    if str(stage_of(row) or "").startswith("R")
                    and str(stage_of(row))[1:].isdigit()
                }
            )
            if p0_rows and numbered_rounds:
                final_stage = f"R{numbered_rounds[-1]}"
                final_round_rows = [row for row in cyclic if stage_of(row) == final_stage]
                final_round_drawdown = largest_drawdown(final_round_rows)
                cyclic_floor_start = p0_rows[-1]["glibc_heap_pd_kb"]
                cyclic_final_round_valley = final_round_drawdown["trough"][
                    "glibc_heap_pd_kb"
                ]
                cyclic_final_round_floor_delta = (
                    cyclic_final_round_valley - cyclic_floor_start
                )
            cthreshold = cvalues[0] * 0.05
            if len(set(cvalues)) == 1:
                cyclic_summary = "byte-exact-no-response"
            elif (
                cdraw["drop_kb"] >= cthreshold
                and cdraw["zram_orig_delta_bytes"] <= 0
                and cdraw["majflt_delta"] == 0
            ):
                cyclic_summary = "material-self-reclaim"
            elif cvalues[-1] - cvalues[0] >= cthreshold:
                cyclic_summary = "retained-floor"
            else:
                cyclic_summary = "subthreshold-or-unstable"

        if target == "ServiceA" and cyclic_summary == "material-self-reclaim":
            classification = "a-self-reclaim+b-residual"
            floor_delta = (
                cyclic_final_round_floor_delta
                if cyclic_final_round_floor_delta != "NA"
                else cyclic_end_delta
            )
            note = (
                "periodic component self-reclaims; final cyclic floor retains "
                f"{int(floor_delta):+d} kB over the initial floor"
            )
        elif target == "ServiceH[ServiceK]" and cyclic_summary == "retained-floor":
            classification = "b-retention"
            note = (
                f"2 s plateau height {max_rise} kB is an upper bound; "
                "cyclic floor also rises"
            )
        elif exact_constant and cyclic_summary in {"NA", "byte-exact-no-response"}:
            classification = "c-byte-exact-no-response"
            note = "NA"
        elif cyclic_summary == "material-self-reclaim":
            classification = "a-self-reclaim"
            note = "cyclic evidence controls over coarse plateau sampling"
        elif cyclic_summary == "retained-floor":
            classification = "b-retention"
            note = "cyclic evidence controls over coarse plateau sampling"
        elif cyclic_summary == "subthreshold-or-unstable":
            classification = "u-cross-probe-unstable"
            note = "coarse plateau movement is not a stable retained surface in cyclic data"
        elif plateau_material_fall and plateau_swap_out_excluded:
            classification = "a-coarse-only"
            note = "2 s plateau-only evidence; timing and short extrema are resolution-limited"
        elif end_delta >= threshold and not plateau_material_fall:
            classification = "b-coarse-only"
            note = "2 s plateau-only retained floor"
        elif plateau_material_fall:
            classification = "u-confounded-coarse"
            note = "material fall has zram/majflt confounding in the 2 s trace"
        else:
            classification = "n-subthreshold"
            note = "not byte-exact, but below the frozen 5% response gate"

        records.append(
            {
                "target": target,
                "classification": classification,
                "p0_baseline_kb": baseline,
                "material_threshold_kb": f"{threshold:.1f}",
                "max_rise_kb": max_rise,
                "end_minus_p0_kb": end_delta,
                "max_drawdown_kb": drawdown["drop_kb"],
                "drawdown_zram_orig_delta_bytes": drawdown["zram_orig_delta_bytes"],
                "drawdown_majflt_delta": drawdown["majflt_delta"],
                "cyclic_max_drawdown_kb": cyclic_drawdown,
                "cyclic_end_minus_start_kb": cyclic_end_delta,
                "cyclic_floor_reference_start_kb": cyclic_floor_start,
                "cyclic_final_round_valley_kb": cyclic_final_round_valley,
                "cyclic_final_round_floor_delta_kb": cyclic_final_round_floor_delta,
                "cyclic_summary": cyclic_summary,
                "note": note,
            }
        )
    return records


def definition_audit(paths: dict[str, Path], repo_root: Path) -> dict[str, Any]:
    patterns = {
        "cyclic": {
            "tail_minimum": "valley = min(sequence[fall_index:]",
            "fall_edge": "fall_seconds = valley[\"elapsed_s\"] - fall[\"elapsed_s\"]",
            "peak_band": "peak_seconds = fall[\"elapsed_s\"] - high_entry[\"elapsed_s\"]",
        },
        "plateau": {
            "stage_peak": "glibc_peaks = [int(stage_lookup[(target, stage)][\"glibc_peak_kb\"])",
            "adjacent_peak_pair": "if abs(glibc_peaks[i] - glibc_peaks[i - 1]) < threshold:",
        },
        "release_ratio": {
            "running_peak": "if value > peak[\"glibc_heap_pd_kb\"]:",
            "event_trough": "if value < active[\"trough\"][\"glibc_heap_pd_kb\"]:",
        },
    }
    result: dict[str, Any] = {}
    for name, path in paths.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        matches: dict[str, Any] = {}
        for label, needle in patterns[name].items():
            found = [index + 1 for index, line in enumerate(lines) if needle in line]
            require(len(found) == 1, f"{name}:{label} definition not uniquely found")
            matches[label] = {"line": found[0], "source": lines[found[0] - 1].strip()}
        result[name] = {
            "path": str(path.relative_to(repo_root)),
            "sha256": sha256(path),
            "definitions": matches,
            "uses_min_over_tail_for_edge": name == "cyclic",
            "published_shape_numbers_affected": (
                ["fall_edge", "peak_band"] if name == "cyclic" else []
            ),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()

    release_path = root / "data/raw/product_release_ratio_timeseries_20260814/raw/timeseries.tsv"
    release_baseline_path = (
        root / "data/raw/cyclic_fall_attribution_20260901/release_ratio_baselines.tsv"
    )
    plateau_path = root / "data/raw/product_plateau_probe_20260814/raw/timeseries.tsv"
    cyclic_path = root / "data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv"
    cyclic_keys_path = root / "data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv"
    release_rows = read_tsv(release_path)
    release_baseline_rows = read_tsv(release_baseline_path)
    release_baselines = {
        (str(row["target"]), int(row["pid"])): int(row["glibc_baseline_kb"])
        for row in release_baseline_rows
    }
    plateau_rows = read_tsv(plateau_path)
    cyclic_rows = read_tsv(cyclic_path)
    cyclic_key_rows = read_tsv(cyclic_keys_path)
    add_actual_cyclic_stages(cyclic_rows, cyclic_key_rows)

    release_records = release_ratio_census(release_rows, release_baselines)
    plateau_records = plateau_crosscheck(plateau_rows, cyclic_rows)
    audit = definition_audit(
        {
            "cyclic": root / "tools/runners/product_cyclic_target_probe_20260814/analyze_cyclic.py",
            "plateau": root / "tools/runners/product_plateau_probe_20260814/scripts/analyze_plateau.py",
            "release_ratio": root / "tools/runners/product_release_ratio_timeseries_20260814/scripts/analyze_timeseries.py",
        },
        root,
    )
    audit["inputs"] = {
        "release_ratio_timeseries_sha256": sha256(release_path),
        "release_ratio_baselines_sha256": sha256(release_baseline_path),
        "plateau_timeseries_sha256": sha256(plateau_path),
        "cyclic_timeseries_sha256": sha256(cyclic_path),
        "cyclic_key_timeline_sha256": sha256(cyclic_keys_path),
    }
    audit["classifier"] = {
        "release_ratio_material_gate": "10% of S1 baseline when available; otherwise first sample in stable-PID segment",
        "release_ratio_retained_height": "last minus first observed sample in each stable-PID segment",
        "plateau_material_gate": "5% of final P0 sample",
        "a": "material drawdown, no positive zram_orig delta, majflt delta zero",
        "b": "material retained floor without an automatic drawdown >=10% of that floor; may coexist with a smaller automatic drawdown component",
        "c": "byte-exact invariant PD",
        "n": "non-exact movement below the frozen response gate",
        "u": "material but swap/PID/cross-probe confounded",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_tsv(args.output / "release_ratio_phenotypes.tsv", release_records)
    write_tsv(args.output / "plateau_cyclic_crosscheck.tsv", plateau_records)
    (args.output / "definition_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "release_targets": len(release_records),
                "plateau_targets": len(plateau_records),
                "cyclic_min_over_tail": audit["cyclic"]["uses_min_over_tail_for_edge"],
                "plateau_min_over_tail": audit["plateau"]["uses_min_over_tail_for_edge"],
                "release_ratio_min_over_tail": audit["release_ratio"]["uses_min_over_tail_for_edge"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
