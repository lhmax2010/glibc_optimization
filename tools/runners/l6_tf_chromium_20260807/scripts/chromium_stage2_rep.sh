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

rep=${1:-1}
set +e
root=/root/l6tfprobe
out="$root/chromium_stage2/rep$rep"
rm -rf "$out"
mkdir -p "$out"

for old in $(pgrep -x AppUIC); do
    oldpg=$(awk '{print $5}' "/proc/$old/stat" 2>/dev/null)
    [ -n "$oldpg" ] && kill -TERM "-$oldpg" 2>/dev/null
done
sleep 2

cp "$root/chromium_heavy.html" /tmp/l6_chromium_heavy.html
chmod 644 /tmp/l6_chromium_heavy.html
export HOME=/var/lib/enlightenment
export XDG_RUNTIME_DIR=/run
export WAYLAND_DISPLAY=wayland-0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/5001/bus
export LD_LIBRARY_PATH="$root/lldb/lib"

{
    echo "rep=$rep"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID|TZ_BUILD_PROJECT' /etc/os-release
    echo "start_epoch=$(date +%s)"
    echo "command=/usr/apps/AppK/bin/AppUIC file:///tmp/l6_chromium_heavy.html"
} >"$out/run_record.txt"
dmesg | tail -200 >"$out/dmesg_before.txt" 2>&1

setsid /usr/apps/AppK/bin/AppUIC \
    file:///tmp/l6_chromium_heavy.html </dev/null >"$out/browser.log" 2>&1 &
wrapper=$!
sleep 1
p=$(pgrep -n -x AppUIC)
pg=$(awk '{print $5}' "/proc/$p/stat" 2>/dev/null)
echo "wrapper_pid=$wrapper" >>"$out/run_record.txt"
echo "pid=$p" >>"$out/run_record.txt"
echo "pgid=$pg" >>"$out/run_record.txt"

capture()
{
    point=$1
    file="$out/$point.txt"
    {
        echo "epoch=$(date +%s) point=$point pid=$p"
        if kill -0 "$p" 2>/dev/null; then echo ALIVE=1; else echo ALIVE=0; fi
        echo "## target_profile"
        "$root/reclaim_probe" profile "$p"
        echo "## smaps_rollup"
        cat "/proc/$p/smaps_rollup"
        echo "## stat"
        cat "/proc/$p/stat"
        echo "## stat_faults"
        awk '{print "minflt=" $10 " majflt=" $12}' "/proc/$p/stat"
        echo "## free"
        free
        echo "## swaps"
        cat /proc/swaps
        echo "## zram_mm_stat"
        cat /sys/block/zram0/mm_stat 2>&1
        echo "## process_group_profiles"
        for q in "$p" $(pgrep -x efl_webprocess); do
            [ -r "/proc/$q/stat" ] || continue
            qpg=$(awk '{print $5}' "/proc/$q/stat")
            [ "$q" = "$p" ] || [ "$qpg" = "$pg" ] || continue
            echo "PID=$q PGID=$qpg"
            tr '\0' ' ' <"/proc/$q/cmdline"
            echo
            "$root/reclaim_probe" profile "$q"
        done
    } >"$file" 2>&1
}

capture T0
sleep 7
capture T1a
sleep 7
capture T1b
sleep 20
capture T2

lldb="$root/lldb/bin/lldb"
"$lldb" -b \
    -o "process attach --pid $p" \
    -o 'thread list' \
    -o 'bt all' \
    -o 'detach' >"$out/lldb_threads_all.txt" 2>&1
echo "lldb_threads_rc=$?" >>"$out/run_record.txt"

"$lldb" -b \
    -o "process attach --pid $p" \
    -o 'thread select 1' \
    -o 'bt' \
    -o 'detach' >"$out/lldb_selected_thread.txt" 2>&1
selected_rc=$?
echo "lldb_selected_rc=$selected_rc" >>"$out/run_record.txt"

if grep -Eiq 'malloc|calloc|realloc|free' "$out/lldb_selected_thread.txt"; then
    echo "INJECTION_SKIPPED=selected thread contains allocator frame" >"$out/lldb_inject.txt"
    inject_rc=90
else
    mi="/tmp/mi_chromium_rep${rep}_${p}.xml"
    before=$(awk '{print $1}' /proc/uptime)
    "$lldb" -b \
        -o "process attach --pid $p" \
        -o 'thread select 1' \
        -o 'bt' \
        -o "expr -t 5000000 -- void *\$fp = (void *)fopen(\"$mi\", \"w\")" \
        -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
        -o 'expr -t 5000000 -- (int)fflush($fp)' \
        -o 'expr -t 5000000 -- (int)fclose($fp)' \
        -o 'expr -t 5000000 -- (int)malloc_trim(0)' \
        -o 'detach' >"$out/lldb_inject.txt" 2>&1
    inject_rc=$?
    after=$(awk '{print $1}' /proc/uptime)
    echo "uptime_before=$before uptime_after=$after" >>"$out/lldb_inject.txt"
    if [ -s "$mi" ]; then
        cp "$mi" "$out/malloc_info.xml"
    fi
    rm -f "$mi"
fi
echo "lldb_inject_rc=$inject_rc" >>"$out/run_record.txt"

capture T4
sleep 5
capture T5

{
    if kill -0 "$p" 2>/dev/null; then echo ALIVE_AFTER_T5=1; else echo ALIVE_AFTER_T5=0; fi
    dmesg | tail -240
} >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1

kill -TERM "-$pg" 2>/dev/null
sleep 2
kill -KILL "-$pg" 2>/dev/null
if kill -0 "$p" 2>/dev/null; then echo "CLEANUP_ALIVE=1"; else echo "CLEANUP_ALIVE=0"; fi \
    >"$out/cleanup.txt"
rm -f /tmp/l6_chromium_heavy.html
exit 0
