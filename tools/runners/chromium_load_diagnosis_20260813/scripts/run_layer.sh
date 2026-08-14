#!/bin/sh
set -u

layer=${1:?layer required}
duration=${2:-30}
extra=${3:-}
env_mode=${4:-plain}
base=/root/chromium_load_diag
out=$base/results/$layer
browser=/usr/apps/AppK/bin/AppUIC

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

case "$layer" in
    L1|L1_xdg) url='about:blank' ;;
    L2) url='data:text/html,<html><body><h1>hi</h1></body></html>' ;;
    L3|L3_xdg) url='file:///tmp/chromium_diag_l3.html' ;;
    L3home) url='file:///opt/usr<USER_HOME>/chromium_diag_l3.html' ;;
    L4) url='file:///tmp/chromium_diag_l4.html' ;;
    L5|L5_xdg|gpu_*) url='file:///tmp/chromium_diag_l5.html' ;;
    *) echo "unknown layer: $layer" >&2; exit 2 ;;
esac

mkdir -p "$out" || exit 3
{
    date -Ins
    echo "layer=$layer"
    echo "duration=$duration"
    echo "url=$url"
    echo "extra=$extra"
    echo "env_mode=$env_mode"
    echo "command=$browser -v -n $extra $url"
    uname -a
    grep -E 'BUILD_ID|VERSION|PRETTY_NAME' /etc/os-release
    systemctl show display-manager -p ActiveState -p SubState -p MainPID -p NRestarts -p Result
} >"$out/run_record.txt" 2>"$out/run_record.err"

dlogutil --monitor -v time '*:V' >"$out/dlog_full.txt" 2>"$out/dlog.err" &
dlog_pid=$!
sleep 1

# extra is restricted to one diagnostic switch selected by the host script.
if [ "$env_mode" = xdg ]; then
    XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 \
        "$browser" -v -n ${extra:+"$extra"} "$url" >"$out/browser.stdout" 2>"$out/browser.stderr" &
elif [ -n "$extra" ]; then
    "$browser" -v -n "$extra" "$url" >"$out/browser.stdout" 2>"$out/browser.stderr" &
else
    "$browser" -v -n "$url" >"$out/browser.stdout" 2>"$out/browser.stderr" &
fi
browser_pid=$!
echo "$browser_pid" >"$out/browser.pid"

sample_processes()
{
    tag=$1
    {
        echo "=== $tag $(date -Ins) ==="
        ps -eo pid,ppid,user,group,stat,etimes,args | grep -E 'PID|AppUIC|efl_webprocess|chromium' | grep -v grep
    } >>"$out/process_timeline.txt" 2>&1
    for pid in $(pgrep -f '/usr/apps/AppK/bin/AppUIC|efl_webprocess' 2>/dev/null); do
        [ -d "/proc/$pid" ] || continue
        {
            echo "=== PID $pid $tag ==="
            tr '\000' ' ' <"/proc/$pid/cmdline"; echo
            grep -E '^(Name|State|Pid|PPid|Uid|Gid|Threads|Cap(Inh|Prm|Eff|Bnd|Amb)|NoNewPrivs|Seccomp):' "/proc/$pid/status"
            printf 'attr_current='; cat "/proc/$pid/attr/current" 2>&1
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
    if ! kill -0 "$browser_pid" 2>/dev/null; then
        echo "BROWSER_EXITED_AT=$elapsed" >>"$out/run_record.txt"
        break
    fi
done

if kill -0 "$browser_pid" 2>/dev/null; then
    echo BROWSER_ALIVE_BEFORE_CLOSE=1 >>"$out/run_record.txt"
    kill "$browser_pid" 2>/dev/null || true
    sleep 3
else
    echo BROWSER_ALIVE_BEFORE_CLOSE=0 >>"$out/run_record.txt"
fi
wait "$browser_pid" 2>/dev/null
echo "BROWSER_EXIT=$?" >>"$out/run_record.txt"

kill "$dlog_pid" 2>/dev/null || true
wait "$dlog_pid" 2>/dev/null || true

{
    echo "=== LOAD TIMELINE ==="
    grep -iE 'ewk_view_url_set|LoadProgress|Did(Start|Finish|Fail)|Document|Frame|Navigation|Console|L4_DONE|L6_UI|about:blank' "$out/dlog_full.txt"
    echo "=== ERRORS ==="
    grep -iE 'EWK|chromium|Blink|Renderer|Network|URLRequest|sandbox|SECURITY|Permission|denied|Failed|Error|EGL|GLES|GPU|DRM|Wayland' "$out/dlog_full.txt"
} >"$out/dlog_focus.txt" 2>&1

{
    date -Ins
    systemctl is-active display-manager
    systemctl show display-manager -p ActiveState -p SubState -p MainPID -p NRestarts -p Result
    test -S /run/wayland-0 && echo WAYLAND_SOCKET_OK
    pgrep -af '/usr/apps/AppK/bin/AppUIC|efl_webprocess' || true
} >"$out/health_after.txt" 2>&1

echo DONE >"$out/DONE"
