#!/bin/sh

kernel=$(uname -r)
case "$kernel" in
    *rpi4*) ;;
    *) echo "ABORT: not RPI4, kernel=$kernel" >&2; exit 97 ;;
esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

rep=$1
case "$rep" in 1|2|3) ;; *) echo "ABORT: rep must be 1..3" >&2; exit 96;; esac
root=/root/l6gstprobe
out="$root/single/rep$rep"
test ! -e "$out" || { echo "ABORT: output exists: $out" >&2; exit 95; }
mkdir -p "$out"
export LD_LIBRARY_PATH="$root/lldb/lib"
pid=

cleanup_child()
{
    if test -n "$pid" && kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
    fi
}
trap cleanup_child EXIT HUP INT TERM

wait_marker()
{
    wanted=$1
    timeout_ticks=$2
    ticks=0
    while test "$ticks" -lt "$timeout_ticks"; do
        grep -F "$wanted" "$out/program_stdout.txt" >/dev/null 2>&1 && return 0
        kill -0 "$pid" 2>/dev/null || return 2
        sleep 0.10
        ticks=$((ticks + 1))
    done
    return 1
}

capture()
{
    capture_point=$1
    file="$out/$capture_point.txt"
    {
        echo "point=$capture_point epoch=$(date +%s) uptime=$(cut -d ' ' -f1 /proc/uptime) pid=$pid"
        if kill -0 "$pid" 2>/dev/null; then echo ALIVE=1; else echo ALIVE=0; fi
        echo '## profile'
        "$root/reclaim_probe" profile "$pid"
        echo '## smaps_rollup'
        cat "/proc/$pid/smaps_rollup"
        echo '## stat'
        cat "/proc/$pid/stat"
        echo '## stat_faults'
        awk '{print "minflt=" $10 " majflt=" $12}' "/proc/$pid/stat"
        echo '## free'
        free
        echo '## swaps'
        cat /proc/swaps
        echo '## zram_mm_stat'
        cat /sys/block/zram0/mm_stat 2>&1
        echo '## allocator_maps'
        grep -Ei 'tcmalloc|jemalloc|mimalloc|scudo' "/proc/$pid/maps" || echo ALLOCATOR_SO_NONE
    } >"$file" 2>&1
}

{
    echo "rep=$rep"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    echo "command=$root/gst_loop_decode $root/small_320x240.mp4 2 20 30"
    echo "start=$(date -Ins 2>/dev/null || date)"
    echo "uptime_start=$(cut -d ' ' -f1 /proc/uptime)"
} >"$out/run_record.txt"
dmesg | tail -240 >"$out/dmesg_before.txt" 2>&1

"$root/gst_loop_decode" "$root/small_320x240.mp4" 2 20 30 \
    >"$out/program_stdout.txt" 2>"$out/program_stderr.txt" &
pid=$!
echo "pid=$pid" >>"$out/run_record.txt"

wait_marker 'cycle=0 state=PROCESS_READY' 50
ready_rc=$?
echo "ready_marker_rc=$ready_rc" >>"$out/run_record.txt"
test "$ready_rc" -eq 0 || exit 20
capture T0

wait_marker 'cycle=1 state=PLAYING_START' 150
playing1_rc=$?
echo "playing1_marker_rc=$playing1_rc" >>"$out/run_record.txt"
test "$playing1_rc" -eq 0 || exit 21
sleep 5
capture T1a
sleep 8
capture T1b

wait_marker 'cycle=1 state=NULL_DONE' 150
null1_rc=$?
echo "null1_marker_rc=$null1_rc" >>"$out/run_record.txt"
test "$null1_rc" -eq 0 || exit 22
sleep 5
capture T2

lldb="$root/lldb/bin/lldb"
"$lldb" -b \
    -o "process attach --pid $pid" \
    -o 'thread list' \
    -o 'bt all' \
    -o 'detach' >"$out/lldb_threads_all.txt" 2>&1
threads_rc=$?
echo "lldb_threads_rc=$threads_rc" >>"$out/run_record.txt"

"$lldb" -b \
    -o "process attach --pid $pid" \
    -o 'thread select 1' \
    -o 'bt' \
    -o 'detach' >"$out/lldb_selected_thread.txt" 2>&1
selected_rc=$?
echo "lldb_selected_rc=$selected_rc" >>"$out/run_record.txt"

if grep -Eiq 'malloc|calloc|realloc|free|arena' "$out/lldb_selected_thread.txt"; then
    echo 'INJECTION_SKIPPED=selected thread contains allocator frame' >"$out/lldb_inject.txt"
    inject_rc=90
else
    mi="$out/malloc_info.xml"
    before=$(cut -d ' ' -f1 /proc/uptime)
    "$lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread select 1' \
        -o 'bt' \
        -o "expr -t 5000000 -- void *\$fp = (void *)fopen(\"$mi\", \"w\")" \
        -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
        -o 'expr -t 5000000 -- (int)fflush($fp)' \
        -o 'expr -t 5000000 -- (int)fclose($fp)' \
        -o 'expr -t 5000000 -- (int)malloc_trim(0)' \
        -o 'detach' >"$out/lldb_inject.txt" 2>&1
    inject_rc=$?
    after=$(cut -d ' ' -f1 /proc/uptime)
    echo "uptime_before=$before uptime_after=$after" >>"$out/lldb_inject.txt"
fi
echo "lldb_inject_rc=$inject_rc" >>"$out/run_record.txt"
capture T4

wait_marker 'cycle=2 state=PLAYING_START' 400
playing2_rc=$?
echo "playing2_marker_rc=$playing2_rc" >>"$out/run_record.txt"
if test "$playing2_rc" -eq 0; then
    sleep 5
    capture T5
else
    inject_rc=91
fi

if kill -0 "$pid" 2>/dev/null; then echo ALIVE_AFTER_T5=1; else echo ALIVE_AFTER_T5=0; fi >>"$out/run_record.txt"
kill -TERM "$pid" 2>/dev/null
wait "$pid" 2>/dev/null
if kill -0 "$pid" 2>/dev/null; then echo CLEANUP_ALIVE=1; else echo CLEANUP_ALIVE=0; fi >"$out/cleanup.txt"

dmesg | tail -300 >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1
{
    echo "inject_rc=$inject_rc"
    echo "end=$(date -Ins 2>/dev/null || date)"
    echo "uptime_end=$(cut -d ' ' -f1 /proc/uptime)"
} >>"$out/run_record.txt"
echo "EXIT=$inject_rc" >"$out/DONE"
exit "$inject_rc"
