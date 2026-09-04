#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/tizen_native_evidence_20260904
asset="$work/small_320x240.mp4"
trim_script="$work/trim_via_gdb.sh"
log="$work/command_log.txt"
samples="$work/samples.tsv"
cells="$work/cells.tsv"
gst_pid=
app_id=attach-panel-gallery
start_rc=0
phase=${NATIVE_PHASE:-all}

mark()
{
    printf '%s\n' "$*" | tee -a "$log"
}

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "$gst_pid" ] && kill -0 "$gst_pid" 2>/dev/null; then
        kill "$gst_pid" 2>/dev/null || true
        wait "$gst_pid" 2>/dev/null || true
    fi
    app_launcher -t "$app_id" >/dev/null 2>&1 || true
    for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
        [ -w "$p" ] && printf '%s\n' schedutil >"$p"
    done
    exit "$rc"
}
trap finish EXIT HUP INT TERM

fail()
{
    mark "FAIL_NATIVE_CONTROLLER reason=$1"
    exit 1
}

sample_one()
{
    sample_label=$1
    sample_pid=$2
    [ -r "/proc/$sample_pid/smaps" ] || return 1
    classes=$(awk '
      function flush_mapping(  len,anon) {
        if (!have_mapping) return
        len=end-start
        anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
        if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) g+=pd
        else if (substr(perms,2,1)=="w" && anon) o+=pd
        else f+=pd
        have_mapping=0
      }
      /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
        flush_mapping(); split($1,a,"-"); start=("0x" a[1])+0; end=("0x" a[2])+0; perms=$2
        name=""; for (i=6;i<=NF;i++) name=name (i==6?"":" ") $i
        pd=0; have_mapping=1; next
      }
      /^Private_Dirty:/ {pd=$2; next}
      END {flush_mapping(); printf "%d %d %d %d",g,o,f,g+o+f}
    ' "/proc/$sample_pid/smaps") || return 1
    set -- $classes
    [ "$#" -eq 4 ] || return 1
    g=$1; o=$2; f=$3; total=$4
    stat_payload=$(sed 's/^[^)]*) //' "/proc/$sample_pid/stat") || return 1
    set -- $stat_payload
    [ "$#" -ge 20 ] || return 1
    minflt=$8; majflt=${10}; starttime=${20}
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$sample_label" "$(date -Ins)" "$(date +%s%N)" "$sample_pid" "$starttime" \
        "$g" "$o" "$f" "$total" "$minflt" "$majflt" >>"$samples"
}

save_memps()
{
    memps_label=$1
    memps_pid=$2
    out="$work/memps_${memps_label}.txt"
    memps "$memps_pid" >"$out" 2>&1
    rc=$?
    printf 'RC=%s\n' "$rc" >>"$out"
    if [ "$rc" -eq 0 ]; then printf 'DONE_MEMPS_%s\n' "$memps_label" >>"$out"; else printf 'FAIL_MEMPS_%s\n' "$memps_label" >>"$out"; fi
    [ "$rc" -eq 0 ]
}

memps_heap()
{
    awk '$NF=="[heap]" {sum+=$4} END {print sum+0}' "$1"
}

inject_trim()
{
    trim_label=$1
    trim_pid=$2
    out="$work/gdb_trim_${trim_label}.txt"
    begin=$(date +%s%N)
    "$trim_script" "$trim_pid" >"$out" 2>&1
    rc=$?
    end=$(date +%s%N)
    elapsed=$(awk -v a="$begin" -v b="$end" 'BEGIN {printf "%.6f",(b-a)/1000000}')
    ret=$(awk '/^\$[0-9]+ = [01]$/ {v=$3} END {if (v=="") v="NA"; print v}' "$out")
    printf 'RC=%s\n' "$rc" >>"$out"
    if [ "$rc" -eq 0 ] && [ "$ret" != NA ]; then
        printf 'DONE_GDB_TRIM_%s\n' "$trim_label" >>"$out"
    else
        printf 'FAIL_GDB_TRIM_%s\n' "$trim_label" >>"$out"
        return 1
    fi
    printf '%s %s\n' "$ret" "$elapsed"
}

inject_malloc_info()
{
    info_label=$1
    info_pid=$2
    xml="$work/malloc_info_${info_label}.xml"
    cmds="$work/gdb_malloc_info_${info_label}.commands"
    out="$work/gdb_malloc_info_${info_label}.txt"
    {
        printf 'set pagination off\n'
        printf 'set $stream = (void *) fopen("%s", "w")\n' "$xml"
        printf 'call (int) malloc_info(0, $stream)\n'
        printf 'call (int) fclose($stream)\n'
        printf 'detach\n'
    } >"$cmds" || return 1
    gdb -p "$info_pid" -batch -x "$cmds" >"$out" 2>&1
    rc=$?
    printf 'RC=%s\n' "$rc" >>"$out"
    if [ "$rc" -eq 0 ] && [ -s "$xml" ] && grep -q '</malloc>' "$xml"; then
        printf 'DONE_GDB_MALLOC_INFO_%s\n' "$info_label" >>"$out"
        return 0
    fi
    printf 'FAIL_GDB_MALLOC_INFO_%s\n' "$info_label" >>"$out"
    return 1
}

