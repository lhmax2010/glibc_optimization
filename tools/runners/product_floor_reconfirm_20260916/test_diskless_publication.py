import hashlib
import csv
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

    def test_complete_publication_positive_end_to_end(self):
        import test_diskless_analysis
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();(source/'raw').mkdir()
            records=[]
            serial='127.0.0.1:26101'
            for label,operation,uid in (
                ('pre_id_before_root_on','id',5001),('pre_root_on','on',None),
                ('pre_id_after_root_on','id',0),('restore_root_off','off',None),
                ('restore_id_after_root_off','id',5001)):
                raw=(f'uid={uid}(example)\nRC=0\nDONE\n' if uid is not None else 'switched\n').encode()
                (source/'raw'/(label+'.txt')).write_bytes(raw)
                argv=['sdb','-s',serial]+(['shell',r.readonly_body(['id'])] if uid is not None else ['root',operation])
                records.append(dict(label=label,argv=argv,remote_rc=0,ended_utc='synthetic',raw_sha256=hashlib.sha256(raw).hexdigest()))
            (source/'commands.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='COMPLETE',root_off_verified_uid=5001)))
            rows=[]
            for candidate in json.loads(r.SNAPSHOT.read_text())['selected']:
                for row in test_diskless_analysis.DisklessAnalysisTests().rows():
                    row.update(target=candidate['target'],pid=candidate['pid'],start_ticks=candidate['start_ticks'])
                    rows.append(row)
            with (source/'timeseries.tsv').open('w') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
                writer.writeheader();writer.writerows(rows)
            r.old.write_json(source/'summary.json',p.analyze(rows))
            timing=dict(transition=None,batches=[dict(sample=i,start_ns=i*10**9,end_ns=i*10**9+3000000,target_period_s=1) for i in range(601)])
            r.old.write_json(source/'sampling_timing.json',timing)
            mapping=root/'mapping.tsv';mapping.write_text('original\treplacement\tscope\ttype\n')
            receipt=root/'receipt.json';receipt.write_text('{}\n')
            p.publish(source,root/'public',mapping,'127.0.0.1',receipt)
            self.assertEqual(json.loads((root/'public/publication.json').read_text())['status'],'COMPLETE')
            self.assertEqual((root/'public/summary.json').read_bytes(),(source/'summary.json').read_bytes())
            (source/'state.json').write_text(json.dumps(dict(mode='diskless',status='STOP',root_off_verified_uid=5001)))
            raw=b'error: Server is not running\n'
            label='root_s1_p123_before'
            (source/'raw'/(label+'.txt')).write_bytes(raw)
            records.insert(-2,dict(label=label,argv=['sdb','-s',serial,'shell',r.readonly_body(['cat','/proc/123/stat'])],
                                  host_rc=1,proof_error='missing RC',raw_sha256=hashlib.sha256(raw).hexdigest()))
            (source/'commands.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))
            p.publish(source,root/'public_stop',mapping,'127.0.0.1',receipt)
            self.assertEqual((root/'public_stop/raw'/(label+'.txt')).read_bytes(),raw)
