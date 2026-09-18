#!/usr/bin/env python3
"""Audit local raw frames, then publish compact alias-only evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

import run_full_session as runner
from analyze_full_session import replay, select_candidates
from publish_compact import redactor, privacy


def read_jsonl(path):
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []


def validate(source):
    state=json.loads((source/'state.json').read_text())
    if state['status'] not in ('COMPLETE','STOP'):raise ValueError('nonterminal state')
    intents=read_jsonl(source/'intents.jsonl');commands=read_jsonl(source/'commands.jsonl')
    for c in commands:
        if hashlib.sha256((source/'raw'/(c['label']+'.txt')).read_bytes()).hexdigest()!=c['raw_sha256']:
            raise ValueError('raw command hash mismatch')
    work=[i for i in intents if i['label']=='working_session']
    shells=[i for i in intents if 'shell' in i['argv'][1:]]
    shorts=[i for i in shells if i['label']!='working_session']
    if len(work)>1 or len(shorts)>3:raise ValueError('extra shell connections')
    for s in shorts:
        if s['label'] not in ('selfcheck_0','selfcheck_1','id_after_root_off') or s['argv'][-1]!=runner.old.readonly_body(['id']):
            raise ValueError('unapproved short shell')
    for c in intents:
        args=c['argv'][1:]
        if 'shell' not in args and not (args in (['devices'],['kill-server'],['start-server']) or
             len(args)==2 and args[0]=='connect' or len(args)==4 and args[0]=='-s' and args[2:] in (['root','on'],['root','off'])):
            raise ValueError('unapproved SDB operation')
    if work:
        pos=intents.index(work[0])
        if [i['label'] for i in intents[pos+1:]]!=['root_off','id_after_root_off']:
            raise ValueError('non-restoration operation after working session')
    frames=read_jsonl(source/'frames.jsonl')
    if frames:
        if len(work)!=1 or frames[0]['label']!='root_id':raise ValueError('missing root-first session')
        nonce=work[0]['nonce'];raw=(source/'stream.raw').read_text().replace('\r','')
        matches=list(re.finditer(r'^===BEGIN '+nonce+r' (\w+) (\d+)===\n(.*?)\n===END '+nonce+r' \1 RC=(\d+) (DONE|FAIL) (\d+)===',raw,re.M|re.S))
        if len(matches)!=len(frames):raise ValueError('raw/frame count mismatch')
        for m,f in zip(matches,frames):
            if (m[1],int(m[2])*10**9,m[3].strip(),int(m[4]),int(m[6])*10**9)!=(
                    f['label'],f['board_epoch_ns'],f['text'],f['rc'],f['board_end_ns']):
                raise ValueError('raw/frame content mismatch')
            if m[5]!=('DONE' if f['rc']==0 else 'FAIL'):raise ValueError('RC flag mismatch')
        runner.bounded((source/'stdin_program.txt').read_text())
        invframes=[f for f in frames if re.fullmatch(r'inv(stat|smaps|after)_\d+',f['label'])]
        if (source/'inventory.json').exists():
            inventory=runner.parse_inventory(invframes)
            if inventory!=json.loads((source/'inventory.json').read_text()):raise ValueError('inventory differs')
        if (source/'candidates.json').exists():
            roster=json.loads((source/'candidates.json').read_text())
            candidates=select_candidates(inventory,roster['primary_names'],roster['observer_pid'])
            if candidates!=roster['selected']:raise ValueError('candidate selection differs')
            rows=[];batches=[];events=[];retired=set();pending=[];sampling=False
            for f in frames:
                if f['label']=='sample_0':sampling=True
                if f['label']=='sampling_final':sampling=False
                if sampling:
                    pending.append(f)
                    if f['label'].startswith('batch_end_'):
                        rs,b,ev=runner.parse_batch(pending,candidates,retired,len(batches));pending=[]
                        rows+=rs;batches.append(b);events+=ev;retired.update(e['pid'] for e in ev)
            if (source/'timeseries.tsv').exists():
                with (source/'timeseries.tsv').open() as f:
                    recorded=[{k:v if k=='target' else int(v) for k,v in row.items()} for row in csv.DictReader(f,delimiter='\t')]
                if rows!=recorded:raise ValueError('timeseries differs from frames')
                for name,value in [('batches',batches),('events',events)]:
                    if value!=json.loads((source/(name+'.json')).read_text()):raise ValueError(name+' differs from frames')
    if state['status']=='COMPLETE':
        for key,uid in [('id_before_root_on',5001),('id_after_root_on',0),('id_after_root_off',5001)]:
            runner.require_uid(state[key],uid)
        if frames[-1]['label']!='work_final' or frames[-1]['rc'] or any(f['rc'] for f in frames if f['label'] in ('root_id','sampling_final','work_final')):
            raise ValueError('final remote proof missing')
        exit_state=json.loads((source/'session_exit.json').read_text())
        if exit_state['host_rc'] or not exit_state['normal']:raise ValueError('transport completion failed')
        if replay(source)!=json.loads((source/'summary.json').read_text()):raise ValueError('summary mismatch')
    return dict(status=state['status'],working_sessions=len(work),short_id_queries=len(shorts),
                completed_batches=state['complete_batches'],raw_frames=len(frames),
                board_file_writes=0,board_sampling_retries=0,
                id_after_root_off=state.get('id_after_root_off'),reason=state.get('reason'))


def publish(source,output,mapping,address):
    receipt=validate(source)
    if output.exists():raise ValueError('refusing overwrite')
    clean=redactor(mapping,address)
    names=('state.json','contract_push.json','contract_gate.json','intents.jsonl','commands.jsonl',
           'session_exit.json','baseline.json','inventory.json','candidates.json','timeseries.tsv',
           'batches.json','events.json','summary.json','cleanup.json')
    paths=[source/n for n in names if (source/n).exists()]+list((source/'raw').glob('*.txt'))
    # Publish complete identity/capability/control frames; smaps stream stays local.
    selected=[f for f in read_jsonl(source/'frames.jsonl') if not re.match(r'(inv|sample_|mem_|zram_|swaps_|before_|smaps_|after_|gone_|batch_end_)',f['label'])]
    runner.old.write_json(source/'control_frames.json',selected);paths.append(source/'control_frames.json')
    if receipt['status']=='STOP' and (source/'stream.raw').exists():
        (source/'stream_tail.txt').write_bytes((source/'stream.raw').read_bytes()[-16384:]);paths.append(source/'stream_tail.txt')
    output.mkdir(parents=True);manifest=[]
    for path in sorted(paths):
        raw=path.read_bytes();text=clean(raw.decode(errors='strict'));rel=path.relative_to(source)
        if privacy.find_endpoints(text):raise ValueError('privacy scan failed')
        dest=output/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        manifest.append(dict(path=str(rel),raw_sha256=hashlib.sha256(raw).hexdigest(),
                             public_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),redacted=raw!=dest.read_bytes()))
    (output/'audit.json').write_text(clean(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n'))
    runner.old.write_json(output/'publication.json',dict(schema='product-floor-full-session-publication.v1',files=manifest,
                         local_stream_sha256=hashlib.sha256((source/'stream.raw').read_bytes()).hexdigest() if (source/'stream.raw').exists() else None,
                         policy='Original command receipts retained locally, available on request; a full stream is retained only if a working session was created. Host paths and private identifiers redacted, board paths retained.'))
    if receipt['status']=='COMPLETE':
        if replay(output)!=json.loads((output/'summary.json').read_text()):raise ValueError('public replay differs')
    print('PASS full-session publication: '+receipt['status']+' files='+str(len(paths)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','mapping'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ip',required=True)
    a=p.parse_args();publish(a.source,a.output,a.mapping,a.ip)
