#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/gst_trim_cost_20260901
bench="$work/gst_loop_decode.armv7l"
probe="$work/reclaim_probe.armv7l"
media="$work/small_320x240.mp4"
sampler="$work/sample_smaps_1s.sh"
control="$work/controller.log"
expected_bench_sha=204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6
expected_probe_sha=3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7
expected_media_sha=3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d
cycles=51
play_seconds=20
null_seconds=1
overall_rc=0
governor_changed=0
after_captured=0
bench_pid=
sampler_pid=

: >"$control" || exit 2

mark()
{
    printf '%s\n' "$*" | tee -a "$control"
}

capture_after()
{
    [ "$after_captured" -eq 0 ] || return 0
    after_captured=1
    date -Ins >"$work/run_end.txt"; rc=$?
    mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_RUN_END || { mark FAIL_RUN_END; overall_rc=92; }
    dmesg >"$work/dmesg_after.txt"; rc=$?
    mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_DMESG_AFTER || { mark FAIL_DMESG_AFTER; overall_rc=93; }
    cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_after.txt"; rc=$?
    mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_ZRAM_AFTER || { mark FAIL_ZRAM_AFTER; overall_rc=94; }
    cat /proc/swaps >"$work/swaps_after.txt"; rc=$?
    mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_SWAPS_AFTER || { mark FAIL_SWAPS_AFTER; overall_rc=95; }
}

restore_governor()
{
    restore_rc=0
    if [ "$governor_changed" -eq 1 ]; then
        for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
            printf '%s\n' schedutil >"$path" || restore_rc=1
        done
    fi
    : >"$work/governor_after.txt"
    for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
        printf '%s=' "$path" >>"$work/governor_after.txt"
        cat "$path" >>"$work/governor_after.txt" || restore_rc=1
    done
    if [ "$restore_rc" -eq 0 ] && [ "$(grep -c '=schedutil$' "$work/governor_after.txt")" -eq 4 ]; then
        mark RC=0; mark DONE_GOVERNOR_RESTORE
    else
        mark "RC=$restore_rc"; mark FAIL_GOVERNOR_RESTORE; overall_rc=91
    fi
}

stop_children()
{
    if [ -n "$bench_pid" ] && kill -0 "$bench_pid" 2>/dev/null; then
        kill -TERM "$bench_pid" 2>/dev/null || true
        wait "$bench_pid" 2>/dev/null || true
    fi
    if [ -n "$sampler_pid" ] && kill -0 "$sampler_pid" 2>/dev/null; then
        kill -TERM "$sampler_pid" 2>/dev/null || true
        wait "$sampler_pid" 2>/dev/null || true
    fi
}

finish()
{
    incoming=$?
    trap - EXIT HUP INT TERM
    stop_children
    [ "$incoming" -eq 0 ] || overall_rc=$incoming
    capture_after
    restore_governor
    mark "RC=$overall_rc"
    if [ "$overall_rc" -eq 0 ]; then mark DONE_GST_TRIM_CONTROLLER; else mark FAIL_GST_TRIM_CONTROLLER; fi
    exit "$overall_rc"
}

wait_marker()
{
    stdout_file=$1
    wanted=$2
    timeout_ticks=$3
    ticks=0
    while [ "$ticks" -lt "$timeout_ticks" ]; do
        grep -F "$wanted" "$stdout_file" >/dev/null 2>&1 && return 0
        kill -0 "$bench_pid" 2>/dev/null || return 2
        sleep 0.10
        ticks=$((ticks + 1))
    done
    return 1
}

capture_point()
{
    out=$1
    cycle=$2
    phase=$3
    json="$out/cycle_$(printf '%02d' "$cycle")_${phase}.json"
    meta="$out/cycle_$(printf '%02d' "$cycle")_${phase}.txt"
    "$probe" profile "$bench_pid" >"$json" 2>"$out/cycle_$(printf '%02d' "$cycle")_${phase}.stderr" || return 1
    stat_payload=$(sed 's/^[^)]*) //' "/proc/$bench_pid/stat") || return 1
    set -- $stat_payload
    [ "$#" -ge 10 ] || return 1
    {
        printf 'cycle=%s\nphase=%s\n' "$cycle" "$phase"
        printf 'timestamp=%s\n' "$(date -Ins)"
        printf 'uptime=%s\n' "$(cut -d ' ' -f1 /proc/uptime)"
        printf 'pid=%s\nminflt=%s\nmajflt=%s\n' "$bench_pid" "$8" "${10}"
        printf 'RC=0\nDONE_CAPTURE_%s\n' "$phase"
    } >"$meta"
}

