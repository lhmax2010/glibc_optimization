#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel:$os_release" in
    *rpi4*:*unified-dev*) ;;
    *) echo "IDENTITY_ABORT kernel=$kernel" >&2; exit 97 ;;
esac

target=${1:-}
rep=${2:-}
pid=${3:-}
case "$target" in
    systemui) appid=AppX ;;
    AppUIB) appid=AppQ ;;
    *) echo "usage: $0 systemui|AppUIB rep pid" >&2; exit 2 ;;
esac
case "$rep" in 1|2|3) ;; *) echo "bad rep: $rep" >&2; exit 2 ;; esac
case "$pid" in ''|*[!0-9]*) echo "bad pid: $pid" >&2; exit 2 ;; esac

probe=/root/probe/reclaim_probe.armv7l
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

[ "$(cat "$run/status.txt" 2>/dev/null)" = READY_FOR_LLDB ] || exit 3
[ "$(get_pid)" = "$pid" ] && [ -d "/proc/$pid" ] || exit 4
[ -f "$run/lldb_trim_complete.txt" ] || exit 5

collect T1p || exit $?

start_ns=$(date +%s%N)
app_launcher -s "$appid" >"$run/T2_action.out" 2>"$run/T2_action.err"
t2_rc=$?
end_ns=$(date +%s%N)
echo "$t2_rc" >"$run/T2_action.rc"
awk -v start="$start_ns" -v end="$end_ns" 'BEGIN { printf "%.3f\n", (end-start)/1000000 }' >"$run/T2_response_ms.txt"
[ "$t2_rc" -eq 0 ] || exit 30
sleep 2
collect T2 || exit $?

fatal_base=$(sed -n 's/^fatal_baseline_count=//p' "$run/safety.log" | head -1)
fatal_now=$(dmesg | grep -Eic "$fatal_pattern" || true)
echo "fatal_check label=T1p_T2 baseline=$fatal_base current=$fatal_now" >>"$run/safety.log"
if [ "$fatal_now" -gt "$fatal_base" ]; then
    dmesg | grep -Ei "$fatal_pattern" | tail -40 >"$run/fatal_new.txt"
    exit 31
fi

echo COMPLETE >"$run/status.txt"
date -u +FINISH_UTC=%Y-%m-%dT%H:%M:%SZ >>"$run/meta.txt"
printf 'COMPLETE target=%s rep=%s pid=%s response_ms=%s\n' "$target" "$rep" "$pid" "$(cat "$run/T2_response_ms.txt")"

