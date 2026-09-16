#!/usr/bin/env python3
"""Host-driven product TV observation. Never uploads or writes on the board."""
import argparse
import concurrent.futures
import csv
import datetime
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from analyze_floor import analyze, proc_stat, smaps

spec = importlib.util.spec_from_file_location('bounded_single_request',
    ROOT/'tools/runners/system_level_before_after_20260908/single_request.py')
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
TAG = 'product-floor-contract-20260916'
PINNED_FILES = [str((HERE/name).relative_to(ROOT)) for name in ('contract.json', 'analyze_floor.py')]
PINNED_FILES.append('tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def contract_gate(receipt):
    if receipt['tag'] != TAG or git('cat-file', '-t', TAG).strip() != b'tag':
        raise ValueError('STOP annotated contract tag required')
    if git('rev-parse', TAG).decode().strip() != receipt['tag_object']:
        raise ValueError('STOP tag object differs from push receipt')
    commit = git('rev-parse', TAG+'^{commit}').decode().strip()
    if commit != receipt['commit']:
        raise ValueError('STOP contract commit differs')
    for path in PINNED_FILES:
        if git('show', commit+':'+path) != (ROOT/path).read_bytes():
            raise ValueError('STOP frozen contract/analyzer changed: '+path)
    refs = git('ls-remote', 'origin', 'refs/tags/'+TAG).decode().split()
    if not refs or refs[0] != receipt['tag_object']:
        raise ValueError('STOP remote contract tag not confirmed')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != receipt['boot_id']:
        raise ValueError('STOP host reboot invalidates monotonic receipt')
    interval = min((time.time_ns()-receipt['epoch_ns'])/1e9,
                   (time.monotonic_ns()-receipt['monotonic_ns'])/1e9)
    if interval < 600:
        raise ValueError('STOP contract push interval below 600 s: %.3f' % interval)
    return {'interval_seconds': interval, 'checked_utc': utc(), 'commit': commit,
            'tag_object': receipt['tag_object'], 'files_sha256': {
                p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in PINNED_FILES}}


def readonly_body(argv):
    # The inherited transport also supports old cleanup operations; do NOT
    # expose those capabilities in this round. Exact read-only argument gate.
    # Two additional, exact queries explicitly required by the PM continuation.
    # Do not extend the historical cleanup transport's executable allowlist.
    if argv in (['/lib/libc.so.6'], ['getconf', 'CLK_TCK']):
        body = 'LC_ALL=C ' + ' '.join(argv) + single.SUFFIX
        single.check_body(body)
        return body
    valid = argv in (['uname', '-r'], ['uname', '-m'], ['id'], ['ps', '-ef'],
                     ['ls', '/proc'], ['uptime'], ['date', '-u'], ['df', '-h'],
                     ['rpm', '-q', 'glibc'], ['rpm', '-q', 'gdb'])
    if len(argv) == 2 and argv[0] == 'cat':
        valid = argv[1] in ('/etc/os-release', '/proc/meminfo', '/proc/swaps', '/proc/uptime',
                           '/proc/sys/kernel/yama/ptrace_scope', '/sys/block/zram0/mm_stat',
                           '/sys/devices/system/cpu/online')
        valid |= bool(re.fullmatch(r'/proc/[1-9]\d*/(?:stat|smaps|cmdline)', argv[1]))
    if not valid:
        raise ValueError('LOCAL_STOP operation is not on the readonly allowlist')
    return single.request(argv)  # 200-byte hard bound includes RC/DONE framing.


class Board:
    def __init__(self, address, output, sdb='sdb'):
        self.address = str(ipaddress.IPv4Address(address))
        self.serial = self.address+':26101'
        self.output, self.sdb = output, sdb
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        (output/'raw').mkdir(parents=True, exist_ok=True)

    def call(self, label, arguments, remote=False):
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', label):
            raise ValueError('unsafe local label')
        argv = [self.sdb, *arguments]
        record = {'label': label, 'argv': argv, 'started_utc': utc(), 'started_ns': time.time_ns()}
        path = self.output/'raw'/(label+'.txt')
        if path.exists():
            raise ValueError('refusing duplicate observation: '+label)
        try:
            run = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            raw, host_rc = run.stdout, run.returncode
        except subprocess.TimeoutExpired as error:
            raw, host_rc = (error.stdout or b'')+b'\nHOST_TIMEOUT\n', 124
        record.update(ended_ns=time.time_ns(), ended_utc=utc(), host_rc=host_rc)
        path.write_bytes(raw)
        text = raw.decode('utf-8', errors='replace').replace('\r', '')
        try:
            if remote:
                rc, value = single.parse(text)
                record['remote_rc'] = rc
            else:
                rc, value = host_rc, text
        except ValueError as error:
            record['proof_error'] = str(error)
            raise ValueError('STOP remote proof: '+label) from error
        finally:
            record['raw_sha256'] = hashlib.sha256(raw).hexdigest()
            with self.lock, (self.output/'commands.jsonl').open('a') as stream:
                stream.write(json.dumps(record)+'\n')
        if host_rc == 124:
            raise ValueError('STOP transport timeout: '+label)
        return rc, value

    def read(self, label, argv, optional=False):
        if self.stopped.is_set():
            raise ValueError('STOP prior read failed; no new board request')
        body = readonly_body(argv)
        try:
            rc, value = self.call(label, ['-s', self.serial, 'shell', body], remote=True)
        except (ValueError, OSError):
            self.stopped.set()
            raise
        if rc and not optional:
            self.stopped.set()
            raise ValueError('STOP remote command failed: '+label+' RC='+str(rc))
        return rc, value

    def identity(self):
        self.call('sdb_version', ['version'])
        rc, connect = self.call('connect', ['connect', self.address])
        if rc or not connect.strip() or re.search(r'failed|unable|cannot|error', connect, re.I):
            raise ValueError('STOP connection failed; no retry')
        self.call('devices', ['devices'])
        _, kernel = self.read('uname_r', ['uname', '-r'])
        if 'rpi4' in kernel.lower():
            raise ValueError('STOP_TEST_BOARD: 该 IP 当前指向测试板，需 PM 确认产品板地址')
        _, arch = self.read('uname_m', ['uname', '-m'])
        _, release = self.read('os_release', ['cat', '/etc/os-release'])
        if re.search(r'unified-(toolchain|dev)|\b(?:development|developer|toolchain)\b', release, re.I):
            raise ValueError('STOP_TEST_IMAGE: development image, not confirmed product TV')
        if not re.search(r'Tizen[^\n]*(?:TV|tv)|unified-gbm', release):
            raise ValueError('STOP_PRODUCT_IDENTITY_UNKNOWN: product TV image not established')
        return {'kernel': kernel, 'arch': arch, 'os_release': release}


def globals_at(board, label):
    _, mem = board.read(label+'_mem', ['cat', '/proc/meminfo'])
    match = re.search(r'^MemAvailable:\s+(\d+) kB$', mem, re.M)
    if not match:
        raise ValueError('STOP missing MemAvailable')
    rc, zram = board.read(label+'_zram', ['cat', '/sys/block/zram0/mm_stat'], optional=True)
    if rc:
        raise ValueError('STOP zram unavailable: swap attribution cannot be evaluated; not zero')
    parts = zram.split()
    if len(parts) < 3 or not all(v.isdecimal() for v in parts[:3]):
        raise ValueError('STOP malformed zram mm_stat')
    _, swaps = board.read(label+'_swaps', ['cat', '/proc/swaps'])
    lines = [line.split() for line in swaps.splitlines() if line.strip()]
    if not lines or lines[0] != ['Filename', 'Type', 'Size', 'Used', 'Priority']:
        raise ValueError('STOP missing/malformed swaps table header')
    if any(len(r) != 5 or not r[2].isdecimal() or not r[3].isdecimal()
           or not re.fullmatch(r'-?\d+', r[4]) for r in lines[1:]):
        raise ValueError('STOP malformed swaps table row')
    used = sum(int(r[3]) for r in lines[1:] if 'zram' in r[0])
    return dict(MemAvailable_kb=int(match[1]), zram_used_kb=used,
                **dict(zip(('zram_orig_bytes', 'zram_compr_bytes', 'zram_mem_used_bytes'), map(int, parts[:3]))))


def names_from_mapping(path):
    with path.open() as stream:
        mapping = list(csv.DictReader(stream, delimiter='\t'))
    names = {'enlightenment': 'enlightenment'}
    for alias in ('ServiceA', 'ServiceH'):
        found = [r['original'] for r in mapping if r['replacement'] == alias]
        if len(found) != 1:
            raise ValueError('STOP ambiguous/missing private candidate mapping: '+alias)
        names[alias] = found[0]
    return names


def inventory(board, names):
    _, listing = board.read('process_view', ['ps', '-ef'])
    if not any(re.match(r'^\S+\s+1\s+', line) for line in listing.splitlines()):
        raise ValueError('STOP incomplete process view: PID 1 missing; no root elevation authorized')
    _, proc = board.read('proc_listing', ['ls', '/proc'])
    pids = sorted(int(p) for p in proc.split() if p.isdecimal())
    records, excluded = [], []
    ps_pids = {int(m[1]) for line in listing.splitlines()
               if (m := re.match(r'^\S+\s+(\d+)\s+', line))}
    for pid in sorted(ps_pids-set(pids)):
        rc, value = board.read('inventory_missing_'+str(pid), ['cat', f'/proc/{pid}/stat'], optional=True)
        if rc and 'No such file or directory' in value:
            excluded.append({'pid': pid, 'reason': 'ps process exited before proc listing'})
            continue
        raise ValueError('STOP proc listing omits visible live/inaccessible PID: '+str(pid))
    for pid in pids:
        rc, value = board.read('inventory_stat_'+str(pid), ['cat', f'/proc/{pid}/stat'], optional=True)
        if rc:
            if 'No such file or directory' in value:
                excluded.append({'pid': pid, 'reason': 'exited during inventory'})
                continue
            raise ValueError('STOP incomplete readable process inventory: '+str(pid))
        stat = proc_stat(value)
        flags = int(value[value.rfind(')')+2:].split()[6])
        if flags & 0x200000 or stat['state'] == 'Z':
            excluded.append({'pid': pid, 'reason': 'kernel thread or zombie'})
            continue
        rc, maps = board.read('inventory_smaps_'+str(pid), ['cat', f'/proc/{pid}/smaps'], optional=True)
        if rc:
            if 'No such file or directory' in maps:
                excluded.append({'pid': pid, 'reason': 'exited during inventory'})
                continue
            raise ValueError('STOP unreadable smaps prevents full ranking: '+str(pid))
        rc, after = board.read('inventory_stat_after_'+str(pid), ['cat', f'/proc/{pid}/stat'], optional=True)
        if rc and 'No such file or directory' in after:
            excluded.append({'pid': pid, 'reason': 'exited before identity recheck'})
            continue
        if rc or (proc_stat(after)['pid'], proc_stat(after)['start_ticks']) != (pid, stat['start_ticks']):
            raise ValueError('STOP process identity unavailable/changed during inventory: '+str(pid))
        if not maps.strip():
            raise ValueError('STOP empty smaps for live userspace PID '+str(pid)+
                             '; complete readable ranking not established; seek PM read-access authorization')
        records.append({**stat, **smaps(maps)})
    ranking = sorted(records, key=lambda r: (-r['glibc_heap_pd_kb'], r['pid']))[:10]
    named = [r for r in records if r['comm'] in names.values()]
    selected = {r['pid']: r for r in ranking+named}
    for r in selected.values():
        alias = next((a for a, name in names.items() if name == r['comm']), None)
        r['target'] = (alias or 'Supplement')+'-PID'+str(r['pid'])
    result = {'processes': records, 'top10': ranking, 'selected': list(selected.values()),
              'excluded': excluded, 'named_matches': {a: [r for r in records if r['comm'] == n] for a, n in names.items()},
              'near_matches': {a: [r for r in records if n[:6].lower() in r['comm'].lower() and r['comm'] != n] for a, n in names.items()}}
    write_json(board.output/'inventory.json', result)
    return list(selected.values())


def sample_process(board, candidate, index):
    pid = candidate['pid']
    stem = 's%04d_p%d' % (index, pid)
    _, before = board.read(stem+'_stat_before', ['cat', f'/proc/{pid}/stat'])
    epoch = time.time_ns()
    _, maps = board.read(stem+'_smaps', ['cat', f'/proc/{pid}/smaps'])
    _, after = board.read(stem+'_stat_after', ['cat', f'/proc/{pid}/stat'])
    first, last = proc_stat(before), proc_stat(after)
    if any((r['pid'], r['start_ticks']) != (pid, candidate['start_ticks']) for r in (first, last)):
        board.stopped.set()
        raise ValueError('STOP PID identity changed during observation')
    return dict(sample=index, epoch_ns=epoch, target=candidate['target'], pid=pid,
                start_ticks=first['start_ticks'], minflt=last['minflt'], majflt=last['majflt'], **smaps(maps))


def observe(board, candidates):
    if not candidates:
        raise ValueError('STOP no living candidates')
    all_rows, timing = [], []
    started = time.monotonic()
    path = board.output/'timeseries.tsv'
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)+1) as pool, path.open('w') as stream:
        writer = None
        for i in range(601):
            delay = started+i-time.monotonic()
            if delay > 0:
                time.sleep(delay)
            begin = time.monotonic()
            global_future = pool.submit(globals_at, board, 's%04d' % i)
            futures = [pool.submit(sample_process, board, r, i) for r in candidates]
            try:
                system = global_future.result()
                rows = [{**f.result(), **system} for f in futures]
            except Exception:
                board.stopped.set()
                for future in futures:
                    future.cancel()
                global_future.cancel()
                raise
            if writer is None:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
                writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            all_rows.extend(rows)
            timing.append({'sample': i, 'lateness_s': max(0, begin-started-i), 'read_duration_s': time.monotonic()-begin})
            write_json(board.output/'sampling_timing.json', timing)
            if time.monotonic() >= started+i+1:
                board.stopped.set()
                raise ValueError('STOP 1 s sampling deadline missed; raw partial retained, no floor conclusion')
            if i % 30 == 0:
                print('PROGRESS readonly sample %d/600 candidates=%d' % (i, len(candidates)), flush=True)
    result = analyze(all_rows)
    write_json(board.output/'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--push-receipt', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--sdb', default='sdb')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new: never overwrite or repeat completed observations')
    args.output.mkdir(parents=True)
    state = {'started_utc': utc(), 'status': 'NOT_EXECUTED', 'board_alias': '<PRODUCT_BOARD_IP>'}
    try:
        receipt = json.loads(args.push_receipt.read_text())
        write_json(args.output/'contract_gate.json', contract_gate(receipt))
        names = names_from_mapping(args.mapping)
        board = Board(args.ip, args.output, args.sdb)
        state['identity'] = board.identity()
        baseline = {}
        for label, command in (('id', ['id']), ('glibc', ['rpm', '-q', 'glibc']),
                               ('libc_version', ['/lib/libc.so.6']), ('meminfo', ['cat', '/proc/meminfo']),
                               ('cpu_online', ['cat', '/sys/devices/system/cpu/online']),
                               ('clk_tck', ['getconf', 'CLK_TCK']),
                               ('uptime', ['uptime']), ('date', ['date', '-u']),
                               ('df', ['df', '-h']), ('proc_uptime', ['cat', '/proc/uptime'])):
            baseline[label] = board.read(label, command)[1]
            write_json(args.output/'baseline.json', baseline)
        baseline['gdb'] = board.read('gdb', ['rpm', '-q', 'gdb'], optional=True)
        baseline['ptrace_scope'] = board.read('ptrace_scope', ['cat', '/proc/sys/kernel/yama/ptrace_scope'], optional=True)
        write_json(args.output/'baseline.json', baseline)
        candidates = inventory(board, names)
        state['candidate_count'] = len(candidates)
        observe(board, candidates)
        state['status'] = 'COMPLETE'
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        state.update(status='STOP', reason=str(error))
        print(str(error), flush=True)
    finally:
        state['ended_utc'] = utc()
        write_json(args.output/'state.json', state)
    print('STATUS '+state['status'], flush=True)
    return 0 if state['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
