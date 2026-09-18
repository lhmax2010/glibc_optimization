#!/usr/bin/env python3
"""Public replay for full-session passive profiles; no board access."""
import argparse
import csv
import json
from pathlib import Path

from analyze_floor import historical
from analyze_persistent import FIELDS, distribution

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE/'full_session_contract.json').read_text())


def select_candidates(inventory, primary_names, observer_pid):
    stable = [p for p in inventory if p.get('status') == 'READABLE' and p['pid'] != observer_pid]
    if len({p['pid'] for p in stable}) != len(stable):
        raise ValueError('duplicate inventory PID')
    ranked = sorted(stable, key=lambda p: (-p['glibc_heap_pd_kb'], p['pid']))
    if len(ranked) < 10:
        raise ValueError('STOP fewer than ten readable userspace processes')
    selected = []
    for p in stable:
        names = [alias for alias, comm in primary_names.items() if p['comm'] == comm]
        rank = next((i+1 for i, row in enumerate(ranked[:10]) if row['pid'] == p['pid']), None)
        if names or rank:
            selected.append(dict(p, target=(names[0] if names else 'Supplemental')+'_'+str(p['pid']),
                                 primary=names, top10_rank=rank))
    return sorted(selected, key=lambda p: p['pid'])


def analyze(rows, candidates, batches, events):
    if len(batches) < 2 or [b['sample'] for b in batches] != list(range(len(batches))):
        raise ValueError('STOP incomplete batch sequence')
    for key in ('board_epoch_ns', 'host_monotonic_ns'):
        if batches[-1][key]-batches[0][key] < 600_000_000_000:
            raise ValueError('STOP less than 600s sampling')
        if any(b[key] <= a[key] for a,b in zip(batches,batches[1:])):
            raise ValueError('STOP nonmonotonic batch clock')
    if len({c['pid'] for c in candidates}) != len(candidates) or not candidates:
        raise ValueError('STOP invalid candidate roster')
    groups = historical.group_by(rows, 'target')
    if set(groups)-{c['target'] for c in candidates}:
        raise ValueError('STOP unknown target')
    retired = {}
    for event in events:
        if event['target'] in retired or event['target'] not in {c['target'] for c in candidates}:
            raise ValueError('STOP duplicate/unknown disappearance')
        if not 0 <= event['sample'] < len(batches) or event['reason'] not in ('MISSING', 'REPLACED'):
            raise ValueError('STOP invalid disappearance')
        retired[event['target']] = event
    results = []
    for c in candidates:
        s = groups.get(c['target'], [])
        limit = retired.get(c['target'], {}).get('sample', len(batches))
        if [r['sample'] for r in s] != list(range(limit)):
            raise ValueError('STOP missing/duplicate target samples')
        for r in s:
            if set(r) != set(FIELDS) or any(type(v) is not int or v < 0 for k,v in r.items() if k != 'target'):
                raise ValueError('STOP invalid row schema')
            if (r['pid'], r['start_ticks']) != (c['pid'], c['start_ticks']):
                raise ValueError('STOP changed process identity')
            if r['total_pd_kb'] != sum(r[k] for k in ('glibc_heap_pd_kb','other_anon_pd_kb','file_backed_pd_kb')):
                raise ValueError('STOP PD sum')
            if r['board_end_ns'] < r['epoch_ns'] or r['host_end_monotonic_ns'] < r['host_monotonic_ns']:
                raise ValueError('STOP reversed read')
            if not batch_global_order(r):
                raise ValueError('STOP reversed/stale global read')
            batch = batches[r['sample']]
            if not batch['board_epoch_ns'] <= r['epoch_ns'] <= r['board_end_ns'] <= batch['board_end_ns']:
                raise ValueError('STOP read outside batch')
            for key in ('MemAvailable_kb','zram_used_kb','zram_orig_bytes','zram_compr_bytes','zram_mem_used_bytes'):
                if r[key] != batch[key]:
                    raise ValueError('STOP inconsistent globals')
        for a,b in zip(s,s[1:]):
            if b['epoch_ns'] <= a['epoch_ns'] or b['host_monotonic_ns'] <= a['host_monotonic_ns'] or any(b[k] < a[k] for k in ('minflt','majflt')):
                raise ValueError('STOP clock/fault regression')
            if b['globals_start_ns'] <= a['globals_start_ns'] or b['globals_start_ns'] < a['globals_end_ns']:
                raise ValueError('STOP global reads stale/overlap')
        complete = c['target'] not in retired
        if complete and any(s[-1][k]-s[0][k] < 600_000_000_000 for k in ('epoch_ns','host_monotonic_ns')):
            raise ValueError('STOP surviving target lacks 600s coverage')
        if len(s) < 2:
            results.append(dict(target=c['target'], points=len(s), complete=False,
                                classification='NOT_EVALUATED', disappearance=retired[c['target']]))
            continue
        result = historical.release_ratio_census(s,{})[0]
        drop = historical.largest_drawdown(s)
        result.update(points=len(s), complete=complete, disappearance=retired.get(c['target']),
                      absolute_floor_kib=min(r['glibc_heap_pd_kb'] for r in s),
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
                      host_interval_ms=distribution([(b['host_monotonic_ns']-a['host_monotonic_ns'])/1e6 for a,b in zip(s,s[1:])]))
        result['floor_change_kib'] = result['last_minute_floor_kib']-result['first_minute_floor_kib']
        results.append(result)
    return dict(status='COMPLETE', nominal_points=601, actual_points=len(batches), targets=results,
                host_batch_interval_ms=distribution([(b['host_monotonic_ns']-a['host_monotonic_ns'])/1e6 for a,b in zip(batches,batches[1:])]))


def batch_global_order(row):
    return row['globals_start_ns'] <= row['globals_end_ns'] <= row['epoch_ns']


def replay(source):
    roster = json.loads((source/'candidates.json').read_text())
    candidates = roster['selected']
    inventory = json.loads((source/'inventory.json').read_text())
    if candidates != select_candidates(inventory,roster['primary_names'],roster['observer_pid']):
        raise ValueError('STOP roster not derived from inventory')
    with (source/'timeseries.tsv').open() as stream:
        rows = [{k:v if k=='target' else int(v) for k,v in r.items()} for r in csv.DictReader(stream, delimiter='\t')]
    return analyze(rows,candidates,json.loads((source/'batches.json').read_text()),json.loads((source/'events.json').read_text()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    result=replay(a.source)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS full-session replay: '+str(result['actual_points'])+' batches; '+str(len(result['targets']))+' candidates')


if __name__=='__main__':
    main()
