#!/bin/sh
set -u

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ip=
output=
artifact_dir=${DEMO_ARTIFACT_DIR:-$repo/tools/reproduce/artifacts}

usage()
{
    cat <<'EOF'
usage: bash tools/reproduce/reproduce.sh board --ip <address> [--output <host-dir>] [--artifact-dir <dir>]

Required bundle names:
  alloc_bench.armv7l
  gst_loop_decode.armv7l
  reclaim_probe.armv7l
  small_320x240.mp4

If the three ELF files are absent, DEMO_TOOLCHAIN_ROOT and DEMO_GST_SYSROOT
can be supplied for the documented builds. The media asset must be supplied.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ip) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; ip=$2; shift 2;;
        --output) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; output=$2; shift 2;;
        --artifact-dir) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; artifact_dir=$2; shift 2;;
        -h|--help) usage; exit 0;;
        *) usage >&2; exit 2;;
    esac
done
[ -n "$ip" ] || { usage >&2; exit 2; }
printf '%s' "$ip" | grep -Eq '^[A-Za-z0-9.-]+$' || { printf 'unsafe address\n' >&2; exit 2; }
if [ -z "$output" ]; then
    output="$repo/board_results/demo_workflow_$(date -u +%Y%m%dT%H%M%SZ)"
fi
case "$output" in /|/home|/opt|/tmp) printf 'refusing broad output path: %s\n' "$output" >&2; exit 2;; esac
mkdir -p "$output" || exit 2

serial="$ip:26101"
s4_remote=/opt/usr/glibc_memopt/s4_retention_20260901
gst_remote=/opt/usr/glibc_memopt/gst_trim_cost_20260901
bands="$repo/tools/reproduce/acceptance_bands.json"
build_tmp=$(mktemp -d /tmp/glibc-memopt-board-build.XXXXXX) || exit 2
cleanup_authorized=0
workflow_complete=0

remote_recovery()
{
    [ "$cleanup_authorized" -eq 1 ] || return 0
    sdb -s "$serial" shell "ok=1; test '$s4_remote' = '/opt/usr/glibc_memopt/s4_retention_20260901' && rm -rf '$s4_remote' || ok=0; test '$gst_remote' = '/opt/usr/glibc_memopt/gst_trim_cost_20260901' && rm -rf '$gst_remote' || ok=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s\\n' schedutil >\"\$p\" || ok=0; done; rmdir /opt/usr/glibc_memopt 2>/dev/null || test ! -d /opt/usr/glibc_memopt || ok=0; test \$ok -eq 1; rc=\$?; echo RC=\$rc; if [ \$rc -eq 0 ]; then echo DONE_WORKFLOW_RECOVERY; else echo FAIL_WORKFLOW_RECOVERY; fi" >"$output/recovery.txt" 2>&1 || true
}

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ "$workflow_complete" -ne 1 ]; then remote_recovery; fi
    case "$build_tmp" in /tmp/glibc-memopt-board-build.*) find "$build_tmp" -depth -delete 2>/dev/null || true;; esac
    exit "$rc"
}
trap finish EXIT HUP INT TERM

die()
{
    printf 'FAIL\t%s\n' "$*" >&2
    exit 1
}

sha_of()
{
    sha256sum "$1" | awk '{print $1}'
}

