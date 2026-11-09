#!/usr/bin/env python3
"""Extract only malloc_trim symbol identities from local, hash-verified readelf text."""
import argparse
import csv
import hashlib
import io
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT/'data/raw/p0_pagemap_residency_20261109'
LINE = re.compile(r'^\s*\d+:\s+[0-9a-fA-F]+\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+.*)?$')

def read_tsv(path):
    with path.open() as f: return list(csv.DictReader(f,delimiter='\t'))

def render(header, rows):
    out=io.StringIO(newline='');w=csv.writer(out,delimiter='\t',lineterminator='\n')
    w.writerow(header);w.writerows(rows);return out.getvalue().encode()

def extract(raw_dir, data):
    inventory={r['path']:r for r in read_tsv(data/'derived/local_only_FILES.tsv')}
    sources=read_tsv(data/'derived/readelf_sources.tsv')
    if len(sources)!=31 or len({r['board_path'] for r in sources})!=31:
        raise ValueError('expected 31 distinct source paths')
    symbols=[];summary=[]
    for row in sources:
        name=row['raw_file']
        if not re.fullmatch(r'resume6_readelf_\d{2}\.raw',name):raise ValueError('invalid source filename')
        raw=(raw_dir/name).read_bytes();meta=inventory[name]
        if len(raw)!=int(meta['bytes']) or hashlib.sha256(raw).hexdigest()!=meta['original_sha256']:
            raise ValueError('local raw hash/size mismatch: '+name)
        matches=[]
        for line in raw.decode().splitlines():
            m=LINE.match(line)
            if not m or 'malloc_trim' not in m[5]:continue
            typ,bind,visibility,ndx,symbol=m.groups()
            matches.append((ndx,symbol))
            symbols.append([row['board_path'],row['realpath'],bind,typ,ndx,symbol])
        if int(row['readelf_rc']):verdict='readelf 失败'
        elif any(ndx=='UND' for ndx,_ in matches):verdict='UND 导入'
        elif matches:verdict='定义'
        else:verdict='字符串误命中'
        if verdict!=row['expected_verdict']:raise ValueError('resume6 report verdict differs: '+row['board_path'])
        summary.append([row['board_path'],verdict])
    return {
        'malloc_trim_symbols.tsv':render(['board_path','realpath','bind','type','ndx','symbol'],symbols),
        'malloc_trim_callers_summary.tsv':render(['board_path','verdict'],summary)
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir',required=True,type=Path,help='local directory containing the 31 original readelf .raw files')
    p.add_argument('--data',type=Path,default=DATA)
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    for name,raw in extract(a.raw_dir,a.data).items():
        path=a.data/'derived'/name
        if a.write:path.write_bytes(raw)
        if path.read_bytes()!=raw:raise ValueError('derived table differs: '+name)
        print('PASS',name,'source-hashes=verified','report-verdicts=31/31','bytes=identical','sha256='+hashlib.sha256(raw).hexdigest())
    print('PASS symbol extraction: Value/Size/Num omitted; realpath unrecorded and empty')

if __name__=='__main__':main()
