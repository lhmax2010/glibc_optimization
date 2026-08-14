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
root=/root/l6ffmpeg_probe
out="$root/stage2/small_320x240_rep$rep"
test ! -e "$out" || { echo "ABORT: output exists: $out" >&2; exit 95; }
mkdir -p "$out"
export LD_LIBRARY_PATH="$root/lldb/lib"
pipeline='gst-launch-1.0 -q filesrc location=/root/l6ffmpeg_probe/small_320x240.mp4 ! qtdemux name=d d.video_0 ! queue ! mpeg4videoparse ! avdec_mpeg4 ! fakesink sync=true'

{
    echo "rep=$rep"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    echo "pipeline=$pipeline"
    echo "phase_method=real-time decode; SIGSTOP at about 20 s; no end-of-stream release"
    echo "start=$(date -Ins 2>/dev/null || date)"
    echo "uptime_start=$(cut -d ' ' -f1 /proc/uptime)"
} >"$out/run_record.txt"
dmesg | tail -200 >"$out/dmesg_before.txt" 2>&1

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

sh -c "exec $pipeline" >"$out/pipeline_stdout.txt" 2>"$out/pipeline_stderr.txt" &
pid=$!
echo "pid=$pid" >>"$out/run_record.txt"

i=0
while test "$i" -lt 100; do
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null)
    case "$exe" in *gst-launch-1.0*) break;; esac
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.01
    i=$((i + 1))
done
kill -STOP "$pid" 2>/dev/null
sleep 0.05
capture T0
kill -CONT "$pid" 2>/dev/null

sleep 5
capture T1a
sleep 10
capture T1b
sleep 5
kill -STOP "$pid" 2>/dev/null
sleep 0.10
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

if grep -Eiq 'malloc|calloc|realloc|free' "$out/lldb_selected_thread.txt"; then
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
if kill -0 "$pid" 2>/dev/null; then echo ALIVE_AFTER_T4=1; else echo ALIVE_AFTER_T4=0; fi >>"$out/run_record.txt"

kill -CONT "$pid" 2>/dev/null
kill -TERM "$pid" 2>/dev/null
sleep 1
kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
wait "$pid" 2>/dev/null
if kill -0 "$pid" 2>/dev/null; then echo CLEANUP_ALIVE=1; else echo CLEANUP_ALIVE=0; fi >"$out/cleanup.txt"

dmesg | tail -260 >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1
{
    echo "inject_rc=$inject_rc"
    echo "end=$(date -Ins 2>/dev/null || date)"
    echo "uptime_end=$(cut -d ' ' -f1 /proc/uptime)"
} >>"$out/run_record.txt"
echo "EXIT=$inject_rc" >"$out/DONE"
exit "$inject_rc"
