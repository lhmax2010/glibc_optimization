#!/usr/bin/env python3
"""PM-authorized all-workflow single SDB shell; never creates board files."""
import argparse
import csv
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shlex
import subprocess
import time

import run_readonly as old
from run_board_script import product_release
from analyze_floor import proc_stat, smaps
from analyze_full_session import CONTRACT, FIELDS, analyze, select_candidates

HERE, ROOT = old.HERE, old.ROOT
PINS = [str((HERE/n).relative_to(ROOT)) for n in
        ('full_session_contract.json','analyze_full_session.py','analyze_floor.py','analyze_persistent.py','persistent_contract.json')]
PINS += ['tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py']
FILTER = '/^[0-9a-fA-F]+-|^Private_Dirty:/'


def bounded(text):
    for line in text.splitlines():
        old.single.check_body(line)
    return text


def journal(path, value):
    with path.open('a') as f:
        f.write(json.dumps(value,ensure_ascii=False)+'\n'); f.flush()


class Transport:
    def __init__(self, address, output, sdb='sdb'):
        self.address=str(ipaddress.IPv4Address(address)); self.serial=self.address+':26101'
        self.output=output; self.sdb=sdb; self.working_opened=False
        (output/'raw').mkdir(parents=True)

    def call(self, label, args):
        allowed = (['devices'],['kill-server'],['start-server'],['connect',self.address],
                   ['-s',self.serial,'root','on'],['-s',self.serial,'root','off'])
        short = args == ['-s',self.serial,'shell',old.readonly_body(['id'])]
        if args not in allowed and not short:
            raise ValueError('LOCAL_STOP no other short requests permitted')
        if self.working_opened and label not in ('root_off','id_after_root_off'):
            raise ValueError('LOCAL_STOP no new setup/short connection after working session')
        path=self.output/'raw'/(label+'.txt')
        if path.exists(): raise ValueError('LOCAL_STOP duplicate request')
        rec=dict(label=label,argv=[self.sdb,*args],started_utc=old.utc(),started_ns=time.time_ns())
        journal(self.output/'intents.jsonl',rec)
        raw=b''; rc=None
        try:
            r=subprocess.run(rec['argv'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
            raw,rc=r.stdout,r.returncode
            text=raw.decode(errors='strict').replace('\r','')
            if short:
                remote_rc,value=old.single.parse(text)
                rec['remote_rc']=remote_rc
                if remote_rc: raise ValueError('STOP remote id RC='+str(remote_rc))
            else: value=text
            if rc: raise ValueError('STOP transport RC='+str(rc))
            if not short and re.search(r'failed|cannot|error|unable',value,re.I):
                raise ValueError('STOP SDB reported failure: '+label)
            return value
        except subprocess.TimeoutExpired as e:
            raw=e.stdout or b''; rc=124
            raise ValueError('STOP command timeout: '+label) from e
        finally:
            path.write_bytes(raw)
            rec.update(host_rc=rc,ended_utc=old.utc(),raw_sha256=hashlib.sha256(raw).hexdigest())
            journal(self.output/'commands.jsonl',rec)

    def id_short(self,label,expected):
        text=self.call(label,['-s',self.serial,'shell',old.readonly_body(['id'])])
        require_uid(text,expected)
        return text


def require_uid(text, expected):
    if not re.match(r'uid='+str(expected)+r'\(',text.strip()):
        raise ValueError('STOP UID not '+str(expected))


class Session:
    def __init__(self, board, nonce=None, silence_seconds=15):
        if board.working_opened: raise ValueError('LOCAL_STOP second working session forbidden')
        self.nonce=nonce or secrets.token_hex(16)
        if not re.fullmatch('[a-f0-9]{32}',self.nonce): raise ValueError('bad nonce')
        self.output=board.output; self.silence=silence_seconds
        self.pending=b''; self.queue=[]; self.active=None; self.seen=set(); self.frames=[]
        self.last=time.monotonic(); self.closed=False
        argv=[board.sdb,'-s',board.serial,'shell']
        journal(self.output/'intents.jsonl',dict(label='working_session',argv=argv,started_utc=old.utc(),nonce=self.nonce))
        self.raw=(self.output/'stream.raw').open('wb')
        try:self.sent=(self.output/'stdin_program.txt').open('w')
        except BaseException:
            self.raw.close();raise
        self.proc=None;self.selector=None
        try:
            self.selector=selectors.DefaultSelector()
            board.working_opened=True
            self.proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            self.selector.register(self.proc.stdout,selectors.EVENT_READ)
        except BaseException:
            if self.proc is not None:
                self.proc.stdin.close()
                try:self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=5)
                self.proc.stdout.close()
            if self.selector is not None:self.selector.close()
            self.raw.close();self.sent.close()
            raise

    def send(self,text):
        bounded(text)
        if len(text.encode()) > 4000: raise ValueError('LOCAL_STOP oversized stdin chunk')
        self.sent.write(text);self.sent.flush()
        self.proc.stdin.write(text.encode());self.proc.stdin.flush()

    def feed(self,line,epoch,mono):
        # printf begins with a newline, so prompts/echo cannot swallow framing.
        line=line.rstrip('\r')
        m=re.fullmatch(r'===BEGIN ([a-f0-9]{32}) ([A-Za-z0-9_]+) (\d+)===',line)
        end=re.fullmatch(r'===END ([a-f0-9]{32}) ([A-Za-z0-9_]+) RC=(\d+) (DONE|FAIL) (\d+)===',line)
        if m:
            if m[1]!=self.nonce or self.active or m[2] in self.seen:
                raise ValueError('STOP duplicate/invalid BEGIN')
            self.active=dict(label=m[2],board_epoch_ns=int(m[3])*10**9,host_epoch_ns=epoch,host_monotonic_ns=mono,lines=[])
        elif end:
            if end[1]!=self.nonce or not self.active or self.active['label']!=end[2]:
                raise ValueError('STOP invalid END')
            rc=int(end[3])
            if not 0<=rc<=255 or end[4]!=('DONE' if rc==0 else 'FAIL'):
                raise ValueError('STOP invalid RC/DONE')
            frame=self.active
            frame.update(rc=rc,board_end_ns=int(end[5])*10**9,host_end_monotonic_ns=mono,
                         text='\n'.join(frame.pop('lines')).strip())
            if frame['board_end_ns'] < frame['board_epoch_ns']:raise ValueError('STOP reversed clock')
            self.seen.add(frame['label']);self.frames.append(frame);self.queue.append(frame);self.active=None
            journal(self.output/'frames.jsonl',frame)
        elif line.startswith('==='):
            raise ValueError('STOP malformed frame')
        elif self.active is not None:
            self.active['lines'].append(line)

    def next(self):
        while not self.queue:
            remaining=self.silence-(time.monotonic()-self.last)
            if remaining<=0 or not self.selector.select(remaining):
                raise ValueError('STOP_STREAM_SILENCE: 15 seconds without output')
            chunk=os.read(self.proc.stdout.fileno(),65536)
            if not chunk:raise ValueError('STOP_STREAM_DISCONNECT')
            self.last=time.monotonic();epoch=time.time_ns();mono=time.monotonic_ns()
            self.raw.write(chunk);self.raw.flush();self.pending+=chunk
            while b'\n' in self.pending:
                line,self.pending=self.pending.split(b'\n',1)
                self.feed(line.decode(errors='strict'),epoch,mono)
        return self.queue.pop(0)

    def request(self,label,command,optional=False):
        if not re.fullmatch('[a-zA-Z0-9_]+',label):raise ValueError('unsafe label')
        self.send('q '+label+' '+command+'\n')
        f=self.next()
        if f['label']!=label:raise ValueError('STOP unexpected response order')
        if f['rc'] and not optional:raise ValueError('STOP remote '+label+' RC='+str(f['rc']))
        return f

    def close(self,normal=False):
        if self.closed:return
        self.closed=True
        if not self.proc.stdin.closed:self.proc.stdin.close()
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.terminate()  # Host SDB client only, never a board PID.
            self.proc.wait(timeout=5)
        finally:
            self.selector.close();self.raw.close();self.sent.close();self.proc.stdout.close()
            old.write_json(self.output/'session_exit.json',dict(host_rc=self.proc.returncode,normal=normal,
                          complete_frames=len(self.frames),partial_frame=self.active,ended_utc=old.utc()))
        if normal and self.proc.returncode:raise ValueError('STOP working transport exit nonzero')


def bootstrap(nonce):
    return bounded('''HISTFILE=; export HISTFILE
LC_ALL=C; export LC_ALL
N='''+nonce+'''
q() {
k=$1; shift
t=$(date +%s) || return
printf '\\n===BEGIN %s %s %s===\\n' "$N" "$k" "$t" || return
"$@"
r=$?
t=$(date +%s) || return
if [ "$r" = 0 ]; then flag=DONE; else flag=FAIL; fi
printf '\\n===END %s %s RC=%s %s %s===\\n' "$N" "$k" "$r" "$flag" "$t" || return
return "$r"
}
q root_id id
''')


def discovery_program():
    return bounded('''discover() {
for path in /proc/[0-9]*/stat; do
p=${path#/proc/}; p=${p%/stat}
q invstat_$p cat "$path" || continue
q invsmaps_$p awk '''+shlex.quote(FILTER)+''' /proc/$p/smaps
q invafter_$p cat "$path"
done
}
discover
q discovery_end printf '%s\\n' DONE
''')


def parse_inventory(frames):
    records=[];sections={}
    for f in frames:
        m=re.fullmatch(r'inv(stat|smaps|after)_(\d+)',f['label'])
        if not m:raise ValueError('STOP unexpected inventory frame')
        sections.setdefault(int(m[2]),{})[m[1]]=f
    for pid,parts in sections.items():
        row=dict(pid=pid,status='TRANSIENT',reason='process disappeared during traversal')
        if parts['stat']['rc']:
            if not re.search(r'No such|not found',parts['stat']['text'],re.I):raise ValueError('STOP unreadable inventory stat')
        elif 'after' not in parts or parts['after']['rc']:
            if 'after' not in parts or not re.search(r'No such|not found',parts['after']['text'],re.I):
                raise ValueError('STOP incomplete/unreadable inventory')
        else:
            before,after=proc_stat(parts['stat']['text']),proc_stat(parts['after']['text'])
            if any(before[k]!=after[k] for k in ('pid','comm','start_ticks')):
                records.append(row);continue
            row.update(after)
            if parts['smaps']['rc']:
                raise ValueError('STOP unreadable inventory smaps PID '+str(pid))
            if not parts['smaps']['text']:
                tail=parts['after']['text'].rsplit(') ',1)[1].split()
                if int(tail[6]) & 0x200000:
                    row.update(status='EMPTY_MAPS',reason='PF_KTHREAD; empty kernel mappings')
                elif after['state'] in ('Z','X'):
                    row.update(status='TRANSIENT',reason='exited/zombie process with empty mappings')
                else:
                    raise ValueError('STOP unexplained empty userspace smaps PID '+str(pid))
            else:
                row.update(smaps(parts['smaps']['text']),status='READABLE',reason='')
        records.append(row)
    return records


def sample_program(candidates):
    if not candidates or any(type(c['pid']) is not int or not 0<c['pid']<=4194304 for c in candidates):
        raise ValueError('LOCAL_STOP invalid candidate PID')
    return bounded('P='+shlex.quote(' '.join(str(c['pid']) for c in candidates))+'''
one() {
p=$1
if [ ! -d /proc/$p ]; then q gone_${i}_$p printf '%s\\n' MISSING; return; fi
q before_${i}_$p cat /proc/$p/stat &&
q smaps_${i}_$p awk '''+shlex.quote(FILTER)+''' /proc/$p/smaps &&
q after_${i}_$p cat /proc/$p/stat && return 0
if [ ! -d /proc/$p ]; then q gone_${i}_$p printf '%s\\n' MISSING; return; fi
return 76
}
collect() {
start=$(date +%s) || return
i=0
while :; do
s=$(date +%s) || return
q sample_$i printf '%s\\n' "$i" || return
q mem_$i cat /proc/meminfo || return
q zram_$i cat /sys/block/zram0/mm_stat || return
q swaps_$i cat /proc/swaps || return
for p in $P; do one "$p" || return; done
q batch_end_$i printf '%s\\n' "$i" || return
IFS= read -r ack || return 73
case "$ack" in
END) now=$(date +%s) || return; [ $((now-start)) -ge 600 ] || return 74; return 0;;
CONTINUE*) ;;
*) return 75;;
esac
drop=${ack#CONTINUE}
for gone in $drop; do
nextP=
for p in $P; do [ "$p" = "$gone" ] || nextP="$nextP $p"; done
P=$nextP
done
now=$(date +%s) || return
while [ "$now" -lt $((s+1)) ]; do
sleep 1 || return
now=$(date +%s) || return
done
i=$((i+1))
done
}
collect
result=$?
q sampling_final test "$result" = 0
''')


def parse_batch(frames,candidates,retired,index):
    labels=[f['label'] for f in frames]
    if labels[:4]!=[f'sample_{index}',f'mem_{index}',f'zram_{index}',f'swaps_{index}'] or labels[-1]!=f'batch_end_{index}':
        raise ValueError('STOP incomplete/out-of-order batch')
    data={f['label']:f for f in frames}
    if len(data)!=len(frames):raise ValueError('STOP duplicate batch frame')
    if any(f['rc'] for f in frames[:4]+frames[-1:]):raise ValueError('STOP globals/frame read failed')
    mem,zram,swaps=[data[f'{k}_{index}'] for k in ('mem','zram','swaps')]
    m=re.search(r'^MemAvailable:\s+(\d+) kB$',mem['text'],re.M)
    z=zram['text'].split();sw=[s.split() for s in swaps['text'].splitlines()]
    if not m or len(z)<3 or not all(v.isdecimal() for v in z):raise ValueError('STOP invalid globals')
    if len(sw)!=2 or sw[0]!=['Filename','Type','Size','Used','Priority'] or len(sw[1])!=5 or sw[1][0]!='/dev/zram0':
        raise ValueError('STOP unsupported swap topology')
    g=dict(MemAvailable_kb=int(m[1]),zram_used_kb=int(sw[1][3]),zram_orig_bytes=int(z[0]),
           zram_compr_bytes=int(z[1]),zram_mem_used_bytes=int(z[2]),
           globals_start_ns=mem['board_epoch_ns'],globals_end_ns=swaps['board_end_ns'])
    batch=dict(sample=index,board_epoch_ns=frames[0]['board_epoch_ns'],board_end_ns=frames[-1]['board_end_ns'],
               host_epoch_ns=frames[0]['host_epoch_ns'],host_monotonic_ns=frames[0]['host_monotonic_ns'],
               host_end_monotonic_ns=frames[-1]['host_end_monotonic_ns'],**g)
    if any(b['board_epoch_ns']<a['board_end_ns'] for a,b in zip(frames,frames[1:])):
        raise ValueError('STOP overlapping/reversed batch reads')
    rows=[];events=[];expected=labels[:4];offset=4
    for c in candidates:
        p=c['pid']
        if p in retired:continue
        reads=[]
        while offset<len(frames)-1 and re.fullmatch(r'(before|smaps|after|gone)_'+str(index)+'_'+str(p),frames[offset]['label']):
            reads.append(frames[offset]);offset+=1
        expected += [f['label'] for f in reads]
        gone=reads and reads[-1]['label']==f'gone_{index}_{p}'
        if gone:
            if reads[-1]['rc'] or reads[-1]['text']!='MISSING':raise ValueError('STOP bad disappearance')
            reason='MISSING'
        else:
            if [f['label'] for f in reads]!=[f'{k}_{index}_{p}' for k in ('before','smaps','after')] or any(f['rc'] for f in reads):
                raise ValueError('STOP incomplete target/read failure')
            before,after=proc_stat(reads[0]['text']),proc_stat(reads[-1]['text'])
            reason='REPLACED' if any(any(s[k]!=c[k] for k in ('pid','comm','start_ticks')) for s in (before,after)) else None
            if not reason and not reads[1]['text'] and after['state'] in ('Z','X'):
                reason='MISSING'  # Process exited but zombie /proc entry remains.
        if reason:
            events.append(dict(target=c['target'],pid=p,sample=index,reason=reason,
                               board_epoch_ns=reads[-1]['board_end_ns'],host_epoch_ns=reads[-1]['host_epoch_ns']))
            continue
        if any(after[k]<before[k] for k in ('minflt','majflt')):raise ValueError('STOP faults regressed')
        f=reads[1]
        rows.append(dict(sample=index,target=c['target'],pid=p,start_ticks=c['start_ticks'],
                         epoch_ns=f['board_epoch_ns'],board_end_ns=f['board_end_ns'],host_epoch_ns=f['host_epoch_ns'],
                         host_monotonic_ns=f['host_monotonic_ns'],host_end_monotonic_ns=f['host_end_monotonic_ns'],
                         **smaps(f['text']),minflt=after['minflt'],majflt=after['majflt'],**g))
    if offset!=len(frames)-1:raise ValueError('STOP unexpected target frame')
    return rows,batch,events


def enough(rows,batches,candidates,retired):
    if len(batches)<2:return False
    keys=('board_epoch_ns','host_monotonic_ns')
    if any(batches[-1][k]-batches[0][k]<600e9 for k in keys):return False
    for c in candidates:
        if c['pid'] in retired:continue
        s=[r for r in rows if r['pid']==c['pid']]
        if not s or any(s[-1][k]-s[0][k]<600e9 for k in ('epoch_ns','host_monotonic_ns')):return False
    return True


def sample(session,candidates,state):
    rows=[];batches=[];events=[];retired=set();pending=[]
    session.send(sample_program(candidates))
    out=session.output
    with (out/'timeseries.tsv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,delimiter='\t',lineterminator='\n');writer.writeheader()
        try:
            while True:
                frame=session.next()
                if frame['label']=='sampling_final':
                    if pending or frame['rc'] or not enough(rows,batches,candidates,retired):
                        raise ValueError('STOP sampling FINAL/coverage failed')
                    break
                pending.append(frame)
                if frame['label'].startswith('batch_end_'):
                    batchrows,batch,new=parse_batch(pending,candidates,retired,len(batches));pending=[]
                    if batches and any(batch[k]<=batches[-1][k] for k in ('board_epoch_ns','host_monotonic_ns')):
                        raise ValueError('STOP batch clock regression')
                    # Fault/PID validation at every batch, not just after 600 seconds.
                    for row in batchrows:
                        prev=next((r for r in reversed(rows) if r['pid']==row['pid']),None)
                        if prev and (any(row[k]<prev[k] for k in ('minflt','majflt')) or
                                     any(row[k]<=prev[k] for k in ('epoch_ns','host_monotonic_ns','globals_start_ns')) or
                                     row['globals_start_ns']<prev['globals_end_ns']):
                            raise ValueError('STOP counter/clock regression')
                    rows+=batchrows;batches.append(batch);events+=new;retired.update(e['pid'] for e in new)
                    writer.writerows(batchrows);f.flush()
                    state['complete_batches']=len(batches)
                    old.write_json(out/'state.json',state)
                    done=enough(rows,batches,candidates,retired)
                    session.send('END\n' if done else 'CONTINUE' + ''.join(' '+str(e['pid']) for e in new)+'\n')
                    if len(batches)%10==1:print('PROGRESS batches='+str(len(batches))+' elapsed_s='+str((batch['host_monotonic_ns']-batches[0]['host_monotonic_ns'])/1e9),flush=True)
        finally:
            old.write_json(out/'batches.json',batches);old.write_json(out/'events.json',events)
    old.write_json(out/'summary.json',analyze(rows,candidates,batches,events))


def working(session,names,state):
    session.send(bootstrap(session.nonce))
    root=session.next()
    if root['label']!='root_id' or root['rc']:raise ValueError('STOP missing root id')
    require_uid(root['text'],0);state['id_after_root_on']=root['text']
    obs=session.request('observer',"printf '%s\\n' \"$$\"")
    observer=int(obs['text'])
    tools='cat date sleep awk uname id ps ls rpm getconf df'
    session.send('probe() {\nmissing=0\nfor tool in '+tools+'; do\ncommand -v "$tool" || { printf "MISSING_TOOL %s\\n" "$tool"; missing=1; }\ndone\nreturn "$missing"\n}\nq tools probe\n')
    probe=session.next()
    if probe['label']!='tools' or probe['rc']:raise ValueError('STOP required board tools missing')
    kernel=session.request('uname_r','uname -r')['text']
    if 'rpi4' in kernel.lower():raise ValueError('STOP_TEST_BOARD: endpoint is RPI4')
    arch=session.request('uname_m','uname -m')['text']
    if arch!='armv7l':raise ValueError('STOP product architecture')
    release=session.request('os_release','cat /etc/os-release')['text']
    if not product_release(release):raise ValueError('STOP product TV image')
    baseline={}
    for label,cmd,optional in [
        ('vk_send','command -v vk_send',True),('glibc','rpm -q glibc',False),('libc','/lib/libc.so.6',False),
        ('meminfo','cat /proc/meminfo',False),('uptime','cat /proc/uptime',False),('date','date -u',False),
        ('cpu_online','cat /sys/devices/system/cpu/online',False),('clock_ticks','getconf CLK_TCK',False),
        ('df','df -h',False),('gdb','rpm -q gdb',True),('yama','cat /proc/sys/kernel/yama/ptrace_scope',True),
        ('self_status','cat /proc/self/status',False),('ps_before','ps -ef',False),('tmp_before','ls -la /tmp',False)]:
        baseline[label]=session.request(label,cmd,optional)
    if not any(re.match(r'^\S+\s+1\s+',line) for line in baseline['ps_before']['text'].splitlines()):
        raise ValueError('STOP incomplete system ps view')
    old.write_json(session.output/'baseline.json',dict(kernel=kernel,arch=arch,os_release=release,reads=baseline))
    session.send(discovery_program());frames=[]
    while True:
        frame=session.next()
        if frame['label']=='discovery_end':
            if frame['rc']:raise ValueError('STOP discovery final')
            break
        frames.append(frame)
    inventory=parse_inventory(frames);old.write_json(session.output/'inventory.json',inventory)
    candidates=select_candidates(inventory,names,observer)
    old.write_json(session.output/'candidates.json',dict(selected=candidates,primary_names=names,observer_pid=observer,
                   absent_primary=[alias for alias,comm in names.items() if not any(c['comm']==comm for c in candidates)]))
    print('PROGRESS discovery complete: '+str(len(inventory))+' processes; '+str(len(candidates))+' candidates',flush=True)
    sample(session,candidates,state)
    tmp=session.request('tmp_after','ls -la /tmp');ps=session.request('ps_after','ps -ef')
    old.write_json(session.output/'cleanup.json',dict(tmp_before=baseline['tmp_before'],tmp_after=tmp,ps_after=ps,
                   no_board_files_written=True,scope='Observer creates no files; unrelated changes are reported, never removed.'))
    final=session.request('work_final',"printf '%s\\n' DONE")
    if final['text']!='DONE':raise ValueError('STOP working final')
    session.send('exit 0\n');session.close(normal=True)


def execute(board,names,state):
    root_attempted=False;session=None
    try:
        for attempt in range(2):
            try:
                devices=board.call('devices_'+str(attempt),['devices'])
                identity=board.id_short('selfcheck_'+str(attempt),5001)
                if not re.search(r'^'+re.escape(board.serial)+r'\s+device\b',devices,re.M):
                    raise ValueError('STOP serial absent from devices')
                state['id_before_root_on']=identity;break
            except (ValueError,OSError):
                if attempt:raise
                board.call('reset_kill',['kill-server']);board.call('reset_start',['start-server'])
                board.call('reset_connect',['connect',board.address])
        root_attempted=True
        board.call('root_on',['-s',board.serial,'root','on'])
        time.sleep(1)  # Bounded host-only settling time; no extra board query.
        session=Session(board)
        working(session,names,state)
        state['status']='COMPLETE'
    except BaseException as e:
        state.update(status='STOP',reason=type(e).__name__+': '+str(e))
    finally:
        if session:
            try:session.close()
            except BaseException as e:state.update(status='STOP',close_error=str(e))
        if root_attempted:
            try:board.call('root_off',['-s',board.serial,'root','off'])
            except BaseException as e:state.update(status='STOP',root_off_error=str(e))
            time.sleep(1)
            try:state['id_after_root_off']=board.id_short('id_after_root_off',5001)
            except BaseException as e:state.update(status='STOP',restore_error=str(e))
        state['ended_utc']=old.utc();old.write_json(board.output/'state.json',state)
    return state


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--record-push',type=Path)
    p.add_argument('--ip');p.add_argument('--output',type=Path);p.add_argument('--mapping',type=Path)
    p.add_argument('--push-receipt',type=Path);p.add_argument('--pm-authorized-readonly-root',action='store_true')
    p.add_argument('--sdb',default='sdb')
    a=p.parse_args()
    if a.record_push:
        tag=CONTRACT['tag'];obj=old.git('rev-parse',tag).decode().strip()
        if old.git('cat-file','-t',tag).strip()!=b'tag' or old.git('ls-remote','origin','refs/tags/'+tag).decode().split()[0]!=obj:
            raise ValueError('STOP remote annotated tag missing')
        if a.record_push.exists():raise ValueError('refusing to overwrite push receipt')
        old.write_json(a.record_push,dict(tag=tag,tag_object=obj,commit=old.git('rev-parse',tag+'^{commit}').decode().strip(),
                      verified_utc=old.utc(),epoch_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),
                      boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
        print('PASS remote contract receipt recorded');return
    if not all((a.ip,a.output,a.mapping,a.push_receipt,a.pm_authorized_readonly_root)):
        p.error('explicit current-round authorization, ip, output, mapping and push receipt required')
    if a.output.exists():raise ValueError('STOP output already exists; no rerun')
    gate=old.contract_gate(json.loads(a.push_receipt.read_text()),CONTRACT['tag'],PINS)
    names=old.names_from_mapping(a.mapping)
    # Current executable must be committed; ignored local evidence is allowed.
    for name in ('run_full_session.py',):
        path=str((HERE/name).relative_to(ROOT))
        if old.git('show','HEAD:'+path)!=(ROOT/path).read_bytes():raise ValueError('STOP uncommitted executor')
    board=Transport(a.ip,a.output,a.sdb)
    old.write_json(a.output/'contract_gate.json',gate)
    old.write_json(a.output/'contract_push.json',json.loads(a.push_receipt.read_text()))
    state=dict(status='RUNNING',started_utc=old.utc(),source_commit=old.git('rev-parse','HEAD').decode().strip(),complete_batches=0)
    result=execute(board,names,state)
    print(result['status']+' batches='+str(result['complete_batches'])+' '+result.get('reason',''),flush=True)
    raise SystemExit(0 if result['status']=='COMPLETE' else 2)


if __name__=='__main__':main()
