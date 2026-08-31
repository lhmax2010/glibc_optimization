#!/bin/sh
set -u

base=/root/chromium_url_entry
out=$base/results/b4_phase
unit=chromium-url-entry-b4
url=file:///tmp/chromium_url_entry_heavy.html
probe=$base/reclaim_probe.armv7l
mkdir -p "$out/heavy" "$out/blank"

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi
[ -x "$probe" ] || exit 4

profile_phase()
{
    phase=$1
    dir=$out/$phase
    main=$(systemctl show "$unit.service" -p MainPID --value 2>/dev/null)
    echo "$main" >"$dir/main.pid"
    if [ -n "$main" ] && [ "$main" -gt 1 ] 2>/dev/null && [ -r "/proc/$main/status" ]; then
        "$probe" profile "$main" >"$dir/main.json" 2>"$dir/main.stderr"
        cat "/proc/$main/smaps_rollup" >"$dir/main.smaps_rollup"
    fi
    for pid in $(pgrep -P "$main" efl_webprocess 2>/dev/null); do
        for child in $(pgrep -P "$pid" efl_webprocess 2>/dev/null); do
            [ -r "/proc/$child/cmdline" ] || continue
            if tr '\000' ' ' <"/proc/$child/cmdline" | grep -q -- '--type=renderer'; then
                echo "$child" >"$dir/renderer.pid"
                "$probe" profile "$child" >"$dir/renderer.json" 2>"$dir/renderer.stderr"
                cat "/proc/$child/smaps_rollup" >"$dir/renderer.smaps_rollup"
            fi
        done
    done
    ps -eo pid,ppid,user,group,stat,etimes,args | grep -E 'PID|AppUIC|efl_webprocess' | grep -v grep >"$dir/processes.txt"
}

systemctl stop "$unit.service" 2>/dev/null || true
pkill -TERM -x AppUIC 2>/dev/null || true
sleep 2
dlogutil --monitor -v time '*:V' >"$out/dlog_full.txt" 2>"$out/dlog.err" &
dlog_pid=$!
sleep 1
{
    date -Ins
    echo "requested_url=$url"
    echo "heavy_profile_at=12s"
    echo "page_navigates_about_blank_at=20s"
    echo "blank_profile_at=32s"
} >"$out/run.txt"
systemd-run --no-block --collect --unit="$unit" --uid=owner --gid=users \
    -p SupplementaryGroups=display \
    -E XDG_RUNTIME_DIR=/run/user/5001 -E WAYLAND_DISPLAY=wayland-0 \
    -E HOME='/opt/usr/home/<USER>' \
    /usr/apps/AppK/bin/AppUIC -v -n "$url" \
    >"$out/launch.stdout" 2>"$out/launch.stderr"
echo "LAUNCH_EXIT=$?" >>"$out/run.txt"
sleep 12
profile_phase heavy
sleep 20
profile_phase blank
{
    command -v lldb || echo MISSING:lldb
    command -v gdb || echo MISSING:gdb
    echo "malloc_info=NOT_COLLECTED_NO_INJECTION_INTERFACE"
} >"$out/malloc_info_status.txt"
systemctl stop "$unit.service" >"$out/stop.txt" 2>&1 || true
sleep 3
kill "$dlog_pid" 2>/dev/null || true
wait "$dlog_pid" 2>/dev/null || true
grep -iE 'ewk_view_url_set|LoadProgressChanged|DidFinishLoad|console message|CHROMIUM_HEAVY|CHROMIUM_NAVIGATING|Permission denied|FATAL|NETWORK ERROR' \
    "$out/dlog_full.txt" >"$out/dlog_focus.txt" 2>&1 || true
{
    systemctl is-active display-manager
    systemctl show display-manager -p MainPID -p NRestarts -p ActiveState -p SubState
    app_launcher -S AppQ 2>&1
    app_launcher -S AppX 2>&1
    systemctl status "$unit.service" --no-pager 2>&1 || true
} >"$out/health_after.txt" 2>&1
echo B4_DONE
