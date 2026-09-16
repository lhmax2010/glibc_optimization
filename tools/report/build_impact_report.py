#!/usr/bin/env python3
"""Build the HQ impact report from frozen public evidence, without a board.

Positive controls are intentional correctness assertions, not measurements.
No clock, network, packages, external graphics, or release-entrypoint changes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import statistics as stats
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path


SYSTEM = 'system_level_before_after_20260908/accepted_matrix/'
S4 = 's4_retention_20260901/'
GST = 'gst_trim_cost_20260901/'
NATIVE = 'tizen_native_evidence_20260904/'
B2 = 'tizen_native_evidence_b2_20260904/'
GUIDE = 'demo_reproduction_guide_20260901.md'
LABELS = {'G1': 'mixed', 'G2': 'medium-only', 'G3': 'gst 解码循环', 'G4': 'enlightenment'}


def expect(actual, expected, label):
    if actual != expected:
        raise ValueError(f'numeric/source control failed: {label}: {actual!r} != {expected!r}')


def fixed(value, places=6):
    return f'{Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN):.{places}f}'


def nr(values, q):
    ordered = sorted(values)
    return ordered[max(1, math.ceil(len(ordered) * q)) - 1]


def load_evidence(repo):
    refs = json.loads((repo / 'tools/report/impact_sources.json').read_text(encoding='utf-8'))
    data = {}
    for relative, digest in refs['sha256'].items():
        path = repo / 'data/raw' / relative
        if not path.resolve().is_relative_to((repo / 'data/raw').resolve()):
            raise ValueError(f'invalid evidence path: {relative}')
        blob = path.read_bytes()
        expect(hashlib.sha256(blob).hexdigest(), digest, relative + ' byte SHA-256')
        text = blob.decode('utf-8')
        data[relative] = json.loads(text) if path.suffix == '.json' else list(csv.DictReader(io.StringIO(text), delimiter='\t'))
    return refs, data


def controls(data):
    """Recheck every displayed aggregate against published values and row data."""
    summary = {(r['group'], r['arm']): r for r in data[SYSTEM + 'summary.tsv']}
    rows = data[SYSTEM + 'cycles.tsv']
    expect(len(rows), 333, 'system cycles')
    for r in rows:
        expect(int(r['rss_drop_kib']), int(r['rss_pre_kib']) - int(r['rss_post_kib']), 'RSS row arithmetic')
    result = {'summary': summary, 'system': {}, 's4': {}}
    published = {
        'G1': ('13.015625', '7.718750', '5.296875', '40.696279', '41.807953', '-0.167969', '9.394531', '1.458574', '4488'),
        'G2': ('13.152344', '7.191406', '5.960938', '45.322245', '45.177290', '5.304688', '8.136719', '1.478167', '5116'),
        'G3': ('8.671875', '6.859375', '1.820312', '21.009919', '16.038164', '1.855469', '2.816406', '0.843612', '1320'),
    }
    for group, expected in published.items():
        trim = [r for r in rows if r['group'] == group and r['arm'] == 'trim']
        first = [r for r in trim if r['cycle'] == '1']
        none = [r for r in rows if r['group'] == group and r['arm'] == 'none']
        expect(len(first), 3, group + ' repeats')
        expect(len(trim), 153 if group == 'G3' else 6, group + ' full-cycle samples')
        expect(all(int(r['rss_drop_kib']) == 0 for r in none), True, group + ' none RSS')
        ratios = [100 * int(r['rss_drop_kib']) / int(r['rss_pre_kib']) for r in trim]
        nets = [int(r['memavailable_net_kib']) / 1024 for r in first]
        derived = (
            fixed(stats.median(int(r['rss_pre_kib']) / 1024 for r in first)),
            fixed(stats.median(int(r['rss_post_kib']) / 1024 for r in first)),
            fixed(stats.median(int(r['rss_drop_kib']) / 1024 for r in first)),
            fixed(stats.median(100 * int(r['rss_drop_kib']) / int(r['rss_pre_kib']) for r in first)),
            fixed(stats.median(ratios)), fixed(stats.median(nets)), fixed(max(nets) - min(nets)),
            summary[group, 'trim']['trim_elapsed_ms_median'],
            str(stats.median(int(r['heap_drop_kib']) for r in first)),
        )
        expect(derived, expected, group + ' published headline / all-cycle scope')
        for field, value in zip(('rss_drop_mib_median', 'rss_drop_pct_median'), derived[2:4]):
            expect(summary[group, 'trim'][field], value, group + ' summary ' + field)
        expect(abs(stats.median(nets)) <= max(nets) - min(nets), True, group + ' NOT-DETECTED')
        result['system'][group] = dict(zip(('pre', 'post', 'drop', 'pct', 'full_pct', 'net', 'spread', 'cost', 'heap_kib'), derived))
        result['system'][group]['full_range'] = (fixed(min(ratios)), fixed(max(ratios)))
    expect(result['system']['G3']['full_range'], ('13.282648', '21.043165'), 'gst full RSS range')
    expect(data[SYSTEM + 'gst_comparison.json']['primary_cycles'], '2-51', 'system gst cost window')
    expect(all(r['capture_majflt'] == '0' for r in rows), True, 'system capture majflt')
    expect(all(r['next_cycle_majflt'] in ('0', 'NA') for r in rows), True, 'available next-cycle majflt')
    g4 = [r for r in rows if r['group'] == 'G4']
    expect([int(r['heap_drop_kib']) for r in g4], [88, 0, 4], 'resident heap PD')
    expect(summary['G4', 'trim']['trim_elapsed_ms_median'], '1899.209517', 'gdb/ptrace cost')
    expect(summary['G4', 'trim']['rss_drop_pct_median'], '0.033659', 'resident RSS percentage')
    g4_rss = [int(r['rss_drop_kib']) / 1024 for r in g4]
    expect((fixed(stats.median(g4_rss)), fixed(max(g4_rss)-min(g4_rss))), ('0.003906', '0.089844'), 'resident RSS NOT-DETECTED')
    result['g4'] = g4
    b = data[S4 + 'b_cycles.tsv']
    for profile, median, extra, amounts in (
        ('mixed', '1.233269', 1351, ['80.175875', '83.146653']),
        ('medium-only', '1.218361', 1465, ['83.439179', '85.453954']),
    ):
        trim = [r for r in b if r['profile'] == profile and r['trim_at'] == 'valley']
        times = [Decimal(r['trim_elapsed_ms']) for r in trim]
        expect(len(times), 6, profile + ' release calls')
        expect(str(stats.median(times).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)), median, profile + ' trim median')
        expect(sorted({r['trim_reclaim_pct_of_released'] for r in trim}), amounts, profile + ' released-payload recovery')
        baseline = next(r for r in b if r['profile'] == profile and r['trim_at'] == 'none' and r['cycle'] == '1')
        faults = stats.median(int(r['next_cycle_minflt']) for r in trim if r['cycle'] == '1') - int(baseline['next_cycle_minflt'])
        expect(faults, extra, profile + ' minflt delta')
        result['s4'][profile] = {'times': times, 'median': median, 'extra': extra}
    expect(all(r['next_cycle_majflt'] == '0' and r['exit_code'] == '0' for r in b), True, 'S4 faults/exit')
    a = data[S4 + 'a_cells.tsv']
    expect([(r['profile'], r['trim_elapsed_ms']) for r in a], [('mixed', '13.331907'), ('medium-only', '12.72324')], 'A anchor costs')
    result['a'] = a
    gst = data[GST + 'cycles.tsv']
    trim_times = [float(r['trim_elapsed_ms']) for r in gst if r['arm'] == 'trim-at-loop-release']
    expect(len(trim_times), 153, 'gst calls')
    quantiles = [nr(trim_times, q) for q in (.5, .95, .99)] + [max(trim_times)]
    expect([fixed(v) for v in quantiles], ['0.671556', '0.818315', '0.842185', '0.856944'], 'gst elapsed distribution')
    result['gst_times'] = trim_times
    result['gst_quantiles'] = quantiles
    reps = data[GST + 'repetitions.tsv']
    calculated = {}
    for arm in ('none', 'trim-at-loop-release'):
        calculated[arm] = []
        for rep in ('1', '2', '3'):
            selected = [r for r in gst if r['arm'] == arm and r['rep'] == rep and r['primary_business_sample'] == '1']
            expect(len(selected), 50, 'gst primary samples')
            expect(all(r['cycle_majflt'] == '0' for r in selected), True, 'gst primary majflt')
            times = [float(r['business_elapsed_ms']) for r in selected]
            row = next(r for r in reps if r['arm'] == arm and r['rep'] == rep)
            for key, q in (('business_p50_ms', .5), ('business_p99_ms', .99)):
                expect(float(row[key]), nr(times, q), 'gst nearest-rank ' + key)
            calculated[arm].append((nr(times, .5), nr(times, .99), sum(int(r['cycle_minflt']) for r in selected)))
    p99_delta = stats.median(r[1] for r in calculated['trim-at-loop-release']) - stats.median(r[1] for r in calculated['none'])
    dispersion = max(r[1] for r in calculated['none']) - min(r[1] for r in calculated['none'])
    p50_delta = stats.median(r[0] for r in calculated['trim-at-loop-release']) - stats.median(r[0] for r in calculated['none'])
    p50_range = max(r[0] for r in calculated['none']) - min(r[0] for r in calculated['none'])
    expect([fixed(v) for v in (p99_delta, dispersion, dispersion-p99_delta, p50_delta, p50_range)],
           ['6.228611', '6.784167', '0.555556', '1.870462', '0.173927'], 'business judgement')
    expect(fixed(100*p99_delta/dispersion, 1), '91.8', 'p99 threshold ratio')
    comparison = data[GST + 'comparison.json']
    expect(comparison['business_cost_visible'], p99_delta > dispersion, 'p99 direction')
    expect(p50_delta > p50_range, True, 'p50 sensitivity disclosure')
    extra = (stats.median(r[2] for r in calculated['trim-at-loop-release']) - stats.median(r[2] for r in calculated['none'])) / 50
    expect(round(extra), 359, 'gst extra minor faults per cycle')
    expect([(r['arm'], r['rep'], r['cycle'], r['cycle_majflt']) for r in gst if r['cycle_majflt'] != '0'], [('none', '1', '1', '4')], 'cold-start exception')
    expect([r['majflt_delta'] for r in data[GST + 'external_summary.tsv']], ['4', '0', '0', '0', '0', '0'], 'external cold-start exception')
    expect(all(r['exit_code'] == '0' for r in gst), True, 'gst exit')
    for prefix in (S4, GST):
        health = data[prefix + 'health.json']
        expect(health['oom_lmk_matches'], [], prefix + ' OOM/LMK')
        for field in ('original_data_size', 'compressed_data_size', 'mem_used_total'):
            expect(health['zram_' + field + '_delta'], 0, prefix + ' zram')
    native = data[NATIVE + 'summary.json']
    e1 = next(r for r in native['cells'] if r['cell'] == 'T2_E1')
    expect((e1['project_reclaimed_kb'], e1['m7_rest_bytes']), (272, 6118675), 'enlightenment E1')
    expect(data[NATIVE + 'health.json']['enlightenment']['stable_across_completed_cells'], True, 'resident identity continuity')
    e4 = data[B2 + 'summary.json']['e4_prime']
    expect((e4['reclaimed_kb'], e4['memps_exact_match']), (36, True), 'enlightenment E4')
    expect(data[B2 + 'summary.json']['health']['stability_monitor_new_livedumps'], 0, 'B2 health')
    paired = [r for r in data['trimmable_estimator_20260905/validation.tsv'] if r['validation_status'] == 'paired']
    expect((len(paired), sum(r['measured_within_bounds'] == 'false' for r in paired)), (15, 15), 'estimator unusable')
    proof = data[SYSTEM + 'composition.json']
    expect(proof['verdict'], 'PASS_ACCEPTED_MATRIX_WITH_DELAYED_CLEANUP', 'accepted matrix')
    expect(len(proof['completed_cells']), 21, 'completed cells')
    for phase in ('START', 'END'):
        expect(proof['cleanup']['health'][phase]['oom_lmk'], 0, 'cleanup OOM/LMK')
        expect(proof['cleanup']['health'][phase]['stability_count'], 0, 'cleanup alerts')
    expect(data['demo_v14_delivery_20260915/verification.json']['demo_v14_peeled_commit'],
           '7289a47b9d24791944cd3b02c00f24b8cb76aa3b', 'delivery package')
    return result


def cite(paths, anchor):
    if isinstance(paths, str):
        paths = [paths]
    links = [f'<a href="../data/raw/{html.escape(p, quote=True)}">{html.escape(p.split("/")[-1])}</a>' for p in paths]
    links.append(f'<a href="{GUIDE}#{anchor}">L1 复算</a>')
    return '<span class="sources">' + ' · '.join(links) + '</span>'


def svg_open(title, height):
    return f'<svg viewBox="0 0 980 {height}" role="img" aria-label="{html.escape(title, quote=True)}"><title>{html.escape(title)}</title>'


def rss_chart(values):
    parts = [svg_open('进程 RSS：调用前后；均为首周期三重复中位，MiB', 390)]
    for i, group in enumerate(('G1', 'G2', 'G3')):
        r = values[group]; y = 50 + i*112
        parts.append(f'<text x="12" y="{y}">{LABELS[group]}</text>')
        for j, (key, label, color) in enumerate((('pre', '前', 'before'), ('post', '后', 'after'))):
            width = float(r[key]) * 38
            parts.append(f'<rect x="172" y="{y-21+j*30}" width="{width:.3f}" height="22" class="{color}"/>')
            parts.append(f'<text x="{184+width:.3f}" y="{y-5+j*30}">{label} {float(r[key]):.2f} MiB</text>')
        parts.append(f'<text x="172" y="{y+63}" class="accent">下降 {float(r["drop"]):.2f} MiB · {float(r["pct"]):.2f}%</text>')
    parts.append('<text x="172" y="385">共同零基线；下表保留精确值，G3 全周期口径另列。</text></svg>')
    return ''.join(parts)


def net_chart(values):
    parts = [svg_open('系统 MemAvailable 净效应与重复极差，均未检出', 266)]
    for i, group in enumerate(('G1', 'G2', 'G3')):
        r = values[group]; y = 51 + i*72
        parts.append(f'<text x="12" y="{y}">{LABELS[group]}</text>')
        # Two magnitude bars, NOT a confidence interval or ±range error bar.
        for j, (value, color) in enumerate(((abs(float(r['net'])), 'after'), (float(r['spread']), 'before'))):
            parts.append(f'<rect x="172" y="{y-18+j*22}" width="{value*34:.3f}" height="15" class="{color}"/>')
        parts.append(f'<text x="530" y="{y-4}">中位 {float(r["net"]):+.6f} MiB</text>')
        parts.append(f'<text x="530" y="{y+19}">极差 {r["spread"]} MiB · NOT-DETECTED</text>')
    parts.append('<text x="172" y="260">绿色：中位绝对值；灰色：重复极差。原符号在标注保留，不是置信区间。</text></svg>')
    return ''.join(parts)


def costs_chart(metrics):
    parts = [svg_open('释放点 trim 调用耗时分布；A 锚点不混池', 290)]
    for i, (label, times, median) in enumerate((
        ('S4 mixed', metrics['s4']['mixed']['times'], '1.233269'),
        ('S4 medium-only', metrics['s4']['medium-only']['times'], '1.218361'),
        ('gst / NULL 后', metrics['gst_times'], '0.671556'),
    )):
        y = 52+i*72
        parts.append(f'<text x="12" y="{y}">{label}</text>')
        parts.append(f'<line x1="190" x2="750" y1="{y}" y2="{y}" class="axis"/>')
        for j, elapsed in enumerate(sorted(times)):
            parts.append(f'<circle cx="{190+float(elapsed)*260:.3f}" cy="{y+(j%5-2)*4}" r="3" class="point"/>')
        parts.append(f'<text x="755" y="{y+5}">中位 {median} ms</text>')
    for tick in (0, .5, 1, 1.5, 2):
        parts.append(f'<text x="{190+tick*260:.0f}" y="242" text-anchor="middle">{tick:g}</text>')
    parts.append('<text x="190" y="275">横轴：耗时（ms）；共同零起点，每个点为一次调用，纵向仅作防重叠。</text></svg>')
    return ''.join(parts)


def applicability_chart(metrics):
    items = [(LABELS[g] + ' / 首周期中位', int(metrics['system'][g]['heap_kib'])) for g in ('G1', 'G2', 'G3')]
    items += [('enlightenment / E1', 272), ('enlightenment / E4′', 36), ('enlightenment / G4 r1', 88), ('enlightenment / G4 r2', 0), ('enlightenment / G4 r3', 4)]
    parts = [svg_open('同为 glibc 堆 PD 的回收量对比，KiB；不是 RSS 百分比', 402)]
    for i, (label, value) in enumerate(items):
        y = 35+i*44
        parts.append(f'<text x="12" y="{y+4}">{label}</text>')
        parts.append(f'<rect x="330" y="{y-15}" width="{value*.094:.3f}" height="23" class="after"/>')
        parts.append(f'<text x="{342+value*.094:.3f}" y="{y+3}">{value} KiB</text>')
    parts.append('<text x="330" y="393">共同零基线、同一 PD 单位；各轮状态不同，只比较实测量级。</text></svg>')
    return ''.join(parts)


STYLE = '''
:root{color-scheme:light;--ink:#152c40;--muted:#4d6070;--green:#087f76;--line:#dbe5e8}
*{box-sizing:border-box}body{margin:0;background:#edf2f3;color:var(--ink);font:16px/1.75 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}
main{max-width:1120px;margin:auto;background:white;padding:42px 54px}a{color:#08616e;text-underline-offset:3px;overflow-wrap:anywhere}
h1{font-size:38px;line-height:1.25;margin:12px 0 20px}h2{font-size:27px;line-height:1.35}h3{font-size:19px}section{border-top:1px solid var(--line);padding:26px 0}header{padding-bottom:25px}
.eyebrow{font-size:13px;letter-spacing:.15em;color:var(--green)}.lead{font-size:21px}.muted,small,figcaption{color:var(--muted)}.scope{background:#f1f6f6;border-left:4px solid var(--green);padding:14px 18px}.caution{background:#fff8eb;border-left:4px solid #ac7425;padding:14px 18px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{border:1px solid var(--line);border-radius:8px;padding:16px}.big{display:block;font-size:29px;color:var(--green);font-weight:700;line-height:1.4}.sources{font-size:12px;display:block;line-height:1.7;margin-top:6px}
nav{display:flex;flex-wrap:wrap;gap:12px 22px;margin:20px 0}figure{margin:22px 0;background:#f8fafb;padding:15px;border:1px solid var(--line);border-radius:8px}svg{width:100%;height:auto;display:block}svg text{font:15px system-ui,"Noto Sans CJK SC",sans-serif;fill:var(--ink)}.before{fill:#b6c4cc}.after,.point{fill:var(--green)}.point{opacity:.65}.axis{stroke:#c7d4da;stroke-width:1}.accent{font-weight:700;fill:var(--green)}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px;margin:18px 0}th,td{padding:11px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#eef4f5}td small{display:block}pre{background:#152c40;color:#edf7f7;padding:18px;overflow:auto;font-size:13px;line-height:1.65}code{font-family:ui-monospace,monospace}li{margin:10px 0}footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:20px;overflow-wrap:anywhere}
@media(max-width:720px){main{padding:24px 18px}h1{font-size:29px}.cards{grid-template-columns:1fr}svg{min-width:710px}figure{overflow:auto}.lead{font-size:18px}}
@media print{body{background:white}main{max-width:none;padding:10px}section{break-inside:auto}figure,.card,tr{break-inside:avoid}a{color:inherit}pre{white-space:pre-wrap;overflow-wrap:anywhere}nav{display:none}}
'''


def build(repo):
    refs, data = load_evidence(repo)
    m = controls(data)
    syscite = cite([SYSTEM+'summary.tsv', SYSTEM+'cycles.tsv'], 'l1-system-before-after')
    s4cite = cite(S4+'b_cycles.tsv', 'l1-s4')
    gstcite = cite([GST+'comparison.json', GST+'cycles.tsv', GST+'repetitions.tsv'], 'l1-gst-trim-cost')
    nativecite = cite([NATIVE+'summary.json', B2+'summary.json'], 'l1-impact-report')
    rows = []
    for group, r in m['system'].items():
        scope = ('<small>G3 为 51 周期负载，此处为 cycle=1；全周期降幅中位 16.038164%（13.28–21.04%；精确范围 13.282648–21.043165%）。</small>' if group == 'G3' else f'<small>全周期降幅中位 {r["full_pct"]}%。</small>')
        rows.append(f'<tr><td>{LABELS[group]}</td><td>{r["pre"]} → {r["post"]}</td><td>{r["drop"]} MiB / {r["pct"]}%{scope}</td><td>{syscite}</td></tr>')
    cost_rows = ''.join(f'<tr><td>S4 B / {p}</td><td>{r["median"]} ms</td><td>+{r["extra"]} minflt；下一周期 majflt=0</td><td>{s4cite}</td></tr>' for p, r in m['s4'].items())
    a_rows = ''.join(f'<tr><td>A 锚点 / {r["profile"]}</td><td>{fixed(r["trim_elapsed_ms"])} ms</td><td>单次大区域机制锚点，不是释放点钩子代价；每档单次观测。</td><td>{cite(S4+"a_cells.tsv", "l1-impact-report")}</td></tr>' for r in m['a'])
    inputs = ''.join(f'<li><a href="../data/raw/{p}">{p}</a> <small>SHA-256 {h}</small></li>' for p,h in refs['sha256'].items())
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="现有 glibc 运行时门控 trim：进程内存回收、已量化代价、稳定性与产品启用边界。">
<title>glibc 门控 trim｜内存优化影响报告</title><style>{STYLE}</style></head><body><main>
<header><div class="eyebrow">TIZEN · GLIBC · 运行时内存回收</div>
<h1>让已释放的内存，真正回到系统</h1>
<p class="lead">本方案不替换 libc、不改本次对照实验的二进制；在现有 glibc 上按释放相位调用 <code>malloc_trim(0)</code>，让可归还的空闲页退出进程驻留内存。</p>
<p><strong>内存有明确收益；按固定 p99 判据未检出性能劣化，已测窗口未发现 OOM/LMK 或目标重启。</strong>
这是带范围的“未检出副作用”，不是所有性能指标零影响或长期稳定性的证明；本报告不宣称性能提升。</p>
<p class="muted">只组织既有公开证据，没有新测量。收益指进程内存回收，不等于整机或产品收益。</p>
<nav aria-label="报告导航"><a href="#summary">摘要</a><a href="#memory">内存收益</a><a href="#performance">性能与稳定性</a><a href="#applicability">适用面</a><a href="#boundaries">边界</a><a href="#reproduction">复现</a></nav></header>

<section id="summary"><h2>一页摘要</h2>
<div class="cards"><div class="card">进程 RSS / mixed 首周期<span class="big">13.02 → 7.72 MiB</span>下降 40.70%；同窗口 none 臂下降为 0。{syscite}</div>
<div class="card">已释放 payload 的回收比例<span class="big">80.18%–85.45%</span>S4 B 批量释放代理；不是 RSS 降幅。{s4cite}</div>
<div class="card">业务 p99 / 固定判据<span class="big">未检出劣化</span>+6.229 ms，未超基线离散 6.784 ms。{gstcite}</div></div>
<p><strong>适用：</strong>glibc 管理、批量释放后仍有驻留空闲页、实测收益达标且代价过门的目标。
<strong>不适用：</strong>已经自动归还、没有可回收驻留、非 glibc 所有权，或收益不足的进程。常驻服务不能因“有空闲块”就默认启用。</p>
<p class="caution">性能结论的必要限定：同一 gst 数据中，p50 差 +1.870462 ms 超过基线离散 0.173927 ms；不能概括成“全部业务延迟无变化”。{gstcite}</p>
</section>

<section id="memory"><h2>内存收益：进程回收明确，系统净增尚未检出</h2>
<figure>{rss_chart(m['system'])}<figcaption>图 1 · 首周期前后 RSS。前值、后值、绝对降幅与百分比分别取三重复中位，不能用两列中位直接相减替代降幅统计。{syscite}</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>测试板负载</th><th>RSS 前 → 后 / MiB</th><th>降幅中位与窗口</th><th>证据 / 复算</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="scope">G3 头条展示首次释放；全周期合并 153 个点，典型降幅约 16.0%。代价统计取 <code>primary_cycles="2-51"</code>，排除冷启动首周期，因此收益与代价窗口不同；首周期收益不是持续周期典型收益。{syscite}{cite(SYSTEM+'gst_comparison.json', 'l1-system-before-after')}</p>
<p>不调用 trim 的对照臂，三个负载全部对应采样点的 RSS 下降均精确为 0。这支持本次调用前后进程下降归因于 trim；不表示系统背景波动为零，也不外推所有运行条件。{syscite}</p>
<figure>{net_chart(m['system'])}<figcaption>图 2 · 系统可用内存的配对净效应。定义为 trim 臂前后变化减去同重复、同周期 none 臂变化；两臂顺序执行，不是同步并行控制。{syscite}</figcaption></figure>
<p>沿用包内“幅度超过重复离散”的固定原则：系统项仅当 <code>|三重复中位| &gt; 重复极差</code> 才判可见；三组均为 <strong>NOT-DETECTED</strong>。gst 使用同一原则的正向劣化判据。它不是统计显著性检验，不能把正的系统中位读成已证明整机净增。{syscite}</p>
<p>释放后仍驻留的合成批量负载，S4 B 单次调用回收已释放 payload 的 <strong>80.175875%–85.453954%</strong>（约 80–85%）。这是堆 PD 回收量除以已释放对象字节，与上面的 RSS 分母不同。{s4cite}</p>
</section>

<section id="performance"><h2>性能与稳定性：检查负面影响，不宣称提升</h2>
<p>释放点调用是有代价的；已测结果支持“调用成本已量化，固定 p99 门未检出劣化”，不能写成数学意义上的零副作用。</p>
<figure>{costs_chart(m)}<figcaption>图 3 · 释放点耗时分布：S4 分档中位约 1.2 ms；gst 中位 0.671556 ms（约 0.67 ms）。gst 是真实多线程解码目标，但调用发生在管线 NULL release 后，非活跃并发分配瞬间的锁停顿测量。{s4cite}{cite(GST+'cycles.tsv', 'l1-gst-trim-cost')}</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>窗口 / 目标</th><th>调用耗时</th><th>代价或性质</th><th>证据 / 复算</th></tr></thead><tbody>{cost_rows}
<tr><td>gst / NULL release 后</td><td>p50 0.671556；p95 0.818315；p99 0.842185；max 0.856944 ms</td><td>153 次合并；下周期约 +359 minflt/循环</td><td>{gstcite}</td></tr>
{a_rows}</tbody></table></div>
<h3>业务延迟：p99 未检出，p50 差异如实保留</h3>
<p><strong>p99 中位差 +6.228611 ms &lt; 基线重复离散 6.784167 ms</strong>，故按固定门未检出劣化。
margin 为 0.555556 ms（约 0.556 ms），达到门槛的 91.8%。每臂三重复，每重复以 cycle 2–51 的 50 个样本计算 nearest-rank p99；这里 p99 就是该重复最大观测值。{gstcite}</p>
<p class="caution">“未检出”不等于数学零，也不构成产品 SLA 等价证明。同一规则用于 p50 会判可见：+1.870462 ms &gt; 0.173927 ms。尚不能证明任意活跃并发线程的锁停顿无影响。{gstcite}</p>
<h3>Faults 与稳定性：看清窗口与异常记录</h3>
<ul><li><strong>major fault：</strong>系统前后对照的采样窗口均为 0；有定义的下一周期也为 0，末周期的 NA 不计作零。S4 下一周期与 gst cycle 2–51 主窗口同样为 0。{syscite}{s4cite}{gstcite}</li>
<li><strong>冷启动例外：</strong>gst none 首重复 cycle=1 在任何 trim 前出现 4 次 major fault，外部序列同样记录 4；不归因于 trim，但不能写“全部实验全程为零”。旧 gst 附加 capture 字段缺失不冒充零，以有效目标内及外部序列为准。{cite([GST+'cycles.tsv', GST+'external_summary.tsv', GST+'health.json'], 'l1-impact-report')}</li>
<li><strong>再激活成本：</strong>S4 mixed / medium-only 下一周期分别增加 +1351 / +1465 minflt；gst 主窗口按重复总和中位之差摊到每循环约 +359。它与空闲页丢弃后重新建立映射相容；minor fault 本身不需要磁盘页读入，不能据此承诺整个进程没有其他磁盘 I/O。{s4cite}{gstcite}</li>
<li><strong>已测稳定性：</strong>S4、gst 的记录窗口零 OOM/LMK，zram 三项 Δ=0；gst 目标正常退出，原生守护进程的已完成观测中 PID/启动身份保持，未发现崩溃或重启。不将有限实验窗口改称长期无异常证明。{cite([S4+'health.json', GST+'health.json', NATIVE+'health.json', B2+'summary.json'], 'l1-impact-report')}</li>
<li><strong>并非全历史零告警：</strong>A 锚点有已知告警豁免记录；触发理由与窗口可复现，未做无害性根因证明。系统矩阵分期执行、延期完成收尾，已知非空目录保留，不能表述成不中断运行且现场零残留。{cite(SYSTEM+'composition.json', 'l1-system-before-after')}<a href="demo_reproduction_guide_20260901.md#l2-acceptance">健康规则与既有记录</a></li></ul>
<h3>集成影响与选择性启用</h3>
<p>本次 trim/none 对照使用相同 ELF，由运行时参数选择是否调用，不替换 libc，不因启用开关改变二进制体积或构建产物。
<strong>启动时间未做专项测量</strong>；释放点设计不要求在启动路径执行 trim，但“产物未变”不是启动耗时完全不变的实证。产品增加调用点是否需要 owner 改动，由集成方式决定。{cite(SYSTEM+'composition.json', 'l1-system-before-after')}<a href="system_level_before_after_20260908.md#13-已验收矩阵合成与优化效果">同产物对照口径</a></p>
<p>不满足门的目标可以完全不调用，因此没有新增的 trim 调用开销；这是一种收缩影响面的方式，不是整个系统风险为零的保证。</p>
</section>

<section id="applicability"><h2>适用面：批量释放收益明显，已测常驻服务收益很小</h2>
<figure>{applicability_chart(m)}<figcaption>图 4 · 同为 glibc 堆 PD 回收，单位 KiB。前三项为系统前后对照的首周期中位；其余为常驻服务单格观测，不混合计算百分比。{syscite}{nativecite}</figcaption></figure>
<p>enlightenment 的 E1 / E4′ 实测回收分别为 <strong>272 KiB / 36 KiB</strong>；G4 为 <strong>88 / 0 / 4 KiB</strong>。
G4 RSS 降幅中位 0.003906 MiB / 0.033659%，对重复极差 0.089844 MiB，NOT-DETECTED。其注入耗时中位 <strong>1899.209517 ms</strong> 含 gdb/ptrace，不与释放点约 1 ms 的调用数字混列。{nativecite}{syscite}</p>
<p>空闲块驻留量不等于可回收量。glibc 归还受完整空闲页与 allocator 状态约束，碎片化可能让许多空闲字节无法形成可归还页；这些聚合观测不能唯一定位块地址或机制路径。
整页估算器在严格配对的 15/15 个观测中未覆盖实测值，因此不能用直方图预测替代实际探针。{cite('trimmable_estimator_20260905/validation.tsv', 'l1-tizen-native-b2')}<a href="trimmable_estimator_20260905.md#3-失败模式与裁决">失败模式</a></p>
<h3>产品启用：连续通过四道硬门</h3>
<p class="scope"><strong>反信号排除 → 堆内驻留确认 → 实测 trim 探针收益达标 → 代价预算</strong></p>
<ol><li>已经自动归还的周期分量排除；PD 自发下降不是需要 trim 的证据。</li>
<li>以 malloc_info 的 M7 口径确认 glibc bins 中有空闲驻留，不把 smaps 平台直接当作可回收量。</li>
<li>同目标、同释放相位实测 trim；收益须达到事前固定阈值，不能由估算器预测替代。</li>
<li>调用时间、下一周期 faults 与活跃并发锁停顿都须符合业务预算；未过门则不启用。</li></ol>
<p><a href="product_landing_recommendation_20260901.md#1-启用门清单">完整产品启用条件</a> · <a href="demo_reproduction_guide_20260901.md#l1-servicea">自动归还反信号的 L1 复算</a></p>
</section>

<section id="boundaries"><h2>边界与未决</h2>
<ul><li><strong>测试板量级，不等于产品收益。</strong>进程 RSS 回收明确；系统净效应未检出，不外推整机收益或业务收益。</li>
<li><strong>产品候选尚未完成 floor 复确认与 live/bin 分解。</strong>需要目标 owner 配合采集堆内分布；现有平台高度只能登记候选。</li>
<li><strong>真实并发预算仍有缺口。</strong>合成代理不能覆盖产品并发；gst 在 NULL 后调用，只补了该释放点与后续循环代价，未直接量化活跃分配时全 arena 锁停顿、帧时延和能耗。</li>
<li><strong>镜像、内存环境与负载差异。</strong>测试板的对象尺寸、分配历史和释放方式不能替代产品现场，产品必须重新验证启用门。</li>
<li><strong>不作统一启用承诺。</strong>已测常驻守护收益很小，M7 驻留与估算器都不能给出统一收益阈值；未检出 p99 劣化不等于所有性能维度无变化。</li></ul>
<p><a href="product_landing_recommendation_20260901.md">产品落点建议</a> · <a href="product_m7_feasibility_20260902.md">产品 M7 可行路径</a> · <a href="gst_trim_cost_20260901.md#d-是否填上并发线程代价未知">并发证据的具体缺口</a></p>
</section>

<section id="reproduction"><h2>复现入口：只读公开证据</h2>
<p>在完整 Git 克隆的仓库根目录执行以下命令，不连接测试板。图表由公开 TSV/JSON 生成；HTML 不依赖脚本、字体下载或外部图片。
单文件可离线阅读或邮件发送；相对证据链接需要配套仓库目录。<a href="{GUIDE}#l1-impact-report">本报告 L1 对照与预期输出</a></p>
<h3>重建本报告并逐字节核验</h3>
<pre>impact_out=$(mktemp -d)
python3 tools/report/build_impact_report.py --output "$impact_out/glibc_memopt_impact_report.html"
cmp "$impact_out/glibc_memopt_impact_report.html" docs/glibc_memopt_impact_report.html
python3 tools/report/build_impact_report.py --check
python3 -m unittest tools.report.test_build_impact_report</pre>
<h3>从原始公开点重放系统前后对照</h3>
<pre>system_out=$(mktemp -d)
system_source=data/raw/system_level_before_after_20260908/accepted_matrix
python3 tools/runners/system_level_before_after_20260908/replay_compact.py \
  --points "$system_source/point_source.json" \
  --gst-cycles "$system_source/gst_cycles.tsv" --output-dir "$system_out"
cmp "$system_source/cycles.tsv" "$system_out/cycles.tsv"
cmp "$system_source/summary.tsv" "$system_out/summary.tsv"
cmp "$system_source/gst_repetitions.tsv" "$system_out/gst_repetitions.tsv"
cmp "$system_source/gst_arms.tsv" "$system_out/gst_arms.tsv"
cmp "$system_source/gst_comparison.json" "$system_out/gst_comparison.json"</pre>
<p>{syscite}</p>
<h3>重放业务代价；其他指标按相应 L1 段复算</h3>
<pre>gst_out=$(mktemp -d)
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --replay-cycles data/raw/gst_trim_cost_20260901/cycles.tsv --output "$gst_out"
cmp "$gst_out/repetitions.tsv" data/raw/gst_trim_cost_20260901/repetitions.tsv
cmp "$gst_out/arm_summary.tsv" data/raw/gst_trim_cost_20260901/arm_summary.tsv
cmp "$gst_out/comparison.json" data/raw/gst_trim_cost_20260901/comparison.json</pre>
<p>{gstcite}{s4cite}{nativecite}</p>
<p><strong>demo-v14 交付包：</strong><a href="demo_package_20260902.md">包入口</a> · <a href="demo_reproduction_guide_20260901.md">完整复现指南</a> · <a href="../data/raw/demo_v14_delivery_20260915/verification.json">冻结快照与交付回执</a>。
该标签保留；本报告是 main 上新增独立说明，不改冻结包。<code>bash tools/reproduce/reproduce.sh verify</code> 是完整 host 校验入口，本报告的重建测试也随正常 verify 执行。</p>
<details><summary>公开输入与冻结字节清单</summary><ul>{inputs}</ul><p><a href="{GUIDE}#l1-impact-report">上述输入的 L1 映射</a> · <a href="../tools/report/impact_sources.json">机器清单</a></p></details>
</section>
<footer>证据基线 commit：{refs['evidence_commit']}（指证据快照，不是生成器执行证明）。本文件为派生产物，可由
<a href="../tools/report/build_impact_report.py">生成脚本</a> 重建。未修改既有测量数据、验收带、机制或复现入口。</footer>
</main></body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='rebuild in memory, compare committed HTML; no writes')
    args = parser.parse_args()
    if args.check and args.output:
        parser.error('--check and --output are mutually exclusive')
    try:
        report = build(args.repo_root).encode('utf-8')
        if args.check:
            if (args.repo_root / 'docs/glibc_memopt_impact_report.html').read_bytes() != report:
                raise ValueError('committed HTML differs from rebuild; regenerate and review the diff')
            print('PASS impact report: frozen inputs, numeric controls, byte-identical HTML')
        else:
            output = args.output or args.repo_root / 'docs/glibc_memopt_impact_report.html'
            output.write_bytes(report)
            print('PASS impact report generated from frozen public evidence')
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'FAIL impact report: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