prepare_artifacts()
{
    mkdir -p "$build_tmp/alloc" "$build_tmp/probe" "$build_tmp/gst" || return 1
    alloc="$artifact_dir/alloc_bench.armv7l"
    probe="$artifact_dir/reclaim_probe.armv7l"
    gst="$artifact_dir/gst_loop_decode.armv7l"
    media="$artifact_dir/small_320x240.mp4"
    if [ ! -f "$alloc" ]; then
        [ -n "${DEMO_TOOLCHAIN_ROOT:-}" ] || die "missing alloc_bench.armv7l and DEMO_TOOLCHAIN_ROOT"
        cp "$repo/tools/alloc_bench/alloc_bench.c" "$repo/tools/alloc_bench/Makefile" "$build_tmp/alloc/" || return 1
        make -C "$build_tmp/alloc" armv7l ARMV7L_ROOT="$DEMO_TOOLCHAIN_ROOT" || return 1
        alloc="$build_tmp/alloc/alloc_bench.armv7l"
    fi
    if [ ! -f "$probe" ]; then
        [ -n "${DEMO_TOOLCHAIN_ROOT:-}" ] || die "missing reclaim_probe.armv7l and DEMO_TOOLCHAIN_ROOT"
        cp "$repo/tools/reclaim_probe/reclaim_probe.c" "$repo/tools/reclaim_probe/Makefile" "$build_tmp/probe/" || return 1
        make -C "$build_tmp/probe" armv7l ARMV7L_ROOT="$DEMO_TOOLCHAIN_ROOT" || return 1
        probe="$build_tmp/probe/reclaim_probe.armv7l"
    fi
    if [ ! -f "$gst" ]; then
        [ -n "${DEMO_TOOLCHAIN_ROOT:-}" ] || die "missing gst_loop_decode.armv7l and DEMO_TOOLCHAIN_ROOT"
        [ -n "${DEMO_GST_SYSROOT:-}" ] || die "missing gst_loop_decode.armv7l and DEMO_GST_SYSROOT"
        TOOLCHAIN_ROOT="$DEMO_TOOLCHAIN_ROOT" GST_SYSROOT="$DEMO_GST_SYSROOT" \
          sh "$repo/tools/runners/gst_trim_cost_20260901/build_armv7l.sh" "$build_tmp/gst/gst_loop_decode.armv7l" || return 1
        gst="$build_tmp/gst/gst_loop_decode.armv7l"
    fi
    [ -f "$media" ] || die "missing required media asset: $media"
    {
        printf 'alloc_bench.armv7l\t%s\t%s\n' "$(sha_of "$alloc")" "$alloc"
        printf 'gst_loop_decode.armv7l\t%s\t%s\n' "$(sha_of "$gst")" "$gst"
        printf 'reclaim_probe.armv7l\t%s\t%s\n' "$(sha_of "$probe")" "$probe"
        printf 'small_320x240.mp4\t%s\t%s\n' "$(sha_of "$media")" "$media"
    } >"$output/artifact_manifest.tsv"
    [ "$(sha_of "$alloc")" = dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd ] || die "alloc_bench SHA mismatch"
    [ "$(sha_of "$gst")" = 204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6 ] || die "gst bench SHA mismatch"
    [ "$(sha_of "$probe")" = 3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7 ] || die "reclaim_probe SHA mismatch"
    [ "$(sha_of "$media")" = 3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d ] || die "media SHA mismatch"
}

run_remote()
{
    label=$1
    body=$2
    log=$3
    remote="$body; rc=\$?; printf 'RC=%s\\n' \"\$rc\"; if [ \"\$rc\" -eq 0 ]; then printf 'DONE_%s\\n' '$label'; else printf 'FAIL_%s\\n' '$label'; fi"
    sdb -s "$serial" shell "$remote" >"$log" 2>&1
    tr -d '\r' <"$log" | grep -Fx RC=0 >/dev/null 2>&1 || return 1
    tr -d '\r' <"$log" | grep -Fx "DONE_$label" >/dev/null 2>&1 || return 1
}

snapshot_stability()
{
    target=$1
    raw="$target.raw"
    body='d=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f" | awk "{print \\$1}") || exit 1; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi'
    run_remote STABILITY_SNAPSHOT "$body" "$raw" || return 1
    printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$target"
    tr -d '\r' <"$raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$target"
}

create_manifest()
{
    remote=$1
    log=$2
    body="cd '$remote' && find . -type f ! -name board_manifest.sha256 ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do sha256sum \"\$f\" || exit 1; done > board_manifest.sha256 && find . -type f ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do n=\$(wc -c < \"\$f\") || exit 1; printf '%s\\t%s\\n' \"\$n\" \"\$f\"; done > board_file_sizes.tsv"
    run_remote MANIFEST "$body" "$log"
}

