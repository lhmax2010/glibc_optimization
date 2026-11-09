#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
from resume7_driver import D,RoundDriver,Stop,Channel,write,utc

b=RoundDriver();results=[];invalidated=[];observations=[]

def read_capture(label,key,command):
    cmd=f'cd /opt/usr/p0/data;{command} >{key}.txt 2>{key}.err'
    body,rc,meta=b.shell(label,cmd,absent=True,replay=False)
    path=D/f'resume7_{label}.txt'
    b.pull('pull_'+label,f'/opt/usr/p0/data/{key}.txt',path)
    text=path.read_text()
    if not text.strip():raise Stop('STOP_EMPTY_CAPTURE '+label+' RC='+str(rc))
    return text,rc,meta

def stat_fields(text):
    end=text.rfind(')')
    if end<0:raise Stop('STOP_BAD_PROC_STAT')
    rest=text[end+2:].split()
    return dict(pid=int(text.split(' ',1)[0]),comm=text[text.find('(')+1:end],
                starttime=int(rest[19]),minflt=int(rest[7]),majflt=int(rest[9]))

def select_target(excluded):
    if not excluded:
        text,rc,meta=b.shell('enlightenment_pid','pgrep -x enlightenment',absent=True)
        ids=text.split()
        if rc==0 and len(ids)==1 and ids[0].isdigit():return int(ids[0]),'enlightenment priority'
        if rc==0:raise Stop('STOP_AMBIGUOUS_ENLIGHTENMENT_PID')
    command="awk 'FNR==1{h=0}/\\[heap\\]/{h=1}h&&/Private_Dirty/{print $2,FILENAME;h=0}' /proc/[0-9]*/smaps"
    text,rc,meta=b.shell('heap_ranking',command,absent=True)
    ranking=[]
    for line in text.splitlines():
        m=re.fullmatch(r'(\d+) /proc/(\d+)/smaps',line)
        if m:ranking.append((int(m[1]),int(m[2])))
    ranking.sort(reverse=True);write('heap_ranking.json',ranking)
    candidates=[row for row in (ranking[1:] if excluded else ranking) if row[1] not in excluded]
    if not candidates:raise Stop('STOP_NO_ELIGIBLE_HEAP_TARGET')
    return candidates[0][1],('next-largest after invalidation' if excluded else 'largest heap Private_Dirty')

