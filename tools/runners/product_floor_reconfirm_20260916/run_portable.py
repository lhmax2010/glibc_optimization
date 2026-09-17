#!/usr/bin/env python3
"""Readonly product probe with native timing and explicit partial permissions."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_board_script as previous
import run_readonly as old

TAG = 'product-floor-portable-contract-20260917'
PINS = [str((HERE/n).relative_to(old.ROOT)) for n in
        ('portable_contract.json', 'contract.json', 'analyze_floor.py')]
PINS += ['tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py']
TOOLS = 'awk sed grep cat date sleep ps id sh rm sha256sum uname rpm getconf uptime df'.split()
OPTIONAL_TOOLS = {'sha256sum', 'sed', 'grep'}  # sed/grep replaced by shell/read and host parsing.
TOOL_BODY = 'for c in '+ ' '.join(TOOLS)+';do command -v $c||echo MISSING:$c;done'+old.single.SUFFIX
COMM_BODY = 'for p in /proc/[0-9]*/comm;do n=;IFS= read -r n <"$p";printf "%s\\t%s\\n" "$p" "$n";done'+old.single.SUFFIX


def probe_body():
    old.single.check_body(TOOL_BODY)
    return TOOL_BODY


class Board(previous.Board):
    def read(self, label, argv, optional=False):
        if len(argv) == 2 and argv[0] == 'cat' and re.fullmatch(r'/proc/[1-9]\d*/status', argv[1]):
            if self.stopped.is_set():
                raise ValueError('STOP prior failure')
            rc, value = self.call(label, ['-s', self.serial, 'shell', old.single.request(argv)], remote=True)
            if rc and not optional:
                self.stopped.set()
                raise ValueError('STOP unreadable status')
            return rc, value
        return super().read(label, argv, optional)


def tools_gate(board):
    rc, output = board.call('tools', ['-s', board.serial, 'shell', probe_body()], remote=True)
    missing = re.findall(r'^MISSING:([a-z0-9]+)$', output, re.M)
    paths = [s for s in output.splitlines() if s.startswith('/')]
    found = {Path(p).name for p in paths}
    if rc or set(missing)|found != set(TOOLS) or set(missing)&found:
        raise ValueError('STOP malformed/incomplete tool probe')
    result = dict(missing=missing, paths=paths, required_missing=sorted(set(missing)-OPTIONAL_TOOLS),
                  alternatives={'sha256sum': 'full script bytes read back; SHA-256 computed and compared on host',
                                'sed': 'shell read / Python parsing', 'grep': 'shell case / Python matching'})
    old.write_json(board.output/'tools.json', result)
    board.has_sha256sum = 'sha256sum' not in missing
    if result['required_missing']:
        raise ValueError('STOP required tools missing: '+','.join(result['required_missing']))
    return result


def baseline(board):
    result = {}
    requests = [('id',['id'],False), ('glibc',['rpm','-q','glibc'],False),
                ('libc_version',['/lib/libc.so.6'],False), ('meminfo',['cat','/proc/meminfo'],False),
                ('cpu_online',['cat','/sys/devices/system/cpu/online'],False),
                ('clk_tck',['getconf','CLK_TCK'],False), ('uptime',['uptime'],False),
                ('date',['date','-u'],False), ('df',['df','-h'],False),
                ('proc_uptime',['cat','/proc/uptime'],False), ('gdb',['rpm','-q','gdb'],True),
                ('ptrace_scope',['cat','/proc/sys/kernel/yama/ptrace_scope'],True),
                ('rpm_dbpath',['rpm','--eval','%{_dbpath}'],False),
                ('tmp_writable',['test','-w','/tmp'],False), ('process_view',['ps','-ef'],False)]
    for name, command, optional in requests:
        result[name] = board.read(name, command, optional)
        old.write_json(board.output/'baseline.json', result)
    return result


def permissions(board, names):
    old.single.check_body(COMM_BODY)
    rc, text = board.call('process_names', ['-s',board.serial,'shell',COMM_BODY], remote=True)
    if rc:
        raise ValueError('STOP process discovery failed')
    discovered, diagnostics = {}, []
    for line in text.splitlines():
        match = re.fullmatch(r'/proc/([1-9]\d*)/comm\t(.*)', line)
        if match:
            if int(match[1]) in discovered:
                raise ValueError('STOP duplicate process discovery')
            discovered[int(match[1])] = match[2]
        elif line.strip():
            diagnostics.append(line)
    if not discovered:
        raise ValueError('STOP no visible process names')
    result = dict(scope='accessible-view only; not a whole-system top ten',
                  pid1_visible=1 in discovered, discovery_diagnostics=diagnostics,
                  matching={a: dict(exact_pids=[p for p,n in discovered.items() if n==name],
                                    nearby=[dict(pid=p,comm=n) for p,n in discovered.items()
                                            if n!=name and name[:8] in n]) for a,name in names.items()},
                  checks=[], records=[], selected=[], ranking=[])
    def save():
        old.write_json(board.output/'permissions.json', result)
    def inspect(pid):
        # Exactly one status and one smaps read per discovered PID in preflight.
        status_rc, status = board.read('permission_status_'+str(pid), ['cat',f'/proc/{pid}/status'], True)
        before_rc, before = board.read('permission_stat_before_'+str(pid), ['cat',f'/proc/{pid}/stat'], True)
        maps_rc, maps = board.read('permission_smaps_'+str(pid), ['cat',f'/proc/{pid}/smaps'], True)
        check = dict(pid=pid, comm=discovered[pid], status_rc=status_rc, smaps_rc=maps_rc,
                     stat_rc=before_rc, readable=False,
                     errors={k:t for k,r,t in [('status',status_rc,status),('smaps',maps_rc,maps),
                                               ('stat',before_rc,before)] if r})
        result['checks'].append(check); save()
        if status_rc or maps_rc or before_rc:
            check['reason']='unreadable or exited; see exact command errors'; save(); return
        if not status.strip() or not maps.strip():
            check['reason']='empty status/smaps; not a usable userspace observation'; save(); return
        stat = old.proc_stat(before)
        after_rc, after = board.read('permission_stat_after_'+str(pid), ['cat',f'/proc/{pid}/stat'], True)
        if after_rc:
            check['reason']='exited or stat unavailable after smaps'; save(); return
        end = old.proc_stat(after)
        if (stat['pid'],stat['start_ticks'],stat['comm']) != (end['pid'],end['start_ticks'],end['comm']) or stat['pid']!=pid or stat['comm']!=discovered[pid]:
            raise ValueError('STOP candidate identity changed during preflight')
        if stat['state']=='Z':
            check['reason']='zombie'; save(); return
        values=old.smaps(maps)
        if not re.search(r'^Pid:\s*'+str(pid)+r'\s*$', status, re.M):
            raise ValueError('STOP status identity mismatch')
        check['readable']=True
        result['records'].append(dict(stat, **values)); save()
    primary = sorted({p for m in result['matching'].values() for p in m['exact_pids']})
    for pid in primary:
        inspect(pid)
    if primary and not result['records']:
        result['decision']='ALL_NAMED_UNREADABLE_NO_PUSH'; save()
        raise ValueError('STOP_READ_PERMISSION: all living named candidates unavailable; PM read-access authorization needed, no script pushed')
    for pid in sorted(set(discovered)-set(primary)):
        inspect(pid)
    ranking=sorted(result['records'],key=lambda r:(-r['glibc_heap_pd_kb'],r['pid']))[:10]
    selected={r['pid']:dict(r,target='Supplemental%02d'%(i+1)) for i,r in enumerate(ranking)}
    for row in result['records']:
        alias=next((a for a,n in names.items() if row['comm']==n),None)
        if alias:
            selected[row['pid']]=dict(row,target=alias+'_'+str(row['pid']))
    result.update(ranking=ranking,selected=list(selected.values()),decision='READABLE_SUBSET')
    save()
    if not selected:
        raise ValueError('STOP_READ_PERMISSION: no readable candidate, no script pushed')
    return result


def script_body(command, path):
    if not previous.SCRIPT_PATH.fullmatch(path):
        raise ValueError('unsafe script path')
    argv={'run':['sh',path,'collect'], 'read':['cat',path], 'hash':['sha256sum',path],
          'absent':['test','-e',path], 'symlink':['test','-L',path], 'remove':['rm','--',path]}[command]
    body='LC_ALL=C '+shlex.join(argv)+old.single.SUFFIX
    old.single.check_body(body)
    return body


def operation(board, label, command, path):
    return board.call(label,['-s',board.serial,'shell',script_body(command,path)],remote=True)


def verify_script(board, label, item):
    path=item['path']
    if operation(board,label+'_symlink','symlink',path)[0] != 1:
        raise ValueError('STOP script symlink/type proof failed')
    if board.has_sha256sum:
        rc,value=operation(board,label,'hash',path)
        if rc or value.split()!=[item['sha256'],path]:
            raise ValueError('STOP script SHA mismatch')
    else:
        rc,_=operation(board,label,'read',path)
        raw=(board.output/'raw'/(label+'.txt')).read_bytes().replace(b'\r\n',b'\n')
        ending=b'\nRC=0\nDONE\n'
        if rc or not raw.endswith(ending):
            raise ValueError('STOP script readback framing')
        body=raw[:-len(ending)]
        if hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise ValueError('STOP script readback byte mismatch')


def install(board, selected, owned):
    script=(HERE/'board_probe.sh').read_text().replace('@TARGETS@',' '.join(
        '{target}:{pid}:{start_ticks}'.format(**r) for r in selected))
    for r in selected:
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',r['target']) or type(r['pid']) is not int or r['pid']<1 or type(r['start_ticks']) is not int or r['start_ticks']<0:
            raise ValueError('STOP unsafe generated target')
    path='/tmp/pf_20260916_'+uuid.uuid4().hex[:12]+'.sh'
    local=board.output/'sampling_script.sh'; local.write_text(script)
    item=dict(path=path,sha256=hashlib.sha256(local.read_bytes()).hexdigest(),
              integrity_method='remote-sha256' if board.has_sha256sum else 'host-sha256-of-full-byte-readback')
    for op in ('absent','symlink'):
        if operation(board,'destination_'+op,op,path)[0]!=1:
            raise ValueError('STOP destination already exists or absence unproven')
    owned.append(item); old.write_json(board.output/'owned_scripts.json',owned)
    board.call('script_push',['-s',board.serial,'push',str(local),path])
    verify_script(board,'script_identity',item)
    return path


def collect(board,path):
    # Reuse the recorder, but supply the native-shell invocation explicitly.
    try:
        return previous.run_script(board,'sampling',path,'collect',body=script_body('run',path))
    finally:
        records=[json.loads(l) for l in (board.output/'commands.jsonl').read_text().splitlines()]
        last=records[-1]
        board.script_exited=(last['label']=='sampling' and last.get('host_rc')!=124 and 'remote_rc' in last)


def cleanup(board,owned,completed):
    result=[]
    if owned and not completed:
        # Failed/incomplete stream cannot prove remote script termination.
        rc,view=board.call('cleanup_process_view',['-s',board.serial,'shell',old.readonly_body(['ps','-ef'])],remote=True)
        if rc or any(i['path'] in view for i in owned):
            raise ValueError('STOP cleanup: own probe may still run; retain script and report')
        if not any(re.match(r'^\S+\s+1\s+',l) for l in view.splitlines()):
            raise ValueError('STOP cleanup: termination not proven in restricted view')
    for i,item in enumerate(owned):
        verify_script(board,'cleanup_identity_'+str(i),item)
        if operation(board,'cleanup_remove_'+str(i),'remove',item['path'])[0]:
            raise ValueError('STOP script removal failed')
        for op in ('absent','symlink'):
            if operation(board,'cleanup_'+op+str(i),op,item['path'])[0]!=1:
                raise ValueError('STOP script still present')
        result.append(dict(item,absent=True))
    old.write_json(board.output/'cleanup.json',result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ip','output','push-receipt','mapping'):
        parser.add_argument('--'+name,required=True,type=str if name=='ip' else Path)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    state=dict(status='NOT_EXECUTED',started_utc=old.utc(),board_alias='<PRODUCT_BOARD_IP>',
               source_commit=old.git('rev-parse','HEAD').decode().strip(),
               harness_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
                               ('run_portable.py','board_probe.sh','run_board_script.py','run_readonly.py')})
    board=None; owned=[]; completed=False
    try:
        old.write_json(args.output/'contract_gate.json',old.contract_gate(json.loads(args.push_receipt.read_text()),TAG,PINS))
        board=Board(args.ip,args.output)
        state['identity']=board.identity()
        tools_gate(board); baseline(board)
        inventory=permissions(board,old.names_from_mapping(args.mapping))
        old.write_json(args.output/'before_globals.json',old.globals_at(board,'before'))
        path=install(board,inventory['selected'],owned)
        print('SAMPLING_STARTED 601 slots / 600 s; readable subset only',flush=True)
        raw=collect(board,path); completed=True
        rows,timing=previous.parse_samples(raw,inventory['selected'])
        cleanup(board,owned,completed); owned=[]
        fields=json.loads((HERE/'contract.json').read_text())['sampling']['fields']
        with (args.output/'timeseries.tsv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,delimiter='\t',lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        old.write_json(args.output/'sampling_timing.json',timing)
        old.write_json(args.output/'summary.json',previous.analyze(rows))
        state['status']='COMPLETE'
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as error:
        state.update(status='STOP',reason=str(error)); print(str(error),flush=True)
    finally:
        if board is not None and (owned or not (args.output/'cleanup.json').exists()):
            try: cleanup(board,owned,completed or getattr(board,'script_exited',False))
            except (OSError,ValueError,subprocess.SubprocessError) as error:
                state.update(status='STOP',cleanup_error=str(error))
        state['ended_utc']=old.utc(); old.write_json(args.output/'state.json',state)
    print('STATUS '+state['status'],flush=True)
    return 0 if state['status']=='COMPLETE' else 2


if __name__=='__main__':
    raise SystemExit(main())
