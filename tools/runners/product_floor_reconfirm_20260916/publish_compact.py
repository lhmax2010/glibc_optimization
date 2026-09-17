#!/usr/bin/env python3
"""Publish only bounded, sanitized host evidence; never contacts a board."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('endpoint_privacy', ROOT/'tools/privacy/scan_endpoints.py')
privacy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = privacy
spec.loader.exec_module(privacy)


def redactor(mapping, address):
    with mapping.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    replacements = [(r['original'], r['replacement']) for r in rows if r['scope'] == 'global'
                    and r['type'] != 'user_home']
    replacements += [(str(ROOT), '<WORKSPACE>'), (str(Path.home()), '<USER_HOME>')]
    replacements.sort(key=lambda pair: -len(pair[0]))
    def redact(text):
        text, _ = privacy.redact_endpoints(text, {address: '<PRODUCT_BOARD_IP>'})
        for source, replacement in replacements:
            text = text.replace(source, replacement)
        return text
    return redact


def publish(source, output, mapping, address, receipt):
    if output.exists():
        raise ValueError('refusing to overwrite compact evidence')
    state = json.loads((source/'state.json').read_text())
    if state['status'] not in ('STOP', 'COMPLETE'):
        raise ValueError('source must have a terminal status')
    if state['status'] == 'COMPLETE':
        if (source/'authorization.json').exists() and state.get('root_off_verified_uid') != 5001:
            raise ValueError('complete publication root-off UID 5001 unproven')
        contract = json.loads((HERE/'contract.json').read_text())
        with (source/'timeseries.tsv').open() as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            if set(reader.fieldnames or []) != set(contract['sampling']['fields']):
                raise ValueError('complete publication missing contract columns')
            rows = list(reader)
        if not rows or any(not re.fullmatch(r'\d+', v) for r in rows for k, v in r.items() if k != 'target'):
            raise ValueError('complete publication missing numeric observations; never substitute zero')
        timing = json.loads((source/'sampling_timing.json').read_text())
        if timing and 'deadline_mono_ns' in timing[0]:
            if len(timing)!=601 or any(r['sample']!=i or
                    r['deadline_mono_ns']!=timing[0]['deadline_mono_ns']+i*1000000000 or
                    not r['deadline_mono_ns']<=r['begin_mono_ns']<=r['end_mono_ns']<r['deadline_mono_ns']+1000000000
                    for i,r in enumerate(timing)):
                raise ValueError('complete publication violates 1 s cadence')
            sys.path.insert(0,str(HERE))
            from analyze_floor import analyze
            numeric=[{k:(v if k=='target' else int(v)) for k,v in r.items()} for r in rows]
            if analyze(numeric)!=json.loads((source/'summary.json').read_text()):
                raise ValueError('complete publication summary mismatch')
            owned=json.loads((source/'owned_scripts.json').read_text())
            cleaned=json.loads((source/'cleanup.json').read_text())
            if not owned or len(owned)!=len(cleaned) or any(dict(o,absent=True)!=c for o,c in zip(owned,cleaned)):
                raise ValueError('complete publication script cleanup unproven')
        elif len(timing) != 601 or any(r['lateness_s']+r['read_duration_s'] >= 1 for r in timing):
            raise ValueError('complete publication violates 1 s cadence')
    clean = redactor(mapping, address)
    output.mkdir(parents=True)
    files = [p for p in source.iterdir() if p.is_file() and p.suffix in ('.json', '.jsonl', '.tsv')]
    # smaps, whole-process inventories and high-rate read streams stay local.
    # The manifest still preserves their hashes in commands.jsonl.
    allowed_raw = {'sdb_version', 'connect', 'devices', 'uname_r', 'uname_m', 'os_release',
                   'glibc', 'libc_version', 'cpu_online', 'clk_tck', 'meminfo',
                   'uptime', 'date', 'id', 'df', 'proc_uptime', 'gdb', 'ptrace_scope',
                   'vk_send_path', 'rpm_path', 'zypper_path', 'rpm_dbpath',
                   'shell_status', 'tmp_writable', 'awk_path', 'timeout_path', 'tools'}
    transition_raw = {'pre_id_before_root_on', 'pre_root_on', 'pre_id_after_root_on',
                      'restore_root_off', 'restore_id_after_root_off'}
    files += [p for p in (source/'raw').glob('*.txt') if p.stem in allowed_raw
              or p.stem in transition_raw
              or any(p.stem == prefix+'_'+label for prefix in ('pre', 'root') for label in allowed_raw)]
    if (source/'commands.jsonl').exists():
        # Permission errors are compact evidence; successful full smaps stay local.
        commands=[json.loads(l) for l in (source/'commands.jsonl').read_text().splitlines()]
        files += [source/'raw'/(r['label']+'.txt') for r in commands
                  if r['label'].startswith(('permission_', 'root_permission_')) and r.get('remote_rc',0)!=0]
    manifest = []
    for path in files:
        relative = path.relative_to(source)
        text = path.read_text()
        public = clean(text)
        if privacy.find_endpoints(public):
            raise ValueError('redaction failed: '+str(relative))
        if path.suffix in ('.json', '.jsonl'):
            # Verify substitutions did not break JSON escape structure.
            for line in public.splitlines() if path.suffix == '.jsonl' else [public]:
                json.loads(line)
        destination = output/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(public)
        manifest.append({'path': str(relative), 'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'public_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                         'redacted': text != public})
    (output/'contract_push.json').write_text(clean(receipt.read_text()))
    (output/'publication.json').write_text(json.dumps({'schema': 'product-floor-publication.v1',
        'status': state['status'], 'files': manifest, 'policy': 'Host paths and internal identifiers sanitized; board runtime paths retained. Full raw evidence local, available on request.'}, indent=2)+'\n')
    print('PASS compact publication: '+state['status']+' files='+str(len(manifest)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--ip', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    publish(args.source, args.output, args.mapping, args.ip, args.receipt)