def sample(pid,tick,n,phase,attempt):
    key=f't{n}_{phase}';tag=f'a{attempt}_{key}'
    cmd="awk '/\\[heap\\]/{f=1} f{print} f&&/^VmFlags/{exit}' /proc/"+str(pid)+"/smaps"
    text,rc,meta=read_capture(tag+'_smaps',key+'_smaps',cmd)
    obs=dict(attempt=attempt,pid=pid,cycle=n,phase=phase,smaps_text=text,smaps_command=meta['file'])
    observations.append(obs);write('observations.json',observations)
    headers=re.findall(r'^([0-9a-f]+)-([0-9a-f]+).*\[heap\]$',text,re.M)
    fields={m[1]:int(m[2]) for m in re.finditer(r'^([A-Za-z_]+):\s+(\d+) kB\s*$',text,re.M)}
    missing=sorted(set(['Size','Rss','Pss','Private_Dirty','Swap'])-fields.keys())
    if len(headers)!=1 or missing:
        obs['missing_required_fields']=missing;write('observations.json',observations)
        raise Stop('STOP_REQUIRED_HEAP_FIELDS_MISSING '+str(missing)+' headers='+str(len(headers)))
    obs['smaps_fields']=fields
    obs['missing_optional_fields']=sorted(set(['SwapPss','LazyFree','Anonymous'])-fields.keys())
    write('observations.json',observations)
    text,rc,meta=read_capture(tag+'_maps',key+'_maps',f'grep "\\[heap\\]" /proc/{pid}/maps')
    ranges=re.findall(r'^([0-9a-f]+)-([0-9a-f]+).*\[heap\]$',text,re.M)
    if ranges!=headers:raise Stop('STOP_HEAP_RANGE_CHANGED_BETWEEN_SMAPS_MAPS')
    start,end=[int(x,16) for x in ranges[0]]
    if start%4096 or end%4096 or end<=start:raise Stop('STOP_INVALID_HEAP_RANGE')
    count=(end-start)//4096;skip=start//4096
    command=f'dd if=/proc/{pid}/pagemap of=/opt/usr/p0/data/{key}_pm.bin bs=8 skip={skip} count={count} 2>/dev/null'
    b.shell(tag+'_dd',command,replay=False)
    path=D/f'resume7_{tag}_pm.bin'
    # No silent retry of post data: the outer handler invalidates this target.
    text,meta=b.call(tag+'_pull_pm',['-s',b_serial(),'pull',f'/opt/usr/p0/data/{key}_pm.bin',str(path)],timeout=120)
    if re.search(r'error:|failed|cannot|denied',text,re.I):raise Stop('STOP_PM_PULL_TEXT '+text)
    data=path.read_bytes()
    if len(data)!=count*8:raise Stop('STOP_PAGEMAP_LENGTH expected='+str(count*8)+' actual='+str(len(data)))
    words=[v[0] for v in struct.iter_unpack('<Q',data)]
    obs.update(start=start,end=end,count=count,present=sum((v>>63)&1 for v in words),swapped=sum((v>>62)&1 for v in words),
               pagemap_file=path.name,pagemap_sha256=hashlib.sha256(data).hexdigest())
    write('observations.json',observations)
    if obs['swapped']!=0:raise Stop('H4_FALSE swapped_pages='+str(obs['swapped']))
    if phase=='pre' and abs(obs['present']*4096-fields['Private_Dirty']*1024)>8192:
        raise Stop('H3_FALSE difference_bytes='+str(obs['present']*4096-fields['Private_Dirty']*1024))
    if phase=='pre':
        text,rc,meta=b.shell(tag+'_xml',f'. /opt/usr/p0/environment;gdb -nx -nh -p {pid} -batch -x /opt/usr/p0/m{n}.gdb',timeout=120,replay=False)
        if re.search(r'Error in sourced command|Permission denied|No such process|Could not|Cannot call|Cannot access',text,re.I):
            raise Stop('STOP_MALLOC_INFO_GDB_ERROR '+text)
        path=D/f'resume7_{tag}.xml'
        text,meta=b.call(tag+'_pull_xml',['-s',b_serial(),'pull',f'/opt/usr/p0/data/t{n}_pre.xml',str(path)],timeout=120)
        if not path.is_file() or b'</malloc>' not in path.read_bytes():raise Stop('STOP_XML_INCOMPLETE')
        if ET.fromstring(path.read_bytes()).tag!='malloc':raise Stop('STOP_XML_ROOT')
        obs['xml_file']=path.name
    text,rc,meta=read_capture(tag+'_stat',key+'_stat',f'cat /proc/{pid}/stat')
    sf=stat_fields(text)
    if sf['pid']!=pid or sf['starttime']!=tick:raise Stop('STOP_TARGET_PID_OR_STARTTIME_CHANGED')
    obs['stat']=sf;write('observations.json',observations)
    return obs

def b_serial():
    from resume7_driver import SERIAL
    return SERIAL

