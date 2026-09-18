import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import audit_full_session_stop as a
import run_full_session as r

SOURCE=a.ROOT/'data/raw/product_floor_reconfirm_20260916/full_session_20260918'


class FullSessionStopTests(unittest.TestCase):
    def test_public_stop_and_contract_byte_hashes(self):
        self.assertEqual(a.audit(SOURCE),json.loads((SOURCE/'stop_receipt.json').read_text()))

    def test_public_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            copy=Path(d)/'copy';shutil.copytree(SOURCE,copy)
            (copy/'raw/reset_start.txt').write_text('server ready\n')
            with self.assertRaisesRegex(ValueError,'hash'):a.audit(copy)

    def test_semantic_start_failure_stops_without_root_or_second_check(self):
        with tempfile.TemporaryDirectory() as d:
            board=r.Transport('127.0.0.1',Path(d)/'out','fake-sdb')
            replies=[b'List of devices attached\n',b'error: target not found\n',b'',b'error: protocol fault: no status\n']
            calls=[]
            def run(argv,**kwargs):
                calls.append(argv)
                return r.subprocess.CompletedProcess(argv,1 if len(calls)==2 else 0,replies[len(calls)-1])
            with mock.patch.object(r.subprocess,'run',side_effect=run),mock.patch.object(r.subprocess,'Popen') as popen:
                state=r.execute(board,{},dict(status='RUNNING',complete_batches=0))
            self.assertEqual(state['status'],'STOP');self.assertIn('reset_start',state['reason'])
            self.assertEqual(len(calls),4);self.assertFalse(popen.called)
            self.assertFalse(any('root' in c for c in calls))


if __name__=='__main__':unittest.main()
