import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

import run_diskless as r
import test_host


class DisklessDriverTests(unittest.TestCase):
    def test_readonly_allowlist_and_hard_200_bytes(self):
        for argv in (['cat', '/proc/4194304/smaps'], ['awk', r.FILTER, '/proc/4194304/smaps'],
                     ['cat', '/proc/123/status'], ['command', '-v', 'awk']):
            self.assertLessEqual(len(r.readonly_body(argv).encode()), 200)
        for argv in (['rm', '/tmp/x'], ['sh', '/tmp/x'], ['kill', '123'], ['reboot'],
                     ['awk', 'BEGIN{system("x")}', '/proc/123/smaps'], ['cat', '/proc/12/../x']):
            with self.assertRaises(ValueError):
                r.readonly_body(argv)
        with tempfile.TemporaryDirectory() as tmp:
            board = r.Board('127.0.0.1', Path(tmp))
            with patch.object(r.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    board.call('long', ['-s', board.serial, 'shell', 'x'*201], True)
                with self.assertRaises(ValueError):
                    board.call('push', ['push', 'x', '/tmp/x'])
                for body in ('LC_ALL=C rm /tmp/x'+r.old.single.SUFFIX,
                             'LC_ALL=C cat /proc/1/stat | sh'+r.old.single.SUFFIX,
                             'id'):
                    with self.assertRaises(ValueError):
                        board.call('unsafe',['-s',board.serial,'shell',body],True)
                run.assert_not_called()

    def test_timeout_only_full_smaps_fallback_and_remote_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = r.Board('127.0.0.1', Path(tmp))
            with patch.object(r.subprocess, 'run', side_effect=subprocess.TimeoutExpired('sdb',20)):
                with self.assertRaises(r.SmapsTimeout):
                    board.read('full', ['cat','/proc/123/smaps'])
                self.assertFalse(board.stopped.is_set())
                with self.assertRaises(ValueError):
                    board.read('compact', ['awk',r.FILTER,'/proc/123/smaps'])
                self.assertTrue(board.stopped.is_set())
            self.assertEqual(len((Path(tmp)/'commands.jsonl').read_text().splitlines()), 2)
        for raw in (b'RC=1\nFAIL\n', b'no proof', b'RC=0\nFAIL\n'):
            with tempfile.TemporaryDirectory() as tmp:
                board = r.Board('127.0.0.1', Path(tmp))
                with patch.object(r.subprocess, 'run', return_value=Mock(stdout=raw,returncode=0)):
                    with self.assertRaises(ValueError):
                        board.read('bad',['cat','/proc/123/stat'])
                self.assertTrue(board.stopped.is_set())

    def test_filter_reuses_identical_pd_parser(self):
        text = ('00100000-00110000 rw-p 00000000 00:00 0\nSize: 64 kB\nPrivate_Dirty: 12 kB\n'
                '00201000-00210000 rw-p 00000000 00:00 0 [heap]\nPrivate_Dirty: 8 kB\n'
                '00301000-00310000 rw-p 00000000 00:00 0\nPrivate_Dirty: 4 kB\n'
                '00401000-00410000 r--p 00000000 00:00 1 /lib/file\nPrivate_Dirty: 2 kB\n')
        import shutil
        if not shutil.which('awk'):
            self.skipTest('awk unavailable; compact transport equivalence requires host awk')
        filtered = subprocess.check_output(['awk',r.FILTER],input=text.encode()).decode()
        self.assertEqual(r.smaps(text),r.smaps(filtered))
        self.assertNotIn('Size:',filtered)

    def test_cadence_boundary_no_revert(self):
        for interval, expected in ((1.5,1),(1.500001,2)):
            clock=r.Cadence()
            for i in range(11):
                clock.complete(round(i*interval*1e9))
            self.assertEqual(clock.period,expected)
            for i in range(11,30):
                clock.complete(round((10*interval+(i-10))*1e9))
            self.assertEqual(clock.period,expected)

    def test_root_restore_on_all_failures_and_no_push(self):
        for fail in ('identity_pre','before','on','identity_root','baseline','candidates','observe',None):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp:
                board=Mock(output=Path(tmp),phase='pre')
                identity=dict(kernel='6.12.60',arch='armv7l',os_release='Tizen TV')
                board.identity.side_effect = [ValueError('pre')] if fail=='identity_pre' else [identity,ValueError('root')] if fail=='identity_root' else [identity,identity]
                def switch(board, mode):
                    if mode=='on' and fail=='on':raise ValueError('root on failed')
                with patch.object(r.authorized,'identity_uid',return_value='uid=5001(owner)',side_effect=ValueError('before') if fail=='before' else None), \
                     patch.object(r,'switch_root',side_effect=switch) as switches, \
                     patch.object(r,'baseline',side_effect=ValueError('baseline') if fail=='baseline' else None), \
                     patch.object(r,'confirm_candidates',side_effect=ValueError('candidates') if fail=='candidates' else None), \
                     patch.object(r,'observe',side_effect=ValueError('observe') if fail=='observe' else None):
                    state={}
                    rc=r.execute(board,{},state)
                    self.assertEqual(rc,0 if fail is None else 2)
                    if fail not in ('identity_pre','before'):
                        self.assertEqual(switches.call_args_list[-1].args[1],'off')
                        self.assertEqual(state['root_off_verified_uid'],5001)
                    else:
                        switches.assert_not_called()
                board.call.assert_not_called()

    def test_restore_failure_never_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            board=Mock(output=Path(tmp))
            identity=dict(kernel='x',arch='armv7l',os_release='Tizen TV')
            board.identity.return_value=identity
            with patch.object(r.authorized,'identity_uid',return_value='uid=5001(owner)'), patch.object(r,'switch_root',side_effect=[None,ValueError('off failed')]) as switch, \
                 patch.object(r,'baseline'),patch.object(r,'confirm_candidates'),patch.object(r,'observe'):
                state={}
                self.assertEqual(r.execute(board,{},state),2)
                self.assertIn('root_off_error',state)
                self.assertEqual(switch.call_count,2)

    def test_root_uid_requires_remote_evidence(self):
        board=Mock()
        for raw in ('uid=5001(owner)','uid=0(root)','garbage'):
            board.call.return_value=(0,raw)
            if raw.startswith('uid=5001('):
                self.assertEqual(r.authorized.identity_uid(board,'id',5001),raw)
            else:
                with self.assertRaises(ValueError):
                    r.authorized.identity_uid(board,'id',5001)

    def test_transition_error_still_queries_uid(self):
        board=Mock()
        for mode in ('on','off'):
            board.call.side_effect=ValueError('transport failed')
            with patch.object(r.time,'sleep'),patch.object(r.authorized,'identity_uid',return_value='id') as proof:
                with self.assertRaisesRegex(ValueError,'transport'):
                    r.switch_root(board,mode)
                proof.assert_called_once_with(board,'id_after_root_'+mode,0 if mode=='on' else 5001)

    def test_process_identity_and_single_compact_transition(self):
        tail=['S']+[str(i) for i in range(1,25)]
        stat='123 (example) '+' '.join(tail)
        maps='00100000-00110000 rw-p 00000000 00:00 0\nPrivate_Dirty: 12 kB\n'
        board=Mock(records={'root_s0_p123_compact':dict(started_ns=1,monotonic_start_ns=2,monotonic_end_ns=3)})
        board.read.side_effect=[(0,stat),r.SmapsTimeout('slow'),(0,maps),(0,stat)]
        compact={}
        row=r.process_sample(board,dict(pid=123,comm='example',start_ticks=19,target='x'),0,compact)
        self.assertEqual(row['compact_smaps'],1)
        self.assertTrue(compact[123])
        board.read.side_effect=[(0,stat),(0,maps),(0,stat.replace('(example)','(new)'))]
        with self.assertRaisesRegex(ValueError,'process changed'):
            r.process_sample(board,dict(pid=123,comm='example',start_ticks=19,target='x'),0,compact)

    def test_no_implicit_authorization_cli(self):
        run=subprocess.run([sys.executable,str(r.HERE/'run_diskless.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0)
        self.assertIn('--pm-authorized-readonly-root',run.stdout)

    def test_candidate_unchanged_restart_and_ambiguity(self):
        def stat(pid,comm='example',start=19):
            tail=['S']+[str(i) for i in range(1,25)];tail[19]=str(start)
            return str(pid)+' ('+comm+') '+' '.join(tail)
        base={'proc_uptime':(0,'1000.0 10.0'),'clk_tck':(0,'100')}
        snapshot={'selected':[dict(pid=123,comm='example',start_ticks=19,target='target')]}
        for shape in ('same','restart','ambiguous','denied'):
            with self.subTest(shape=shape),tempfile.TemporaryDirectory() as tmp:
                board=Mock(output=Path(tmp))
                if shape=='same':board.read.side_effect=[(0,stat(123)),(0,'status'),(0,'1000.0 10.0')]
                elif shape=='denied':board.read.side_effect=[(1,'cat: Permission denied')]
                else:
                    listing='root 1 0\nroot 456 0'+('\nroot 457 0' if shape=='ambiguous' else '')
                    board.read.side_effect=[(1,'cat: /proc/123/stat: No such file or directory'),(0,listing),
                                           (0,stat(1,'system')),(0,stat(456,start=22)),
                                           (0,stat(457,start=23)) if shape=='ambiguous' else (0,'status'),(0,'1000.0 10.0')]
                if shape in ('denied','ambiguous'):
                    with self.assertRaises(ValueError):r.confirm_candidates(board,snapshot,base)
                else:
                    selected=r.confirm_candidates(board,snapshot,base)
                    self.assertEqual(selected[0]['pid'],123 if shape=='same' else 456)
                    self.assertEqual(bool(json.loads((Path(tmp)/'candidates.json').read_text())['changes']),shape=='restart')

    def test_observe_full_duration_with_actual_slow_batches(self):
        import concurrent.futures
        import threading
        class Clock:
            ns=1000000000
            def monotonic_ns(self):return self.ns
            def sleep(self,s):self.ns+=round(s*1e9)
        class Pool:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def submit(self,func,*args):
                future=concurrent.futures.Future()
                try:future.set_result(func(*args))
                except BaseException as error:future.set_exception(error)
                return future
        clock=Clock()
        selected=json.loads(r.SNAPSHOT.read_text())['selected']
        def sample(board,candidate,index,compact):
            return dict(sample=index,epoch_ns=clock.ns,monotonic_ns=clock.ns,read_end_ns=clock.ns+1000000,
                        target=candidate['target'],pid=candidate['pid'],start_ticks=candidate['start_ticks'],
                        glibc_heap_pd_kb=1000,other_anon_pd_kb=100,file_backed_pd_kb=10,total_pd_kb=1110,
                        minflt=index,majflt=0,compact_smaps=0)
        def globals_sample(board,index):
            values=dict(MemAvailable_kb=10000,zram_used_kb=0,zram_orig_bytes=0,zram_compr_bytes=0,
                        zram_mem_used_bytes=0,globals_start_ns=clock.ns,globals_end_ns=clock.ns+2000000)
            clock.ns+=3000000000
            return values
        with tempfile.TemporaryDirectory() as tmp:
            board=Mock(output=Path(tmp),stopped=threading.Event())
            with patch.object(r,'time',clock),patch.object(r.concurrent.futures,'ThreadPoolExecutor',Pool), \
                 patch.object(r,'process_sample',side_effect=sample),patch.object(r,'globals_sample',side_effect=globals_sample):
                r.observe(board,selected)
            timing=json.loads((Path(tmp)/'sampling_timing.json').read_text())
            self.assertEqual(timing['transition']['after_sample'],10)
            self.assertEqual(timing['transition']['median_previous_10_intervals_s'],3)
            summary=json.loads((Path(tmp)/'summary.json').read_text())
            self.assertEqual(len(summary),11)
            self.assertTrue(all(s['elapsed_s']==600 for s in summary))


import sys
