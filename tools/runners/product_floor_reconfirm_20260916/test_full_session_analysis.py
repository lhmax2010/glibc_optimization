import copy
import unittest

import analyze_full_session as a
from test_persistent_analysis import batch, parse, CANDIDATE


def fixture():
    row=parse(batch()).rows[0]
    rows=[]; batches=[]
    for i in range(601):
        r=copy.deepcopy(row); r['sample']=i
        for key in ('epoch_ns','board_end_ns','host_epoch_ns','host_monotonic_ns','host_end_monotonic_ns','globals_start_ns','globals_end_ns'):
            r[key]+=i*1_000_000_000
        rows.append(r)
        batches.append(dict(sample=i,board_epoch_ns=r['globals_start_ns']-1,
                            host_monotonic_ns=r['host_monotonic_ns']-1,board_end_ns=r['board_end_ns']+1,
                            **{k:r[k] for k in ('MemAvailable_kb','zram_used_kb','zram_orig_bytes','zram_compr_bytes','zram_mem_used_bytes')}))
    return rows,[CANDIDATE],batches,[]


class FullAnalysisTests(unittest.TestCase):
    def test_dynamic_top10_primary_union(self):
        inv=[dict(status='READABLE',pid=i,comm='p'+str(i),glibc_heap_pd_kb=i*4) for i in range(1,15)]
        cs=a.select_candidates(inv,{'ServiceA':'p1','ServiceH':'p2','enlightenment':'p14'},13)
        self.assertEqual(len(cs),12)
        self.assertEqual({c['pid'] for c in cs},{1,2,4,5,6,7,8,9,10,11,12,14})
        self.assertEqual(next(c for c in cs if c['pid']==14)['top10_rank'],1)
        with self.assertRaisesRegex(ValueError,'ten'):a.select_candidates(inv[:4],{},99)
        with self.assertRaisesRegex(ValueError,'duplicate'):a.select_candidates(inv+[inv[0]],{},99)

    def test_complete_and_dropouts(self):
        x=fixture(); r=a.analyze(*x)
        self.assertEqual(r['actual_points'],601)
        self.assertTrue(r['targets'][0]['complete'])
        for n in (0,1,200):
            rows,cs,bs,_=fixture()
            out=a.analyze(rows[:n],cs,bs,[dict(target='example',sample=n,reason='MISSING')])
            self.assertFalse(out['targets'][0]['complete'])
            self.assertEqual(out['targets'][0]['points'],n)

    def test_bad_rows_and_events_fail_closed(self):
        for key,value in [('pid',9),('total_pd_kb',99),('majflt',0),('MemAvailable_kb',0),('globals_end_ns',10**30)]:
            x=fixture();x[0][-1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):a.analyze(*x)
        x=fixture()
        with self.assertRaisesRegex(ValueError,'600'):a.analyze(x[0][:-1],x[1],x[2][:-1],[])
        with self.assertRaisesRegex(ValueError,'samples'):a.analyze(x[0][1:],x[1],x[2],[])
        with self.assertRaisesRegex(ValueError,'unknown'):a.analyze(*x[:3],[dict(target='bogus',sample=1,reason='MISSING')])


if __name__=='__main__':unittest.main()
