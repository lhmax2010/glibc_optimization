#!/usr/bin/env python3
"""Host-only replay of preserved raw P0 files. Never connects to a board."""
import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'data/raw/p0_pagemap_residency_20261109'
RES_COLS = 'trim present_pre present_post swapped_pre swapped_post pd_pre_kib pd_post_kib rss_pre_kib rss_post_kib reclaimed_bytes minflt_delta majflt_delta trim_ret inject_ms h1_pass h3_pass'.split()
POOL_COLS = 'trim arena rest top unsorted_total sorted_ge_page_total sorted_lt_page_total sorted_ge_page_inner_bytes'.split()

def tsv(cols, rows):
    out = io.StringIO(newline='')
    w = csv.writer(out, delimiter='\t', lineterminator='\n')
    w.writerow(cols)
    w.writerows(rows)
    return out.getvalue().encode()

def sample(raw, n, phase, mode):
    prefix = raw / f't{n}_{phase}'
    smaps = prefix.with_name(prefix.name + '_smaps.txt').read_text()
    fields = {m[1]: int(m[2]) for m in re.finditer(r'^(\w+):\s+(\d+) kB$', smaps, re.M)}
    for key in ('Size', 'Rss', 'Pss', 'Private_Dirty', 'Swap'):
        if key not in fields: raise ValueError('required smaps field missing: '+key)
    mappings = prefix.with_name(prefix.name + '_maps.txt').read_text().splitlines()
    if len(mappings) != 1 or '[heap]' not in mappings[0]: raise ValueError('not one heap mapping')
    start, end = (int(v, 16) for v in mappings[0].split()[0].split('-'))
    if start % 4096 or end % 4096 or end <= start: raise ValueError('invalid heap range')
    if smaps.split()[0] != mappings[0].split()[0]: raise ValueError('smaps/maps range mismatch')
    expected = (end-start)//4096
    if mode == 'bin':
        data = prefix.with_name(prefix.name + '_pm.bin').read_bytes()
        if len(data) != expected*8: raise ValueError('pagemap byte count mismatch')
        words = [v[0] for v in struct.iter_unpack('<Q', data)]
        bits = [[i,w>>63&1,w>>62&1,w>>56&1,w>>55&1] for i,w in enumerate(words)]
    else:
        with prefix.with_name(prefix.name + '_pagemap_bits.tsv').open() as src:
            reader = csv.reader(src,delimiter='\t')
            if next(reader) != ['page_index','present','swapped','exclusive','soft_dirty']:
                raise ValueError('bit table header mismatch')
            bits = [[int(v) for v in row] for row in reader]
    if len(bits) != expected: raise ValueError('bit row count mismatch')
    for i,row in enumerate(bits):
        if len(row)!=5 or row[0]!=i or any(v not in (0,1) for v in row[1:]):
            raise ValueError('invalid page index or bit value')
    stat = prefix.with_name(prefix.name + '_stat.txt').read_text()
    tail = stat[stat.rfind(')')+2:].split()
    return dict(pd=fields['Private_Dirty'], rss=fields['Rss'], present=sum(v[1] for v in bits), swapped=sum(v[2] for v in bits), minflt=int(tail[7]), majflt=int(tail[9]), pid=int(stat.split()[0]), starttime=int(tail[19]))

