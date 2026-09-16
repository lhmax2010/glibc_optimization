#!/usr/bin/env python3
"""PM-authorized /tmp readonly probe; no target stimulation or elevation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_readonly as old
from analyze_floor import analyze

TAG = 'product-floor-board-script-contract-20260916'
PINS = [str((HERE/name).relative_to(old.ROOT)) for name in
        ('board_script_contract.json', 'contract.json', 'analyze_floor.py')]
PINS += ['tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py']
SCRIPT_PATH = re.compile(r'/tmp/pf_20260916_[a-f0-9]{12}\.sh')


def product_release(text):
    if re.search(r'unified-(toolchain|dev)|\b(?:development|developer|toolchain)\b', text, re.I):
        return False
    return bool(re.search(r'Tizen[^\n]*TV|TV[^\n]*Tizen', text, re.I))


def extra_body(argv):
    allowed = argv in (['command', '-v', 'vk_send'], ['command', '-v', 'rpm'],
                      ['command', '-v', 'zypper'], ['command', '-v', 'awk'],
                      ['command', '-v', 'timeout'], ['command', '-v', 'sha256sum'],
                      ['rpm', '--eval', '%{_dbpath}'], ['date', '+%s%N'],
                      ['cat', '/proc/self/status'], ['test', '-w', '/tmp'])
    if len(argv) == 3 and argv[:2] == ['test', '-w']:
        allowed |= bool(re.fullmatch(r'/(?:usr/)?(?:var/)?(?:lib|share)/rpm', argv[2]))
    if not allowed:
        return old.readonly_body(argv)
    body = 'LC_ALL=C '+shlex.join(argv)+old.single.SUFFIX
    old.single.check_body(body)
    return body


class Board(old.Board):
    def read(self, label, argv, optional=False):
        if self.stopped.is_set():
            raise ValueError('STOP prior read failed; no new observation')
        body = extra_body(argv)
        try:
            rc, text = self.call(label, ['-s', self.serial, 'shell', body], remote=True)
            if rc and not optional:
                raise ValueError('STOP remote command failed: '+label+' RC='+str(rc))
            return rc, text
        except (OSError, ValueError):
            self.stopped.set()
            raise

    def identity(self):
        self.call('sdb_version', ['version'])
        rc, text = self.call('connect', ['connect', self.address])
        if rc or not text.strip() or re.search(r'failed|unable|cannot|error', text, re.I):
            raise ValueError('STOP connection failed; no retry')
        _, devices = self.call('devices', ['devices'])
        if not re.search(r'^'+re.escape(self.serial)+r'\s+device\b', devices, re.M):
            raise ValueError('STOP requested serial is not an online device')
        _, kernel = self.read('uname_r', ['uname', '-r'])
        if 'rpi4' in kernel.lower():
            raise ValueError('STOP_TEST_BOARD: 该 IP 当前指向测试板，需 PM 确认产品板地址')
        _, arch = self.read('uname_m', ['uname', '-m'])
        if arch.strip() != 'armv7l':
            raise ValueError('STOP_PRODUCT_ARCH: expected armv7l')
        _, release = self.read('os_release', ['cat', '/etc/os-release'])
        if not product_release(release):
            raise ValueError('STOP_PRODUCT_IMAGE: Tizen10/TV product identity not established')
        vk = self.read('vk_send_path', ['command', '-v', 'vk_send'], optional=True)
        return dict(kernel=kernel, arch=arch, os_release=release, vk_send=vk)


def baseline(board):
    values = {}
    requests = (
        ('id', ['id'], False), ('glibc', ['rpm', '-q', 'glibc'], False),
        ('libc_version', ['/lib/libc.so.6'], False), ('meminfo', ['cat', '/proc/meminfo'], False),
        ('cpu_online', ['cat', '/sys/devices/system/cpu/online'], False),
        ('clk_tck', ['getconf', 'CLK_TCK'], False), ('uptime', ['uptime'], False),
        ('date', ['date', '-u'], False), ('df', ['df', '-h'], False),
        ('proc_uptime', ['cat', '/proc/uptime'], False),
        ('gdb', ['rpm', '-q', 'gdb'], True),
        ('ptrace_scope', ['cat', '/proc/sys/kernel/yama/ptrace_scope'], True),
        ('rpm_path', ['command', '-v', 'rpm'], False),
        ('zypper_path', ['command', '-v', 'zypper'], True),
        ('rpm_dbpath', ['rpm', '--eval', '%{_dbpath}'], False),
        ('shell_status', ['cat', '/proc/self/status'], False),
        ('tmp_writable', ['test', '-w', '/tmp'], False),
        ('awk_path', ['command', '-v', 'awk'], False),
        ('timeout_path', ['command', '-v', 'timeout'], False),
        ('sha256sum_path', ['command', '-v', 'sha256sum'], False),
        ('clock_ns', ['date', '+%s%N'], False),
        ('process_view', ['ps', '-ef'], False),
    )
    for label, argv, optional in requests:
        values[label] = board.read(label, argv, optional)
        old.write_json(board.output/'baseline.json', values)
        if label == 'clock_ns' and not re.fullmatch(r'\d{18,20}', values[label][1]):
            raise ValueError('STOP nanosecond date unavailable')
        if label == 'process_view' and not any(re.match(r'^\S+\s+1\s+', s) for s in values[label][1].splitlines()):
            raise ValueError('STOP incomplete process view: PID 1 missing; PM read-access authorization needed')
    dbpath = values['rpm_dbpath'][1].strip()
    if re.fullmatch(r'/(?:usr/)?(?:var/)?(?:lib|share)/rpm', dbpath):
        values['rpm_db_writable'] = board.read('rpm_db_writable', ['test', '-w', dbpath], True)
    else:
        values['rpm_db_writable'] = ['NOT_EVALUATED', 'unrecognized database path; no guessed permissions']
    old.write_json(board.output/'baseline.json', values)
    old.globals_at(board, 'before')
    return values


def script_body(command, path, mode=None):
    if not SCRIPT_PATH.fullmatch(path):
        raise ValueError('unsafe script path')
    if command == 'run':
        if mode not in ('inventory', 'collect'):
            raise ValueError('invalid script mode')
        argv = ['timeout', '625' if mode == 'collect' else '90', 'sh', path, mode]
    elif command in ('hash', 'absent', 'symlink', 'remove'):
        argv = {'hash': ['sha256sum', path], 'absent': ['test', '-e', path],
                'symlink': ['test', '-L', path], 'remove': ['rm', '--', path]}[command]
    else:
        raise ValueError('invalid script operation')
    body = 'LC_ALL=C '+shlex.join(argv)+old.single.SUFFIX
    old.single.check_body(body)
    return body


def operation(board, label, command, path, mode=None):
    body = script_body(command, path, mode)
    return board.call(label, ['-s', board.serial, 'shell', body], remote=True)


def require_hash(board, label, path, expected):
    linkrc, _ = operation(board, label+'_no_symlink', 'symlink', path)
    if linkrc != 1:
        raise ValueError('STOP script became symlink or type cannot be established')
    rc, value = operation(board, label, 'hash', path)
    if rc or value.split() != [expected, path]:
        raise ValueError('STOP script hash mismatch: '+label)


def install_script(board, label, targets, owned):
    path = '/tmp/pf_20260916_'+uuid.uuid4().hex[:12]+'.sh'
    script = (HERE/'board_probe.sh').read_text().replace('@TARGETS@', ' '.join(
        '{target}:{pid}:{start_ticks}'.format(**row) for row in targets))
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', row['target']) or
           not isinstance(row['pid'], int) or row['pid'] < 1 or
           not isinstance(row['start_ticks'], int) or row['start_ticks'] < 0 for row in targets):
        raise ValueError('invalid generated target')
    local = board.output/(label+'.sh')
    local.write_text(script)
    digest = hashlib.sha256(local.read_bytes()).hexdigest()
    for kind in ('absent', 'symlink'):
        rc, _ = operation(board, label+'_'+kind, kind, path)
        if rc != 1:
            raise ValueError('STOP script destination exists or cannot establish absence')
    owned.append(dict(path=path, sha256=digest, local=local.name))
    old.write_json(board.output/'owned_scripts.json', owned)
    board.call(label+'_push', ['-s', board.serial, 'push', str(local), path])
    require_hash(board, label+'_hash', path, digest)
    return path


def run_script(board, label, path, mode):
    body = script_body('run', path, mode)
    argv = [board.sdb, '-s', board.serial, 'shell', body]
    target = board.output/'raw'/(label+'.txt')
    if target.exists():
        raise ValueError('refusing repeat script execution')
    started = old.utc()
    with target.open('wb') as stream:
        try:
            proc = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                  timeout=650 if mode == 'collect' else 110)
            host_rc = proc.returncode
        except subprocess.TimeoutExpired:
            host_rc = 124
    raw = target.read_bytes()
    record = dict(label=label, argv=argv, started_utc=started, ended_utc=old.utc(),
                  host_rc=host_rc, raw_sha256=hashlib.sha256(raw).hexdigest())
    try:
        rc, value = old.single.parse(raw.decode(errors='replace'))
        record['remote_rc'] = rc
    except ValueError as error:
        record['proof_error'] = str(error)
        raise
    finally:
        with (board.output/'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(record)+'\n')
    if host_rc == 124 or rc:
        raise ValueError('STOP script failed: '+label+' remote_RC='+str(rc))
    return value


def select_inventory(text, names):
    records, excluded = [], []
    for line in text.splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[0] == 'X':
            excluded.append(dict(pid=int(parts[1]), reason=parts[2])); continue
        if len(parts) != 10 or parts[0] != 'I':
            raise ValueError('STOP malformed inventory row')
        row = dict(pid=int(parts[1]), comm=parts[2])
        row.update(zip(('start_ticks', 'glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb',
                        'total_pd_kb', 'minflt', 'majflt'), map(int, parts[3:])))
        if row['total_pd_kb'] != sum(row[k] for k in ('glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb')):
            raise ValueError('STOP inventory PD mismatch')
        records.append(row)
    if not any(row['pid'] == 1 for row in records) or len({r['pid'] for r in records}) != len(records):
        raise ValueError('STOP incomplete/duplicate userspace inventory')
    ranking = sorted(records, key=lambda row: (-row['glibc_heap_pd_kb'], row['pid']))[:10]
    selected = {r['pid']: dict(r, target='Supplemental%02d' % (i+1)) for i, r in enumerate(ranking)}
    matching = {}
    for alias, name in names.items():
        found = [r for r in records if r['comm'] == name]
        matching[alias] = {'exact_pids': [r['pid'] for r in found],
                           'nearby': [r for r in records if name[:8] in r['comm'] and r not in found]}
        for r in found:
            selected[r['pid']] = dict(r, target=alias+'_'+str(r['pid']))
    return {'records': records, 'excluded': excluded, 'ranking': ranking,
            'matching': matching, 'selected': list(selected.values())}


def parse_samples(text, candidates):
    procs, globals_, timing = {}, {}, {}
    expected = {c['target']: (c['pid'], c['start_ticks']) for c in candidates}
    complete = 0
    for line in text.splitlines():
        if line == 'SAMPLING_DONE':
            complete += 1; continue
        p = line.split('\t')
        if p[0] == 'P' and len(p) == 12:
            i, epoch = int(p[1]), int(p[2]); target = p[3]
            if target not in expected or (i, target) in procs:
                raise ValueError('duplicate/unknown target')
            row = dict(sample=i, epoch_ns=epoch, target=target)
            row.update(zip(('pid', 'start_ticks', 'glibc_heap_pd_kb', 'other_anon_pd_kb',
                            'file_backed_pd_kb', 'total_pd_kb', 'minflt', 'majflt'), map(int, p[4:])))
            if (row['pid'], row['start_ticks']) != expected[target]:
                raise ValueError('target identity differs')
            procs[i, target] = row
        elif p[0] == 'G' and len(p) == 8:
            i = int(p[1])
            if i in globals_:
                raise ValueError('duplicate global row')
            globals_[i] = (int(p[2]), dict(zip(('MemAvailable_kb', 'zram_used_kb', 'zram_orig_bytes',
                             'zram_compr_bytes', 'zram_mem_used_bytes'), map(int, p[3:]))))
        elif p[0] == 'T' and len(p) == 5:
            i, begin, end, deadline = map(int, p[1:])
            if i in timing or not deadline <= begin <= end < deadline+1000000000:
                raise ValueError('timing/deadline violated')
            timing[i] = dict(sample=i, begin_mono_ns=begin, end_mono_ns=end, deadline_mono_ns=deadline)
        else:
            raise ValueError('unexpected sample output')
    if complete != 1 or set(timing) != set(range(601)) or set(globals_) != set(range(601)) or len(procs) != 601*len(expected):
        raise ValueError('incomplete ten-minute collection')
    rows = []
    for i in range(601):
        if timing[i]['deadline_mono_ns'] != timing[0]['deadline_mono_ns']+i*1000000000:
            raise ValueError('nonuniform deadlines')
        for target in expected:
            row = procs[i, target]
            if row['epoch_ns'] != globals_[i][0]:
                raise ValueError('mismatched global slot')
            rows.append(dict(row, **globals_[i][1]))
    analyze(rows)  # frozen semantic checks; no partial dataset can pass
    return rows, list(timing.values())


def cleanup(board, owned):
    results = []
    if owned:
        # This read is cleanup-only, even after a failed observation gate.
        body = old.readonly_body(['ps', '-ef'])
        rc, listing = board.call('cleanup_process_view', ['-s', board.serial, 'shell', body], remote=True)
        if rc or not any(re.match(r'^\S+\s+1\s+', line) for line in listing.splitlines()):
            raise ValueError('cleanup process visibility unproven')
        if any(item['path'] in listing for item in owned):
            raise ValueError('own probe may still be running; do not delete active script')
    for i, item in enumerate(owned):
        rc, _ = operation(board, 'cleanup_exists_'+str(i), 'absent', item['path'])
        if rc == 1:
            results.append(dict(path=item['path'], absent=True)); continue
        if rc:
            raise ValueError('cleanup existence not established')
        require_hash(board, 'cleanup_hash_'+str(i), item['path'], item['sha256'])
        rc, _ = operation(board, 'cleanup_remove_'+str(i), 'remove', item['path'])
        if rc:
            raise ValueError('cleanup removal failed')
        rc, _ = operation(board, 'cleanup_absent_'+str(i), 'absent', item['path'])
        linkrc, _ = operation(board, 'cleanup_no_symlink_'+str(i), 'symlink', item['path'])
        if rc != 1 or linkrc != 1:
            raise ValueError('cleanup absence not proved')
        results.append(dict(path=item['path'], sha256=item['sha256'], absent=True))
    old.write_json(board.output/'cleanup.json', results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--push-receipt', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    state = dict(started_utc=old.utc(), status='NOT_EXECUTED', board_alias='<PRODUCT_BOARD_IP>',
                 source_commit=old.git('rev-parse', 'HEAD').decode().strip(),
                 harness_sha256={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                 for name in ('run_board_script.py', 'board_probe.sh', 'run_readonly.py')})
    owned, board = [], None
    try:
        receipt = json.loads(args.push_receipt.read_text())
        old.write_json(args.output/'contract_gate.json', old.contract_gate(receipt, TAG, PINS))
        names = old.names_from_mapping(args.mapping)
        board = Board(args.ip, args.output)
        state['identity'] = board.identity()
        values = baseline(board)
        path = install_script(board, 'inventory_script', [], owned)
        inventory = select_inventory(run_script(board, 'inventory', path, 'inventory'), names)
        old.write_json(args.output/'inventory.json', inventory)
        path = install_script(board, 'sampling_script', inventory['selected'], owned)
        print('SAMPLING_STARTED 601 slots / 600 s; no target stimulation', flush=True)
        raw = run_script(board, 'sampling', path, 'collect')
        rows, timing = parse_samples(raw, inventory['selected'])
        fields = json.loads((HERE/'contract.json').read_text())['sampling']['fields']
        with (args.output/'timeseries.tsv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        old.write_json(args.output/'sampling_timing.json', timing)
        old.write_json(args.output/'summary.json', analyze(rows))
        state['status'] = 'COMPLETE'
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        state.update(status='STOP', reason=str(error))
        print(str(error), flush=True)
    finally:
        if board is not None:
            try:
                cleanup(board, owned)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                state.update(status='STOP', cleanup_error=str(error))
        state['ended_utc'] = old.utc()
        old.write_json(args.output/'state.json', state)
    print('STATUS '+state['status'], flush=True)
    return 0 if state['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
