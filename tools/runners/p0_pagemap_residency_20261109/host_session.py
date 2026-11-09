#!/usr/bin/env python3
"""Local evidence capture; one shell, bounded requests, no automatic retries."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
SDB = '/home/linhao/.local/bin/sdb'
TARGET = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('P0_BOARD_IP', '')).strip()
if not TARGET:
    print('board address argument or P0_BOARD_IP is required', file=sys.stderr)
    raise SystemExit(2)
SERIAL = TARGET + ':26101'

def record(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def stamp():
    return {'epoch_ns': time.time_ns(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}

def local(label, args):
    meta = {'argv': args, 'start': stamp()}
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        raw, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as e:
        raw, rc = e.stdout or b'', 124
    (OUT / (label + '.raw')).write_bytes(raw)
    meta.update(end=stamp(), host_rc=rc, sha256=hashlib.sha256(raw).hexdigest())
    record(label + '.json', meta)
    print(label, raw.decode(errors='replace'), 'HOST_RC', rc, flush=True)
    if rc or re.search(rb'failed|cannot|error|unable', raw, re.I):
        raise RuntimeError('STOP ' + label + ': transport failed')
    return raw

class Session:
    def __init__(self):
        self.p = subprocess.Popen([SDB, '-s', SERIAL, 'shell'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.p.stdout, selectors.EVENT_READ)
        self.raw = (OUT / 'session.raw').open('wb')
        self.journal = (OUT / 'commands.jsonl').open('w')
        self.seq = 0
        self.buffer = b''
        record('session_start.json', stamp())

    def request(self, label, command):
        if not re.fullmatch(r'[a-zA-Z0-9_]+', label) or '\n' in command:
            raise ValueError('STOP invalid label or multiline request')
        self.seq += 1
        key = 'P0_' + str(self.seq)
        begin = ('BEGIN_' + key).encode()
        end = ('END_' + key).encode()
        payload = ("printf '\\nBEGIN_" + key + "\\n'; " + command +
                   "; r=$?; printf '\\nEND_" + key + " RC=%s ' \"$r\"; " +
                   'if [ "$r" -eq 0 ]; then echo DONE; else echo FAIL; fi\n').encode()
        if len(payload) > 200:
            raise ValueError('STOP payload exceeds 200 bytes; not sent')
        meta = {'label': label, 'command': command, 'payload_bytes': len(payload), 'start': stamp()}
        self.journal.write(json.dumps(meta, ensure_ascii=False) + '\n'); self.journal.flush()
        self.p.stdin.write(payload); self.p.stdin.flush()
        lines = []
        active = False
        last = time.monotonic()
        while True:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                line = line.rstrip(b'\r')
                if line == begin:
                    active = True
                    continue
                m = re.fullmatch(re.escape(end) + rb' RC=(\d+) (DONE|FAIL)', line)
                if active and m:
                    rc = int(m[1]); raw = b'\n'.join(lines) + b'\n'
                    (OUT / (label + '.raw')).write_bytes(raw)
                    meta.update(end=stamp(), remote_rc=rc, sha256=hashlib.sha256(raw).hexdigest())
                    record(label + '.json', meta)
                    print('BOARD_RESULT', json.dumps({'label': label, 'rc': rc,
                          'text': raw.decode(errors='replace')}, ensure_ascii=False), flush=True)
                    if (m[2] == b'DONE') != (rc == 0) or rc:
                        raise RuntimeError('STOP remote command failure: ' + label)
                    return raw
                if active:
                    lines.append(line)
            remaining = 15 - (time.monotonic() - last)
            if remaining <= 0 or not self.sel.select(remaining):
                raise RuntimeError('STOP session silent for 15 seconds')
            chunk = os.read(self.p.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('STOP session disconnected')
            last = time.monotonic()
            self.raw.write(chunk); self.raw.flush(); self.buffer += chunk

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.terminate()  # Host client only; no board process signal.
            self.p.wait(timeout=5)
        self.sel.close(); self.raw.close(); self.journal.close()
        record('session_end.json', dict(stamp(), host_rc=self.p.returncode))

session = None
try:
    local('connect', [SDB, 'connect', TARGET])
    devices = local('devices', [SDB, 'devices'])
    if not re.search(re.escape(SERIAL.encode()) + rb'\s+device(?:\s|$)', devices):
        raise RuntimeError('STOP target not listed as device')
    session = Session()
    for label, cmd in [('uname_r', 'uname -r'), ('uname_m', 'uname -m'),
                       ('os_release', 'cat /etc/os-release')]:
        session.request(label, cmd)
    uid = session.request('id_u', 'id -u').strip()
    if uid != b'0':
        raise RuntimeError('STOP_ROOT_REQUIRED observed UID=' + uid.decode(errors='replace'))
    print('READY_FOR_TASKS', flush=True)
    for line in sys.stdin:
        q = json.loads(line)
        if q.get('stop'):
            break
        session.request(q['label'], q['command'])
    record('state.json', {'status': 'SESSION_CLOSED', 'end': stamp()})
except Exception as e:
    record('state.json', {'status': 'STOPPED', 'reason': str(e), 'end': stamp()})
    print(str(e), flush=True)
    sys.exit(2)
finally:
    if session is not None:
        session.close()
