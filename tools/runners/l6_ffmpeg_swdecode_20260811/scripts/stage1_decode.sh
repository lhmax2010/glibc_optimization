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

label=$1
input=$2
root=/root/l6ffmpeg_probe
out="$root/stage1/$label"
test ! -e "$out" || { echo "ABORT: output exists: $out" >&2; exit 96; }
mkdir -p "$out/samples"

case "$label" in
    original_960x640)
        pipeline="gst-launch-1.0 -q filesrc location=$input ! qtdemux name=d d.video_0 ! queue ! h264parse ! avdec_h264 ! fakesink sync=false"
        initial_delay=1
        middle_delay=8
        tail_delay=1
        max_tail=40
        ;;
    small_320x240)
        pipeline="gst-launch-1.0 -q filesrc location=$input ! qtdemux name=d d.video_0 ! queue ! mpeg4videoparse ! avdec_mpeg4 ! fakesink sync=false"
        initial_delay=0.05
        middle_delay=0.15
        tail_delay=0.10
        max_tail=100
        ;;
    *) echo "ABORT: unknown label: $label" >&2; exit 95 ;;
esac

{
    echo "label=$label"
    echo "input=$input"
    echo "pipeline=$pipeline"
    echo "kernel=$kernel"
    grep -E 'PRETTY_NAME|BUILD_ID' /etc/os-release
    echo "start=$(date -Ins 2>/dev/null || date)"
    echo "uptime_start=$(cut -d ' ' -f1 /proc/uptime)"
} >"$out/run_record.txt"
dmesg | tail -200 >"$out/dmesg_before.txt" 2>&1

capture()
{
    sample_point=$1
    sample_seq=$2
    file="$out/samples/${sample_seq}_${sample_point}.txt"
    {
        echo "point=$sample_point seq=$sample_seq epoch=$(date +%s) uptime=$(cut -d ' ' -f1 /proc/uptime) pid=$pid"
        if kill -0 "$pid" 2>/dev/null; then echo ALIVE=1; else echo ALIVE=0; fi
        echo '## profile'
        "$root/reclaim_probe" profile "$pid"
        echo '## smaps_rollup'
        cat "/proc/$pid/smaps_rollup"
        echo '## stat_faults'
        awk '{print "minflt=" $10 " majflt=" $12}' "/proc/$pid/stat"
        echo '## allocator_maps'
        grep -Ei 'tcmalloc|jemalloc|mimalloc|scudo' "/proc/$pid/maps" || echo ALLOCATOR_SO_NONE
    } >"$file" 2>&1
    printf '%s\t%s\t%s\n' "$sample_seq" "$sample_point" "$file" >>"$out/sample_index.tsv"
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
capture T0 000
kill -CONT "$pid" 2>/dev/null

sleep "$initial_delay"
kill -0 "$pid" 2>/dev/null && capture T1a 001
sleep "$middle_delay"
kill -0 "$pid" 2>/dev/null && capture T1b 002

i=0
seq=3
while kill -0 "$pid" 2>/dev/null && test "$i" -lt "$max_tail"; do
    capture "tail_$i" "$(printf '%03d' "$seq")"
    sleep "$tail_delay"
    i=$((i + 1))
    seq=$((seq + 1))
done

wait "$pid"
pipeline_rc=$?
{
    echo "pipeline_rc=$pipeline_rc"
    echo "end=$(date -Ins 2>/dev/null || date)"
    echo "uptime_end=$(cut -d ' ' -f1 /proc/uptime)"
    echo "tail_samples=$i"
} >>"$out/run_record.txt"

dmesg | tail -240 >"$out/dmesg_after.txt" 2>&1
grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' \
    "$out/dmesg_after.txt" >"$out/dmesg_alerts.txt" 2>&1
echo "EXIT=$pipeline_rc" >"$out/DONE"
exit "$pipeline_rc"
