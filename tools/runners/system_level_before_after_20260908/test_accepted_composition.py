"""Public-only replay and immutable accepted composition regression tests."""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE=pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys,'path',[str(HERE),*sys.path]):
    import compose_accepted_measurement as comp
    import analyze_directory_disposition as audit
    import replay_compact
    import publish_measurement
    import audit_single_cleanup_20260911 as single

PUBLIC=comp.PUBLIC/'accepted_matrix'
CLEANUP=comp.PUBLIC/'directory_disposition_20260911'


class AcceptedCompositionTests(unittest.TestCase):
    def test_manifest_and_five_frozen_derived_files_byte_exact(self):
        for item in json.loads((PUBLIC/'manifest.json').read_text())['files']:
            path=PUBLIC/item['path']
            self.assertEqual(path.stat().st_size,item['bytes'])
            self.assertEqual(comp.digest(path),item['sha256'])
        with tempfile.TemporaryDirectory() as temp:
            out=pathlib.Path(temp)
            count,groups=replay_compact.replay(json.loads((PUBLIC/'point_source.json').read_text()),PUBLIC/'gst_cycles.tsv',out)
            self.assertEqual((count,groups),(333,7))
            for name in comp.DERIVED:
                self.assertEqual((out/name).read_bytes(),(PUBLIC/name).read_bytes(),name)

    def test_sources_keep_old_stops_and_split_epochs_explicit(self):
        receipt=json.loads((PUBLIC/'composition.json').read_text())
        self.assertEqual(receipt['historical_execution_verdicts'],['STOP','STOP'])
        self.assertEqual(receipt['execution_sha256'],list(comp.RECEIPTS))
        self.assertEqual([len(r['cells']) for r in receipt['execution_epochs']],[18,3])
        self.assertEqual(json.loads((comp.PUBLIC/'completed_prefix/completed_points.json').read_text())['execution']['verdict'],'STOP')
        self.assertEqual(json.loads((comp.PUBLIC/'g4_authorized_20260910/execution/execution.json').read_text())['verdict'],'STOP')
        self.assertEqual(receipt['cleanup_audit_sha256'],comp.digest(CLEANUP/'audit.json'))

    def test_negative_system_net_and_g4_idle_not_next_faults(self):
        rows=replay_compact.derive_rows(json.loads((PUBLIC/'point_source.json').read_text()))
        import statistics
        g1=[r for r in rows if (r['group'],r['arm'],r['cycle'])==('G1','trim',1)]
        self.assertEqual(statistics.median(r['memavailable_net_kib'] for r in g1),-172)
        g4=[r for r in rows if r['group']=='G4']
        self.assertEqual([r['heap_drop_kib'] for r in g4],[88,0,4])
        self.assertTrue(all(r['memavailable_net_mib'] is None and r['next_cycle_minflt'] is None for r in g4))
        self.assertEqual([r['idle_120s_minflt'] for r in g4],[1,0,1])

    def test_missing_duplicate_points_and_wrong_cycle_fail(self):
        source=json.loads((PUBLIC/'point_source.json').read_text())
        for mode in ('missing','duplicate','cycle'):
            bad=json.loads(json.dumps(source))
            if mode=='missing':bad['points'].pop()
            elif mode=='duplicate':bad['points'].append(bad['points'][-1])
            else:bad['points'][-1]['metric']['cycle']=2
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                replay_compact.derive_rows(bad)

    def test_cleanup_replay_positive_and_hash_corruption(self):
        result=audit.replay(CLEANUP)
        self.assertEqual(result['uid_sequence'],[5001,0,5001])
        self.assertEqual(result['commands'],111)
        self.assertEqual(result['request_bytes'],[70,161])
        self.assertEqual([r['verdict'] for r in result['disposition']],['REPORT_ONLY_PENDING_NONEMPTY']*4)
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)/'copy';shutil.copytree(CLEANUP,root)
            (root/'ROOT_END_PS.txt').write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                audit.replay(root)

    def test_cleanup_semantics_still_checked_after_updated_manifest(self):
        changes={'ROOT_END_PS.txt':lambda t:t.replace('    1     0', ' 9999     0'),
            'ROOT_ID_OFF_1.txt':lambda t:t.replace('uid=5001(', 'uid=0('),
            'ROOT_END_DF_ROOT.txt':lambda t:t.replace('RC=0\nDONE','RC=1\nFAIL'),
            'ROOT_END_DIR_4.txt':lambda t:t.replace('14509','99999')}
        for name,edit in changes.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=pathlib.Path(temp)/'copy';shutil.copytree(CLEANUP,root)
                original=(root/name).read_text();altered=edit(original)
                self.assertNotEqual(original,altered)
                (root/name).write_text(altered)
                manifest=json.loads((root/'manifest.json').read_text())
                for item in manifest['files']:
                    if item['path']==name:item['public_sha256']=comp.digest(root/name)
                (root/'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):audit.replay(root)

    def test_historical_publisher_not_weakened(self):
        with tempfile.TemporaryDirectory() as temp:
            run=pathlib.Path(temp)/'run';run.mkdir()
            (run/'execution.json').write_text(json.dumps({'verdict':'STOP','cleanup':'FAIL'}))
            with self.assertRaisesRegex(ValueError,'incomplete/failed matrix'):
                publish_measurement.publish_to_staging(run,pathlib.Path(temp)/'out')

    def test_all_public_composition_and_cleanup_manifest_inputs_tracked(self):
        import subprocess
        tracked=set(subprocess.check_output(['git','ls-files'],cwd=comp.ROOT,text=True).splitlines())
        for base,key in ((PUBLIC,'sha256'),(CLEANUP,'public_sha256')):
            for row in json.loads((base/'manifest.json').read_text())['files']:
                self.assertIn((base/row['path']).relative_to(comp.ROOT).as_posix(),tracked)


class ContractIdentityTests(unittest.TestCase):
    def test_machine_constants_resolve_commit_and_match_both_file_hashes(self):
        refs=single.verify_contract_sources(comp.ROOT)
        self.assertEqual(refs['contract_commit'],'54ee2ba8d2819014f3e5656de023ffaf283b4a4a')
        self.assertEqual(refs['human_evidence']['tag_object'],'0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3')
        for relative,digest in refs['files_sha256'].items():
            frozen=subprocess.check_output(['git','show',refs['contract_commit']+':'+relative],cwd=comp.ROOT)
            self.assertEqual(hashlib.sha256(frozen).hexdigest(),digest)
            self.assertEqual((comp.ROOT/relative).read_bytes(),frozen)

    def clone(self, parent, *, no_tags=False, shallow=False):
        clone=parent/'clone'
        command=['git','clone','--quiet','--no-checkout']
        if no_tags:command.append('--no-tags')
        if shallow:command+=['--depth','1']
        subprocess.run([*command,comp.ROOT.as_uri(),str(clone)],check=True,capture_output=True)
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=comp.ROOT,text=True).strip()
        # Explicit HEAD fetch supports demo and detached-tag source checkouts.
        fetch=['git','fetch','--quiet','--no-tags']+(['--depth','1'] if shallow else [])
        subprocess.run([*fetch,comp.ROOT.as_uri(),head],cwd=clone,check=True,capture_output=True)
        subprocess.run(['git','checkout','--quiet','--detach',head],cwd=clone,check=True,capture_output=True)
        # Exercise current code during development too, before its commit exists.
        for name in ('audit_single_cleanup_20260911.py','contract_refs.json','analyze_directory_disposition.py'):
            shutil.copyfile(HERE/name,clone/(HERE/name).relative_to(comp.ROOT))
        return clone

    def public_replay(self, clone, *, expected_pass):
        relative=HERE.relative_to(comp.ROOT)
        result=subprocess.run([sys.executable,str(clone/relative/'analyze_directory_disposition.py'),
            str(clone/CLEANUP.relative_to(comp.ROOT))],capture_output=True,text=True)
        if not expected_pass:
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertEqual(result.stdout,'')
            self.assertIn('FAIL directory-disposition-replay: contract-source-unavailable',result.stderr)
            self.assertIn('git fetch --no-tags --unshallow origin',result.stderr)
            self.assertIn('git fetch --no-tags --deepen <depth> origin',result.stderr)
            return
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['verdict'],'PASS_DELAYED_CLEANUP_WITH_REPORT_ONLY_NONEMPTY')
        with tempfile.TemporaryDirectory() as directory:
            public=clone/PUBLIC.relative_to(comp.ROOT)
            replay=subprocess.run([sys.executable,str(clone/relative/'replay_compact.py'),
                '--points',str(public/'point_source.json'),'--gst-cycles',str(public/'gst_cycles.tsv'),
                '--output-dir',directory],capture_output=True,text=True)
            self.assertEqual(replay.returncode,0,replay.stdout+replay.stderr)
            for name in comp.DERIVED:
                self.assertEqual((pathlib.Path(directory)/name).read_bytes(),(public/name).read_bytes(),name)

    def test_full_and_no_tags_clone_public_replay_pass(self):
        for no_tags in (False,True):
            with self.subTest(no_tags=no_tags),tempfile.TemporaryDirectory() as directory:
                clone=self.clone(pathlib.Path(directory),no_tags=no_tags)
                if no_tags:
                    self.assertEqual(subprocess.check_output(['git','tag','--list'],cwd=clone),b'')
                self.public_replay(clone,expected_pass=True)

    def test_shallow_missing_commit_fails_explicitly_then_reachable_without_tags_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            clone=self.clone(pathlib.Path(directory),no_tags=True,shallow=True)
            self.assertEqual(subprocess.check_output(['git','rev-parse','--is-shallow-repository'],cwd=clone).strip(),b'true')
            self.public_replay(clone,expected_pass=False)
            commit=single.verify_contract_sources(comp.ROOT)['contract_commit']
            subprocess.run(['git','fetch','--quiet','--no-tags','--depth','1',comp.ROOT.as_uri(),commit],
                cwd=clone,check=True,capture_output=True)
            self.assertEqual(subprocess.check_output(['git','tag','--list'],cwd=clone),b'')
            self.assertEqual(subprocess.check_output(['git','rev-parse','--is-shallow-repository'],cwd=clone).strip(),b'true')
            self.public_replay(clone,expected_pass=True)

    def test_contract_bytes_refs_and_object_type_cannot_be_weakened(self):
        with tempfile.TemporaryDirectory() as directory:
            clone=self.clone(pathlib.Path(directory))
            refs_path=clone/HERE.relative_to(comp.ROOT)/'contract_refs.json'
            original=refs_path.read_bytes();refs=json.loads(original)
            for relative in refs['files_sha256']:
                target=clone/relative;data=target.read_bytes();target.write_bytes(data+b'\n')
                with self.assertRaisesRegex(ValueError,'bytes changed'):single.verify_contract_sources(clone)
                target.write_bytes(data)
            for fault in ('schema','short','named-tag','tag-object','hash','missing-file','extra-file'):
                bad=json.loads(original)
                if fault=='schema':bad['schema']='wrong'
                elif fault=='short':bad['contract_commit']='54ee2ba'
                elif fault=='named-tag':bad['contract_commit']=bad['human_evidence']['annotated_tag']
                elif fault=='tag-object':bad['contract_commit']=bad['human_evidence']['tag_object']
                elif fault=='hash':bad['files_sha256'][next(iter(bad['files_sha256']))]='0'*64
                elif fault=='missing-file':bad['files_sha256'].pop(next(iter(bad['files_sha256'])))
                elif fault=='extra-file':bad['files_sha256']['../outside']='0'*64
                refs_path.write_text(json.dumps(bad))
                with self.subTest(fault=fault),self.assertRaises(ValueError):single.verify_contract_sources(clone)
            refs_path.write_bytes(original)
            # A human label is documentary, not a hidden machine dependency.
            refs['human_evidence']['annotated_tag']='not-resolvable-in-any-clone'
            refs_path.write_text(json.dumps(refs))
            single.verify_contract_sources(clone)


if __name__=='__main__':
    unittest.main()
