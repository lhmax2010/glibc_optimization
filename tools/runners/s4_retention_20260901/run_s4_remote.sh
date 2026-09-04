#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/s4_retention_20260901
bench="$work/alloc_bench.armv7l"
sampler="$work/sample_smaps_1s.sh"
hist="$work/medium_1k_16k.hist"
control="$work/controller.log"
expected_bench_sha=${EXPECTED_ALLOC_SHA:-}
expected_hist_sha=2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b
overall_rc=0
governor_changed=0
after_captured=0

case "$expected_bench_sha" in
    ''|*[!0-9a-f]*) echo "EXPECTED_ALLOC_SHA must be a lowercase SHA-256" >&2; exit 2;;
esac
[ "${#expected_bench_sha}" -eq 64 ] || { echo "EXPECTED_ALLOC_SHA must contain 64 hex digits" >&2; exit 2; }
if [ "${1:-}" = --sha-contract-only ]; then
    printf 'SHA_CONTRACT alloc_bench.armv7l=%s\n' "$expected_bench_sha"
    exit 0
fi

: >"$control" || exit 2

mark()
{
    printf '%s\n' "$*" | tee -a "$control"
}

capture_after()
{
    [ "$after_captured" -eq 0 ] || return 0
    after_captured=1
    date -Ins >"$work/run_end.txt"
    rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_RUN_END || { mark FAIL_RUN_END; overall_rc=92; }
    dmesg >"$work/dmesg_after.txt"
    rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_DMESG_AFTER || { mark FAIL_DMESG_AFTER; overall_rc=93; }
    cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_after.txt"
    rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_ZRAM_AFTER || { mark FAIL_ZRAM_AFTER; overall_rc=94; }
    cat /proc/swaps >"$work/swaps_after.txt"
    rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] && mark DONE_SWAPS_AFTER || { mark FAIL_SWAPS_AFTER; overall_rc=95; }
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

finish()
{
    incoming=$?
    trap - EXIT HUP INT TERM
    [ "$incoming" -eq 0 ] || overall_rc=$incoming
    capture_after
    restore_governor
    mark "RC=$overall_rc"
    if [ "$overall_rc" -eq 0 ]; then mark DONE_S4_CONTROLLER; else mark FAIL_S4_CONTROLLER; fi
    exit "$overall_rc"
}

kernel=$(uname -r); rc=$?
mark "kernel=$kernel"; mark "RC=$rc"
case "$kernel" in *rpi4*) mark DONE_CONTROLLER_UNAME_R;; *) mark FAIL_CONTROLLER_UNAME_R; exit 10;; esac

arch=$(uname -m); rc=$?
mark "arch=$arch"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$arch" = armv7l ] || { mark FAIL_CONTROLLER_UNAME_M; exit 11; }
mark DONE_CONTROLLER_UNAME_M

build_id=$(awk -F= '/^BUILD_ID=/{print $2; exit}' /etc/os-release); rc=$?
mark "BUILD_ID=$build_id"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$build_id" = tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l ] || { mark FAIL_CONTROLLER_BUILD_ID; exit 12; }
mark DONE_CONTROLLER_BUILD_ID

glibc_rpm=$(rpm -q glibc); rc=$?
mark "glibc=$glibc_rpm"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$glibc_rpm" = glibc-2.40-1.6.armv7l ] || { mark FAIL_CONTROLLER_GLIBC; exit 13; }
mark DONE_CONTROLLER_GLIBC

memtotal=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo); rc=$?
mark "MemTotal_kB=$memtotal"; mark "RC=$rc"
case "$memtotal" in ''|*[!0-9]*) mark FAIL_CONTROLLER_MEMTOTAL; exit 14;; esac
[ "$memtotal" -ge 8036234 ] && [ "$memtotal" -le 8198582 ] || { mark FAIL_CONTROLLER_MEMTOTAL; exit 14; }
mark DONE_CONTROLLER_MEMTOTAL