run_cell()
{
    arm=$1
    rep=$2
    order=$3
    cell_name=$(printf '%02d_%s_rep%s' "$order" "$arm" "$rep")
    out="$work/cells/$cell_name"
    mkdir -p "$out" || return 40
    fifo="$out/control.fifo"
    mkfifo "$fifo" || return 41
    exec 3<>"$fifo" || return 42
    {
        printf 'order=%s\narm=%s\nrep=%s\ncycles=%s\nplay_seconds=%s\nnull_seconds=%s\n' \
          "$order" "$arm" "$rep" "$cycles" "$play_seconds" "$null_seconds"
        printf 'CMD=%s %s %s %s %s %s control-stdin\n' "$bench" "$media" "$cycles" "$play_seconds" "$null_seconds" "$arm"
    } >"$out/command.txt"
    date -Ins >"$out/start.txt" || return 43
    "$bench" "$media" "$cycles" "$play_seconds" "$null_seconds" "$arm" control-stdin \
      <"$fifo" >"$out/program_stdout.txt" 2>"$out/program_stderr.txt" &
    bench_pid=$!
    printf '%s\n' "$bench_pid" >"$out/pid.txt"
    "$sampler" "$bench_pid" "$out/external_1s.tsv" "$out/external_sampler_meta.txt" \
      >"$out/external_sampler_stdout.txt" 2>"$out/external_sampler_stderr.txt" &
    sampler_pid=$!

    wait_marker "$out/program_stdout.txt" 'cycle=0 state=PROCESS_READY' 100 || return 44
    cycle=1
    while [ "$cycle" -le "$cycles" ]; do
        wait_marker "$out/program_stdout.txt" "cycle=$cycle state=RELEASE_READY" 500 || return 45
        capture_point "$out" "$cycle" pre || return 46
        printf 'PRE_CAPTURED\n' >&3 || return 47
        wait_marker "$out/program_stdout.txt" "TRIM_METRIC cycle=$cycle " 100 || return 48
        wait_marker "$out/program_stdout.txt" "cycle=$cycle state=RELEASE_DONE" 100 || return 49
        capture_point "$out" "$cycle" post || return 50
        printf 'POST_CAPTURED\n' >&3 || return 51
        wait_marker "$out/program_stdout.txt" "cycle=$cycle state=CYCLE_DONE" 100 || return 52
        cycle=$((cycle + 1))
    done

    wait "$bench_pid"; bench_rc=$?
    wait "$sampler_pid"; sampler_rc=$?
    bench_pid=; sampler_pid=
    exec 3>&-
    rm -f "$fifo" || return 53
    date -Ins >"$out/end.txt"
    printf 'bench_rc=%s\nsampler_rc=%s\n' "$bench_rc" "$sampler_rc" >"$out/exit_status.txt"
    cycle_metrics=$(grep -c '^CYCLE_METRIC ' "$out/program_stdout.txt")
    trim_metrics=$(grep -c '^TRIM_METRIC ' "$out/program_stdout.txt")
    pre_json=$(find "$out" -type f -name 'cycle_*_pre.json' | wc -l)
    post_json=$(find "$out" -type f -name 'cycle_*_post.json' | wc -l)
    sampler_samples=$(awk -F= '/^samples=/{print $2; exit}' "$out/external_sampler_meta.txt" 2>/dev/null)
    sampler_meta_ok=0
    case "$sampler_samples" in ''|*[!0-9]*) ;; *)
        if [ "$sampler_samples" -gt 0 ] && grep -Fx RC=0 "$out/external_sampler_meta.txt" >/dev/null 2>&1 \
          && grep -Fx DONE_EXTERNAL_SAMPLER "$out/external_sampler_meta.txt" >/dev/null 2>&1; then sampler_meta_ok=1; fi;; esac
    mark "cell=$cell_name bench_rc=$bench_rc sampler_rc=$sampler_rc cycle_metrics=$cycle_metrics trim_metrics=$trim_metrics pre_json=$pre_json post_json=$post_json samples=${sampler_samples:-NA} sampler_meta_ok=$sampler_meta_ok"
    if [ "$bench_rc" -ne 0 ] || [ "$sampler_rc" -ne 0 ] || [ "$sampler_meta_ok" -ne 1 ] \
      || [ "$cycle_metrics" -ne "$cycles" ] || [ "$trim_metrics" -ne "$cycles" ] \
      || [ "$pre_json" -ne "$cycles" ] || [ "$post_json" -ne "$cycles" ]; then
        mark RC=1; mark "FAIL_CELL_$cell_name"; return 54
    fi
    mark RC=0; mark "DONE_CELL_$cell_name"
}

