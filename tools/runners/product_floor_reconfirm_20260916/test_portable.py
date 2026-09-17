import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('portable_floor',HERE/'run_portable.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
spec2=importlib.util.spec_from_file_location('probe_fixture',HERE/'test_board_script.py')
fixtures=importlib.util.module_from_spec(spec2); spec2.loader.exec_module(fixtures)


class PortableTests(unittest.TestCase):
    def test_permission_summary_validates_recorded_rc_without_zero_filling(self):
        import summarize_permissions as audit
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            checks=[dict(pid=10,status_rc=0,smaps_rc=1,readable=False,
                         errors={'smaps':'cat: /proc/10/smaps: Permission denied'},reason='unreadable')]
            (root/'permissions.json').write_text(json.dumps(dict(checks=checks,matching={'A':{'exact_pids':[]}},pid1_visible=False)))
            records=[dict(label='permission_'+field+'_10',remote_rc=rc,argv=['sdb','shell','cat'])
                     for field,rc in [('status',0),('smaps',1)]]
            (root/'commands.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            result=audit.summarize(root)
            self.assertEqual(result['readable_pids'],[])
            self.assertEqual(result['smaps_permission_denied_pids'],[10])
            self.assertEqual(result['script_pushes'],0)
            records[-1]['remote_rc']=0
            (root/'commands.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            with self.assertRaisesRegex(ValueError,'RC mismatch'):audit.summarize(root)

    def env(self,root,missing=()):
        bindir=root/'bin'; bindir.mkdir()
        for command in m.TOOLS:
            if command not in missing:
                # Only commands actually exercised by the shell parser need real tools.
                # Probe-only names do not turn RPM or other optional host tools into dependencies.
                path=shutil.which(command) if command in {'awk','cat','date','sleep','sh'} else '/bin/true'
                if path is None:
                    self.skipTest('portable shell fixture needs host executable: '+command)
                (bindir/command).symlink_to(path)
        return dict(os.environ,PATH=str(bindir))

    def test_no_timeout_and_missing_sha_actually_execute(self):
        for missing in ((),('sha256sum',),('sha256sum','sed','grep')):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as d:
                root=Path(d); env=self.env(root,missing)
                run=subprocess.run(['/bin/sh','-c',m.probe_body()],env=env,text=True,capture_output=True)
                self.assertEqual(run.returncode,0)
                board=Mock(output=root); board.call.return_value=m.old.single.parse(run.stdout)
                result=m.tools_gate(board)
                self.assertEqual(set(result['missing']),set(missing))
                self.assertNotIn('timeout',m.script_body('run','/tmp/pf_20260916_0123456789ab.sh'))
                target=fixtures.BoardScriptTests().fake_proc(root)
                script=(HERE/'board_probe.sh').read_text().replace('proc_root=/proc','proc_root='+d)
                p=root/'script.sh';p.write_text(script)
                proc=subprocess.run(['/bin/sh',str(p),'proc','Example:1:123'],env=env,text=True,capture_output=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
                self.assertEqual(proc.stdout.split('\t')[6:10],['20','4','2','26'])

    def test_missing_required_tools_reported_together_before_any_other_action(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); env=self.env(root,('awk','cat','sleep','sha256sum'))
            run=subprocess.run(['/bin/sh','-c',m.probe_body()],env=env,text=True,capture_output=True)
            b=Mock(output=root);b.call.return_value=m.old.single.parse(run.stdout)
            with self.assertRaisesRegex(ValueError,'awk,cat,sleep'):m.tools_gate(b)
            result=json.loads((root/'tools.json').read_text())
            self.assertEqual(set(result['missing']),{'awk','cat','sleep','sha256sum'})
            script=root/'script.sh';script.write_text((HERE/'board_probe.sh').read_text())
            probe=subprocess.run(['/bin/sh',str(script),'collect'],env=env,text=True,capture_output=True)
            self.assertEqual(probe.returncode,78)
            for name in ('awk','cat','sleep'):self.assertIn(name,probe.stderr)
            self.assertNotIn('SAMPLING_DONE',probe.stdout)

    def board(self,root,readable):
        b=Mock(output=root); b.call.return_value=(0,'/proc/10/comm\talpha\n/proc/20/comm\tbeta')
        def read(label,argv,optional=False):
            pid=int(argv[1].split('/')[2]); field=argv[1].split('/')[-1]
            if pid not in readable:return (1,f'cat: {argv[1]}: Permission denied')
            if field=='status':return (0,f'Name:\talpha\nPid:\t{pid}\n')
            if field=='smaps':return (0,fixtures.SMAPS)
            tail=['S']+['0']*24;tail[19]='123'
            return (0,f'{pid} (alpha) '+ ' '.join(tail))
        b.read.side_effect=read
        return b

    def test_all_unreadable_stops_without_any_push_and_preserves_each_error(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.board(Path(d),set())
            with self.assertRaisesRegex(ValueError,'all living named'):m.permissions(b,{'A':'alpha','B':'beta'})
            result=json.loads((Path(d)/'permissions.json').read_text())
            self.assertEqual(result['decision'],'ALL_NAMED_UNREADABLE_NO_PUSH')
            self.assertEqual(len(result['checks']),2)
            self.assertTrue(all('Permission denied' in r['errors']['smaps'] for r in result['checks']))
            self.assertEqual(b.call.call_count,1)
            self.assertEqual(len([c for c in b.read.call_args_list if c.args[1][1].endswith('/smaps')]),2)
            self.assertEqual(len([c for c in b.read.call_args_list if c.args[1][1].endswith('/status')]),2)

    def test_partial_view_samples_only_readable_no_pid1_requirement(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.board(Path(d),{10})
            result=m.permissions(b,{'A':'alpha','B':'beta'})
            self.assertFalse(result['pid1_visible'])
            self.assertEqual([r['pid'] for r in result['selected']],[10])
            self.assertEqual(result['selected'][0]['target'],'A_10')
            self.assertEqual(len(result['checks']),2)

    def test_sha_missing_full_bytes_compared_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'raw').mkdir()
            body=b'#!/bin/sh\necho example\n';item=dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256=hashlib.sha256(body).hexdigest())
            b=Mock(output=root,has_sha256sum=False)
            raw=root/'raw/proof.txt'
            for content in (body,body+b' ',body[:-1]):
                raw.write_bytes(content+b'\nRC=0\nDONE\n')
                with patch.object(m,'operation',side_effect=[(1,''),(0,'ignored')]):
                    if content==body:m.verify_script(b,'proof',item)
                    else:
                        with self.assertRaisesRegex(ValueError,'byte mismatch'):m.verify_script(b,'proof',item)
            raw.write_bytes((body+b'\nRC=0\nDONE\n').replace(b'\n',b'\r\n'))
            with patch.object(m,'operation',side_effect=[(1,''),(0,'ignored')]):
                m.verify_script(b,'proof',item)

    def test_cleanup_exit_proof_suffices_under_restricted_ps_and_hash_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            b=Mock(output=Path(d));item=dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256='a'*64)
            with patch.object(m,'verify_script') as check,patch.object(m,'operation',side_effect=[(0,''),(1,''),(1,'')]):
                m.cleanup(b,[item],True)
                check.assert_called_once()
                b.call.assert_not_called()
            with patch.object(m,'verify_script',side_effect=ValueError('mismatch')),patch.object(m,'operation') as op:
                with self.assertRaisesRegex(ValueError,'mismatch'):m.cleanup(b,[item],True)
                op.assert_not_called()

    def test_incomplete_stream_cannot_delete_under_unproven_process_visibility(self):
        with tempfile.TemporaryDirectory() as d:
            item=dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256='a'*64)
            for view in ('owner 99 0 sh','root 1 0 init\nowner 99 0 sh '+item['path']):
                b=Mock(output=Path(d));b.call.return_value=(0,view)
                with patch.object(m,'operation') as op,self.assertRaisesRegex(ValueError,'cleanup:'):
                    m.cleanup(b,[item],False)
                op.assert_not_called()

    def test_all_requests_bounded_and_wrong_paths_rejected(self):
        self.assertLessEqual(len(m.probe_body().encode()),200)
        self.assertLessEqual(len(m.COMM_BODY.encode()),200)
        for op in ('run','read','hash','absent','symlink','remove'):
            self.assertLessEqual(len(m.script_body(op,'/tmp/pf_20260916_0123456789ab.sh').encode()),200)
            with self.assertRaises(ValueError):m.script_body(op,'/tmp/unrelated')

    def test_exec_comm_change_is_not_accepted_as_same_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.board(Path(d),{10}); original=b.read.side_effect
            def changed(label,argv,optional=False):
                rc,text=original(label,argv,optional)
                return rc,text.replace('(alpha)','(changed)') if 'stat_after' in label else text
            b.read.side_effect=changed
            with self.assertRaisesRegex(ValueError,'identity changed'):m.permissions(b,{'A':'alpha'})

    def test_main_cleanup_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); receipt=root/'receipt.json';receipt.write_text('{}')
            b=Mock();b.identity.return_value={}
            def install(board,selected,owned):
                owned.append(dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256='a'*64))
                return owned[0]['path']
            with patch.object(sys,'argv',['probe','--ip','192.0.2.1','--output',str(root/'out'),
                       '--mapping',str(root/'map'),'--push-receipt',str(receipt)]), \
                 patch.object(m.old,'git',return_value=b'commit'),patch.object(m.old,'contract_gate',return_value={}), \
                 patch.object(m.old,'names_from_mapping',return_value={}),patch.object(m,'Board',return_value=b), \
                 patch.object(m,'tools_gate'),patch.object(m,'baseline'), \
                 patch.object(m,'permissions',return_value={'selected':[]}),patch.object(m.old,'globals_at',return_value={}), \
                 patch.object(m,'install',side_effect=install),patch.object(m,'collect',return_value='raw'), \
                 patch.object(m.previous,'parse_samples',return_value=([],[])), \
                 patch.object(m,'cleanup',side_effect=ValueError('cleanup failed')) as cleanup:
                self.assertEqual(m.main(),2)
                cleanup.assert_called_once()
            self.assertEqual(json.loads((root/'out/state.json').read_text())['status'],'STOP')

    def test_601_native_slots_no_timeout_no_sha_and_failure_propagation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); env=self.env(root,('sha256sum',))
            fixtures.BoardScriptTests().fake_proc(root)
            (root/'meminfo').write_text('MemAvailable: 1234 kB\n')
            (root/'swaps').write_text('Filename Type Size Used Priority\n')
            zram=root/'sys/block/zram0';zram.mkdir(parents=True)
            (zram/'mm_stat').write_text('0 0 0\n')
            script=(HERE/'board_probe.sh').read_text().replace('proc_root=/proc','proc_root='+d)
            script=script.replace('sys_root=/sys','sys_root='+str(root/'sys')).replace('@TARGETS@','Example:1:123')
            # Deterministic host clock fixture speeds 601 slots; production clock remains unchanged.
            script=script.replace('mono_ns() { awk \'{printf "%.0f\\n",$1*1000000000}\' "$proc_root/uptime"; }',
                                  'mono_ns() { echo "${deadline:-0}"; }')
            self.assertIn('mono_ns() { echo',script)
            path=root/'probe.sh';path.write_text(script)
            run=subprocess.run(['/bin/sh',str(path),'collect'],env=env,text=True,capture_output=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            rows,timing=m.previous.parse_samples(run.stdout,[dict(target='Example',pid=1,start_ticks=123)])
            self.assertEqual(len(rows),601);self.assertEqual(len(timing),601)
            self.assertEqual(rows[-1]['epoch_ns']-rows[0]['epoch_ns'],600000000000)
            (root/'1/smaps').write_text('')
            failed=subprocess.run(['/bin/sh',str(path),'collect'],env=env,text=True,capture_output=True,timeout=5)
            self.assertEqual(failed.returncode,72)
            self.assertIn('read child failed',failed.stderr)
            self.assertNotIn('SAMPLING_DONE',failed.stdout)


if __name__=='__main__':unittest.main()
