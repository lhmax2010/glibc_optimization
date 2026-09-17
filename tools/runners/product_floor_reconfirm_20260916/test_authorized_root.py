import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_authorized_root as m
import test_board_script as fixtures


class AuthorizationTests(unittest.TestCase):
    def test_receipt_audits_raw_uid_proofs_not_state_claim(self):
        import audit_authorized_receipt as audit
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'raw').mkdir();commands=[]
            for label,uid in [('pre_id_before_root_on',5001),('pre_root_on',None),
                              ('pre_id_after_root_on',0),('restore_root_off',None),
                              ('restore_id_after_root_off',5001)]:
                if uid is None:
                    commands.append(dict(label=label,argv=['sdb','-s','fixture','root','on' if label=='pre_root_on' else 'off']))
                else:
                    raw=f'uid={uid}(name)\n\nRC=0\nDONE\n'.encode()
                    (root/'raw'/(label+'.txt')).write_bytes(raw)
                    commands.append(dict(label=label,argv=['sdb','-s','fixture','shell',m.old.readonly_body(['id'])],
                                         remote_rc=0,raw_sha256=hashlib.sha256(raw).hexdigest(),ended_utc='fixture'))
            (root/'commands.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in commands))
            self.assertEqual([x['uid'] for x in audit.audit(root)['uid_transitions']],[5001,0,5001])
            commands[-1]['remote_rc']=1
            (root/'commands.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in commands))
            with self.assertRaisesRegex(ValueError,'not proven'):audit.audit(root)

    def test_complete_stream_is_analyzed_only_after_script_cleanup_and_root_is_restored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); b=Mock(output=root)
            b.identity.return_value=dict(kernel='6.12.60',arch='armv7l',os_release='Tizen TV')
            b.read.return_value=(0,'CapEff: 0')
            state={'status':'NOT_EXECUTED'}
            inventory=dict(pid1_visible=True,selected=[dict(target='Example',pid=1,start_ticks=123)])
            (root/'commands.jsonl').write_text(json.dumps(dict(label='root_sampling',host_rc=0,remote_rc=0))+'\n')
            with patch.object(m,'identity_uid',return_value='uid=5001(owner)'), \
                 patch.object(m,'root_switch') as switch, patch.object(m.portable,'tools_gate'), \
                 patch.object(m.portable,'baseline',return_value={'process_view':(0,'root 1 0 init')}), \
                 patch.object(m.old,'names_from_mapping',return_value={}), \
                 patch.object(m.portable,'permissions',return_value=inventory), \
                 patch.object(m.old,'globals_at',return_value={}), \
                 patch.object(m.portable,'install',return_value='/tmp/pf_20260916_0123456789ab.sh'), \
                 patch.object(m.portable.previous,'run_script',return_value=fixtures.BoardScriptTests().series()), \
                 patch.object(m.portable,'cleanup') as clean:
                self.assertEqual(m.execute(b,Path('unused'),state),0)
            self.assertEqual([c.args[1] for c in switch.call_args_list],['on','off'])
            self.assertEqual(clean.call_count,1)
            self.assertEqual(state['status'],'COMPLETE')
            self.assertEqual(state['root_off_verified_uid'],5001)
            self.assertEqual(len((root/'timeseries.tsv').read_text().splitlines()),602)
            self.assertEqual(json.loads((root/'summary.json').read_text())[0]['absolute_floor_kib'],20)

    def test_root_byte_readback_uses_prefixed_raw_label(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);b=m.Board('192.0.2.1',root);b.phase='root';b.has_sha256sum=False
            body=b'#!/bin/sh\ntrue\n'
            (root/'raw/root_proof.txt').write_bytes(body+b'\nRC=0\nDONE\n')
            item=dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256=hashlib.sha256(body).hexdigest())
            with patch.object(m.portable,'operation',side_effect=[(1,''),(0,'')]):m.portable.verify_script(b,'proof',item)

    def test_root_publisher_requires_restoration_before_any_output(self):
        import publish_compact
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';source.mkdir()
            (source/'state.json').write_text('{"status":"COMPLETE"}')
            (source/'authorization.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'root-off UID 5001'):
                publish_compact.publish(source,root/'public',Path('unused'),'192.0.2.1',Path('unused'))
            self.assertFalse((root/'public').exists())

    def test_stop_publisher_keeps_policy_denial_and_cleanup_proofs(self):
        import publish_compact
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';(source/'raw').mkdir(parents=True)
            (source/'state.json').write_text('{"status":"STOP"}')
            (source/'raw/root_sampling.txt').write_text('[uep][bash] the file is NOT signed!!\nRC=1\nFAIL\n')
            (source/'raw/root_cleanup_remove_0.txt').write_text('RC=0\nDONE\n')
            (source/'raw/root_permission_smaps_1.txt').write_text('private full maps')
            mapping=root/'map.tsv';mapping.write_text('original\treplacement\tscope\ttype\n')
            receipt=root/'receipt.json';receipt.write_text('{}')
            publish_compact.publish(source,root/'public',mapping,'192.0.2.1',receipt)
            self.assertIn('NOT signed',(root/'public/raw/root_sampling.txt').read_text())
            self.assertTrue((root/'public/raw/root_cleanup_remove_0.txt').exists())
            self.assertFalse((root/'public/raw/root_permission_smaps_1.txt').exists())

    def test_root_permission_replay_uses_exact_prefixed_command_proofs(self):
        import summarize_permissions
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'authorization.json').write_text('{}')
            (root/'permissions.json').write_text(json.dumps(dict(pid1_visible=True,
                matching={},checks=[dict(pid=1,status_rc=0,smaps_rc=0,readable=True,errors={})])))
            rows=[dict(label='root_permission_'+field+'_1',remote_rc=0,argv=['sdb','shell','cat']) for field in ('status','smaps')]
            (root/'commands.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=summarize_permissions.summarize(root)
            self.assertEqual(result['readable_pids'],[1]);self.assertTrue(result['pid1_visible'])

    def test_missing_authorization_never_contacts_board(self):
        run = subprocess.run([sys.executable, str(HERE/'run_authorized_root.py'),
                              '--ip', '127.0.0.1', '--output', 'unused',
                              '--push-receipt', 'unused', '--mapping', 'unused'],
                             text=True, capture_output=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('--pm-authorization-20260916', run.stderr)

    def test_id_not_sdb_exit_proves_transition(self):
        for mode, uid in (('on',5001),('on',0),('off',0),('off',5001)):
            b = Mock(serial='fixture')
            b.call.side_effect = [(0, 'Switched'), (0, f'uid={uid}(name) gid=0(root)')]
            with patch.object(m.time, 'sleep'):
                if uid == (0 if mode=='on' else 5001):
                    m.root_switch(b, mode)
                else:
                    with self.assertRaisesRegex(ValueError, 'UID proof'): m.root_switch(b, mode)
            self.assertEqual(b.call.call_count, 2)
            self.assertEqual(b.call.call_args_list[0].args[1][-2:],['root',mode])
            self.assertEqual(b.call.call_args_list[1].args[1][-1],m.old.readonly_body(['id']))

    def test_wrong_initial_uid_never_elevates(self):
        with tempfile.TemporaryDirectory() as d:
            b=Mock(output=Path(d)); b.identity.return_value={}; b.call.return_value=(0,'uid=0(root)')
            state={'status':'NOT_EXECUTED'}
            with patch.object(m,'root_switch') as switch,patch.object(m.portable,'cleanup'):
                self.assertEqual(m.execute(b,Path('unused'),state),2)
            switch.assert_not_called()
            self.assertEqual(state['root_transition'],'NOT_ATTEMPTED')

    def test_restore_happens_after_every_failure_no_retry_no_kill(self):
        for stage in ('before', 'on', 'identity', 'tools', 'baseline', 'permissions', 'globals', 'install', 'sampling', 'cleanup'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                b = Mock(output=root, phase='pre')
                identity = dict(kernel='6.12.60', arch='armv7l', os_release='Tizen TV')
                b.identity.side_effect = [ValueError('before')] if stage == 'before' else [identity, ValueError('identity') if stage == 'identity' else identity]
                b.read.return_value = (0, 'CapEff: 0')
                state = {'status': 'NOT_EXECUTED'}
                def fault(name, result):
                    return Mock(side_effect=ValueError(name)) if stage == name else Mock(return_value=result)
                transition = Mock(side_effect=[ValueError('on'), None] if stage == 'on' else [None, None])
                base = {'process_view': (0, 'root 1 0 init')}
                inv = dict(pid1_visible=True, selected=[dict(pid=1, start_ticks=1, target='Example')])
                (root/'commands.jsonl').write_text(json.dumps(dict(label='root_sampling',host_rc=0,remote_rc=0))+'\n')
                with patch.object(m, 'identity_uid', return_value='uid=5001(owner)'), patch.object(m, 'root_switch', transition), \
                     patch.object(m.portable, 'tools_gate', fault('tools', None)), \
                     patch.object(m.portable, 'baseline', fault('baseline', base)), \
                     patch.object(m.old, 'names_from_mapping', return_value={}), \
                     patch.object(m.portable, 'permissions', fault('permissions', inv)), \
                     patch.object(m.old, 'globals_at', fault('globals', {})), \
                     patch.object(m.portable, 'install', fault('install', '/tmp/pf_20260916_0123456789ab.sh')), \
                     patch.object(m.portable.previous, 'run_script', fault('sampling', 'fixture')), \
                     patch.object(m.portable, 'cleanup', fault('cleanup', None)) as clean:
                    self.assertEqual(m.execute(b, Path('unused'), state), 2)
                if stage == 'before':
                    self.assertEqual(transition.call_count, 0)
                else:
                    self.assertEqual([c.args[1] for c in transition.call_args_list], ['on','off'])
                    self.assertEqual(state['root_off_verified_uid'],5001)
                self.assertEqual(clean.call_count, 1)
                self.assertFalse(b.call.called)  # No extra target command or kill on failure.

    def test_root_off_failure_stops_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            b = Mock(output=Path(d)); b.identity.return_value={}
            state={'status':'NOT_EXECUTED'}
            with patch.object(m,'identity_uid',return_value='uid=5001(owner)'), \
                 patch.object(m,'root_switch',side_effect=[ValueError('on'),ValueError('off')]) as switch, \
                 patch.object(m.portable,'cleanup'):
                self.assertEqual(m.execute(b,Path('unused'),state),2)
            self.assertEqual(switch.call_count,2)
            self.assertEqual(state['root_off_error'],'off')
            self.assertNotIn('root_off_verified_uid',state)

    def test_full_view_gate_rejects_missing_pid_one(self):
        with self.assertRaisesRegex(ValueError,'PID 1'): m.full_view_gate({'process_view':(0,'root 11 0 sh')})
        m.full_view_gate({'process_view':(0,'root 1 0 init')})

    def test_remote_bodies_still_bounded_and_script_paths_restricted(self):
        for command in ('run','read','hash','absent','symlink','remove'):
            self.assertLessEqual(len(m.portable.script_body(command,'/tmp/pf_20260916_0123456789ab.sh').encode()),200)
        with self.assertRaises(ValueError):m.portable.script_body('remove','/tmp')


if __name__ == '__main__': unittest.main()
