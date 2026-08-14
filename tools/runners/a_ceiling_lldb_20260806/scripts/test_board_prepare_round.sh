#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel:$os_release" in
    *rpi4*:*unified-dev*) ;;
    *) echo "IDENTITY_ABORT kernel=$kernel" >&2; exit 97 ;;
esac

target=${1:-}
rep=${2:-}
case "$target" in
    systemui) appid=AppX ;;
    AppUIB) appid=AppQ ;;
    *) echo "usage: $0 systemui|AppUIB rep" >&2; exit 2 ;;
esac
case "$rep" in 1|2|3) ;; *) echo "bad rep: $rep" >&2; exit 2 ;; esac

probe=/root/probe/reclaim_probe.armv7l
load=/root/probe/test_board_prepare_load.sh
run=/root/a_ceiling_runs/$target/rep$rep
fatal_pattern='Killed process|Out of memory|lowmemory|fatal signal|segfault|SIGSEGV|signal 11|SIG11'

get_pid()
{
    app_launcher -S 2>/dev/null |
        awk -v id="$appid" '$1 == id {gsub(/[()]/, "", $2); print $2; exit}'
}

collect()
{
    label=$1
    dir=$run/$label
    mkdir -p "$dir" || return 1
    date -u +%Y-%m-%dT%H:%M:%SZ >"$dir/date_utc.txt"
    "$probe" profile "$pid" >"$dir/profile.json" 2>"$dir/profile.err"
    echo "$?" >"$dir/profile.rc"
    cat "/proc/$pid/smaps_rollup" >"$dir/smaps_rollup.txt" 2>"$dir/smaps_rollup.err"
    stat_line=$(cat "/proc/$pid/stat" 2>"$dir/stat.err")
    printf '%s\n' "$stat_line" >"$dir/stat.txt"
    stat_rest=${stat_line#*) }
    set -- $stat_rest
    printf 'minflt=%s\nmajflt=%s\n' "${8:-NA}" "${10:-NA}" >"$dir/faults.txt"
    free >"$dir/free.txt" 2>"$dir/free.err"
    cat /proc/swaps >"$dir/swaps.txt"
    cat /sys/block/zram0/mm_stat >"$dir/zram_mm_stat.txt" 2>"$dir/zram_mm_stat.err"
    app_launcher -r "$appid" >"$dir/app_running.txt" 2>"$dir/app_running.err"
    echo "$?" >"$dir/app_running.rc"
    dmesg | tail -200 >"$dir/dmesg_tail.txt" 2>"$dir/dmesg_tail.err"
    current=$(get_pid)
    if [ "$current" != "$pid" ] || [ ! -d "/proc/$pid" ]; then
        echo "PID_NOT_STABLE label=$label expected=$pid actual=${current:-NA}" >"$run/failure.txt"
        return 10
    fi
    return 0
}

rm -rf "$run"
mkdir -p "$run" || exit 3
{
    echo IDENTITY_OK=RPI4_UNIFIED_DEV
    echo "kernel=$kernel"
    echo "target=$target"
    echo "appid=$appid"
    echo "rep=$rep"
    date -u +START_UTC=%Y-%m-%dT%H:%M:%SZ
} >"$run/meta.txt"

dmesg | grep -Ei "$fatal_pattern" >"$run/fatal_baseline.txt" || true
fatal_base=$(wc -l <"$run/fatal_baseline.txt")
echo "fatal_baseline_count=$fatal_base" >"$run/safety.log"

old_pid=$(get_pid)
echo "old_pid=${old_pid:-NA}" >>"$run/meta.txt"
app_launcher -t "$appid" >"$run/restart_terminate.out" 2>"$run/restart_terminate.err"
echo "$?" >"$run/restart_terminate.rc"

i=0
while [ "$i" -lt 30 ]; do
    now=$(get_pid)
    [ -z "$old_pid" ] || [ "$now" != "$old_pid" ] && break
    sleep 1
    i=$((i + 1))
done

app_launcher -s "$appid" >"$run/restart_start.out" 2>"$run/restart_start.err"
start_rc=$?
echo "$start_rc" >"$run/restart_start.rc"

i=0
new_pid=
while [ "$i" -lt 30 ]; do
    new_pid=$(get_pid)
    if [ -n "$new_pid" ] && [ -d "/proc/$new_pid" ] &&
       { [ -z "$old_pid" ] || [ "$new_pid" != "$old_pid" ]; }; then
        break
    fi
    sleep 1
    i=$((i + 1))
done
if [ -z "$new_pid" ] || [ ! -d "/proc/$new_pid" ] ||
   { [ -n "$old_pid" ] && [ "$new_pid" = "$old_pid" ]; }; then
    echo "RESTART_FAILED old=${old_pid:-NA} new=${new_pid:-NA} start_rc=$start_rc" >"$run/failure.txt"
    exit 20
fi
echo "restart_pid=$new_pid" >>"$run/meta.txt"

"$load" >"$run/load_prepare.out" 2>"$run/load_prepare.err"
load_rc=$?
echo "$load_rc" >"$run/load_prepare.rc"
[ "$load_rc" -eq 0 ] || exit 21

echo IDLE_START_60S >>"$run/meta.txt"
sleep 60
pid=$(get_pid)
if [ -z "$pid" ] || [ ! -d "/proc/$pid" ]; then
    echo "TARGET_MISSING_AFTER_IDLE appid=$appid" >"$run/failure.txt"
    exit 22
fi
if [ "$pid" != "$new_pid" ]; then
    echo "PID_CHANGED_DURING_LOAD restart=$new_pid current=$pid" >"$run/failure.txt"
    exit 23
fi
echo "pid=$pid" >>"$run/meta.txt"
readlink "/proc/$pid/exe" >"$run/exe.txt" 2>"$run/exe.err"
tr '\000' ' ' <"/proc/$pid/cmdline" >"$run/cmdline.txt" 2>"$run/cmdline.err"

collect T0 || exit $?
fatal_now=$(dmesg | grep -Eic "$fatal_pattern" || true)
echo "fatal_check label=T0 baseline=$fatal_base current=$fatal_now" >>"$run/safety.log"
if [ "$fatal_now" -gt "$fatal_base" ]; then
    dmesg | grep -Ei "$fatal_pattern" | tail -40 >"$run/fatal_new.txt"
    exit 24
fi

echo READY_FOR_LLDB >"$run/status.txt"
date -u +T0_READY_UTC=%Y-%m-%dT%H:%M:%SZ >>"$run/meta.txt"
printf 'READY target=%s rep=%s pid=%s old_pid=%s\n' "$target" "$rep" "$pid" "${old_pid:-NA}"

