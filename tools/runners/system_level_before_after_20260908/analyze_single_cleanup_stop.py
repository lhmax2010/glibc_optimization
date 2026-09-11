#!/usr/bin/env python3
"""Host-only transcription checks for the 2026-09-11 STOP; never invokes SDB."""
import argparse
import hashlib
import json
import pathlib

from audit_single_cleanup_20260911 import SOURCE, process_check
from audit_cleanup_20260911 import health_delta
from single_request import check_body, parse


def analyze(directory):
    for row in json.loads((directory/'manifest.json').read_text())['files']:
        assert hashlib.sha256((directory/row['path']).read_bytes()).hexdigest() == row['public_sha256']
    audit=json.loads((directory/'audit.json').read_text())
    assert audit['verdict']=='STOP' and audit['reason']=='process table missing PID 1'
    commands=json.loads((directory/'commands.json').read_text())
    shell=[c for c in commands if 'shell' in c['argv']]
    sizes=[check_body(c['argv'][-1]) for c in shell]
    results={c['label']:parse((directory/(c['label']+'.txt')).read_text()) for c in shell}
    assert results['NONROOT_PS_START'][0]==0
    table=results['NONROOT_PS_START'][1]
    pids=[int(line.split()[0]) for line in table.splitlines()[1:]]
    try:
        process_check(table)
    except ValueError as error:
        assert str(error)==audit['reason']
    else:
        raise AssertionError('incomplete process list falsely accepted')
    prior=json.loads((SOURCE/'execution.json').read_text())
    assert results['NONROOT_BOOT_START']==(0,prior['preflight']['boot_id'])
    increment=health_delta((SOURCE/'raw/round_health/dmesg_before.txt').read_text(),
        results['NONROOT_DMESG_START'][1], (SOURCE/'raw/round_health/zram_before.txt').read_text(),
        results['NONROOT_ZRAM_START'][1])
    assert all(c['argv'][0]=='sdb' for c in commands)
    assert not any('root' in c['argv'] for c in commands)
    assert all(audit[key]==0 for key in ('measurement_cells_run','board_files_pushed',
        'packages_changed','governor_writes','processes_terminated'))
    assert results['NONROOT_ID_BEFORE'][1].startswith('uid=5001(')
    assert results['NONROOT_ID_FINAL'][1].startswith('uid=5001(')
    summary=dict(verdict='STOP_NOT_CLEANUP_PASS',commands=len(commands),shell_requests=len(shell),
        body_min_bytes=min(sizes),body_max_bytes=max(sizes),remote_rc_zero=sum(r[0]==0 for r in results.values()),
        ps_remote_rc=0,ps_rows=len(pids),pid_1_visible=1 in pids,
        prior_target_visible=prior['preflight']['enlightenment_pid'] in pids,
        dmesg_prefix_retained=True,dmesg_increment_lines=len(increment),oom_lmk_increment=0,
        zram_three_delta=[0,0,0],permission_denied_labels=sorted(audit['permission_denied_items']),
        nonroot_sweep_complete=False,root_rounds=0,final_uid=5001,accepted_cells_rerun=0)
    return json.dumps(summary,indent=2)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path)
    args=parser.parse_args()
    text=analyze(args.directory)
    if args.output:
        if args.output.exists():
            parser.error('refuse to overwrite prior output')
        args.output.write_text(text)
    print(text,end='')
