import json
from pathlib import Path
import shutil
import tempfile
import unittest

import audit_persistent_stop as audit


class PersistentStopEvidenceTests(unittest.TestCase):
    source=Path(__file__).resolve().parents[3]/'data/raw/product_floor_reconfirm_20260916/persistent_20260918'

    def test_published_stop_replays_exactly_without_board(self):
        result=audit.analyze(self.source)
        self.assertEqual(result,json.loads((self.source/'stop_audit.json').read_text()))
        self.assertEqual(result['completed_points'],0)
        self.assertEqual(result['persistent_sampling_sessions'],0)
        self.assertEqual(result['authorization']['uid_transitions'][-1]['uid'],5001)
        self.assertEqual(result['rediscovery_stat_receipts'],520)

    def test_stop_evidence_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'copy';shutil.copytree(self.source,source)
            (source/'raw/restore_id_after_root_off.txt').write_text('uid=0(root)\nRC=0\nDONE\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                audit.analyze(source)


if __name__=='__main__':unittest.main()
