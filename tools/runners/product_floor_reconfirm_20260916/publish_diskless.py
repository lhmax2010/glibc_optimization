#!/usr/bin/env python3
"""Validate diskless evidence and publish an alias-only compact receipt."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex

import run_diskless as runner
from analyze_diskless import analyze, validate_timing
from audit_authorized_receipt import audit
from publish_compact import redactor, privacy


def validate(source):
    state = json.loads((source/'state.json').read_text())
    if state.get('mode') != 'diskless' or state.get('status') not in ('STOP','COMPLETE'):
        raise ValueError('invalid diskless terminal state')
    commands = source/'commands.jsonl'
    records = [json.loads(s) for s in commands.read_text().splitlines()] if commands.exists() else []
    if len({r['label'] for r in records}) != len(records):
        raise ValueError('duplicate command labels')
    for r in records:
        path = source/'raw'/(r['label']+'.txt')
        if hashlib.sha256(path.read_bytes()).hexdigest() != r['raw_sha256']:
            raise ValueError('raw command integrity failed: '+r['label'])
        argv = r['argv'][1:]
        if 'shell' in argv:
            body = argv[-1]
            if not body.startswith('LC_ALL=C ') or not body.endswith(runner.old.single.SUFFIX):
                raise ValueError('remote framing differs')
            operation = shlex.split(body[len('LC_ALL=C '):-len(runner.old.single.SUFFIX)])
            if runner.readonly_body(operation) != body:
                raise ValueError('noncanonical readonly operation')
        elif not (argv in (['version'],['devices']) or len(argv)==2 and argv[0]=='connect'
                  or len(argv)==4 and argv[0]=='-s' and argv[2:] in (['root','on'],['root','off'])):
            raise ValueError('board mutation/file transfer found')
    if state.get('root_off_verified_uid') == 5001:
        try:
            receipt = audit(source)
        except (KeyError, ValueError, FileNotFoundError) as error:
            if state['status'] == 'COMPLETE':
                raise
            receipt = dict(status='INCOMPLETE_AUTHORIZATION_EVIDENCE',reason=str(error),
                           terminal_status='STOP',script_pushes=0)
        if receipt['script_pushes']:
            raise ValueError('diskless run pushed a file')
        runner.old.write_json(source/'authorization_receipt.json', receipt)
    if state['status'] == 'COMPLETE':
        if state.get('root_off_verified_uid') != 5001:
            raise ValueError('root restoration unproved')
        with (source/'timeseries.tsv').open() as stream:
            rows = [{k:v if k=='target' else int(v) for k,v in row.items()} for row in csv.DictReader(stream,delimiter='\t')]
        if analyze(rows) != json.loads((source/'summary.json').read_text()):
            raise ValueError('summary mismatch')
        validate_timing(rows,json.loads((source/'sampling_timing.json').read_text()))
    return state


def publish(source, output, mapping, address, receipt):
    state = validate(source)
    if output.exists():
        raise ValueError('refusing publication overwrite')
    clean = redactor(mapping,address)
    files = [p for p in source.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.tsv')]
    files += [p for p in (source/'raw').glob('*.txt') if not re.match(r'root_s\d+_',p.stem)]
    if state['status'] == 'STOP' and (source/'commands.jsonl').exists():
        for line in (source/'commands.jsonl').read_text().splitlines():
            record = json.loads(line)
            path = source/'raw'/(record['label']+'.txt')
            if (record.get('proof_error') or record.get('host_rc') or record.get('remote_rc', 0)) and path.stat().st_size <= 16384:
                files.append(path)
    files = sorted(set(files))
    output.mkdir(parents=True)
    manifest=[]
    for path in files:
        raw=path.read_bytes(); text=clean(raw.decode())
        if privacy.find_endpoints(text):
            raise ValueError('redaction failed')
        relative=path.relative_to(source);dest=output/relative
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        if path.suffix in ('.json','.jsonl'):
            for value in text.splitlines() if path.suffix=='.jsonl' else [text]:
                json.loads(value)
        manifest.append(dict(path=str(relative),raw_sha256=hashlib.sha256(raw).hexdigest(),
                             public_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),redacted=raw!=dest.read_bytes()))
    (output/'contract_push.json').write_text(clean(receipt.read_text()))
    runner.old.write_json(output/'publication.json',dict(schema='product-floor-diskless-publication.v1',
        status=state['status'],files=manifest,policy='Full smaps/local raw retained on host, available on request; aliases and host paths redacted; board paths retained.'))
    print('PASS diskless publication: '+state['status']+' files='+str(len(manifest)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','mapping','receipt'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ip',required=True)
    a=p.parse_args();publish(a.source,a.output,a.mapping,a.ip,a.receipt)
