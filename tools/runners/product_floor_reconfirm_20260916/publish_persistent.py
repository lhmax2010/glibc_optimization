#!/usr/bin/env python3
"""Validate local stream against derived rows; publish alias-only compact evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex

import run_persistent as runner
from analyze_persistent import Parser, analyze
from analyze_floor import proc_stat
from audit_authorized_receipt import audit
from publish_compact import redactor, privacy


def validate(source):
    state=json.loads((source/'state.json').read_text())
    if state.get('mode')!='persistent' or state.get('status') not in ('STOP','COMPLETE') or state.get('board_files_created')!=0:
        raise ValueError('invalid persistent terminal state')
    command_file=source/'commands.jsonl'
    records=[json.loads(s) for s in command_file.read_text().splitlines()] if command_file.exists() else []
    if len({r['label'] for r in records})!=len(records):raise ValueError('duplicate command')
    for r in records:
        raw=(source/'raw'/(r['label']+'.txt')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['raw_sha256']:raise ValueError('raw command hash mismatch')
        argv=r['argv'][1:]
        if 'shell' in argv:
            body=argv[-1]
            if not body.startswith('LC_ALL=C ') or not body.endswith(runner.old.single.SUFFIX):raise ValueError('request framing')
            operation=shlex.split(body[9:-len(runner.old.single.SUFFIX)])
            if runner.readonly_body(operation)!=body:raise ValueError('unapproved board operation')
        elif not (argv in (['version'],['devices'],['kill-server'],['start-server']) or
                  len(argv)==2 and argv[0]=='connect' or
                  len(argv)==4 and argv[0]=='-s' and argv[2:] in (['root','on'],['root','off'])):
            raise ValueError('unapproved SDB operation')
    if sum(r['argv'][-1]=='kill-server' for r in records)>1 or sum(r['argv'][-1]=='start-server' for r in records)>1:
        raise ValueError('more than one connectivity reset')
    if state.get('root_off_verified_uid')==5001:
        runner.old.write_json(source/'authorization_receipt.json',audit(source))
    stream_path=source/'stream_state.json'
    if stream_path.exists():
        stream=json.loads(stream_path.read_text())
        raw=(source/'stream.raw').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=stream['stream_sha256']:raise ValueError('stream hash differs')
        candidates=json.loads((source/'candidates.json').read_text())['selected']
        text=runner.program(stream['nonce'],candidates)
        if (source/'stdin_program.txt').read_bytes()!=text.encode() or hashlib.sha256(text.encode()).hexdigest()!=stream['stdin_sha256']:
            raise ValueError('stdin program differs from readonly generator')
        serials={r['argv'][2] for r in records if len(r['argv'])>3 and r['argv'][1]=='-s'}
        if len(stream['argv'])!=4 or stream['argv'][1]!='-s' or stream['argv'][3]!='shell' or serials!={stream['argv'][2]}:
            raise ValueError('sampling is not one interactive shell')
        markers=[json.loads(s) for s in (source/'markers.jsonl').read_text().splitlines()]
        parser=Parser(stream['nonce'],candidates)
        mi=0;parse_error=None
        try:
            for line in raw.decode().splitlines():
                # Host records times only for exact marker lines; data lines use
                # the last receipt clock (they do not define measurement time).
                if line.startswith('===') and line.endswith('==='):
                    if mi>=len(markers) or markers[mi]['line']!=line:raise ValueError('marker transcript mismatch')
                    mark=markers[mi];mi+=1
                else:mark=markers[max(0,mi-1)] if markers else dict(host_epoch_ns=0,host_monotonic_ns=0)
                parser.feed(line,mark['host_epoch_ns'],mark['host_monotonic_ns'])
        except ValueError as error:
            parse_error=str(error)
        with (source/'timeseries.tsv').open() as f:
            rows=[{k:v if k=='target' else int(v) for k,v in row.items()} for row in csv.DictReader(f,delimiter='\t')]
        if rows!=parser.rows or len(parser.batches)!=stream['complete_batches']:
            raise ValueError('derived rows differ from recorded stream')
        if state['status']=='COMPLETE':
            if parse_error or mi!=len(markers) or not parser.final or stream['host_rc']!=0:
                raise ValueError('stream completion proof failed')
            if analyze(rows,candidates)!=json.loads((source/'summary.json').read_text()):raise ValueError('summary differs')
    if state['status']=='COMPLETE' and (state.get('root_off_verified_uid')!=5001 or not stream_path.exists()):
        raise ValueError('completion lacks stream/root restoration proof')
    return state


def publish(source,output,mapping,address,receipt):
    state=validate(source)
    if output.exists():raise ValueError('refusing publication overwrite')
    clean=redactor(mapping,address)
    files=[p for p in source.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.tsv')]
    known={c['comm'] for c in json.loads(runner.SNAPSHOT.read_text())['selected']}
    # Repeated system-wide stat queries are an incident, not a time series.
    # Keep every command/hash locally; publish identity/baseline, matching
    # candidate records and errors, not hundreds of unrelated kernel tasks.
    for path in (source/'raw').glob('*.txt'):
        if re.fullmatch(r'root_rediscover_\d+_\d+',path.stem):
            rc,value=runner.old.single.parse(path.read_text())
            if not rc and clean(proc_stat(value)['comm']) not in known:
                continue
        files.append(path)
    if state['status']=='STOP' and (source/'stream.raw').exists():
        raw=(source/'stream.raw').read_bytes()
        # Large smaps transcript stays local; preserve failure tail verbatim.
        (source/'stream_tail.txt').write_bytes(raw[-16384:])
        files.append(source/'stream_tail.txt')
    output.mkdir(parents=True)
    manifest=[]
    for path in sorted(files):
        raw=path.read_bytes();text=clean(raw.decode(errors='replace'))
        if privacy.find_endpoints(text):raise ValueError('redaction failed')
        relative=path.relative_to(source);dest=output/relative
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        if path.suffix in ('.json','.jsonl'):
            for value in text.splitlines() if path.suffix=='.jsonl' else [text]:json.loads(value)
        manifest.append(dict(path=str(relative),raw_sha256=hashlib.sha256(raw).hexdigest(),
                             public_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),redacted=raw!=dest.read_bytes()))
    (output/'contract_push.json').write_text(clean(receipt.read_text()))
    runner.old.write_json(output/'publication.json',dict(schema='product-floor-persistent-publication.v1',
        status=state['status'],files=manifest,
        policy='Full stream and original identifiers retained locally, available on request. Public files use established aliases; board paths retained.'))
    print('PASS persistent publication: '+state['status']+' files='+str(len(manifest)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','mapping','receipt'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ip',required=True)
    args=p.parse_args();publish(args.source,args.output,args.mapping,args.ip,args.receipt)
