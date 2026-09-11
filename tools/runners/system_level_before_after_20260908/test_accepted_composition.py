"""Public-only replay and immutable accepted composition regression tests."""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
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


if __name__=='__main__':
    unittest.main()