def calculate(base, mode):
    # Validate all imported byte copies: historical FILES/SHA256SUMS remain records,
    # not manifests of the intentionally smaller public evidence set.
    public = json.loads((base/'derived/public_copy_hashes.json').read_text())
    with (base/'derived/local_only_FILES.tsv').open() as f:
        local_only = {row['path']:row for row in csv.DictReader(f,delimiter='\t')}
    for item in json.loads((base/'copy_manifest.json').read_text()):
        path = ROOT/item['target']
        if re.fullmatch(r'resume6_readelf_\d{2}\.raw',path.name):
            entry=local_only[path.name]
            if path.exists() or entry['original_sha256']!=item['sha256'] or int(entry['bytes'])!=item['bytes']:
                raise ValueError('local-only readelf inventory mismatch: '+path.name)
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != public[item['target']]:
            raise ValueError('copied evidence hash differs: '+item['target'])
    if hashlib.sha256((base/'prediction.txt').read_bytes()).hexdigest() != 'ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14':
        raise ValueError('prediction hash mismatch')
    raw = base/'resume7_data'
    state = json.loads((base/'resume7_state.json').read_text())
    records = {r['label']: r for r in state['records']}
    residency, pools = [], []
    identity = None
    for n in (1, 2, 3):
        pre, post = sample(raw,n,'pre',mode), sample(raw,n,'post',mode)
        identity = identity or (pre['pid'],pre['starttime'])
        if any((v['pid'],v['starttime']) != identity for v in (pre,post)): raise ValueError('target changed')
        record = records[f'a0_t{n}_trim']
        receipt = (base/record['file']).read_text()
        returned = re.findall(r'^\$\d+ = (-?\d+)\s*$',receipt,re.M)
        if len(returned)!=1: raise ValueError('trim result ambiguous')
        ms = Decimal(record['end_ns']-record['start_ns'])/Decimal(1000000)
        reclaimed = (pre['pd']-post['pd'])*1024
        h1 = reclaimed == (pre['present']-post['present'])*4096
        h3 = abs(pre['present']*4096-pre['pd']*1024)<=8192
        if pre['swapped'] or post['swapped']: raise ValueError('H4 failed')
        if n>1 and (pre['present']-post['present']>1 or reclaimed>4096): raise ValueError('H2 failed')
        residency.append([n,pre['present'],post['present'],pre['swapped'],post['swapped'],pre['pd'],post['pd'],pre['rss'],post['rss'],reclaimed,post['minflt']-pre['minflt'],post['majflt']-pre['majflt'],int(returned[0]),format(ms,'.6f'),str(h1).lower(),str(h3).lower()])
        tree = ET.parse(raw/f't{n}_pre.xml').getroot()
        if tree.tag!='malloc': raise ValueError('invalid malloc XML')
        for heap in tree.findall('heap'):
            rest = int(heap.find("total[@type='rest']").get('size'))
            entries = list(heap.find('sizes'))
            unsorted = sum(int(e.get('total')) for e in entries if e.tag=='unsorted')
            large = [e for e in entries if e.tag=='size' and int(e.get('to'))>=4096]
            small = [e for e in entries if e.tag=='size' and int(e.get('to'))<4096]
            top = rest-sum(int(e.get('total')) for e in entries if e.tag in ('size','unsorted'))
            inner = 0
            for entry in large:
                count,total = int(entry.get('count')),int(entry.get('total'))
                if count<=0: raise ValueError('nonpositive histogram count')
                inner += count*max(0,(total-24*count)//(4096*count))*4096
            pools.append([n,int(heap.get('nr')),rest,top,unsorted,sum(int(e.get('total')) for e in large),sum(int(e.get('total')) for e in small),inner])
    if mode == 'bin':
        aux = list(struct.iter_unpack('<II',(raw/'auxv.bin').read_bytes()))
    else:
        with (raw/'auxv.tsv').open() as src:
            reader = csv.DictReader(src,delimiter='\t')
            aux = [(int(row['type']),int(row['value'])) for row in reader]
    secure = [value for kind,value in aux if kind==23]
    if len(secure)!=1: raise ValueError('AT_SECURE missing/ambiguous')
    return {'residency_summary.tsv':tsv(RES_COLS,residency),'malloc_info_pools.tsv':tsv(POOL_COLS,pools)},secure[0]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=DEFAULT)
    p.add_argument('--write',action='store_true',help='write derived tables, then compare fixed manual references')
    args=p.parse_args()
    values,secure=calculate(args.data,'text')
    binary,binary_secure=calculate(args.data,'bin')
    if values != binary or secure != binary_secure:
        raise ValueError('text/bin derived tables or AT_SECURE differ')
    for n in (1,2,3):
        for phase in ('pre','post'):
            prefix=args.data/'resume7_data'/f't{n}_{phase}'
            words=[v[0] for v in struct.iter_unpack('<Q',prefix.with_name(prefix.name+'_pm.bin').read_bytes())]
            expected=[[i,w>>63&1,w>>62&1,w>>56&1,w>>55&1] for i,w in enumerate(words)]
            with prefix.with_name(prefix.name+'_pagemap_bits.tsv').open() as src:
                reader=csv.reader(src,delimiter='\t'); next(reader)
                actual=[[int(v) for v in row] for row in reader]
            if actual!=expected: raise ValueError('per-page bit mismatch')
    print('PASS pagemap_bits.tsv vs .bin: all six files, every page and all four bits identical; residency tables byte-identical')
    for name,expected in values.items():
        manual=args.data/'derived'/('manual_'+name)
        if manual.read_bytes()!=expected: raise ValueError('manual reference differs: '+name)
        target=args.data/'derived'/name
        if args.write: target.write_bytes(expected)
        if target.read_bytes()!=expected: raise ValueError('committed table differs: '+name)
        print('PASS',name,'manual-values=identical','bytes=identical','sha256='+hashlib.sha256(expected).hexdigest())
    print('PASS H1/H2/H3/H4; AT_SECURE='+str(secure))

if __name__=='__main__': main()
