#!/usr/bin/env python3
"""Offline impact report: frozen evidence, scope, links and exact rebuild.

Imported by test_build_demo_report so the unchanged verify entrypoint runs this
suite too. No extra executables beyond its existing Python/git environment.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from tools.report import build_impact_report as impact

REPO = Path(__file__).resolve().parents[2]
REPORT = REPO / 'docs/glibc_memopt_impact_report.html'
EN_REPORT = REPO / 'docs/glibc_memopt_impact_report.en.html'
BUILDER = REPO / 'tools/report/build_impact_report.py'


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.attributes = []
        self.tags = []
        self.structure = []
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.structure.append(('start', tag))
        self.attributes.extend(attrs)

    def handle_endtag(self, tag):
        self.structure.append(('end', tag))

    def handle_data(self, data):
        self.text.append(data)


class ImpactReportTests(unittest.TestCase):
    def test_english_cli_rebuild_is_byte_identical_and_repeatable(self):
        self.assertEqual(impact.build(REPO, 'en').encode(), EN_REPORT.read_bytes())
        self.assertEqual(impact.build(REPO, 'en'), impact.build(REPO, 'en'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'english.html'
            for arguments in (['--check'], ['--output', str(output)]):
                run = subprocess.run([sys.executable, str(BUILDER), '--lang', 'en', *arguments],
                                     cwd=REPO, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(output.read_bytes(), EN_REPORT.read_bytes())
        with self.assertRaisesRegex(ValueError, 'unsupported report language'):
            impact.build(REPO, 'invalid')

    def test_languages_have_identical_structure_plot_geometry_and_numbers(self):
        cn, en = Document(REPORT.read_text()), Document(EN_REPORT.read_text())
        self.assertEqual(cn.tags, en.tags)
        self.assertEqual(cn.structure, en.structure)
        # Text/accessible labels change; every other attribute is invariant,
        # including all chart coordinates, navigation and section identities.
        structural = lambda d: [(key, value) for key, value in d.attributes
                                if key not in ('lang', 'aria-label', 'content', 'title')]
        self.assertEqual(structural(cn), structural(en))
        tokens = re.compile(r'[+−-]?\d+(?:\.\d+)?%?')
        self.assertEqual(len(cn.text), len(en.text))
        for index, (left, right) in enumerate(zip(cn.text, en.text)):
            self.assertEqual(tokens.findall(left), tokens.findall(right), index)
        self.assertNotRegex(EN_REPORT.read_text(), impact.HAN)
        self.assertIn(('lang', 'en'), en.attributes)

    def test_languages_preserve_each_required_limit_and_plain_language_notice(self):
        catalog = json.loads((REPO/'tools/report/impact_en.json').read_text())
        required = {'no_zero_impact', 'no_speedup_claim', 'different_denominators',
                    'not_product_benefit', 'finite_observation', 'startup_unmeasured',
                    'typical_slowdown', 'injection_overhead', 'after_pipeline_stop',
                    'not_zero_system_risk', 'other_retained_memory'}
        self.assertEqual(set(catalog['limitations']), required)
        cn, en = (''.join(Document(path.read_text()).text) for path in (REPORT, EN_REPORT))
        for key, (left, right) in catalog['limitations'].items():
            with self.subTest(limit=key):
                self.assertEqual(cn.count(left), 1)
                self.assertEqual(en.count(right), cn.count(left))
        self.assertIn('英文版单独提供', cn)
        self.assertIn('Chinese edition is provided separately', en)
        self.assertIn('Chinese technical documentation is authoritative', en)

    def test_both_languages_apply_standalone_keyword_and_internal_name_gates(self):
        for path in (REPORT, EN_REPORT):
            text = path.read_text()
            impact.check_keywords(text)
            self.assertEqual(impact.check_single_file(text), 5)
        for sample in ('mixed', 'medium-only', 'G1', 'g4', 'S4', 'M7', 'T1′', '反信号'):
            with self.subTest(sample=sample), self.assertRaisesRegex(ValueError, 'internal report term'):
                impact.check_keywords(f'<p>{sample}</p>')
        for lang in ('zh-CN', 'en'):
            for addition, diagnostic in (('<!-- p99 -->', 'forbidden report keyword'),
                                          ('<meta content="agent">', 'forbidden report keyword'),
                                          ('<p>G3</p>', 'internal report term'),
                                          ('<a href="report.html">go</a>', 'only #anchor')):
                with self.subTest(lang=lang, addition=addition), \
                     mock.patch.object(impact, 'costs_chart', return_value=addition), \
                     self.assertRaisesRegex(ValueError, diagnostic):
                    impact.build(REPO, lang)

    def test_translation_fails_closed_for_missing_or_changed_numeric_placeholders(self):
        for messages in ({}, {'数值 {0} / {1}': 'Values {1} / {0}'},
                         {'数值 {0} / {1}': 'Values {0}'},
                         {'数值 {0} / {1}': 'Values {0} / {1} / {0}'},
                         {'数值 {0} / {1}': 'Values {0} / {1} / 99'},
                         {'数值 {0} / {1}': '未翻译 {0} / {1}'}):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                impact.EnglishReport(messages).translate('数值 1.233269 / 1.218361')
        translator = impact.EnglishReport({'数值 {0} / {1}': 'Values {0} / {1}'})
        self.assertEqual(translator.translate('数值 1.233269 / 1.218361'),
                         'Values 1.233269 / 1.218361')
        for message in ('Change -{0}%', 'Change +{0}', 'Change {0}%'):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, 'signs and percentages'):
                impact.EnglishReport({'变化 +{0}%': message}).translate('变化 +1.23%')

    def test_english_cli_catalogue_failure_never_writes_output(self):
        for messages in ({}, {'glibc 运行时内存回收｜影响报告': 'p99'}):
            with self.subTest(messages=messages), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)/'english.html'
                # Substitute only the real catalogue read. All rendering,
                # validation and CLI error/output handling remain real.
                code = ('from pathlib import Path\nfrom unittest.mock import patch\n'
                        'from tools.report import build_impact_report as b\n'
                        'read = Path.read_text\n'
                        f'catalogue = {json.dumps({"messages": messages})!r}\n'
                        'def edited(path, *a, **kw):\n'
                        '    return catalogue if path.name == "impact_en.json" else read(path, *a, **kw)\n'
                        'with patch.object(Path, "read_text", edited):\n    b.main()\n')
                for exists in (False, True):
                    if exists:
                        output.write_bytes(b'previous approved file')
                    run = subprocess.run([sys.executable, '-c', code, '--lang', 'en', '--output', str(output)],
                                         cwd=REPO, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    self.assertIn('FAIL impact report:', run.stderr)
                    self.assertNotIn('PASS', run.stdout)
                    if exists:
                        self.assertEqual(output.read_bytes(), b'previous approved file')
                    else:
                        self.assertFalse(output.exists())

    def test_rebuild_matches_submission_and_is_repeatable(self):
        one, two = impact.build(REPO), impact.build(REPO)
        self.assertEqual(one, two)
        self.assertEqual(one.encode(), REPORT.read_bytes())
        run = subprocess.run([sys.executable, str(BUILDER), '--check'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, 'PASS impact report: frozen inputs, numeric controls, byte-identical HTML\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copy.html'
            run = subprocess.run([sys.executable, str(BUILDER), '--output', str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(path.read_bytes(), REPORT.read_bytes())

    def test_no_external_resources_or_links_and_accessible_figures(self):
        text = REPORT.read_text()
        doc = Document(text)
        for tag in ('script', 'img', 'iframe', 'object', 'embed', 'link'):
            self.assertNotIn(tag, doc.tags)
        self.assertNotRegex(text.lower(), r'https?://|@import|url\(')
        for name, value in doc.attributes:
            if name in ('href', 'src'):
                self.assertFalse(value.startswith(('/', '//')) or ':' in value, value)
            self.assertFalse(name.startswith('on'), name)
        self.assertEqual(doc.tags.count('svg'), 4)
        self.assertEqual(len(re.findall(r'<svg[^>]*role="img"[^>]*aria-label="[^"]+"', text)), 4)
        for forbidden in ('评审', '人工智能', 'AI ', '其他团队', '竞品'):
            self.assertNotIn(forbidden, ''.join(doc.text))

    def test_links_are_only_in_page_and_numeric_blocks_need_no_extra_files(self):
        run = subprocess.run([sys.executable, str(REPO/'tools/reproduce/check_links.py'), str(REPORT)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        text = REPORT.read_text()
        doc = impact.ReportDocument(text)
        self.assertEqual(impact.check_single_file(text), len(doc.links))
        self.assertEqual(len(doc.links), 5)
        blocks = re.findall(r'<figure>.*?</figure>|<tr><td>.*?</tr>|<div class="card">.*?</div>', text, re.S)
        self.assertGreater(len(blocks), 10)
        for block in blocks:
            self.assertNotIn('href=', block)

    def test_single_html_in_empty_directory_has_working_navigation(self):
        text = REPORT.read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.html'
            report.write_text(text)
            with mock.patch.object(impact, 'snapshot', side_effect=AssertionError('reader has no repo')):
                self.assertEqual(impact.check_single_file(report.read_text()), 5)
            run = subprocess.run([sys.executable, str(REPO/'tools/reproduce/check_links.py'), str(report)],
                                 cwd=root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(list(root.iterdir()), [report])

    def test_every_file_link_is_rejected_even_if_publicly_delivered(self):
        cases = (
            '../README.md',
            '../data/raw/s4_retention_20260901/b_cycles.tsv',
            'demo_reproduction_guide_20260901.md#l1-s4',
            '../tools/report/build_impact_report.py',
            '../board_results/not-public.json',
            'https://example.invalid/report', '//example.invalid/report',
            'file:///tmp/report.html', 'mailto:reader@example.invalid',
            'data:text/html,hello', '%23summary', '?chapter=summary#summary',
            'javascript:alert(1)',
        )
        for link in cases:
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, 'only #anchor'):
                impact.check_single_file(f'<a href="{link}">link</a>')

    def test_fragment_targets_resources_and_plain_text_paths(self):
        for link in ('#absent', '', '#', '../../outside', '/etc/passwd'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                impact.check_single_file(f'<a href="{link}">link</a>')
        for snippet in ('<base href="https://example.invalid">',
                        '<svg><use xlink:href="picture.svg#plot"/></svg>',
                        '<img src="picture.svg">', '<script>alert(1)</script>',
                        '<meta http-equiv="refresh" content="0;url=elsewhere">',
                        '<style>body{background:url(picture.png)}</style>',
                        '<p>docs/report.html</p>', '<p>data/raw/source.tsv</p>',
                        '<p>/tmp/report.html</p>', '<p>../README.md</p>'):
            with self.subTest(snippet=snippet), self.assertRaises(ValueError):
                impact.check_single_file(snippet)
        self.assertEqual(impact.check_single_file('<section id="内存"></section><a href="#%E5%86%85%E5%AD%98">go</a>'), 1)

    def test_delivery_evidence_gate_remains_strict_without_reader_links(self):
        refs, _ = impact.load_evidence(REPO)
        impact.check_delivery_evidence(REPO, refs['sha256'])
        with self.assertRaisesRegex(ValueError, 'delivery evidence'):
            impact.check_delivery_evidence(REPO, {impact.SYSTEM+'cycles.tsv': '0'*64})

    def test_missing_snapshot_is_not_a_skip_and_explains_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tools/report').mkdir(parents=True)
            refs = json.loads((REPO/'tools/report/impact_delivery.json').read_text())
            refs['commit'] = '0'*40
            (root/'tools/report/impact_delivery.json').write_text(json.dumps(refs))
            with self.assertRaisesRegex(ValueError, 'git fetch --no-tags origin .*no checks were skipped'):
                impact.snapshot(root)

    def test_delivery_pin_and_source_hashes_resolve_to_frozen_bytes(self):
        refs, files = impact.snapshot(REPO)
        self.assertEqual(refs['commit'], '7289a47b9d24791944cd3b02c00f24b8cb76aa3b')
        self.assertEqual(refs['tag'], 'demo-v14')
        evidence, _ = impact.load_evidence(REPO)
        for relative, digest in evidence['sha256'].items():
            blob = impact.snapshot_blob(REPO, files['data/raw/' + relative])
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, relative)

    def test_keywords_rejected_in_body_captions_comments_and_metadata(self):
        samples = ('<p>AI</p>', '<p>人工智能</p>', '<p>模型</p>',
                   '<figcaption>多轮评审流程</figcaption>', '<!-- agent -->',
                   '<meta name="generator" content="OpenAI">',
                   '<meta name="generator" content="AI_generated">',
                   '<svg aria-label="AGENT"><title>plot</title></svg>',
                   '<p>ag&#101;nt</p>', '<p>A<span>I</span></p>',
                   '<!-- ＡＩ -->', '<p>ag\u200bent</p>',
                   '<p>p99</p>', '<meta name="description" content="P50">',
                   '<figcaption>p95 / percentile</figcaption>', '<!-- 极差 -->',
                   '<svg aria-label="离散"><title>plot</title></svg>',
                   '<p>百分位</p>', '<p>NOT-DETECTED</p>', '<p>判据 N1</p>',
                   '<p>中位数 / nearest-rank</p>', '<p>p<span>99</span></p>',
                   '<p>ＮＯＴ－ＤＥＴＥＣＴＥＤ</p>', '<p>p&#57;9</p>')
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaisesRegex(ValueError, 'forbidden report keyword'):
                impact.check_keywords(sample)
        impact.check_keywords('<main>RSS / available memory / domain</main>')
        impact.check_keywords(REPORT.read_text())

    def test_build_itself_fails_for_missing_links_and_forbidden_metadata(self):
        for addition, message in (('<a href="../README.md">link</a>', 'only #anchor'),
                                  ('<!-- agent -->', 'forbidden report keyword'),
                                  ('<meta content="p99">', 'forbidden report keyword')):
            with self.subTest(addition=addition), mock.patch.object(impact, 'costs_chart', return_value=addition):
                with self.assertRaisesRegex(ValueError, message):
                    impact.build(REPO)

    def test_cli_rejects_bad_output_without_writing_or_overwriting(self):
        for addition in ('<a href="../README.md">link</a>', '<!-- p99 -->', '<meta content="AI">'):
            with self.subTest(addition=addition), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)/'report.html'
                code = ('from unittest.mock import patch\n'
                        'from tools.report import build_impact_report as b\n'
                        f'with patch.object(b, "costs_chart", return_value={addition!r}):\n'
                        '    b.main()\n')
                for exists in (False, True):
                    if exists:
                        output.write_bytes(b'previous approved file')
                    run = subprocess.run([sys.executable, '-c', code, '--output', str(output)],
                                         cwd=REPO, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                    self.assertIn('FAIL impact report:', run.stderr)
                    self.assertNotIn('PASS', run.stdout)
                    if exists:
                        self.assertEqual(output.read_bytes(), b'previous approved file')
                    else:
                        self.assertFalse(output.exists())

    def test_plain_language_terms_and_first_use_definitions(self):
        doc = Document(REPORT.read_text())
        visible = ''.join(doc.text)
        self.assertNotRegex(visible, r'\bmixed\b|medium-only|\bG[1-4]\b|\bS4\b|B 组|A 锚点|T1[′\x27]|\bM7\b|反信号|滞留型|自回收型')
        # SVG captions, aria labels and metadata are reader-facing too.
        for name, value in doc.attributes:
            if name in ('aria-label', 'content', 'title'):
                self.assertNotRegex(value, r'\bG[1-4]\b|\bS4\b|\bM7\b|mixed|medium-only')
        for definition in ('混合尺寸分配负载反复申请不同大小的对象',
                           '中等尺寸为主的分配负载执行同样的过程',
                           '操作系统按页回收内存', '堆内 Private_Dirty',
                           '包含代码、栈、共享页及其他映射',
                           '但不调用 trim 的一组运行',
                           '同一条件下重复测量自身的波动范围'):
            self.assertIn(definition, visible)
        self.assertNotIn('#l1-impact-report', REPORT.read_text())

    def test_standalone_reading_needs_no_repository_and_has_plain_footer(self):
        text = ''.join(Document(REPORT.read_text()).text)
        for old in ('本方案不替换 libc、不改本次对照实验的二进制',
                    '干净 Git 克隆', '阅读副本', 'docs/', 'board_results',
                    'data/raw/', 'tools/', 'L1', 'REPRODUCE_ALLOW_DIRTY'):
            self.assertNotIn(old, text)
        self.assertIn('<footer>完整数据与复现包见内部交付仓库 glibc_optimization，标签 demo-v14。</footer>', REPORT.read_text())

    def test_frozen_input_change_is_rejected_without_changing_data(self):
        refs, _ = impact.load_evidence(REPO)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tools/report').mkdir(parents=True)
            (root/'tools/report/impact_sources.json').write_bytes((REPO/'tools/report/impact_sources.json').read_bytes())
            first = next(iter(refs['sha256']))
            path = root/'data/raw'/first
            path.parent.mkdir(parents=True)
            path.write_bytes((REPO/'data/raw'/first).read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'byte SHA-256'):
                impact.load_evidence(root)

    def test_independent_numeric_assertions_reject_scope_or_health_drift(self):
        _, original = impact.load_evidence(REPO)
        cases = [
            (impact.SYSTEM+'cycles.tsv', lambda x: next(r for r in x if r['group']=='G2' and r['arm']=='trim' and r['cycle']=='2').update(rss_drop_kib='0')),
            (impact.SYSTEM+'cycles.tsv', lambda x: next(r for r in x if r['group']=='G3' and r['arm']=='trim' and r['cycle']=='2').update(rss_drop_kib='0')),
            (impact.SYSTEM+'cycles.tsv', lambda x: next(r for r in x if r['group']=='G1' and r['arm']=='none').update(rss_drop_kib='1')),
            (impact.SYSTEM+'cycles.tsv', lambda x: next(r for r in x if r['group']=='G1' and r['arm']=='trim' and r['cycle']=='1').update(memavailable_net_kib='999999')),
            (impact.S4+'b_cycles.tsv', lambda x: x[0].update(trim_elapsed_ms='99')),
            (impact.S4+'b_cycles.tsv', lambda x: x[0].update(trim_reclaim_pct_of_released='99')),
            (impact.GST+'cycles.tsv', lambda x: x[0].update(cycle_majflt='0')),
            (impact.GST+'repetitions.tsv', lambda x: x[0].update(business_p50_ms='0')),
            (impact.GST+'health.json', lambda x: x.update(oom_lmk_matches=['OOM'])),
            (impact.NATIVE+'health.json', lambda x: x['enlightenment'].update(stable_across_completed_cells=False)),
            (impact.B2+'summary.json', lambda x: x['e4_prime'].update(reclaimed_kb=99)),
        ]
        for path, mutate in cases:
            with self.subTest(path=path, mutation=cases.index((path, mutate))):
                data = copy.deepcopy(original)
                mutate(data[path])
                with self.assertRaises(ValueError):
                    impact.controls(data)

    def test_important_limits_are_adjacent_not_hidden(self):
        text = ''.join(Document(REPORT.read_text()).text)
        for value in ('没有观察到下降不等于所有指标零影响', '不宣称性能提升', '1.870462', '0.173927',
                      '冷启动例外', '出现 4 次 major fault', '启动时间未做专项测量',
                      '不是整个系统风险为零', '管线进入 NULL 状态、停止并释放资源后', '不与释放点约 1 ms',
                      '不能证明变化一定存在或一定不存在', '不等于整机或产品收益', '碎片化可能',
                      '同一进程中其他尚未归还的内存仍须单独实测',
                      '居中的两轮里较快的一轮', '回收比例不是内存占用降幅',
                      '未做无害性根因证明', '四道硬门'):
            self.assertIn(value, text)
        self.assertNotIn('全部实验窗口为 0', text)
        self.assertNotIn('性能提升已证明', text)

    def test_cross_carrier_published_numbers_match(self):
        text = REPORT.read_text()
        carriers = {
            'docs/demo_report.html': ('13.015625', '7.718750', '40.696279', '45.322245',
                '45.177290', '16.038164', '13.282648', '21.043165', '9.394531', '8.136719', '2.816406',
                '1899.209517', '0.033659', '1.233269', '1.218361', '0.671556'),
            'docs/gst_trim_cost_20260901.md': ('6.228611', '6.784167', '0.555556', '91.8%',
                '1.870462', '0.173927', '0.818315', '0.842185', '0.856944', '+359'),
            'docs/demo_reproduction_guide_20260901.md': ('1.233269', '1.218361', '13.015625', '45.177290',
                '80.175875', '85.453954', '1351', '1465', '0.033659'),
        }
        for path, values in carriers.items():
            other = (REPO/path).read_text()
            for number in values:
                self.assertIn(number, text, ('impact', number))
                self.assertIn(number, other, (path, number))

    def test_plain_language_call_time_coverage_matches_the_same_rows(self):
        _, data = impact.load_evidence(REPO)
        calls = [float(r['trim_elapsed_ms']) for r in data[impact.GST+'cycles.tsv']
                 if r['arm'] == 'trim-at-loop-release']
        for percentage, limit in ((95, 0.818315), (99, 0.842185)):
            self.assertGreaterEqual(100 * sum(value <= limit for value in calls), percentage * len(calls))
            self.assertIn(f'{percentage}% 不超过 {limit:.6f}',
                          REPORT.read_text().replace(' 的调用不超过', ' 不超过'))
        self.assertEqual(max(calls), 0.856944)

    def test_default_verify_discovers_impact_suite_without_entrypoint_changes(self):
        parent = (REPO/'tools/report/test_build_demo_report.py').read_text()
        self.assertIn('from tools.report.test_build_impact_report import ImpactReportTests', parent)
        entry = (REPO/'tools/reproduce/reproduce.sh').read_text()
        self.assertIn('tools/report/test_build_demo_report.py', entry)

    def test_l1_supplement_runs_and_matches_documented_output(self):
        guide = (REPO/'docs/demo_reproduction_guide_20260901.md').read_text()
        section = guide.split('<a id="l1-impact-report"></a>')[1].split('<a id="l1-servicea"></a>')[0]
        code = re.search(r"python3 - <<'PY'\n(.*?)\nPY", section, re.S).group(1)
        expected = re.findall(r'```text\n(.*?)\n```', section, re.S)[-1] + '\n'
        run = subprocess.run([sys.executable, '-c', code], cwd=REPO, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, expected)


if __name__ == '__main__':
    unittest.main()
