#!/bin/sh

set -u
. /root/l6uirelease/probe_common.sh

out="$root/runs/chromium/blocked_attempt"
test ! -e "$out" || { echo "ABORT: output exists: $out" >&2; exit 96; }
mkdir -p "$out"

main=
cleanup()
{
    if test -n "$main" && kill -0 "$main" 2>/dev/null; then
        kill -TERM "$main" 2>/dev/null || true
        sleep 4
        kill -0 "$main" 2>/dev/null && kill -KILL "$main" 2>/dev/null || true
    fi
    for child in $(pgrep -f 'efl_webprocess.*l6_ui_heavy_release' 2>/dev/null); do
        kill -TERM "$child" 2>/dev/null || true
    done
}
trap cleanup EXIT HUP INT TERM

{
    echo "start=$(date -Ins)"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    rpm -q glibc
    echo 'command=AppUIC -v -n file:///tmp/l6_ui_heavy_release.html'
} >"$out/run_record.txt"
dmesg | tail -300 >"$out/dmesg_before.txt" 2>&1

export DBUS_SESSION_BUS_ADDRESS='kernel:path=/sys/fs/kdbus/5001-user/bus;unix:path=/run/user/5001/bus'
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/run/user/5001
export ELM_DISPLAY=wl
export ELM_ENGINE=wayland_egl
export ELM_PROFILE=common
export ELM_SCALE=1.8
export ECORE_IMF_MODULE=wayland
export TIZEN_WAYLAND_SHM_DIR=/run/.efl
export HOME='/opt/usr/home/<USER>'
export USER=owner
export LOGNAME=owner
export LANG=en_US.UTF-8

/usr/apps/AppK/bin/AppUIC -v -n \
    file:///tmp/l6_ui_heavy_release.html >"$out/AppUIC_stdout.txt" 2>"$out/AppUIC_stderr.txt" &
main=$!
echo "main_pid=$main" >>"$out/run_record.txt"
sleep 12
renderer=$(pgrep -f 'efl_webprocess --type=renderer.*l6_ui_heavy_release' | head -1)
echo "renderer_pid=$renderer" >>"$out/run_record.txt"
capture_point "$main" P12_main "$out"
if test -n "$renderer"; then capture_point "$renderer" P12_renderer "$out"; fi

sleep 25
capture_point "$main" P37_main "$out"
if test -n "$renderer" && kill -0 "$renderer" 2>/dev/null; then
    capture_point "$renderer" P37_renderer "$out"
fi
dlogutil -v time -d 2>/dev/null | grep -E "CHROMIUM\\(($main|$renderer)\\)" >"$out/chromium_dlog.txt" || true
{
    grep -E 'ewk_view_url_set|LoadProgressChanged|DidFinishLoad|StartJob url|L6_UI' "$out/chromium_dlog.txt" || true
} >"$out/load_evidence.txt"

if grep -E 'LoadProgressChanged.*progress : 1([^0-9]|$)' "$out/load_evidence.txt" >/dev/null 2>&1; then
    echo LOAD_PROGRESS_1=1 >>"$out/run_record.txt"
else
    echo LOAD_PROGRESS_1=0 >>"$out/run_record.txt"
fi
if grep -E 'about:blank#L6_UI_RELEASED|L6_UI_RELEASED' "$out/load_evidence.txt" >/dev/null 2>&1; then
    echo RELEASE_NAVIGATION_VERIFIED=1 >>"$out/run_record.txt"
else
    echo RELEASE_NAVIGATION_VERIFIED=0 >>"$out/run_record.txt"
fi

cleanup
trap - EXIT HUP INT TERM
health_snapshot "$out/health_after.txt"
dmesg | tail -500 >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1 || true
echo "end=$(date -Ins) EXIT=0" >>"$out/run_record.txt"
touch "$out/DONE"
