#!/bin/sh
set -u

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
ip=
output=
frozen=
gbs=
remote=/opt/usr/glibc_memopt/a_anchor_replication_20260904
contract="$repo/tools/runners/a_anchor_replication_20260904/preregistered_contract.json"

usage()
{
    echo "usage: $0 --ip <address> --output <host-dir> --frozen <ELF> --gbs <ELF>" >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ip) ip=$2; shift 2;;
        --output) output=$2; shift 2;;
        --frozen) frozen=$2; shift 2;;
        --gbs) gbs=$2; shift 2;;
        -h|--help) usage; exit 0;;
        *) usage; exit 2;;
    esac
done
[ -n "$ip" ] && [ -n "$output" ] && [ -f "$frozen" ] && [ -f "$gbs" ] || { usage; exit 2; }
printf '%s' "$ip" | grep -Eq '^[A-Za-z0-9.-]+$' || { echo "unsafe address" >&2; exit 2; }
case "$output" in /|/home|/opt|/tmp) echo "refusing broad output path" >&2; exit 2;; esac
mkdir -p "$output" || exit 2
serial="$ip:26101"
cleanup_authorized=0
workflow_complete=0

asset_field()
{
    python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(next(x for x in p["artifacts"] if x["name"]=="alloc_bench.armv7l")[sys.argv[2]])' "$repo/tools/reproduce/deliverables_manifest.json" "$1"
}

sha_of()
{
    sha256sum "$1" | awk '{print $1}'
}

run_remote()
{
    label=$1; body=$2; log=$3
    command="$body; rc=\$?; printf 'RC=%s\n' \"\$rc\"; if [ \"\$rc\" -eq 0 ]; then printf 'DONE_%s\n' '$label'; else printf 'FAIL_%s\n' '$label'; fi"
    sdb -s "$serial" shell "$command" </dev/null >"$log" 2>&1
    tr -d '\r' <"$log" | grep -Fx RC=0 >/dev/null 2>&1 || return 1
    tr -d '\r' <"$log" | grep -Fx "DONE_$label" >/dev/null 2>&1 || return 1
}

remote_recovery()
{
    [ "$cleanup_authorized" -eq 1 ] || return 0
    run_remote RECOVERY "test '$remote' = /opt/usr/glibc_memopt/a_anchor_replication_20260904 && { [ ! -e '$remote' ] || find '$remote' -depth -delete; } && for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do printf '%s\\n' schedutil >\"\$p\" || exit 1; done; rmdir /opt/usr/glibc_memopt 2>/dev/null || test ! -d /opt/usr/glibc_memopt" "$output/recovery.txt" || true
}

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    [ "$workflow_complete" -eq 1 ] || remote_recovery
    exit "$rc"
}
trap finish EXIT HUP INT TERM

die()
{
    echo "FAIL $*" >&2
    exit 1
}

snapshot_stability()
{
    target=$1; raw="$target.raw"
    body='d=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f") || exit 1; h=${h%% *}; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi'
    run_remote STABILITY_SNAPSHOT "$body" "$raw" || return 1
    printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$target"
    tr -d '\r' <"$raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$target"
}

create_manifest()
{
    body="cd '$remote' && find . -type f ! -name board_manifest.sha256 ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do sha256sum \"\$f\" || exit 1; done > board_manifest.sha256 && find . -type f ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do n=\$(wc -c < \"\$f\") || exit 1; printf '%s\\t%s\\n' \"\$n\" \"\$f\"; done > board_file_sizes.tsv"
    run_remote MANIFEST "$body" "$1"
}

