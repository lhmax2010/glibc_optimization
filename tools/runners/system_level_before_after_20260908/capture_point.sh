#!/bin/sh
printf '%s\n' 'NOT-EVALUATED: unexecuted capture draft; shared-board occupancy STOP. Not a runnable reproduction entry.' >&2
exit 2
# Before future use: strict cell/phase path validation and parent-symlink rejection.
# One read-only observation window. All output files stay under this round's workdir.
set -u
work=/opt/usr/glibc_memopt/system_level_before_after_20260908
pid=${1:?PID required}
out=${2:?point directory required}
case "$pid" in ''|*[!0-9]*) exit 2;; esac
case "$out" in "$work"/G[1-4]_*/points/[0-9][0-9]_pre|"$work"/G[1-4]_*/points/[0-9][0-9]_post) ;; *) exit 2;; esac
[ ! -e "$out" ] || { echo FAIL_POINT_ALREADY_EXISTS; exit 2; }
mkdir -p "$out" || exit 2
log="$out/capture_commands.txt"
record()
{
    name=$1
    shift
    "$@" >"$out/$name" 2>"$out/$name.stderr"
    rc=$?
    printf 'CMD=%s RC=%s\n' "$*" "$rc" >>"$log"
    if [ "$rc" -eq 0 ]; then printf 'DONE_%s\n' "$name" >>"$log"; else printf 'FAIL_%s\n' "$name" >>"$log"; return 1; fi
}
start=$(date +%s%N) || exit 3
record stat.txt cat "/proc/$pid/stat" || exit 4
record status.txt cat "/proc/$pid/status" || exit 5
record profile.json "$work/reclaim_probe.armv7l" profile "$pid" || exit 6
record meminfo.txt cat /proc/meminfo || exit 7
record zram.txt cat /sys/block/zram0/mm_stat || exit 8
record memps.txt memps "$pid" || exit 9
record stat_check.txt cat "/proc/$pid/stat" || exit 10
end=$(date +%s%N) || exit 11
case "$start:$end" in *[!0-9:]*) echo FAIL_POINT_CLOCK; exit 12;; esac
printf '{"start_ns":%s,"end_ns":%s}\n' "$start" "$end" >"$out/meta.json" || exit 13
printf 'RC=0\nDONE_CAPTURE_POINT\n'
