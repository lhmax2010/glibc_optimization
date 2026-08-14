#!/bin/sh

kernel=$(uname -r)
case "$kernel" in
    *rpi4*) ;;
    *) echo "ABORT: not RPI4, kernel=$kernel" >&2; exit 97 ;;
esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image detected" >&2
    exit 98
fi

set +e
out=/root/l6tfprobe/chromium_ub_pre
rm -rf "$out"
mkdir -p "$out"
for old in $(pgrep -x AppUIC); do
    oldpg=$(awk '{print $5}' "/proc/$old/stat" 2>/dev/null)
    [ -n "$oldpg" ] && kill -TERM "-$oldpg" 2>/dev/null
done
sleep 2
cp /root/l6tfprobe/chromium_heavy.html /tmp/l6_chromium_heavy.html
chmod 644 /tmp/l6_chromium_heavy.html

export HOME=/var/lib/enlightenment
export XDG_RUNTIME_DIR=/run
export WAYLAND_DISPLAY=wayland-0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/5001/bus

setsid /usr/apps/AppK/bin/AppUIC \
    file:///tmp/l6_chromium_heavy.html </dev/null >"$out/browser.log" 2>&1 &
wrapper=$!
sleep 1
p=$(pgrep -n -x AppUIC)
pg=$(awk '{print $5}' "/proc/$p/stat" 2>/dev/null)
echo "$wrapper" >"$out/wrapper.pid"
echo "$p" >"$out/main.pid"
echo "$pg" >"$out/process_group"

sample()
{
    point=$1
    file="$out/$point.txt"
    {
        echo "date=$(date +%s) POINT=$point MAIN=$p"
        if kill -0 "$p" 2>/dev/null; then
            echo MAIN_ALIVE=1
        else
            echo MAIN_ALIVE=0
        fi
        pstree -ap "$p"
        for q in "$p" $(pgrep -x efl_webprocess); do
            [ -r "/proc/$q/stat" ] || continue
            qpg=$(awk '{print $5}' "/proc/$q/stat")
            [ "$q" = "$p" ] || [ "$qpg" = "$pg" ] || continue
            echo "## PID=$q PGID=$qpg"
            tr '\0' ' ' <"/proc/$q/cmdline"
            echo
            /root/l6tfprobe/reclaim_probe profile "$q"
        done
    } >"$file" 2>&1
}

sample baseline_1s
sleep 7
sample heavy_8s
sleep 7
sample heavy_15s
sleep 20
sample released_35s
sleep 30
sample survival_65s

{
    if kill -0 "$p" 2>/dev/null; then
        echo ALIVE_AFTER_65=1
    else
        echo ALIVE_AFTER_65=0
    fi
    echo "## browser log"
    sed -n '1,320p' "$out/browser.log"
    echo "## dlog evidence"
    dlogutil -v time -d 2>/dev/null |
        grep -E "$p|l6_chromium_heavy|L6_BASELINE|L6_HEAVY|L6_RELEASED|file:///tmp" |
        tail -320
} >"$out/load_evidence.txt" 2>&1

kill -TERM "-$pg" 2>/dev/null
sleep 2
kill -KILL "-$pg" 2>/dev/null
wait "$p" 2>/dev/null
rm -f /tmp/l6_chromium_heavy.html
exit 0
