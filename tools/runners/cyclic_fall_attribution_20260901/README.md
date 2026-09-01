# Cyclic fall attribution 2026-09-01

Host-only analyzers for the F2/F3 audit and product phenotype census. Neither
script opens a board connection or mutates the source raw data.

Recompute F2/F3:

```sh
python3 analyze_attribution.py \
  --timeseries ../../../data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv \
  --keys ../../../data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv \
  --published-analyzer ../product_cyclic_target_probe_20260814/analyze_cyclic.py \
  --output OUTPUT_DIR
```

Recompute the definition audit and two ten-target tables from repository root:

```sh
python3 tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py \
  --repo-root . \
  --output OUTPUT_DIR
```

The release-ratio classifier reads the compact alias-only S1 baselines under
`data/raw/cyclic_fall_attribution_20260901/`; it falls back to the first sample
only for a PID created after S1. Frozen material-response gates remain 10% for
release-ratio and 5% for plateau. The ServiceA residual is derived from the P0
floor and the final fixed wall-clock round valley; the wall-clock origin is
reconstructed independently from `key_timeline.tsv`.

Run the host-only branch tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 test_host.py -v
```
