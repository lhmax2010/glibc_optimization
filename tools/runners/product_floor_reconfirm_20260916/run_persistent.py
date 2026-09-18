#!/usr/bin/env python3
"""PM-authorized readonly stdin stream. No board file creation or default elevation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shlex
import subprocess
import time

import run_diskless as prior
from analyze_persistent import CONTRACT, FIELDS, Parser, analyze, covered
from publish_compact import redactor

old, HERE = prior.old, prior.HERE
TAG = CONTRACT['tag']
SNAPSHOT = old.ROOT/CONTRACT['candidates_snapshot']
PINS = [str((HERE/name).relative_to(old.ROOT)) for name in
        ('persistent_contract.json', 'analyze_persistent.py', 'analyze_floor.py')]
PINS += ['tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py', str(SNAPSHOT.relative_to(old.ROOT))]


def readonly_body(argv):
    if argv == ['ls', '-la', '/tmp']:
        body = 'LC_ALL=C '+shlex.join(argv)+old.single.SUFFIX
        old.single.check_body(body)
        return body
    return prior.readonly_body(argv)


class Board(prior.Board):
    def call(self, label, arguments, remote=False):
        label = self.phase+'_'+label
        if not re.fullmatch('[A-Za-z0-9_-]+', label):
            raise ValueError('LOCAL_STOP unsafe label')
        if remote:
            if len(arguments) != 4 or arguments[:3] != ['-s', self.serial, 'shell']:
                raise ValueError('LOCAL_STOP invalid request')
            body = arguments[-1]
            old.single.check_body(body)
            if not body.startswith('LC_ALL=C ') or not body.endswith(old.single.SUFFIX):
                raise ValueError('LOCAL_STOP missing framing')
            operation = shlex.split(body[9:-len(old.single.SUFFIX)])
            if readonly_body(operation) != body:
                raise ValueError('LOCAL_STOP noncanonical operation')
        elif arguments not in (['version'], ['devices'], ['connect', self.address], ['kill-server'], ['start-server'],
                               ['-s', self.serial, 'root', 'on'], ['-s', self.serial, 'root', 'off']):
            raise ValueError('LOCAL_STOP unapproved SDB operation')
        path = self.output/'raw'/(label+'.txt')
        if path.exists():
            raise ValueError('LOCAL_STOP duplicate observation')
        rec = dict(label=label, argv=[self.sdb,*arguments], started_utc=old.utc(),
                   started_ns=time.time_ns(), monotonic_start_ns=time.monotonic_ns())
        try:
            result = subprocess.run(rec['argv'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            raw, rc = result.stdout, result.returncode
        except subprocess.TimeoutExpired as error:
            raw, rc = (error.stdout or b'')+b'\nHOST_TIMEOUT\n', 124
        except OSError as error:
            raw, rc = ('HOST_EXEC_ERROR '+str(error)+'\n').encode(), 127
        path.write_bytes(raw)
        rec.update(ended_utc=old.utc(), ended_ns=time.time_ns(), monotonic_end_ns=time.monotonic_ns(),
                   host_rc=rc, raw_sha256=hashlib.sha256(raw).hexdigest())
        try:
            text = raw.decode(errors='replace').replace('\r','')
            remote_rc, text = old.single.parse(text) if remote else (rc,text)
            if remote:
                rec['remote_rc'] = remote_rc
            if rc:
                raise ValueError('STOP transport RC='+str(rc)+': '+label)
            return remote_rc,text
        except ValueError as error:
            rec['proof_error'] = str(error)
            raise
        finally:
            self.records[label] = rec
            with (self.output/'commands.jsonl').open('a') as stream:
                stream.write(json.dumps(rec)+'\n')

    def read(self, label, argv, optional=False):
        if self.stopped.is_set():
            raise ValueError('STOP prior read failed')
        try:
            rc, text = self.call(label, ['-s',self.serial,'shell',readonly_body(argv)], True)
            if rc and not optional:
                raise ValueError('STOP required read failed: '+label+' RC='+str(rc))
            return rc,text
        except (ValueError,OSError):
            self.stopped.set()
            raise

    def identity(self):
        _, kernel = self.read('uname_r',['uname','-r'])
        if 'rpi4' in kernel.lower():
            raise ValueError('STOP_TEST_BOARD: address currently points at RPI4')
        _, arch = self.read('uname_m',['uname','-m'])
        if arch.strip() != 'armv7l':
            raise ValueError('STOP product architecture')
        _, release = self.read('os_release',['cat','/etc/os-release'])
        if not prior.previous.product_release(release):
            raise ValueError('STOP product TV image identity')
        vk = self.read('vk_send_path',['command','-v','vk_send'],True)
        return dict(kernel=kernel,arch=arch,os_release=release,vk_send=vk)


def connectivity(board):
    board.call('sdb_version',['version'])
    for attempt in range(2):
        try:
            _, devices = board.call('devices_'+str(attempt),['devices'])
            # The short request is made even if devices lacks the serial, so
            # the one reset decision has both requested diagnostic observations.
            rc, value = board.call('selfcheck_'+str(attempt),
                                  ['-s',board.serial,'shell',readonly_body(['id'])],True)
            if rc or not re.match(r'uid=\d+\(',value) or not re.search(r'^'+re.escape(board.serial)+r'\s+device\b',devices,re.M):
                raise ValueError('STOP connectivity self-check failed')
            return
        except (ValueError,OSError):
            if attempt:
                raise
            board.call('reset_kill_server',['kill-server'])
            board.call('reset_start_server',['start-server'])
            _, value = board.call('reset_connect',['connect',board.address])
            if re.search(r'error|failed|unable|cannot',value,re.I):
                raise ValueError('STOP single reset connect failed')


def program(nonce, candidates):
    if not re.fullmatch('[a-f0-9]{32}',nonce) or not candidates:
        raise ValueError('LOCAL_STOP invalid stream identity')
    if any(type(c['pid']) is not int or not 0 < c['pid'] <= 4194304 for c in candidates):
        raise ValueError('LOCAL_STOP invalid PID')
    # Interpret directly in SDB's shell. An exec in a piped script can discard
    # bytes already buffered by the old shell. Empty HISTFILE prevents saving
    # interactive input; no script file or sourced /dev/stdin is involved.
    lines = ['HISTFILE=; export HISTFILE', 'LC_ALL=C; export LC_ALL',
             'N='+nonce,
             'stamp() { q=$(date +%s) || return; printf "%s000000000" "$q"; }',
             'item() {', 'k=$1; p=$2; shift 2',
             't=$(stamp) || return', 'printf "===READ %s %s %s %s===\\n" "$N" "$k" "$p" "$t" || return',
             '"$@"', 'r=$?', 't=$(stamp) || return',
             'if [ "$r" = 0 ]; then flag=DONE; else flag=FAIL; fi',
             'printf "\\n===RC %s %s %s %s===\\n" "$N" "$r" "$flag" "$t" || return',
             'return "$r"', '}', 'batch() {',
             'item mem 0 cat /proc/meminfo || return',
             'item zram 0 cat /sys/block/zram0/mm_stat || return',
             'item swaps 0 cat /proc/swaps || return']
    for c in candidates:
        pid=c['pid']
        lines += [f'item before {pid} cat /proc/{pid}/stat || return',
                  f"item smaps {pid} awk '{prior.FILTER}' /proc/{pid}/smaps || return",
                  f'item after {pid} cat /proc/{pid}/stat || return']
    lines += ['}', 'collect() {', 'missing=0', 'for tool in cat date sleep awk; do',
              'command -v "$tool" || missing=1', 'done', '[ "$missing" = 0 ] || return 72',
              'printf "===SESSION %s %s===\\n" "$N" "$$" || return',
              'start=$(date +%s) || return', 'i=0', 'while :; do',
              's=$(date +%s) || return', 't=$(stamp) || return',
              'printf "===SAMPLE %s %s %s===\\n" "$N" "$i" "$t" || return',
              'batch || return', 't=$(stamp) || return',
              'printf "===END %s %s %s RC=0 DONE===\\n" "$N" "$i" "$t" || return',
              'IFS= read -r ack || return 73', 'now=$(date +%s) || return',
              'case "$ack" in', 'END) [ $((now-start)) -ge 600 ] || return 74; return 0;;',
              'CONTINUE) ;;', '*) return 75;;', 'esac',
              'while [ "$now" -lt $((s+1)) ]; do', 'sleep 1 || return', 'now=$(date +%s) || return', 'done',
              'i=$((i+1))', 'done', '}', 'finish() {', 'collect', 'r=$?',
              'if [ "$r" = 0 ]; then flag=DONE; else flag=FAIL; fi',
              'printf "===FINAL %s RC=%s %s===\\n" "$N" "$r" "$flag"', 'exit "$r"', '}', 'finish']
    for line in lines:
        old.single.check_body(line)
    return '\n'.join(lines)+'\n'


def receive(argv, text, nonce, candidates, output, silence_seconds=15):
    """Only terminate the local client after EOF; never signal a board PID."""
    parser = Parser(nonce,candidates)
    (output/'stdin_program.txt').write_text(text)
    state = dict(argv=argv, nonce=nonce, started_utc=old.utc(),
                 stdin_sha256=hashlib.sha256(text.encode()).hexdigest(),
                 max_stdin_line_bytes=max(len(s.encode()) for s in text.splitlines()),
                 board_epoch_resolution_seconds=1, complete_batches=0, nominal_points=601)
    proc = subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout,selectors.EVENT_READ)
    pending = b''
    last = time.monotonic()
    try:
        proc.stdin.write(text.encode()); proc.stdin.flush()
        with (output/'stream.raw').open('wb') as raw, (output/'markers.jsonl').open('w') as markers, \
                (output/'timeseries.tsv').open('w') as series:
            writer = csv.DictWriter(series,fieldnames=FIELDS,delimiter='\t',lineterminator='\n')
            writer.writeheader();series.flush()
            while True:
                remaining = silence_seconds-(time.monotonic()-last)
                if remaining <= 0 or not selector.select(remaining):
                    raise ValueError('STOP_STREAM_SILENCE: 15 seconds without received bytes')
                chunk = os.read(proc.stdout.fileno(),65536)
                epoch, mono = time.time_ns(), time.monotonic_ns()
                if not chunk:
                    if not parser.final:
                        raise ValueError('STOP_STREAM_DISCONNECT: no complete remote FINAL')
                    break
                last = time.monotonic()
                raw.write(chunk);raw.flush();pending += chunk
                while b'\n' in pending:
                    line,pending = pending.split(b'\n',1)
                    decoded = line.decode(errors='strict').rstrip('\r')
                    rows = parser.feed(decoded,epoch,mono)
                    if re.fullmatch(r'===.*===',decoded):
                        markers.write(json.dumps(dict(line=decoded,host_epoch_ns=epoch,host_monotonic_ns=mono))+'\n');markers.flush()
                    if rows:
                        writer.writerows(rows);series.flush()
                        state['complete_batches'] = len(parser.batches)
                        old.write_json(output/'stream_state.json',state)
                        done = covered(parser.rows,candidates)
                        proc.stdin.write(b'END\n' if done else b'CONTINUE\n');proc.stdin.flush()
                        if rows[0]['sample'] % 10 == 0:
                            print('PROGRESS complete_batches='+str(len(parser.batches))+' host_elapsed_s='+
                                  str(round((mono-parser.batches[0]['host_start_ns'])/1e9,3)),flush=True)
                    if parser.final and not proc.stdin.closed:
                        proc.stdin.close()
            rc=proc.wait(timeout=5)
            state['host_rc']=rc
            if rc or not parser.final or not covered(parser.rows,candidates):
                raise ValueError('STOP stream exit/coverage proof failed')
            old.write_json(output/'summary.json',analyze(parser.rows,candidates))
            state['status']='COMPLETE'
    except BaseException as error:
        state.update(status='STOP',reason=type(error).__name__+': '+str(error))
        raise
    finally:
        if not proc.stdin.closed:
            proc.stdin.close()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()  # Local SDB client only; never a board kill command.
            proc.wait(timeout=5)
            state['host_client_terminated_after_eof']=True
        selector.close();proc.stdout.close()
        state.update(ended_utc=old.utc(),host_rc=proc.returncode,observer_pid=getattr(parser,'observer_pid',None),
                     complete_batches=len(parser.batches),final_proven=parser.final)
        raw=output/'stream.raw'
        if raw.exists():state['stream_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
        old.write_json(output/'batches.json',parser.batches)
        old.write_json(output/'stream_state.json',state)


def execute(board,snapshot,state):
    root_attempted=False
    try:
        connectivity(board)
        state['identity_before']=board.identity()
        state['id_before']=prior.authorized.identity_uid(board,'id_before_root_on',5001)
        root_attempted=True
        prior.switch_root(board,'on')
        board.phase='root'
        state['identity']=board.identity()
        if any(state['identity'][k]!=state['identity_before'][k] for k in ('kernel','arch','os_release')):
            raise ValueError('STOP identity changed across elevation')
        base=prior.baseline(board)
        candidates=prior.confirm_candidates(board,snapshot,base)
        board.read('tmp_before',['ls','-la','/tmp'])
        nonce=secrets.token_hex(16)
        text=program(nonce,candidates)
        receive([board.sdb,'-s',board.serial,'shell'],text,nonce,candidates,board.output)
        board.read('tmp_after',['ls','-la','/tmp'])
        _, processes=board.read('processes_after',['ps','-ef'])
        prior.authorized.full_view_gate({'process_view':(0,processes)})
        stream=json.loads((board.output/'stream_state.json').read_text())
        if any(re.match(r'^\S+\s+'+str(stream['observer_pid'])+r'\s+',line) for line in processes.splitlines()):
            raise ValueError('STOP observer process remains after stream exit')
        state.update(status='COMPLETE',residue='no board files created; stdin program and read-only commands audited; tmp before/after retained')
    except BaseException as error:
        state.update(status='STOP',reason=type(error).__name__+': '+str(error))
        print(state['reason'],flush=True)
    finally:
        if root_attempted:
            board.phase='restore'
            try:
                prior.switch_root(board,'off')
                state['root_off_verified_uid']=5001
            except BaseException as error:
                state.update(status='STOP',root_off_error=str(error))
        state['ended_utc']=old.utc()
        old.write_json(board.output/'state.json',state)
    return 0 if state['status']=='COMPLETE' else 2


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ip','output','push-receipt','mapping','previous-private-snapshot'):
        p.add_argument('--'+name,required=True,type=str if name=='ip' else Path)
    p.add_argument('--pm-authorized-readonly-root',required=True,action='store_true')
    args=p.parse_args()
    clean=redactor(args.mapping,args.ip)
    if json.loads(clean(args.previous_private_snapshot.read_text()))!=json.loads(SNAPSHOT.read_text()):
        raise ValueError('LOCAL_STOP private/public prior snapshot mismatch')
    gate=old.contract_gate(json.loads(args.push_receipt.read_text()),TAG,PINS)
    args.output.mkdir(parents=True,exist_ok=False)
    old.write_json(args.output/'contract_gate.json',gate)
    old.write_json(args.output/'authorization.json',CONTRACT)
    state=dict(status='NOT_EXECUTED',mode='persistent',started_utc=old.utc(),board_alias='<PRODUCT_BOARD_IP>',
               source_commit=old.git('rev-parse','HEAD').decode().strip(),
               harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),board_files_created=0)
    rc=execute(Board(args.ip,args.output),json.loads(args.previous_private_snapshot.read_text()),state)
    print('STATUS '+state['status'],flush=True)
    return rc


if __name__=='__main__':raise SystemExit(main())
