import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import publish_diskless as p
import run_diskless as r


class PublicationTests(unittest.TestCase):
    def test_stop_without_completed_elevation_still_archivable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp);(source/'raw').mkdir()
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='STOP',root_off_verified_uid=5001)))
            raw=b'uid=5001(owner)\nRC=0\nDONE\n'
            (source/'raw/restore_id_after_root_off.txt').write_bytes(raw)
            record=dict(label='restore_id_after_root_off',argv=['sdb','-s','127.0.0.1:26101','shell',r.readonly_body(['id'])],
                        raw_sha256=hashlib.sha256(raw).hexdigest())
            (source/'commands.jsonl').write_text(json.dumps(record)+'\n')
            self.assertEqual(p.validate(source)['status'],'STOP')
            self.assertEqual(json.loads((source/'authorization_receipt.json').read_text())['status'],'INCOMPLETE_AUTHORIZATION_EVIDENCE')

    def test_mutation_and_corrupt_raw_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp);(source/'raw').mkdir()
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='STOP')))
            raw=b'RC=0\nDONE\n';(source/'raw/command.txt').write_bytes(raw)
            record=dict(label='command',argv=['sdb','-s','127.0.0.1:26101','shell','LC_ALL=C rm /tmp/x'+r.old.single.SUFFIX],
                        raw_sha256=hashlib.sha256(raw).hexdigest())
            (source/'commands.jsonl').write_text(json.dumps(record)+'\n')
            with self.assertRaises(ValueError):p.validate(source)
            record['argv'][-1]=r.readonly_body(['id']);record['raw_sha256']='0'*64
            (source/'commands.jsonl').write_text(json.dumps(record)+'\n')
            with self.assertRaisesRegex(ValueError,'integrity'):p.validate(source)

    def test_complete_without_restore_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='COMPLETE')))
            with self.assertRaisesRegex(ValueError,'restoration'):p.validate(source)

    def test_stop_before_first_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='STOP')))
            self.assertEqual(p.validate(source)['status'],'STOP')
