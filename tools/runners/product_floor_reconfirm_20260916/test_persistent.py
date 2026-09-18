import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import run_persistent as r
from test_persistent_analysis import batch, CANDIDATE, NONCE


class PersistentDriverTests(unittest.TestCase):
    def test_allowlist_size_and_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            board=r.Board('127.0.0.1',Path(tmp))
            with patch.object(r.subprocess,'run') as run:
                for args in (['push','x','/tmp/x'],['reboot'],['-s',board.serial,'shell','x'*201],
                             ['-s',board.serial,'shell','LC_ALL=C rm /tmp/x'+r.old.single.SUFFIX]):
                    with self.assertRaises(ValueError):board.call('bad',args,'shell' in args)
                run.assert_not_called()
        for candidates in ([dict(pid='1;reboot')],[dict(pid=-1)]):
            with self.assertRaises(ValueError):r.program(NONCE,candidates)
        text=r.program(NONCE,[CANDIDATE])
        self.assertLessEqual(max(len(s.encode()) for s in text.splitlines()),200)
        for forbidden in ('timeout ', 'rm ', 'kill ', 'reboot', ' >', 'tee ', 'push ', 'attach'):
            self.assertNotIn(forbidden,text)
        result=subprocess.run([sys.executable,str(r.HERE/'run_persistent.py'),'--help'],capture_output=True,text=True)
        self.assertIn('--pm-authorized-readonly-root',result.stdout)

    def test_connectivity_exactly_one_reset_no_sampling_retry(self):
        board=Mock(serial='127.0.0.1:26101',address='127.0.0.1')
        def call(label,args,*unused):
            if label.startswith('selfcheck'):raise ValueError('server down')
            return 0,'serial device'
        board.call.side_effect=call
        with self.assertRaises(ValueError):r.connectivity(board)
        labels=[c.args[0] for c in board.call.call_args_list]
        self.assertEqual(labels.count('reset_kill_server'),1)
        self.assertEqual(labels.count('reset_start_server'),1)
        self.assertEqual(labels.count('selfcheck_0'),1)
        self.assertEqual(labels.count('selfcheck_1'),1)
        board.call.reset_mock()
        board.call.side_effect=lambda label,*args:(0,'uid=5001(owner)' if label.startswith('selfcheck') else board.serial+' device')
        r.connectivity(board)
        self.assertNotIn('reset_kill_server',[c.args[0] for c in board.call.call_args_list])

    def test_receiver_success_and_protocol_failures(self):
        good=f'===SESSION {NONCE} 2===\n'+batch()+f'===FINAL {NONCE} RC=0 DONE===\n'
        cases=[(good,None), (good.replace('0 DONE','1 FAIL'),'remote read'),
               (good.split('===END')[0],'DISCONNECT'), (good.rsplit('===FINAL',1)[0],'DISCONNECT')]
        for raw,error in cases:
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp:
                # Fake transport consumes input, emits one sample, waits for ACK,
                # then sends FINAL. No SDB, board, or optional packages involved.
                code='import sys; sys.stdin.readline(); print('+repr(raw.split('===FINAL')[0])+',end="",flush=True); '
                if '===FINAL' in raw:
                    code+='sys.stdin.readline(); print('+repr('===FINAL'+raw.split('===FINAL')[1])+',end="",flush=True)'
                with patch.object(r,'covered',return_value=True),patch.object(r,'analyze',return_value=[]):
                    if error:
                        with self.assertRaisesRegex(ValueError,error):
                            r.receive([sys.executable,'-c',code],'start\n',NONCE,[CANDIDATE],Path(tmp),0.5)
                    else:
                        r.receive([sys.executable,'-c',code],'start\n',NONCE,[CANDIDATE],Path(tmp),0.5)
                        self.assertEqual(json.loads((Path(tmp)/'stream_state.json').read_text())['status'],'COMPLETE')

    def test_silence_stops_no_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            started=time.monotonic()
            with self.assertRaisesRegex(ValueError,'SILENCE'):
                r.receive([sys.executable,'-c','import sys;sys.stdin.readline();sys.stdin.read()'],
                          'start\n',NONCE,[CANDIDATE],Path(tmp),0.05)
            state=json.loads((Path(tmp)/'stream_state.json').read_text())
            self.assertEqual(state['complete_batches'],0)
            self.assertFalse(state['final_proven'])
            self.assertLess(time.monotonic()-started,5)

    def test_actual_posix_shell_stdin_ack_eof_and_end(self):
        if not shutil.which('awk') or not shutil.which('sh'):
            self.skipTest('host sh and awk required for real stdin protocol test')
        current=r.prior.proc_stat(Path('/proc/self/stat').read_text())
        current['target']='self'
        # Only test global-read payloads are substituted; PID reads, shell
        # program, ACK parser and final-return logic execute in the real sh.
        text=r.program(NONCE,[current])
        text=text.replace('item mem 0 cat /proc/meminfo','item mem 0 printf "MemAvailable: 100 kB\\n"')
        text=text.replace('item zram 0 cat /sys/block/zram0/mm_stat','item zram 0 printf "0 0 0\\n"')
        text=text.replace('item swaps 0 cat /proc/swaps',
                          'item swaps 0 printf "Filename Type Size Used Priority\\n/dev/zram0 partition 100 0 -1\\n"')
        for ack,expected in ((None,73),('END',74),('CONTINUE',73)):
            proc=subprocess.Popen(['/bin/sh'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
            try:
                proc.stdin.write(text.encode());proc.stdin.flush()
                received=b''; deadline=time.monotonic()+5
                while b'===END '+NONCE.encode() not in received:
                    self.assertTrue(selector.select(max(0,deadline-time.monotonic())),received.decode())
                    received+=os.read(proc.stdout.fileno(),65536)
                if ack:
                    proc.stdin.write((ack+'\n').encode());proc.stdin.flush()
                proc.stdin.close()
                rest=proc.stdout.read();received+=rest
                self.assertEqual(proc.wait(timeout=5),expected,received.decode())
                self.assertIn(f'===FINAL {NONCE} RC={expected} FAIL===',received.decode())
                self.assertEqual(received.count(b'===SAMPLE'),2 if ack=='CONTINUE' else 1)
            finally:
                if not proc.stdin.closed:proc.stdin.close()
                if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
                selector.close();proc.stdout.close()

    def test_root_off_on_each_failure_no_board_writes(self):
        for fail in ('connectivity','before','on','identity','baseline','candidates','stream','tmp_after',None):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp);(out/'stream_state.json').write_text(json.dumps(dict(observer_pid=123)))
                board=Mock(output=out,serial='127.0.0.1:26101',sdb='sdb')
                identity=dict(kernel='6.12',arch='armv7l',os_release='Tizen TV')
                board.identity.side_effect=[identity,ValueError('identity')] if fail=='identity' else [identity,identity]
                def read(label,*args):
                    if label==fail:raise ValueError(fail)
                    return 0,'root 1 0 init'
                board.read.side_effect=read
                def switch(board,mode):
                    if mode=='on' and fail=='on':raise ValueError('on')
                with patch.object(r,'connectivity',side_effect=ValueError('connect') if fail=='connectivity' else None), \
                     patch.object(r.prior.authorized,'identity_uid',return_value='uid=5001(owner)',side_effect=ValueError('before') if fail=='before' else None), \
                     patch.object(r.prior,'switch_root',side_effect=switch) as transitions, \
                     patch.object(r.prior,'baseline',side_effect=ValueError('baseline') if fail=='baseline' else None), \
                     patch.object(r.prior,'confirm_candidates',side_effect=ValueError('candidates') if fail=='candidates' else None,return_value=[CANDIDATE]), \
                     patch.object(r,'receive',side_effect=ValueError('stream') if fail=='stream' else None):
                    state={};rc=r.execute(board,{},state)
                    self.assertEqual(rc,0 if fail is None else 2)
                    if fail not in ('connectivity','before'):
                        self.assertEqual(transitions.call_args_list[-1].args[1],'off')
                        self.assertEqual(state['root_off_verified_uid'],5001)
                    else:transitions.assert_not_called()

    def test_publisher_rejects_command_or_program_tamper(self):
        import publish_persistent as pub
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp);(source/'raw').mkdir()
            state=dict(mode='persistent',status='STOP',board_files_created=0)
            (source/'state.json').write_text(json.dumps(state))
            board=r.Board('127.0.0.1',source)
            with patch.object(r.subprocess,'run',return_value=Mock(stdout=b'uid=5001(owner)\nRC=0\nDONE\n',returncode=0)):
                board.read('id',['id'])
            self.assertEqual(pub.validate(source)['status'],'STOP')
            (source/'raw/pre_id.txt').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):pub.validate(source)

    def test_all_missing_board_tools_reported_before_sampling(self):
        text=r.program(NONCE,[CANDIDATE])
        # Run only function definitions under real sh with an empty PATH.
        text=text.rsplit('\nfinish\n',1)[0]+'\nPATH=/nonexistent\nfinish\n'
        result=subprocess.run(['/bin/sh'],input=text,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,72)
        self.assertNotIn('===SAMPLE',result.stdout)
        self.assertIn('RC=72 FAIL',result.stdout)

    def test_ordinary_success_real_shell(self):
        if not shutil.which('awk'):
            self.skipTest('host awk required for real shell test')
        current=r.prior.proc_stat(Path('/proc/self/stat').read_text());current['target']='self'
        text=r.program(NONCE,[current])
        text=text.replace('item mem 0 cat /proc/meminfo','item mem 0 printf "MemAvailable: 100 kB\\n"')
        text=text.replace('item zram 0 cat /sys/block/zram0/mm_stat','item zram 0 printf "0 0 0\\n"')
        text=text.replace('item swaps 0 cat /proc/swaps','item swaps 0 printf "Filename Type Size Used Priority\\n/dev/zram0 partition 100 0 -1\\n"')
        # Test-only clock acceleration; deployed contract duration stays 600 s.
        text=text.replace('start=$(date +%s) || return','start=$(($(date +%s)-601)) || return')
        with tempfile.TemporaryDirectory() as tmp,patch.object(r,'covered',return_value=True),patch.object(r,'analyze',return_value=[]):
            r.receive(['/bin/sh'],text,NONCE,[current],Path(tmp),2)
            state=json.loads((Path(tmp)/'stream_state.json').read_text())
            self.assertTrue(state['final_proven']);self.assertEqual(state['host_rc'],0)


if __name__=='__main__':unittest.main()
