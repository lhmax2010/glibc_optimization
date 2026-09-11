#!/usr/bin/env python3
"""Independently replay the PM directory disposition from public, hash-bound logs."""
import argparse
import hashlib
import json
import pathlib
import tempfile
import types

from dispose_gdb_dirs_20260911 import (DirectoryDisposition, BOTTOM_UP, IMAGE, DIRS,
    stat, directory_identity, SOURCE, sources, parse, request, health_delta, ANALYSIS)
from audit_restricted_resume_20260911 import process_rows
from single_request import absent, absent_listing


def require(ok,why):
    if not ok:
        raise ValueError(why)


def replay(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    for item in manifest['files']:
        path=directory/item['path']
        require(not pathlib.PurePosixPath(item['path']).is_absolute() and '..' not in pathlib.PurePosixPath(item['path']).parts,'unsafe manifest path')
        require(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==item['public_sha256'],'public source hash mismatch')
    receipt=json.loads((directory/'audit.json').read_text())
    require(receipt['verdict']=='PASS_READONLY_CLEANUP','cleanup not passed')
    require(receipt['schema']=='system-before-after.directory-disposition.v1','wrong disposition schema')
    prior,_,inventory=sources()
    require(receipt['source_execution_sha256']==hashlib.sha256((SOURCE/'execution.json').read_bytes()).hexdigest(),'wrong accepted G4 source')
    commands=json.loads((directory/'commands.json').read_text())
    with tempfile.TemporaryDirectory(prefix='directory-policy-replay-') as tmp:
        obj=DirectoryDisposition(types.SimpleNamespace(ip='192.0.2.1',output_dir=pathlib.Path(tmp)/'policy'))
        allowed=obj.allowed
    readings={}
    sizes=[]
    root=False
    on=off=0
    seen=set()
    for command in commands:
        label,argv=command['label'],command['argv']
        require(label not in seen,'duplicate command label')
        seen.add(label)
        if 'shell' not in argv:
            if label=='ROOT_ON':
                require(argv==['sdb','-s','<TEST_BOARD_IP>:26101','root','on'] and not root and on==0,'unscoped root on')
                root=True;on+=1
            elif label.startswith('ROOT_OFF_'):
                require(argv==['sdb','-s','<TEST_BOARD_IP>:26101','root','off'] and root and off<2,'invalid root off')
                off+=1
            else:
                require((label,argv) in [('SDB_VERSION',['sdb','version']),('CONNECT',['sdb','connect','<TEST_BOARD_IP>'])],'unexpected non-shell operation')
            continue
        require(argv[:4]==['sdb','-s','<TEST_BOARD_IP>:26101','shell'] and len(argv)==5,'wrong shell transport')
        body=argv[-1]
        sizes.append(len(body.encode()))
        require(sizes[-1]<=200,'overlength request')
        name=label.removeprefix('NONROOT_').removeprefix('ROOT_')
        fixed={'ID_BEFORE':['id'],'ID_BEFORE_ROOT':['id'],'ID_ROOT':['id'],'ID_OFF_1':['id'],'ID_OFF_2':['id'],
            'UNAME_R':['uname','-r'],'UNAME_M':['uname','-m'],'OS_RELEASE':['cat','/etc/os-release'],
            'GLIBC':['rpm','-q','glibc'],'MEMINFO':['cat','/proc/meminfo']}
        if name.startswith('REMOVE_'):
            i=int(name.split('_')[1]);expected=['rmdir','--',BOTTOM_UP[i]]
            require(root,'nonroot removal')
        else:
            expected=allowed.get(name,fixed.get(name))
        require(expected is not None and body==request(expected),'unregistered operation '+label)
        code,text=parse((directory/(label+'.txt')).read_text())
        readings[name]=(code,text)
        if name=='ID_BEFORE':
            require(code==0 and text.startswith('uid=5001('),'initial ID failed')
        if name=='ID_ROOT':
            require(root and code==0 and text.startswith('uid=0('),'root ID failed')
        if name.startswith('ID_OFF_') and code==0 and text.startswith('uid=5001('):
            root=False
        if name=='ID_BEFORE_ROOT':
            require(code==0 and text.startswith('uid=5001('),'pre-root ID failed')
    require(on==1 and off>=1 and not root and commands[-1]['label'].startswith('ROOT_ID_OFF_'),'root lifecycle incomplete')
    def good(key):
        code,text=readings[key]
        require(code==0,'failed required read '+key)
        return text
    require('rpi4' in good('UNAME_R') and good('UNAME_M')=='armv7l','identity mismatch')
    from execute_contract import CONTRACT,GDB_NAMES
    require('BUILD_ID='+CONTRACT['identity']['build_id'] in good('OS_RELEASE').splitlines(),'BUILD_ID mismatch')
    require(good('GLIBC')==CONTRACT['identity']['glibc'],'glibc drift')
    dispositions=[]
    for i,path in enumerate(BOTTOM_UP):
        listing=good('CHECK_LIST_%d'%i)
        if 'REMOVE_%d'%i in readings:
            require(not listing,'nonempty directory removal attempted')
            require(readings['REMOVE_%d'%i][0]==0,'removal failed')
            require(absent(*readings['VERIFY_REMOVED_%d'%i]),'removal not verified')
            require(absent(*readings['END_DIR_%d'%i]) and absent_listing(*readings['END_LIST_%d'%i]),'removed path returned')
            verdict='ARCHIVED_RMDIR_VERIFIED_ABSENT'
        else:
            require(bool(listing),'empty path left without disposition')
            before=good('INITIAL_STAT_%d'%DIRS.index(path))
            require(directory_identity(good('END_DIR_%d'%i))==directory_identity(before),'retained directory changed')
            good('END_LIST_%d'%i)
            verdict='PRESERVED_IMAGE_ANCESTOR' if path=='/usr/share/gdb' and listing=='python' else 'REPORT_ONLY_PENDING_NONEMPTY'
        dispositions.append(dict(path=path,verdict=verdict,raw_listing=listing))
    require(directory_identity(good('END_DIR_4'))==directory_identity(good('INITIAL_STAT_%d'%DIRS.index(IMAGE))),'image directory changed')
    good('END_LIST_4')
    health={}
    for phase in ('START','END'):
        prefix=phase+'_'
        require(good(prefix+'BOOT')==prior['preflight']['boot_id'],'boot changed')
        rows,_=process_rows(good(prefix+'PS'))
        require(498 in rows and rows[498]['comm']=='enlightenment','daemon missing')
        identity=ANALYSIS.proc_stat(good(prefix+'TARGET'))
        require(identity['pid']==498 and identity['starttime']==prior['target_starttime'],'daemon identity changed')
        require(sorted(good(prefix+'PACKAGES').splitlines())==inventory,'package inventory changed')
        for n in GDB_NAMES:
            require(readings[prefix+'ABSENT_'+n]==(1,'package %s is not installed'%n),'gdb dependency present')
        for n in range(4):
            require(good(prefix+'GOV_%d'%n)=='schedutil','governor changed')
        for name in ('WORK','WORK_PARENT'):
            require(absent(*readings[prefix+name]),'work residue')
        for name in ('DF_ROOT','DF_OPTUSR','DATE','MEMINFO','TOP_TMP','TOP_HOME','TOP_OPTUSR'):
            good(prefix+name)
        increment=health_delta((SOURCE/'raw/round_health/dmesg_before.txt').read_text(),good(prefix+'DMESG'),
            (SOURCE/'raw/round_health/zram_before.txt').read_text(),good(prefix+'ZRAM'))
        require(good(prefix+'ALERTS')=='','this observed replay requires empty stability directory')
        health[phase]=dict(process_rows=len(rows),pid_1=True,packages=len(inventory),governors=['schedutil']*4,
            stability_count=0,dmesg_increment_lines=len(increment),oom_lmk=0,zram_delta=[0,0,0])
    require(receipt['directories_removed']==[d['path'] for d in dispositions if d['verdict']=='ARCHIVED_RMDIR_VERIFIED_ABSENT'],'receipt removals inconsistent')
    require(all(receipt[k]==0 for k in ('measurement_cells_run','board_files_pushed','packages_changed','governor_writes','processes_terminated')),'unexpected mutation claims')
    return dict(verdict='PASS_DELAYED_CLEANUP_WITH_REPORT_ONLY_NONEMPTY',files=len(manifest['files']),
        commands=len(commands),shell_requests=len(sizes),request_bytes=[min(sizes),max(sizes)],
        uid_sequence=[5001,0,5001],root_rounds=on,root_off_attempts=off,
        disposition=dispositions,health=health,measurement_cells_rerun=0,
        source_execution_sha256=receipt['source_execution_sha256'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=pathlib.Path)
    args=p.parse_args()
    print(json.dumps(replay(args.directory),indent=2)+'')


if __name__=='__main__':
    main()