archive_new_alerts()
{
    before=$1
    after=$2
    archive_dir=$3
    mkdir -p "$archive_dir" || return 1
    list="$archive_dir/new_paths.txt"
    python3 "$repo/tools/reproduce/stability_monitor.py" diff --before "$before" --after "$after" --output "$list" || return 1
    : >"$archive_dir/host_sha256.txt"
    while IFS= read -r remote; do
        [ -n "$remote" ] || continue
        printf '%s\n' "$remote" | grep -Eq '^/opt/usr/share/crash/livedump/[A-Za-z0-9._-]+\.zip$' || return 1
        base=${remote##*/}
        expected=$(awk -F '\t' -v path="$remote" '$1==path {print $4}' "$after")
        [ -n "$expected" ] || return 1
        sdb -s "$serial" pull "$remote" "$archive_dir/$base" >"$archive_dir/pull_$base.txt" 2>&1 || return 1
        actual=$(sha_of "$archive_dir/$base") || return 1
        [ "$actual" = "$expected" ] || return 1
        printf '%s  %s\n' "$actual" "$base" >>"$archive_dir/host_sha256.txt"
    done <"$list"
}

classify_and_clean()
{
    workload=$1
    before=$2
    after=$3
    archive_dir=$4
    pull=$5
    prefix=$6
    clean_list="$prefix.clean_paths.txt"
    initial="$prefix.initial.json"
    initial_rc=0
    python3 "$repo/tools/reproduce/stability_monitor.py" classify \
      --before "$before" --after "$after" --archive-dir "$archive_dir" --pull "$pull" \
      --workload "$workload" --bands "$bands" --output "$initial" --clean-list "$clean_list" || initial_rc=$?
    while IFS= read -r remote; do
        [ -n "$remote" ] || continue
        printf '%s\n' "$remote" | grep -Eq '^/opt/usr/share/crash/livedump/[A-Za-z0-9._-]+\.zip$' || return 1
        run_remote EXPECTED_OR_ATTRIBUTABLE_ALERT_CLEANUP "test -f '$remote' && rm -f '$remote' && test ! -e '$remote'" "$archive_dir/cleanup_${remote##*/}.txt" || return 1
    done <"$clean_list"
    snapshot_stability "$prefix.post_cleanup.tsv" || return 1
    final_rc=0
    python3 "$repo/tools/reproduce/stability_monitor.py" classify \
      --before "$before" --after "$after" --post-clean "$prefix.post_cleanup.tsv" \
      --archive-dir "$archive_dir" --pull "$pull" --workload "$workload" --bands "$bands" \
      --output "$prefix.final.json" || final_rc=$?
    [ "$initial_rc" -eq 0 ] && [ "$final_rc" -eq 0 ]
}

cleanup_workdir()
{
    remote=$1
    expected=$2
    log=$3
    [ "$remote" = "$expected" ] || return 1
    run_remote WORKDIR_CLEANUP "test '$remote' = '$expected' && rm -rf '$remote' && test ! -e '$remote'" "$log" || return 1
    run_remote EMPTY_PARENT_CLEANUP "rmdir /opt/usr/glibc_memopt && test ! -e /opt/usr/glibc_memopt" "$log.parent" || return 1
}

governor_final()
{
    run_remote GOVERNOR_FINAL 'n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do g=$(cat "$p") || exit 1; printf "%s=%s\n" "$p" "$g"; [ "$g" = schedutil ] && n=$((n+1)); done; [ "$n" -eq 4 ]' "$1"
}

prepare_artifacts || die "artifact preparation"
command -v sdb >/dev/null 2>&1 || die "sdb not found"
sdb version >"$output/sdb_version.txt" 2>&1 || true
sdb connect "$ip" >"$output/sdb_connect.txt" 2>&1 || true
sdb devices >"$output/sdb_devices.txt" 2>&1 || true

mkdir -p "$output/s4/preflight" "$output/gst/preflight" "$output/gst/capability"
SDB_SERIAL="$serial" sh "$repo/tools/runners/s4_retention_20260901/preflight_gate.sh" "$output/s4/preflight" || die "S4 identity/environment gate"
SDB_SERIAL="$serial" sh "$repo/tools/runners/gst_trim_cost_20260901/preflight_gate.sh" "$output/gst/preflight" || die "gst identity/environment gate"
SDB_SERIAL="$serial" sh "$repo/tools/runners/gst_trim_cost_20260901/capability_probe.sh" "$output/gst/capability" || die "gst capability gate"
cleanup_authorized=1

snapshot_stability "$output/s4/stability_before.tsv" || die "S4 stability before"
run_remote CREATE_S4_WORKDIR "test ! -e '$s4_remote' && mkdir -p '$s4_remote'" "$output/s4/create_workdir.txt" || die "S4 workdir"
sdb -s "$serial" push "$alloc" "$s4_remote/alloc_bench.armv7l" >"$output/s4/push_alloc.txt" 2>&1 || die "S4 bench push"
sdb -s "$serial" push "$repo/tools/runners/s4_retention_20260901/run_s4_remote.sh" "$s4_remote/run_s4_remote.sh" >"$output/s4/push_runner.txt" 2>&1 || die "S4 runner push"
sdb -s "$serial" push "$repo/tools/runners/s4_retention_20260901/sample_smaps_1s.sh" "$s4_remote/sample_smaps_1s.sh" >"$output/s4/push_sampler.txt" 2>&1 || die "S4 sampler push"
sdb -s "$serial" push "$repo/tools/runners/s4_retention_20260901/medium_1k_16k.hist" "$s4_remote/medium_1k_16k.hist" >"$output/s4/push_hist.txt" 2>&1 || die "S4 hist push"
run_remote S4_ASSET_VERIFY "chmod 0755 '$s4_remote/alloc_bench.armv7l' '$s4_remote/run_s4_remote.sh' '$s4_remote/sample_smaps_1s.sh' && test \$(sha256sum '$s4_remote/alloc_bench.armv7l' | awk '{print \$1}') = dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd && test \$(sha256sum '$s4_remote/medium_1k_16k.hist' | awk '{print \$1}') = 2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b" "$output/s4/asset_verify.txt" || die "S4 asset verification"
run_remote S4_REMOTE_INVOKE "sh '$s4_remote/run_s4_remote.sh'" "$output/s4/remote_invoke.txt" || die "S4 controller"
grep -F DONE_S4_CONTROLLER "$output/s4/remote_invoke.txt" >/dev/null || die "S4 controller marker"
snapshot_stability "$output/s4/stability_after.tsv" || die "S4 stability after"
create_manifest "$s4_remote" "$output/s4/manifest.txt" || die "S4 manifest"
sdb -s "$serial" pull "$s4_remote" "$output/s4/board_pull" >"$output/s4/pull.txt" 2>&1 || die "S4 pull"
python3 "$repo/tools/runners/s4_retention_20260901/analyze_s4.py" --pull "$output/s4/board_pull" --output "$output/s4/derived" >"$output/s4/analyze.txt" 2>&1 || die "S4 analysis"
archive_new_alerts "$output/s4/stability_before.tsv" "$output/s4/stability_after.tsv" "$output/s4/stability_archives" || die "S4 alert archive"
s4_stability_rc=0
classify_and_clean s4 "$output/s4/stability_before.tsv" "$output/s4/stability_after.tsv" "$output/s4/stability_archives" "$output/s4/board_pull" "$output/s4/stability" || s4_stability_rc=$?
cleanup_workdir "$s4_remote" /opt/usr/glibc_memopt/s4_retention_20260901 "$output/s4/cleanup.txt" || die "S4 cleanup"
governor_final "$output/s4/governor_final.txt" || die "S4 governor restore"

snapshot_stability "$output/gst/stability_before.tsv" || die "gst stability before"
run_remote CREATE_GST_WORKDIR "test ! -e '$gst_remote' && mkdir -p '$gst_remote'" "$output/gst/create_workdir.txt" || die "gst workdir"
sdb -s "$serial" push "$gst" "$gst_remote/gst_loop_decode.armv7l" >"$output/gst/push_bench.txt" 2>&1 || die "gst bench push"
sdb -s "$serial" push "$probe" "$gst_remote/reclaim_probe.armv7l" >"$output/gst/push_probe.txt" 2>&1 || die "gst probe push"
sdb -s "$serial" push "$media" "$gst_remote/small_320x240.mp4" >"$output/gst/push_media.txt" 2>&1 || die "gst media push"
sdb -s "$serial" push "$repo/tools/runners/gst_trim_cost_20260901/run_gst_trim_cost_remote.sh" "$gst_remote/run_gst_trim_cost_remote.sh" >"$output/gst/push_runner.txt" 2>&1 || die "gst runner push"
sdb -s "$serial" push "$repo/tools/runners/gst_trim_cost_20260901/sample_smaps_1s.sh" "$gst_remote/sample_smaps_1s.sh" >"$output/gst/push_sampler.txt" 2>&1 || die "gst sampler push"
run_remote GST_ASSET_VERIFY "chmod 0755 '$gst_remote/gst_loop_decode.armv7l' '$gst_remote/reclaim_probe.armv7l' '$gst_remote/run_gst_trim_cost_remote.sh' '$gst_remote/sample_smaps_1s.sh' && test \$(sha256sum '$gst_remote/gst_loop_decode.armv7l' | awk '{print \$1}') = 204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6 && test \$(sha256sum '$gst_remote/reclaim_probe.armv7l' | awk '{print \$1}') = 3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7 && test \$(sha256sum '$gst_remote/small_320x240.mp4' | awk '{print \$1}') = 3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d" "$output/gst/asset_verify.txt" || die "gst asset verification"
run_remote GST_REMOTE_INVOKE "sh '$gst_remote/run_gst_trim_cost_remote.sh'" "$output/gst/remote_invoke.txt" || die "gst controller"
grep -F DONE_GST_TRIM_CONTROLLER "$output/gst/remote_invoke.txt" >/dev/null || die "gst controller marker"
snapshot_stability "$output/gst/stability_after.tsv" || die "gst stability after"
create_manifest "$gst_remote" "$output/gst/manifest.txt" || die "gst manifest"
sdb -s "$serial" pull "$gst_remote" "$output/gst/board_pull" >"$output/gst/pull.txt" 2>&1 || die "gst pull"
python3 "$repo/tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py" --pull "$output/gst/board_pull" --output "$output/gst/derived" >"$output/gst/analyze.txt" 2>&1 || die "gst analysis"
archive_new_alerts "$output/gst/stability_before.tsv" "$output/gst/stability_after.tsv" "$output/gst/stability_archives" || die "gst alert archive"
gst_stability_rc=0
classify_and_clean gst "$output/gst/stability_before.tsv" "$output/gst/stability_after.tsv" "$output/gst/stability_archives" "$output/gst/board_pull" "$output/gst/stability" || gst_stability_rc=$?
cleanup_workdir "$gst_remote" /opt/usr/glibc_memopt/gst_trim_cost_20260901 "$output/gst/cleanup.txt" || die "gst cleanup"
governor_final "$output/gst/governor_final.txt" || die "gst governor restore"

python3 "$repo/tools/runners/s4_retention_20260901/analyze_s4.py" --replay-public "$output/s4/derived" --output "$output/s4/acceptance" >"$output/s4/acceptance_replay.txt" 2>&1 || die "S4 acceptance input"
acceptance_rc=0
python3 "$repo/tools/reproduce/evaluate_acceptance.py" \
  --bands "$bands" --s4-summary "$output/s4/acceptance/acceptance_input.json" \
  --gst-derived "$output/gst/derived" \
  --stability "$output/s4/stability.final.json" --stability "$output/gst/stability.final.json" \
  --output "$output/acceptance_result.json" | tee "$output/acceptance_table.txt" || acceptance_rc=$?

cleanup_authorized=0
workflow_complete=1
if [ "$s4_stability_rc" -ne 0 ] || [ "$gst_stability_rc" -ne 0 ] || [ "$acceptance_rc" -ne 0 ]; then
    printf 'OVERALL\tFAIL\n' | tee -a "$output/acceptance_table.txt"
    exit 1
fi
printf 'OVERALL\tPASS\n' | tee -a "$output/acceptance_table.txt"
printf 'RESULTS\t%s\n' "$output"
