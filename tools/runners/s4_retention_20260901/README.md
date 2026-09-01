# S4 reference and retention-trim harness (2026-09-01)

This directory is the executable contract for the two A reference cells and
eight B retention/trim cells. The workload parameters are frozen in
`run_s4_remote.sh`; do not edit them after seeing results.

Artifacts:

- `preflight_gate.sh`: read-only identity and environment gate. Every remote
  command emits `RC=` plus an explicit `DONE_`/`FAIL_` marker.
- `run_s4_remote.sh`: board controller with a four-core governor trap,
  before/after zram and dmesg capture, fixed A/B commands, and per-cell 1 s
  smaps sampling.
- `sample_smaps_1s.sh`: the S2/product-compatible glibc heap PD versus
  other-anon classifier.
- `medium_1k_16k.hist`: exact historical medium-only distribution
  (`sha256=2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b`).
- `analyze_s4.py`: mandatory manifest/size, JSON/XML, exact sampler metadata,
  trim-sentinel and external-series validation plus compact metric derivation.
- `test_host.py`: host-only regression tests; it never opens an sdb channel.

The fixed board work path is
`/opt/usr/glibc_memopt/s4_retention_20260901`. The required bench is the S2
artifact with SHA-256
`dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`.
The controller refuses a different binary or histogram, requires the exact
LLVM image identity/glibc baseline, requires all four governors to start at
`schedutil`, switches them to `performance`, and restores all four to
`schedutil` on every trapped exit.

Host-side validation after pulling the whole work directory:

```sh
python3 tools/runners/s4_retention_20260901/analyze_s4.py \
  --pull board_results/s4_retention_20260901/board_pull \
  --output board_results/s4_retention_20260901/derived
```

The complete `board_results/` tree remains local. Only the compact derived
tables and health summary are copied into `data/raw/` after redaction.
