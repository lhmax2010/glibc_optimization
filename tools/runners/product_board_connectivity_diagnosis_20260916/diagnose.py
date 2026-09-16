#!/usr/bin/env python3
"""Host-only recorder for the PM-authorized connectivity diagnosis; no sampling."""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import time

SUFFIX = ';r=$?;echo;echo RC=$r;test $r = 0 && echo DONE || echo FAIL'
SSH_READS = (
    ('uname_r', 'uname -r'), ('uname_m', 'uname -m'),
    ('os_release', 'cat /etc/os-release'), ('ps', 'ps -ef'),
    ('sdbd_status', 'systemctl --no-pager --full status sdbd'),
)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def tcp_probe(address, port, banner=False):
    """Connect once, send zero payload bytes; cap connect+recv at three seconds."""
    start = time.monotonic()
    connected = False
    payload = b''
    result = {'address': address, 'port': port, 'sent_bytes': 0}
    try:
        with socket.create_connection((address, port), timeout=3) as stream:
            connected = True
            result['tcp_connected'] = True
            if banner:
                stream.settimeout(max(0.001, 3-(time.monotonic()-start)))
                payload = stream.recv(4096)
                result['receive'] = 'data' if payload else 'EOF'
            else:
                result['receive'] = 'not requested'
    except OSError as error:
        result.update(error_type=type(error).__name__, error=str(error),
                      errno=error.errno, tcp_connected=connected)
    result.update(elapsed_seconds=time.monotonic()-start)
    if banner:
        result.update(received_bytes=len(payload), received_repr=repr(payload),
                      received_hex=payload.hex())
    return (0 if connected else 1), json.dumps(result, indent=2)+'\n'


class Recorder:
    def __init__(self, output):
        self.output = output
        output.mkdir(parents=True, exist_ok=False)
        (output/'raw').mkdir()

    def save(self, label, argv, started, rc, stdout, stderr=b'', **extra):
        if isinstance(stdout, str):
            stdout = stdout.encode()
        paths = {}
        for name, value in (('stdout', stdout), ('stderr', stderr)):
            path = self.output/'raw'/(label+'.'+name+'.txt')
            path.write_bytes(value)
            paths[name] = {'path': str(path.relative_to(self.output)),
                           'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
        record = dict(label=label, argv=argv, started_utc=started, ended_utc=utc(),
                      host_rc=rc, streams=paths, **extra)
        with (self.output/'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(record)+'\n')
        print('%s host_rc=%s' % (label, rc), flush=True)
        return rc, stdout.decode(errors='replace'), stderr.decode(errors='replace')

    def command(self, label, argv, timeout=15):
        started = utc()
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=timeout,
                                  env={**os.environ, 'LC_ALL': 'C'})
            return self.save(label, argv, started, proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired as error:
            return self.save(label, argv, started, 124, error.stdout or b'', error.stderr or b'',
                             host_timeout_seconds=timeout)
        except OSError as error:
            return self.save(label, argv, started, 127, b'', str(error).encode())

    def tcp(self, label, address, port, banner=False):
        started = utc()
        rc, output = tcp_probe(address, port, banner)
        return self.save(label, ['python/socket', address, str(port), 'recv-only' if banner else 'connect-only'],
                         started, rc, output)


def ssh_argv(address, command):
    return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
            '-o', 'ConnectionAttempts=1', '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null', '-o', 'GlobalKnownHostsFile=/dev/null',
            '-o', 'UpdateHostKeys=no', '-o', 'ControlMaster=no',
            'root@'+address, command]


def remote_body(command):
    if command not in dict(SSH_READS).values():
        raise ValueError('remote operation outside the five authorized reads')
    body = 'LC_ALL=C '+command+SUFFIX
    if len(body.encode()) > 200:
        raise ValueError('remote request exceeds 200 bytes; not sent')
    return body


def diagnose(recorder, address):
    ipaddress.IPv4Address(address)  # literal endpoint; no DNS/command injection
    summary = {'started_utc': utc(), 'board_alias': '<PRODUCT_BOARD_IP>'}
    recorder.command('ping', ['ping', '-n', '-c', '4', '-W', '2', address], timeout=12)
    sdb_port = recorder.tcp('tcp_26101', address, 26101)
    ssh_port = recorder.tcp('tcp_22', address, 22)
    recorder.tcp('tcp_local_26099_before', '127.0.0.1', 26099)
    recorder.command('arp', ['ip', 'neigh', 'show', 'to', address])
    recorder.command('sdb_version', ['sdb', 'version'])
    recorder.command('local_listener_before', ['ss', '-ltnp', 'sport = :26099'])
    recorder.command('local_sdb_before', ['pgrep', '-a', '-x', 'sdb'])
    recorder.command('sdb_kill_server', ['sdb', 'kill-server'])
    recorder.command('sdb_start_server', ['sdb', 'start-server'])
    recorder.command('local_listener_after', ['ss', '-ltnp', 'sport = :26099'])
    recorder.command('local_sdb_after', ['pgrep', '-a', '-x', 'sdb'])
    recorder.tcp('tcp_local_26099_after', '127.0.0.1', 26099)
    connect = recorder.command('sdb_connect_default', ['sdb', 'connect', address])
    recorder.command('sdb_devices', ['sdb', 'devices'])
    failed = connect[0] != 0 or any(word in (connect[1]+connect[2]).lower()
                                   for word in ('failed', 'error', 'unable', 'cannot'))
    if sdb_port[0] == 0 and failed:
        recorder.tcp('sdb_banner', address, 26101, banner=True)
        summary['banner'] = 'attempted: TCP reachable and sdb connect failed'
    else:
        summary['banner'] = 'not applicable: TCP unreachable or no reported connect failure'
    recorder.command('sdb_connect_explicit', ['sdb', 'connect', address+':26101'])
    if ssh_port[0] != 0:
        summary['ssh'] = 'SKIPPED: TCP/22 unreachable; PM conditional skip'
    else:
        ssh = recorder.command('ssh_uname_a', ssh_argv(address, 'uname -a'))
        summary['ssh'] = 'host_rc='+str(ssh[0])
        if ssh[0] == 0:
            for label, command in SSH_READS:
                rc, stdout, stderr = recorder.command('ssh_'+label, ssh_argv(address, remote_body(command)))
                lines = stdout.replace('\r', '').splitlines()
                valid = len(lines) >= 2 and lines[-2].startswith('RC=')
                if valid:
                    try:
                        remote_rc = int(lines[-2][3:])
                        valid = 0 <= remote_rc <= 255 and lines[-1] == ('DONE' if remote_rc == 0 else 'FAIL')
                    except ValueError:
                        valid = False
                if rc or not valid:
                    summary['ssh_read_stop'] = label+': missing remote proof or transport failed'
                    break
    summary.update(ended_utc=utc(), status='DIAGNOSIS_FINISHED_NO_MEASUREMENTS')
    (recorder.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ipaddress.IPv4Address(args.ip)
    diagnose(Recorder(args.output), args.ip)