kernel=$(uname -r); rc=$?; mark "kernel=$kernel"; mark "RC=$rc"
case "$kernel" in *rpi4*) mark DONE_CONTROLLER_UNAME_R;; *) mark FAIL_CONTROLLER_UNAME_R; exit 10;; esac
arch=$(uname -m); rc=$?; mark "arch=$arch"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$arch" = armv7l ] || { mark FAIL_CONTROLLER_UNAME_M; exit 11; }; mark DONE_CONTROLLER_UNAME_M
build_id=$(awk -F= '/^BUILD_ID=/{print $2; exit}' /etc/os-release); rc=$?; mark "BUILD_ID=$build_id"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$build_id" = tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l ] || { mark FAIL_CONTROLLER_BUILD_ID; exit 12; }; mark DONE_CONTROLLER_BUILD_ID
glibc_rpm=$(rpm -q glibc); rc=$?; mark "glibc=$glibc_rpm"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$glibc_rpm" = glibc-2.40-1.6.armv7l ] || { mark FAIL_CONTROLLER_GLIBC; exit 13; }; mark DONE_CONTROLLER_GLIBC
memtotal=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo); rc=$?; mark "MemTotal_kB=$memtotal"; mark "RC=$rc"
case "$memtotal" in ''|*[!0-9]*) mark FAIL_CONTROLLER_MEMTOTAL; exit 14;; esac
[ "$memtotal" -ge 8036234 ] && [ "$memtotal" -le 8198582 ] || { mark FAIL_CONTROLLER_MEMTOTAL; exit 14; }; mark DONE_CONTROLLER_MEMTOTAL

for spec in "$bench:$expected_bench_sha:BENCH" "$probe:$expected_probe_sha:PROBE" "$media:$expected_media_sha:MEDIA"; do
    path=${spec%%:*}; rest=${spec#*:}; expected=${rest%%:*}; label=${rest##*:}
    actual=$(sha256sum "$path" | awk '{print $1}'); rc=$?; mark "$label sha256=$actual"; mark "RC=$rc"
    [ "$rc" -eq 0 ] && [ "$actual" = "$expected" ] || { mark "FAIL_${label}_SHA"; exit 15; }
    mark "DONE_${label}_SHA"
done
ldd "$bench" >"$work/bench_ldd.txt" 2>&1; rc=$?; mark "RC=$rc"
[ "$rc" -eq 0 ] && ! grep -F 'not found' "$work/bench_ldd.txt" >/dev/null 2>&1 || { mark FAIL_BENCH_LDD; exit 16; }; mark DONE_BENCH_LDD

: >"$work/governor_before.txt"; gov_count=0
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_before.txt"; cat "$path" >>"$work/governor_before.txt" || exit 17
    gov_count=$((gov_count + 1))
done
mark "governor_count=$gov_count"; mark RC=0; mark DONE_GOVERNOR_BEFORE
[ "$gov_count" -eq 4 ] && [ "$(grep -c '=schedutil$' "$work/governor_before.txt")" -eq 4 ] || { mark RC=1; mark FAIL_GOVERNOR_INITIAL_NOT_SCHEDUTIL; exit 18; }
mark RC=0; mark DONE_GOVERNOR_INITIAL_SCHEDUTIL

trap finish EXIT
trap 'overall_rc=90; exit 90' HUP INT TERM
governor_changed=1
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s\n' performance >"$path" || exit 20; done
: >"$work/governor_performance.txt"
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s=' "$path" >>"$work/governor_performance.txt"; cat "$path" >>"$work/governor_performance.txt" || exit 21; done
[ "$(grep -c '=performance$' "$work/governor_performance.txt")" -eq 4 ] || exit 22
mark RC=0; mark DONE_GOVERNOR_PERFORMANCE

cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_before.txt"; rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 23; mark DONE_ZRAM_BEFORE
cat /proc/swaps >"$work/swaps_before.txt"; rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 24; mark DONE_SWAPS_BEFORE
dmesg >"$work/dmesg_before.txt"; rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 25; mark DONE_DMESG_BEFORE
date -Ins >"$work/run_start.txt"; rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 26; mark DONE_RUN_START

run_cell none 1 1 || exit $?
run_cell trim-at-loop-release 1 2 || exit $?
run_cell trim-at-loop-release 2 3 || exit $?
run_cell none 2 4 || exit $?
run_cell none 3 5 || exit $?
run_cell trim-at-loop-release 3 6 || exit $?

exit 0
