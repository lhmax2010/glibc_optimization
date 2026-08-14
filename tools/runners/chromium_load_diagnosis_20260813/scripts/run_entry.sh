#!/bin/sh
set -u

mode=${1:?mode required}
duration=${2:-25}
base=/root/chromium_load_diag
out=$base/results/$mode
appid=AppK
efl=/usr/apps/AppK/bin/efl_webview_app
mini=/usr/apps/AppK/bin/mini_browser
url=file:///tmp/chromium_diag_l3.html
[ "$mode" = app_efl_heavy ] && url=file:///tmp/chromium_diag_l5.html

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

mkdir -p "$out" || exit 3
{
    date -Ins
    echo "mode=$mode"
    echo "duration=$duration"
    echo "url=$url"
    uname -a
    grep -E 'BUILD_ID|VERSION|PRETTY_NAME' /etc/os-release
    systemctl show display-manager -p ActiveState -p SubState -p MainPID -p NRestarts -p Result
} >"$out/run_record.txt" 2>"$out/run_record.err"

dlogutil --monitor -v time '*:V' >"$out/dlog_full.txt" 2>"$out/dlog.err" &
dlog_pid=$!
sleep 1

launcher_pid=
case "$mode" in
    direct_efl)
        echo "command=XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 $efl $url" >>"$out/run_record.txt"
        XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 \
            "$efl" "$url" >"$out/entry.stdout" 2>"$out/entry.stderr" &
        launcher_pid=$!
        ;;
    direct_mini)
        echo "command=XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 $mini" >>"$out/run_record.txt"
        XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 \
            "$mini" >"$out/entry.stdout" 2>"$out/entry.stderr" &
        launcher_pid=$!
        ;;
    app_efl|app_efl_heavy)
        echo "command=app_launcher -s $appid __APP_SVC_URI__ $url" >>"$out/run_record.txt"
        app_launcher -s "$appid" __APP_SVC_URI__ "$url" >"$out/entry.stdout" 2>"$out/entry.stderr"
        echo "APP_LAUNCH_EXIT=$?" >>"$out/run_record.txt"
        ;;
    *)
        echo "unknown mode: $mode" >&2
        kill "$dlog_pid" 2>/dev/null || true
        exit 2
        ;;
esac

sample_processes()
{
    tag=$1
    {
        echo "=== $tag $(date -Ins) ==="
        ps -eo pid,ppid,user,group,stat,etimes,args | grep -E 'PID|efl_webview_app|mini_browser|efl_webprocess|chromium' | grep -v grep
        app_launcher -S "$appid" 2>&1 || true
    } >>"$out/process_timeline.txt" 2>&1
    for pid in $(pgrep -f '/usr/apps/AppK/bin/(efl_webview_app|mini_browser)|efl_webprocess' 2>/dev/null); do
        [ -d "/proc/$pid" ] || continue
        {
            echo "=== PID $pid $tag ==="
            tr '\000' ' ' <"/proc/$pid/cmdline"; echo
            grep -E '^(Name|State|Pid|PPid|Uid|Gid|Threads|Cap(Inh|Prm|Eff|Bnd|Amb)|NoNewPrivs|Seccomp):' "/proc/$pid/status"
            printf 'attr_current='; cat "/proc/$pid/attr/current" 2>&1
            printf 'env='; tr '\000' '\n' <"/proc/$pid/environ" | grep -E '^(XDG_RUNTIME_DIR|WAYLAND_DISPLAY|HOME|USER|LOGNAME)=' || true
        } >>"$out/process_security.txt" 2>&1
        grep -iE 'lib(EGL|GLES|GL|drm|gbm|tbm|wayland)|swiftshader|gpu|v3d|vc4' "/proc/$pid/maps" \
            >"$out/maps_gpu_${pid}_${tag}.txt" 2>&1 || true
    done
}

sleep 2
sample_processes T02
elapsed=2
while [ "$elapsed" -lt "$duration" ]; do
    sleep 5
    elapsed=$((elapsed + 5))
    sample_processes "T$(printf '%02d' "$elapsed")"
done

if [ "$mode" = app_efl ] || [ "$mode" = app_efl_heavy ]; then
    app_launcher -t "$appid" >"$out/close.stdout" 2>"$out/close.stderr"
    echo "APP_CLOSE_EXIT=$?" >>"$out/run_record.txt"
elif [ -n "$launcher_pid" ]; then
    if kill -0 "$launcher_pid" 2>/dev/null; then
        echo ENTRY_ALIVE_BEFORE_CLOSE=1 >>"$out/run_record.txt"
        kill "$launcher_pid" 2>/dev/null || true
        sleep 3
    else
        echo ENTRY_ALIVE_BEFORE_CLOSE=0 >>"$out/run_record.txt"
    fi
    wait "$launcher_pid" 2>/dev/null
    echo "ENTRY_EXIT=$?" >>"$out/run_record.txt"
fi

kill "$dlog_pid" 2>/dev/null || true
wait "$dlog_pid" 2>/dev/null || true

{
    echo "=== LOAD TIMELINE ==="
    grep -iE 'ewk_view_url_set|LoadProgress|Did(Start|Finish|Fail)|Document|Frame|Navigation|Console|about:blank|google' "$out/dlog_full.txt"
    echo "=== ERRORS ==="
    grep -iE 'EWK|chromium|Blink|Renderer|Network|URLRequest|sandbox|SECURITY|Permission|denied|Failed|Error|EGL|GLES|GPU|DRM|Wayland|shared memory' "$out/dlog_full.txt"
} >"$out/dlog_focus.txt" 2>&1

{
    date -Ins
    systemctl is-active display-manager
    systemctl show display-manager -p ActiveState -p SubState -p MainPID -p NRestarts -p Result
    test -S /run/wayland-0 && echo WAYLAND_SOCKET_OK
    app_launcher -S "$appid" 2>&1 || true
    pgrep -af '/usr/apps/AppK/bin/(efl_webview_app|mini_browser)|efl_webprocess' || true
} >"$out/health_after.txt" 2>&1

echo DONE >"$out/DONE"
