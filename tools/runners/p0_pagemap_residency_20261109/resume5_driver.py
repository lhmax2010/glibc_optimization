#!/usr/bin/env python3
"""Local-only bounded serial SDB driver. No new injection implementation."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

D = Path(__file__).resolve().parent
ROOT = D.parents[1]
SDB = '/home/linhao/.local/bin/sdb'
IP = os.environ.get('P0_BOARD_IP', '').strip()
if not IP:
    print('P0_BOARD_IP is required; no default board address', file=sys.stderr)
    raise SystemExit(2)
SERIAL = IP + ':26101'
SUFFIX = ';r=$?;printf "\\nRC=%s\\n" "$r";[ "$r" = 0 ]&&echo DONE||echo FAIL'
CHANNEL = re.compile(r'broken pipe|protocol fault|connection reset|failed to connect|server is not running|device not found|device offline|closed connection', re.I)

class Stop(RuntimeError): pass
class Channel(Stop): pass

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name, value):
    (D / ('resume5_' + name)).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

class Driver:
    def __init__(self):
        path = D / 'resume5_state.json'
        self.s = json.loads(path.read_text()) if path.exists() else dict(calls=0, reconnects=0, channel_failures=0, last_end_monotonic=0, records=[])
        actual = hashlib.sha256((D/'prediction.txt').read_bytes()).hexdigest()
        if actual != 'ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14':
            raise Stop('STOP_PREDICTION_HASH')

    def save(self): write('state.json', self.s)

    def call(self, label, args, timeout=30):
        if self.s['calls'] >= 150: raise Stop('STOP_CALL_BUDGET_150')
        time.sleep(max(0, self.s['last_end_monotonic'] + .5 - time.monotonic()))
        self.s['calls'] += 1
        n = self.s['calls']
        name = f'resume5_call_{n:03d}_{label}.raw'
        meta = dict(n=n, label=label, argv=[SDB]+args, start_utc=utc(), start_ns=time.time_ns(), start_monotonic=time.monotonic(), file=name)
        self.s['records'].append(meta); self.save()
        print('BEGIN', n, label, meta['start_utc'], flush=True)
        try:
            p = subprocess.run([SDB]+args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
            raw, host_rc = p.stdout, p.returncode
        except subprocess.TimeoutExpired as e:
            raw, host_rc = e.stdout or b'', 124
        (D/name).write_bytes(raw)
        self.s['last_end_monotonic'] = time.monotonic()
        meta.update(end_utc=utc(), end_ns=time.time_ns(), host_rc=host_rc, sha256=hashlib.sha256(raw).hexdigest())
        self.save()
        text = raw.decode(errors='replace').replace('\r','')
        if CHANNEL.search(text):
            self.s['channel_failures'] += 1
            self.save()
            print('CHANNEL_FAILURE', n, repr(text), flush=True)
            raise Channel('STOP_CHANNEL ' + label)
        if host_rc != 0:
            raise Stop('STOP_HOST_RC ' + label + ' rc=' + str(host_rc))
        print('END', n, label, 'bytes='+str(len(raw)), flush=True)
        return text, meta

    def shell_once(self, label, command, timeout=30, absent=False):
        if '\n' in command or len((command+SUFFIX).encode()) > 200:
            raise Stop('STOP_PAYLOAD_200_NOT_SENT ' + label)
        text, meta = self.call(label, ['-s',SERIAL,'shell',command+SUFFIX], timeout)
        m = re.search(r'\nRC=(\d+)\n(DONE|FAIL)\s*$', text)
        if not m: raise Stop('STOP_MISSING_REMOTE_RECEIPT ' + label)
        rc = int(m[1]); body = text[:m.start()]
        meta.update(remote_rc=rc, payload_bytes=len((command+SUFFIX).encode()))
        self.save()
        if (m[2]=='DONE') != (rc==0): raise Stop('STOP_BAD_REMOTE_RECEIPT ' + label)
        if rc and not absent: raise Stop('STOP_REMOTE_RC '+label+' rc='+str(rc)+' output='+body[:500])
        if rc == 0 and re.search(r'(?:^|\n)(?:.*: )?(?:error:|Permission denied|command not found|the file is NOT signed)', body, re.I):
            raise Stop('STOP_ERROR_TEXT ' + label + ' ' + body[:500])
        return body, rc, meta

    def identity_once(self):
        text, meta = self.call('root_on', ['-s', SERIAL, 'root', 'on'])
        print('ROOT_ON', repr(text), flush=True)
        if re.search(r'error|failed|unable|cannot|denied',text,re.I): raise Stop('STOP_ROOT_ON_TEXT '+text)
        ident = {}
        for key, command in [('uname_r','uname -r'),('uname_m','uname -m'),('os_release','cat /etc/os-release'),('id_u','id -u')]:
            body, rc, meta = self.shell_once('identity_'+key, command)
            ident[key] = body.strip()
            print('IDENTITY', key, repr(body), flush=True)
        if ident['id_u'] != '0': raise Stop('STOP_ROOT_REQUIRED '+ident['id_u'])
        if not ident['uname_r'] or not ident['uname_m'] or 'BUILD_ID=' not in ident['os_release']:
            raise Stop('STOP_INCOMPLETE_IDENTITY')
        if 'identity' in self.s and self.s['identity'] != ident: raise Stop('STOP_IDENTITY_CHANGED')
        self.s['identity'] = ident
        self.s.setdefault('identities',[]).append(dict(utc=utc(), values=ident, reconnects=self.s['reconnects']))
        self.save()

    def recover(self):
        while True:
            if self.s['channel_failures'] >= 4 or self.s['reconnects'] >= 3:
                raise Stop('STOP_CHANNEL_RECONNECT_LIMIT')
            self.s['reconnects'] += 1; self.save()
            try:
                text, meta = self.call('reconnect', ['connect',IP])
                if re.search(r'error|failed|unable|cannot', text, re.I): raise Stop('STOP_CONNECT_TEXT '+text)
                self.identity_once()
                return
            except Channel:
                continue

    def start(self):
        try:
            text, meta = self.call('connect', ['connect',IP])
            if re.search(r'error|failed|unable|cannot', text, re.I): raise Stop('STOP_CONNECT_TEXT '+text)
            self.identity_once()
        except Channel:
            self.recover()

    def shell(self, label, command, timeout=30, absent=False, replay=True):
        try: return self.shell_once(label,command,timeout,absent)
        except Channel:
            if not replay: raise
            self.recover()
            return self.shell_once(label+'_after_reconnect',command,timeout,absent)

    def transfer(self,label,args):
        try: text,meta=self.call(label,['-s',SERIAL]+args,timeout=120)
        except Channel:
            self.recover();text,meta=self.call(label+'_after_reconnect',['-s',SERIAL]+args,timeout=120)
        if re.search(r'error:|failed|cannot|permission denied|NOT signed',text,re.I):
            raise Stop('STOP_TRANSFER_TEXT '+label+' '+text)
        return text,meta

    def pull_file(self,name):
        path=D/('resume5_'+name)
        if path.exists(): raise Stop('STOP_LOCAL_DEST_EXISTS '+name)
        self.transfer('pull_'+name.replace('.','_'),['pull','/tmp/p0/'+name,str(path)])
        if not path.is_file(): raise Stop('STOP_PULL_FILE_MISSING '+name)
        return path

class RoundDriver(Driver):
    def __init__(self):
        super().__init__()
        self.cleaning=False
        self.s.setdefault('installed_by_p0',[])

    def call(self,label,args,timeout=30):
        if not self.cleaning and self.s['calls']>=132:
            raise Stop('STOP_BUDGET_RESERVE_18_FOR_CLEANUP')
        return super().call(label,args,timeout)

    def identity_once(self):
        super().identity_once()
        for label,cmd in [('uptime','cat /proc/uptime'),
                          ('tools','command -v dd grep pgrep ps tar rpm 2>&1'),
                          ('df_before','df -k / /tmp'),
                          ('mounts','grep -E " / | /tmp " /proc/mounts')]:
            body,rc,meta=self.shell_once(label,cmd)
            self.s[label]=body
            print('BASELINE',label,repr(body),flush=True)
        self.shell_once('mkdir_p0','mkdir -p /tmp/p0')
        self.save()

    def baseline(self):
        # Capture before any possible stop, so mandatory cleanup can compare.
        self.shell('rpmqa_before','rpm -qa | sort > /tmp/p0/rpmqa_before.txt',timeout=90)
        path=self.pull_file('rpmqa_before.txt')
        names=path.read_text().splitlines()
        if not names: raise Stop('STOP_EMPTY_RPM_BASELINE')
        self.s['rpmqa_before_file']=path.name
        self.s['rpmqa_before_count']=len(names)
        self.save()

    def cleanup(self):
        self.cleaning=True
        errors=[]
        def attempt(label,fn):
            try:return fn()
            except Exception as e:
                errors.append(label+': '+str(e));print('CLEANUP_ERROR',label,str(e),flush=True)
                return None
        installed=self.s['installed_by_p0']
        if self.s.get('install_started') and not self.s.get('install_accounted'):
            errors.append('Installation outcome unaccounted; never infer packages to uninstall')
        if installed:
            text,rc,meta=self.shell('installed_manifest_read','cat /tmp/p0/installed_by_p0.txt')
            if text.splitlines()!=installed:raise Stop('STOP_UNINSTALL_MANIFEST_MISMATCH')
            args='$(cat /tmp/p0/installed_by_p0.txt)'
            result=attempt('rpm_erase_test',lambda:self.shell('rpm_erase_test','rpm -e --test '+args,timeout=120,replay=False))
            if result is not None:
                attempt('rpm_erase',lambda:self.shell('rpm_erase','rpm -e '+args,timeout=120,replay=False))
        attempt('rpmqa_after',lambda:self.shell('rpmqa_after','rpm -qa | sort > /tmp/p0/rpmqa_after.txt',timeout=90))
        path=attempt('pull_rpmqa_after',lambda:self.pull_file('rpmqa_after.txt'))
        if path is not None and self.s.get('rpmqa_before_file'):
            import difflib
            before=(D/self.s['rpmqa_before_file']).read_text()
            after=path.read_text()
            diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='rpmqa_before',tofile='rpmqa_after'))
            (D/'resume5_rpmqa.diff').write_text(diff)
            self.s['rpmqa_equal']=not diff
            if diff:errors.append('rpmqa differs; no automatic repair')
        else:
            self.s['rpmqa_equal']=None
            errors.append('rpmqa before/after unavailable')
        attempt('gdb_after',lambda:self.shell('gdb_after','command -v gdb 2>&1',absent=True))
        packed=attempt('archive_data',lambda:self.shell('archive_data','tar -C /tmp/p0 --exclude=rpms --exclude=gdbroot --exclude=all_data.tar -cf /tmp/p0/all_data.tar .',timeout=120))
        if packed is not None:
            attempt('pull_archive',lambda:self.pull_file('all_data.tar'))
        attempt('remove_tmp',lambda:self.shell('remove_tmp','rm -rf /tmp/p0',replay=False))
        result=attempt('tmp_absent',lambda:self.shell('tmp_absent','ls /tmp/p0 2>&1',absent=True))
        if result is not None:
            body,rc,meta=result
            if rc==0 or 'No such file or directory' not in body:errors.append('/tmp/p0 absence not confirmed')
        attempt('df_after',lambda:self.shell('df_after','df -k / /tmp'))
        result=attempt('root_off',lambda:self.call('cleanup_root_off',['-s',SERIAL,'root','off']))
        if result is not None and re.search(r'error|failed|cannot|denied',result[0],re.I):errors.append('root off error text')
        result=attempt('uid_after',lambda:self.shell_once('cleanup_id_u','id -u'))
        if result is not None and result[0].strip()!='5001':errors.append('UID after root off is not 5001')
        self.s['cleanup']={'utc':utc(),'errors':errors,'complete':not errors};self.save()

def reconnaissance(b):
    queries=[('swaps','cat /proc/swaps',False),('swappiness','cat /proc/sys/vm/swappiness',False),
      ('meminfo','grep -E "MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree" /proc/meminfo',False),
      ('zram_devices','ls /sys/block/ | grep zram',True)]
    observations={}
    for label,cmd,optional in queries:
        body,rc,meta=b.shell(label,cmd,absent=optional);observations[label]={'text':body,'rc':rc}
    if 'zram0' in observations['zram_devices']['text'].splitlines():
        for name in ['disksize','mm_stat','comp_algorithm']:
            label='zram_'+name;body,rc,meta=b.shell(label,'cat /sys/block/zram0/'+name)
            observations[label]={'text':body,'rc':rc}
    queries=[('psi','cat /proc/pressure/memory',True),('cgroup_filesystems','grep cgroup /proc/filesystems',True),
      ('cgroup_top','ls /sys/fs/cgroup/',True),
      ('memory_controller','find /sys/fs/cgroup -maxdepth 2 \\( -name memory.max -o -name memory.limit_in_bytes \\) 2>/dev/null | head -5',False),
      ('resourced_pid','pgrep -l resourced',True),('resourced_dir','ls /etc/resourced/ 2>&1',True)]
    for label,cmd,optional in queries:
        body,rc,meta=b.shell(label,cmd,absent=optional);observations[label]={'text':body,'rc':rc}
    if observations['resourced_dir']['rc']==0:
        body,rc,meta=b.shell('resourced_config','cat /etc/resourced/*.conf',absent=True)
        observations['resourced_config']={'text':body,'rc':rc}
    write('zram_observations.json',observations)
    b.s['reconnaissance']='COMPLETE';b.save()

def symbols(b):
    for label,command in [('hits_lib','grep -l malloc_trim /usr/lib/lib*.so* 2>/dev/null > /tmp/p0/hits_lib.txt'),
                          ('hits_bin','grep -l malloc_trim /usr/bin/* 2>/dev/null > /tmp/p0/hits_bin.txt')]:
        body,rc,meta=b.shell(label,command,timeout=240,absent=True)
        if rc not in (0,1):raise Stop('STOP_GREP_SCAN_ERROR '+label+' rc='+str(rc))
    focus,rc,meta=b.shell('focus_ls','ls -l /usr/lib/libappcore* /usr/lib/libcapi-appfw-* /usr/bin/resourced 2>&1',absent=True)
    print('FOCUS_RAW',focus,flush=True)
    lib=b.pull_file('hits_lib.txt');exe=b.pull_file('hits_bin.txt')
    libs=lib.read_text().splitlines();bins=exe.read_text().splitlines();hits=sorted(set(libs+bins))
    b.s['symbol_hits']=hits
    b.s['libc_positive_control']='/usr/lib/libc.so.6' in libs
    b.save()
    if not b.s['libc_positive_control']:raise Stop('HARD_STOP_LIBC_POSITIVE_CONTROL_MISSING')
    if len(hits)>50:raise Stop('STOP_ELF_COUNT_OVER_50')
    for name in hits:
        if not re.fullmatch(r'/usr/(?:lib/lib|bin/)[a-zA-Z0-9_.+/-]+',name):raise Stop('STOP_UNSAFE_ELF_PATH '+name)
    body,rc,meta=b.shell('elf_sizes','cat /tmp/p0/hits_*.txt | while read f;do stat -Lc "%s %n" "$f";done')
    sizes={}
    for line in body.splitlines():
        size,name=line.split(' ',1);sizes[name]=int(size)
    if set(sizes)!=set(hits):raise Stop('STOP_ELF_SIZE_LIST_MISMATCH')
    b.s['symbol_total_bytes']=sum(sizes.values());b.save()
    if sum(sizes.values())>200_000_000:raise Stop('STOP_ELF_BYTES_OVER_200MB')
    folder=D/'resume5_elf';folder.mkdir(exist_ok=False)
    rows=[]
    for name in hits:
        if Path(name).name=='libc.so.6':continue
        target=folder/name.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
        b.transfer('pull_elf_'+str(len(rows)+1),['pull',name,str(target)])
        if target.stat().st_size!=sizes[name]:raise Stop('STOP_ELF_PULL_SIZE '+name)
        result=subprocess.run(['/usr/bin/readelf','-sW','--dyn-syms',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (D/f'resume5_readelf_{len(rows)+1:02d}.stdout').write_bytes(result.stdout)
        (D/f'resume5_readelf_{len(rows)+1:02d}.stderr').write_bytes(result.stderr)
        matched=[line for line in result.stdout.decode(errors='replace').splitlines() if 'malloc_trim' in line]
        row=dict(path=name,bytes=sizes[name],sha256=hashlib.sha256(target.read_bytes()).hexdigest(),readelf_rc=result.returncode,lines=matched,
                 kind='symbol' if matched else 'string_only',definitions=[line for line in matched if ' UND ' not in line],imports=[line for line in matched if ' UND ' in line])
        rows.append(row);write('symbols.json',rows)
        if result.returncode:raise Stop('STOP_HOST_READELF_ERROR '+name)
    b.s['symbols']='COMPLETE';b.save();print('SYMBOL_SUMMARY',json.dumps(rows,ensure_ascii=False),flush=True)

if __name__=='__main__':
    b=RoundDriver()
    try:
        if sys.argv[1]!='phase_a':raise Stop('Unknown phase')
        b.start();b.baseline();reconnaissance(b);symbols(b)
        b.s['phase_a']='COMPLETE';b.save();print('PHASE_A_COMPLETE',flush=True)
    except Exception as e:
        b.s.update(status='STOPPED',reason=str(e),stopped_utc=utc());b.save();print('STOP',str(e),flush=True)
        b.cleanup()
        sys.exit(2)

