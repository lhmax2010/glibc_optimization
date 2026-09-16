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
import posixpath
import re
import statistics as stats
import subprocess
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SYSTEM = 'system_level_before_after_20260908/accepted_matrix/'
S4 = 's4_retention_20260901/'
GST = 'gst_trim_cost_20260901/'
NATIVE = 'tizen_native_evidence_20260904/'
B2 = 'tizen_native_evidence_b2_20260904/'
GUIDE = 'demo_reproduction_guide_20260901.md'
PROFILES = {'mixed': '混合尺寸分配负载', 'medium-only': '中等尺寸为主的分配负载'}
LABELS = {'G1': PROFILES['mixed'], 'G2': PROFILES['medium-only'],
          'G3': '媒体解码循环负载', 'G4': '常驻 UI 合成器进程'}


class ReportDocument(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.text = [], set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src'):
                if not value:
                    raise ValueError('empty report link')
                self.links.append(value)
            if key == 'id':
                self.ids.add(value)

    def handle_data(self, data):
        self.text.append(data)


FORBIDDEN = re.compile(
    r'人工智能|智能体|模型|评审|复审|'
    r'(?<![a-z0-9])(?:ai|agents?|agentic|llms?|models?|codex|openai|chatgpt|'
    r'claude|gemini|kimi|reviews?)(?![a-z0-9])', re.I)


def check_keywords(report):
    # Include comments, metadata and attributes, not just visible paragraphs.
    # Also inspect joined text so entities or inline tags cannot split a word.
    doc = ReportDocument(report)
    for source in (report, ''.join(doc.text)):
        text = unicodedata.normalize('NFKC', html.unescape(source))
        text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
        match = FORBIDDEN.search(text)
        if match:
            raise ValueError(f'forbidden report keyword: {match.group()}')


def snapshot(repo):
    refs = json.loads((repo / 'tools/report/impact_delivery.json').read_text())
    commit = refs['commit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('delivery snapshot must be a full commit SHA')
    run = subprocess.run(['git', '-C', str(repo), 'ls-tree', '-rz', '--full-tree', commit], capture_output=True)
    if run.returncode:
        raise ValueError(f'delivery snapshot {commit} unavailable; fetch it with '
                         f'git fetch --no-tags origin {commit}; no checks were skipped')
    files = {}
    for entry in run.stdout.split(b'\0'):
        if entry:
            meta, path = entry.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            if kind == 'blob' and mode in ('100644', '100755'):
                files[path.decode()] = oid
    return refs, files


def snapshot_blob(repo, oid):
    run = subprocess.run(['git', '-C', str(repo), 'cat-file', 'blob', oid], capture_output=True)
    if run.returncode:
        raise ValueError(f'delivery blob unavailable: {oid}; fetch the delivery snapshot')
    return run.stdout


def document_anchors(text, path):
    found = ReportDocument(text).ids
    if not path.endswith('.md'):
        return found
    counts = {}
    for line in text.splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*$', line)
        if match:
            title = re.sub(r'`([^`]*)`', r'\1', match[1].strip().lower())
            base = re.sub(r'\s+', '-', re.sub(r'[^\w\-\s\u4e00-\u9fff]', '', title))
            count = counts.get(base, 0)
            counts[base] = count + 1
            found.add(base if not count else f'{base}-{count}')
    return found


def check_delivery_links(repo, report, evidence=None):
    refs, files = snapshot(repo)
    document = ReportDocument(report)
    cache = {}

    def read(path):
        if path not in files:
            raise ValueError(f'link not in {refs["tag"]} snapshot: {path}')
        if path not in cache:
            cache[path] = snapshot_blob(repo, files[path])
        return cache[path]

    for link in document.links:
        url = urlsplit(link)
        if url.scheme or url.netloc or url.query or url.path.startswith('/'):
            raise ValueError(f'report link must be repository-relative: {link}')
        path = posixpath.normpath(posixpath.join('docs', unquote(url.path))) if url.path else ''
        if path == '..' or path.startswith('../') or '\\' in path:
            raise ValueError(f'report link escapes delivery snapshot: {link}')
        anchors = document.ids
        if path:
            blob = read(path)
            if url.fragment:
                anchors = document_anchors(blob.decode('utf-8'), path)
        if url.fragment and unquote(url.fragment) not in anchors:
            raise ValueError(f'anchor not in {refs["tag"]} snapshot: {link}')
    # The linked frozen files must contain the exact bytes used in the plots.
    for relative, expected in (evidence or {}).items():
        expect(hashlib.sha256(read('data/raw/' + relative)).hexdigest(), expected,
               'delivery evidence ' + relative)
    return len(document.links)


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
    return result


def cite(paths, anchor):
    if isinstance(paths, str):
        paths = [paths]
    links = [f'<a href="../data/raw/{html.escape(p, quote=True)}">公开证据{index if len(paths) > 1 else ""}</a>'
             for index, p in enumerate(paths, 1)]
    links.append(f'<a href="{GUIDE}#{anchor}">公开数据复算（L1）</a>')
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
            parts.append(f'<rect x="250" y="{y-21+j*30}" width="{width:.3f}" height="22" class="{color}"/>')
            parts.append(f'<text x="{262+width:.3f}" y="{y-5+j*30}">{label} {float(r[key]):.2f} MiB</text>')
        parts.append(f'<text x="250" y="{y+63}" class="accent">下降 {float(r["drop"]):.2f} MiB · {float(r["pct"]):.2f}%</text>')
    parts.append('<text x="250" y="385">共同零基线；精确值见下表，媒体负载全周期口径另列。</text></svg>')
    return ''.join(parts)


def net_chart(values):
    parts = [svg_open('系统 MemAvailable 净效应与重复极差，均未检出', 266)]
    for i, group in enumerate(('G1', 'G2', 'G3')):
        r = values[group]; y = 51 + i*72
        parts.append(f'<text x="12" y="{y}">{LABELS[group]}</text>')
        # Two magnitude bars, NOT a confidence interval or ±range error bar.
        for j, (value, color) in enumerate(((abs(float(r['net'])), 'after'), (float(r['spread']), 'before'))):
            parts.append(f'<rect x="250" y="{y-18+j*22}" width="{value*34:.3f}" height="15" class="{color}"/>')
        parts.append(f'<text x="590" y="{y-4}">中位 {float(r["net"]):+.6f} MiB</text>')
        parts.append(f'<text x="590" y="{y+19}">极差 {r["spread"]} MiB · NOT-DETECTED</text>')
    parts.append('<text x="120" y="260">绿色：中位绝对值；灰色：重复极差。原符号在标注保留，不是置信区间。</text></svg>')
    return ''.join(parts)


def costs_chart(metrics):
    parts = [svg_open('释放点 trim 调用耗时分布；大块释放基准单独列出', 290)]
    for i, (label, times, median) in enumerate((
        (PROFILES['mixed'], metrics['s4']['mixed']['times'], '1.233269'),
        (PROFILES['medium-only'], metrics['s4']['medium-only']['times'], '1.218361'),
        ('媒体管线停止释放后', metrics['gst_times'], '0.671556'),
    )):
        y = 52+i*72
        parts.append(f'<text x="12" y="{y}">{label}</text>')
        parts.append(f'<line x1="250" x2="730" y1="{y}" y2="{y}" class="axis"/>')
        for j, elapsed in enumerate(sorted(times)):
            parts.append(f'<circle cx="{250+float(elapsed)*230:.3f}" cy="{y+(j%5-2)*4}" r="3" class="point"/>')
        parts.append(f'<text x="755" y="{y+5}">中位 {median} ms</text>')
    for tick in (0, .5, 1, 1.5, 2):
        parts.append(f'<text x="{250+tick*230:.0f}" y="242" text-anchor="middle">{tick:g}</text>')
    parts.append('<text x="160" y="275">横轴：耗时（ms）；共同零起点，每个点为一次调用，纵向仅作防重叠。</text></svg>')
    return ''.join(parts)


def applicability_chart(metrics):
    items = [(LABELS[g] + ' / 首周期中位', int(metrics['system'][g]['heap_kib'])) for g in ('G1', 'G2', 'G3')]
    items += [('常驻 UI 合成器 / 初始观测', 272), ('常驻 UI 合成器 / 应用释放后', 36),
              ('常驻 UI 合成器 / 后续观测一', 88), ('常驻 UI 合成器 / 后续观测二', 0),
              ('常驻 UI 合成器 / 后续观测三', 4)]
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
    nativecite = cite([NATIVE+'summary.json', B2+'summary.json'], 'l1-tizen-native-b2')
    rows = []
    for group, r in m['system'].items():
        scope = ('<small>媒体负载运行 51 周期，此处为首周期；全周期降幅中位 16.038164%（13.28–21.04%；精确范围 13.282648–21.043165%）。</small>' if group == 'G3' else f'<small>全周期降幅中位 {r["full_pct"]}%。</small>')
        rows.append(f'<tr><td>{LABELS[group]}</td><td>{r["pre"]} → {r["post"]}</td><td>{r["drop"]} MiB / {r["pct"]}%{scope}</td><td>{syscite}</td></tr>')
    cost_rows = ''.join(f'<tr><td>{PROFILES[p]} / 批量释放后</td><td>{r["median"]} ms</td><td>+{r["extra"]} 次 minor fault；下一周期 major fault 为 0</td><td>{s4cite}</td></tr>' for p, r in m['s4'].items())
    a_rows = ''.join(f'<tr><td>大块释放后的回收基准 / {PROFILES[r["profile"]]}</td><td>{fixed(r["trim_elapsed_ms"])} ms</td><td>大区域回收调用，不代表日常释放点的调用成本；每档单次观测。</td><td>{cite(S4+"a_cells.tsv", "l1-s4")}</td></tr>' for r in m['a'])
    report = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="在现有 glibc 上按条件归还空闲内存：进程回收量、调用代价、稳定性与产品启用边界。">
<title>glibc 运行时内存回收｜影响报告</title><style>{STYLE}</style></head><body><main>
<header><div class="eyebrow">TIZEN · GLIBC · 运行时内存回收</div>
<h1>让已释放的内存，真正回到系统</h1>
<p class="lead">本方案不替换 libc、不改本次对照实验的二进制；在现有 glibc 上，于业务批量释放对象后按条件调用 <code>malloc_trim(0)</code>。</p>
<p><code>malloc_trim</code> 是 glibc 提供的运行时接口：它尝试把分配器中已经空闲、但仍占用物理内存的完整页归还内核。
操作系统按页回收内存；一页内只要还有必须保留的数据，就不能整页丢弃。因此，<code>free</code> 释放的对象字节不一定都能立即转化为可回收页。</p>
<p><strong>内存有明确收益；按固定 p99 判据未检出性能劣化，已测窗口未发现 OOM/LMK 或目标重启。</strong>
这是带范围的“未检出副作用”，不是所有性能指标零影响或长期稳定性的证明；本报告不宣称性能提升。</p>
<p class="muted">只组织既有公开证据，没有新测量。收益指进程内存回收，不等于整机或产品收益。</p>
<nav aria-label="报告导航"><a href="#summary">摘要</a><a href="#memory">内存收益</a><a href="#performance">性能与稳定性</a><a href="#applicability">适用面</a><a href="#boundaries">边界</a><a href="#reproduction">复现</a></nav></header>

<section id="summary"><h2>一页摘要</h2>
<p>本报告包含两种<strong>批量分配—释放负载</strong>：混合尺寸分配负载反复申请不同大小的对象，再集中释放其中一部分；中等尺寸为主的分配负载执行同样的过程，但以中等大小对象为主。
<strong>媒体解码循环负载</strong>则反复进行软件解码，停止管线并释放资源后再进入下一轮。
常驻 UI 合成器进程（enlightenment）作为不同使用场景的对照：它持续负责界面合成，不以大批对象集中释放为主要形态。</p>
<p>下文的<strong>对照臂</strong>指使用相同二进制和相同负载参数、但不调用 trim 的一组运行；与调用 trim 的运行在对应时点取样。
<strong>RSS</strong>是进程当前驻留在物理内存中的总页量，包含代码、栈、共享页及其他映射；<strong>堆内 Private_Dirty（简称堆 PD）</strong>仅统计本报告归类到 glibc 堆的私有脏页，二者不是同一个范围。
所有内存图表使用 MiB 或 KiB。</p>
<div class="cards"><div class="card">混合尺寸分配负载 / 首周期 RSS<span class="big">13.02 → 7.72 MiB</span>下降 40.70%；不调用 trim 的对照下降为 0。{syscite}</div>
<div class="card">已释放对象字节的回收比例<span class="big">80.18%–85.45%</span>批量释放后仍占用堆内存的合成负载；不是 RSS 降幅。{s4cite}</div>
<div class="card">业务尾部延迟 / 固定判据<span class="big">未检出劣化</span>p99 差 +6.229 ms，小于基线重复波动 6.784 ms。{gstcite}</div></div>
<p><strong>适用：</strong>由 glibc 管理、批量释放后仍有驻留空闲页、实测收益达标且代价在预算内的目标。
<strong>不适用：</strong>已经自行归还的那部分内存，以及没有可回收驻留空闲页、使用其他分配器或实测收益不足的进程。
同一进程中其他尚未归还的内存仍须单独实测；常驻服务不能因“有空闲块”就默认启用。</p>
<p>统计量的读法：中位数表示排序后的中间位置，极差表示最大值减最小值；p50 表示中间水平，p99 用于观察较慢的尾部延迟。判定阈值和样本窗口在后文就地列出。</p>
<p class="caution">性能结论的必要限定：同一媒体解码数据中，p50 差 +1.870462 ms 超过基线重复波动 0.173927 ms；不能概括成“全部业务延迟无变化”。{gstcite}</p>
</section>

<section id="memory"><h2>内存收益：进程回收明确，系统净增尚未检出</h2>
<figure>{rss_chart(m['system'])}<figcaption>图 1 · 首周期前后 RSS。前值、后值、绝对降幅与百分比分别取三重复中位，不能用两列中位直接相减替代降幅统计。{syscite}</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>测试板负载</th><th>RSS 前 → 后 / MiB</th><th>降幅中位与窗口</th><th>证据 / 复算</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="scope">媒体解码负载的头条展示首次释放；全周期合并 153 个点，典型降幅约 16.0%。代价统计只取第 2–51 周期，排除冷启动首周期，因此收益与代价窗口不同；首周期收益不是持续周期典型收益。{syscite}{cite(SYSTEM+'gst_comparison.json', 'l1-system-before-after')}</p>
<p>不调用 trim 的对照臂，三个负载全部对应采样点的 RSS 下降均精确为 0。这支持本次调用前后进程下降归因于 trim；不表示系统背景波动为零，也不外推所有运行条件。{syscite}</p>
<figure>{net_chart(m['system'])}<figcaption>图 2 · 系统可用内存（MemAvailable）的配对净效应。计算方式：调用 trim 前后的变化，减去同重复、同周期中不调用 trim 的变化；两组顺序执行，不是同步并行控制。{syscite}</figcaption></figure>
<p>固定判据要求：只有三重复中位数的绝对值大于重复极差，才把系统净效应判为可见。
本次每组差值都小于同一条件下重复测量自身的波动范围，因此三组均为 <strong>NOT-DETECTED（未检出）</strong>。
业务 p99 也按“劣化幅度超过基线重复波动才判可见”的同一原则判断。这不是统计显著性检验，不能把正的系统中位读成已证明整机净增。{syscite}</p>
<p>对于释放后内存仍留在堆内的合成批量负载，单次调用回收已释放对象字节的 <strong>80.175875%–85.453954%</strong>（约 80–85%）。这是堆 PD 回收量除以已释放对象字节，与上面的 RSS 分母不同。{s4cite}</p>
</section>

<section id="performance"><h2>性能与稳定性：检查负面影响，不宣称提升</h2>
<p>释放点调用是有代价的；已测结果支持“调用成本已量化，按固定 p99 判据未检出劣化”，不能写成数学意义上的零副作用。</p>
<figure>{costs_chart(m)}<figcaption>图 3 · 释放点耗时分布：两种分配负载的中位约 1.2 ms；媒体解码负载中位 0.671556 ms（约 0.67 ms）。后者是真实多线程解码目标，但调用发生在管线进入 NULL 状态、停止并释放资源后，不是活跃并发分配瞬间的锁停顿测量。{s4cite}{cite(GST+'cycles.tsv', 'l1-gst-trim-cost')}</figcaption></figure>
<div class="table-wrap"><table><thead><tr><th>窗口 / 目标</th><th>调用耗时</th><th>代价或性质</th><th>证据 / 复算</th></tr></thead><tbody>{cost_rows}
<tr><td>媒体管线停止并释放资源后</td><td>p50 0.671556；p95 0.818315；p99 0.842185；最大值 0.856944 ms</td><td>153 次合并；下周期每循环约增加 +359 次 minor fault</td><td>{gstcite}</td></tr>
{a_rows}</tbody></table></div>
<h3>业务延迟：p99 未检出，p50 差异如实保留</h3>
<p><strong>p99 中位差 +6.228611 ms &lt; 基线重复波动 6.784167 ms</strong>：加上调用后的差值没有超过不调用时重复测量自身的波动，因此按固定判据未检出劣化。
距判定阈值还差 0.555556 ms（约 0.556 ms），已达到门槛的 91.8%。每组运行三重复，每重复取第 2–51 周期的 50 个样本；p99 按排序后向上取整的百分位位置计算（nearest-rank），这里恰好是该重复的最大观测值。{gstcite}</p>
<p class="caution">“未检出”不等于数学零，也不构成产品 SLA 等价证明。同一规则用于 p50 会判可见：+1.870462 ms &gt; 0.173927 ms。尚不能证明任意活跃并发线程的锁停顿无影响。{gstcite}</p>
<h3>缺页与稳定性：看清窗口与异常记录</h3>
<p>minor fault 指无需从后备存储读入页面就能处理的缺页；major fault 则需要调入页面。前者增加通常表现为页映射重新建立的成本，不能与后者混为一谈。
OOM/LMK 指内存不足或低内存杀进程记录；zram 是内存中的压缩交换设备，本报告记录其原始数据量、压缩数据量与占用内存量的变化。</p>
<ul><li><strong>major fault：</strong>系统前后对照的采样窗口均为 0；有定义的下一周期也为 0，末周期的缺失值不计作零。批量分配负载下一周期与媒体解码第 2–51 周期主窗口同样为 0。{syscite}{s4cite}{gstcite}</li>
<li><strong>冷启动例外：</strong>媒体解码不调用 trim 的首重复、首周期，在任何 trim 前出现 4 次 major fault，外部序列同样记录 4；不归因于 trim，但不能写“全部实验全程为零”。早期媒体实验的附加采样字段缺失不冒充零，以有效目标内及外部序列为准。{cite([GST+'cycles.tsv', GST+'external_summary.tsv', GST+'health.json'], 'l1-gst-trim-cost')}</li>
<li><strong>再激活成本：</strong>混合尺寸与中等尺寸为主的分配负载，下一周期分别增加 +1351 / +1465 次 minor fault；媒体解码主窗口按重复总和中位之差摊到每循环约 +359。它与空闲页丢弃后重新建立映射相容；minor fault 本身不需要磁盘页读入，不能据此承诺整个进程没有其他磁盘 I/O。{s4cite}{gstcite}</li>
<li><strong>已测稳定性：</strong>批量分配与媒体解码的记录窗口零 OOM/LMK，zram 三项变化均为 0；媒体目标正常退出，常驻 UI 合成器的已完成观测中进程号和启动身份保持，未发现崩溃或重启。不将有限实验窗口改称长期无异常证明。{cite([S4+'health.json', GST+'health.json'], 'l1-gst-trim-cost')}{cite([NATIVE+'health.json', B2+'summary.json'], 'l1-tizen-native-b2')}</li>
<li><strong>并非全历史零告警：</strong>大块释放后的回收基准有已知告警豁免记录；触发理由与窗口可复现，未做无害性根因证明。系统前后对照实验分期执行、延期完成收尾，已知非空目录保留，不能表述成不中断运行且现场零残留。{cite(SYSTEM+'composition.json', 'l1-system-before-after')}<a href="demo_reproduction_guide_20260901.md#l2-acceptance">健康规则与既有记录</a></li></ul>
<h3>集成影响与选择性启用</h3>
<p>本次调用与不调用的对照使用相同可执行文件，由运行时参数选择是否调用，不替换 libc，不因启用开关改变二进制体积或构建产物。
<strong>启动时间未做专项测量</strong>；释放点设计不要求在启动路径执行 trim，但“产物未变”不是启动耗时完全不变的实证。产品增加调用点是否需要目标维护者改动，由集成方式决定。{cite(SYSTEM+'composition.json', 'l1-system-before-after')}<a href="system_level_before_after_20260908.md#13-已验收矩阵合成与优化效果">同产物对照口径</a></p>
<p>不满足门的目标可以完全不调用，因此没有新增的 trim 调用开销；这是一种收缩影响面的方式，不是整个系统风险为零的保证。</p>
</section>

<section id="applicability"><h2>适用面：批量释放收益明显，已测常驻服务收益很小</h2>
<figure>{applicability_chart(m)}<figcaption>图 4 · 同为 glibc 堆 PD 回收，单位 KiB。前三项为系统前后对照的首周期中位；其余为常驻服务单格观测，不混合计算百分比。{syscite}{nativecite}</figcaption></figure>
<p>常驻 UI 合成器的初始观测、应用释放后的观测，实测回收分别为 <strong>272 KiB / 36 KiB</strong>；后续三次观测为 <strong>88 / 0 / 4 KiB</strong>。
后续 RSS 降幅中位 0.003906 MiB / 0.033659%，小于重复极差 0.089844 MiB，判为 NOT-DETECTED（未检出）。其注入耗时中位 <strong>1899.209517 ms</strong> 包含 gdb 调试器附加、通过 ptrace 控制目标进程等注入开销，不与释放点约 1 ms 的调用数字混列。{nativecite}{syscite}</p>
<p>空闲块驻留量不等于可回收量。glibc 归还受完整空闲页与分配器状态约束，碎片化可能让许多空闲字节无法形成可归还页；这些聚合观测不能唯一定位块地址或机制路径。
整页估算器在严格配对的 15/15 个观测中未覆盖实测值，因此不能用直方图预测替代实际探针。{cite('trimmable_estimator_20260905/validation.tsv', 'l1-tizen-native-b2')}<a href="trimmable_estimator_20260905.md#3-失败模式与裁决">失败模式</a></p>
<h3>产品启用：连续通过四道硬门</h3>
<p class="scope"><strong>排除已经自行归还的那部分内存 → 确认释放后的空闲内存仍留在堆内 → 实测 trim 回收收益达标 → 确认代价在预算内</strong></p>
<ol><li>对已经自行归还的周期分量，不启用额外回收；堆 PD 自发下降不是需要 trim 的证据。</li>
<li>用 glibc 的 <code>malloc_info</code> 接口查看各分配区域的空闲块统计，确认有已释放但仍驻留的内存；不能只看到内核 <code>smaps</code> 的内存曲线不下降，就认定这些内存全都可回收。</li>
<li>在同目标、同释放时点试调用 trim 并测量实际收益；收益须达到事前固定阈值，不能用空闲块尺寸直方图的预测替代。</li>
<li>调用时间、下一周期缺页与活跃并发锁停顿都须符合业务预算；未过门则不启用。</li></ol>
<p><a href="product_landing_recommendation_20260901.md#1-启用门清单">完整产品启用条件</a> · <a href="demo_reproduction_guide_20260901.md#l1-servicea">堆内存自行归还的公开数据复算</a></p>
</section>

<section id="boundaries"><h2>边界与未决</h2>
<ul><li><strong>测试板量级，不等于产品收益。</strong>进程 RSS 回收明确；系统净效应未检出，不外推整机收益或业务收益。</li>
<li><strong>产品候选的持续内存占用尚未重新确认，也未区分仍在使用的对象与已释放的空闲块。</strong>需要目标维护者配合采集堆内分布；曲线上不再下降的内存量只能用来登记待查对象。</li>
<li><strong>真实并发预算仍有缺口。</strong>合成负载不能覆盖产品并发；媒体实验在管线停止释放后调用，只补了该释放点与后续循环代价，未直接量化活跃分配时各分配区域锁竞争造成的停顿、帧时延和能耗。</li>
<li><strong>镜像、内存环境与负载差异。</strong>测试板的对象尺寸、分配历史和释放方式不能替代产品现场，产品必须重新验证启用门。</li>
<li><strong>不作统一启用承诺。</strong>已测常驻守护收益很小，空闲块驻留统计与整页估算器都不能给出统一收益阈值；未检出 p99 劣化不等于所有性能维度无变化。</li></ul>
<p><a href="product_landing_recommendation_20260901.md">产品落点建议</a> · <a href="product_m7_feasibility_20260902.md">产品堆内空闲块采集的可行路径</a> · <a href="gst_trim_cost_20260901.md#d-是否填上并发线程代价未知">并发证据的具体缺口</a></p>
</section>

<section id="reproduction"><h2>复现入口：只读公开证据</h2>
<p>本报告可作为单文件离线阅读或邮件发送；图表以内联 SVG 保存，不下载脚本、字体或图片。
<strong>先验包，再添加阅读材料：</strong>先在未添加本报告的干净 Git 克隆根目录运行 <code>bash tools/reproduce/reproduce.sh verify</code>，核验 demo-v14 交付包。
之后另用一份阅读副本放置本报告；不要在待验证的干净克隆中添加文件，完整校验会拒绝未跟踪文件，不应绕过该门。</p>
<p>
如需打开相对证据链接，请将单独收到的本报告放入 <strong>demo-v14 交付快照的 docs/ 目录</strong>，再打开本文件。正文链接只引用该快照已公开的文件与章节，不要求访问本地工作区或后续提交。</p>
<p><strong>L1 复算</strong>是仅用公开表格和脚本重新计算已发布结果，不连接测试板，不产生新测量。下面各入口提供可照抄的命令与预期输出：</p>
<ul><li><a href="{GUIDE}#l1-system-before-after">进程 RSS、系统可用内存净效应与常驻服务对照：复算命令及逐字节比较</a>{syscite}</li>
<li><a href="{GUIDE}#l1-s4">批量释放回收比例、调用耗时与下一周期缺页：复算命令</a>{s4cite}</li>
<li><a href="{GUIDE}#l1-gst-trim-cost">媒体解码业务延迟与调用耗时分布：复算命令及逐字节比较</a>{gstcite}</li>
<li><a href="{GUIDE}#l1-tizen-native-b2">原生进程观测与整页估算器：复算命令</a>{nativecite}</li></ul>
<p><strong>demo-v14 交付包：</strong><a href="../README.md">交付入口（含中文入口）</a> · <a href="demo_package_20260902.md">演示材料与证据导航</a> · <a href="{GUIDE}">完整复现指南</a>。
该冻结包的完整 host 校验不包含本次另行提供的报告重建测试。本报告不修改该冻结包。
完整原始件本地留存，可按请求提供；上述公开紧凑证据可直接访问。</p>
</section>
<footer>链接与证据校验基线：demo-v14，commit 7289a47b9d24791944cd3b02c00f24b8cb76aa3b。本文件为可重建的派生产物；数字来自交付包公开证据。未修改既有测量数据、验收带、机制或复现入口。</footer>
</main></body></html>
'''
    check_keywords(report)
    check_delivery_links(repo, report, refs['sha256'])
    return report


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
