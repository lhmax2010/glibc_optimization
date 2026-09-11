#!/usr/bin/env python3
"""Recompute the terminal restricted-audit STOP, offline; no board operations."""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import re

from audit_restricted_resume_20260911 import previous_checks, process_rows, REUSE
from audit_single_cleanup_20260911 import sources, SOURCE, GDB_NAMES, ANALYSIS, WORK, BOOT
from audit_cleanup_20260911 import health_delta
from single_request import check_body, parse, request, absent


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def analyze(directory):
    directory=pathlib.Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    for row in manifest['files']:
        p=directory/row['path']
        require(not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==row['public_sha256'],
            'audit source hash mismatch: '+row['path'])
    audit=json.loads((directory/'audit.json').read_text())
    require(audit['verdict']=='STOP' and audit['end_utc'], 'expected terminal STOP')
    commands=json.loads((directory/'commands.json').read_text())
    require(len({c['label'] for c in commands})==len(commands), 'duplicate command label')
    shell=[c for c in commands if 'shell' in c['argv']]
    require(all(c['label'].startswith(('NONROOT_','ROOT_')) for c in shell),
        'unclassified shell label')
    sizes=[check_body(c['argv'][-1]) for c in shell]
    results={c['label']:parse((directory/(c['label']+'.txt')).read_text()) for c in shell}
    prior,paths,inventory=sources()
    _,cached=previous_checks()
    require(set(audit['reused_nonroot_checks'])==set(REUSE), 'reused checks differ')
    require(not any('NONROOT_'+label in results for label in REUSE), 'successful check repeated')
    require(audit['source_execution_sha256']==hashlib.sha256((SOURCE/'execution.json').read_bytes()).hexdigest(),
        'G4 source binding mismatch')
    pending=json.loads((directory/'permission_denied.json').read_text())
    require(pending==audit['permission_denied_items'], 'root list changed')
    allowed={label:request(item['argv']) for label,item in pending.items()}
    nonroot={'ID_BEFORE':['id'],'ID_BEFORE_ROOT':['id'], 'DF_ROOT':['df','-k','/'],
        'DF_OPTUSR':['df','-k','/opt/usr'],'DATE':['date','-u'],'UPTIME':['uptime'],
        'SWAPS':['cat','/proc/swaps'],'TCP4':['cat','/proc/net/tcp'],'TCP6':['cat','/proc/net/tcp6'],
        'PACKAGES':['rpm','-qa','--queryformat','%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\\n'],
        'BOOT_END':['cat',BOOT],'DMESG_END':['dmesg'],'ZRAM_END':['cat','/sys/block/zram0/mm_stat']}
    for n in range(4):
        nonroot['GOV_%d'%n]=['cat','/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor'%n]
    for name in GDB_NAMES:
        nonroot['ABSENT_'+name]=['rpm','-q',name]
    for label,path in (('WORK',WORK),('WORK_PARENT','/opt/usr/glibc_memopt')):
        nonroot[label]=['stat','-c','%F|%s|%Y|%u:%g','--',path]
    for label,path in (('TOP_TMP','/tmp'),('TOP_HOME','/home'),('TOP_OPTUSR','/opt/usr')):
        nonroot[label]=['ls','-A','--',path]
    for i,path in enumerate(paths):
        label='PATH_%04d'%i
        nonroot[label]=['stat','-c','%F|%s|%Y|%u:%g','--',path]
        if results['NONROOT_'+label][0]==0:
            nonroot[label+'_OWNER']=['rpm','-qf','--',path]
    require({c['label'] for c in shell if c['label'].startswith('NONROOT_')}==
        {'NONROOT_'+label for label in nonroot}, 'nonroot command set differs')
    for c in shell:
        require(c['argv'][:4]==['sdb','-s','<TEST_BOARD_IP>:26101','shell'], 'unexpected transport')
        if c['label'].startswith('NONROOT_'):
            require(c['argv'][-1]==request(nonroot[c['label'][8:]]), 'nonroot operation differs')
    require([c['argv'] for c in commands if 'shell' not in c['argv']]==[
        ['sdb','version'],['sdb','connect','<TEST_BOARD_IP>'],
        ['sdb','-s','<TEST_BOARD_IP>:26101','root','on'],
        ['sdb','-s','<TEST_BOARD_IP>:26101','root','off']], 'unexpected non-shell operation')
    root_shell=[c for c in shell if c['label'].startswith('ROOT_')]
    for c in root_shell:
        label=c['label'][5:]
        expected=request(['id']) if label in ('ID_ROOT','ID_OFF_1') else allowed.get(label)
        require(c['argv'][-1]==expected, 'root command outside restricted list')
    require([c['label'] for c in commands if c['argv'][-2:]==['root','on']]==['ROOT_ON'], 'root-on count')
    require([c['label'] for c in commands if c['argv'][-2:]==['root','off']]==['ROOT_OFF_1'], 'root-off count')
    require(commands[-1]['label']=='ROOT_ID_OFF_1', 'unexpected operation after root-off proof')
    for label,uid in (('NONROOT_ID_BEFORE',5001),('NONROOT_ID_BEFORE_ROOT',5001),
                      ('ROOT_ID_ROOT',0),('ROOT_ID_OFF_1',5001)):
        require(results[label][0]==0 and results[label][1].startswith('uid=%d('%uid), 'UID proof mismatch')
    require(audit['root_authorization']['root_off']=='PASS_NONROOT', 'root restoration not verified')
    require(all(audit[k]==0 for k in ('measurement_cells_run','board_files_pushed','packages_changed',
        'governor_writes','processes_terminated')), 'unexpected mutation')
    views={}
    for when in ('START','END'):
        rc,text=results['ROOT_PS_'+when]
        require(rc==0, 'process read failed')
        rows,_=process_rows(text)
        require(498 in rows and rows[498]['comm']=='enlightenment', 'original target not visible')
        views[when]=dict(rows=len(rows),pid_1=True,original_target_visible=True)
        require(results['ROOT_ALERTS_'+when]==(0,''), 'nonempty or failed alert listing')
    stat=ANALYSIS.proc_stat(results['ROOT_TARGET_STAT'][1])
    require(results['ROOT_TARGET_STAT'][0]==0 and stat['pid']==498 and
        stat['starttime']==prior['target_starttime'], 'target identity changed')
    require(results['NONROOT_BOOT_END']==(0,prior['preflight']['boot_id']), 'boot changed')
    increments={}
    for when in ('START','END'):
        dm=cached['DMESG_START'][1] if when=='START' else results['NONROOT_DMESG_END']
        zr=cached['ZRAM_START'][1] if when=='START' else results['NONROOT_ZRAM_END']
        require(dm[0]==zr[0]==0, 'health read failed')
        increments[when]=len(health_delta((SOURCE/'raw/round_health/dmesg_before.txt').read_text(), dm[1],
            (SOURCE/'raw/round_health/zram_before.txt').read_text(),zr[1]))
    for n in range(4):
        require(results['NONROOT_GOV_%d'%n]==(0,'schedutil'), 'governor drift')
    require(results['NONROOT_PACKAGES'][0]==0 and sorted(results['NONROOT_PACKAGES'][1].splitlines())==inventory,
        'package inventory drift')
    for name in GDB_NAMES:
        require(results['NONROOT_ABSENT_'+name]==(1,'package %s is not installed'%name), 'package not absent')
    for label in ('WORK','WORK_PARENT'):
        require(absent(*results['NONROOT_'+label]), 'work directory not absent')
    path_labels=[c['label'] for c in shell if re.fullmatch('NONROOT_PATH_[0-9]{4}',c['label'])]
    require(path_labels==['NONROOT_PATH_%04d'%i for i in range(len(paths))], 'incomplete/repeated path sweep')
    residues=[]
    by_label={c['label']:c for c in shell}
    for i,path in enumerate(paths):
        label='NONROOT_PATH_%04d'%i
        require(by_label[label]['argv'][-1]==request(['stat','-c','%F|%s|%Y|%u:%g','--',path]), 'wrong path checked')
        result=results[label]
        if absent(*result):
            continue
        require(result[0]==0, 'path unreadable')
        kind,size,stamp,owner=result[1].split('|')
        owner_rc,owner_text=results[label+'_OWNER']
        require(kind=='directory' and owner_rc==1 and owner_text=='file '+path+' is not owned by any package',
            'not the recorded unowned-directory observation')
        residues.append(dict(path=path,kind=kind,size=int(size),mtime_epoch=int(stamp),uid_gid=owner,
            mtime_utc=datetime.datetime.fromtimestamp(int(stamp),datetime.timezone.utc).isoformat(),
            owner_rc=owner_rc,owner=owner_text,source=label+'.txt',owner_source=label+'_OWNER.txt',
            disposition='NOT_REMOVED; contents/creator/emptiness not proven'))
    require(residues and audit['reason']=='unowned/unknown residue; metadata archived, not removed: '+residues[0]['path'],
        'STOP reason not supported')
    start=datetime.datetime.fromisoformat(audit['start_utc']); end=datetime.datetime.fromisoformat(audit['end_utc'])
    summary=dict(verdict='STOP_NOT_CLEANUP_PASS',reason=audit['reason'],elapsed_seconds=(end-start).total_seconds(),
        commands=len(commands),shell_requests=len(shell),body_min_bytes=min(sizes),body_max_bytes=max(sizes),
        remote_rc_counts=dict(sorted(collections.Counter(str(x[0]) for x in results.values()).items())),
        reused_checks=list(REUSE),root_scope=list(pending),root_rounds=1,root_off_attempts=1,final_uid=5001,
        process_views=views,target_starttime=stat['starttime'],governors=['schedutil']*4,
        stability_counts=[0,0],dmesg_increment_lines=increments,zram_three_delta=[0,0,0],oom_lmk_increment=0,
        package_count=len(inventory),packages_added=[],packages_removed=[],six_packages_absent=list(GDB_NAMES),
        path_count=len(paths),absent_paths=len(paths)-len(residues),unowned_directories=residues,
        measurement_cells_rerun=0,files_removed=0,processes_terminated=0,
        limitation='health samples precede root-off; no mutations except authorized privilege round')
    return json.dumps(summary,indent=2)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path)
    args=parser.parse_args()
    output=analyze(args.directory)
    if args.output:
        with args.output.open('x') as stream:
            stream.write(output)
    print(output,end='')
