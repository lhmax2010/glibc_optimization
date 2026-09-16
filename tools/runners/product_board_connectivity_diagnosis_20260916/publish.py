#!/usr/bin/env python3
"""Publish redacted diagnosis logs; host-only, with raw/public byte hashes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('floor_publication',
    ROOT/'tools/runners/product_floor_reconfirm_20260916/publish_compact.py')
floor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(floor)


def publish(source, output, mapping, address):
    if output.exists():
        raise ValueError('refusing to overwrite public evidence')
    clean = floor.redactor(mapping, address)
    manifest = []
    output.mkdir(parents=True)
    paths = sorted(source.rglob('*.txt'))+sorted(source.rglob('*.json'))+sorted(source.rglob('*.jsonl'))
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError('nonregular evidence')
        relative = path.relative_to(source)
        raw = path.read_bytes()
        public = clean(raw.decode())
        public = re.sub(r'(?i)(?<![a-z0-9])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![a-z0-9])',
                        '<PRODUCT_BOARD_MAC>', public)
        if floor.privacy.find_endpoints(public):
            raise ValueError('unredacted endpoint: '+str(relative))
        if path.suffix in ('.json', '.jsonl'):
            for text in public.splitlines() if path.suffix == '.jsonl' else [public]:
                json.loads(text)
        target = output/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(public)
        manifest.append({'path': str(relative), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                         'public_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                         'redacted': raw != target.read_bytes()})
    (output/'publication.json').write_text(json.dumps({'schema': 'connectivity-diagnosis-publication.v1',
        'files': manifest, 'policy': 'Endpoint/host-path aliases only; empty streams preserved. Full raw evidence retained locally.'}, indent=2)+'\n')
    transcript = ['# 逐条连接诊断原文（脱敏公开副本）', '',
        '仅端点、host 路径与既有别名脱敏；空 stdout/stderr 单独标明，不补写为成功。', '']
    for log in sorted(output.rglob('commands.jsonl')):
        for line in log.read_text().splitlines():
            row = json.loads(line)
            transcript += ['## '+row['label'], '',
                '`'+shlex.join(row['argv'])+'`', '',
                row['started_utc']+' → '+row['ended_utc']+'; host RC='+str(row['host_rc']), '']
            for name in ('stdout', 'stderr'):
                path = log.parent/row['streams'][name]['path']
                text = path.read_text()
                transcript += [name+':', '', '```text', text.rstrip('\n'), '```', ''] if text else [name+': 空（0 bytes）。', '']
    (output/'transcript.md').write_text('\n'.join(transcript).rstrip()+'\n')
    print('PASS public diagnosis files='+str(len(manifest)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--ip', required=True)
    args = parser.parse_args()
    publish(args.source, args.output, args.mapping, args.ip)
