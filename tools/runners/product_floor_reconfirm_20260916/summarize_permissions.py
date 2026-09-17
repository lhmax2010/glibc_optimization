#!/usr/bin/env python3
"""Host-only permission evidence summary; no floor or memory inference."""
import argparse
import collections
import json
from pathlib import Path


def summarize(source):
    permissions=json.loads((source/'permissions.json').read_text())
    commands=[json.loads(s) for s in (source/'commands.jsonl').read_text().splitlines()]
    checks=permissions['checks']
    if len({c['pid'] for c in checks})!=len(checks):
        raise ValueError('duplicate checked PID')
    by_label={c['label']:c for c in commands}
    for check in checks:
        for field,key in [('status','status_rc'),('smaps','smaps_rc')]:
            name=f'permission_{field}_{check["pid"]}'
            if by_label[name]['remote_rc']!=check[key]:
                raise ValueError('permission RC mismatch: '+name)
    return dict(schema='product-floor-permissions-summary.v1',
        commands=len(commands),remote_requests=sum('remote_rc' in c for c in commands),
        maximum_remote_request_bytes=max(len(c['argv'][-1].encode()) for c in commands if 'remote_rc' in c),
        checked_pids=len(checks),readable_pids=[c['pid'] for c in checks if c['readable']],
        reasons=dict(collections.Counter(c.get('reason','readable') for c in checks)),
        smaps_permission_denied_pids=[c['pid'] for c in checks if 'Permission denied' in c['errors'].get('smaps','')],
        exited_or_unavailable_pids=[c['pid'] for c in checks if 'No such file or directory' in c['errors'].get('smaps','')],
        named_exact_pids={a:v['exact_pids'] for a,v in permissions['matching'].items()},
        named_nearby=permissions['matching'],pid1_visible=permissions['pid1_visible'],
        script_pushes=sum('push' in c['argv'][1:4] for c in commands),
        note='Unseen in this restricted view is not proof of process absence; empty smaps is not zero heap PD.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=summarize(args.source)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('PASS permission evidence: checked=%d readable=%d pushes=%d'%(result['checked_pids'],len(result['readable_pids']),result['script_pushes']))


if __name__=='__main__':main()
