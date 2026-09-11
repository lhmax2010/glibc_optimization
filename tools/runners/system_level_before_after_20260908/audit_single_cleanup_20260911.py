#!/usr/bin/env python3
"""Only delayed cleanup. One operation/request; no measurement or package change.

Finish the non-root sweep before making an immutable permission-denied list.
The optional single root round may read only that list (or named descendants
of an unreadable listed directory). Each such read still uses <=200 bytes.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import re
import shlex
import subprocess

from preflight import Gate, ROOT, git, utc
from audit_cleanup_20260911 import SOURCE, original_body, health_delta
from execute_contract import CONTRACT, ANALYSIS, GDB_NAMES, WORK, STABILITY
from single_request import request, check_body, parse, permission, absent, absent_listing

TOKEN = 'PM-SINGLE-CLEANUP-20260910'
PS = ['ps', '-ww', '-eo', 'pid,ppid,tty,comm,args']
STAT_FORMAT = '%F|%s|%Y|%u:%g'
CRASH = '/opt/usr/share/crash/livedump'
BOOT = '/proc/sys/kernel/random/boot_id'


def file_path(path):
    if not re.fullmatch(r'/[A-Za-z0-9_+./@-]+', path) or '..' in path.split('/') or path == '/':
        raise ValueError('unsafe/unsupported path: ' + path)
    return path


def stat_op(path):
    return ['stat', '-c', STAT_FORMAT, '--', file_path(path)]


def verify_contract_sources(root):
    """Host identity is commit + SHA + exact bytes, never a named Git ref.

    The independent board preflight still requires its annotated tag and push
    receipt/600-second interval. This reader neither fetches nor changes Git.
    """
    relative = 'tools/runners/system_level_before_after_20260908/'
    refs_path = root / relative / 'contract_refs.json'
    if refs_path.is_symlink():
        raise ValueError('contract refs must not be a symlink')
    refs = json.loads(refs_path.read_text())
    if not isinstance(refs, dict) or refs.get('schema') != 'system-before-after.contract-refs.v1':
        raise ValueError('unsupported contract refs schema')
    commit = refs.get('contract_commit')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('contract commit must be a full 40-character SHA, not a tag name')
    hashes = refs.get('files_sha256')
    paths = {relative + name for name in ('contract.json', 'analyze_system_level.py')}
    if not isinstance(hashes, dict) or set(hashes) != paths or any(
            not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
            for value in hashes.values()):
        raise ValueError('contract refs require exactly two valid file SHA-256 values')
    kind = subprocess.run(['git', 'cat-file', '-t', commit], cwd=root, capture_output=True)
    if kind.returncode:
        raise ValueError('contract-source-unavailable: commit ' + commit +
            '; no PASS/SKIP. In a shallow clone run git fetch --no-tags --unshallow origin '
            '(or git fetch --no-tags --deepen <depth> origin). To fetch only the pinned object: '
            'git fetch --no-tags origin ' + commit + '; then rerun host replay.')
    if kind.stdout.strip() != b'commit':
        raise ValueError('contract_commit must identify a commit object, not an annotated tag object')
    for path in sorted(paths):
        frozen = subprocess.run(['git', 'show', commit + ':' + path], cwd=root, capture_output=True)
        if frozen.returncode:
            raise ValueError('contract-file-unavailable: ' + commit + ':' + path +
                             '; restore the pinned Git object before replay; no PASS/SKIP')
        if hashlib.sha256(frozen.stdout).hexdigest() != hashes[path]:
            raise ValueError('contract committed file hash mismatch: ' + path)
        local = root / path
        if local.is_symlink() or local.read_bytes() != frozen.stdout:
            raise ValueError('contract/analyzer bytes changed: ' + path)
    return refs


def sources():
    verify_contract_sources(ROOT)
    for item in json.loads((SOURCE / 'manifest.json').read_text())['files']:
        p = SOURCE / item['path']
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != item['public_sha256']:
            raise ValueError('immutable source mismatch: ' + item['path'])
    prior = json.loads((SOURCE / 'execution.json').read_text())
    if prior['completed_cells'] != ['G4_trim_r1', 'G4_trim_r2', 'G4_trim_r3']:
        raise ValueError('three accepted G4 required')
    paths = sorted(set(original_body('GDB_INSTALLED_PATHS', (SOURCE / 'GDB_INSTALLED_PATHS.txt').read_text()).splitlines()))
    inventory = sorted(original_body('PACKAGE_INVENTORY_BEFORE', (SOURCE / 'PACKAGE_INVENTORY_BEFORE.txt').read_text()).splitlines())
    if not paths or not inventory:
        raise ValueError('empty original package sources')
    # Each path is independent. Prevalidate every possible known-path operation
    # locally; never dispatch an exploratory request to learn a length limit.
    for path in paths + [WORK, '/opt/usr/glibc_memopt', CRASH]:
        for op in (stat_op(path), ['rpm', '-qf', '--', path], ['sha256sum', '--', path]):
            request(op)
    return prior, paths, inventory


def process_check(text):
    if not re.search(r'\bPID\s+PPID\s+TT\s+COMMAND', text):
        raise ValueError('incomplete process table header')
    rows = {}
    for line in text.splitlines()[1:]:
        fields = line.split(None, 4)
        if len(fields) != 5 or not fields[0].isdigit() or not fields[1].isdigit():
            raise ValueError('malformed process table row')
        rows[int(fields[0])] = (int(fields[1]), *fields[2:])
    if 1 not in rows:
        raise ValueError('process table missing PID 1')
    collectors = [pid for pid, row in rows.items() if row[2] == 'ps' and row[3] == shlex.join(PS)]
    if len(collectors) != 1:
        raise ValueError('ambiguous collector process')
    own = {collectors[0]}
    parent = rows[collectors[0]][0]
    while parent in rows and rows[parent][2] in ('sh', 'bash'):
        # Exclude only our exact command ancestors, never arbitrary PTY shells.
        if not rows[parent][3].endswith(' -c ' + request(PS)):
            break
        own.add(parent)
        parent = rows[parent][0]
    for pid, (_, tty, comm, args) in rows.items():
        if pid in own:
            continue
        if tty.startswith('pts/'):
            raise ValueError('foreign interactive session PID %d; not cleared' % pid)
        if re.search(r'alloc_bench|gst_loop_decode|gst-launch|^gdb$|sample_smaps|run_cell_remote', comm):
            raise ValueError('remaining/foreign load PID %d; not terminated' % pid)
        if re.search(r'(?:sample_smaps[^ ]*\.sh|run_cell_remote\.sh|/sampler\.py)', args):
            raise ValueError('remaining sampler/controller PID %d' % pid)


class SingleAudit(Gate):
    authorization_token = TOKEN

    def inspect_processes(self, label, text):
        process_check(text)

    def inspect_connections(self, connections):
        if len(connections) > 1:
            raise ValueError('multiple SDB clients; no clearing')

    def allow_signal(self, argv):
        return False

    def allow_scoped_root(self, scope, argv):
        if not scope or scope not in self.pending:
            return False
        directory = self.pending[scope]['directory']
        if not directory or argv[-1] != directory + '/' + pathlib.PurePosixPath(argv[-1]).name:
            return False
        return argv[0] in ('stat','sha256sum','base64') or (
            argv == ['rm','--',argv[-1]] and argv[-1] in self.authorized_removals)

    def __init__(self, args):
        args.output_dir.mkdir(parents=True, exist_ok=False)
        super().__init__(args.ip, args.output_dir)
        self.args = args
        self.phase = 'NONROOT'
        self.pending = {}
        self.results = {}
        self.authorized_removals = set()
        self.raised = False
        self.receipt = dict(schema='system-before-after.single-cleanup.v1', start_utc=utc(),
            verdict='STOP', body_limit_bytes=200, approved_by='PM', pm_decision_date='2026-09-10',
            measurement_cells_run=0, board_files_pushed=0, packages_changed=0, governor_writes=0,
            processes_terminated=0, root_elevation='NOT_NEEDED', accepted_measurements='21 PRESERVED')

    def save(self):
        (self.out / 'audit.json').write_text(json.dumps(self.receipt, indent=2) + '\n')

    def run(self, label, argv, timeout=20):
        if pathlib.Path(argv[0]).name != 'sdb':
            raise ValueError('audit transport only accepts sdb')
        if 'shell' in argv:
            i = argv.index('shell')
            if len(argv) != i + 2:
                raise ValueError('one complete request body required')
            check_body(argv[-1])  # final dispatch boundary, independent of caller
        elif argv[-2:] not in (['root', 'on'], ['root', 'off']) and not (
                argv == ['sdb', 'version'] or argv == ['sdb', 'connect', self.addr]):
            raise ValueError('no push/pull/install/other transport in audit')
        if len(self.commands) % 100 == 0 or 'ROOT_' in label or label.startswith('ID_'):
            print('COMMAND', len(self.commands), label, utc(), flush=True)
        return super().run(label, argv, timeout)

    def op(self, label, argv, defer=True, scope=None):
        body = request(argv)
        if argv[0] == 'kill' and not self.allow_signal(argv):
            raise ValueError('signal requires archived exact process attribution')
        if argv[0] in ('rm','rmdir') and (argv != ['rm','--',argv[-1]] or
                argv[-1] not in self.authorized_removals or 'nonroot_sweep_completed_utc' not in self.receipt):
            raise ValueError('removal requires exact archived attribution after nonroot sweep')
        identity_label = label in ('ID_ROOT','ID_OFF_1','ID_OFF_2')
        if self.phase == 'ROOT' and identity_label and argv != ['id']:
            raise ValueError('root identity exception permits id only')
        if self.phase == 'ROOT' and not identity_label:
            registered = self.pending.get(label)
            if registered is None or registered['argv'] != argv:
                if not self.allow_scoped_root(scope, argv):
                    raise ValueError('root read outside pre-recorded denied list; root directory scope permits metadata/archive reads only')
        _, text = self.run(self.phase + '_' + label, ['sdb', '-s', self.serial, 'shell', body])
        rc, payload = parse(text)
        if self.phase == 'NONROOT' and defer and permission(rc, payload):
            if label in self.pending:
                raise ValueError('duplicate permission item')
            self.pending[label] = dict(argv=argv, reason=payload, directory=argv[-1] if argv[0] == 'ls' else None)
            self.receipt['permission_denied_items'] = self.pending
            self.save()
            return None
        result = (rc, payload)
        self.results[label] = result
        return result

    def ok(self, label, argv, defer=True):
        result = self.op(label, argv, defer)
        if result is not None and result[0] != 0:
            raise ValueError('read failed: ' + label + ': ' + result[1])
        return None if result is None else result[1]

    def identity(self):
        self.receipt['id_before'] = self.ok('ID_BEFORE', ['id'], False)
        if not self.receipt['id_before'].startswith('uid=5001('):
            raise ValueError('expected initial UID=5001')
        if 'rpi4' not in self.ok('UNAME_R', ['uname', '-r'], False):
            raise ValueError('kernel identity mismatch')
        if self.ok('UNAME_M', ['uname', '-m'], False) != 'armv7l':
            raise ValueError('architecture identity mismatch')
        release = self.ok('OS_RELEASE', ['cat', '/etc/os-release'], False)
        if 'BUILD_ID=' + CONTRACT['identity']['build_id'] not in release.splitlines():
            raise ValueError('BUILD_ID mismatch')
        if self.ok('GLIBC', ['rpm', '-q', 'glibc'], False) != CONTRACT['identity']['glibc']:
            raise ValueError('glibc drift')
        memory = self.ok('MEMINFO', ['cat', '/proc/meminfo'], False)
        match = re.search(r'^MemTotal:\s+(\d+) kB$', memory, re.M)
        if not match or not 8036234 <= int(match[1]) <= 8198582:
            raise ValueError('MemTotal drift')

    def snapshot(self, when):
        self.ok('BOOT_' + when, ['cat', BOOT])
        self.ok('PS_' + when, PS)
        self.ok('DMESG_' + when, ['dmesg'])
        self.ok('ZRAM_' + when, ['cat', '/sys/block/zram0/mm_stat'])
        result = self.op('ALERTS_' + when, ['ls', '-A', '--', CRASH])
        if result is not None and result[0] != 0 and not absent_listing(*result):
            raise ValueError('livedump enumeration failed')
        if result is not None and result[0] == 0 and result[1]:
            self.archive_alerts('ALERTS_' + when, result[1].splitlines())

    def check_stat(self, label, path):
        result = self.op(label, stat_op(path))
        if result is not None and not absent(*result) and result[0] != 0:
            raise ValueError('stat failed, not absence: ' + path)
        # If stat is inaccessible, independently try the owner query as nonroot
        # too, so a necessary root query is explicitly registered BEFORE root-on.
        if result is None or result[0] == 0:
            self.op(label + '_OWNER', ['rpm', '-qf', '--', path])

    def nonroot(self, prior, paths):
        self.snapshot('START')
        if 'PS_START' in self.results and self.results['PS_START'][0] == 0:
            self.inspect_processes('PS_START', self.results['PS_START'][1])
        self.ok('TARGET_STAT', ['cat', '/proc/%d/stat' % prior['preflight']['enlightenment_pid']])
        for n in range(4):
            self.ok('GOV_%d' % n, ['cat', '/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor' % n])
        self.ok('DF_ROOT', ['df', '-k', '/'])
        self.ok('DF_OPTUSR', ['df', '-k', '/opt/usr'])
        self.ok('DATE', ['date', '-u'])
        self.ok('UPTIME', ['uptime'])
        self.ok('SWAPS', ['cat', '/proc/swaps'])
        self.ok('TCP4', ['cat', '/proc/net/tcp'])
        self.ok('TCP6', ['cat', '/proc/net/tcp6'])
        self.ok('PACKAGES', ['rpm', '-qa', '--queryformat', '%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\\n'])
        for name in GDB_NAMES:
            self.op('ABSENT_' + name, ['rpm', '-q', name])
        for label, path in [('WORK_PARENT', '/opt/usr/glibc_memopt'), ('WORK', WORK)]:
            self.check_stat(label, path)
        for label, path in [('TOP_TMP', '/tmp'), ('TOP_HOME', '/home'), ('TOP_OPTUSR', '/opt/usr')]:
            listing = self.ok(label, ['ls', '-A', '--', path])
            if listing is not None:
                self.top_entries(label, path, listing)
        for i, path in enumerate(paths):
            self.check_stat('PATH_%04d' % i, path)
        self.snapshot('END')

    def top_entries(self, label, directory, listing):
        # Only named project candidates, not arbitrary system/user content.
        # Anything unrecognized remains an observation, never a deletion target.
        for i, name in enumerate(listing.splitlines()):
            if re.search(r'alloc_bench|gst_loop_decode|reclaim_probe|glibc_memopt|small_320x240|sample_smaps|run_cell_remote', name):
                path = file_path(directory + '/' + name)
                self.op(label + '_SUSPECT_%04d'%i, stat_op(path), scope=label)
                self.receipt.setdefault('top_level_suspects', []).append(dict(path=path, verdict='UNATTRIBUTED_NOT_REMOVED'))
        self.save()

    def pre_root_check(self, prior, inventory):
        """Already-readable hard failures cannot authorize an unnecessary root."""
        def available(label):
            result = self.results.get(label)
            return result[1] if result is not None and result[0] == 0 else None
        for when in ('START','END'):
            value = available('BOOT_'+when)
            if value is not None and value != prior['preflight']['boot_id']:
                raise ValueError('boot changed since accepted G4')
            value = available('PS_'+when)
            if value is not None:
                self.inspect_processes('PS_'+when, value)
            dm, zr = available('DMESG_'+when), available('ZRAM_'+when)
            old_dm=(SOURCE/'raw/round_health/dmesg_before.txt').read_text()
            old_zr=(SOURCE/'raw/round_health/zram_before.txt').read_text()
            # Independent known failures, not a PASS for a still-denied peer.
            if dm is not None:
                health_delta(old_dm, dm, old_zr, old_zr)
            if zr is not None:
                health_delta(old_dm, old_dm, old_zr, zr)
        target = available('TARGET_STAT')
        if target is not None:
            identity = ANALYSIS.proc_stat(target)
            if identity['pid'] != prior['preflight']['enlightenment_pid'] or identity['starttime'] != prior['target_starttime']:
                raise ValueError('target restarted')
        for n in range(4):
            value=available('GOV_%d'%n)
            if value is not None and value != 'schedutil':
                raise ValueError('governor not restored')
        value=available('PACKAGES')
        if value is not None and sorted(value.splitlines()) != inventory:
            raise ValueError('package inventory changed')
        for name in GDB_NAMES:
            label='ABSENT_'+name
            if label in self.results and self.results[label] != (1,'package %s is not installed'%name):
                raise ValueError('package absence not proven: '+name)
        for label in ('WORK','WORK_PARENT'):
            if label in self.results and not absent(*self.results[label]):
                raise ValueError('work residue; metadata archived, ownership disposition required')
        if self.receipt.get('top_level_suspects'):
            raise ValueError('top-level project candidate needs attribution; metadata archived, not deleted')
        connections=[]
        for label in ('TCP4','TCP6'):
            value=available(label)
            if value is not None:
                for line in value.splitlines():
                    f=line.split()
                    if len(f)>3 and f[1].upper().endswith(':65F5') and f[3]=='01':
                        connections.append(line)
        self.inspect_connections(connections)
        for label,result in self.results.items():
            if label.endswith('_OWNER') and result[0] != 0:
                if result[0] != 1 or not (result[1].startswith('file ') and
                        result[1].endswith(' is not owned by any package')):
                    raise ValueError('package owner query failed: '+label)
        for when in ('START','END'):
            label='ALERTS_'+when
            listing=available(label)
            if listing and all(label+'_%04d_'%i+suffix in self.results
                    for i,_ in enumerate(listing.splitlines()) for suffix in ('STAT','SHA','B64')):
                self.classify_alerts(label,listing.splitlines(),prior)

    def elevate_denied(self):
        # Immutable audit trail before changing privilege. No root scan of items
        # that were readable as owner, and no implicit/default root authorization.
        self.receipt.setdefault('nonroot_sweep_completed_utc', utc())
        (self.out / 'permission_denied.json').write_text(json.dumps(self.pending, indent=2) + '\n')
        if not self.pending:
            self.receipt['id_final'] = self.ok('ID_FINAL', ['id'], False)
            return
        if self.args.pm_authorization != self.authorization_token:
            raise ValueError('permission list requires explicit PM-A authorization')
        self.receipt['root_elevation'] = 'DENIED_LIST_ONLY'
        self.receipt['root_authorization'] = dict(approved_by='PM', decision_date='2026-09-10',
            scope='single round; pre-recorded unreadable/incomplete cleanup items only',
            id_before=self.ok('ID_BEFORE_ROOT', ['id'], False), root_off='NOT-EVALUATED')
        if not self.receipt['root_authorization']['id_before'].startswith('uid=5001('):
            raise ValueError('session changed before root round')
        self.save()
        self.raised = True
        self.run('ROOT_ON', ['sdb', '-s', self.serial, 'root', 'on'])
        self.phase = 'ROOT'
        self.receipt['root_authorization']['id_after_on'] = self.ok('ID_ROOT', ['id'], False)
        if not self.receipt['root_authorization']['id_after_on'].startswith('uid=0('):
            raise ValueError('root not established')
        for label, item in self.pending.items():
            self.op(label, item['argv'], False)
            if item['directory'] and self.results[label][0] == 0:
                if item['directory'] == CRASH:
                    self.archive_alerts(label, self.results[label][1].splitlines())
                else:
                    self.top_entries(label, item['directory'], self.results[label][1])

    def validate(self, prior, paths, inventory):
        if self.receipt.get('top_level_suspects'):
            raise ValueError('top-level project candidate needs attribution; metadata archived, not deleted')
        def get(label):
            if label not in self.results:
                raise ValueError('unresolved unreadable item: ' + label)
            return self.results[label]
        def good(label):
            code, text = get(label)
            if code:
                raise ValueError('failed item: ' + label + ': ' + text)
            return text
        for label in self.pending:
            code, text = get(label)
            if permission(code, text):
                raise ValueError('still unreadable as root: ' + label)
        old_dmesg = (SOURCE / 'raw/round_health/dmesg_before.txt').read_text()
        old_zram = (SOURCE / 'raw/round_health/zram_before.txt').read_text()
        for when in ('START', 'END'):
            if good('BOOT_' + when) != prior['preflight']['boot_id']:
                raise ValueError('boot changed since accepted G4')
            self.inspect_processes('PS_' + when, good('PS_' + when))
            increment = health_delta(old_dmesg, good('DMESG_' + when), old_zram, good('ZRAM_' + when))
            (self.out / ('dmesg_increment_' + when + '.txt')).write_text('\n'.join(increment) + '\n')
            code, listing = get('ALERTS_' + when)
            if code != 0 and not absent_listing(code, listing):
                raise ValueError('alert enumeration failed')
            names = listing.splitlines() if code == 0 else []
            self.receipt['stability_' + when] = dict(count=len(names), entries=names)
            if names:
                self.classify_alerts('ALERTS_'+when, names, prior)
        target = ANALYSIS.proc_stat(good('TARGET_STAT'))
        if target['pid'] != prior['preflight']['enlightenment_pid'] or target['starttime'] != prior['target_starttime']:
            raise ValueError('target restarted')
        for n in range(4):
            if good('GOV_%d' % n) != 'schedutil':
                raise ValueError('governor not restored')
        actual = sorted(good('PACKAGES').splitlines())
        self.receipt['package_inventory'] = dict(before_count=len(inventory), current_count=len(actual),
            added=sorted(set(actual)-set(inventory)), removed=sorted(set(inventory)-set(actual)))
        if actual != inventory:
            raise ValueError('package inventory changed')
        for name in GDB_NAMES:
            if get('ABSENT_' + name) != (1, 'package %s is not installed' % name):
                raise ValueError('package absence not proven: ' + name)
        for label in ('WORK_PARENT', 'WORK'):
            if not absent(*get(label)):
                raise ValueError('work residue; metadata archived, ownership disposition required')
        nvr = {s.replace(' ', '-', 1) for s in inventory}
        residues = []
        for i, path in enumerate(paths):
            label = 'PATH_%04d' % i
            code, text = get(label)
            if absent(code, text):
                continue
            if code or not re.fullmatch(r'[^|]+\|\d+\|\d+\|\d+:\d+', text):
                raise ValueError('invalid path stat: ' + path)
            owner_rc, owner = get(label + '_OWNER')
            residues.append(dict(path=path, metadata=text, owner_rc=owner_rc, owner=owner))
            self.receipt['package_residue_observations'] = residues
            self.save()
            if owner_rc != 0 or not owner.splitlines() or any(x not in nvr for x in owner.splitlines()):
                raise ValueError('unowned/unknown residue; metadata archived, not removed: ' + path)
        self.receipt['residue_inventory'] = dict(total_paths=len(paths), absent=len(paths)-len(residues),
            shared_owned_paths=len(residues), disposition='shared/system-owned entries left untouched')
        for label in ('DF_ROOT', 'DF_OPTUSR', 'DATE', 'UPTIME', 'SWAPS', 'TOP_TMP', 'TOP_HOME', 'TOP_OPTUSR'):
            good(label)
        connections = []
        for label in ('TCP4', 'TCP6'):
            for line in good(label).splitlines():
                f = line.split()
                if len(f)>3 and f[1].upper().endswith(':65F5') and f[3]=='01':
                    connections.append(line)
        self.inspect_connections(connections)
        self.receipt['health'] = dict(oom_lmk_new=0, zram_three_delta=[0,0,0],
            attributable_alerts_new=0, boot_unchanged=True, dmesg_prefix_retained=True)
        self.receipt['verdict'] = 'PASS_READONLY_CLEANUP'

    def archive_alerts(self, scope, names):
        for i, name in enumerate(names):
            if '/' in name or not re.fullmatch(r'[A-Za-z0-9_.+-]+', name):
                raise ValueError('unsupported livedump filename; no action')
            path = file_path(CRASH + '/' + name)
            for suffix, op in [('STAT', stat_op(path)), ('SHA', ['sha256sum', '--', path]),
                               ('B64', ['base64', '--', path])]:
                self.op(scope + '_%04d_' % i + suffix, op, scope=scope)

    def classify_alerts(self, scope, names, prior):
        rows=[]
        for i,name in enumerate(names):
            values={}
            for suffix in ('STAT','SHA','B64'):
                code,value=self.results[scope+'_%04d_'%i+suffix]
                if code:
                    raise ValueError('livedump read failed: '+name+' '+suffix)
                values[suffix]=value
            fields=values['STAT'].split('|')
            if len(fields)!=4 or fields[0]!='regular file':
                raise ValueError('livedump not a regular non-symlink file')
            data=base64.b64decode(''.join(values['B64'].splitlines()),validate=True)
            sha=hashlib.sha256(data).hexdigest()
            if len(data)!=int(fields[1]) or sha!=values['SHA'].split()[0]:
                raise ValueError('livedump base64/size/SHA mismatch')
            folder=self.out/'livedump'/scope
            folder.mkdir(parents=True,exist_ok=True)
            archive=folder/name
            archive.write_bytes(data)
            reason,info=STABILITY.inspect_archive(archive)
            pid=str(info.get('threads',{}).get('pid',''))
            exe=str(info.get('exe_file_path',''))
            known={str(prior['preflight']['enlightenment_pid']):{'/usr/bin/enlightenment'}}
            windows=[]
            for cell in prior['completed_cells']:
                directory=SOURCE/'raw'/cell
                windows.append((int((directory/'start_ns.txt').read_text()),int((directory/'end_ns.txt').read_text())))
                for filename in ('controller_identity.txt','sampler_identity.txt','debugger_identity.txt'):
                    f=directory/filename
                    if f.is_file():
                        helper=f.read_text().split()[0]
                        allowed={'/usr/bin/gdb'} if filename=='debugger_identity.txt' else {'/bin/sh','/usr/bin/sh','/bin/bash','/usr/bin/bash'}
                        known.setdefault(helper,set()).update(allowed)
            stamp=int(fields[2])*10**9
            inside=any(start<=stamp and stamp+10**9<=end for start,end in windows)
            overlap=any(stamp<=end and stamp+10**9>start for start,end in windows)
            identity=pid in known and (exe in known[pid] or
                (pid==str(prior['preflight']['enlightenment_pid']) and pathlib.PurePosixPath(exe).name=='enlightenment') or exe.startswith(WORK+'/'))
            own=identity and inside
            row=dict(path=CRASH+'/'+name,sha256=sha,size=len(data),mtime_epoch=int(fields[2]),
                pid=pid,executable=exe,reason=reason,attributable=own,
                ambiguous=identity and overlap and not inside,
                verdict='FAIL' if own else 'REPORT_ONLY_UNATTRIBUTED_LEFT_UNTOUCHED')
            rows.append(row)
            self.receipt['alerts_'+scope]=rows
            self.save()  # metadata and full archive precede any exact cleanup
            if own:
                # No batched deletion or shell predicates. Recheck each property
                # separately, then remove only this archived, hash-bound file.
                self.authorized_removals.add(row['path'])
                for suffix,op,expected in [('RECHECK_STAT',stat_op(row['path']),values['STAT']),
                        ('RECHECK_SHA',['sha256sum','--',row['path']],values['SHA'])]:
                    result=self.op(scope+'_%04d_'%i+suffix,op,False,scope=scope)
                    if result!=(0,expected):
                        raise ValueError('attributable livedump changed before cleanup; not removed')
                result=self.op(scope+'_%04d_REMOVE'%i,['rm','--',row['path']],False,scope=scope)
                if result[0]:
                    raise ValueError('attributable livedump removal failed')
                result=self.op(scope+'_%04d_VERIFY'%i,stat_op(row['path']),False,scope=scope)
                if not absent(*result):
                    raise ValueError('attributable livedump removal not verified')
                row['archived_then_removed_verified']=True
                self.save()
            if own or row['ambiguous']:
                raise ValueError('attributable/ambiguous new alert; no health waiver')

    def drop_root(self):
        auth = self.receipt['root_authorization']
        auth['off_attempts'] = []
        for n in (1,2):
            entry = dict(attempt=n, start_utc=utc())
            auth['off_attempts'].append(entry)
            try:
                self.run('ROOT_OFF_%d'%n, ['sdb','-s',self.serial,'root','off'])
                observed = self.ok('ID_OFF_%d'%n, ['id'], False)
                entry['id'] = observed
                if not observed.startswith('uid=5001('):
                    raise ValueError('non-root restoration not verified')
                auth['root_off'] = 'PASS_NONROOT'
                return
            except Exception as error:
                entry['error'] = str(error)
            finally:
                entry['end_utc'] = utc()
        auth['root_off'] = 'FAIL'
        self.receipt['verdict'] = 'STOP'

    def execute(self):
        try:
            self.receipt['executor_commit'] = git('rev-parse','HEAD')
            if git('status','--porcelain'):
                raise ValueError('clean committed snapshot required')
            if git('ls-remote','origin','refs/heads/main').split()[0] != self.receipt['executor_commit']:
                raise ValueError('executor must be pushed before connection')
            prior, paths, inventory = sources()
            self.receipt['source_execution_sha256'] = hashlib.sha256((SOURCE/'execution.json').read_bytes()).hexdigest()
            self.run('SDB_VERSION',['sdb','version'])
            _, text = self.run('CONNECT',['sdb','connect',self.addr])
            if re.search(r'failed|unable|cannot|error|HOST_TIMEOUT',text,re.I):
                raise ValueError('connection failure; no retry')
            self.identity()
            self.nonroot(prior, paths)
            self.receipt['nonroot_sweep_completed_utc'] = utc()
            self.pre_root_check(prior, inventory)
            self.elevate_denied()
            self.validate(prior, paths, inventory)
        except Exception as error:
            self.receipt['verdict'] = 'STOP'
            self.receipt['reason'] = str(error).replace(self.addr,'<TEST_BOARD_IP>')
        finally:
            if self.raised:
                self.drop_root()
            elif 'id_before' in self.receipt and 'id_final' not in self.receipt:
                try:
                    self.receipt['id_final'] = self.ok('ID_FINAL',['id'],False)
                except Exception as error:
                    self.receipt['final_id_error'] = str(error)
                    self.receipt['verdict'] = 'STOP'
            if not self.raised and not self.receipt.get('id_final','').startswith('uid=5001('):
                self.receipt['verdict'] = 'STOP'
            self.receipt['end_utc'] = utc()
            self.save()
        print('FINAL_SINGLE_CLEANUP',json.dumps(self.receipt),flush=True)
        return 0 if self.receipt['verdict']=='PASS_READONLY_CLEANUP' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip',required=True)
    p.add_argument('--output-dir',required=True,type=pathlib.Path)
    p.add_argument('--pm-authorization',choices=[TOKEN])
    args=p.parse_args()
    if not args.output_dir.resolve().is_relative_to(ROOT/'board_results'):
        p.error('output must be a new local board_results directory')
    return SingleAudit(args).execute()


if __name__=='__main__':
    raise SystemExit(main())
