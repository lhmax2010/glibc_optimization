#!/usr/bin/env python3
"""Build the self-contained Chinese glibc memory-optimization Demo report."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def nearest_rank(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(1, math.ceil(quantile * len(ordered))) - 1]


def scale(value: float, low: float, high: float, start: float, extent: float) -> float:
    if high == low:
        return start + extent / 2
    return start + (value - low) * extent / (high - low)


def servicea_chart(rows: list[dict[str, str]], rounds: list[dict[str, str]]) -> str:
    width, height = 980, 360
    left, top, plot_w, plot_h = 62, 24, 888, 270
    samples = [(int(row["sample"]), int(row["glibc_heap_pd_kb"])) for row in rows]
    xmin, xmax = samples[0][0], samples[-1][0]
    ymin, ymax = min(value for _, value in samples), max(value for _, value in samples)
    points = " ".join(
        f"{scale(sample, xmin, xmax, left, plot_w):.2f},{top + plot_h - scale(value, ymin, ymax, 0, plot_h):.2f}"
        for sample, value in samples
    )
    grid = []
    for index in range(5):
        y = top + plot_h * index / 4
        value = ymax - (ymax - ymin) * index / 4
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end">{value / 1024:.1f}</text>')
    markers = []
    for item in rounds:
        round_id = esc(item["round"])
        peak_sample = int(item["peak_sample"])
        peak_value = int(item["peak_glibc_kb"])
        valley_sample = int(item["valley_sample"])
        valley_value = int(item["valley_glibc_kb"])
        px = scale(peak_sample, xmin, xmax, left, plot_w)
        py = top + plot_h - scale(peak_value, ymin, ymax, 0, plot_h)
        vx = scale(valley_sample, xmin, xmax, left, plot_w)
        vy = top + plot_h - scale(valley_value, ymin, ymax, 0, plot_h)
        markers.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" class="peak"/>')
        markers.append(f'<circle cx="{vx:.2f}" cy="{vy:.2f}" r="4" class="valley"/>')
        markers.append(f'<text x="{px:.2f}" y="{max(14, py - 9):.2f}" text-anchor="middle" class="round">{round_id}</text>')
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="servicea-title servicea-desc">
  <title id="servicea-title">ServiceA glibc heap Private Dirty 周期时间线</title>
  <desc id="servicea-desc">八轮周期的峰值和谷底；橙点是峰值，绿点是谷底。</desc>
  {''.join(grid)}
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/>
  <polyline points="{points}" class="series"/>
  {''.join(markers)}
  <text x="18" y="{top + plot_h / 2}" transform="rotate(-90 18 {top + plot_h / 2})" text-anchor="middle">glibc heap PD (MiB)</text>
  <text x="{left + plot_w / 2}" y="330" text-anchor="middle">采样序号（1 s 口径）</text>
  <g class="legend"><circle cx="690" cy="346" r="4" class="peak"/><text x="700" y="350">峰值</text><circle cx="770" cy="346" r="4" class="valley"/><text x="780" y="350">谷底</text></g>
</svg>"""


def bar_chart(items: list[tuple[str, float, str]], *, title: str, unit: str, ceiling: float | None = None) -> str:
    width, height = 820, 300
    left, top, plot_w, plot_h = 80, 36, 700, 210
    maximum = ceiling or max(value for _, value, _ in items) * 1.18
    bar_width = min(110, plot_w / max(1, len(items)) * 0.55)
    slot = plot_w / len(items)
    bars = []
    for index, (label, value, css_class) in enumerate(items):
        x = left + slot * index + (slot - bar_width) / 2
        bar_h = value / maximum * plot_h
        y = top + plot_h - bar_h
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" class="bar {css_class}"/>')
        bars.append(f'<text x="{x + bar_width / 2:.1f}" y="{y - 9:.1f}" text-anchor="middle" class="value">{value:.3f}</text>')
        bars.append(f'<text x="{x + bar_width / 2:.1f}" y="{top + plot_h + 23:.1f}" text-anchor="middle">{esc(label)}</text>')
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <title>{esc(title)}</title>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/>
  {''.join(bars)}
  <text x="20" y="{top + plot_h / 2}" transform="rotate(-90 20 {top + plot_h / 2})" text-anchor="middle">{esc(unit)}</text>
</svg>"""


def dot_chart(values: list[float]) -> str:
    width, height = 820, 190
    left, top, plot_w = 70, 42, 700
    low, high = min(values), max(values)
    dots = []
    for index, value in enumerate(sorted(values)):
        x = scale(value, low, high, left, plot_w)
        y = top + (index % 7) * 11
        dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" class="dot"/>')
    ticks = []
    for index in range(5):
        value = low + (high - low) * index / 4
        x = left + plot_w * index / 4
        ticks.append(f'<line x1="{x:.1f}" y1="125" x2="{x:.1f}" y2="132" class="axis"/><text x="{x:.1f}" y="151" text-anchor="middle">{value:.2f}</text>')
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="153 次 GStreamer release-point trim 耗时分布">
  <title>153 次 GStreamer release-point trim 耗时分布</title>
  {''.join(dots)}
  <line x1="{left}" y1="128" x2="{left + plot_w}" y2="128" class="axis"/>
  {''.join(ticks)}
  <text x="{left + plot_w / 2}" y="178" text-anchor="middle">trim elapsed (ms)</text>
</svg>"""


