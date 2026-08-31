#!/bin/sh
set -u

base=/root/chromium_url_entry
out=$base/results/b2_systemd_AppUIC
unit=chromium-url-entry-AppUIC
url=file:///tmp/chromium_url_entry_simple.html
mkdir -p "$out"

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

systemctl stop "$unit.service" 2>/dev/null || true
pkill -TERM -x AppUIC 2>/dev/null || true
sleep 2
dlogutil --monitor -v time '*:V' >"$out/dlog_full.txt" 2>"$out/dlog.err" &
dlog_pid=$!
sleep 1
{
    date -Ins
    echo "requested_url=$url"
    echo "CMD=systemd-run --no-block --collect --unit=$unit --uid=<USER> --gid=users -p SupplementaryGroups=display -E XDG_RUNTIME_DIR=/run/user/5001 -E WAYLAND_DISPLAY=wayland-0 -E HOME=/opt/usr/home/<USER> /usr/apps/AppK/bin/AppUIC -v -n $url"
} >"$out/run.txt"
systemd-run --no-block --collect --unit="$unit" --uid='<USER>' --gid=users \
    -p SupplementaryGroups=display \
    -E XDG_RUNTIME_DIR=/run/user/5001 -E WAYLAND_DISPLAY=wayland-0 \
    -E HOME='/opt/usr/home/<USER>' \
    /usr/apps/AppK/bin/AppUIC -v -n "$url" \
    >"$out/launch.stdout" 2>"$out/launch.stderr"
echo "LAUNCH_EXIT=$?" >>"$out/run.txt"
sleep 15
{
    systemctl status "$unit.service" --no-pager
    systemctl show "$unit.service" -p MainPID -p ActiveState -p SubState -p Result
} >"$out/unit_status.txt" 2>&1 || true
{
    ps -eo pid,ppid,user,group,stat,etimes,args | grep -E 'PID|AppUIC|efl_webprocess' | grep -v grep
    for pid in $(pgrep -f 'AppUIC|efl_webprocess' 2>/dev/null); do
        [ -r "/proc/$pid/status" ] || continue
        echo "=== PID $pid ==="
        tr '\000' ' ' <"/proc/$pid/cmdline"; echo
        grep -E '^(Name|State|Pid|PPid|Uid|Gid|CapEff|NoNewPrivs|Seccomp):' "/proc/$pid/status"
        printf 'attr_current='; cat "/proc/$pid/attr/current"
    done
} >"$out/processes.txt" 2>&1
systemctl stop "$unit.service" >"$out/stop.txt" 2>&1 || true
sleep 3
kill "$dlog_pid" 2>/dev/null || true
wait "$dlog_pid" 2>/dev/null || true
grep -iE 'ewk_view_url_set|LoadProgressChanged|DidFinishLoad|console message|CHROMIUM_URL_ENTRY|Permission denied|FATAL|NETWORK ERROR' \
    "$out/dlog_full.txt" >"$out/dlog_focus.txt" 2>&1 || true
{
    systemctl is-active display-manager
    systemctl show display-manager -p MainPID -p NRestarts -p ActiveState -p SubState
    app_launcher -S AppQ 2>&1
    app_launcher -S AppX 2>&1
    systemctl status "$unit.service" --no-pager 2>&1 || true
} >"$out/health_after.txt" 2>&1
echo B2_UBROWSER_DONE
