# Tizen native evidence B2 runner

This directory contains the 2026-09-04 B2 fixed-contract replay, read-only reconnaissance
scripts, the official-snapshot GDB package helper, formal board controller,
host analyzer, and host tests for the dated append in
`docs/tizen_native_evidence_20260904.md`.

The original run had no independent pre-run commit/tag. Its date and evidence-level
wording were corrected from the raw nanosecond timestamps; the measured machine
evidence is unchanged. The current replay contract and scripts consistently use the
2026-09-04 round/workdir. The exact hashes of the contract and runner that executed
remain recorded as `executed_*_sha256` in the public `run_record.txt` and can be
recovered from Git commit `a35413df78f22d68d9eaac2ea59e807005c7f2c2`.

The workflow is intentionally split:

1. Pass the three-part identity gate and the exact glibc/MemTotal/root gates.
2. Run `recon_idle_remote.sh` over SDB stdin so the 60-second idle probe creates
   no board file.
3. Confirm the six-package set is initially absent, then install the SHA-pinned
   official GDB dependencies with
   `manage_gdb_official_snapshot.sh`; the helper enforces the 1.2 GiB root-space
   floor.
4. Validate attach only against the round-owned `alloc_bench` with
   `recon_gdb_selftest_remote.sh`.
5. Prove the five-process decode construction and the selected 30-second UI app
   lifecycle with `recon_gst_sequence_remote.sh` and `recon_app_remote.sh`.
6. Inspect `fixed_contract.json`, then run `run_b2_remote.sh` without
   overrides.
7. Build a board-side file manifest, pull and verify every entry, remove the GDB
   package set, delete only the exact round directory, and recheck governors,
   packages, processes, and paths.

The formal controller executes five sequential official `gst-launch-1.0`
processes. Each is injected once; consecutive injection-start timestamps must be
at least 120,000,000,000 ns apart. It then starts, holds for 30 seconds, and
stops `setting-myaccount-efl` five times before one enlightenment M7/trim cell.
E1–E3 are not rerun.

Full copyable commands, asset hashes, package NVRs, acceptance interpretation,
and cleanup are in the
[HQ L2 B2 guide](../../../docs/demo_reproduction_guide_20260901.md#l2-tizen-native-evidence-b2).
Host checks and analysis are:

```sh
python3 tools/runners/tizen_native_evidence_b2_20260904/test_host.py
python3 tools/runners/tizen_native_evidence_b2_20260904/analyze_b2.py \
  --pull <complete-board-pull> --idle-log <idle-60s-raw-log> \
  --output <derived-output>
```

The reclaim values and GDB durations are observations, not tolerance bands.
GDB duration includes ptrace. Exact gates cover identity, parseability,
PID/starttime stability, project/memps equality, buffer progress, the 120-second
interval, health, and cleanup.
