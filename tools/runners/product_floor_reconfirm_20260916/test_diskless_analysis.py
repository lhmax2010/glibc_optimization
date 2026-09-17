import copy
import unittest
import analyze_diskless as analysis
import test_host


class DisklessAnalysisTests(unittest.TestCase):
    def analyze(self, rows):
        return analysis.analyze(rows, expected_targets={'example'})

    def rows(self, period=1):
        rows = test_host.AnalysisTests().rows()[::period]
        for i, r in enumerate(rows):
            r.update(sample=i, monotonic_ns=r['epoch_ns'], read_end_ns=r['epoch_ns']+1000000,
                     compact_smaps=0, globals_start_ns=r['epoch_ns'], globals_end_ns=r['epoch_ns']+2000000)
        return rows

    def test_one_and_two_seconds_same_classifier(self):
        for period in (1, 2):
            r = self.analyze(self.rows(period))[0]
            self.assertEqual(r['elapsed_s'], 600)
            self.assertEqual(r['classification'], 'c-byte-exact-no-response')
            self.assertEqual(r['actual_interval_ms']['median'], period*1000)

    def test_actual_minute_not_last_sixty_points(self):
        rows = self.rows(2)
        for r in rows:
            if r['monotonic_ns'] > 530e9:
                r.update(glibc_heap_pd_kb=2000, total_pd_kb=2110)
        r = self.analyze(rows)[0]
        self.assertEqual(r['floor_change_kib'], 1000)
        self.assertEqual(r['classification'], 'b-retention')

    def test_stop_conditions(self):
        mutations = (lambda r: r.pop(), lambda r: r[9].update(start_ticks=99),
                     lambda r: r[9].update(total_pd_kb=0), lambda r: r[9].update(minflt=0),
                     lambda r: r[9].update(monotonic_ns=0), lambda r: r[9].update(compact_smaps=2),
                     lambda r: r[9].update(read_end_ns=0), lambda r: r[9].update(sample=0))
        for mutate in mutations:
            rows = self.rows()
            mutate(rows)
            with self.assertRaises(ValueError):
                self.analyze(rows)
        with self.assertRaises(ValueError):
            self.analyze([])
        rows = self.rows()
        second = copy.deepcopy(rows[:-1])
        for r in second:
            r['target'] = 'second'
        with self.assertRaises(ValueError):
            self.analyze(rows+second)

    def test_compact_disclosure_and_fault_audit(self):
        rows = self.rows()
        for r in rows[300:]:
            r.update(compact_smaps=1, majflt=1, zram_orig_bytes=4096)
        result = self.analyze(rows)[0]
        self.assertEqual(result['compact_smaps_samples'], 301)
        self.assertEqual(result['window_majflt_delta'], 1)
        self.assertEqual(result['zram_positive_steps'], 1)

    def test_missing_candidate_or_required_global_fields(self):
        with self.assertRaisesRegex(ValueError, 'roster'):
            analysis.analyze(self.rows(), {'example', 'missing'})
        for field in analysis.GLOBALS:
            rows = self.rows()
            for row in rows:
                row.pop(field)
            with self.assertRaises(ValueError):
                self.analyze(rows)
        rows = self.rows()
        for row in rows:
            row.update(globals_start_ns=0, globals_end_ns=1)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.analyze(rows)

    def test_historical_labels_exact_for_fall_dual_and_confounded(self):
        for final, zram in ((500, 0), (2000, 0), (500, 4096)):
            rows = self.rows()
            for i, r in enumerate(rows):
                heap = 1000 if i < 100 else 3000 if i < 200 else final
                r.update(glibc_heap_pd_kb=heap, total_pd_kb=heap+110,
                         zram_orig_bytes=zram if i >= 200 else 0)
            expected = analysis.historical.release_ratio_census(rows, {})[0]
            actual = self.analyze(rows)[0]
            self.assertTrue(all(actual[k] == v for k, v in expected.items()))

    def test_timing_transition_and_batch_proof(self):
        rows = self.rows()
        timing = dict(transition=None, batches=[dict(sample=i, start_ns=i*10**9,
                     end_ns=i*10**9+3000000, target_period_s=1) for i in range(601)])
        analysis.validate_timing(rows, timing)
        for mutation in (lambda t: t['batches'][2].update(target_period_s=2),
                         lambda t: t['batches'][2].update(end_ns=2*10**9+1),
                         lambda t: t.update(transition={'after_sample': 10})):
            changed = copy.deepcopy(timing)
            mutation(changed)
            with self.assertRaises(ValueError):
                analysis.validate_timing(rows, changed)