archive_alerts()
{
    mkdir -p "$output/stability_archives" || return 1
    python3 "$repo/tools/reproduce/stability_monitor.py" diff --before "$output/stability_before.tsv" --after "$output/stability_after.tsv" --output "$output/stability_archives/new_paths.txt" || return 1
    : >"$output/stability_archives/host_sha256.txt"
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        printf '%s\n' "$path" | grep -Eq '^/opt/usr/share/crash/livedump/[A-Za-z0-9._-]+\.zip$' || return 1
        base=${path##*/}
        expected=$(awk -F '\t' -v p="$path" '$1==p {print $4}' "$output/stability_after.tsv")
        [ -n "$expected" ] || return 1
        sdb -s "$serial" pull "$path" "$output/stability_archives/$base" </dev/null >"$output/stability_archives/pull_$base.txt" 2>&1 || return 1
        actual=$(sha_of "$output/stability_archives/$base") || return 1
        [ "$actual" = "$expected" ] || return 1
        printf '%s  %s\n' "$actual" "$base" >>"$output/stability_archives/host_sha256.txt"
    done <"$output/stability_archives/new_paths.txt"
}

frozen_expected=$(asset_field frozen_sha256) || die "manifest frozen SHA"
gbs_expected=$(asset_field gbs_build_sha256) || die "manifest GBS SHA"
[ "$(sha_of "$frozen")" = "$frozen_expected" ] || die "host frozen SHA"
[ "$(sha_of "$gbs")" = "$gbs_expected" ] || die "host GBS SHA"
{
    printf 'artifact\tsha_source\tsha256\n'
    printf 'alloc_bench.armv7l\tfrozen\t%s\n' "$frozen_expected"
    printf 'alloc_bench.armv7l\tgbs\t%s\n' "$gbs_expected"
} >"$output/artifact_manifest.tsv"

sdb version </dev/null >"$output/sdb_version.txt" 2>&1 || true
sdb connect "$ip" </dev/null >"$output/sdb_connect.txt" 2>&1 || true
sdb devices </dev/null >"$output/sdb_devices.txt" 2>&1 || true
mkdir -p "$output/preflight"
SDB_SERIAL="$serial" sh "$repo/tools/runners/s4_retention_20260901/preflight_gate.sh" "$output/preflight" || die "identity/environment gate"
cleanup_authorized=1
snapshot_stability "$output/stability_before.tsv" || die "stability before"
run_remote CREATE_WORKDIR "test ! -e '$remote' && mkdir -p '$remote/bin/frozen' '$remote/bin/gbs'" "$output/create_workdir.txt" || die "workdir"
sdb -s "$serial" push "$frozen" "$remote/bin/frozen/alloc_bench.armv7l" </dev/null >"$output/push_frozen.txt" 2>&1 || die "push frozen"
sdb -s "$serial" push "$gbs" "$remote/bin/gbs/alloc_bench.armv7l" </dev/null >"$output/push_gbs.txt" 2>&1 || die "push GBS"
sdb -s "$serial" push "$repo/tools/runners/a_anchor_replication_20260904/run_a_anchor_remote.sh" "$remote/run_a_anchor_remote.sh" </dev/null >"$output/push_runner.txt" 2>&1 || die "push runner"
sdb -s "$serial" push "$repo/tools/runners/s4_retention_20260901/sample_smaps_1s.sh" "$remote/sample_smaps_1s.sh" </dev/null >"$output/push_sampler.txt" 2>&1 || die "push sampler"
sdb -s "$serial" push "$repo/tools/runners/s4_retention_20260901/medium_1k_16k.hist" "$remote/medium_1k_16k.hist" </dev/null >"$output/push_hist.txt" 2>&1 || die "push histogram"
run_remote ASSET_VERIFY "chmod 0755 '$remote/bin/frozen/alloc_bench.armv7l' '$remote/bin/gbs/alloc_bench.armv7l' '$remote/run_a_anchor_remote.sh' '$remote/sample_smaps_1s.sh' && test \$(sha256sum '$remote/bin/frozen/alloc_bench.armv7l' | awk '{print \$1}') = '$frozen_expected' && test \$(sha256sum '$remote/bin/gbs/alloc_bench.armv7l' | awk '{print \$1}') = '$gbs_expected' && test \$(sha256sum '$remote/medium_1k_16k.hist' | awk '{print \$1}') = 2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b" "$output/asset_verify.txt" || die "asset verification"
run_remote A_ANCHOR_INVOKE "EXPECTED_FROZEN_SHA='$frozen_expected' EXPECTED_GBS_SHA='$gbs_expected' sh '$remote/run_a_anchor_remote.sh'" "$output/remote_invoke.txt" || die "remote controller"
grep -F DONE_A_ANCHOR_CONTROLLER "$output/remote_invoke.txt" >/dev/null || die "controller marker"
snapshot_stability "$output/stability_after.tsv" || die "stability after"
create_manifest "$output/manifest.txt" || die "manifest"
sdb -s "$serial" pull "$remote" "$output/board_pull" </dev/null >"$output/pull.txt" 2>&1 || die "pull"
python3 "$repo/tools/runners/a_anchor_replication_20260904/analyze_a_anchor.py" --pull "$output/board_pull" --contract "$contract" --output "$output/derived" >"$output/analyze.txt" 2>&1 || die "analysis"
archive_alerts || die "alert archive"
initial_rc=0
python3 "$repo/tools/reproduce/stability_monitor.py" classify --before "$output/stability_before.tsv" --after "$output/stability_after.tsv" --archive-dir "$output/stability_archives" --pull "$output/board_pull" --workload a-anchor --bands "$contract" --output "$output/stability.initial.json" --clean-list "$output/stability.clean_paths.txt" >"$output/stability.initial.txt" 2>&1 || initial_rc=$?
while IFS= read -r path; do
    [ -n "$path" ] || continue
    printf '%s\n' "$path" | grep -Eq '^/opt/usr/share/crash/livedump/[A-Za-z0-9._-]+\.zip$' || die "unsafe alert cleanup path"
    run_remote ALERT_CLEANUP "test -f '$path' && rm -f '$path' && test ! -e '$path'" "$output/stability_archives/cleanup_${path##*/}.txt" || die "alert cleanup"
done <"$output/stability.clean_paths.txt"
snapshot_stability "$output/stability.post_cleanup.tsv" || die "post-cleanup stability"
final_rc=0
python3 "$repo/tools/reproduce/stability_monitor.py" classify --before "$output/stability_before.tsv" --after "$output/stability_after.tsv" --post-clean "$output/stability.post_cleanup.tsv" --archive-dir "$output/stability_archives" --pull "$output/board_pull" --workload a-anchor --bands "$contract" --output "$output/stability.final.json" >"$output/stability.final.txt" 2>&1 || final_rc=$?
run_remote WORKDIR_CLEANUP "test '$remote' = /opt/usr/glibc_memopt/a_anchor_replication_20260904 && find '$remote' -depth -delete && test ! -e '$remote'" "$output/cleanup.txt" || die "workdir cleanup"
run_remote EMPTY_PARENT_CLEANUP "rmdir /opt/usr/glibc_memopt && test ! -e /opt/usr/glibc_memopt" "$output/cleanup_parent.txt" || die "parent cleanup"
run_remote GOVERNOR_FINAL 'n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do g=$(cat "$p") || exit 1; printf "%s=%s\n" "$p" "$g"; [ "$g" = schedutil ] && n=$((n+1)); done; [ "$n" -eq 4 ]' "$output/governor_final.txt" || die "governor final"
cleanup_authorized=0
workflow_complete=1
[ "$initial_rc" -eq 0 ] && [ "$final_rc" -eq 0 ] || die "stability gate"
printf 'OVERALL\tPASS\nRESULTS\t%s\n' "$output"
