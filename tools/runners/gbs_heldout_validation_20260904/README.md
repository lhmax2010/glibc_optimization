# GBS held-out A-anchor validation

This prospective contract is committed and tagged before board connection. It
runs four GBS-only cells in fixed order and adjudicates every cell independently
against the already published v4 calibration interval. These observations never
enter the interval's construction sample.

```sh
bash tools/runners/gbs_heldout_validation_20260904/run_heldout_host.sh \
  --ip <TEST_BOARD_IP> \
  --output board_results/gbs_heldout_validation_20260904/workflow \
  --gbs /path/to/gbs/alloc_bench.armv7l
```

The authoritative matrix, thresholds, artifact identity, health gates, and
temporary known-alert registration are in `contract.json`. No failed or
out-of-band cell may be replaced. Complete artifacts remain in local
`board_results/`; compact rows, decision, and health records are published only
after the run.
