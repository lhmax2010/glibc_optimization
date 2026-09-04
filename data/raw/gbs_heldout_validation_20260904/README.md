# GBS held-out validation compact evidence

The prospective contract and analyzer were committed at
`1b6304c583a7ed2e03790ffe5308dabf158eb30c` and fixed by lightweight tag
`gbs-heldout-contract-20260904` before board connection. `heldout_cells.tsv` is
the four-cell compact input; `decision.json` is its v4 closed-interval decision.
`health.json`, the preflight records, controller log, governor/zram snapshots,
and final stability classification retain the compact identity and health chain.

Rebuild the two derived files with:

```sh
tmp=$(mktemp -d)
python3 tools/runners/gbs_heldout_validation_20260904/analyze_heldout.py \
  --replay data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv --output "$tmp"
cmp "$tmp/heldout_cells.tsv" data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv
cmp "$tmp/decision.json" data/raw/gbs_heldout_validation_20260904/decision.json
```

Expected output: `replayed cells=4 verdict=PASS passed=4/4`; both comparisons
are silent. Complete XML, JSON, one-second time series, commands, pulled file
manifests, and livedump archives remain in local `board_results/` and are
available on request.
