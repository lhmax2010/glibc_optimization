# GStreamer trim-cost harness (2026-09-01)

This directory is the executable contract for the frozen two-arm, three-repeat
GStreamer loop-release experiment in
[`docs/gst_trim_cost_20260901.md`](../../../docs/gst_trim_cost_20260901.md).

Files:

- `preflight_gate.sh`: read-only SDB identity/environment gate.
- `capability_probe.sh`: read-only GStreamer plugin/package and filesystem probe.
- `build_armv7l.sh`: host-only cross-build wrapper for the instrumented target.
- `run_gst_trim_cost_remote.sh`: board controller with the frozen ABBAAB order,
  per-cycle handshake captures, health evidence, and governor restore trap.
- `sample_smaps_1s.sh`: S2/S4-compatible external one-second sampler.
- `analyze_gst_trim_cost.py`: mandatory integrity and result validator.
- `test_host.py`: host-only regression tests; it never invokes SDB.

The controller expects these board assets in the fixed work directory:

- `gst_loop_decode.armv7l` SHA-256
  `204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6`
- `reclaim_probe.armv7l` SHA-256
  `3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7`
- `small_320x240.mp4` SHA-256
  `3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d`

Host analysis after pulling the complete directory:

```sh
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --pull board_results/gst_trim_cost_20260901/board_pull \
  --output board_results/gst_trim_cost_20260901/derived
```

Host-only replay from the public compact cycle table requires no private board
archive and writes only the three mathematical derivatives used by the Demo:

```sh
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --replay-cycles data/raw/gst_trim_cost_20260901/cycles.tsv \
  --output /tmp/gst-trim-cost-replay
cmp /tmp/gst-trim-cost-replay/repetitions.tsv \
  data/raw/gst_trim_cost_20260901/repetitions.tsv
cmp /tmp/gst-trim-cost-replay/arm_summary.tsv \
  data/raw/gst_trim_cost_20260901/arm_summary.tsv
cmp /tmp/gst-trim-cost-replay/comparison.json \
  data/raw/gst_trim_cost_20260901/comparison.json
```

`cycles.tsv` repeats the cell-level external sample count, sampler overrun count,
and exit code on every cycle row. This deliberate redundancy makes the compact
table a self-contained replay input; the replay path reads no other evidence file.

Rebuild with a glibc-2.40 GCC 14.2 scratch root and a compatible armv7l
GStreamer sysroot (the two roots may be different):

```sh
TOOLCHAIN_ROOT=/path/to/toolchain/scratch.armv7l.0 \
GST_SYSROOT=/path/to/gstreamer/scratch.armv7l.0 \
  tools/runners/gst_trim_cost_20260901/build_armv7l.sh \
  /tmp/gst_loop_decode.armv7l
```

The known build's source and binary hashes are the values above. A different
binary hash is a new build batch and must be recorded as such; it does not make
the experiment invalid if the source, compiler, ABI, and runtime gates match.

The complete `board_results/` tree remains local. Only compact derived tables and
sanitized command/health evidence are published under `data/raw/`.

The executed 2026-09-01 controller batch had one explicitly preserved metadata
defect: POSIX sh `$10` expanded as `$1` plus `0`, so the auxiliary capture-point
`majflt` field was `S0`. The controller in this directory uses `${10}`. The
analyzer accepts the historical batch only when all 306 pre/post pairs carry
that exact marker and labels the field unavailable; numeric per-cycle
`getrusage` and independent one-second `/proc/stat` majflt remain mandatory.
