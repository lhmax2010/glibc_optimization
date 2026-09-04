#!/bin/sh
set -u

app_id=${1:-}
case "$app_id" in
    ''|*[!A-Za-z0-9._-]*) echo RC=2; echo FAIL_APP_RECON; exit 2 ;;
esac
work=/opt/usr/glibc_memopt/tizen_native_evidence_b2_20260904
log="$work/recon_app_${app_id}.log"
pid=

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        app_launcher -t "$app_id" >>"$log" 2>&1 || true
    fi
    exit "$rc"
}
trap finish EXIT HUP INT TERM

fail()
{
    echo "app_id=$app_id reason=$1"
    echo RC=1
    echo FAIL_APP_RECON
    exit 1
}

: >"$log"
begin=$(date +%s%N)
launch=$(app_launcher -s "$app_id" 2>&1)
launch_rc=$?
printf '%s\nlaunch_rc=%s\n' "$launch" "$launch_rc" >>"$log"
[ "$launch_rc" -eq 0 ] || fail launch
pid=$(printf '%s\n' "$launch" | awk '/successfully launched pid =/{print $(NF-3); exit}')
case "$pid" in ''|*[!0-9]*) fail pid_parse ;; esac
launched_pid=$pid
kill -0 "$pid" 2>/dev/null || fail not_alive_after_launch
starttime=$(sed 's/^[^)]*) //' "/proc/$pid/stat" | awk '{print $20}')
sleep 30
alive_ns=$(date +%s%N)
kill -0 "$pid" 2>/dev/null || fail not_alive_at_30s
current_start=$(sed 's/^[^)]*) //' "/proc/$pid/stat" | awk '{print $20}')
[ "$current_start" = "$starttime" ] || fail pid_reused
app_launcher -t "$app_id" >>"$log" 2>&1
term_rc=$?
term_ns=$(date +%s%N)
printf 'terminate_rc=%s\n' "$term_rc" >>"$log"
[ "$term_rc" -eq 0 ] || fail terminate
sleep 2
kill -0 "$pid" 2>/dev/null && fail alive_after_terminate
pid=
alive_s=$(awk -v a="$begin" -v b="$alive_ns" 'BEGIN {printf "%.9f",(b-a)/1000000000}')
echo "app_id=$app_id launched_pid=$launched_pid starttime_ticks=$starttime alive_check_s=$alive_s terminate_rc=$term_rc terminate_ns=$term_ns"
echo RC=0
echo DONE_APP_RECON
