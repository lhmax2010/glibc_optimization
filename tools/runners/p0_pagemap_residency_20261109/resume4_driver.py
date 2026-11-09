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
    (D / ('resume4_' + name)).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

class Driver:
    def __init__(self):
        path = D / 'resume4_state.json'
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
        name = f'resume4_call_{n:03d}_{label}.raw'
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
        path=D/('resume4_'+name)
        if path.exists(): raise Stop('STOP_LOCAL_DEST_EXISTS '+name)
        self.transfer('pull_'+name.replace('.','_'),['pull','/tmp/p0/'+name,str(path)])
        if not path.is_file(): raise Stop('STOP_PULL_FILE_MISSING '+name)
        return path

class RoundDriver(Driver):
    def identity_once(self):
        super().identity_once()
        body,rc,meta=self.shell_once('uptime','cat /proc/uptime')
        print('UPTIME_RAW',repr(body),flush=True)
        self.s['uptime']=body
        body,rc,meta=self.shell_once('tool_inventory','command -v gdb dd grep pgrep ps 2>&1',absent=True)
        print('TOOL_INVENTORY_RAW',repr(body),'REMOTE_RC',rc,flush=True)
        self.s['tool_inventory']=body
        self.save()
        # command -v with multiple operands does not report each missing name.
        # Verify absent gdb explicitly before applying the user-specified hard gate.
        names={Path(line.strip()).name for line in body.splitlines() if line.strip()}
        if 'gdb' not in names:
            body,rc,meta=self.shell_once('gdb_presence','command -v gdb',absent=True)
            print('GDB_PRESENCE_RAW',repr(body),'REMOTE_RC',rc,flush=True)
            if rc or not body.strip():
                self.s['gdb_dependency_evidence']={
                    'commit':'7289a47b9d24791944cd3b02c00f24b8cb76aa3b',
                    'trim_tool':'tools/reclaim_probe/trim_via_gdb.sh',
                    'source':'requires command -v gdb; otherwise GDB_UNAVAILABLE exit 127; exec gdb -p PID -batch',
                    'xml_tool':'g4_m7.py imports gdb and is sourced by GDB, not standalone',
                    'readme':'tizen_native_evidence_20260904/README.md requires separately installing GDB; no bundled independent injector'}
                self.save()
                raise Stop('HARD_STOP_GDB_MISSING_AND_DEMO_V14_REQUIRES_GDB')
        self.s['tools_ready']=True;self.save()

    def cleanup_root(self):
        # Cleanup only; no reconnect that would switch root back on.
        try:
            text,meta=self.call('cleanup_root_off',['-s',SERIAL,'root','off'])
            print('ROOT_OFF_RAW',repr(text),flush=True)
            if re.search(r'error|failed|unable|cannot|denied',text,re.I):
                raise Stop('ROOT_OFF_TEXT '+text)
            text,rc,meta=self.shell_once('cleanup_id_u','id -u')
            print('UID_AFTER_ROOT_OFF',repr(text),flush=True)
            if text.strip()!='5001':raise Stop('ROOT_OFF_UID_NOT_5001 '+text)
            self.s['cleanup']={'root_off':'COMPLETE','uid':5001,'utc':utc()}
        except Exception as e:
            self.s['cleanup']={'root_off':'UNCONFIRMED','reason':str(e),'utc':utc()}
        self.save()

if __name__=='__main__':
    b=RoundDriver()
    try:
        if sys.argv[1]!='stage0':raise Stop('Unsupported stage')
        b.start()
        b.shell('mkdir_p0','mkdir -p /tmp/p0')
        b.s['stage0']='COMPLETE';b.save()
        print('STAGE0_READY',flush=True)
    except Stop as e:
        b.s.update(status='STOPPED',reason=str(e),stopped_utc=utc());b.save()
        print('STOP',str(e),flush=True)
        if any(x['label']=='root_on' for x in b.s['records']):b.cleanup_root()
        sys.exit(2)
