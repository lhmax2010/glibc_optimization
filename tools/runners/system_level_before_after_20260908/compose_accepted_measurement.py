#!/usr/bin/env python3
"""Compose PM-accepted immutable 18+3 observations after separate cleanup proof.

Never rewrite the historical STOP receipts or widen publish_measurement's gate.
This is a host-only composition of two execution epochs and delayed cleanup.
"""
import argparse
import json
import pathlib
import tempfile

from publish_measurement import verified_manifest,digest,ANALYSIS
from publish_execution_log import no_symlink
from replay_compact import CONTRACT,replay,derive_rows
from analyze_directory_disposition import replay as cleanup_replay,require

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PUBLIC=ROOT/'data/raw/system_level_before_after_20260908'
RECEIPTS=('5cc81666216b4ee204f0cf5171ac8af0dc7655992b66bc0dd399145c4f64c61c',
          '373282a0a93179a8f8563dd3a6889a6a9e6277df8d1149e49ada334e97711886')
DERIVED=('cycles.tsv','summary.tsv','gst_repetitions.tsv','gst_arms.tsv','gst_comparison.json')


def compose(prefix_run,g4_run,cleanup,output):
    paths=[pathlib.Path(p).absolute() for p in (prefix_run,g4_run,cleanup,output)]
    prefix_run,g4_run,cleanup,output=paths
    for path in paths:
        no_symlink(path)
        require('..' not in path.parts,'parent traversal')
    require(not output.exists(),'composition output must be new')
    require(all(output!=p and output not in p.parents and p not in output.parents for p in paths[:-1]),'overlapping output')
    validation=cleanup_replay(cleanup)
    require(validation['source_execution_sha256']==RECEIPTS[1],'cleanup belongs to wrong G4')
    receipts=[json.loads((p/'execution.json').read_text()) for p in (prefix_run,g4_run)]
    for index,p in enumerate((prefix_run,g4_run)):
        require(digest(p/'execution.json')==RECEIPTS[index],'accepted execution receipt changed')
    original18=json.loads((PUBLIC/'completed_prefix/completed_points.json').read_text())
    original3=json.loads((PUBLIC/'g4_authorized_20260910/observations/g4_points.json').read_text())
    cells18=[c for c in CONTRACT['cells'] if c['group']!='G4']
    cells3=[c for c in CONTRACT['cells'] if c['group']=='G4']
    require([c['id'] for c in cells18]==receipts[0]['completed_cells'],'wrong accepted prefix')
    require([c['id'] for c in cells3]==receipts[1]['completed_cells'],'wrong accepted G4')
    require(all(r['verdict']=='STOP' for r in receipts),'historical STOP must remain intact')
    source=dict(schema='system-before-after.accepted-composition.v1',contract_tag=CONTRACT['contract_tag'],
        scope='PM-accepted immutable 18+3; separate execution epochs and delayed cleanup, not an uninterrupted run',
        points=[],cell_health={},pull_manifests={})
    rows=[]
    for run,cells,old in ((prefix_run,cells18,original18),(g4_run,cells3,original3)):
        raw=run/'raw'
        rows.extend(ANALYSIS.analyze(raw,{**CONTRACT,'cells':cells}))
        old_points={(x['id'],x['metric']['cycle']):x for x in old['points']}
        for cell in cells:
            name=cell['id'];path=raw/name
            manifest=verified_manifest(run,raw,name)
            require(manifest==old['pull_manifests'][name],'old public pull proof mismatch')
            source['pull_manifests'][name]=manifest
            meta=json.loads((path/'cell.json').read_text())
            require(meta==old['cell_health'][name],'old public cell health mismatch')
            source['cell_health'][name]=meta
            for metric in json.loads((path/'metrics.json').read_text()):
                entry=dict(id=name,cycle=metric['cycle'],metric=metric,raw_point_sha256={})
                for phase in ('pre','post'):
                    point=path/'points'/('%02d_%s'%(metric['cycle'],phase))
                    entry[phase]=ANALYSIS.read_point(point)
                    entry['raw_point_sha256'][phase]={p.name:digest(p) for p in sorted(point.iterdir()) if p.is_file()}
                if cell['group']=='G4':
                    entry['idle_pre']=ANALYSIS.proc_stat((path/'idle_stat_start.txt').read_text())
                    entry['idle_post']=ANALYSIS.proc_stat((path/'idle_stat_end.txt').read_text())
                published=old_points[(name,metric['cycle'])]
                require(all(entry[k]==v for k,v in published.items()),'accepted public point differs from raw: '+name)
                source['points'].append(entry)
    require(rows==derive_rows(source) and len(rows)==333,'raw/compact composition mismatch')
    summary=ANALYSIS.summarize(rows)
    gst_rows=[]
    original=ANALYSIS.GST.derive_cycle_summaries
    def capture(values):
        gst_rows.extend(values)
        return original(values)
    ANALYSIS.GST.derive_cycle_summaries=capture
    try:
        repetitions,arms,comparison=ANALYSIS.gst_summaries(prefix_run/'raw',rows)
    finally:
        ANALYSIS.GST.derive_cycle_summaries=original
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.accepted-composition-',dir=output.parent) as tmp:
        stage=pathlib.Path(tmp)/'public';stage.mkdir()
        (stage/'point_source.json').write_text(json.dumps(source,indent=2,allow_nan=False)+'\n')
        ANALYSIS.write_tsv(stage/'cycles.tsv',rows)
        ANALYSIS.write_tsv(stage/'summary.tsv',summary)
        ANALYSIS.GST.write_tsv(stage/'gst_cycles.tsv',gst_rows)
        ANALYSIS.GST.write_tsv(stage/'gst_repetitions.tsv',repetitions)
        ANALYSIS.GST.write_tsv(stage/'gst_arms.tsv',arms)
        (stage/'gst_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
        rebuilt=pathlib.Path(tmp)/'replay'
        replay(source,stage/'gst_cycles.tsv',rebuilt)
        for name in DERIVED:
            require((stage/name).read_bytes()==(rebuilt/name).read_bytes(),'full/compact byte mismatch '+name)
        for index,(run,cells) in enumerate(((prefix_run,cells18),(g4_run,cells3))):
            require(digest(run/'execution.json')==RECEIPTS[index],'receipt changed during composition')
            for cell in cells:
                require(verified_manifest(run,run/'raw',cell['id'])==source['pull_manifests'][cell['id']],
                    'raw proof changed during composition')
        require(cleanup_replay(cleanup)==validation,'cleanup evidence changed during composition')
        composition=dict(schema='system-before-after.accepted-composition-receipt.v1',
            verdict='PASS_ACCEPTED_MATRIX_WITH_DELAYED_CLEANUP',
            contract_tag=CONTRACT['contract_tag'],contract_tag_object=receipts[0]['tag_object'],
            execution_sha256=list(RECEIPTS),historical_execution_verdicts=['STOP','STOP'],
            execution_epochs=[dict(start_utc=r['start_utc'],end_utc=r['end_utc'],cells=r['completed_cells']) for r in receipts],
            acceptance=dict(approved_by='PM',decision_date='2026-09-10',rule='preserve accepted 21; never rerun'),
            cleanup=validation,cleanup_audit_sha256=digest(cleanup/'audit.json'),
            completed_cells=[c['id'] for c in CONTRACT['cells']],cycles=len(rows),gst_cycles=len(gst_rows),
            cmp_files=list(DERIVED),original_raw_policy='complete originals retained locally; available on request')
        (stage/'composition.json').write_text(json.dumps(composition,indent=2)+'\n')
        (stage/'manifest.json').write_text(json.dumps(dict(schema='system-before-after.composed-files.v1',
            files=[dict(path=p.name,sha256=digest(p),bytes=p.stat().st_size) for p in sorted(stage.iterdir())]),indent=2)+'\n')
        stage.rename(output)
    print('PASS accepted composition cells=21 cycles=333 cmp=5 historical_STOP_preserved cleanup=PASS_WITH_NONEMPTY_REPORT_ONLY')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix-run',type=pathlib.Path,required=True)
    p.add_argument('--g4-run',type=pathlib.Path,required=True)
    p.add_argument('--cleanup',type=pathlib.Path,required=True)
    p.add_argument('--output-dir',type=pathlib.Path,required=True)
    a=p.parse_args()
    compose(a.prefix_run,a.g4_run,a.cleanup,a.output_dir)


if __name__=='__main__':
    main()
