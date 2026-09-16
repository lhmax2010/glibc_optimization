#!/usr/bin/env python3
"""Host-only parser/replay for the fixed passive product-floor contract."""
import argparse
import csv
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT/'tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py'
spec = importlib.util.spec_from_file_location('historical_phenotypes', OLD)
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)
HEADER = re.compile(r'^([0-9a-fA-F]+)-([0-9a-fA-F]+) ([rwxps-]{4}) \S+ \S+ \S+(?:\s+(.*))?$')


def smaps(text):
    totals = [0, 0, 0]
    mapping = None
    seen = 0

    def flush():
        nonlocal seen
        if mapping is None:
            return
        start, end, perms, name, dirty = mapping
        if dirty is None:
            raise ValueError('missing Private_Dirty in mapping')
        length = end-start
        if name == '[heap]' or (perms == 'rw-p' and name == '' and start % 1048576 == 0 and 0 < length <= 1048576):
            kind = 0
        elif perms[1] == 'w' and (not name or (name.startswith('[') and name.endswith(']'))):
            kind = 1
        else:
            kind = 2
        totals[kind] += dirty
        seen += 1

    for line in text.splitlines():
        match = HEADER.fullmatch(line)
        if match:
            flush()
            mapping = [int(match[1], 16), int(match[2], 16), match[3], match[4] or '', None]
        elif line.startswith('Private_Dirty:'):
            match = re.fullmatch(r'Private_Dirty:\s+(\d+) kB', line)
            if match is None or mapping is None or mapping[4] is not None:
                raise ValueError('malformed/duplicate Private_Dirty')
            mapping[4] = int(match[1])
    flush()
    if not seen:
        raise ValueError('no smaps mappings')
    return dict(zip(('glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb', 'total_pd_kb'),
                    totals + [sum(totals)]))


def proc_stat(text):
    match = re.fullmatch(r'(\d+) \((.*)\) (.*)', text.strip())
    if not match:
        raise ValueError('invalid proc stat')
    tail = match[3].split()
    return {'pid': int(match[1]), 'comm': match[2], 'state': tail[0],
            'minflt': int(tail[7]), 'majflt': int(tail[9]), 'start_ticks': int(tail[19])}


def analyze(rows):
    results = []
    for target, sequence in historical.group_by(rows, 'target').items():
        if len(sequence) != 601 or [r['sample'] for r in sequence] != list(range(601)):
            raise ValueError('incomplete 10-minute sequence: '+target)
        if len({(r['pid'], r['start_ticks']) for r in sequence}) != 1:
            raise ValueError('process identity changed: '+target)
        for r in sequence:
            if r['total_pd_kb'] != sum(r[k] for k in ('glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb')):
                raise ValueError('PD buckets do not sum: '+target)
        for a, b in zip(sequence, sequence[1:]):
            if b['epoch_ns'] <= a['epoch_ns'] or any(b[k] < a[k] for k in ('minflt', 'majflt')):
                raise ValueError('clock or fault counter regression: '+target)
        result = historical.release_ratio_census(sequence, {})[0]
        result.update({
            'absolute_floor_kib': min(r['glibc_heap_pd_kb'] for r in sequence),
            'first_minute_floor_kib': min(r['glibc_heap_pd_kb'] for r in sequence[:60]),
            'last_minute_floor_kib': min(r['glibc_heap_pd_kb'] for r in sequence[-60:]),
            'window_minflt_delta': sequence[-1]['minflt']-sequence[0]['minflt'],
            'window_majflt_delta': sequence[-1]['majflt']-sequence[0]['majflt'],
            'zram_positive_steps': sum(b['zram_orig_bytes'] > a['zram_orig_bytes'] for a, b in zip(sequence, sequence[1:])),
            'elapsed_s': (sequence[-1]['epoch_ns']-sequence[0]['epoch_ns'])/1e9,
        })
        result['floor_change_kib'] = result['last_minute_floor_kib']-result['first_minute_floor_kib']
        drop = historical.largest_drawdown(sequence)
        result['drawdown_total_pd_delta_kib'] = drop['trough']['total_pd_kb']-drop['peak']['total_pd_kb']
        result['drawdown_other_anon_delta_kib'] = drop['trough']['other_anon_pd_kb']-drop['peak']['other_anon_pd_kb']
        results.append(result)
    if not results:
        raise ValueError('no candidates sampled')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeseries', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.timeseries.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    for row in rows:
        for key in row:
            if key != 'target':
                row[key] = int(row[key])
    result = analyze(rows)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print('PASS product-floor replay: '+str(len(result))+' candidates')


if __name__ == '__main__':
    main()