actual_sha=$(sha256sum "$bench" | awk '{print $1}'); rc=$?
mark "bench_sha256=$actual_sha"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$actual_sha" = "$expected_bench_sha" ] || { mark FAIL_CONTROLLER_BENCH_SHA; exit 15; }
mark DONE_CONTROLLER_BENCH_SHA

actual_hist_sha=$(sha256sum "$hist" | awk '{print $1}'); rc=$?
mark "hist_sha256=$actual_hist_sha"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$actual_hist_sha" = "$expected_hist_sha" ] || { mark FAIL_CONTROLLER_HIST_SHA; exit 16; }
mark DONE_CONTROLLER_HIST_SHA

: >"$work/governor_before.txt"
gov_count=0
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_before.txt"
    cat "$path" >>"$work/governor_before.txt" || exit 17
    gov_count=$((gov_count + 1))
done
mark "governor_count=$gov_count"; mark RC=0; mark DONE_GOVERNOR_BEFORE
[ "$gov_count" -eq 4 ] || exit 18
[ "$(grep -c '=schedutil$' "$work/governor_before.txt")" -eq 4 ] || { mark RC=1; mark FAIL_GOVERNOR_INITIAL_NOT_SCHEDUTIL; exit 19; }
mark RC=0; mark DONE_GOVERNOR_INITIAL_SCHEDUTIL

trap finish EXIT
trap 'overall_rc=90; exit 90' HUP INT TERM
governor_changed=1
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s\n' performance >"$path" || exit 20
done
: >"$work/governor_performance.txt"
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_performance.txt"
    cat "$path" >>"$work/governor_performance.txt" || exit 21
done
[ "$(grep -c '=performance$' "$work/governor_performance.txt")" -eq 4 ] || exit 22
mark RC=0; mark DONE_GOVERNOR_PERFORMANCE

cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_before.txt"
rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 23; mark DONE_ZRAM_BEFORE
cat /proc/swaps >"$work/swaps_before.txt"
rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 24; mark DONE_SWAPS_BEFORE
dmesg >"$work/dmesg_before.txt"
rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 25; mark DONE_DMESG_BEFORE
date -Ins >"$work/run_start.txt"
rc=$?; mark "RC=$rc"; [ "$rc" -eq 0 ] || exit 26; mark DONE_RUN_START

run_a()
{
    cell=$1
    profile_arg=$2
    out="$work/A/$cell/rep1"
    mkdir -p "$out/xml" || return 30
    {
        printf 'group=A\ncell=%s\nrep=1\n' "$cell"
        printf 'CMD=%s --threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15 --idle-trim --post-trim-ops-per-thread 4096 --profile %s --live-set 4096 --idle-release 50 --release-order high --outdir %s\n' "$bench" "$profile_arg" "$out/xml"
    } >"$out/command.txt"
    date -Ins >"$out/start.txt" || return 31
    "$bench" --threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15 \
      --idle-trim --post-trim-ops-per-thread 4096 --profile "$profile_arg" \
      --live-set 4096 --idle-release 50 --release-order high --outdir "$out/xml" \
      >"$out/result.json" 2>"$out/stderr.txt" &
    bench_pid=$!
    printf '%s\n' "$bench_pid" >"$out/pid.txt"
    "$sampler" "$bench_pid" "$out/external_1s.tsv" "$out/external_sampler_meta.txt" \
      >"$out/external_sampler_stdout.txt" 2>"$out/external_sampler_stderr.txt" &
    sampler_pid=$!
    wait "$bench_pid"; bench_rc=$?
    wait "$sampler_pid"; sampler_rc=$?
    date -Ins >"$out/end.txt"
    printf 'bench_rc=%s\nsampler_rc=%s\n' "$bench_rc" "$sampler_rc" >"$out/exit_status.txt"
    sampler_samples=$(awk -F= '/^samples=/{print $2; exit}' "$out/external_sampler_meta.txt" 2>/dev/null)
    sampler_meta_ok=0
    case "$sampler_samples" in ''|*[!0-9]*) ;; *)
        if [ "$sampler_samples" -gt 0 ] && grep -Fx RC=0 "$out/external_sampler_meta.txt" >/dev/null 2>&1 \
          && grep -Fx DONE_EXTERNAL_SAMPLER "$out/external_sampler_meta.txt" >/dev/null 2>&1; then sampler_meta_ok=1; fi;; esac
    mark "group=A cell=$cell bench_rc=$bench_rc sampler_rc=$sampler_rc samples=${sampler_samples:-NA} sampler_meta_ok=$sampler_meta_ok"
    if [ "$bench_rc" -ne 0 ] || [ "$sampler_rc" -ne 0 ] || [ "$sampler_meta_ok" -ne 1 ] \
      || [ ! -s "$out/result.json" ] || [ ! -s "$out/external_1s.tsv" ]; then
        mark RC=1; mark "FAIL_A_$cell"; return 32
    fi
    mark RC=0; mark "DONE_A_$cell"
}

