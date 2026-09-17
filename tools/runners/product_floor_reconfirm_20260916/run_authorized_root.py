#!/usr/bin/env python3
"""Single-round PM authorization; opt-in only, not the default probe entry."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_portable as portable

old = portable.old
TAG = 'product-floor-root-contract-20260917'
PINS = portable.PINS + [str((HERE/'root_authorization_contract.json').relative_to(old.ROOT))]


class Board(portable.Board):
    phase = 'pre'

    def recorded_label(self, label):
        return self.phase+'_'+label

    def call(self, label, arguments, remote=False):
        return super().call(self.recorded_label(label), arguments, remote)


def identity_uid(board, label, expected):
    # Direct bounded read also works during mandatory restoration after a STOP.
    rc, text = board.call(label, ['-s', board.serial, 'shell', old.readonly_body(['id'])], remote=True)
    match = re.search(r'^uid=(\d+)\(', text)
    if rc or not match or int(match[1]) != expected:
        raise ValueError('STOP UID proof failed: '+label+' expected='+str(expected))
    return text


def root_switch(board, mode):
    if mode not in ('on', 'off'):
        raise ValueError('invalid root transition')
    rc, text = board.call('root_'+mode, ['-s', board.serial, 'root', mode])
    # SDB's exit code is not a privilege proof; id is always required afterward.
    time.sleep(1)
    identity_uid(board, 'id_after_root_'+mode, 0 if mode == 'on' else 5001)
    if rc or re.search(r'failed|unable|cannot|error', text, re.I):
        raise ValueError('STOP root transition reported error: '+mode)


def full_view_gate(baseline):
    if not any(re.match(r'^\S+\s+1\s+', line) for line in baseline['process_view'][1].splitlines()):
        raise ValueError('STOP root process view lacks PID 1')


def execute(board, mapping, state):
    owned = []
    cleanup_attempted = False
    root_attempted = False
    completed = False
    try:
        state['identity_before'] = board.identity()
        state['id_before'] = identity_uid(board, 'id_before_root_on', 5001)
        root_attempted = True  # Even an ambiguous root-on failure requires restoration.
        root_switch(board, 'on')
        board.phase = 'root'
        state['identity'] = board.identity()
        for key in ('kernel', 'arch', 'os_release'):
            if state['identity'][key] != state['identity_before'][key]:
                raise ValueError('STOP product identity changed across root transition')
        portable.tools_gate(board)
        base = portable.baseline(board)
        full_view_gate(base)
        base['shell_status'] = board.read('shell_status', ['cat', '/proc/self/status'])
        old.write_json(board.output/'baseline.json', base)
        inventory = portable.permissions(board, old.names_from_mapping(mapping))
        if not inventory['pid1_visible']:
            raise ValueError('STOP root proc discovery lacks PID 1')
        inventory['scope'] = 'Root ps/proc include PID 1; ranking covers readable userspace only; exclusions retained, not a simultaneous census.'
        old.write_json(board.output/'permissions.json', inventory)
        old.write_json(board.output/'before_globals.json', old.globals_at(board, 'before'))
        path = portable.install(board, inventory['selected'], owned)
        print('SAMPLING_STARTED 601 slots / 600 s; authorized readonly root round', flush=True)
        # Same collector/parser, no default runner or frozen classifier modification.
        try:
            raw = portable.previous.run_script(board, 'root_sampling', path, 'collect',
                                               body=portable.script_body('run', path))
            completed = True
        finally:
            records = [json.loads(line) for line in (board.output/'commands.jsonl').read_text().splitlines()]
            last = records[-1]
            completed = (last['label'] == 'root_sampling' and last.get('host_rc') != 124
                         and 'remote_rc' in last)
        cleanup_attempted = True
        portable.cleanup(board, owned, completed)
        owned = []
        rows, timing = portable.previous.parse_samples(raw, inventory['selected'])
        fields = json.loads((HERE/'contract.json').read_text())['sampling']['fields']
        with (board.output/'timeseries.tsv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        old.write_json(board.output/'sampling_timing.json', timing)
        old.write_json(board.output/'summary.json', portable.previous.analyze(rows))
        state['status'] = 'COMPLETE'
    except BaseException as error:
        state.update(status='STOP', reason=type(error).__name__+': '+str(error))
        print(state['reason'], flush=True)
    finally:
        try:
            if not cleanup_attempted:
                portable.cleanup(board, owned, completed)
        except BaseException as error:
            state.update(status='STOP', cleanup_error=str(error))
        finally:
            if root_attempted:
                board.phase = 'restore'
                try:
                    root_switch(board, 'off')
                    state['root_off_verified_uid'] = 5001
                except BaseException as error:
                    state.update(status='STOP', root_off_error=str(error))
            else:
                state['root_transition'] = 'NOT_ATTEMPTED'
        state['ended_utc'] = old.utc()
        old.write_json(board.output/'state.json', state)
    return 0 if state['status'] == 'COMPLETE' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ip', 'output', 'push-receipt', 'mapping'):
        parser.add_argument('--'+name, required=True, type=str if name == 'ip' else Path)
    parser.add_argument('--pm-authorization-20260916', action='store_true', required=True,
                        help='One-round user authorization; not authority for future runs')
    args = parser.parse_args()
    # Pure host gates before any board action.
    old.names_from_mapping(args.mapping)
    gate = old.contract_gate(json.loads(args.push_receipt.read_text()), TAG, PINS)
    args.output.mkdir(parents=True, exist_ok=False)
    old.write_json(args.output/'contract_gate.json', gate)
    old.write_json(args.output/'authorization.json', json.loads((HERE/'root_authorization_contract.json').read_text()))
    state = dict(status='NOT_EXECUTED', started_utc=old.utc(), board_alias='<PRODUCT_BOARD_IP>',
                 source_commit=old.git('rev-parse', 'HEAD').decode().strip(),
                 harness_sha256={n: hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
                                 ('run_authorized_root.py', 'run_portable.py', 'board_probe.sh',
                                  'run_board_script.py', 'run_readonly.py')})
    rc = execute(Board(args.ip, args.output), args.mapping, state)
    print('STATUS '+state['status'], flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
