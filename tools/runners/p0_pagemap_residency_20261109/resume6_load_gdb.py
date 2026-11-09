#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
from resume6_driver import D,RoundDriver,Stop,utc

b=RoundDriver()
try:
    proof=json.loads((D/'resume6_gdbroot_archive.json').read_text())
    archive=D/proof['file']
    h=hashlib.sha256()
    with archive.open('rb') as f:
        for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
    if h.hexdigest()!=proof['sha256']:raise Stop('STOP_HOST_GDBROOT_HASH_CHANGED')
    b.transfer('push_gdbroot',['push',str(archive),'/opt/usr/p0/gdbroot.tar'])
    b.shell('extract_gdbroot','cd /opt/usr/p0 && tar xf gdbroot.tar && rm gdbroot.tar',timeout=180,replay=False)
    text,rc,meta=b.shell('gdb_ld_trace','LD_TRACE_LOADED_OBJECTS=1 LD_LIBRARY_PATH=/opt/usr/p0/gdbroot/usr/lib /opt/usr/p0/gdbroot/usr/bin/gdb 2>&1')
    print('LD_TRACE_RAW',text,flush=True)
    if 'not found' in text:raise Stop('HARD_STOP_GDB_MISSING_SHARED_LIBRARIES '+text)
    if 'Permission denied' in text:raise Stop('HARD_STOP_GDB_EXECUTION_DENIED '+text)
    # The exact requested environment is sourced per invocation to keep each
    # complete remote request, including its receipt, below 200 bytes.
    env='export PATH=/opt/usr/p0/gdbroot/usr/bin:$PATH\nexport LD_LIBRARY_PATH=/opt/usr/p0/gdbroot/usr/lib\nexport PYTHONHOME=/opt/usr/p0/gdbroot/usr\nexport EXPECTED_BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l\n'
    path=D/'resume6_gdb_environment.txt'
    with path.open('x') as f:f.write(env)
    b.transfer('push_gdb_environment',['push',str(path),'/opt/usr/p0/environment'])
    text,rc,meta=b.shell('gdb_version','. /opt/usr/p0/environment;gdb -nx -nh -batch -ex "show version" 2>&1 | head -3')
    print('GDB_VERSION_RAW',text,flush=True)
    if 'Permission denied' in text:raise Stop('HARD_STOP_GDB_EXECUTION_DENIED '+text)
    if 'GNU gdb (GDB) 16.3' not in text:raise Stop('STOP_GDB_VERSION_NOT_EXPECTED '+text)
    b.s['gdb_version']=text;b.s['gdb_ready']=True;b.save()
    print('GDB_READY',flush=True)
except Exception as e:
    b.s.update(status='STOPPED',reason=str(e),stopped_utc=utc());b.save();print('STOP',str(e),flush=True)
    b.cleanup();sys.exit(2)
