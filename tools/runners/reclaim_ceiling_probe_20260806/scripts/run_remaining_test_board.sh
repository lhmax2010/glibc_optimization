#!/bin/bash
set -u

SDB='<USER_HOME>/tizen-studio/tools/sdb'
SER='<TEST_BOARD_IP>:26101'
ROOT='<WORKSPACE>/board_results/reclaim_ceiling_probe_20260806/test_board'

run_one()
{
    local target=$1
    local rep=$2
    local stem=${target}_rep${rep}
    local dest=$ROOT/runs/$target/rep$rep
    local rc pull_rc driver_rc

    echo "RUN_START target=$target rep=$rep utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    rm -rf "$dest"
    mkdir -p "$dest"
    "$SDB" -s "$SER" shell "mkdir -p /root/reclaim_runs/$target; /root/test_board_measure_one.sh $target $rep >/root/reclaim_runs/$target/rep${rep}_driver.out 2>/root/reclaim_runs/$target/rep${rep}_driver.err; rc=\$?; echo \"\$rc\" >/root/reclaim_runs/$target/rep${rep}_driver.rc; exit \"\$rc\"" \
        >"$ROOT/${stem}_transport.stdout" 2>"$ROOT/${stem}_transport.stderr"
    rc=$?
    printf '%s\n' "$rc" >"$ROOT/${stem}_transport.rc"
    echo "RUN_REMOTE_DONE target=$target rep=$rep rc=$rc utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    "$SDB" -s "$SER" pull "/root/reclaim_runs/$target/rep$rep" "$dest/" \
        >"$ROOT/${stem}_pull.stdout" 2>"$ROOT/${stem}_pull.stderr"
    pull_rc=$?
    printf '%s\n' "$pull_rc" >"$ROOT/${stem}_pull.rc"
    "$SDB" -s "$SER" pull "/root/reclaim_runs/$target/rep${rep}_driver.out" "$dest/driver.out" >/dev/null 2>&1
    "$SDB" -s "$SER" pull "/root/reclaim_runs/$target/rep${rep}_driver.err" "$dest/driver.err" >/dev/null 2>&1
    "$SDB" -s "$SER" pull "/root/reclaim_runs/$target/rep${rep}_driver.rc" "$dest/driver.rc" >/dev/null 2>&1
    driver_rc=$(cat "$dest/driver.rc" 2>/dev/null || echo MISSING)
    echo "RUN_PULL_DONE target=$target rep=$rep pull_rc=$pull_rc driver_rc=$driver_rc"

    if [ "$rc" -ne 0 ] || [ "$pull_rc" -ne 0 ] || [ "$driver_rc" != 0 ]; then
        echo "RUN_ABORT target=$target rep=$rep remote_rc=$rc pull_rc=$pull_rc driver_rc=$driver_rc"
        return 1
    fi
    if [ ! -f "$dest/status.txt" ] || [ "$(cat "$dest/status.txt")" != COMPLETE ]; then
        echo "RUN_ABORT target=$target rep=$rep status_missing_or_incomplete"
        return 1
    fi
    if [ -e "$dest/failure.txt" ] || [ -e "$dest/fatal_new.txt" ]; then
        echo "RUN_ABORT target=$target rep=$rep safety_failure"
        return 1
    fi
    echo "RUN_VALID target=$target rep=$rep response_ms=$(cat "$dest/T4_response_ms.txt")"
    return 0
}

for item in AppUIB:1 AppUIB:2 AppUIB:3; do
    target=${item%:*}
    rep=${item#*:}
    run_one "$target" "$rep" || exit 1
done

echo "ALL_REMAINING_COMPLETE utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
