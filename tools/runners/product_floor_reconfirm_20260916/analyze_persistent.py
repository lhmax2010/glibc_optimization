#!/usr/bin/env python3
"""Strict host replay of nonce-framed, single-session readonly observations."""
import argparse
import csv
import json
from pathlib import Path
import re
import statistics

from analyze_floor import historical, proc_stat, smaps

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE/'persistent_contract.json').read_text())
FIELDS = ('sample target pid start_ticks epoch_ns board_end_ns host_epoch_ns host_monotonic_ns '
          'host_end_monotonic_ns glibc_heap_pd_kb other_anon_pd_kb file_backed_pd_kb total_pd_kb '
          'minflt majflt MemAvailable_kb zram_used_kb zram_orig_bytes zram_compr_bytes '
          'zram_mem_used_bytes globals_start_ns globals_end_ns').split()


def distribution(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values))


class Parser:
    def __init__(self, nonce, candidates):
        if not re.fullmatch('[a-f0-9]{32}', nonce):
            raise ValueError('invalid nonce')
        self.nonce, self.candidates = nonce, candidates
        self.rows, self.batches = [], []
        self.started = self.final = False
        self.batch = self.reading = None
        self.sections = {}
        self.plan = [('mem', 0), ('zram', 0), ('swaps', 0)]
        for c in candidates:
            self.plan += [(k, c['pid']) for k in ('before', 'smaps', 'after')]

    def feed(self, line, epoch_ns, monotonic_ns):
        line = line.rstrip('\r\n')
        # Shell prompts/echo are not evidence. Inside a data section they are
        # retained and must satisfy that section's parser.
        marker = re.fullmatch(r'===(.*?)===', line)
        if not marker:
            if self.reading is not None:
                self.reading['lines'].append(line)
            return None
        words = marker[1].split()
        if len(words) < 2 or words[1] != self.nonce:
            raise ValueError('STOP unexpected stream marker')
        kind = words[0]
        if kind == 'SESSION' and len(words) == 3 and not self.started:
            if not words[2].isdigit():
                raise ValueError('STOP invalid observer PID')
            self.started = True
            self.observer_pid = int(words[2])
            return None
        if not self.started or self.final:
            raise ValueError('STOP marker outside session')
        if kind == 'SAMPLE' and len(words) == 4 and self.batch is None:
            index, stamp = map(int, words[2:])
            if index != len(self.batches) or stamp < 10**18:
                raise ValueError('STOP invalid sample sequence/epoch')
            self.batch = dict(sample=index, board_start_ns=stamp,
                              host_epoch_ns=epoch_ns, host_start_ns=monotonic_ns)
            self.sections = {}
        elif kind == 'READ' and len(words) == 5 and self.batch is not None and self.reading is None:
            key = (words[2], int(words[3]))
            if len(self.sections) >= len(self.plan) or key != self.plan[len(self.sections)]:
                raise ValueError('STOP missing/duplicate/out-of-order read')
            self.reading = dict(key=key, board_start_ns=int(words[4]),
                                host_epoch_ns=epoch_ns, host_start_ns=monotonic_ns, lines=[])
        elif kind == 'RC' and len(words) == 5 and self.reading is not None:
            if words[2:4] != ['0', 'DONE']:
                raise ValueError('STOP remote read failed: '+' '.join(words[2:4]))
            r = self.reading
            r.update(board_end_ns=int(words[4]), host_end_ns=monotonic_ns)
            if r['board_end_ns'] < r['board_start_ns']:
                raise ValueError('STOP read clock regressed')
            self.sections[r['key']] = r
            self.reading = None
        elif kind == 'END' and len(words) == 6 and self.batch is not None and self.reading is None:
            if int(words[2]) != self.batch['sample'] or words[4:] != ['RC=0', 'DONE']:
                raise ValueError('STOP invalid batch ending')
            if list(self.sections) != self.plan:
                raise ValueError('STOP incomplete batch')
            self.batch.update(board_end_ns=int(words[3]), host_end_ns=monotonic_ns)
            rows = self.finish_batch()
            self.batches.append(self.batch)
            self.rows.extend(rows)
            self.batch = None
            return rows
        elif kind == 'FINAL' and len(words) == 4 and self.batch is None and self.reading is None:
            if words[2:] != ['RC=0', 'DONE'] or not self.batches:
                raise ValueError('STOP remote final failure')
            self.final = True
        else:
            raise ValueError('STOP malformed/unexpected frame: '+kind)
        return None

    def finish_batch(self):
        if self.batch['board_end_ns'] < self.batch['board_start_ns']:
            raise ValueError('STOP batch clock regressed')
        previous_end = self.batch['board_start_ns']
        for section in self.sections.values():
            if not previous_end <= section['board_start_ns'] <= section['board_end_ns'] <= self.batch['board_end_ns']:
                raise ValueError('STOP read outside batch or overlapping')
            previous_end = section['board_end_ns']
        if self.batches and self.batch['board_start_ns'] < self.batches[-1]['board_end_ns']:
            raise ValueError('STOP overlapping batches')
        def content(key):
            return '\n'.join(self.sections[key]['lines']).strip()
        mem = re.search(r'^MemAvailable:\s+(\d+) kB$', content(('mem', 0)), re.M)
        zram = content(('zram', 0)).split()
        swaps = [s.split() for s in content(('swaps', 0)).splitlines()]
        if mem is None or len(zram) < 3 or any(not s.isdecimal() for s in zram):
            raise ValueError('STOP invalid globals')
        if not swaps or swaps[0] != ['Filename', 'Type', 'Size', 'Used', 'Priority']:
            raise ValueError('STOP invalid swaps header')
        used = [int(s[3]) for s in swaps[1:] if len(s) == 5 and s[0] == '/dev/zram0']
        if len(used) != 1 or len(swaps) != 2:
            raise ValueError('STOP unsupported/missing swap devices')
        global_fields = dict(MemAvailable_kb=int(mem[1]), zram_used_kb=used[0],
                             zram_orig_bytes=int(zram[0]), zram_compr_bytes=int(zram[1]),
                             zram_mem_used_bytes=int(zram[2]),
                             globals_start_ns=self.sections[('mem', 0)]['board_start_ns'],
                             globals_end_ns=self.sections[('swaps', 0)]['board_end_ns'])
        rows = []
        for c in self.candidates:
            pid = c['pid']
            before, after = [proc_stat(content((k, pid))) for k in ('before', 'after')]
            if any(any(s[k] != c[k] for k in ('pid', 'comm', 'start_ticks')) for s in (before, after)):
                raise ValueError('STOP candidate identity changed')
            if any(after[k] < before[k] for k in ('minflt', 'majflt')):
                raise ValueError('STOP faults regressed within read')
            r = self.sections[('smaps', pid)]
            row = dict(sample=self.batch['sample'], target=c['target'], pid=pid, start_ticks=c['start_ticks'],
                       epoch_ns=r['board_start_ns'], board_end_ns=r['board_end_ns'],
                       host_epoch_ns=r['host_epoch_ns'], host_monotonic_ns=r['host_start_ns'],
                       host_end_monotonic_ns=r['host_end_ns'],
                       **smaps(content(('smaps', pid))), minflt=after['minflt'], majflt=after['majflt'], **global_fields)
            if self.rows:
                previous = self.rows[-len(self.candidates)+len(rows)]
                if any(row[k] < previous[k] for k in ('minflt', 'majflt')):
                    raise ValueError('STOP fault counter regressed')
            rows.append(row)
        return rows


