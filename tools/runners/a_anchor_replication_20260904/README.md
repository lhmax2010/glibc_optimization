# A-anchor replication harness (2026-09-04)

This harness executes the fixed-contract 12-cell frozen/GBS A-anchor matrix. The
authoritative order, thresholds, prior observations, and temporary
stability-monitor registration are in `fixed_contract.json`.

```sh
bash tools/runners/a_anchor_replication_20260904/run_a_anchor_host.sh \
  --ip <TEST_BOARD_IP> \
  --output board_results/a_anchor_replication_20260904/workflow \
  --frozen /path/to/frozen/alloc_bench.armv7l \
  --gbs /path/to/gbs/alloc_bench.armv7l
```

The host runner performs the identity/environment gates, verifies both ELF
hashes before and after push, records and restores the governor, archives and
cleans registered stability alerts, validates the pulled manifest, and runs
`analyze_a_anchor.py`. Complete board artifacts remain under `board_results/`;
only the compact derived evidence is eligible for `data/raw/` publication.

The official run matched the H-V branch. Rebuild its group table and decision
from the compact public rows without board access:

```sh
tmp=$(mktemp -d)
python3 tools/runners/a_anchor_replication_20260904/analyze_a_anchor.py \
  --replay data/raw/a_anchor_replication_20260904/a_cells.tsv \
  --output "$tmp"
cmp "$tmp/group_summary.tsv" data/raw/a_anchor_replication_20260904/group_summary.tsv
cmp "$tmp/decision.json" data/raw/a_anchor_replication_20260904/decision.json
```

Expected final line: `replayed cells=12 verdict=H-V`; both `cmp` commands are
silent. The resulting v4 common A-anchor bands are mixed
`52.794499% ±4.304705 pp` and medium-only `50.669791% ±4.918088 pp`, with eight
combined observations per profile.
