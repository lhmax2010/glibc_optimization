#!/usr/bin/env python3
"""Replay actual-time diskless observations; historical PD classifier unchanged."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_floor import historical

HERE = Path(__file__).resolve().parent
FIELDS = set(json.loads((HERE/'diskless_contract.json').read_text())['sampling']['fields'].split(', '))
GLOBALS = ('MemAvailable_kb', 'zram_used_kb', 'zram_orig_bytes', 'zram_compr_bytes',
           'zram_mem_used_bytes', 'globals_start_ns', 'globals_end_ns')


def distribution(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values))


def analyze(rows, expected_targets=None):
    if not rows:
        raise ValueError('STOP no candidate observations')
    results = []
    groups = historical.group_by(rows, 'target')
    if expected_targets is None:
        snapshot = HERE.parents[2]/json.loads((HERE/'diskless_contract.json').read_text())['candidates_snapshot']
        expected_targets = {r['target'] for r in json.loads(snapshot.read_text())['selected']}
    if set(groups) != set(expected_targets):
        raise ValueError('STOP candidate roster differs from frozen snapshot')
    for r in rows:
        if set(r) != FIELDS or any(type(v) is not int or v < 0 for k, v in r.items() if k != 'target'):
            raise ValueError('STOP missing/invalid required fields')
    for batch in historical.group_by(rows, 'sample').values():
        if len({tuple(r[k] for k in GLOBALS) for r in batch}) != 1:
            raise ValueError('STOP inconsistent global observations within batch')
    counts = {len(s) for s in groups.values()}
    if len(counts) != 1:
        raise ValueError('STOP incomplete candidate batch')
    for target, seq in groups.items():
        if len(seq) < 2 or [r['sample'] for r in seq] != list(range(len(seq))):
            raise ValueError('STOP missing/duplicate sample: '+target)
        if len({(r['pid'], r['start_ticks']) for r in seq}) != 1:
            raise ValueError('STOP process identity changed: '+target)
        elapsed = (seq[-1]['monotonic_ns']-seq[0]['monotonic_ns'])/1e9
        if elapsed < 600:
            raise ValueError('STOP observation shorter than 600 seconds: '+target)
        for r in seq:
            if r['total_pd_kb'] != sum(r[k] for k in ('glibc_heap_pd_kb', 'other_anon_pd_kb', 'file_backed_pd_kb')):
                raise ValueError('STOP inconsistent PD sum: '+target)
            if r['read_end_ns'] < r['monotonic_ns'] or r['globals_end_ns'] < r['globals_start_ns']:
                raise ValueError('STOP reversed read interval')
            if r['compact_smaps'] not in (0, 1):
                raise ValueError('STOP invalid compact scope flag')
        for a, b in zip(seq, seq[1:]):
            if b['monotonic_ns'] <= a['monotonic_ns'] or b['epoch_ns'] <= a['epoch_ns']:
                raise ValueError('STOP clock regressed')
            if b['globals_start_ns'] <= a['globals_end_ns']:
                raise ValueError('STOP global reads stale/overlap across batches')
            if any(b[k] < a[k] for k in ('minflt', 'majflt', 'compact_smaps')):
                raise ValueError('STOP faults regressed or compact mode reverted')
        first = seq[0]['monotonic_ns']
        last = seq[-1]['monotonic_ns']
        result = historical.release_ratio_census(seq, {})[0]
        drop = historical.largest_drawdown(seq)
        result.update(
            absolute_floor_kib=min(r['glibc_heap_pd_kb'] for r in seq),
            absolute_peak_kib=max(r['glibc_heap_pd_kb'] for r in seq),
            first_minute_floor_kib=min(r['glibc_heap_pd_kb'] for r in seq if r['monotonic_ns'] < first+60e9),
            last_minute_floor_kib=min(r['glibc_heap_pd_kb'] for r in seq if r['monotonic_ns'] > last-60e9),
            window_minflt_delta=seq[-1]['minflt']-seq[0]['minflt'],
            window_majflt_delta=seq[-1]['majflt']-seq[0]['majflt'],
            zram_positive_steps=sum(b['zram_orig_bytes'] > a['zram_orig_bytes'] for a, b in zip(seq, seq[1:])),
            zram_orig_window_delta_bytes=seq[-1]['zram_orig_bytes']-seq[0]['zram_orig_bytes'],
            drawdown_total_pd_delta_kib=drop['trough']['total_pd_kb']-drop['peak']['total_pd_kb'],
            drawdown_other_anon_delta_kib=drop['trough']['other_anon_pd_kb']-drop['peak']['other_anon_pd_kb'],
            elapsed_s=elapsed, compact_smaps_samples=sum(r['compact_smaps'] for r in seq),
            actual_interval_ms=distribution([(b['monotonic_ns']-a['monotonic_ns'])/1e6 for a, b in zip(seq, seq[1:])]),
            smaps_read_ms=distribution([(r['read_end_ns']-r['monotonic_ns'])/1e6 for r in seq]),
            global_start_skew_ms=distribution([(r['globals_start_ns']-r['monotonic_ns'])/1e6 for r in seq]),
        )
        result['floor_change_kib'] = result['last_minute_floor_kib']-result['first_minute_floor_kib']
        results.append(result)
    return results


def validate_timing(rows, timing):
    batches = timing['batches']
    grouped = historical.group_by(rows, 'sample')
    if len(batches) != len(grouped):
        raise ValueError('STOP timing batch count mismatch')
    period, transition = 1, None
    for i, batch in enumerate(batches):
        if batch['sample'] != i or batch['target_period_s'] != period or batch['end_ns'] < batch['start_ns']:
            raise ValueError('STOP invalid timing/target period')
        if i and (batch['start_ns'] < batches[i-1]['end_ns'] or
                  batch['start_ns'] < batches[i-1]['start_ns']+period*1e9):
            raise ValueError('STOP overlapping/burst batch')
        for r in grouped[str(i)]:
            if not (batch['start_ns'] <= r['monotonic_ns'] <= r['read_end_ns'] <= batch['end_ns'] and
                    batch['start_ns'] <= r['globals_start_ns'] <= r['globals_end_ns'] <= batch['end_ns']):
                raise ValueError('STOP read outside its batch')
        if period == 1 and i >= 10:
            median = statistics.median((b['start_ns']-a['start_ns'])/1e9
                                      for a, b in zip(batches[i-10:i], batches[i-9:i+1]))
            if median > 1.5:
                period = 2
                transition = dict(after_sample=i, median_previous_10_intervals_s=median,
                                  from_period_s=1, to_period_s=2)
    if timing['transition'] != transition:
        raise ValueError('STOP cadence transition proof differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeseries', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timing', type=Path, required=True)
    args = parser.parse_args()
    with args.timeseries.open() as stream:
        rows = [{k: v if k == 'target' else int(v) for k, v in r.items()}
                for r in csv.DictReader(stream, delimiter='\t')]
    result = analyze(rows)
    validate_timing(rows, json.loads(args.timing.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('PASS diskless product-floor replay: '+str(len(result))+' candidates')


if __name__ == '__main__':
    main()