def build(repo: Path, source_commit: str) -> str:
    raw = repo / "data/raw"
    guide = "demo_reproduction_guide_20260901.md"
    service_rows = [
        row for row in read_tsv(raw / "product_cyclic_target_probe_20260814/raw/timeseries.tsv")
        if row["target"] == "ServiceA"
    ]
    rounds = read_tsv(raw / "cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv")
    quality = json.loads((raw / "cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json").read_text())
    attribution = json.loads((raw / "cyclic_fall_attribution_20260901/summary.json").read_text())
    release = read_tsv(raw / "cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv")
    plateau = read_tsv(raw / "cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv")
    a2_cells = read_tsv(raw / "a_anchor_replication_20260904/a_cells.tsv")
    a2_decision = json.loads((raw / "a_anchor_replication_20260904/decision.json").read_text())
    b_cells = read_tsv(raw / "s4_retention_20260901/b_cells.tsv")
    b_cycles = read_tsv(raw / "s4_retention_20260901/b_cycles.tsv")
    s4_health = json.loads((raw / "s4_retention_20260901/health.json").read_text())
    gst_cycles = read_tsv(raw / "gst_trim_cost_20260901/cycles.tsv")
    gst_reps = read_tsv(raw / "gst_trim_cost_20260901/repetitions.tsv")
    gst_comparison = json.loads((raw / "gst_trim_cost_20260901/comparison.json").read_text())
    batch_rows = read_tsv(raw / "demo_reproduction_20260901/batch_release_phase.tsv")
    native = json.loads((raw / "tizen_native_evidence_20260904/summary.json").read_text())
    native_health = json.loads((raw / "tizen_native_evidence_20260904/health.json").read_text())
    acceptance = json.loads((repo / "tools/reproduce/acceptance_bands.json").read_text())

    expected_docs = (
        "docs/demo_narrative_20260901.md",
        "docs/product_landing_recommendation_20260901.md",
        "docs/demo_reproduction_guide_20260901.md",
        "docs/demo_package_20260902.md",
        "docs/tizen_native_evidence_20260904.md",
    )
    for relative in expected_docs:
        if not (repo / relative).is_file():
            raise FileNotFoundError(relative)

    releases = [int(row["total_release_kb"]) for row in rounds]
    peak_valley_median = statistics.median(releases)
    service_counter = quality["target_counters"]["ServiceA"]
    zram_total = sum(
        int(row["zram_orig_peak_to_valley_bytes"])
        for row in read_tsv(raw / "cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv")
        if row["target"] == "ServiceA"
    )
    release_counts = {"a": 0, "b": 0, "c": 0, "N": 0}
    for row in release:
        value = row["classification"]
        if value.startswith("a-"):
            release_counts["a"] += 1
        if "+b-" in value or value.startswith("b-"):
            release_counts["b"] += 1
        if value.startswith("c-"):
            release_counts["c"] += 1
        if value.startswith("n-"):
            release_counts["N"] += 1
    plateau_counts = {"a": 0, "b": 0, "c": 0, "N": 0, "U": 0}
    for row in plateau:
        value = row["classification"]
        if value.startswith("a-"):
            plateau_counts["a"] += 1
        if "+b-" in value or value.startswith("b-"):
            plateau_counts["b"] += 1
        if value.startswith("c-"):
            plateau_counts["c"] += 1
        if value.startswith("n-"):
            plateau_counts["N"] += 1
        if value.startswith("u-"):
            plateau_counts["U"] += 1

    release_by_target = {row["target"]: row for row in release}
    plateau_by_target = {row["target"]: row for row in plateau}
    anchors = {
        profile: float(item["center_pct"])
        for profile, item in a2_decision["candidate_bands"].items()
    }
    anchor_radius = {
        profile: float(item["plus_minus_pp"])
        for profile, item in a2_decision["candidate_bands"].items()
    }
    anchor_trim_max = max(float(row["trim_elapsed_ms"]) for row in a2_cells)
    b_by_profile: dict[str, list[dict[str, str]]] = {}
    for row in b_cells:
        if row["trim_at"] == "valley":
            b_by_profile.setdefault(row["profile"], []).append(row)
    b_ratio = {
        profile: statistics.median(float(row["trim_reclaim_pct_of_released_median"]) for row in rows)
        for profile, rows in b_by_profile.items()
    }
    s4_trim_median_by_profile = {
        profile: float(statistics.median(
            Decimal(row["trim_elapsed_ms"])
            for row in b_cycles
            if row["trim_at"] == "valley" and row["profile"] == profile
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        for profile in ("mixed", "medium-only")
    }
    batch_single = [row for row in batch_rows if row["series"] == "single"]
    batch_scale = [row for row in batch_rows if row["series"] == "scale"]
    batch_pct = statistics.median(float(row["reclaim_pct"]) for row in batch_single)
    batch_mib = statistics.median(float(row["reclaimed_mib"]) for row in batch_single)
    next_fault = {}
    for profile in ("mixed", "medium-only"):
        valley = next(row for row in b_cells if row["profile"] == profile and row["trim_at"] == "valley" and row["rep"] == "1")
        none = next(row for row in b_cells if row["profile"] == profile and row["trim_at"] == "none")
        next_fault[profile] = int(valley["cycle1_next_minflt"]) - int(none["cycle1_next_minflt"])

    trim_cycles = [row for row in gst_cycles if row["arm"] == "trim-at-loop-release"]
    trim_times = [float(row["trim_elapsed_ms"]) for row in trim_cycles]
    first_releases = [row for row in trim_cycles if row["cycle"] == "1"]
    gst_dist = [nearest_rank(trim_times, q) for q in (0.5, 0.95, 0.99)] + [max(trim_times)]
    gst_arms = {row["arm"]: row for row in read_tsv(raw / "gst_trim_cost_20260901/arm_summary.tsv")}
    gst_p99_margin = float(gst_comparison["none_p99_repeat_dispersion_ms"]) - float(gst_comparison["delta_p99_ms"])
    gst_p99_threshold_pct = float(gst_comparison["delta_p99_ms"]) * 100 / float(gst_comparison["none_p99_repeat_dispersion_ms"])
    gst_p50_delta = float(gst_arms["trim-at-loop-release"]["business_p50_ms_median"]) - float(gst_arms["none"]["business_p50_ms_median"])
    gst_p50_dispersion = float(gst_arms["none"]["business_p50_ms_range"])
    gst_minflt_per_cycle = round(
        (int(gst_arms["trim-at-loop-release"]["primary_minflt_sum_median"]) - int(gst_arms["none"]["primary_minflt_sum_median"]))
        / int(gst_comparison["primary_samples_per_repeat"])
    )
    p99_items = [
        (f"none r{row['rep']}", float(row["business_p99_ms"]), "none")
        for row in gst_reps if row["arm"] == "none"
    ] + [
        (f"trim r{row['rep']}", float(row["business_p99_ms"]), "trim")
        for row in gst_reps if row["arm"] == "trim-at-loop-release"
    ]
    p99_origin = min(value for _, value, _ in p99_items) - 1
    p99_display = [(label, value - p99_origin, css) for label, value, css in p99_items]

    # Positive-control assertions deliberately fail the build when a public
    # evidence fixture drifts; they are not estimates or duplicated analysis.
    assert peak_valley_median == 6212
    assert Decimal(str(peak_valley_median)) / Decimal(1024) == Decimal("6.06640625")
    assert round(peak_valley_median / 1024, 2) == 6.07
    assert attribution["F3"]["valley_band_entry_delay_min_s"] == 5.223693
    assert attribution["F3"]["valley_band_entry_delay_max_s"] == 8.910626
    assert attribution["F2"]["large_step_count"] == 32
    assert attribution["F2"]["near_equal_within_50pct_count"] == 0
    assert service_counter["majflt_first"] == service_counter["majflt_last"] == 167
    assert zram_total == -262144
    assert release_counts == {"a": 1, "b": 4, "c": 1, "N": 5}
    assert plateau_counts == {"a": 1, "b": 2, "c": 1, "N": 6, "U": 1}
    assert release_by_target["ServiceD"]["classification"] == "b-retention"
    assert plateau_by_target["ServiceD"]["classification"] == "n-subthreshold"
    assert int(release_by_target["enlightenment"]["retained_height_kb"]) == 1736
    assert int(release_by_target["enlightenment"]["max_drawdown_kb"]) == 120
    assert int(plateau_by_target["ServiceH[ServiceK]"]["max_rise_kb"]) == 2360
    assert int(plateau_by_target["ServiceH[ServiceK]"]["cyclic_end_minus_start_kb"]) == 868
    assert int(release_by_target["ServiceH"]["retained_height_kb"]) == 580
    assert int(plateau_by_target["ServiceA"]["cyclic_final_round_floor_delta_kb"]) == 788
    assert round(batch_pct, 4) == 48.9451 and round(batch_mib, 6) == 1.359375
    assert len(batch_scale) == 8
    assert round(min(float(row["reclaim_pct"]) for row in batch_scale), 4) == 48.5232
    assert round(max(float(row["reclaim_pct"]) for row in batch_scale), 4) == 49.3671
    assert a2_decision["verdict"] == "H-V"
    assert anchors == {"mixed": 52.794499, "medium-only": 50.669791}
    assert anchor_radius == {"mixed": 4.304705, "medium-only": 4.918088}
    assert all(item["n"] == 8 for item in a2_decision["candidate_bands"].values())
    assert round(anchor_trim_max, 6) == 15.885352
    assert b_ratio == {"mixed": 81.661264, "medium-only": 84.446566}
    assert min(float(row["trim_reclaim_pct_of_released"]) for row in b_cycles if row["trim_at"] == "valley") == 80.175875
    assert max(float(row["trim_reclaim_pct_of_released"]) for row in b_cycles if row["trim_at"] == "valley") == 85.453954
    assert s4_trim_median_by_profile == {"mixed": 1.233269, "medium-only": 1.218361}
    assert next_fault == {"mixed": 1351, "medium-only": 1465}
    assert gst_comparison["delta_p99_ms"] == 6.228611
    assert gst_comparison["none_p99_repeat_dispersion_ms"] == 6.784167
    assert gst_comparison["business_cost_visible"] is False
    assert round(gst_p99_margin, 6) == 0.555556
    assert round(gst_p99_threshold_pct, 1) == 91.8
    assert round(gst_p50_delta, 3) == 1.870 and round(gst_p50_dispersion, 3) == 0.174
    assert gst_minflt_per_cycle == 359
    assert len(trim_times) == 153
    assert [round(value, 6) for value in gst_dist] == [0.671556, 0.818315, 0.842185, 0.856944]
    assert min(float(row["reclaim_pct_of_pre"]) for row in first_releases) == 51.014041
    assert max(float(row["reclaim_pct_of_pre"]) for row in first_releases) == 51.406250
    assert min(int(row["glibc_pd_reclaimed_kb"]) for row in first_releases) == 1308
    assert max(int(row["glibc_pd_reclaimed_kb"]) for row in first_releases) == 1316
    assert acceptance["schema"] == "glibc-memopt-demo.acceptance.v4"
    assert acceptance["tolerance_bands"]["s4_a_anchor_reclaim_pct"]["center_pct_by_profile"] == anchors
    assert acceptance["tolerance_bands"]["s4_a_anchor_reclaim_pct"]["plus_minus_pp_by_profile"] == anchor_radius
    assert native["completion"] == {
        "t1_completed": 1,
        "t1_preregistered": 5,
        "t1_stop": "pipeline EOS at 60.100233983 s before T1_2",
        "t2_baseline_completed": 3,
        "t2_baseline_preregistered": 3,
        "t2_release_phase_completed": 0,
        "t2_release_phase_preregistered": 1,
        "t2_release_phase_stop": "attach-panel-gallery was no longer running at the first terminate command",
    }
    assert native["t1"]["reclaimed_kb"] == [12]
    assert native["t2"]["reclaimed_kb"] == [272, 4, 4]
    assert native["t2"]["pre_sample_intervals_s"] == [119.80687691, 119.856460299]
    assert native["t2"]["interval_requirement_met"] is False
    assert [row.get("m7_rest_bytes") for row in native["cells"] if row["group"] == "T2"] == [6118675, 6118694, 6118706]
    assert all(row["project_reclaimed_kb"] == row["memps_reclaimed_kb"] for row in native["cells"])
    assert native_health["enlightenment"]["idle_glibc_heap_pd_min_kb"] == native_health["enlightenment"]["idle_glibc_heap_pd_max_kb"] == 3472
    assert native_health["formal_window"]["stability_monitor_new_alerts"] == 0
    assert native_health["formal_window"]["dmesg_oom_lmk_new_matches"] == 0
    assert [native_health["formal_window"][key] for key in (
        "zram_original_data_size_delta", "zram_compressed_data_size_delta", "zram_mem_used_total_delta"
    )] == [0, 0, 0]

    evidence_service = "../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv"
    evidence_s4_a = "../data/raw/a_anchor_replication_20260904/a_cells.tsv"
    evidence_s4_a_decision = "../data/raw/a_anchor_replication_20260904/decision.json"
    evidence_s4_b = "../data/raw/s4_retention_20260901/b_cycles.tsv"
    evidence_gst = "../data/raw/gst_trim_cost_20260901/cycles.tsv"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tizen glibc 门控 trim Demo 报告</title>
<style>
:root{{--ink:#17212b;--muted:#576574;--paper:#f6f3ed;--card:#fff;--navy:#17324d;--teal:#087f78;--orange:#dc6b2f;--line:#d8d3ca;--soft:#e8f3f1;--warn:#fff1d6;--danger:#8a2f2f}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.62 system-ui,-apple-system,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif}}
a{{color:#075c75;text-underline-offset:3px}} a:hover{{color:#8b3d1c}} header{{background:var(--navy);color:white;padding:72px max(24px,calc((100vw - 1120px)/2)) 54px;border-bottom:8px solid var(--teal)}}
header p{{max-width:780px;font-size:1.16rem;color:#dce8f1}} header .eyebrow{{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:#8edbd2}} h1{{font-size:clamp(2.35rem,6vw,4.8rem);line-height:.98;margin:.3rem 0 1.2rem;max-width:920px}} h2{{font-size:clamp(1.8rem,3vw,2.6rem);line-height:1.12;color:var(--navy);margin:0 0 1rem}} h3{{color:var(--navy);margin-top:1.8rem}}
nav{{position:sticky;top:0;z-index:5;background:#fffdf9ee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:10px max(18px,calc((100vw - 1120px)/2));overflow:auto;white-space:nowrap}} nav a{{margin-right:20px;font-size:.88rem;text-decoration:none;font-weight:700}}
main{{max-width:1120px;margin:auto;padding:42px 24px 80px}} section{{padding:42px 0;border-bottom:1px solid var(--line)}} .lead{{font-size:1.18rem;max-width:850px}} .grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}} .card{{grid-column:span 4;background:var(--card);padding:22px;border:1px solid var(--line);border-top:5px solid var(--teal);box-shadow:0 6px 18px #17212b0d}} .card.wide{{grid-column:span 6}} .card strong.metric{{display:block;font-size:2rem;line-height:1.1;color:var(--navy);font-variant-numeric:tabular-nums;margin:.35rem 0}} .card small{{color:var(--muted)}} .contract{{border-top-color:var(--orange)}} .number{{font-variant-numeric:tabular-nums;font-weight:750}} .pill{{display:inline-block;padding:3px 9px;border-radius:99px;background:var(--soft);color:#075a56;font-size:.78rem;font-weight:800}} .pill.warn{{background:var(--warn);color:#7a4b00}} .pill.fail{{background:#f6dede;color:var(--danger)}}
figure{{margin:24px 0;background:white;border:1px solid var(--line);padding:18px}} figcaption{{color:var(--muted);font-size:.9rem;margin-top:10px}} .chart{{width:100%;height:auto;display:block}} .chart text{{font:12px system-ui,sans-serif;fill:var(--muted)}} .chart .grid{{stroke:#e7e2d9;stroke-width:1}} .chart .axis{{stroke:#82909c;stroke-width:1.2}} .chart .series{{fill:none;stroke:var(--navy);stroke-width:2.1}} .chart .peak{{fill:var(--orange)}} .chart .valley{{fill:var(--teal)}} .chart .round{{font-weight:800;fill:var(--navy)}} .chart .bar{{fill:var(--teal)}} .chart .bar.none{{fill:#9aa7b1}} .chart .bar.trim{{fill:var(--orange)}} .chart .value{{font-weight:800;fill:var(--navy)}} .chart .dot{{fill:var(--orange);opacity:.72}}
table{{width:100%;border-collapse:collapse;background:white;font-size:.92rem}} th,td{{text-align:left;vertical-align:top;padding:11px 12px;border-bottom:1px solid var(--line)}} th{{background:var(--navy);color:white}} tbody tr:nth-child(even){{background:#f7faf9}} .callout{{border-left:5px solid var(--orange);background:var(--warn);padding:16px 20px;margin:20px 0}} .flow{{font-weight:800;color:var(--navy);background:var(--soft);padding:18px;text-align:center;letter-spacing:.01em}}
code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.9em}} footer{{background:#101d29;color:#cbd6df;padding:30px max(24px,calc((100vw - 1120px)/2));font-size:.86rem}} footer code{{color:white}} .source-links{{font-size:.88rem;color:var(--muted)}}
@media(max-width:760px){{.card,.card.wide{{grid-column:1/-1}} main{{padding-inline:16px}} table{{display:block;overflow:auto}} header{{padding-top:48px}}}}
@media print{{nav{{display:none}} body{{background:white}} section{{break-inside:avoid}} .card,figure{{box-shadow:none}} a{{color:inherit}}}}
</style>
</head>
<body>
<header>
  <div class="eyebrow">Tizen · glibc 2.40 · ptmalloc</div>
  <h1>只在“确有驻留”时 trim</h1>
  <p>把自动归还当作反信号，先用 M7 确认 allocator 空闲驻留，再在明确释放相位执行 <code>malloc_trim(0)</code>，并把回收、再激活 faults、业务 p99 和健康门作为同一份合同验收。</p>
</header>
<nav aria-label="报告章节"><a href="#summary">摘要</a><a href="#finding-one">发现一</a><a href="#finding-two">发现二</a><a href="#s4">S4 效果</a><a href="#gst">真实并发</a><a href="#native">真实平台进程</a><a href="#reproduce">复现</a><a href="#boundaries">边界</a></nav>
<main>
<section id="summary">
  <span class="pill">一页摘要</span><h2>方案、交付合同与头条结果</h2>
  <p class="lead">机会面不是“大进程”，而是“未自动下降 + M7 已确认驻留 + 代价过门”的释放相位。证据链先排除已由 glibc 自动归还的周期分量，再把 trim 限定到 retained-bin 表型。</p>
  <div class="grid">
    <div class="card contract"><strong>有力复现步骤</strong><small>L1 公开证据复算；L2 身份门、哈希、矩阵、拉回、恢复现场。</small></div>
    <div class="card contract"><strong>同板同镜像对照</strong><small>S4 锚点 + trim/none；gst 两臂各三重复。</small></div>
    <div class="card contract"><strong>结果说明价值</strong><small>收益、faults、业务 p99、健康门和边界同批呈现。</small></div>
    <div class="card contract"><strong>同条件复现同数据</strong><small>payload 确定性字节逐值一致；容差项落带；validity gates 全部通过。</small></div>
  </div>
  <p class="source-links">合同映射：<a href="demo_package_20260902.md#delivery-contracts">Demo 包 §0</a> · <a href="{guide}#l2-acceptance">复现指南验收带</a></p>
  <div class="grid">
    <div class="card"><small>瞬时释放共同锚点（frozen/GBS，n=8/profile）</small><strong class="metric">{anchors['mixed']:.2f}% / {anchors['medium-only']:.2f}%</strong><span>mixed ±{anchor_radius['mixed']:.6f} pp；medium-only ±{anchor_radius['medium-only']:.6f} pp；of pre-trim heap</span><br><a href="{evidence_s4_a_decision}">裁决 JSON</a> · <a href="{guide}#l1-a-anchor-replication">L1 复算</a></div>
    <div class="card"><small>门控 trim 回收 / 已释放</small><strong class="metric">{min(float(r['trim_reclaim_pct_of_released']) for r in b_cycles if r['trim_at']=='valley'):.2f}%–{max(float(r['trim_reclaim_pct_of_released']) for r in b_cycles if r['trim_at']=='valley'):.2f}%</strong><span>调用中位 mixed {s4_trim_median_by_profile['mixed']:.6f} / medium-only {s4_trim_median_by_profile['medium-only']:.6f} ms；majflt 0</span><br><a href="{evidence_s4_b}">证据 TSV</a> · <a href="{guide}#l1-s4">L1 复算</a></div>
    <div class="card"><small>gst 业务 p99 预登记判定（REPORT_ONLY）</small><strong class="metric">+{gst_comparison['delta_p99_ms']:.3f} ms &lt; {gst_comparison['none_p99_repeat_dispersion_ms']:.3f} ms</strong><span class="pill">未检出；margin {gst_p99_margin:.3f} ms（阈值 {gst_p99_threshold_pct:.1f}%）</span><br><a href="../data/raw/gst_trim_cost_20260901/comparison.json">证据 JSON</a> · <a href="{guide}#l1-gst-trim-cost">L1 复算</a></div>
  </div>
</section>

<section id="finding-one">
  <span class="pill">发现一</span><h2>ServiceA：自动归还是反信号</h2>
  <p>八轮 glibc-heap PD 峰谷中位为 <a class="number" href="{evidence_service}">{peak_valley_median:.0f} KiB（{peak_valley_median / 1024:.2f} MiB）</a>，但下降同时满足 total PD 实跌、全局 zram 总变化 <a class="number" href="../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv">{zram_total} B</a>、majflt <a class="number" href="../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json">{service_counter['majflt_first']}→{service_counter['majflt_last']}</a>，且 <a class="number" href="../data/raw/cyclic_fall_attribution_20260901/summary.json">{attribution['F2']['large_step_count']} 个大步中近等幅迁移为 {attribution['F2']['near_equal_within_50pct_count']}</a>。因此该周期分量已经离开 Private_Dirty，不是重复 trim 的收益。</p>
  <figure>{servicea_chart(service_rows, rounds)}<figcaption>图 1 · ServiceA 1 s 时序与八轮峰谷。<a href="../data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv">原始时序</a> · <a href="{evidence_service}">逐轮标注</a> · <a href="{guide}#l1-servicea">复算命令</a></figcaption></figure>
  <div class="flow">PD 实跌 → zram 无正增长 → majflt 恒零 → other-anon 无镜像迁移 → 自动归还反信号</div>
  <div class="callout">旧“下降沿 {attribution['F3']['published_fall_edge_median_s']:.6f} s”是尾窗最小值落点伪影。按 1 s 采样上界，释放在峰后 {attribution['F3']['valley_band_entry_delay_min_s']:.6f}–{attribution['F3']['valley_band_entry_delay_max_s']:.6f} s 内基本完成。<a href="../data/raw/cyclic_fall_attribution_20260901/summary.json">证据 JSON</a> · <a href="{guide}#l1-servicea">L1 复算</a></div>
</section>

<section id="finding-two">
  <span class="pill">发现二</span><h2>滞留表型才是作用面</h2>
  <h3>release-ratio 表（10 个目标，双标签按分量计）</h3>
  <div class="grid">{''.join(f'<div class="card"><small>release-ratio 标签 {key}</small><strong class="metric">{value}</strong><span>目标/分量</span></div>' for key, value in release_counts.items())}</div>
  <h3>plateau/cyclic 表（10 个目标，双标签按分量计）</h3>
  <div class="grid">{''.join(f'<div class="card"><small>plateau/cyclic 标签 {key}</small><strong class="metric">{value}</strong><span>目标/分量</span></div>' for key, value in plateau_counts.items())}</div>
  <p class="source-links">两组计数分别来自 <a href="../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv">release-ratio TSV</a> 与 <a href="../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv">plateau/cyclic TSV</a>，不跨表合并。ServiceD 在前表为 b-retention、后表为 N-subthreshold；这是采样窗口/阈值造成的跨表分类冲突，按 <a href="cyclic_fall_mechanism_attribution_v2_20260901.md#5-十目标表型普查">归因 v2</a> 原样披露。完整复算见 <a href="{guide}#l1-phenotypes">L1 表型复算</a>。</p>
  <table><thead><tr><th>候选</th><th>已登记 floor / 上界</th><th>门控含义</th><th>证据</th></tr></thead><tbody>
    <tr><td>enlightenment</td><td class="number">+{int(release_by_target['enlightenment']['retained_height_kb'])} KiB</td><td>a 周期分量排除；b floor 保留，并附自动归还能力告警</td><td><a href="../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv">TSV</a> · <a href="{guide}#l1-phenotypes">复算</a></td></tr>
    <tr><td>ServiceH[ServiceK]</td><td class="number">{int(plateau_by_target['ServiceH[ServiceK]']['max_rise_kb'])} KiB（{int(plateau_by_target['ServiceH[ServiceK]']['max_rise_kb'])/1024:.2f} MiB）上界；+{int(plateau_by_target['ServiceH[ServiceK]']['cyclic_end_minus_start_kb'])}/+{int(release_by_target['ServiceH']['retained_height_kb'])} KiB floor</td><td>PID/探针边界保留；需产品侧 M7</td><td><a href="../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv">TSV</a> · <a href="{guide}#l1-phenotypes">复算</a></td></tr>
    <tr><td>ServiceA</td><td class="number">+{int(plateau_by_target['ServiceA']['cyclic_final_round_floor_delta_kb'])} KiB 谷底残渣</td><td>周期分量排除；残渣 live/bin 未判</td><td><a href="../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv">TSV</a> · <a href="{guide}#l1-phenotypes">复算</a></td></tr>
    <tr><td>批量释放相位类</td><td class="number">{batch_pct:.1f}% / {batch_mib:.2f} MiB × {len(batch_scale)} 进程</td><td>来自 &lt;TEST_IMAGE_B&gt;/glibc-2.40-2.8 的相容性对照，非冻结矩阵</td><td><a href="../data/raw/demo_reproduction_20260901/batch_release_phase.tsv">TSV</a> · <a href="{guide}#l1-batch-release">复算</a></td></tr>
  </tbody></table>
</section>

<section id="s4">
  <span class="pill">效果</span><h2>S4：M7 阳性后，valley trim 回收驻留页</h2>
  <div class="flow">反信号排除 → M7 rest/unsorted 驻留确认 → valley trim → faults / 时延 / 健康门</div>
  <div class="grid">
    <div class="card wide"><h3>瞬时释放共同锚点（n=8/profile）</h3>{bar_chart([('mixed', anchors['mixed'], 'trim'), ('medium-only', anchors['medium-only'], 'trim')], title='S4 A 组 frozen/GBS H-V 共同锚点', unit='reclaim / pre-trim heap (%)', ceiling=60)}<p>mixed {anchors['mixed']:.6f}% ±{anchor_radius['mixed']:.6f} pp；medium-only {anchors['medium-only']:.6f}% ±{anchor_radius['medium-only']:.6f} pp。<a href="{evidence_s4_a}">12 格证据</a> · <a href="{evidence_s4_a_decision}">H-V 裁决</a> · <a href="{guide}#l1-a-anchor-replication">复算</a></p></div>
    <div class="card wide"><h3>B 组三重复中位</h3>{bar_chart([('mixed trim', b_ratio['mixed'], 'trim'), ('mixed none', 0.0, 'none'), ('medium trim', b_ratio['medium-only'], 'trim'), ('medium none', 0.0, 'none')], title='S4 B 组 trim/none 回收已释放 payload', unit='reclaim / released (%)', ceiling=100)}<p><a href="../data/raw/s4_retention_20260901/b_cells.tsv">格级证据</a> · <a href="{guide}#l2-acceptance">中位验收规则</a></p></div>
  </div>
  <table><thead><tr><th>profile</th><th>回收 / 已释放（三重复中位）</th><th>trim 耗时中位</th><th>下一周期额外 minflt</th><th>majflt</th></tr></thead><tbody>
    <tr><td>mixed</td><td class="number">{b_ratio['mixed']:.2f}%</td><td class="number">{s4_trim_median_by_profile['mixed']:.6f} ms</td><td class="number">+{next_fault['mixed']}</td><td class="number">0</td></tr>
    <tr><td>medium-only</td><td class="number">{b_ratio['medium-only']:.2f}%</td><td class="number">{s4_trim_median_by_profile['medium-only']:.6f} ms</td><td class="number">+{next_fault['medium-only']}</td><td class="number">0</td></tr>
  </tbody></table>
  <p class="source-links"><a href="../data/raw/s4_retention_20260901/b_cells.tsv">代价证据 TSV</a> · <a href="../data/raw/s4_retention_20260901/health.json">健康证据 JSON</a> · <a href="{guide}#l1-s4">L1 复算</a>。zram 三项 Δ={s4_health['zram_original_data_size_delta']}/{s4_health['zram_compressed_data_size_delta']}/{s4_health['zram_mem_used_total_delta']}，OOM/LMK={len(s4_health['oom_lmk_matches'])}。</p>
  <p class="source-links">时延带分开解释：B 组释放点 trim 单次 &lt;{acceptance['tolerance_bands']['release_point_trim_single_call_ms']['max_exclusive_ms']:g} ms；A2 锚点实测最大 {anchor_trim_max:.6f} ms，以 &lt;{acceptance['tolerance_bands']['s4_a_anchor_trim_single_call_ms']['max_exclusive_ms']:g} ms 验收，且不作为钩子代价。<a href="{evidence_s4_a}">A2 证据</a> · <a href="../tools/reproduce/acceptance_bands.json">机器规则</a></p>
</section>

<section id="gst">
  <span class="pill">真实并发</span><h2>gst：方向只报告；本批按预登记业务 p99 门未检出</h2>
  <p>trim 臂 repeat-median p99 相对 none 增加 <a class="number" href="../data/raw/gst_trim_cost_20260901/comparison.json">{gst_comparison['delta_p99_ms']:.6f} ms</a>，低于 none 重复离散带 <a class="number" href="../data/raw/gst_trim_cost_20260901/comparison.json">{gst_comparison['none_p99_repeat_dispersion_ms']:.6f} ms</a>，margin 为 <strong>{gst_p99_margin:.3f} ms</strong>，达到门槛的 <strong>{gst_p99_threshold_pct:.1f}%</strong>。同一规则用于 p50 时判可见：<strong>+{gst_p50_delta:.3f} ms</strong> 对 <strong>{gst_p50_dispersion:.3f} ms</strong>。trim 臂另增加约 <strong>+{gst_minflt_per_cycle} minflt/循环</strong>。p99 方向是 <code>REPORT_ONLY</code>，只校验 nearest-rank 与离散带计算，不能写“零代价”。</p>
  <div class="callout">如果你的板上 p99 判为“可见”，保留原始三重复与规则复算，标记 <code>REPORT_ONLY: visible</code>，量化 delta、none 离散带和 margin，并上报为批次差异；不要把它改成 workflow 硬失败，也不要据此修改冻结参数。</div>
  <figure>{bar_chart(p99_display, title='gst 两臂三重复业务 p99（为显示差异减去共同基线）', unit=f'p99 − {p99_origin:.6f} ms')}<figcaption>图 4 · 柱高减去共同显示基线，不改变臂间差；原始毫秒值见 <a href="../data/raw/gst_trim_cost_20260901/repetitions.tsv">repetitions.tsv</a>，判定见 <a href="../data/raw/gst_trim_cost_20260901/comparison.json">comparison.json</a>，复算见 <a href="{guide}#l1-gst-trim-cost">L1 gst</a>。</figcaption></figure>
  <figure>{dot_chart(trim_times)}<figcaption>图 5 · 全部 {len(trim_times)} 次 release-point trim。p50/p95/p99/max = <span class="number">{gst_dist[0]:.6f}/{gst_dist[1]:.6f}/{gst_dist[2]:.6f}/{gst_dist[3]:.6f} ms</span>。<a href="{evidence_gst}">证据 TSV</a> · <a href="{guide}#l1-gst-trim-cost">复算</a></figcaption></figure>
  <table><thead><tr><th>trim 重复</th><th>首次 release 回收率</th><th>首次回收</th></tr></thead><tbody>{''.join(f'<tr><td>rep{row["rep"]}</td><td class="number">{float(row["reclaim_pct_of_pre"]):.6f}%</td><td class="number">{int(row["glibc_pd_reclaimed_kb"])/1024:.6f} MiB</td></tr>' for row in first_releases)}</tbody></table>
  <p class="source-links"><a href="{evidence_gst}">首次回收证据 TSV</a> · <a href="{guide}#l1-gst-trim-cost">公开 replay 与预期输出</a></p>
</section>

<section id="native">
  <span class="pill">真实平台进程实证</span><h2>Tizen 自带进程与工具的交叉见证</h2>
  <p>在 Tizen 守护进程 <code>enlightenment</code> 上，glibc <code>malloc_info</code> 每格均显示 8 个 arena、约 5.84 MiB rest；随后三次 <code>malloc_trim(0)</code> 的项目主堆读数分别下降 <strong>272 / 4 / 4 KiB</strong>，Tizen 自带 <code>memps</code> 对同一 <code>[heap]</code> 逐格给出完全相同的前后值。PID 与启动时刻未变，majflt 增量、zram 三项增量、新增 OOM/LMK 和 stability 告警均为 0。</p>
  <table><thead><tr><th>格</th><th>M7 rest (B)</th><th>项目 heap PD (KiB)</th><th>memps [heap] (KiB)</th><th>回收</th><th>含 ptrace 的注入时延</th></tr></thead><tbody>
    {''.join(f'<tr><td>{row["cell"]}</td><td class="number">{row["m7_rest_bytes"]}</td><td>{row["project_pre_kb"]} → {row["project_post_kb"]}</td><td>{row["memps_pre_heap_kb"]} → {row["memps_post_heap_kb"]}</td><td class="number">{row["project_reclaimed_kb"]} KiB</td><td>{row["injection_ms"]:.6f} ms</td></tr>' for row in native["cells"] if row["group"] == "T2")}
  </tbody></table>
  <div class="callout"><strong>完成边界：</strong>Tizen <code>gst-launch-1.0</code> 冻结管线在 60.100233983 s EOS，只完成 1/5（该格回收 12 KiB，buffer 903→941）；Gallery 在首次 terminate 前自行退出，释放相位格完成 0/1。T2 的两个前置采样间隔为 119.806876910/119.856460299 s，严格低于预登记 120 s，故三个完整观测不标成完全合规重复。含 ptrace 的 1.15–1.77 s 不是钩子代价。</div>
  <p class="source-links"><a href="tizen_native_evidence_20260904.md">完整报告</a> · <a href="../data/raw/tizen_native_evidence_20260904/cells_derived.tsv">格级证据</a> · <a href="../data/raw/tizen_native_evidence_20260904/summary.json">完成度与偏差</a> · <a href="{guide}#l2-tizen-native-evidence">L2 复现</a></p>
</section>

<section id="reproduce">
  <span class="pill">复现入口</span><h2>三条路，同一事实源</h2>
  <div class="grid">
    <div class="card"><strong>① 离线阅读</strong><small>本 HTML 是单文件派生产物；所有图表由公开证据生成。</small></div>
    <div class="card"><strong>② Host verify · 分钟级</strong><small><code>bash tools/reproduce/reproduce.sh</code> 执行全部 L1 与 cmp。</small></div>
    <div class="card"><strong>③ Board · 小时级</strong><small><code>reproduce.sh board --artifact-source gbs --ip &lt;addr&gt;</code> 编排既有 S4/gst harness；GBS 已通过 A2/H-V 重基线。</small></div>
  </div>
  <p><a href="../tools/reproduce/README.md">Workflow 上手</a> · <a href="{guide}#workflow-fast-path">快速通道</a> · <a href="{guide}#l2-run">手工 L2</a>。确定性项、validity gates 和容差带都来自 <a href="../tools/reproduce/acceptance_bands.json">acceptance_bands.json</a>。“同样的数据”指 payload 确定性字节逐值一致、容差项落带且 validity gates 通过。</p>
</section>

<section id="boundaries">
  <span class="pill warn">边界</span><h2>这份证据没有承诺什么</h2>
  <ul>
    <li>合成代理仍缺产品候选的 M7 live/bin 分解、产品业务时延，以及真实并发分配线程的直接全-arena 锁停顿。</li>
    <li>gst trim 在 PLAYING→NULL release 后触发；它测到下一循环业务墙钟，但没有把 trim 放进并发分配热区。</li>
    <li><strong>“p99 未检出”不等于“零代价”</strong>：结论严格受三重复、{gst_comparison['primary_samples_per_repeat']} 个主样本与预登记离散门约束。<a href="../data/raw/gst_trim_cost_20260901/comparison.json">判定证据</a></li>
    <li><strong>同 seed 不钉 arena 指派</strong>：单重复实测出现 <a href="../data/raw/demo_rehearsal_20260902/s4_medium_only_rep2_reclaim.tsv">68.169197%</a>（约 1 MiB 页台阶）；回收字节值不属于确定性项，S4 B 分别锚定发布值 {b_ratio['mixed']:.6f}% / {b_ratio['medium-only']:.6f}% 并按每档三重复中位 ±{acceptance['tolerance_bands']['s4_b_reclaim_pct_repeat_median']['plus_minus_pp']:g} pp 验收。n=3 的中位至多容忍一个离群。<a href="../tools/reproduce/acceptance_bands.json">机器规则</a></li>
    <li><strong>known-alert waiver 不是无害性证明</strong>：S4 A 最多 {acceptance['stability_monitor']['expected_alerts'][0]['max_count_total']} 个匹配 <code>alloc_bench cpu.relative</code> 的 livedump；触发理由与窗口可复现，但未做根因证明。观测到且完成记录、归档、精确清理和复核才记 <code>EXPECTED</code>，未观测只记 <code>REGISTERED/NOT-EVALUATED</code>；其他可归因告警仍失败。<a href="../tools/reproduce/health_gate_template.md">健康门模板</a></li>
    <li>Tizen 原生交叉见证不是完整成功矩阵：T1 为 1/5、UI 释放相位格为 0/1，且 T2 间隔约短 0.2 s；只能引用完成格的测量值，不能外推产品收益。</li>
  </ul>
  <p>产品侧启用仍须通过反信号排除、M7 驻留确认和代价预算三道硬门：<a href="product_landing_recommendation_20260901.md#1-启用门清单">落点建议</a>。</p>
</section>
</main>
<footer>构建来源 commit：<code>{esc(source_commit)}</code> · 本文件为派生产物，可由 <code>python3 tools/report/build_demo_report.py</code> 重建。全部图表使用仓库内 TSV/JSON 生成，无 CDN、无外部图片。</footer>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--record-source-commit", action="store_true", help="record git HEAD before rebuilding the checked-in derivative")
    parser.add_argument("--marker-output", type=Path, help="override the source marker path (mainly for tests)")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = args.output or repo / "docs/demo_report.html"
    marker = args.marker_output or repo / "tools/report/source_commit.txt"
    if args.record_source_commit:
        if args.source_commit:
            parser.error("--record-source-commit and --source-commit are mutually exclusive")
        source_commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(source_commit + "\n", encoding="utf-8")
    else:
        source_commit = args.source_commit or (marker.read_text(encoding="utf-8").strip() if marker.is_file() else "WORKTREE")
    document = build(repo, source_commit)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8", newline="\n")
    print(f"built {output} ({len(document.encode('utf-8'))} bytes) source={source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
