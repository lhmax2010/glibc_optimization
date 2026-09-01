#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/cyclic_s2_20260831
bench="$work/alloc_bench.armv7l"
sampler="$work/sample_smaps_1s.sh"
control="$work/controller.log"
expected_sha=dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd
overall_rc=0
governor_changed=0

: >"$control" || exit 2

mark()
{
    printf '%s\n' "$*" | tee -a "$control"
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
        mark 'RC=0'
        mark 'DONE_GOVERNOR_RESTORE'
    else
        mark "RC=$restore_rc"
        mark 'FAIL_GOVERNOR_RESTORE'
        overall_rc=91
    fi
}

finish()
{
    incoming=$?
    trap - EXIT HUP INT TERM
    [ "$incoming" -eq 0 ] || overall_rc=$incoming
    restore_governor
    mark "RC=$overall_rc"
    if [ "$overall_rc" -eq 0 ]; then
        mark 'DONE_S2_CONTROLLER'
    else
        mark 'FAIL_S2_CONTROLLER'
    fi
    exit "$overall_rc"
}

kernel=$(uname -r)
rc=$?
mark "kernel=$kernel"
mark "RC=$rc"
case "$kernel" in *rpi4*) mark 'DONE_CONTROLLER_UNAME_R';; *) mark 'FAIL_CONTROLLER_UNAME_R'; exit 10;; esac

arch=$(uname -m)
rc=$?
mark "arch=$arch"
mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$arch" = armv7l ] || { mark 'FAIL_CONTROLLER_UNAME_M'; exit 11; }
mark 'DONE_CONTROLLER_UNAME_M'

build_id=$(awk -F= '/^BUILD_ID=/{print $2; exit}' /etc/os-release)
rc=$?
mark "BUILD_ID=$build_id"
mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$build_id" = tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l ] || { mark 'FAIL_CONTROLLER_BUILD_ID'; exit 12; }
mark 'DONE_CONTROLLER_BUILD_ID'

actual_sha=$(sha256sum "$bench" | awk '{print $1}')
rc=$?
mark "bench_sha256=$actual_sha"
mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$actual_sha" = "$expected_sha" ] || { mark 'FAIL_CONTROLLER_BENCH_SHA'; exit 13; }
mark 'DONE_CONTROLLER_BENCH_SHA'

: >"$work/governor_before.txt"
gov_count=0
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_before.txt"
    cat "$path" >>"$work/governor_before.txt" || exit 14
    gov_count=$((gov_count + 1))
done
mark "governor_count=$gov_count"
mark 'RC=0'
mark 'DONE_GOVERNOR_BEFORE'
[ "$gov_count" -eq 4 ] || exit 15
if [ "$(grep -c '=schedutil$' "$work/governor_before.txt")" -ne 4 ]; then
    mark 'RC=1'
    mark 'FAIL_GOVERNOR_INITIAL_NOT_SCHEDUTIL'
    exit 16
fi
mark 'RC=0'
mark 'DONE_GOVERNOR_INITIAL_SCHEDUTIL'

trap finish EXIT
trap 'overall_rc=90; exit 90' HUP INT TERM
governor_changed=1
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s\n' performance >"$path" || exit 16
done
: >"$work/governor_performance.txt"
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_performance.txt"
    cat "$path" >>"$work/governor_performance.txt" || exit 17
done
[ "$(grep -c '=performance$' "$work/governor_performance.txt")" -eq 4 ] || exit 18
mark 'RC=0'
mark 'DONE_GOVERNOR_PERFORMANCE'

cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_before.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 19
mark 'DONE_ZRAM_BEFORE'
cat /proc/swaps >"$work/swaps_before.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 20
mark 'DONE_SWAPS_BEFORE'
dmesg >"$work/dmesg_before.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 21
mark 'DONE_DMESG_BEFORE'
date -Ins >"$work/run_start.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 22
mark 'DONE_RUN_START'

run_profile()
{
    profile=$1
    out="$work/$profile"
    mkdir -p "$out/xml" || return 30
    {
        printf '%s\n' "$bench --profile $profile --threads 4 --seed 20260814 --live-set 512 --idle-release 50 --release-order high --touch-full --cycles 8 --cycle-rise 3.4 --cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 --trim-at none --warmup 0 --outdir $out/xml"
    } >"$out/command.txt"
    date -Ins >"$out/start.txt" || return 31
    "$bench" --profile "$profile" --threads 4 --seed 20260814 --live-set 512 --idle-release 50 \
      --release-order high --touch-full --cycles 8 --cycle-rise 3.4 \
      --cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 \
      --trim-at none --warmup 0 --outdir "$out/xml" \
      >"$out/result.json" 2>"$out/stderr.txt" &
    bench_pid=$!
    printf '%s\n' "$bench_pid" >"$out/pid.txt"
    "$sampler" "$bench_pid" "$out/external_1s.tsv" "$out/external_sampler_meta.txt" \
      >"$out/external_sampler_stdout.txt" 2>"$out/external_sampler_stderr.txt" &
    sampler_pid=$!
    wait "$bench_pid"
    bench_rc=$?
    wait "$sampler_pid"
    sampler_rc=$?
    date -Ins >"$out/end.txt"
    printf 'bench_rc=%s\nsampler_rc=%s\n' "$bench_rc" "$sampler_rc" >"$out/exit_status.txt"
    sampler_samples=$(awk -F= '/^samples=/{print $2; exit}' "$out/external_sampler_meta.txt" 2>/dev/null)
    sampler_meta_ok=0
    case "$sampler_samples" in
        ''|*[!0-9]*) ;;
        *)
            if [ "$sampler_samples" -gt 0 ] \
              && grep -Fx 'RC=0' "$out/external_sampler_meta.txt" >/dev/null 2>&1 \
              && grep -Fx 'DONE_EXTERNAL_SAMPLER' "$out/external_sampler_meta.txt" >/dev/null 2>&1; then
                sampler_meta_ok=1
            fi
            ;;
    esac
    mark "profile=$profile bench_rc=$bench_rc sampler_rc=$sampler_rc"
    mark "profile=$profile sampler_samples=${sampler_samples:-NA} sampler_meta_ok=$sampler_meta_ok"
    if [ "$bench_rc" -ne 0 ] || [ "$sampler_rc" -ne 0 ] \
      || [ "$sampler_meta_ok" -ne 1 ] || [ ! -s "$out/result.json" ] \
      || [ ! -s "$out/external_1s.tsv" ]; then
        mark "RC=1"
        mark "FAIL_PROFILE_$profile"
        return 32
    fi
    mark 'RC=0'
    mark "DONE_PROFILE_$profile"
    return 0
}

run_profile mixed || exit $?
run_profile medium-only || exit $?

date -Ins >"$work/run_end.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 40
mark 'DONE_RUN_END'
dmesg >"$work/dmesg_after.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 41
mark 'DONE_DMESG_AFTER'
cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_after.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 42
mark 'DONE_ZRAM_AFTER'
cat /proc/swaps >"$work/swaps_after.txt"
rc=$?
mark "RC=$rc"
[ "$rc" -eq 0 ] || exit 43
mark 'DONE_SWAPS_AFTER'

exit 0
