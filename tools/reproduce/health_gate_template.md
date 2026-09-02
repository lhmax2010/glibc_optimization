> Public archive note: application/process names are aliases. Board identifiers,
> image delivery paths, and local filesystem paths are sanitized.

# Board-run health gate template (v2)

This template is the reporting contract for every board run after 2026-09-02. The
machine-readable source of truth is
[`acceptance_bands.json`](acceptance_bands.json). Record the pre/post lists before
classifying any new stability-monitor artifact.

## Required health evidence

| Item | Before | After | Delta | Attribution | Verdict |
|---|---|---|---|---|---|
| stability-monitor exact paths/count |  |  |  |  |  |
| zram `original/compressed/mem_used_total` |  |  |  | n/a |  |
| dmesg OOM/LMK matches |  |  |  | n/a |  |
| governor (`cpu0`–`cpu3`) |  |  |  | n/a |  |
| work directory and test processes |  |  |  |  |  |

An attributable alert that is not preregistered is `FAIL`. A foreign or
unattributed alert is `REPORT_ONLY` and must not be altered. A preregistered alert
is `EXPECTED` only when its reason, workload window, binary and count all match;
it must still be recorded, archived, removed by exact path, and rechecked.

## Preregistered expected alerts

| ID | Trigger / owner | Registered window | Upper bound | Disposition | Matched verdict |
|---|---|---|---:|---|---|
| `s4-a-alloc-bench-cpu-relative` | `cpu.relative` / `alloc_bench.armv7l` | `A/mixed/rep1`, `A/medium-only/rep1` | 2 total | record → archive → exact cleanup → recheck | `EXPECTED` |

These livedumps are benign monitoring artifacts, not hook-cost measurements. A
different trigger, binary, window, or a third matching file is not covered by the
registration.

## Archive and exact cleanup pattern

Never delete a glob. Resolve each new path, pull it, verify its hash and metadata,
then delete that exact path only. Replace the placeholders below with the paths
already recorded in the run evidence.

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
export ALERT_REMOTE='/opt/usr/share/crash/livedump/<exact-file>.zip'
export ALERT_ARCHIVE='board_results/<round>/stability-monitor'
mkdir -p "$ALERT_ARCHIVE"
sdb -s "$SDB_SERIAL" shell "sha256sum '$ALERT_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_ALERT_HASH || echo FAIL_ALERT_HASH" \
  | tee "$ALERT_ARCHIVE/remote_sha256.txt"
sdb -s "$SDB_SERIAL" pull "$ALERT_REMOTE" "$ALERT_ARCHIVE/"
sha256sum "$ALERT_ARCHIVE/<exact-file>.zip" | tee "$ALERT_ARCHIVE/host_sha256.txt"
unzip -p "$ALERT_ARCHIVE/<exact-file>.zip" dump_reason | tee "$ALERT_ARCHIVE/dump_reason.txt"
unzip -p "$ALERT_ARCHIVE/<exact-file>.zip" info.json | tee "$ALERT_ARCHIVE/info.json"
sdb -s "$SDB_SERIAL" shell "test '$ALERT_REMOTE' = '/opt/usr/share/crash/livedump/<exact-file>.zip' && rm -f '$ALERT_REMOTE' && test ! -e '$ALERT_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_EXPECTED_ALERT_CLEANUP || echo FAIL_EXPECTED_ALERT_CLEANUP"
```

The report must retain the exact remote/host SHA comparison, parsed trigger,
executable path, PID/window attribution, count against the registered upper bound,
cleanup marker, and post-cleanup absence check.
