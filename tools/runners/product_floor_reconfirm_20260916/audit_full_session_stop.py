#!/usr/bin/env python3
"""Offline audit of the pre-elevation connectivity stop; no tag dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]


def audit(source):
    publication=json.loads((source/'publication.json').read_text())
    for item in publication['files']:
        path=source/item['path']
        if not path.resolve().is_relative_to(source.resolve()):raise ValueError('unsafe public path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['public_sha256']:raise ValueError('public hash mismatch')
    state=json.loads((source/'state.json').read_text())
    gate=json.loads((source/'contract_gate.json').read_text())
    if state['status']!='STOP' or state['complete_batches']!=0 or not state['reason'].endswith('reset_start'):
        raise ValueError('not expected connectivity stop')
    if gate['interval_seconds']<600:raise ValueError('contract interval too short')
    for path,expected in gate['files_sha256'].items():
        try:raw=subprocess.check_output(['git','-C',str(ROOT),'show',gate['commit']+':'+path],stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            raise ValueError('contract commit unavailable; git fetch --no-tags origin '+gate['commit']) from error
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('contract file hash mismatch')
    commands=[json.loads(s) for s in (source/'commands.jsonl').read_text().splitlines()]
    intents=[json.loads(s) for s in (source/'intents.jsonl').read_text().splitlines()]
    expected=['devices_0','selfcheck_0','reset_kill','reset_start']
    if [c['label'] for c in commands]!=expected or [i['label'] for i in intents]!=expected:
        raise ValueError('unexpected operation after stop')
    if 'target not found' not in (source/'raw/selfcheck_0.txt').read_text():raise ValueError('missing target failure')
    if (source/'raw/reset_start.txt').read_text().strip()!='error: protocol fault: no status':
        raise ValueError('missing server protocol failure')
    if commands[-1]['host_rc']!=0:raise ValueError('expected semantic failure despite RC0')
    if json.loads((source/'control_frames.json').read_text())!=[]:raise ValueError('unexpected working frame')
    return dict(schema='full-session-connectivity-stop.v1',status='STOP',reason='STOP_SDB_SERVER_PROTOCOL_FAULT',
                source_commit=state['source_commit'],contract_commit=gate['commit'],
                contract_push_interval_seconds=gate['interval_seconds'],
                completed_sdb_commands=4,server_reset_attempts=1,connect_calls=0,
                short_id_attempts=1,working_sessions=0,completed_points=0,
                root_on_calls=0,root_off_calls=0,uid_proven_this_round=False,
                identity_proven_this_round=False,board_file_writes=0,
                limitation='No board identity or floor observation; local server failure does not establish device state.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit(a.source)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS full-session STOP audit: 0 working sessions; 0 points; 0 elevation; one server reset failed')
