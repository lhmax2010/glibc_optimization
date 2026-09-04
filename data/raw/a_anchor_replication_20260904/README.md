# A-anchor replication compact evidence (2026-09-04)

This directory is the public, sanitized subset of the preregistered frozen/GBS
A-anchor replication. Complete JSON, XML, 1 s sampling, dmesg, command, pulled
manifest, and stability-monitor archives remain in the local `board_results`
archive and are available on request.

- [`a_cells.tsv`](a_cells.tsv): all 12 cells in execution order.
- [`group_summary.tsv`](group_summary.tsv): the four `{ELF × profile}` summaries.
- [`decision.json`](decision.json): executable H-L/H-V adjudication and v4 band values.
- [`health.json`](health.json): dmesg, zram, faults, alignment, and governor result.
- [`gbs_v4_recheck.tsv`](gbs_v4_recheck.tsv): compact v4 re-evaluation of the
  archived GBS S4+gst matrix; the complete source archive remains local.
- [`execution_gates.txt`](execution_gates.txt): sanitized identity, environment, hash,
  order, stability-monitor, and final-cleanup evidence.

Recalculate the tables and decision with:

```sh
python3 tools/runners/a_anchor_replication_20260904/analyze_a_anchor.py \
  --replay data/raw/a_anchor_replication_20260904/a_cells.tsv \
  --output /tmp/a-anchor-replay
cmp /tmp/a-anchor-replay/group_summary.tsv data/raw/a_anchor_replication_20260904/group_summary.tsv
cmp /tmp/a-anchor-replay/decision.json data/raw/a_anchor_replication_20260904/decision.json
```

Application/process names are aliases. Host-side paths are sanitized; board
runtime paths are retained. The frozen test-image BUILD_ID is intentionally
public for reproducibility.
