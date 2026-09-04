#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/a_anchor_replication_20260904
frozen="$work/bin/frozen/alloc_bench.armv7l"
gbs="$work/bin/gbs/alloc_bench.armv7l"
sampler="$work/sample_smaps_1s.sh"
hist="$work/medium_1k_16k.hist"
control="$work/controller.log"
expected_frozen=${EXPECTED_FROZEN_SHA:-}
expected_gbs=${EXPECTED_GBS_SHA:-}
expected_hist=2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b
overall_rc=0
governor_changed=0
after_captured=0

valid_sha()
{
    case "$1" in ''|*[!0-9a-f]*) return 1;; esac
    [ "${#1}" -eq 64 ]
}

valid_sha "$expected_frozen" || { echo "bad EXPECTED_FROZEN_SHA" >&2; exit 2; }
valid_sha "$expected_gbs" || { echo "bad EXPECTED_GBS_SHA" >&2; exit 2; }
: >"$control" || exit 3

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
    if [ "$overall_rc" -eq 0 ]; then mark DONE_A_ANCHOR_CONTROLLER; else mark FAIL_A_ANCHOR_CONTROLLER; fi
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

for record in "frozen:$frozen:$expected_frozen" "gbs:$gbs:$expected_gbs" "hist:$hist:$expected_hist"; do
    name=${record%%:*}; rest=${record#*:}; path=${rest%%:*}; expected=${rest#*:}
    actual=$(sha256sum "$path" | awk '{print $1}'); rc=$?
    mark "${name}_sha256=$actual"; mark "RC=$rc"
    [ "$rc" -eq 0 ] && [ "$actual" = "$expected" ] || { mark "FAIL_${name}_SHA"; exit 15; }
    mark "DONE_${name}_SHA"
done

: >"$work/governor_before.txt"
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_before.txt"
    cat "$path" >>"$work/governor_before.txt" || exit 16
done
[ "$(grep -c '=schedutil$' "$work/governor_before.txt")" -eq 4 ] || { mark FAIL_GOVERNOR_INITIAL_NOT_SCHEDUTIL; exit 17; }
mark RC=0; mark DONE_GOVERNOR_INITIAL_SCHEDUTIL

trap finish EXIT
trap 'overall_rc=90; exit 90' HUP INT TERM
governor_changed=1
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s\n' performance >"$path" || exit 18
done
: >"$work/governor_performance.txt"
for path in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s=' "$path" >>"$work/governor_performance.txt"
    cat "$path" >>"$work/governor_performance.txt" || exit 19
done
[ "$(grep -c '=performance$' "$work/governor_performance.txt")" -eq 4 ] || exit 20
mark RC=0; mark DONE_GOVERNOR_PERFORMANCE

cat /sys/block/zram0/mm_stat >"$work/zram_mm_stat_before.txt" || exit 21
mark RC=0; mark DONE_ZRAM_BEFORE
cat /proc/swaps >"$work/swaps_before.txt" || exit 22
mark RC=0; mark DONE_SWAPS_BEFORE
dmesg >"$work/dmesg_before.txt" || exit 23
mark RC=0; mark DONE_DMESG_BEFORE
date -Ins >"$work/run_start.txt" || exit 24
mark RC=0; mark DONE_RUN_START

run_cell()
{
    order=$1
    elf=$2
    profile=$3
    rep=$4
    case "$elf" in frozen) bench=$frozen;; gbs) bench=$gbs;; *) return 30;; esac
    case "$profile" in mixed) profile_arg=mixed;; medium-only) profile_arg="external:$hist";; *) return 31;; esac
    cell=$(printf '%02d_%s_%s_rep%s' "$order" "$elf" "$profile" "$rep")
    out="$work/cells/$cell"
    mkdir -p "$out/xml" || return 32
    {
        printf 'order=%s\nelf=%s\nprofile=%s\nrep=%s\n' "$order" "$elf" "$profile" "$rep"
        printf 'CMD=%s --threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15 --idle-trim --post-trim-ops-per-thread 4096 --profile %s --live-set 4096 --idle-release 50 --release-order high --outdir %s\n' "$bench" "$profile_arg" "$out/xml"
    } >"$out/command.txt"
    date -Ins >"$out/start.txt" || return 33
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
    samples=$(awk -F= '/^samples=/{print $2; exit}' "$out/external_sampler_meta.txt" 2>/dev/null)
    sampler_ok=0
    case "$samples" in ''|*[!0-9]*) ;; *)
        if [ "$samples" -gt 0 ] && grep -Fx RC=0 "$out/external_sampler_meta.txt" >/dev/null 2>&1 \
          && grep -Fx DONE_EXTERNAL_SAMPLER "$out/external_sampler_meta.txt" >/dev/null 2>&1; then sampler_ok=1; fi;; esac
    mark "order=$order cell=$cell bench_rc=$bench_rc sampler_rc=$sampler_rc samples=${samples:-NA} sampler_ok=$sampler_ok"
    if [ "$bench_rc" -ne 0 ] || [ "$sampler_rc" -ne 0 ] || [ "$sampler_ok" -ne 1 ] \
      || [ ! -s "$out/result.json" ] || [ ! -s "$out/external_1s.tsv" ]; then
        mark RC=1; mark "FAIL_CELL_$cell"; return 34
    fi
    mark RC=0; mark "DONE_CELL_$cell"
}

run_cell 1 frozen mixed 1 || exit $?
run_cell 2 gbs mixed 1 || exit $?
run_cell 3 frozen medium-only 1 || exit $?
run_cell 4 gbs medium-only 1 || exit $?
run_cell 5 frozen mixed 2 || exit $?
run_cell 6 gbs mixed 2 || exit $?
run_cell 7 frozen medium-only 2 || exit $?
run_cell 8 gbs medium-only 2 || exit $?
run_cell 9 frozen mixed 3 || exit $?
run_cell 10 gbs mixed 3 || exit $?
run_cell 11 frozen medium-only 3 || exit $?
run_cell 12 gbs medium-only 3 || exit $?

exit 0
