#!/usr/bin/env python3
"""Replay published STOP evidence; never promote partial reads to a profile."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import run_persistent as r
from analyze_floor import proc_stat
from audit_authorized_receipt import audit


def analyze(source):
    state=json.loads((source/'state.json').read_text())
    if state['status']!='STOP' or state['mode']!='persistent':raise ValueError('not this STOP receipt')
    manifest=json.loads((source/'publication.json').read_text())
    for f in manifest['files']:
        if hashlib.sha256((source/f['path']).read_bytes()).hexdigest()!=f['public_sha256']:
            raise ValueError('public hash mismatch: '+f['path'])
    auth=audit(source)
    commands=[json.loads(s) for s in (source/'commands.jsonl').read_text().splitlines()]
    snapshot=json.loads(r.SNAPSHOT.read_text())['selected']
    stats={}
    for path in sorted((source/'raw').glob('root_rediscover_449_*.txt')):
        rc,body=r.old.single.parse(path.read_text())
        if not rc:
            st=proc_stat(body)
            stats.setdefault(st['comm'],[]).append((path,st))
    observed=[]
    uptime=float(json.loads((source/'baseline.json').read_text())['proc_uptime'][1].split()[0])
    for c in snapshot:
        match=stats.get(c['comm'],[])
        fact=dict(target=c['target'],comm=c['comm'],prior_pid=c['pid'],prior_start_ticks=c['start_ticks'],
                  status='OBSERVED_IN_DISCOVERY' if len(match)==1 else 'NOT_CONFIRMED')
        if len(match)==1:
            path,st=match[0]
            fact.update(pid=st['pid'],start_ticks=st['start_ticks'],
                        elapsed_s_at_baseline=uptime-st['start_ticks']/250,
                        evidence=str(path.relative_to(source)))
        observed.append(fact)
    # No stream was opened in this incident. Reject accidental use on another
    # attempt rather than incorrectly classifying a partially sampled stream.
    if (source/'stream_state.json').exists() or (source/'timeseries.tsv').exists():
        raise ValueError('unexpected stream in pre-sampling STOP')
    return dict(schema='persistent-presampling-stop.v1',status='STOP',
                reason_code='STOP_DISCOVERY_SHORT_CONNECTION_REGRESSION',
                original_reason=state['reason'],completed_sdb_receipts=len(commands),
                rediscovery_stat_receipts=sum(bool(re.fullmatch(r'root_rediscover_\d+_\d+',x['label'])) for x in commands),
                server_resets=sum(x['argv'][-1]=='kill-server' for x in commands),
                persistent_sampling_sessions=0,nominal_points=601,completed_points=0,
                authorization=auth,candidates=observed,
                accounting='Completed receipts only; interrupt may leave one started query without a completed receipt. No board reconnect or rerun after STOP.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=analyze(args.source)
    r.old.write_json(args.output,result)
    print('PASS persistent STOP audit: completed_points=0; UID 5001 -> 0 -> 5001; no stream/no retry')