def covered(rows, candidates):
    groups = historical.group_by(rows, 'target')
    return set(groups) == {c['target'] for c in candidates} and all(
        all(s[-1][k]-s[0][k] >= 600_000_000_000 for k in ('epoch_ns', 'host_monotonic_ns'))
        for s in groups.values())


def analyze(rows, candidates, expected_targets=None):
    if expected_targets is None:
        snapshot = HERE.parents[2]/CONTRACT['candidates_snapshot']
        expected_targets = {c['target'] for c in json.loads(snapshot.read_text())['selected']}
    if ({c['target'] for c in candidates} != set(expected_targets) or
            len(candidates) != len(expected_targets) or len({c['pid'] for c in candidates}) != len(candidates)):
        raise ValueError('STOP candidate roster differs from frozen snapshot')
    if not covered(rows, candidates):
        raise ValueError('STOP incomplete 600-second candidate coverage')
    groups = historical.group_by(rows, 'target')
    if len({len(s) for s in groups.values()}) != 1:
        raise ValueError('STOP incomplete batch')
    for batch in historical.group_by(rows, 'sample').values():
        keys = ('MemAvailable_kb', 'zram_used_kb', 'zram_orig_bytes', 'zram_compr_bytes',
                'zram_mem_used_bytes', 'globals_start_ns', 'globals_end_ns')
        if len({tuple(r[k] for k in keys) for r in batch}) != 1:
            raise ValueError('STOP inconsistent batch globals')
    results = []
    for c in candidates:
        s = groups[c['target']]
        if [r['sample'] for r in s] != list(range(len(s))):
            raise ValueError('STOP missing/duplicate sample')
        for r in s:
            if set(r) != set(FIELDS) or any(type(v) is not int or v < 0 for k, v in r.items() if k != 'target'):
                raise ValueError('STOP invalid row schema')
            if (r['pid'], r['start_ticks']) != (c['pid'], c['start_ticks']):
                raise ValueError('STOP changed process identity')
            if r['total_pd_kb'] != sum(r[k] for k in ('glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb')):
                raise ValueError('STOP PD bucket sum')
            if r['board_end_ns'] < r['epoch_ns'] or r['host_end_monotonic_ns'] < r['host_monotonic_ns']:
                raise ValueError('STOP reversed read')
            if r['globals_end_ns'] < r['globals_start_ns'] or r['globals_end_ns'] > r['epoch_ns']:
                raise ValueError('STOP globals outside sequential read interval')
        for a, b in zip(s, s[1:]):
            if b['epoch_ns'] < a['epoch_ns'] or b['host_monotonic_ns'] <= a['host_monotonic_ns'] or any(b[k] < a[k] for k in ('minflt', 'majflt')):
                raise ValueError('STOP time/fault regression')
            if b['globals_start_ns'] <= a['globals_start_ns'] or b['globals_start_ns'] < a['globals_end_ns']:
                raise ValueError('STOP global reads stale/overlap')
        result = historical.release_ratio_census(s, {})[0]
        drop = historical.largest_drawdown(s)
        result.update(absolute_floor_kib=min(r['glibc_heap_pd_kb'] for r in s),
                      absolute_peak_kib=max(r['glibc_heap_pd_kb'] for r in s),
                      first_minute_floor_kib=min(r['glibc_heap_pd_kb'] for r in s if r['epoch_ns'] < s[0]['epoch_ns']+60e9),
                      last_minute_floor_kib=min(r['glibc_heap_pd_kb'] for r in s if r['epoch_ns'] > s[-1]['epoch_ns']-60e9),
                      window_minflt_delta=s[-1]['minflt']-s[0]['minflt'],
                      window_majflt_delta=s[-1]['majflt']-s[0]['majflt'],
                      zram_positive_steps=sum(b['zram_orig_bytes'] > a['zram_orig_bytes'] for a,b in zip(s,s[1:])),
                      zram_orig_window_delta_bytes=s[-1]['zram_orig_bytes']-s[0]['zram_orig_bytes'],
                      drawdown_total_pd_delta_kib=drop['trough']['total_pd_kb']-drop['peak']['total_pd_kb'],
                      drawdown_other_anon_delta_kib=drop['trough']['other_anon_pd_kb']-drop['peak']['other_anon_pd_kb'],
                      board_elapsed_s=(s[-1]['epoch_ns']-s[0]['epoch_ns'])/1e9,
                      host_elapsed_s=(s[-1]['host_monotonic_ns']-s[0]['host_monotonic_ns'])/1e9,
                      board_interval_ms=distribution([(b['epoch_ns']-a['epoch_ns'])/1e6 for a,b in zip(s,s[1:])]),
                      host_interval_ms=distribution([(b['host_monotonic_ns']-a['host_monotonic_ns'])/1e6 for a,b in zip(s,s[1:])]),
                      read_ms=distribution([(r['board_end_ns']-r['epoch_ns'])/1e6 for r in s]))
        result['floor_change_kib'] = result['last_minute_floor_kib']-result['first_minute_floor_kib']
        results.append(result)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    candidates = json.loads((args.source/'candidates.json').read_text())['selected']
    with (args.source/'timeseries.tsv').open() as stream:
        rows = [{k: v if k == 'target' else int(v) for k,v in r.items()} for r in csv.DictReader(stream, delimiter='\t')]
    result = analyze(rows, candidates)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('PASS persistent product-floor replay: '+str(len(result))+' candidates')


if __name__ == '__main__':
    main()
