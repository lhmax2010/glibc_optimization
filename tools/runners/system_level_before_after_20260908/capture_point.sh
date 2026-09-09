#!/bin/sh
# One read-only observation window. All output files stay under this round's workdir.
set -u
work=/opt/usr/glibc_memopt/system_level_before_after_20260908
pid=${1:?PID required}
out=${2:?point directory required}
case "$pid" in ''|*[!0-9]*) exit 2;; esac
relative=${out#"$work"/}
cell=${relative%%/*}
case "$cell" in G[123]_none_r[123]|G[123]_trim_r[123]|G4_trim_r[123]) ;; *) echo FAIL_POINT_CELL; exit 2;; esac
phase=${relative#"$cell"/points/}
case "$phase" in [0-9][0-9]_pre|[0-9][0-9]_post) ;; *) echo FAIL_POINT_PHASE; exit 2;; esac
[ "$out" = "$work/$cell/points/$phase" ] || { echo FAIL_POINT_PATH; exit 2; }
cycle=${phase%%_*}
case "$cell:$cycle" in G[12]_*:0[12]|G3_*:0[1-9]|G3_*:[1-4][0-9]|G3_*:5[01]|G4_*:01) ;; *) echo FAIL_POINT_CYCLE; exit 2;; esac
ancestor=$out
while [ "$ancestor" != / ]; do
    [ ! -L "$ancestor" ] || { echo FAIL_POINT_SYMLINK; exit 2; }
    ancestor=${ancestor%/*}
    [ -n "$ancestor" ] || break
done
[ ! -e "$out" ] || { echo FAIL_POINT_ALREADY_EXISTS; exit 2; }
mkdir -p "$out" || exit 2
log="$out/capture_commands.txt"
record()
{
    name=$1
    shift
    "$@" >"$out/$name" 2>"$out/$name.stderr"
    rc=$?
    printf 'CMD=%s RC=%s\n' "$*" "$rc" >>"$log" || return 1
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