run_b()
{
    profile=$1
    trim_at=$2
    rep=$3
    out="$work/B/$profile/$trim_at/rep$rep"
    mkdir -p "$out/xml" || return 40
    {
        printf 'group=B\nprofile=%s\ntrim_at=%s\nrep=%s\n' "$profile" "$trim_at" "$rep"
        printf 'CMD=%s --profile %s --threads 4 --seed 20260814 --live-set 512 --idle-release 50 --release-order high --touch-full --cycles 2 --cycle-rise 3.4 --cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 --trim-at %s --warmup 0 --outdir %s\n' "$bench" "$profile" "$trim_at" "$out/xml"
    } >"$out/command.txt"
    date -Ins >"$out/start.txt" || return 41
    "$bench" --profile "$profile" --threads 4 --seed 20260814 --live-set 512 \
      --idle-release 50 --release-order high --touch-full --cycles 2 \
      --cycle-rise 3.4 --cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 \
      --trim-at "$trim_at" --warmup 0 --outdir "$out/xml" \
      >"$out/result.json" 2>"$out/stderr.txt" &
    bench_pid=$!
    printf '%s\n' "$bench_pid" >"$out/pid.txt"
    "$sampler" "$bench_pid" "$out/external_1s.tsv" "$out/external_sampler_meta.txt" \
      >"$out/external_sampler_stdout.txt" 2>"$out/external_sampler_stderr.txt" &
    sampler_pid=$!
    wait "$bench_pid"; bench_rc=$?
    wait "$sampler_pid"; sampler_rc=$?
    date -Ins >"$out/end.txt"
    printf 'bench_rc=%s\nsampler_rc=%s\n' "$bench_rc" "$sampler_rc" >"$out/exit_status.txt"
    sampler_samples=$(awk -F= '/^samples=/{print $2; exit}' "$out/external_sampler_meta.txt" 2>/dev/null)
    sampler_meta_ok=0
    case "$sampler_samples" in ''|*[!0-9]*) ;; *)
        if [ "$sampler_samples" -gt 0 ] && grep -Fx RC=0 "$out/external_sampler_meta.txt" >/dev/null 2>&1 \
          && grep -Fx DONE_EXTERNAL_SAMPLER "$out/external_sampler_meta.txt" >/dev/null 2>&1; then sampler_meta_ok=1; fi;; esac
    mark "group=B profile=$profile trim_at=$trim_at rep=$rep bench_rc=$bench_rc sampler_rc=$sampler_rc samples=${sampler_samples:-NA} sampler_meta_ok=$sampler_meta_ok"
    if [ "$bench_rc" -ne 0 ] || [ "$sampler_rc" -ne 0 ] || [ "$sampler_meta_ok" -ne 1 ] \
      || [ ! -s "$out/result.json" ] || [ ! -s "$out/external_1s.tsv" ]; then
        mark RC=1; mark "FAIL_B_${profile}_${trim_at}_rep${rep}"; return 42
    fi
    mark RC=0; mark "DONE_B_${profile}_${trim_at}_rep${rep}"
}

run_a mixed mixed || exit $?
run_a medium-only "external:$hist" || exit $?
for profile in mixed medium-only; do
    for rep in 1 2 3; do run_b "$profile" valley "$rep" || exit $?; done
    run_b "$profile" none 1 || exit $?
done

exit 0