wait_interval()
{
    prior=$1
    interval=$2
    [ "$prior" -eq 0 ] && return 0
    now=$(date +%s)
    due=$((prior + interval))
    [ "$now" -ge "$due" ] || sleep $((due - now))
}

run_cell()
{
    cell_group=$1
    cell_label=$2
    cell_pid=$3
    sample_one "${cell_label}_pre" "$cell_pid" || return 1
    save_memps "${cell_label}_pre" "$cell_pid" || return 1
    pre_memps=$(memps_heap "$work/memps_${cell_label}_pre.txt") || return 1
    pre_line=$(tail -n 1 "$samples")
    pre_g=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $6}')
    pre_min=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $10}')
    pre_maj=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $11}')
    starttime=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $5}')
    before_buffers=NA
    if [ "$cell_group" = T1 ]; then before_buffers=$(grep -c 'last-message = chain' "$work/gst_pipeline.log" 2>/dev/null || true); fi
    trim_data=$(inject_trim "$cell_label" "$cell_pid") || return 1
    set -- $trim_data
    [ "$#" -eq 2 ] || return 1
    trim_ret=$1; trim_ms=$2
    sample_one "${cell_label}_post" "$cell_pid" || return 1
    save_memps "${cell_label}_post" "$cell_pid" || return 1
    post_memps=$(memps_heap "$work/memps_${cell_label}_post.txt") || return 1
    post_line=$(tail -n 1 "$samples")
    post_g=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $6}')
    post_min=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $10}')
    post_maj=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $11}')
    post_start=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $5}')
    [ "$post_start" = "$starttime" ] || return 1
    after_buffers=NA
    if [ "$cell_group" = T1 ]; then after_buffers=$(grep -c 'last-message = chain' "$work/gst_pipeline.log" 2>/dev/null || true); fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$cell_group" "$cell_label" "$cell_pid" "$starttime" "$pre_g" "$post_g" "$pre_memps" "$post_memps" \
        "$trim_ret" "$trim_ms" "$pre_min" "$post_min" "$pre_maj" "$post_maj" "$before_buffers" "$after_buffers" >>"$cells"
}

mkdir -p "$work/health" || fail mkdir_health
: >"$log"
printf 'label\ttimestamp\tepoch_ns\tpid\tstarttime_ticks\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\n' >"$samples" || fail samples_header
printf 'group\tcell\tpid\tstarttime_ticks\tproject_pre_kb\tproject_post_kb\tmemps_pre_heap_kb\tmemps_post_heap_kb\ttrim_ret\tinjection_ms\tminflt_pre\tminflt_post\tmajflt_pre\tmajflt_post\tbuffers_pre\tbuffers_post\n' >"$cells" || fail cells_header

kernel=$(uname -r); rc=$?; mark "kernel=$kernel"; mark "RC=$rc"; [ "$rc" -eq 0 ] && case "$kernel" in *rpi4*) :;; *) fail kernel;; esac; mark DONE_GATE_KERNEL
arch=$(uname -m); rc=$?; mark "arch=$arch"; mark "RC=$rc"; [ "$rc" -eq 0 ] && [ "$arch" = armv7l ] || fail arch; mark DONE_GATE_ARCH
build=$(awk -F= '/^BUILD_ID=/{print $2; exit}' /etc/os-release); rc=$?; mark "BUILD_ID=$build"; mark "RC=$rc"; [ "$rc" -eq 0 ] && [ "$build" = tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l ] || fail build_id; mark DONE_GATE_BUILD_ID
glibc=$(rpm -q glibc); rc=$?; mark "$glibc"; mark "RC=$rc"; [ "$rc" -eq 0 ] && [ "$glibc" = glibc-2.40-1.6.armv7l ] || fail glibc; mark DONE_GATE_GLIBC
memtotal=$(awk '/^MemTotal:/{print $2}' /proc/meminfo); rc=$?; mark "MemTotal_kB=$memtotal"; mark "RC=$rc"; [ "$rc" -eq 0 ] && [ "$memtotal" = 8117408 ] || fail memtotal; mark DONE_GATE_MEMTOTAL
[ "$(id -u)" -eq 0 ] || fail root
command -v gdb >/dev/null 2>&1 || fail gdb
command -v memps >/dev/null 2>&1 || fail memps
command -v gst-launch-1.0 >/dev/null 2>&1 || fail gst_launch
test "$(sha256sum "$asset" | awk '{print $1}')" = 3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d || fail asset_sha
mark 'RC=0'; mark DONE_ASSET_AND_TOOL_GATES

