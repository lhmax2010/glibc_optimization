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
    (D / ('resume7_' + name)).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

class Driver:
    def __init__(self):
        path = D / 'resume7_state.json'
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
        name = f'resume7_call_{n:03d}_{label}.raw'
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
        path=D/('resume7_'+name)
        if path.exists(): raise Stop('STOP_LOCAL_DEST_EXISTS '+name)
        self.transfer('pull_'+name.replace('.','_'),['pull','/tmp/p0/'+name,str(path)])
        if not path.is_file(): raise Stop('STOP_PULL_FILE_MISSING '+name)
        return path

class RoundDriver(Driver):
    def __init__(self):
        super().__init__();self.cleaning=False

    def call(self,label,args,timeout=30):
        if not self.cleaning and self.s['calls']>=138:raise Stop('STOP_RESERVE_12_CLEANUP_CALLS')
        return super().call(label,args,timeout)

    def identity_once(self):
        super().identity_once()
        for label,cmd in [('uptime','cat /proc/uptime'),('memtotal','grep MemTotal /proc/meminfo'),
                          ('tools','command -v dd grep pgrep ps tar 2>&1'),('df_before','df -k /opt/usr'),
                          ('mount_optusr','grep " /opt/usr " /proc/mounts')]:
            body,rc,meta=self.shell_once(label,cmd,absent=label=='tools')
            self.s[label]=body;print('BASELINE',label,repr(body),flush=True)
        mounts=self.s['mount_optusr'].splitlines()
        if len(mounts)!=1:raise Stop('STOP_OPTUSR_MOUNT_AMBIGUOUS')
        fields=mounts[0].split();flags=fields[3].split(',')
        if fields[0]!='/dev/mmcblk0p5' or fields[1]!='/opt/usr' or 'rw' not in flags or 'noexec' in flags:
            raise Stop('HARD_STOP_OPTUSR_MOUNT_REQUIREMENTS')
        lines=self.s['df_before'].splitlines()
        free=int(lines[-1].split()[-3])
        if free*1024<500_000_000:raise Stop('HARD_STOP_OPTUSR_FREE_BELOW_500MB')
        self.s['tar_available']=any(Path(x).name=='tar' for x in self.s['tools'].splitlines())
        self.shell_once('mkdir_p0','mkdir -p /opt/usr/p0/data')
        self.s['directory_created']=True;self.save()

    def pull(self,label,remote,local):
        local=Path(local)
        if local.exists():raise Stop('STOP_DEST_EXISTS '+str(local))
        self.transfer(label,['pull',remote,str(local)])
        if not local.is_file():raise Stop('STOP_PULL_MISSING '+str(local))
        return local

    def cleanup(self):
        self.cleaning=True;errors=[]
        def attempt(label,fn):
            try:return fn()
            except Exception as e:
                errors.append(label+': '+str(e));print('CLEANUP_ERROR',label,str(e),flush=True)
        if self.s.get('directory_created') and self.s.get('tar_available'):
            packed=attempt('archive_data',lambda:self.shell('archive_data','cd /opt/usr/p0 && tar cf data.tar data',timeout=120,replay=False))
            if packed is not None:
                attempt('pull_data',lambda:self.pull('pull_data','/opt/usr/p0/data.tar',D/'resume7_data.tar'))
        attempt('remove_p0',lambda:self.shell('remove_p0','rm -rf /opt/usr/p0',replay=False))
        result=attempt('p0_absent',lambda:self.shell('p0_absent','ls /opt/usr/p0 2>&1',absent=True))
        if result is not None and (result[1]==0 or 'No such file or directory' not in result[0]):errors.append('p0 absence unconfirmed')
        attempt('df_after',lambda:self.shell('df_after','df -k /opt/usr'))
        result=attempt('root_off',lambda:self.call('cleanup_root_off',['-s',SERIAL,'root','off']))
        if result is not None and re.search(r'error|failed|cannot|denied',result[0],re.I):errors.append('root off text error')
        result=attempt('uid_after',lambda:self.shell_once('cleanup_id_u','id -u'))
        if result is not None and result[0].strip()!='5001':errors.append('UID not restored to 5001')
        self.s['cleanup']={'utc':utc(),'complete':not errors,'errors':errors};self.save()

def extract_files(archive,destination):
    import tarfile
    from pathlib import PurePosixPath
    destination.mkdir(exist_ok=False)
    paths=[]
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            pp=PurePosixPath(m.name)
            if pp.is_absolute() or '..' in pp.parts:raise Stop('STOP_UNSAFE_TAR_PATH '+m.name)
            if m.isdir():continue
            if not (m.isfile() or m.islnk()):raise Stop('STOP_TAR_NOT_REGULAR '+m.name)
            expected_size=m.size
            if m.islnk():
                link=PurePosixPath(m.linkname)
                if link.is_absolute() or '..' in link.parts:raise Stop('STOP_UNSAFE_TAR_LINK '+m.linkname)
                target=t.getmember(m.linkname)
                if not target.isfile():raise Stop('STOP_TAR_LINK_TARGET_NOT_REGULAR '+m.linkname)
                expected_size=target.size
            path=destination.joinpath(*pp.parts);path.parent.mkdir(parents=True,exist_ok=True)
            with t.extractfile(m) as src,path.open('xb') as dst:
                while True:
                    chunk=src.read(65536)
                    if not chunk:break
                    dst.write(chunk)
            if path.stat().st_size!=expected_size:raise Stop('STOP_TAR_SIZE '+m.name)
            paths.append(path)
    return paths
