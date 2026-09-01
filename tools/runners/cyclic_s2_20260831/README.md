# Cyclic S2 2026-08-31 harness

This directory publishes the executable harness used for the frozen S2 run.
It contains no board result payloads and no live board address. Complete raw
results remain in the private local `board_results/` archive.

## Files

- `preflight_gate.sh`: host-side identity and environment gate. Every remote
  command emits `RC=` plus a `DONE_`/`FAIL_` marker; the script does not trust
  the SDB process exit code.
- `run_s2_remote.sh`: board-side controller. It verifies identity and binary
  SHA-256, requires all four governors to start at `schedutil`, changes them to
  `performance`, runs the two frozen profiles, and restores all governors to
  `schedutil` through an exit trap.
- `sample_smaps_1s.sh`: board-side 1 s external sampler using the same glibc
  heap / other-anon / file-backed classification as the product probes. Zero
  samples and stat/smaps parse failures return nonzero with an explicit FAIL
  marker.
- `analyze_s2.py`: host parser for the two JSON files and external sequences;
  it validates cycles `1..8`, sample order, elapsed-time order, and PID
  stability before deriving results.
- `test_host.py`: host-only regression tests for failed sampling, normal
  target exit, cycle ordering, duplicate cycles, and PID drift.

The private archive preserves the byte-identical 2026-08-31 execution copies.
Before publication, the reusable copies here were hardened to close fail-open
sampling, non-`schedutil` initial-state, and unordered-cycle cases; the frozen
workload and smaps classification are unchanged. Historical execution hashes
are:

```text
94b10919bff96a6971f633167e479fb9ebdf10dd8d68110a9b21d2780977f897  run_s2_remote.sh
a058448caff556fdf858fb81302fa96ce4316cdf412425bf8d15a769a432323e  sample_smaps_1s.sh
```

The hardened publication hashes are:

```text
4288f86c667b78fb067aedca2a2cec43a3de6900adaf61dcbe2c738a65aae307  run_s2_remote.sh
e484edb54951f835096452097f760d72e0433212d96a5561a3778a16fc9e8e5e  sample_smaps_1s.sh
9b8950f9593760173f25dc96c903aeba7cbfcbe2f03bcbfe141925de3e3bb8fe  analyze_s2.py
```

The hardened analyzer still reproduces all three archived derived outputs
byte-for-byte on the valid S2 pull.

## Frozen workload

Both `mixed` and `medium-only` use exactly:

```text
--threads 4 --seed 20260814 --live-set 512 --idle-release 50
--release-order high --touch-full --cycles 8 --cycle-rise 3.4
--cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20
--trim-at none --warmup 0
```

The controller expects `alloc_bench.armv7l` SHA-256
`dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`
and the board work directory `/opt/usr/glibc_memopt/cyclic_s2_20260831`.

## Reuse boundary

Set `SDB_SERIAL` out of band, run the preflight gate, and stop unless it prints
`IDENTITY_AND_ENV_GATE_PASS`. Uploading, executing, pulling, and deleting board
files are intentionally not wrapped into a one-command host driver: each is a
separate reviewed state transition. After a pull, derive the compact tables with:

```sh
python3 analyze_s2.py --pull PATH_TO_PULL --output PATH_TO_DERIVED
```

Run the host-only regression suite with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 test_host.py -v
```

The 2026-08-31 report remains the source of truth for manifest verification,
JSON/XML parse gates, cleanup evidence, and the final S2 decision.
