#!/usr/bin/env python3
"""Host-only audit of the one-round UID transitions and command boundary."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_readonly import single


def audit(source):
    commands=[json.loads(line) for line in (source/'commands.jsonl').read_text().splitlines()]
    labels={c['label']:c for c in commands}
    if len(labels)!=len(commands):raise ValueError('duplicate command label')
    result=dict(schema='product-floor-root-receipt.v1',uid_transitions=[],remote_requests=0,
                maximum_remote_request_bytes=0,root_on_calls=0,root_off_calls=0,script_pushes=0)
    for c in commands:
        argv=c['argv']
        if 'shell' in argv:
            result['remote_requests']+=1
            size=single.check_body(argv[-1])
            result['maximum_remote_request_bytes']=max(result['maximum_remote_request_bytes'],size)
        if argv[-2:]==['root','on']:result['root_on_calls']+=1
        if argv[-2:]==['root','off']:result['root_off_calls']+=1
        if len(argv)>3 and argv[3]=='push':result['script_pushes']+=1
    # Before/after elevation and restoration must all have original RC proof.
    for label,expected in [('pre_id_before_root_on',5001),('pre_id_after_root_on',0),
                           ('restore_id_after_root_off',5001)]:
        c=labels[label]; raw=(source/'raw'/(label+'.txt')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=c['raw_sha256']:
            # Public receipts intentionally redact text. Their public hash is
            # checked against publication.json, never against unredacted hashes.
            manifest=json.loads((source/'publication.json').read_text())
            entry=next(e for e in manifest['files'] if e['path']=='raw/'+label+'.txt')
            if hashlib.sha256(raw).hexdigest()!=entry['public_sha256']:raise ValueError('UID raw hash mismatch')
        rc,text=single.parse(raw.decode())
        match=re.search(r'^uid=(\d+)\(',text)
        if rc or c.get('remote_rc')!=0 or not match or int(match[1])!=expected:
            raise ValueError('UID transition not proven: '+label)
        result['uid_transitions'].append(dict(label=label,uid=expected,ended_utc=c['ended_utc']))
    if result['root_on_calls']!=1 or result['root_off_calls']!=1:
        raise ValueError('authorization transition count differs from one round')
    if not (commands.index(labels['pre_id_before_root_on']) < commands.index(labels['pre_root_on'])
            < commands.index(labels['pre_id_after_root_on']) < commands.index(labels['restore_root_off'])
            < commands.index(labels['restore_id_after_root_off'])):
        raise ValueError('root transition ordering mismatch')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=audit(a.source)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('PASS authorized receipt: UID 5001 -> 0 -> 5001; one root round')


if __name__=='__main__':main()
