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

root=/root/l6scaleprobe2
out="$root/multi/run4"
test ! -e "$out" || { echo "ABORT: output exists: $out" >&2; exit 96; }
mkdir -p "$out"
export LD_LIBRARY_PATH="$root/lldb/lib"
pids=

cleanup_all()
{
    for pid in $pids; do
        kill -0 "$pid" 2>/dev/null && kill -TERM "$pid" 2>/dev/null
    done
    sleep 1
    for pid in $pids; do
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
    done
}
trap cleanup_all EXIT HUP INT TERM

wait_marker()
{
    marker_file=$1
    wanted=$2
    timeout_ticks=$3
    ticks=0
    while test "$ticks" -lt "$timeout_ticks"; do
        grep -F "$wanted" "$marker_file" >/dev/null 2>&1 && return 0
        sleep 0.10
        ticks=$((ticks + 1))
    done
    return 1
}

wait_marker_offset()
{
    marker_file=$1
    wanted=$2
    offset=$3
    wait_marker "$marker_file" "$wanted" 500 || return 1
    marker=$(grep -F "$wanted" "$marker_file" | tail -1 |
        sed -n 's/.*monotonic=\([0-9.]*\).*/\1/p')
    now=$(cut -d ' ' -f1 /proc/uptime)
    delay=$(awk -v marker="$marker" -v now="$now" -v offset="$offset" \
        'BEGIN { d = marker + offset - now; if (d < 0) d = 0; printf "%.3f", d }')
    sleep "$delay"
}

capture_process()
{
    lane=$1
    pid=$2
    point=$3
    file="$out/lane$lane/$point.txt"
    {
        echo "lane=$lane point=$point epoch=$(date +%s.%N) uptime=$(cut -d ' ' -f1 /proc/uptime) pid=$pid"
        if kill -0 "$pid" 2>/dev/null; then echo ALIVE=1; else echo ALIVE=0; fi
        echo '## profile'
        "$root/reclaim_probe" profile "$pid"
        echo '## smaps_rollup'
        cat "/proc/$pid/smaps_rollup"
        echo '## stat'
        cat "/proc/$pid/stat"
        echo '## stat_fields'
        awk '{print "state=" $3 " minflt=" $10 " majflt=" $12 " utime=" $14 " stime=" $15}' "/proc/$pid/stat"
        echo '## zram_mm_stat'
        cat /sys/block/zram0/mm_stat
        echo '## free'
        free
    } >"$file" 2>&1
}

capture_system()
{
    point=$1
    {
        echo "point=$point epoch=$(date +%s.%N) uptime=$(cut -d ' ' -f1 /proc/uptime)"
        grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
        free
        cat /proc/swaps
        echo '## zram_mm_stat'
        cat /sys/block/zram0/mm_stat
        echo '## target_states'
        for lane in 1 2 3 4 5 6 7 8; do
            eval pid=\$pid$lane
            if test -n "$pid" && test -r "/proc/$pid/stat"; then
                awk -v lane="$lane" '{print "lane=" lane " pid=" $1 " state=" $3 " minflt=" $10 " majflt=" $12 " utime=" $14 " stime=" $15}' "/proc/$pid/stat"
            else
                echo "lane=$lane pid=$pid MISSING"
            fi
        done
    } >"$out/system_$point.txt" 2>&1
}

