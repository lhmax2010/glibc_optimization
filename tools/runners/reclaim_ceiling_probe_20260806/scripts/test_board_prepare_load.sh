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

echo IDENTITY_OK=RPI4_UNIFIED_DEV
echo "kernel=$kernel"
date -u +START_UTC=%Y-%m-%dT%H:%M:%SZ

round=1
while [ "$round" -le 3 ]; do
    echo "=== INTERACTION_ROUND $round ==="
    echo '--- foreground Chromium/EFL browser ---'
    app_launcher -s AppL 2>&1
    echo "browser_start_rc=$?"
    sleep 3

    echo '--- foreground EFL account settings ---'
    app_launcher -s setting-myaccount-efl 2>&1
    echo "settings_start_rc=$?"
    sleep 3

    echo '--- return AppUIB ---'
    app_launcher -s AppQ 2>&1
    echo "AppUIB_start_rc=$?"
    sleep 3

    echo '--- resume browser then return home ---'
    aul_test resume AppL 2>&1
    echo "browser_resume_rc=$?"
    sleep 2
    app_launcher -s AppQ 2>&1
    echo "AppUIB_return_rc=$?"
    sleep 2
    round=$((round + 1))
done

echo '=== RUNNING_APPS ==='
app_launcher -S 2>&1
echo '=== RELEVANT_PROCESSES ==='
ps -eo pid,ppid,comm,rss,args 2>&1 |
    grep -Ei 'AppUIA|AppUIB|runner|chromium|browser|myaccount|webprocess|efl' |
    grep -v grep
date -u +FINISH_UTC=%Y-%m-%dT%H:%M:%SZ
