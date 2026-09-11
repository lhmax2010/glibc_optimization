"""Public restricted-audit evidence replay and failure guards; never SDB."""
import hashlib
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
    import analyze_restricted_cleanup as replay

EVIDENCE=HERE.parents[2]/'data/raw/system_level_before_after_20260908/cleanup_restricted_20260911'


class RestrictedCleanupReplay(unittest.TestCase):
    def test_every_original_source_manifest_file_is_git_tracked(self):
        root=HERE.parents[2]
        relative=replay.SOURCE.relative_to(root)
        tracked=set(subprocess.check_output(['git','ls-files','--full-name','--',str(relative)],
            cwd=root,text=True).splitlines())
        for row in json.loads((replay.SOURCE/'manifest.json').read_text())['files']:
            self.assertIn(str(relative/row['path']),tracked,'manifest source missing from clean clone')

    def test_original_stop_replays_byte_exact_without_board_calls(self):
        real_run=subprocess.run
        def git_only(argv,**kwargs):
            self.assertEqual(argv[:2],['git','show'])
            return real_run(argv,**kwargs)
        with mock.patch('subprocess.run',side_effect=git_only):
            self.assertEqual(replay.analyze(EVIDENCE),(EVIDENCE/'host_replay.json').read_text())
        result=json.loads(replay.analyze(EVIDENCE))
        self.assertEqual(result['verdict'],'STOP_NOT_CLEANUP_PASS')
        self.assertEqual((result['path_count'],result['absent_paths']), (2570,2565))
        self.assertEqual((result['root_rounds'],result['root_off_attempts'],result['final_uid']), (1,1,5001))
        self.assertEqual(result['body_max_bytes'],189)

    def mutate(self,name,transform,update_hash=False):
        temporary=tempfile.TemporaryDirectory(prefix='restricted-replay-host-')
        self.addCleanup(temporary.cleanup)
        target=pathlib.Path(temporary.name)/'evidence'
        shutil.copytree(EVIDENCE,target)
        path=target/name
        path.write_text(transform(path.read_text()))
        if update_hash:
            manifest=json.loads((target/'manifest.json').read_text())
            for item in manifest['files']:
                if item['path']==name:
                    item['public_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            (target/'manifest.json').write_text(json.dumps(manifest))
        return target

    def test_corrupted_file_fails_before_interpretation(self):
        target=self.mutate('NONROOT_PATH_2477.txt',lambda text:text+'corruption')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            replay.analyze(target)

    def test_root_missing_pid_one_even_with_updated_manifest_is_rejected(self):
        target=self.mutate('ROOT_PS_START.txt',lambda text:'\n'.join(
            line for line in text.splitlines() if not line.split() or line.split()[0]!='1')+'\n',True)
        with self.assertRaisesRegex(ValueError,'PID 1'):
            replay.analyze(target)

    def test_final_uid_and_root_scope_cannot_be_forged_by_receipt(self):
        target=self.mutate('ROOT_ID_OFF_1.txt',lambda text:text.replace('uid=5001(', 'uid=0('),True)
        with self.assertRaisesRegex(ValueError,'UID proof'):
            replay.analyze(target)
        def outside(text):
            rows=json.loads(text)
            next(r for r in rows if r['label']=='ROOT_TARGET_STAT')['argv'][-1]=replay.request(['cat','/proc/999/stat'])
            return json.dumps(rows)
        target=self.mutate('commands.json',outside,True)
        with self.assertRaisesRegex(ValueError,'outside restricted list'):
            replay.analyze(target)

    def test_nonroot_operation_is_bound_even_if_manifest_updated(self):
        def mutate_command(text):
            rows=json.loads(text)
            next(r for r in rows if r['label']=='NONROOT_DATE')['argv'][-1]=replay.request(['rm','--','/fixture/forbidden'])
            return json.dumps(rows)
        target=self.mutate('commands.json',mutate_command,True)
        with self.assertRaisesRegex(ValueError,'nonroot operation differs'):
            replay.analyze(target)

    def test_extra_unclassified_shell_request_is_rejected(self):
        def add_command(text):
            rows=json.loads(text)
            extra=dict(next(r for r in rows if r['label']=='NONROOT_DATE'))
            extra['label']='UNCLASSIFIED'
            rows.append(extra)
            return json.dumps(rows)
        target=self.mutate('commands.json',add_command,True)
        with self.assertRaisesRegex(ValueError,'unclassified shell label'):
            replay.analyze(target)


if __name__=='__main__':
    unittest.main()
