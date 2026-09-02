# GStreamer trim-cost compact evidence (2026-09-01)

This directory contains the sanitized, compact outputs of the frozen six-cell
board matrix documented in
[`docs/gst_trim_cost_20260901.md`](../../../docs/gst_trim_cost_20260901.md).
Application/process names are aliases and the board address is represented as
`<TEST_BOARD_IP>`.

- `cycles.tsv`: all 306 cycle records, including business time, trim time,
  pre/post glibc heap PD, reclaim, faults, and repeated cell-level sampler/exit
  metadata. The repeated fields make this the sole input needed to reproduce the
  three statistical derivatives below.
- `repetitions.tsv`: per-cell nearest-rank percentiles and repeat summaries.
- `arm_summary.tsv`: median-of-repeat statistics and repeat ranges by arm.
- `external_summary.tsv`: counts, overruns, and full-run faults for the six
  independent one-second series.
- `comparison.json`: the preregistered p99 visibility decision.
- `health.json`: dmesg, zram, governor, and capture-metadata quality status.
- `dmesg_increment.txt`: empty because the captured dmesg increment was zero
  lines.
- `preflight_and_integrity.txt`: sanitized identity, capability, asset,
  execution, pull, and cleanup evidence.

The complete 1 s series, profile JSON, PIDs, full dmesg snapshots, media, and
ARM binaries remain only in the private local `board_results/` archive. Rebuild
the compact tables with
[`analyze_gst_trim_cost.py`](../../../tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py)
after pulling a complete manifest-backed board directory.

Alternatively, rebuild `repetitions.tsv`, `arm_summary.tsv`, and
`comparison.json` from this public directory alone:

```sh
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --replay-cycles data/raw/gst_trim_cost_20260901/cycles.tsv \
  --output /tmp/gst-trim-cost-replay
```
