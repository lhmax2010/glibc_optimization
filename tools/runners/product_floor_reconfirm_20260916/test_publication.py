import hashlib
import csv
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
    def test_portable_complete_timing_summary_and_cleanup_are_hard_gates(self):
        import sys
        sys.path.insert(0,str(HERE))
        from analyze_floor import analyze
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';(source/'raw').mkdir(parents=True)
            (source/'state.json').write_text('{"status":"COMPLETE"}')
            rows=[dict(sample=i,epoch_ns=i*1000000000,target='Example',pid=1,start_ticks=123,
                       glibc_heap_pd_kb=20,other_anon_pd_kb=4,file_backed_pd_kb=2,total_pd_kb=26,
                       minflt=i,majflt=0,MemAvailable_kb=1000,zram_used_kb=0,zram_orig_bytes=0,
                       zram_compr_bytes=0,zram_mem_used_bytes=0) for i in range(601)]
            with (source/'timeseries.tsv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)
            timing=[dict(sample=i,deadline_mono_ns=i*1000000000,begin_mono_ns=i*1000000000,
                         end_mono_ns=i*1000000000+10000000) for i in range(601)]
            (source/'sampling_timing.json').write_text(json.dumps(timing))
            summary=analyze(rows);(source/'summary.json').write_text(json.dumps(summary))
            owned=[dict(path='/tmp/pf_20260916_0123456789ab.sh',sha256='a'*64)]
            (source/'owned_scripts.json').write_text(json.dumps(owned))
            (source/'cleanup.json').write_text(json.dumps([dict(owned[0],absent=True)]))
            mapping,receipt=root/'mapping.tsv',root/'receipt.json'
            mapping.write_text('type\tscope\toriginal\treplacement\n');receipt.write_text('{}\n')
            publisher.publish(source,root/'pass',mapping,'192.0.2.1',receipt)
            timing[10]['end_mono_ns']+=1000000000
            (source/'sampling_timing.json').write_text(json.dumps(timing))
            with self.assertRaisesRegex(ValueError,'cadence'):
                publisher.publish(source,root/'bad_timing',mapping,'192.0.2.1',receipt)
            timing[10]['end_mono_ns']-=1000000000
            (source/'sampling_timing.json').write_text(json.dumps(timing))
            (source/'summary.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'summary mismatch'):
                publisher.publish(source,root/'bad_summary',mapping,'192.0.2.1',receipt)
            (source/'summary.json').write_text(json.dumps(summary))
            (source/'cleanup.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'cleanup unproven'):
                publisher.publish(source,root/'bad_cleanup',mapping,'192.0.2.1',receipt)

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
