import copy
import unittest

import analyze_persistent as a

NONCE = 'a'*32
CANDIDATE = dict(target='example', pid=123, start_ticks=19, comm='example')


def batch(index=0):
    stamp = 1_800_000_000_000_000_000+index*1_000_000_000
    lines = [f'===SAMPLE {NONCE} {index} {stamp}===']
    tail = ['S']+[str(i) for i in range(1,25)]
    sections = [('mem',0,'MemAvailable: 100 kB'), ('zram',0,'0 0 0 0 0'),
                ('swaps',0,'Filename Type Size Used Priority\n/dev/zram0 partition 100 0 -1'),
                ('before',123,'123 (example) '+' '.join(tail)),
                ('smaps',123,'00100000-00110000 rw-p 00000000 00:00 0\nPrivate_Dirty: 12 kB'),
                ('after',123,'123 (example) '+' '.join(tail))]
    for kind,pid,value in sections:
        stamp += 1000
        lines += [f'===READ {NONCE} {kind} {pid} {stamp}===',value,f'===RC {NONCE} 0 DONE {stamp+500}===']
    return '\n'.join(lines+[f'===END {NONCE} {index} {stamp+1000} RC=0 DONE==='])+'\n'


def parse(text):
    parser = a.Parser(NONCE,[CANDIDATE])
    for i,line in enumerate((f'===SESSION {NONCE} 2===\n'+text).splitlines()):
        parser.feed(line, 1_800_000_000_000_000_000+i, 10_000_000_000+i)
    return parser


class PersistentAnalysisTests(unittest.TestCase):
    def test_framing_and_fields(self):
        p = parse(batch()+f'===FINAL {NONCE} RC=0 DONE===\n')
        self.assertTrue(p.final)
        self.assertEqual(len(p.rows),1)
        self.assertEqual(p.rows[0]['glibc_heap_pd_kb'],12)
        self.assertEqual(set(p.rows[0]),set(a.FIELDS))
        self.assertFalse(a.covered(p.rows,[CANDIDATE]))

    def test_partial_not_committed(self):
        p = parse(batch().split('===END')[0])
        self.assertEqual(p.rows,[])
        self.assertFalse(p.final)

    def test_bad_frame_read_identity_and_globals(self):
        for old,new in [('0 DONE','1 FAIL'), ('(example)','(changed)'),
                        ('Private_Dirty: 12','Private_Dirty: bad'), ('MemAvailable:', 'Absent:'),
                        ('READ '+NONCE+' smaps', 'READ '+NONCE+' after'),
                        ('RC=0 DONE','RC=1 FAIL'), ('/dev/zram0','/dev/other')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse(batch().replace(old,new))

    def test_nonce_mismatch_and_duplicate_end(self):
        for text in (batch().replace(NONCE,'b'*32), batch()+batch()):
            with self.assertRaises(ValueError):parse(text)

    def test_coverage_classifier_and_timing(self):
        row = parse(batch()).rows[0]
        rows=[]
        for i in range(601):
            r=copy.deepcopy(row);r['sample']=i
            for k in ('epoch_ns','board_end_ns','host_epoch_ns','host_monotonic_ns',
                      'host_end_monotonic_ns','globals_start_ns','globals_end_ns'):
                r[k]+=i*1_000_000_000
            rows.append(r)
        result=a.analyze(rows,[CANDIDATE],{'example'})[0]
        self.assertEqual(result['absolute_floor_kib'],12)
        self.assertEqual(result['board_interval_ms']['median'],1000)
        self.assertEqual(result['board_elapsed_s'],600)
        with self.assertRaisesRegex(ValueError,'600-second'):
            a.analyze(rows[:-1],[CANDIDATE],{'example'})
        with self.assertRaisesRegex(ValueError,'roster'):
            a.analyze(rows,[CANDIDATE])
        broken=copy.deepcopy(rows)
        broken[-1]['globals_start_ns']=broken[-2]['globals_start_ns']
        broken[-1]['globals_end_ns']=broken[-2]['globals_end_ns']
        with self.assertRaisesRegex(ValueError,'stale'):
            a.analyze(broken,[CANDIDATE],{'example'})
        rows[-1]['minflt']=0
        with self.assertRaisesRegex(ValueError,'regression'):
            a.analyze(rows,[CANDIDATE],{'example'})


if __name__=='__main__':unittest.main()
