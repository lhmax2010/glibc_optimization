#!/bin/sh
set -u

base=/root/chromium_url_entry
results=$base/results
appid=AppK
url=file:///tmp/chromium_url_entry_simple.html

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

mkdir -p "$results" || exit 3

stop_demo()
{
    for pid in $(pgrep -x efl_webview_app 2>/dev/null); do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 3
}

run_attempt()
{
    name=$1
    out=$results/$name
    mkdir -p "$out"
    stop_demo
    dlogutil --monitor -v time '*:V' >"$out/dlog_full.txt" 2>"$out/dlog.err" &
    dlog_pid=$!
    sleep 1
    {
        date -Ins
        echo "attempt=$name"
        echo "requested_url=$url"
    } >"$out/run.txt"
    case "$name" in
        app_launcher_uri)
            echo "CMD=app_launcher -s $appid __APP_SVC_URI__ $url" >>"$out/run.txt"
            app_launcher -s "$appid" __APP_SVC_URI__ "$url" >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
        app_launcher_standard)
            echo "CMD=app_launcher -s $appid __APP_SVC_OP_TYPE__ http://tizen.org/appcontrol/operation/view __APP_SVC_URI__ $url __APP_SVC_MIME_TYPE__ text/html" >>"$out/run.txt"
            app_launcher -s "$appid" \
                __APP_SVC_OP_TYPE__ http://tizen.org/appcontrol/operation/view \
                __APP_SVC_URI__ "$url" __APP_SVC_MIME_TYPE__ text/html \
                >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
        aul_launch_standard)
            echo "CMD=aul_test launch $appid __APP_SVC_OP_TYPE__ http://tizen.org/appcontrol/operation/view __APP_SVC_URI__ $url __APP_SVC_MIME_TYPE__ text/html" >>"$out/run.txt"
            aul_test launch "$appid" \
                __APP_SVC_OP_TYPE__ http://tizen.org/appcontrol/operation/view \
                __APP_SVC_URI__ "$url" __APP_SVC_MIME_TYPE__ text/html \
                >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
        aul_open_content)
            echo "CMD=aul_test open_content /tmp/chromium_url_entry_simple.html" >>"$out/run.txt"
            aul_test open_content /tmp/chromium_url_entry_simple.html \
                >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
        app_direct_uri)
            echo "CMD=app_launcher -e $appid __APP_SVC_URI__ $url" >>"$out/run.txt"
            app_launcher -e "$appid" __APP_SVC_URI__ "$url" \
                >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
        launch_app_uri)
            echo "CMD=launch_app $appid __APP_SVC_URI__ $url" >>"$out/run.txt"
            launch_app "$appid" __APP_SVC_URI__ "$url" \
                >"$out/launch.stdout" 2>"$out/launch.stderr"
            ;;
    esac
    launch_rc=$?
    echo "LAUNCH_EXIT=$launch_rc" >>"$out/run.txt"
    sleep 10
    {
        ps -eo pid,ppid,user,group,stat,etimes,args | grep -E 'PID|efl_webview_app|efl_webprocess' | grep -v grep
        for pid in $(pgrep -f 'efl_webview_app|efl_webprocess' 2>/dev/null); do
            [ -r "/proc/$pid/status" ] || continue
            echo "=== PID $pid ==="
            tr '\000' ' ' <"/proc/$pid/cmdline"; echo
            grep -E '^(Name|State|Pid|PPid|Uid|Gid|CapEff|NoNewPrivs|Seccomp):' "/proc/$pid/status"
            printf 'attr_current='; cat "/proc/$pid/attr/current"
        done
    } >"$out/processes.txt" 2>&1
    stop_demo
    kill "$dlog_pid" 2>/dev/null || true
    wait "$dlog_pid" 2>/dev/null || true
    grep -iE 'ewk_view_url_set|LoadProgressChanged|DidFinishLoad|console message|CHROMIUM_URL_ENTRY|Permission denied|FATAL|NETWORK ERROR' \
        "$out/dlog_full.txt" >"$out/dlog_focus.txt" 2>&1 || true
    {
        systemctl is-active display-manager
        systemctl show display-manager -p MainPID -p NRestarts -p ActiveState -p SubState
        app_launcher -S AppQ 2>&1
        app_launcher -S AppX 2>&1
    } >"$out/health_after.txt" 2>&1
    echo "DONE attempt=$name launch_exit=$launch_rc"
}

for attempt in app_launcher_uri app_launcher_standard aul_launch_standard aul_open_content app_direct_uri launch_app_uri; do
    run_attempt "$attempt"
done

echo B1_DONE
