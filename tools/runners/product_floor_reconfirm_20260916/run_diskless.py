#!/usr/bin/env python3
"""One authorized readonly root round. No board files or scripts, ever."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_authorized_root as authorized
import run_board_script as previous
from analyze_floor import proc_stat, smaps
from analyze_diskless import analyze, validate_timing
from publish_compact import redactor

old = authorized.old
TAG = 'product-floor-diskless-contract-20260917'
SNAPSHOT = old.ROOT/'data/raw/product_floor_reconfirm_20260916/root_authorized_20260917/permissions.json'
PINS = [str((HERE/name).relative_to(old.ROOT)) for name in ('diskless_contract.json', 'analyze_diskless.py', 'analyze_floor.py')]
PINS += ['tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py', str(SNAPSHOT.relative_to(old.ROOT))]
FILTER = '/^[0-9a-fA-F]+-|^Private_Dirty:/'


class SmapsTimeout(ValueError):
    pass


def switch_root(board, mode):
    if mode not in ('on', 'off'):
        raise ValueError('LOCAL_STOP invalid root transition')
    transport_error = None
    try:
        rc, text = board.call('root_'+mode, ['-s', board.serial, 'root', mode])
        if rc or re.search(r'failed|unable|cannot|error', text, re.I):
            raise ValueError('STOP root transition reported failure: '+mode)
    except (OSError, ValueError) as error:
        transport_error = error
    time.sleep(1)
    # Even a failed/ambiguous client response must leave actual UID evidence.
    authorized.identity_uid(board, 'id_after_root_'+mode, 0 if mode == 'on' else 5001)
    if transport_error:
        raise transport_error


def readonly_body(argv):
    if argv == ['command', '-v', 'awk'] or argv == ['command', '-v', 'vk_send']:
        pass
    elif len(argv) == 2 and argv[0] == 'cat' and (argv[1] == '/proc/self/status' or
            re.fullmatch(r'/proc/[1-9]\d*/status', argv[1])):
        pass
    elif len(argv) == 3 and argv[:2] == ['awk', FILTER] and re.fullmatch(r'/proc/[1-9]\d*/smaps', argv[2]):
        pass
    else:
        return old.readonly_body(argv)
    body = 'LC_ALL=C '+shlex.join(argv)+old.single.SUFFIX
    old.single.check_body(body)
    return body


class Board(old.Board):
    phase = 'pre'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = {}

    def call(self, label, arguments, remote=False):
        label = self.phase+'_'+label
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', label):
            raise ValueError('LOCAL_STOP unsafe label')
        if remote:
            if arguments[:3] != ['-s', self.serial, 'shell'] or len(arguments) != 4:
                raise ValueError('LOCAL_STOP remote shape')
            old.single.check_body(arguments[-1])
            body = arguments[-1]
            if not body.startswith('LC_ALL=C ') or not body.endswith(old.single.SUFFIX):
                raise ValueError('LOCAL_STOP invalid readonly framing')
            operation = shlex.split(body[len('LC_ALL=C '):-len(old.single.SUFFIX)])
            if readonly_body(operation) != body:
                raise ValueError('LOCAL_STOP noncanonical readonly request')
        elif arguments not in (['version'], ['devices'], ['connect', self.address],
                ['-s', self.serial, 'root', 'on'], ['-s', self.serial, 'root', 'off']):
            raise ValueError('LOCAL_STOP no board mutation/file transport allowed')
        path = self.output/'raw'/(label+'.txt')
        if path.exists():
            raise ValueError('LOCAL_STOP duplicate observation')
        record = dict(label=label, argv=[self.sdb, *arguments], started_utc=old.utc(),
                      started_ns=time.time_ns(), monotonic_start_ns=time.monotonic_ns())
        try:
            run = subprocess.run(record['argv'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            raw, host_rc = run.stdout, run.returncode
        except subprocess.TimeoutExpired as error:
            raw, host_rc = (error.stdout or b'')+b'\nHOST_TIMEOUT\n', 124
        except OSError as error:
            raw, host_rc = ('HOST_EXEC_ERROR '+str(error)+'\n').encode(), 127
        record.update(ended_ns=time.time_ns(), ended_utc=old.utc(),
                      monotonic_end_ns=time.monotonic_ns(), host_rc=host_rc)
        path.write_bytes(raw)
        text = raw.decode('utf-8', errors='replace').replace('\r', '')
        try:
            if host_rc == 124:
                # Only the specifically authorized full-smaps fallback is recoverable.
                if remote and re.fullmatch(r'LC_ALL=C cat /proc/[1-9]\d*/smaps', arguments[-1].removesuffix(old.single.SUFFIX)):
                    raise SmapsTimeout('full smaps timed out: '+label)
                raise ValueError('STOP transport timeout: '+label)
            rc, value = old.single.parse(text) if remote else (host_rc, text)
            if remote:
                record['remote_rc'] = rc
            if host_rc:
                raise ValueError('STOP host transport RC='+str(host_rc)+': '+label)
            return rc, value
        except ValueError as error:
            record['proof_error'] = str(error)
            raise
        finally:
            record['raw_sha256'] = hashlib.sha256(raw).hexdigest()
            with self.lock, (self.output/'commands.jsonl').open('a') as stream:
                self.records[label] = record
                stream.write(json.dumps(record)+'\n')

    def read(self, label, argv, optional=False):
        if self.stopped.is_set():
            raise ValueError('STOP prior read failed')
        body = readonly_body(argv)
        try:
            rc, value = self.call(label, ['-s', self.serial, 'shell', body], remote=True)
            if rc and not optional:
                raise ValueError('STOP required read '+label+' RC='+str(rc))
            return rc, value
        except SmapsTimeout:
            raise
        except (OSError, ValueError):
            self.stopped.set()
            raise

    def identity(self):
        if self.phase == 'pre':
            self.call('sdb_version', ['version'])
            _, text = self.call('connect', ['connect', self.address])
            if not text.strip() or re.search(r'failed|unable|cannot|error', text, re.I):
                raise ValueError('STOP connection failed; no retry')
            _, devices = self.call('devices', ['devices'])
            if not re.search(r'^'+re.escape(self.serial)+r'\s+device\b', devices, re.M):
                raise ValueError('STOP serial not online')
        _, kernel = self.read('uname_r', ['uname', '-r'])
        if 'rpi4' in kernel.lower():
            raise ValueError('STOP_TEST_BOARD: product address points at test board')
        _, arch = self.read('uname_m', ['uname', '-m'])
        if arch.strip() != 'armv7l':
            raise ValueError('STOP product architecture')
        _, release = self.read('os_release', ['cat', '/etc/os-release'])
        if not previous.product_release(release):
            raise ValueError('STOP product TV image identity')
        vk = self.read('vk_send_path', ['command', '-v', 'vk_send'], optional=True)
        return dict(kernel=kernel, arch=arch, os_release=release, vk_send=vk)


def baseline(board):
    values = {}
    for label, argv, optional in (
        ('id', ['id'], False), ('glibc', ['rpm', '-q', 'glibc'], False),
        ('libc_version', ['/lib/libc.so.6'], False), ('meminfo', ['cat', '/proc/meminfo'], False),
        ('cpu_online', ['cat', '/sys/devices/system/cpu/online'], False),
        ('clk_tck', ['getconf', 'CLK_TCK'], False), ('uptime', ['uptime'], False),
        ('date', ['date', '-u'], False), ('df', ['df', '-h'], False),
        ('proc_uptime', ['cat', '/proc/uptime'], False), ('gdb', ['rpm', '-q', 'gdb'], True),
        ('ptrace_scope', ['cat', '/proc/sys/kernel/yama/ptrace_scope'], True),
        ('shell_status', ['cat', '/proc/self/status'], False),
        ('awk_path', ['command', '-v', 'awk'], False), ('process_view', ['ps', '-ef'], False)):
        values[label] = board.read(label, argv, optional)
        old.write_json(board.output/'baseline.json', values)
    authorized.full_view_gate(values)
    if not re.search(r'^MemTotal:\s+\d+ kB$', values['meminfo'][1], re.M):
        raise ValueError('STOP missing MemTotal')
    return values


def confirm_candidates(board, snapshot, base):
    selected, changes = [], []
    for prior in snapshot['selected']:
        pid = prior['pid']
        rc, text = board.read('candidate_stat_'+str(pid), ['cat', f'/proc/{pid}/stat'], optional=True)
        if rc and not text.endswith(': No such file or directory'):
            raise ValueError('STOP unreadable candidate stat')
        current = proc_stat(text) if not rc else None
        if current is None or (current['comm'], current['start_ticks']) != (prior['comm'], prior['start_ticks']):
            _, listing = board.read('rediscover_'+str(pid), ['ps', '-ef'])
            found = []
            for other in sorted({int(m[1]) for line in listing.splitlines() if (m := re.match(r'^\S+\s+(\d+)\s+', line))}):
                rc, text = board.read(f'rediscover_{pid}_{other}', ['cat', f'/proc/{other}/stat'], optional=True)
                if rc and text.endswith(': No such file or directory'):
                    continue
                if rc:
                    raise ValueError('STOP rediscovery unreadable PID')
                candidate = proc_stat(text)
                if candidate['comm'] == prior['comm']:
                    found.append(candidate)
            if len(found) != 1:
                raise ValueError('STOP restarted candidate absent/ambiguous: '+prior['target'])
            current = found[0]
            changes.append(dict(target=prior['target'], prior_pid=pid, prior_start_ticks=prior['start_ticks'],
                                new_pid=current['pid'], new_start_ticks=current['start_ticks']))
        if current['pid'] != pid and not any(c['target'] == prior['target'] for c in changes):
            raise ValueError('STOP unexpected PID')
        pid = current['pid']
        board.read('candidate_status_'+str(pid), ['cat', f'/proc/{pid}/status'])
        current.update(target=prior['target'])
        selected.append(current)
    if len({s['pid'] for s in selected}) != len(selected):
        raise ValueError('STOP candidates collapsed onto duplicate PID')
    _, uptime = board.read('candidates_uptime', ['cat', '/proc/uptime'])
    for current in selected:
        current['elapsed_s'] = float(uptime.split()[0])-current['start_ticks']/int(base['clk_tck'][1])
        if current['elapsed_s'] < 0:
            raise ValueError('STOP invalid process start age')
    result = dict(selected=selected, changes=changes, selection='previous primary/top10 snapshot, not a new ranking')
    old.write_json(board.output/'candidates.json', result)
    return selected


def process_sample(board, candidate, index, compact):
    pid, target = candidate['pid'], candidate['target']
    label = f's{index}_p{pid}'
    _, before = board.read(label+'_before', ['cat', f'/proc/{pid}/stat'])
    before = proc_stat(before)
    mode = compact.get(pid, False)
    map_label = label+('_compact' if mode else '_smaps')
    try:
        _, text = board.read(map_label, ['awk', FILTER, f'/proc/{pid}/smaps'] if mode else ['cat', f'/proc/{pid}/smaps'])
    except SmapsTimeout:
        compact[pid] = mode = True
        map_label = label+'_compact'
        _, text = board.read(map_label, ['awk', FILTER, f'/proc/{pid}/smaps'])
    _, after = board.read(label+'_after', ['cat', f'/proc/{pid}/stat'])
    after = proc_stat(after)
    for value in (before, after):
        if (value['pid'], value['start_ticks'], value['comm']) != (pid, candidate['start_ticks'], candidate['comm']):
            raise ValueError('STOP process changed during observation: '+target)
    if any(after[k] < before[k] for k in ('minflt', 'majflt')):
        raise ValueError('STOP faults regressed during smaps')
    record = board.records['root_'+map_label]
    return dict(sample=index, epoch_ns=record['started_ns'], monotonic_ns=record['monotonic_start_ns'],
                read_end_ns=record['monotonic_end_ns'], target=target, pid=pid, start_ticks=candidate['start_ticks'],
                **smaps(text), minflt=after['minflt'], majflt=after['majflt'], compact_smaps=int(mode))


def globals_sample(board, index):
    label = f's{index}_global'
    start = time.monotonic_ns()
    values = old.globals_at(board, label)
    return dict(**values, globals_start_ns=start, globals_end_ns=time.monotonic_ns())


class Cadence:
    def __init__(self):
        self.starts, self.period, self.transition = [], 1, None

    def complete(self, started):
        self.starts.append(started)
        if self.period == 1 and len(self.starts) >= 11:
            intervals = [(b-a)/1e9 for a, b in zip(self.starts[-11:], self.starts[-10:])]
            median = statistics.median(intervals)
            if median > 1.5:
                self.period = 2
                self.transition = dict(after_sample=len(self.starts)-1, median_previous_10_intervals_s=median,
                                       from_period_s=1, to_period_s=2)
        return self.period


def observe(board, candidates):
    cadence, compact, rows, timing = Cadence(), {}, [], []
    first = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)+1) as pool:
        while True:
            if timing:
                wait = (timing[-1]['start_ns']+cadence.period*1e9-time.monotonic_ns())/1e9
                if wait > 0:
                    time.sleep(wait)
            index, begin, period = len(timing), time.monotonic_ns(), cadence.period
            work = [pool.submit(process_sample, board, c, index, compact) for c in candidates]
            global_work = pool.submit(globals_sample, board, index)
            try:
                batch = [task.result() for task in work]
                globals_now = global_work.result()
            except BaseException:
                board.stopped.set()
                for task in work+[global_work]:
                    task.cancel()
                raise
            for row in batch:
                row.update(globals_now)
                first.setdefault(row['target'], row['monotonic_ns'])
            path = board.output/'timeseries.tsv'
            with path.open('a') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(batch[0]), delimiter='\t', lineterminator='\n')
                if index == 0:
                    writer.writeheader()
                writer.writerows(batch)
            rows.extend(batch)
            cadence.complete(begin)
            timing.append(dict(sample=index, start_ns=begin, end_ns=time.monotonic_ns(), target_period_s=period))
            old.write_json(board.output/'sampling_timing.json', dict(batches=timing, transition=cadence.transition))
            if index % 10 == 0:
                print(f'PROGRESS sample={index} elapsed={(begin-timing[0]["start_ns"])/1e9:.1f}s target={cadence.period}s', flush=True)
            if all(r['monotonic_ns']-first[r['target']] >= 600e9 for r in batch):
                break
    validate_timing(rows, dict(batches=timing, transition=cadence.transition))
    old.write_json(board.output/'summary.json', analyze(rows))


def execute(board, snapshot, state):
    root_attempted = False
    try:
        state['identity_before'] = board.identity()
        state['id_before'] = authorized.identity_uid(board, 'id_before_root_on', 5001)
        root_attempted = True
        switch_root(board, 'on')
        board.phase = 'root'
        state['identity'] = board.identity()
        if any(state['identity'][k] != state['identity_before'][k] for k in ('kernel', 'arch', 'os_release')):
            raise ValueError('STOP identity changed across root transition')
        base = baseline(board)
        candidates = confirm_candidates(board, snapshot, base)
        observe(board, candidates)
        state['status'] = 'COMPLETE'
    except BaseException as error:
        state.update(status='STOP', reason=type(error).__name__+': '+str(error))
        print(state['reason'], flush=True)
    finally:
        if root_attempted:
            board.phase = 'restore'
            try:
                switch_root(board, 'off')
                state['root_off_verified_uid'] = 5001
            except BaseException as error:
                state.update(status='STOP', root_off_error=str(error))
        state['ended_utc'] = old.utc()
        old.write_json(board.output/'state.json', state)
    return 0 if state['status'] == 'COMPLETE' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ip', 'output', 'push-receipt', 'mapping', 'previous-private-snapshot'):
        parser.add_argument('--'+name, required=True, type=str if name == 'ip' else Path)
    parser.add_argument('--pm-authorized-readonly-root', action='store_true', required=True)
    args = parser.parse_args()
    clean = redactor(args.mapping, args.ip)
    if json.loads(clean(args.previous_private_snapshot.read_text())) != json.loads(SNAPSHOT.read_text()):
        raise ValueError('LOCAL_STOP previous private/public snapshot mismatch')
    snapshot = json.loads(args.previous_private_snapshot.read_text())
    gate = old.contract_gate(json.loads(args.push_receipt.read_text()), TAG, PINS)
    args.output.mkdir(parents=True, exist_ok=False)
    old.write_json(args.output/'contract_gate.json', gate)
    old.write_json(args.output/'authorization.json', json.loads((HERE/'diskless_contract.json').read_text()))
    state = dict(status='NOT_EXECUTED', mode='diskless', started_utc=old.utc(), board_alias='<PRODUCT_BOARD_IP>',
                 source_commit=old.git('rev-parse', 'HEAD').decode().strip(),
                 harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), board_files_created=0)
    rc = execute(Board(args.ip, args.output), snapshot, state)
    print('STATUS '+state['status'], flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
