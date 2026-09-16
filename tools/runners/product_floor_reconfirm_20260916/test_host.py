import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('floor_analysis', HERE/'analyze_floor.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def rows(self):
        return [dict(sample=i, epoch_ns=i*1000000000, target='example', pid=10, start_ticks=20,
                     glibc_heap_pd_kb=1000, other_anon_pd_kb=100, file_backed_pd_kb=10, total_pd_kb=1110,
                     minflt=i, majflt=0, MemAvailable_kb=10000, zram_used_kb=0,
                     zram_orig_bytes=0, zram_compr_bytes=0, zram_mem_used_bytes=0) for i in range(601)]

    def test_exact_constant_and_floor(self):
        result = analysis.analyze(self.rows())[0]
        self.assertEqual(result['classification'], 'c-byte-exact-no-response')
        self.assertEqual(result['absolute_floor_kib'], 1000)
        self.assertEqual(result['floor_change_kib'], 0)
        self.assertEqual(result['elapsed_s'], 600)

    def test_incomplete_restart_bucket_and_counter_fail(self):
        for change in (lambda x: x.pop(), lambda x: x[9].update(start_ticks=21),
                       lambda x: x[9].update(total_pd_kb=2), lambda x: x[9].update(minflt=0)):
            rows = self.rows()
            change(rows)
            with self.assertRaises(ValueError):
                analysis.analyze(rows)

    def test_historical_classification_is_reused(self):
        rows = self.rows()
        for row in rows[300:]:
            row['glibc_heap_pd_kb'] = 2000
            row['total_pd_kb'] = 2110
        result = analysis.analyze(rows)[0]
        self.assertEqual(result['classification'], 'b-retention')
        self.assertEqual(result['floor_change_kib'], 1000)

    def test_smaps_historical_mapping_classes(self):
        text = ('00100000-00110000 rw-p 00000000 00:00 0\nPrivate_Dirty: 12 kB\n'
                '00201000-00210000 rw-p 00000000 00:00 0 [heap]\nPrivate_Dirty: 8 kB\n'
                '00301000-00310000 rw-p 00000000 00:00 0\nPrivate_Dirty: 4 kB\n'
                '00401000-00410000 r--p 00000000 00:00 1 /lib/file\nPrivate_Dirty: 2 kB\n')
        self.assertEqual(analysis.smaps(text), dict(glibc_heap_pd_kb=20, other_anon_pd_kb=4,
                                                file_backed_pd_kb=2, total_pd_kb=26))
        for invalid in ('', 'Private_Dirty: 1 kB', text.replace('Private_Dirty: 12 kB', '')):
            with self.assertRaises(ValueError):
                analysis.smaps(invalid)

    def test_stat_parentheses_and_start_identity(self):
        tail = ['S'] + [str(i) for i in range(1, 25)]
        value = analysis.proc_stat('10 (name ) with spaces) '+' '.join(tail))
        self.assertEqual(value['comm'], 'name ) with spaces')
        self.assertEqual((value['minflt'], value['majflt'], value['start_ticks']), (7, 9, 19))


if __name__ == '__main__':
    unittest.main()