malloc_info_only()
{
    lane=$1
    pid=$2
    phase=$3
    laneout="$out/lane$lane"
    mi="$laneout/malloc_info_$phase.xml"
    "$root/lldb/bin/lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread list' \
        -o 'bt all' \
        -o 'thread select 1' \
        -o 'bt' \
        -o "expr -t 5000000 -- void *\$fp = (void *)fopen(\"$mi\", \"w\")" \
        -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
        -o 'expr -t 5000000 -- (int)fflush($fp)' \
        -o 'expr -t 5000000 -- (int)fclose($fp)' \
        -o 'detach' >"$laneout/lldb_$phase.txt" 2>&1
    rc=$?
    echo "lldb_${phase}_rc=$rc" >>"$laneout/run_record.txt"
    return "$rc"
}

malloc_info_and_trim()
{
    lane=$1
    pid=$2
    laneout="$out/lane$lane"
    mi="$laneout/malloc_info_T2.xml"
    before=$(cut -d ' ' -f1 /proc/uptime)
    "$root/lldb/bin/lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread list' \
        -o 'bt all' \
        -o 'thread select 1' \
        -o 'bt' \
        -o 'platform shell date +%s.%N' \
        -o "expr -t 5000000 -- void *\$fp = (void *)fopen(\"$mi\", \"w\")" \
        -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
        -o 'expr -t 5000000 -- (int)fflush($fp)' \
        -o 'expr -t 5000000 -- (int)fclose($fp)' \
        -o 'expr -t 5000000 -- (int)malloc_trim(0)' \
        -o 'platform shell date +%s.%N' \
        -o 'detach' >"$laneout/lldb_T2_trim.txt" 2>&1
    rc=$?
    after=$(cut -d ' ' -f1 /proc/uptime)
    echo "uptime_before=$before uptime_after=$after" >>"$laneout/lldb_T2_trim.txt"
    echo "lldb_T2_trim_rc=$rc" >>"$laneout/run_record.txt"
    return "$rc"
}

{
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    echo 'command=gst_loop_decode small_320x240.mp4 2 20 40'
    echo 'lanes=8 stagger_seconds=1 T1b_offset=13 T2_offset=5'
    echo "start=$(date -Ins) uptime=$(cut -d ' ' -f1 /proc/uptime)"
} >"$out/run_record.txt"
dmesg | tail -300 >"$out/dmesg_before.txt" 2>&1
capture_system PRE_START

for lane in 1 2 3 4 5 6 7 8; do
    laneout="$out/lane$lane"
    mkdir -p "$laneout"
    "$root/gst_loop_decode" "$root/small_320x240.mp4" 2 20 40 \
        >"$laneout/program_stdout.txt" 2>"$laneout/program_stderr.txt" &
    pid=$!
    pids="$pids $pid"
    eval pid$lane=$pid
    {
        echo "lane=$lane pid=$pid"
        echo "launch_epoch=$(date +%s.%N) launch_uptime=$(cut -d ' ' -f1 /proc/uptime)"
    } >"$laneout/run_record.txt"
    wait_marker "$laneout/program_stdout.txt" 'cycle=0 state=PROCESS_READY' 50 || exit 20
    capture_process "$lane" "$pid" T0
    sleep 1
done

t1_jobs=
for lane in 1 2 3 4 5 6 7 8; do
    eval pid=\$pid$lane
    (wait_marker_offset "$out/lane$lane/program_stdout.txt" 'cycle=1 state=PLAYING_START' 13 &&
        capture_process "$lane" "$pid" T1b &&
        malloc_info_only "$lane" "$pid" T1b) &
    t1_jobs="$t1_jobs $!"
done

t2_jobs=
for lane in 1 2 3 4 5 6 7 8; do
    eval pid=\$pid$lane
    (wait_marker_offset "$out/lane$lane/program_stdout.txt" 'cycle=1 state=NULL_DONE' 5 &&
        capture_process "$lane" "$pid" T2) &
    t2_jobs="$t2_jobs $!"
done

for job in $t1_jobs; do wait "$job" || exit 21; done
for job in $t2_jobs; do wait "$job" || exit 22; done
capture_system PRE_TRIM

for lane in 1 2 3 4 5 6 7 8; do
    eval pid=\$pid$lane
    malloc_info_and_trim "$lane" "$pid" || echo "TRIM_FAILED lane=$lane" >>"$out/anomalies.txt"
    capture_process "$lane" "$pid" T4
done
capture_system POST_TRIM

for lane in 1 2; do
    eval pid=\$pid$lane
    if wait_marker_offset "$out/lane$lane/program_stdout.txt" 'cycle=2 state=PLAYING_START' 5; then
        capture_process "$lane" "$pid" T5
    else
        echo "REFAULT_FAILED lane=$lane" >>"$out/anomalies.txt"
    fi
done
capture_system POST_REFAULT

for lane in 1 2 3 4 5 6 7 8; do
    eval pid=\$pid$lane
    if kill -0 "$pid" 2>/dev/null; then echo ALIVE_BEFORE_CLEANUP=1; else echo ALIVE_BEFORE_CLEANUP=0; fi >>"$out/lane$lane/run_record.txt"
done
cleanup_all
trap - EXIT HUP INT TERM
for lane in 1 2 3 4 5 6 7 8; do
    eval pid=\$pid$lane
    if kill -0 "$pid" 2>/dev/null; then echo CLEANUP_ALIVE=1; else echo CLEANUP_ALIVE=0; fi >"$out/lane$lane/cleanup.txt"
done

dmesg | tail -400 >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1
{
    echo "end=$(date -Ins) uptime=$(cut -d ' ' -f1 /proc/uptime)"
    echo EXIT=0
} >>"$out/run_record.txt"
echo EXIT=0 >"$out/DONE"
exit 0
