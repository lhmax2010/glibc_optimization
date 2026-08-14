#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel" in
    *rpi4*) ;;
    *) echo "IDENTITY_ABORT_NOT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
case "$os_release" in
    *unified-dev*) ;;
    *) echo "IDENTITY_ABORT_NOT_UNIFIED_DEV" >&2; exit 98 ;;
esac

target=${1:-}
rep=${2:-}
case "$target" in systemui|browser|AppUIB|settings) ;; *) echo "bad target" >&2; exit 2 ;; esac
case "$rep" in 1|2|3) ;; *) echo "bad rep" >&2; exit 2 ;; esac

probe=/root/reclaim_probe.armv7l
prepare=/root/test_board_prepare_load.sh
run=/root/reclaim_runs/$target/rep$rep
fatal_pattern='Killed process|Out of memory|lowmemory|fatal signal|segfault|SIGSEGV|signal 11|SIG11'
rm -rf "$run"
mkdir -p "$run" || exit 3

case "$target" in
    systemui) appid=AppX ;;
    browser) appid=AppL ;;
    AppUIB) appid=AppQ ;;
    settings) appid=setting-myaccount-efl ;;
esac

get_pid()
{
    app_launcher -S 2>/dev/null |
        awk -v id="$appid" '$1 == id {gsub(/[()]/, "", $2); print $2; exit}'
}

check_alive()
{
    label=$1
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "PROCESS_DIED label=$label pid=$pid" | tee "$run/failure.txt"
        return 1
    fi
    current=$(get_pid)
    if [ "$current" != "$pid" ]; then
        echo "PID_CHANGED label=$label original=$pid current=${current:-NA}" | tee "$run/failure.txt"
        return 1
    fi
    return 0
}

check_fatal()
{
    label=$1
    now=$(dmesg 2>/dev/null | grep -Eic "$fatal_pattern" || true)
    echo "fatal_check label=$label baseline=$fatal_base current=$now" >>"$run/safety.log"
    if [ "$now" -gt "$fatal_base" ]; then
        dmesg 2>/dev/null | grep -Ei "$fatal_pattern" | tail -40 >"$run/fatal_new.txt"
        echo "FATAL_EVENT label=$label baseline=$fatal_base current=$now" | tee "$run/failure.txt"
        return 1
    fi
    return 0
}

collect()
{
    step=$1
    dir=$run/$step
    mkdir -p "$dir" || return 1
    date -u +%Y-%m-%dT%H:%M:%SZ >"$dir/date_utc.txt"
    free >"$dir/free.txt" 2>"$dir/free.err"
    grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo >"$dir/meminfo.txt"
    cat /proc/swaps >"$dir/swaps.txt"
    if [ -r /sys/block/zram0/mm_stat ]; then
        cat /sys/block/zram0/mm_stat >"$dir/zram_mm_stat.txt"
    else
        echo UNAVAILABLE >"$dir/zram_mm_stat.txt"
    fi
    "$probe" profile "$pid" >"$dir/profile.json" 2>"$dir/profile.err"
    profile_rc=$?
    echo "$profile_rc" >"$dir/profile.rc"
    cat "/proc/$pid/smaps_rollup" >"$dir/smaps_rollup.txt" 2>"$dir/smaps_rollup.err"
    cat "/proc/$pid/stat" >"$dir/stat.txt" 2>"$dir/stat.err"
    stat_line=$(cat "/proc/$pid/stat" 2>/dev/null)
    stat_rest=${stat_line#*) }
    set -- $stat_rest
    printf 'minflt=%s\nmajflt=%s\n' "${8:-NA}" "${10:-NA}" >"$dir/faults.txt"
    app_launcher -r "$appid" >"$dir/app_running.txt" 2>"$dir/app_running.err"
    echo "$?" >"$dir/app_running.rc"
    dmesg 2>/dev/null | tail -200 >"$dir/dmesg_tail.txt"
    check_alive "$step" || return 10
    check_fatal "$step" || return 11
    [ "$profile_rc" -eq 0 ] || return 12
    return 0
}

{
    echo IDENTITY_OK=RPI4_UNIFIED_DEV
    echo "kernel=$kernel"
    echo "target=$target"
    echo "appid=$appid"
    echo "rep=$rep"
    date -u +START_UTC=%Y-%m-%dT%H:%M:%SZ
} >"$run/meta.txt"

"$prepare" >"$run/load_prepare.out" 2>"$run/load_prepare.err"
prepare_rc=$?
echo "$prepare_rc" >"$run/load_prepare.rc"
[ "$prepare_rc" -eq 0 ] || exit 20
if [ "$target" = browser ]; then
    app_launcher -s "$appid" >"$run/browser_keep_foreground.out" 2>"$run/browser_keep_foreground.err"
    keep_rc=$?
    echo "$keep_rc" >"$run/browser_keep_foreground.rc"
    [ "$keep_rc" -eq 0 ] || exit 22
    sleep 3
fi
echo IDLE_START_60S >>"$run/meta.txt"
sleep 60

pid=$(get_pid)
if [ -z "$pid" ] || [ ! -d "/proc/$pid" ]; then
    echo "TARGET_PID_NOT_FOUND appid=$appid" | tee "$run/failure.txt"
    exit 21
fi
echo "pid=$pid" >>"$run/meta.txt"
readlink "/proc/$pid/exe" >"$run/exe.txt" 2>"$run/exe.err"
tr '\000' ' ' <"/proc/$pid/cmdline" >"$run/cmdline.txt" 2>"$run/cmdline.err"

dmesg 2>/dev/null | grep -Ei "$fatal_pattern" >"$run/fatal_baseline.txt" || true
fatal_base=$(wc -l <"$run/fatal_baseline.txt")
echo "fatal_baseline_count=$fatal_base" >>"$run/safety.log"

collect T0 || exit $?

echo 'SKIPPED: gdb unavailable; malloc_trim was not called' >"$run/T1_action.txt"
sleep 10
collect T1 || exit $?

"$probe" pageout "$pid" glibc-heap >"$run/T2_action.json" 2>"$run/T2_action.err"
t2_rc=$?
echo "$t2_rc" >"$run/T2_action.rc"
[ "$t2_rc" -eq 0 ] || exit 30
sleep 10
collect T2 || exit $?

"$probe" pageout "$pid" other-anon >"$run/T3_action.json" 2>"$run/T3_action.err"
t3_rc=$?
echo "$t3_rc" >"$run/T3_action.rc"
[ "$t3_rc" -eq 0 ] || exit 31
sleep 10
collect T3 || exit $?

start_ns=$(date +%s%N)
if [ "$target" = settings ]; then
    aul_test resume "$appid" >"$run/T4_action.out" 2>"$run/T4_action.err"
    t4_raw_rc=$?
    if grep -q 'test successful' "$run/T4_action.out"; then
        t4_rc=0
    else
        t4_rc=$t4_raw_rc
    fi
    echo "$t4_raw_rc" >"$run/T4_action_raw.rc"
else
    app_launcher -s "$appid" >"$run/T4_action.out" 2>"$run/T4_action.err"
    t4_rc=$?
fi
end_ns=$(date +%s%N)
echo "$t4_rc" >"$run/T4_action.rc"
awk -v start="$start_ns" -v end="$end_ns" 'BEGIN { printf "%.3f\n", (end-start)/1000000 }' >"$run/T4_response_ms.txt"
[ "$t4_rc" -eq 0 ] || exit 32
sleep 10
collect T4 || exit $?

echo COMPLETE >"$run/status.txt"
date -u +FINISH_UTC=%Y-%m-%dT%H:%M:%SZ >>"$run/meta.txt"
exit 0
