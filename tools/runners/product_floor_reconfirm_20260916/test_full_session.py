import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import run_full_session as r
import publish_full_session as publisher


class SessionTests(unittest.TestCase):
    def test_framing_and_byte_gate(self):
        r.bounded('x'*200+'\n')
        for text in ('x'*201,'界'*67,'bad\0line'):
            with self.assertRaises(ValueError):r.bounded(text)
        with tempfile.TemporaryDirectory() as d:
            s=object.__new__(r.Session)
            s.output=Path(d);s.nonce='a'*32;s.active=None;s.seen=set();s.frames=[];s.queue=[]
            s.feed('prompt> q example id',1,1)
            s.feed('===BEGIN '+'a'*32+' example 1800000000===',1,1)
            s.feed('uid=0(root)',2,2)
            s.feed('===END '+'a'*32+' example RC=0 DONE 1800000000===',3,3)
            self.assertEqual(s.queue[0]['text'],'uid=0(root)')
            with self.assertRaises(ValueError):s.feed('===BEGIN '+'a'*32+' example 1800000000===',4,4)

    def test_short_request_allowlist_and_second_work_session(self):
        with tempfile.TemporaryDirectory() as d:
            b=r.Transport('127.0.0.1',Path(d)/'out')
            with mock.patch.object(r.subprocess,'run') as run:
                with self.assertRaises(ValueError):b.call('bad',['-s',b.serial,'shell','cat /proc/1/stat'])
                self.assertFalse(run.called)
            b.working_opened=True
            with self.assertRaises(ValueError):r.Session(b)
            with self.assertRaises(ValueError):b.call('devices',['devices'])

    def test_real_shell_bootstrap_and_watchdog(self):
        with tempfile.TemporaryDirectory() as d:
            b=r.Transport('127.0.0.1',Path(d)/'out')
            original=r.subprocess.Popen
            with mock.patch.object(r.subprocess,'Popen',side_effect=lambda *a,**kw:original(['/bin/sh'],**kw)):
                s=r.Session(b,silence_seconds=.15)
                try:
                    s.send(r.bootstrap(s.nonce));f=s.next()
                    self.assertEqual(f['label'],'root_id')
                    f=s.request('hello',"printf '%s\\n' hello")
                    self.assertEqual(f['text'],'hello')
                    with self.assertRaisesRegex(ValueError,'SILENCE'):s.next()
                finally:s.close()

    def test_initialization_failure_closes_local_client(self):
        with tempfile.TemporaryDirectory() as d:
            b=r.Transport('127.0.0.1',Path(d)/'out');original=r.subprocess.Popen;children=[]
            def start(*args,**kwargs):
                p=original(['/bin/sh'],**kwargs);children.append(p);return p
            with mock.patch.object(r.subprocess,'Popen',side_effect=start), \
                 mock.patch.object(r.selectors,'DefaultSelector') as selector:
                selector.return_value.register.side_effect=OSError('host selector failure')
                with self.assertRaisesRegex(OSError,'selector'):r.Session(b)
                self.assertTrue(children[0].stdin.closed)
                self.assertIsNotNone(children[0].poll())

    def test_disconnect_partial_and_bad_rc(self):
        for variant in ('disconnect','partial','rc'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as d:
                b=r.Transport('127.0.0.1',Path(d)/'out');original=r.subprocess.Popen
                with mock.patch.object(r.subprocess,'Popen',side_effect=lambda *a,**kw:original(['/bin/sh'],**kw)):
                    s=r.Session(b)
                    try:
                        if variant=='rc':
                            s.send(r.bootstrap(s.nonce));s.next()
                            with self.assertRaisesRegex(ValueError,'RC=1'):s.request('fail','false')
                        else:
                            prefix=("printf '===BEGIN "+s.nonce+" cut 1800000000===\\n'\n") if variant=='partial' else ''
                            s.send(prefix+'exit 0\n')
                            with self.assertRaisesRegex(ValueError,'DISCONNECT'):s.next()
                    finally:s.close()


class FullFlowTests(unittest.TestCase):
    """Real POSIX shell, fake host fixture filesystem; no discovery mock."""
    def flow(self, fault=None):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);output=root/'out';fakeproc=root/'proc';fakeproc.mkdir()
            # Every PID differs from any prior recorded board process.
            for pid in range(101,113):
                (fakeproc/str(pid)).mkdir()
                tail=['S']+['0']*24;tail[7]='10';tail[9]='0';tail[19]=str(pid*10)
                name={101:'enlightenment',102:'serviceH',103:'serviceA'}.get(pid,'p'+str(pid))
                (fakeproc/str(pid)/'stat').write_text(f'{pid} ({name}) '+' '.join(tail)+'\n')
                (fakeproc/str(pid)/'smaps').write_text('00100000-00110000 rw-p 00000000 00:00 0\nPrivate_Dirty: '+str(pid)+' kB\n')
            if fault=='empty':(fakeproc/'101'/'smaps').write_text('')
            # Prefix exists only in this host test, never sent to a board.
            prefix='''date() { if [ "$1" = +%s ]; then /bin/date +%s; else printf 'test date\\n'; fi; }
id() { printf 'uid=0(root) gid=0(root)\\n'; }
uname() { if [ "$1" = -r ]; then printf '6.12.60\\n'; else printf 'armv7l\\n'; fi; }
rpm() { printf 'glibc-2.40-1.12.armv7l\\n'; }
getconf() { printf '250\\n'; }
ps() { printf 'root 1 0 init\\n'; }
df() { printf '/opt/usr 2G\\n'; }
ls() { printf 'empty test fixture\\n'; }
cat() {
case "$1" in
/etc/os-release) printf 'NAME=Tizen\\nVERSION=Tizen10TV\\n';;
'''+str(fakeproc)+'''/meminfo) printf 'MemTotal: 1599416 kB\\nMemAvailable: 1000000 kB\\n';;
'''+str(fakeproc)+'''/swaps) printf 'Filename Type Size Used Priority\\n/dev/zram0 partition 100 0 -1\\n';;
/sys/block/zram0/mm_stat) printf '0 0 0 0 0\\n';;
'''+str(fakeproc)+'''/uptime) printf '12345.0 0\\n';;
/sys/devices/system/cpu/online) printf '0-3\\n';;
'''+str(fakeproc)+'''/self/status) printf 'Uid: 0 0 0 0\\n';;
*) /bin/cat "$@";;
esac
}
'''
            if fault=='identity':prefix+='uname() { printf "rpi4\\n"; }\n'
            calls=[];real_run=subprocess.run;real_popen=subprocess.Popen
            def fake_run(argv,**kwargs):
                if argv[0]!='fake-sdb':return real_run(argv,**kwargs)
                calls.append(argv[1:]);args=argv[1:]
                if args==['devices']:out='127.0.0.1:26101 device product\n'
                elif args[-2:]==['root','on']:
                    out='error root on\n' if fault=='root_on' else 'Switched to root\n'
                elif args[-2:]==['root','off']:out='error root off\n' if fault=='root_off' else 'Switched to user\n'
                elif 'shell' in args:out='uid=5001(developer) gid=5001(developer)\n\nRC=0\nDONE\n'
                else:raise AssertionError(argv)
                return subprocess.CompletedProcess(argv,0,out.encode())
            def fake_popen(argv,**kwargs):
                self.assertEqual(argv,['fake-sdb','-s','127.0.0.1:26101','shell']);calls.append(argv[1:])
                proc=real_popen(['/bin/sh'],**kwargs);proc.stdin.write(prefix.encode());proc.stdin.flush();return proc
            original_send=r.Session.send
            def send(session,text):
                # Only virtualize host fixture paths/clock; execute real traversal,
                # framing, candidate selection, sampling shell and driver branches.
                text=text.replace('/proc/',str(fakeproc)+'/')
                text=text.replace('q libc /lib/libc.so.6',"q libc printf 'GNU libc 2.40\\n'")
                text=text.replace('start=$(date +%s) || return','start=0')
                if fault=='gone' and text.startswith('P='):
                    # Disappearance is a host fixture deletion, no board commands.
                    import shutil
                    shutil.rmtree(fakeproc/'101')
                return original_send(session,text)
            with mock.patch.object(r.subprocess,'run',side_effect=fake_run),mock.patch.object(r.subprocess,'Popen',side_effect=fake_popen), \
                 mock.patch.object(r.Session,'send',send),mock.patch.object(r,'enough',side_effect=lambda rows,bs,cs,ret:len(bs)>=2), \
                 mock.patch.object(r,'analyze',return_value={'status':'TEST_ONLY_COVERAGE_CHECKED_SEPARATELY'}),mock.patch.object(r.time,'sleep'):
                b=r.Transport('127.0.0.1',output,'fake-sdb')
                state=r.execute(b,{'enlightenment':'enlightenment','ServiceH':'serviceH','ServiceA':'serviceA'},dict(status='RUNNING',complete_batches=0))
            expected='STOP' if fault in ('identity','root_on','root_off','empty') else 'COMPLETE'
            self.assertEqual(state['status'],expected,state)
            shells=[c for c in calls if 'shell' in c]
            self.assertEqual(len(shells),2 if fault=='root_on' else 3,calls)
            self.assertEqual(sum(c[-2:]==['root','on'] for c in calls),1)
            self.assertEqual(sum(c[-2:]==['root','off'] for c in calls),1)
            self.assertEqual(calls[-2][-2:],['root','off'])
            self.assertIn('uid=5001',state['id_after_root_off'])
            if expected=='COMPLETE':
                inv=json.loads((output/'inventory.json').read_text())
                cs=json.loads((output/'candidates.json').read_text())['selected']
                self.assertEqual(len(inv),12);self.assertEqual(len(cs),12)
                if fault=='gone':
                    ev=json.loads((output/'events.json').read_text());self.assertEqual(ev[0]['pid'],101)
                    self.assertEqual(len(ev),1)
                    self.assertNotIn('before_1_101',(output/'frames.jsonl').read_text())
                intents=[json.loads(s) for s in (output/'intents.jsonl').read_text().splitlines()]
                self.assertEqual(sum(i['label']=='working_session' for i in intents),1)
                self.assertLessEqual(max(len(s.encode()) for s in (output/'stdin_program.txt').read_text().splitlines()),200)
                # Full stream/frame/row proof is exercised even in accelerated
                # fixture; never present its shortened window as COMPLETE.
                state['status']='STOP';r.old.write_json(output/'state.json',state)
                audit=publisher.validate(output)
                self.assertEqual(audit['working_sessions'],1)
                self.assertEqual(audit['short_id_queries'],2)
                self.assertEqual(audit['completed_batches'],2)
                frames=(output/'frames.jsonl').read_text()
                (output/'frames.jsonl').write_text(frames.replace('Private_Dirty: 102','Private_Dirty: 999',1))
                with self.assertRaisesRegex(ValueError,'content mismatch'):publisher.validate(output)

    def test_all_pids_changed_one_working_session(self):self.flow()
    def test_disappearance_keeps_other_candidates(self):self.flow('gone')
    def test_identity_stop_only_restores(self):self.flow('identity')
    def test_ambiguous_root_on_still_restores(self):self.flow('root_on')
    def test_root_off_failure_still_queries_uid(self):self.flow('root_off')
    def test_empty_live_userspace_maps_stop_not_silent_exclusion(self):self.flow('empty')


if __name__=='__main__':unittest.main()
