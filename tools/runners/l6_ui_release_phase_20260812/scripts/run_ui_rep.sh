#!/bin/sh

set -u
. /root/l6uirelease/probe_common.sh

target=${1:?target required}
rep=${2:?rep required}
runout="$root/runs/$target/rep$rep"
test ! -e "$runout" || { echo "ABORT: output exists: $runout" >&2; exit 96; }
mkdir -p "$runout"

apps='AppP AppR AppJ AppW setting-myaccount-efl'

get_pid()
{
    app=$1
    aul_test get_pid "$app" 2>&1 | sed -n 's/.*ret = \([0-9][0-9]*\).*/\1/p' | tail -1
}

wait_pid()
{
    app=$1
    old=${2:-}
    ticks=0
    while test "$ticks" -lt 100; do
        pid=$(get_pid "$app")
        if test -n "$pid" && test "$pid" != "$old" && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
        sleep 0.2
        ticks=$((ticks + 1))
    done
    return 1
}

restart_app()
{
    app=$1
    old=$(get_pid "$app")
    echo "restart app=$app old_pid=$old epoch=$(date +%s.%N)" >>"$runout/run_record.txt"
    app_launcher -t "$app" >>"$runout/restart.txt" 2>&1 || true
    sleep 3
    app_launcher -s "$app" >>"$runout/restart.txt" 2>&1 || return 1
    pid=$(wait_pid "$app" "$old") || return 1
    echo "restart app=$app new_pid=$pid" >>"$runout/run_record.txt"
    echo "$pid"
}

terminate_workload_apps()
{
    for app in setting-myaccount-efl AppW AppJ AppR AppP; do
        app_launcher -t "$app" >>"$runout/workload.txt" 2>&1 || true
        sleep 1
    done
}

cleanup()
{
    if test "$target" = AppUIB; then
        terminate_workload_apps
    fi
}
trap cleanup EXIT HUP INT TERM

{
    echo "target=$target rep=$rep"
    echo "start=$(date -Ins) uptime=$(cut -d ' ' -f1 /proc/uptime)"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    rpm -q glibc
} >"$runout/run_record.txt"
dmesg | tail -300 >"$runout/dmesg_before.txt" 2>&1
health_snapshot "$runout/health_before.txt"

case "$target" in
    AppUIB)
        pid=$(restart_app AppQ) || { echo RESTART_FAILED >>"$runout/run_record.txt"; exit 20; }
        ;;
    systemui)
        pid=$(restart_app AppX) || { echo RESTART_FAILED >>"$runout/run_record.txt"; exit 20; }
        ;;
    *)
        echo "unknown target: $target" >&2
        exit 64
        ;;
esac

sleep 12
capture_point "$pid" T0 "$runout"

if test "$target" = AppUIB; then
    for app in $apps; do
        echo "launch app=$app epoch=$(date +%s.%N)" >>"$runout/workload.txt"
        app_launcher -s "$app" >>"$runout/workload.txt" 2>&1 || true
        sleep 3
        app_launcher -r "$app" >>"$runout/workload.txt" 2>&1 || true
        aul_test get_pid "$app" >>"$runout/workload.txt" 2>&1 || true
    done
else
    for scene in 1 2 3 4 5; do
        echo "launch alias=tizen.syspopup scene=$scene epoch=$(date +%s.%N)" >>"$runout/workload.txt"
        aul_test launch tizen.syspopup message "L6_UI_SYSTEMUI_REP_${rep}_SCENE_$scene" \
            errorMessage "L6_UI_SYSTEMUI_REP_${rep}_SCENE_$scene" >>"$runout/workload.txt" 2>&1 || true
        sleep 1
    done
    sleep 3
fi

capture_point "$pid" T1 "$runout"
malloc_info_capture "$pid" T1 "$runout" || { echo MI_T1_FAILED >>"$runout/run_record.txt"; exit 21; }

if test "$target" = AppUIB; then
    terminate_workload_apps
else
    sleep 12
fi
sleep 10

capture_point "$pid" T2 "$runout"
malloc_info_capture "$pid" T2 "$runout" || { echo MI_T2_FAILED >>"$runout/run_record.txt"; exit 22; }
{
    echo 'T1'
    malloc_info_totals "$runout/malloc_info_T1.xml"
    echo 'T2'
    malloc_info_totals "$runout/malloc_info_T2.xml"
} >"$runout/m7_totals.txt"
set -- $(sed -n 's/unsorted_bytes=\([0-9]*\) fast_bytes=[0-9]* rest_bytes=\([0-9]*\).*/\1 \2/p' "$runout/m7_totals.txt")
t1_unsorted=$1
t1_rest=$2
t2_unsorted=$3
t2_rest=$4
if test "${PHASE_ONLY:-0}" = 1; then
    echo "M7_DECISION=HOST_REVIEW unsorted_delta=$((t2_unsorted - t1_unsorted)) rest_delta=$((t2_rest - t1_rest))" >>"$runout/run_record.txt"
elif test "$t2_unsorted" -gt "$t1_unsorted" && test "$t2_rest" -gt "$t1_rest"; then
    echo "M7_DECISION=GO unsorted_delta=$((t2_unsorted - t1_unsorted)) rest_delta=$((t2_rest - t1_rest))" >>"$runout/run_record.txt"
    trim_capture "$pid" "$runout" || { echo TRIM_FAILED >>"$runout/run_record.txt"; exit 23; }
    capture_point "$pid" T4 "$runout"
    if test "$target" = AppUIB; then
        app_launcher -s AppP >>"$runout/refault_action.txt" 2>&1 || true
        sleep 5
        capture_point "$pid" T5 "$runout"
        app_launcher -t AppP >>"$runout/refault_action.txt" 2>&1 || true
    else
        aul_test launch tizen.syspopup message "L6_UI_REFAULT_$rep" \
            errorMessage "L6_UI_REFAULT_$rep" >>"$runout/refault_action.txt" 2>&1 || true
        sleep 5
        capture_point "$pid" T5 "$runout"
        sleep 8
    fi
else
    echo "M7_DECISION=SKIP unsorted_delta=$((t2_unsorted - t1_unsorted)) rest_delta=$((t2_rest - t1_rest))" >>"$runout/run_record.txt"
fi

if ! kill -0 "$pid" 2>/dev/null; then echo TARGET_ALIVE=0 >>"$runout/run_record.txt"; exit 25; fi
if ! systemctl is-active --quiet display-manager; then echo COMPOSITOR_ACTIVE=0 >>"$runout/run_record.txt"; exit 26; fi
echo TARGET_ALIVE=1 >>"$runout/run_record.txt"
echo COMPOSITOR_ACTIVE=1 >>"$runout/run_record.txt"
health_snapshot "$runout/health_after.txt"
dmesg | tail -500 >"$runout/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$runout/dmesg_after.txt" >"$runout/dmesg_alerts.txt" 2>&1 || true
echo "end=$(date -Ins) EXIT=0" >>"$runout/run_record.txt"
touch "$runout/DONE"
trap - EXIT HUP INT TERM
exit 0