dmesg >"$work/health/dmesg_before.txt" 2>&1 || fail dmesg_before
cat /sys/block/zram0/mm_stat >"$work/health/zram_before.txt" || fail zram_before
cat /proc/swaps >"$work/health/swaps_before.txt" || fail swaps_before
for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do cat "$p"; done >"$work/health/governor_before.txt" || fail governor_before
for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s\n' performance >"$p" || fail governor_set; done
for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do [ "$(cat "$p")" = performance ] || fail governor_verify; done
mark 'RC=0'; mark DONE_GOVERNOR_PERFORMANCE

case "$phase" in
all)
    gst-launch-1.0 -v multifilesrc location="$asset" start-index=0 stop-index=0 loop=true ! decodebin ! identity name=counter silent=false ! fakesink sync=true >"$work/gst_pipeline.log" 2>&1 &
    gst_pid=$!
    printf '%s\n' "$gst_pid" >"$work/gst_pid.txt"
    sleep 30
    kill -0 "$gst_pid" 2>/dev/null || fail gst_not_alive_after_steady
    grep -q 'last-message = chain' "$work/gst_pipeline.log" || fail gst_no_buffer_evidence
    mark "GST_PID=$gst_pid"; mark 'RC=0'; mark DONE_T1_STEADY
    t1_last=0
    i=1
    while [ "$i" -le 5 ]; do
        wait_interval "$t1_last" 60
        t1_last=$(date +%s)
        run_cell T1 "T1_${i}" "$gst_pid" || fail "T1_${i}"
        mark 'RC=0'; mark "DONE_T1_${i}"
        i=$((i + 1))
    done
    kill -0 "$gst_pid" 2>/dev/null || fail gst_not_alive_after_cells
    grep -q 'ERROR' "$work/gst_pipeline.log" && fail gst_error_log
    kill "$gst_pid" 2>/dev/null || fail gst_term
    wait "$gst_pid" 2>/dev/null || true
    gst_pid=
    mark 'RC=0'; mark DONE_T1_PIPELINE_CLEANUP
    ;;
t2)
    mark 'T1_SKIPPED_REASON=recorded frozen pipeline EOS at 60.100233983 s before T1_2'
    mark 'RC=0'; mark DONE_T1_RECORDED_FAILURE_SKIP
    ;;
*) fail invalid_phase ;;
esac

enlightenment_pid=$(pidof enlightenment 2>/dev/null | awk '{print $1}')
[ -n "$enlightenment_pid" ] || fail enlightenment_absent
[ "$(readlink "/proc/$enlightenment_pid/exe")" = /usr/bin/enlightenment ] || fail enlightenment_exe
printf '%s\n' "$enlightenment_pid" >"$work/enlightenment_pid.txt"
t2_last=0
i=1
while [ "$i" -le 3 ]; do
    wait_interval "$t2_last" 120
    t2_last=$(date +%s)
    inject_malloc_info "T2_E${i}" "$enlightenment_pid" || fail "T2_E${i}_malloc_info"
    run_cell T2 "T2_E${i}" "$enlightenment_pid" || fail "T2_E${i}_trim"
    mark 'RC=0'; mark "DONE_T2_E${i}"
    i=$((i + 1))
done

i=1
while [ "$i" -le 5 ]; do
    app_launcher -s "$app_id" >>"$work/app_activity.log" 2>&1
    rc=$?; printf 'start_%s_RC=%s\n' "$i" "$rc" >>"$work/app_activity.log"; [ "$rc" -eq 0 ] || fail "app_start_$i"
    mark 'RC=0'; mark "DONE_APP_START_${i}"
    sleep 5
    app_launcher -t "$app_id" >>"$work/app_activity.log" 2>&1
    rc=$?; printf 'terminate_%s_RC=%s\n' "$i" "$rc" >>"$work/app_activity.log"; [ "$rc" -eq 0 ] || fail "app_terminate_$i"
    mark 'RC=0'; mark "DONE_APP_TERMINATE_${i}"
    sleep 5
    i=$((i + 1))
done
inject_malloc_info T2_E4 "$enlightenment_pid" || fail T2_E4_malloc_info
run_cell T2 T2_E4 "$enlightenment_pid" || fail T2_E4_trim
mark 'RC=0'; mark DONE_T2_E4

[ "$(readlink "/proc/$enlightenment_pid/exe")" = /usr/bin/enlightenment ] || fail enlightenment_restarted
dmesg >"$work/health/dmesg_after.txt" 2>&1 || fail dmesg_after
cat /sys/block/zram0/mm_stat >"$work/health/zram_after.txt" || fail zram_after
cat /proc/swaps >"$work/health/swaps_after.txt" || fail swaps_after
for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s\n' schedutil >"$p" || fail governor_restore; done
for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do cat "$p"; done >"$work/health/governor_after.txt" || fail governor_after
grep -qv '^schedutil$' "$work/health/governor_after.txt" && fail governor_after_value
mark 'RC=0'; mark DONE_GOVERNOR_RESTORED
mark 'RC=0'; mark DONE_NATIVE_CONTROLLER
trap - EXIT HUP INT TERM
exit 0
