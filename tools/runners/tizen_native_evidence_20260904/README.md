# Tizen native evidence runner

This directory preserves the preregistered contract, board controller, official
snapshot GDB package helper, host analyzer, and host tests for
`docs/tizen_native_evidence_20260904.md`.

The published execution is deliberately incomplete: the frozen T1 pipeline
reached EOS at 60.100233983 seconds after one of five cells, and the selected UI
application exited before the first terminate command. The analyzer requires the
exact completed sequence `T1_1,T2_E1,T2_E2,T2_E3`; it does not turn these stops
into passing cells.

## Inputs

- RPI4 with the exact BUILD_ID and glibc NVR in `preregistered_contract.json`.
- `small_320x240.mp4` supplied out of repository and verified as
  `3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d`.
- SDB access as root. Every remote command must be accepted only through its
  `RC=0` plus matching `DONE_*` marker.

## GDB install and removal

The helper fetches only the six SHA-pinned ARM RPMs from the official Base
Toolchain `20260813.050338` snapshot. It refuses installation unless subtracting
their 53,010,679-byte installed size leaves at least 1.2 GiB on `/`.

```sh
sh tools/runners/tizen_native_evidence_20260904/manage_gdb_official_snapshot.sh \
  install --ip <addr> --cache <host-cache>

sh tools/runners/tizen_native_evidence_20260904/manage_gdb_official_snapshot.sh \
  remove --ip <addr>
```

The second command is the required teardown; the report records the equivalent
raw `rpm -e --test` and `rpm -e` package list.

## Board execution

After the identity/environment gates, create only the exact work directory and
push the media, `run_native_evidence_remote.sh`, and
`../../reclaim_probe/trim_via_gdb.sh`. Run the controller without overrides for
T1. Preserve its failed exit and pull it as `<T1-board-pull>`. Once the recorded
EOS is confirmed, run the independent T2 phase as follows and pull it as
`<T2-board-pull>`:

```sh
sdb -s <addr>:26101 shell \
  'NATIVE_PHASE=t2 /opt/usr/glibc_memopt/tizen_native_evidence_20260904/run_native_evidence_remote.sh; rc=$?; echo RC=$rc; [ $rc -eq 0 ] && echo DONE_FORMAL_T2_INVOKE || echo FAIL_FORMAL_T2_INVOKE'

python3 tools/runners/tizen_native_evidence_20260904/analyze_native_evidence.py \
  --t1-pull <T1-board-pull> --pull <T2-board-pull> --output <derived-dir>
```

The board controller traps EXIT/HUP/INT/TERM and restores all four governors to
`schedutil`. After pulling and hashing every file, remove the six GDB packages,
delete only `/opt/usr/glibc_memopt/tizen_native_evidence_20260904`, remove the
parent only if empty, and verify no round process remains.

## Acceptance interpretation

Deterministic/validity checks are exact identities and asset SHA, parseable
TSV/XML, stable PID plus starttime, `memps [heap]` equal to the project main-heap
value, zero majflt/zram/OOM-LMK/new-alert deltas, and clean teardown. There is no
reclaim or GDB-injection latency tolerance band: native daemon state is not fixed,
and ptrace latency is not hook cost. The published incomplete counts and two
sub-120-second intervals must remain `INCOMPLETE/PROTOCOL-DEVIATION`, not PASS.

Run host checks with:

```sh
python3 tools/runners/tizen_native_evidence_20260904/test_host.py
```
