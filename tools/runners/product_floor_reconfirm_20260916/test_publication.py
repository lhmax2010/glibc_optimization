import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('floor_publisher', HERE/'publish_compact.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationTests(unittest.TestCase):
    def test_stopped_connection_retains_lines_and_hashes_without_fake_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root/'source', root/'public'
            (source/'raw').mkdir(parents=True)
            (source/'state.json').write_text(json.dumps({'status': 'STOP', 'reason': 'connection failed'}))
            (source/'raw/connect.txt').write_text('connecting to 192.0.2.1:26101 ...\nfailed to connect to 192.0.2.1:26101\n')
            (source/'raw/s1_smaps.txt').write_text('not a public raw payload')
            mapping, receipt = root/'mapping.tsv', root/'receipt.json'
            mapping.write_text('type\tscope\toriginal\treplacement\n')
            receipt.write_text('{}\n')
            publisher.publish(source, output, mapping, '192.0.2.1', receipt)
            public = (output/'raw/connect.txt').read_text()
            self.assertEqual(public, 'connecting to <PRODUCT_BOARD_IP>:26101 ...\nfailed to connect to <PRODUCT_BOARD_IP>:26101\n')
            self.assertFalse((output/'timeseries.tsv').exists())
            self.assertFalse((output/'raw/s1_smaps.txt').exists())
            files = json.loads((output/'publication.json').read_text())['files']
            for file in files:
                self.assertEqual(file['raw_sha256'], hashlib.sha256((source/file['path']).read_bytes()).hexdigest())
                self.assertEqual(file['public_sha256'], hashlib.sha256((output/file['path']).read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                publisher.publish(source, output, mapping, '192.0.2.1', receipt)

    def test_complete_publication_missing_contract_fields_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'
            source.mkdir()
            (source/'state.json').write_text('{"status":"COMPLETE"}')
            (source/'timeseries.tsv').write_text('sample\ttarget\n0\texample\n')
            with self.assertRaisesRegex(ValueError, 'missing contract columns'):
                publisher.publish(source, root/'public', root/'mapping.tsv', '192.0.2.1', root/'receipt.json')
            self.assertFalse((root/'public').exists())


if __name__ == '__main__':
    unittest.main()