def main():
    b.start()
    b.transfer('push_gdbroot',['push',str(D/'resume6_gdbroot.tar'),'/opt/usr/p0/gdbroot.tar'])
    b.shell('extract_gdbroot','cd /opt/usr/p0 && tar xf gdbroot.tar && rm gdbroot.tar',timeout=180,replay=False)
    b.transfer('push_gdb_environment',['push',str(D/'resume6_gdb_environment.txt'),'/opt/usr/p0/environment'])
    text,rc,meta=b.shell('gdb_version','. /opt/usr/p0/environment;gdb -nx -nh -batch -ex "show version" 2>&1 | head -3')
    if 'GNU gdb (GDB) 16.3' not in text or 'Permission denied' in text:raise Stop('STOP_GDB_VERSION '+text)
    b.s['gdb_ready']=True;b.save()
    b.transfer('push_trim_source',['push',str(D/'resume6_source_trim_via_gdb.sh'),'/opt/usr/p0/trim_via_gdb.sh'])
    for n in (1,2,3):
        content='set pagination off\nset $stream = (void *) fopen("/opt/usr/p0/data/t'+str(n)+'_pre.xml", "w")\ncall (int) malloc_info(0, $stream)\ncall (int) fclose($stream)\ndetach\n'
        path=D/f'resume7_m{n}.gdb'
        with path.open('x') as f:f.write(content)
        b.transfer('push_m'+str(n),['push',str(path),f'/opt/usr/p0/m{n}.gdb'])
    excluded=set();attempt=0
    while True:
        pid,reason=select_target(excluded)
        text,rc,meta=b.shell('target_stat_'+str(attempt),f'cat /proc/{pid}/stat')
        target=stat_fields(text)
        if target['pid']!=pid:raise Stop('STOP_TARGET_PID')
        text,rc,meta=b.shell('target_uptime_'+str(attempt),'cat /proc/uptime')
        target.update(selection=reason,uptime=text,attempt=attempt)
        write('target.json',target);print('TARGET',json.dumps(target),flush=True)
        b.shell('auxv_dd_'+str(attempt),f'dd if=/proc/{pid}/auxv of=/opt/usr/p0/data/auxv.bin 2>/dev/null')
        aux=b.pull('pull_auxv_'+str(attempt),'/opt/usr/p0/data/auxv.bin',D/f'resume7_auxv_a{attempt}.bin')
        data=aux.read_bytes()
        if len(data)%8:raise Stop('STOP_AUXV_LENGTH')
        pairs=list(struct.iter_unpack('<II',data));secure=[v for k,v in pairs if k==23]
        if len(secure)!=1:raise Stop('STOP_AUXV_AT_SECURE_MISSING')
        write('auxv.json',dict(attempt=attempt,pid=pid,AT_SECURE=secure[0],pairs=pairs))
        inflight=False
        try:
            for n in (1,2,3):
                pre=sample(pid,target['starttime'],n,'pre',attempt)
                inflight=True
                text,rc,meta=b.shell(f'a{attempt}_t{n}_trim',f'. /opt/usr/p0/environment;sh /opt/usr/p0/trim_via_gdb.sh {pid}',timeout=120,replay=False)
                returned=re.findall(r'^\$\d+ = (-?\d+)\s*$',text,re.M)
                if len(returned)!=1:raise Stop('STOP_TRIM_RETURN_MISSING '+text)
                trim=dict(return_value=int(returned[0]),elapsed_ms=(meta['end_ns']-meta['start_ns'])/1e6,command_file=meta['file'])
                post=sample(pid,target['starttime'],n,'post',attempt)
                inflight=False
                reclaimed=(pre['smaps_fields']['Private_Dirty']-post['smaps_fields']['Private_Dirty'])*1024
                delta=pre['present']-post['present']
                row=dict(attempt=attempt,pid=pid,cycle=n,pre=pre,post=post,trim=trim,reclaimed_bytes=reclaimed,
                         rss_delta_bytes=(pre['smaps_fields']['Rss']-post['smaps_fields']['Rss'])*1024,
                         minflt_delta=post['stat']['minflt']-pre['stat']['minflt'],majflt_delta=post['stat']['majflt']-pre['stat']['majflt'],
                         H1=reclaimed==delta*4096,H2=None if n==1 else delta<=1 and reclaimed<=4096,
                         H3=abs(pre['present']*4096-pre['smaps_fields']['Private_Dirty']*1024)<=8192,H4=pre['swapped']==post['swapped']==0)
                results.append(row);write('trim_results.json',results)
                print('TRIM_RESULT',json.dumps({k:v for k,v in row.items() if k not in ('pre','post')}),flush=True)
                if not row['H1'] or row['H2'] is False:raise Stop('HYPOTHESIS_FALSE '+json.dumps({k:row[k] for k in ('cycle','H1','H2','reclaimed_bytes')}))
            b.s['measurement']='COMPLETE';b.save();return
        except Channel as e:
            if not inflight:
                b.recover();raise Stop('STOP_CHANNEL_BEFORE_TRIM_NO_MEASUREMENT_REPLAY '+str(e))
            invalidated.append(dict(pid=pid,attempt=attempt,reason=str(e)));write('invalidated.json',invalidated)
            excluded.add(pid);b.recover()
            b.shell('archive_invalid_'+str(attempt),'cd /opt/usr/p0 && tar cf invalid.tar data',replay=False)
            b.pull('pull_invalid_'+str(attempt),'/opt/usr/p0/invalid.tar',D/f'resume7_invalid_a{attempt}.tar')
            attempt+=1

try:
    main();b.s['status']='COMPLETE';b.save()
except Exception as e:
    b.s.update(status='STOPPED',reason=str(e),stopped_utc=utc());b.save();print('STOP',str(e),flush=True)
finally:
    b.cleanup()
sys.exit(0 if b.s.get('status')=='COMPLETE' and b.s['cleanup']['complete'] else 2)
