#!/usr/bin/env python3
"""Offline impact report: frozen evidence, scope, links and exact rebuild.

Imported by test_build_demo_report so the unchanged verify entrypoint runs this
suite too. No extra executables beyond its existing Python/git environment.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from tools.report import build_impact_report as impact

REPO = Path(__file__).resolve().parents[2]
REPORT = REPO / 'docs/glibc_memopt_impact_report.html'
BUILDER = REPO / 'tools/report/build_impact_report.py'


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.attributes = []
        self.tags = []
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


class ImpactReportTests(unittest.TestCase):
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

    def test_links_and_numeric_blocks_have_raw_and_l1_sources(self):
        run = subprocess.run([sys.executable, str(REPO/'tools/reproduce/check_links.py'), str(REPORT)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        text = REPORT.read_text()
        blocks = re.findall(r'<figure>.*?</figure>|<tr><td>.*?</tr>|<div class="card">.*?</div>', text, re.S)
        self.assertGreater(len(blocks), 10)
        for block in blocks:
            self.assertIn('href="../data/raw/', block)
            self.assertRegex(block, r'demo_reproduction_guide_20260901.md#l1-[^"]+')

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
        for value in ('未检出性能劣化', '不宣称性能提升', '1.870462', '0.173927',
                      '冷启动例外', '出现 4 次 major fault', '启动时间未做专项测量',
                      '不是整个系统风险为零', 'NULL release 后', '不与释放点约 1 ms',
                      '不是统计显著性检验', '不等于整机或产品收益', '碎片化可能',
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
