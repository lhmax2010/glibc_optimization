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
    def test_dependency_stop_publishes_exact_remote_failure_without_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root/'source', root/'public'
            (source/'raw').mkdir(parents=True)
            (source/'state.json').write_text(json.dumps({
                'status': 'STOP', 'reason': 'STOP remote command failed: timeout_path RC=1'}))
            (source/'cleanup.json').write_text('[]\n')
            raw = {'timeout_path': '\nRC=1\nFAIL\n',
                   'vk_send_path': '/usr/bin/vk_send\n\nRC=0\nDONE\n',
                   'rpm_dbpath': '/var/lib/rpm\n\nRC=0\nDONE\n',
                   'shell_status': 'CapEff:\t0000000000000000\n\nRC=0\nDONE\n'}
            for name, body in raw.items():
                (source/'raw'/f'{name}.txt').write_text(body)
            mapping, receipt = root/'mapping.tsv', root/'receipt.json'
            mapping.write_text('type\tscope\toriginal\treplacement\n')
            receipt.write_text('{}\n')
            publisher.publish(source, output, mapping, '192.0.2.1', receipt)
            for name, body in raw.items():
                self.assertEqual((output/'raw'/f'{name}.txt').read_text(), body)
            self.assertEqual(json.loads((output/'cleanup.json').read_text()), [])
            for name in ('timeseries.tsv', 'summary.json', 'inventory.json', 'owned_scripts.json'):
                self.assertFalse((output/name).exists())

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
