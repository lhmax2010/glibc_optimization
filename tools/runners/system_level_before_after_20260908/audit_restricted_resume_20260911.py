#!/usr/bin/env python3
"""PM-approved continuation of the single-request audit, NEVER a measurement.

Reuse hashed successful NONROOT START/identity checks from the preceding STOP.
Finish unexecuted checks as nonroot, then one root round for the recorded denied
or incomplete categories. Foreign processes are observations, never kill targets.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import re
import shlex
import time

from audit_single_cleanup_20260911 import (SingleAudit, ROOT, SOURCE, PS, CRASH, WORK,
    ANALYSIS, CONTRACT, health_delta, request, parse, absent, utc)

TOKEN = 'PM-ROOT-PROCESS-20260910'
PREVIOUS = ROOT/'data/raw/system_level_before_after_20260908/cleanup_single_20260911'
REUSE = ('UNAME_R','UNAME_M','OS_RELEASE','GLIBC','MEMINFO','BOOT_START','DMESG_START','ZRAM_START')


def previous_checks(directory=PREVIOUS):
    manifest=json.loads((directory/'manifest.json').read_text())
    for row in manifest['files']:
        p=directory/row['path']
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['public_sha256']:
            raise ValueError('preceding cleanup evidence hash mismatch')
    receipt=json.loads((directory/'audit.json').read_text())
    if (receipt['verdict']!='STOP' or receipt['reason']!='process table missing PID 1' or
            not receipt['id_final'].startswith('uid=5001(')):
        raise ValueError('not the PM-approved predecessor')
    commands={row['label']:row for row in json.loads((directory/'commands.json').read_text())}
    checks={}
    for label in REUSE:
        name='NONROOT_'+label
        code,text=parse((directory/(name+'.txt')).read_text())
        if code:
            raise ValueError('cannot reuse unsuccessful item')
        checks[label]=(commands[name]['argv'][-1],(code,text))
    code,text=parse((directory/'NONROOT_PS_START.txt').read_text())
    if code or re.search(r'^\s*1\s+',text,re.M):
        raise ValueError('missing source evidence of incomplete nonroot process view')
    return receipt,checks


def process_rows(text):
    lines=text.splitlines()
    if not lines or not re.search(r'\bPID\s+PPID\s+TT\s+COMMAND',lines[0]):
        raise ValueError('full-system process header missing')
    rows={}
    for line in lines[1:]:
        parts=line.split(None,4)
        if len(parts)!=5 or not parts[0].isdigit() or not parts[1].isdigit() or int(parts[0]) in rows:
            raise ValueError('malformed/duplicate process row')
        rows[int(parts[0])]=dict(ppid=int(parts[1]),tty=parts[2],comm=parts[3],args=parts[4],raw=line)
    if 1 not in rows or rows[1]['ppid']!=0 or rows[1]['args'] not in ('/sbin/init','/usr/lib/systemd/systemd','/usr/bin/systemd'):
        raise ValueError('full-system view requires PID 1 init and root context')
    collectors=[pid for pid,row in rows.items() if row['comm']=='ps' and row['args']==shlex.join(PS)]
    if len(collectors)!=1:
        raise ValueError('ambiguous process collector')
    own={collectors[0]}
    parent=rows[collectors[0]]['ppid']
    while parent in rows and rows[parent]['comm'] in ('sh','bash'):
        if not rows[parent]['args'].endswith(' -c '+request(PS)):
            break
        own.add(parent)
        parent=rows[parent]['ppid']
    return rows,own


def known_helpers(source=SOURCE):
    result={}
    for cell in ('G4_trim_r1','G4_trim_r2','G4_trim_r3'):
        for filename,exe,script in (
            ('controller_identity.txt',('/bin/sh','/usr/bin/sh'),'run_cell_remote.sh'),
            ('sampler_identity.txt',('/bin/sh','/usr/bin/sh'),'sample_smaps_1s.sh'),
            ('debugger_identity.txt',('/usr/bin/gdb',),'g4_m7.py')):
            p=source/'raw'/cell/filename
            pid,ticks=map(int,p.read_text().split())
            result[pid]=dict(starttime=ticks,exe=exe,script=script)
    return result


class RestrictedResume(SingleAudit):
    authorization_token=TOKEN

    def __init__(self,args):
        super().__init__(args)
        self.preceding,self.cached=previous_checks()
        self.helpers=known_helpers()
        self.process_ops=set()
        self.signals=set()
        self.inspected=set()
        self.receipt.update(schema='system-before-after.restricted-cleanup.v2',
            root_elevation='REGISTERED_NOT_YET_ATTEMPTED',
            preceding_audit='data/raw/system_level_before_after_20260908/cleanup_single_20260911/audit.json',
            preceding_audit_sha256=hashlib.sha256((PREVIOUS/'audit.json').read_bytes()).hexdigest(),
            reused_nonroot_checks={},foreign_process_policy='REPORT_ONLY; no stopping or termination')

    def register(self,label,argv,reason):
        request(argv)
        self.pending[label]=dict(argv=argv,reason=reason,directory=argv[-1] if argv[0]=='ls' else None)
        self.receipt['permission_denied_items']=self.pending
        self.save()

    def op(self,label,argv,defer=True,scope=None):
        if self.phase=='NONROOT':
            if label in self.cached:
                expected,result=self.cached[label]
                if request(argv)!=expected:
                    raise ValueError('attempt to substitute reused operation')
                self.results[label]=result
                self.receipt['reused_nonroot_checks'][label]='NONROOT_'+label+'.txt'
                self.save()
                return result
            if label in ('PS_START','PS_END'):
                if argv!=PS:
                    raise ValueError('restricted process operation changed')
                self.register(label,argv,'PM: predecessor ps RC=0 omits PID 1; full-system view requires root')
                return None
            if label=='TARGET_STAT':
                expected=['cat','/proc/498/stat']
                if argv!=expected:
                    raise ValueError('restricted original target changed')
                self.register(label,argv,'PM process scope: predecessor full-system view incomplete and PID 498 not visible')
                return None
            if label in ('ALERTS_START','ALERTS_END'):
                if argv!=['ls','-A','--',CRASH]:
                    raise ValueError('restricted alert directory changed')
                self.register(label,argv,'predecessor NONROOT_ALERTS_START: Permission denied; no repeat nonroot probe')
                return None
        result=super().op(label,argv,defer,scope)
        if self.phase=='ROOT' and label in ('PS_START','PS_END') and result and result[0]==0:
            self.inspect_processes(label,result[1])
        return result

    def inspect_connections(self,connections):
        self.receipt['other_sdb_connections']=dict(established_count=len(connections),
            verdict='REPORT_ONLY_NOT_CLEARED',rows=connections)

    def allow_scoped_root(self,scope,argv):
        if scope in ('PS_START','PS_END') and scope in self.pending and tuple(argv) in self.process_ops:
            return True
        return super().allow_scoped_root(scope,argv)

    def allow_signal(self,argv):
        return self.phase=='ROOT' and tuple(argv) in self.signals

    def proc_read(self,scope,pid,part,argv):
        self.process_ops.add(tuple(argv))
        result=self.op(scope+'_PID_%d_'%pid+part,argv,False,scope=scope)
        if result[0]:
            raise ValueError('process metadata unreadable: %d %s'%(pid,part))
        return result[1]

    def inspect_processes(self,label,text):
        if label in self.inspected:
            return
        if self.phase!='ROOT' or not self.receipt.get('root_authorization',{}).get('id_after_on','').startswith('uid=0('):
            raise ValueError('full-system process proof requires authorized root context')
        rows,collectors=process_rows(text)
        if 498 not in rows or rows[498]['comm']!='enlightenment':
            raise ValueError('original daemon not present in root full-system view')
        observations=[]
        for pid,row in rows.items():
            if pid in collectors or pid==498:
                continue
            candidate=(pid in self.helpers or re.search(r'alloc_bench|gst_loop_decode|gst-launch|^gdb$|sample_smaps|run_cell_remote',row['comm']) or WORK+'/' in row['args'])
            if not candidate and row['tty']=='?':
                continue
            record=dict(pid=pid,**row,verdict='REPORT_ONLY_NONPROJECT_OR_UNATTRIBUTED_NOT_CLEARED')
            observations.append(record)
            self.receipt.setdefault('process_observations',{})[label]=observations
            self.save()
            if not candidate or pid not in self.helpers:
                continue
            meta={'STAT':self.proc_read(label,pid,'STAT',['cat','/proc/%d/stat'%pid])}
            stat=ANALYSIS.proc_stat(meta['STAT'])
            expected=self.helpers[pid]
            if stat['pid']!=pid or stat['starttime']!=expected['starttime']:
                record.update(metadata=meta,identity_match=False)
                self.save()
                continue
            for part,argv in (('EXE',['readlink','/proc/%d/exe'%pid]),('CMDLINE',['base64','/proc/%d/cmdline'%pid]),
                ('CWD',['readlink','/proc/%d/cwd'%pid])):
                meta[part]=self.proc_read(label,pid,part,argv)
            command=base64.b64decode(''.join(meta['CMDLINE'].splitlines()),validate=True).decode().split('\0')
            exe=meta['EXE'].removesuffix(' (deleted)')
            ours=(stat['pid']==pid and stat['starttime']==expected['starttime'] and
                exe in expected['exe'] and WORK+'/'+expected['script'] in command)
            record.update(metadata=meta,identity_match=ours)
            self.save()  # archive raw ps/stat/exe/cmdline/cwd BEFORE any signal
            if not ours:
                continue
            for part in ('STAT','EXE','CMDLINE'):
                argv=['cat','/proc/%d/stat'%pid] if part=='STAT' else (
                    ['readlink','/proc/%d/exe'%pid] if part=='EXE' else ['base64','/proc/%d/cmdline'%pid])
                current=self.proc_read(label,pid,'RECHECK_'+part,argv)
                current_stat=ANALYSIS.proc_stat(current) if part=='STAT' else None
                unchanged=(current_stat['pid']==pid and current_stat['starttime']==stat['starttime']) if part=='STAT' else current==meta[part]
                if not unchanged:
                    raise ValueError('process identity changed before TERM; no signal')
            signal=['kill','-TERM','--',str(pid)]
            self.process_ops.add(tuple(signal)); self.signals.add(tuple(signal))
            code,output=self.op(label+'_PID_%d_TERM'%pid,signal,False,scope=label)
            if code:
                raise ValueError('exact attributed process TERM failed')
            self.receipt['processes_terminated']+=1
            time.sleep(0.2)
            verify=['stat','--','/proc/%d'%pid]
            self.process_ops.add(tuple(verify))
            result=self.op(label+'_PID_%d_ABSENT'%pid,verify,False,scope=label)
            if not absent(*result):
                raise ValueError('attributed process termination not verified')
            record['verdict']='ARCHIVED_TERM_VERIFIED_ABSENT'
            self.save()
        self.receipt.setdefault('process_views',{})[label]=dict(rows=len(rows),pid_1=True,
            target_498=True,command=PS,context='UID=0; ps -e all-system selection',foreign_is_report_only=True)
        self.inspected.add(label)
        self.save()

    def drop_root(self):
        super().drop_root()
        if self.receipt['root_authorization']['root_off']!='PASS_NONROOT':
            return
        self.phase='NONROOT'
        # Only when disposition actually changed state, verify health afterwards;
        # these are new post-disposition timepoints, never duplicate root reads.
        removed=self.receipt['processes_terminated'] or any(
            isinstance(v,list) and any(isinstance(x,dict) and x.get('archived_then_removed_verified') for x in v)
            for k,v in self.receipt.items() if k.startswith('alerts_'))
        if removed:
            try:
                dm=self.ok('POST_DISPOSITION_DMESG',['dmesg'],False)
                zr=self.ok('POST_DISPOSITION_ZRAM',['cat','/sys/block/zram0/mm_stat'],False)
                health_delta((SOURCE/'raw/round_health/dmesg_before.txt').read_text(),dm,
                    (SOURCE/'raw/round_health/zram_before.txt').read_text(),zr)
                self.receipt['post_disposition_health']='PASS'
            except Exception as error:
                self.receipt['reason']='post-disposition health: '+str(error)
                self.receipt['verdict']='STOP'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip',required=True)
    parser.add_argument('--output-dir',type=pathlib.Path,required=True)
    parser.add_argument('--pm-authorization',choices=[TOKEN],required=True)
    args=parser.parse_args()
    if not args.output_dir.resolve().is_relative_to(ROOT/'board_results'):
        parser.error('output must be a new local board_results directory')
    return RestrictedResume(args).execute()


if __name__=='__main__':
    raise SystemExit(main())
