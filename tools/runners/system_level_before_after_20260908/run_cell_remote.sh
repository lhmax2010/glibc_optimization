#!/bin/sh
# Run precisely one contract cell. Host must validate/pull/health-check before the next.
set -u
work=/opt/usr/glibc_memopt/system_level_before_after_20260908
cell=${1:?cell required}
case "$cell" in G[12]_none_r[123]|G[12]_trim_r[123]|G3_none_r[123]|G3_trim_r[123]|G4_trim_r[123]) ;; *) echo FAIL_CELL_ID; exit 2;; esac
out="$work/$cell"
ancestor=$out
while [ "$ancestor" != / ]; do
    [ ! -L "$ancestor" ] || { echo FAIL_WORK_SYMLINK; exit 2; }
    ancestor=${ancestor%/*}
    [ -n "$ancestor" ] || break
done
[ -d "$work" ] || { echo FAIL_WORK_NOT_PREPARED; exit 2; }
[ ! -e "$out" ] || { echo FAIL_CELL_ALREADY_EXISTS; exit 2; }
mkdir -p "$out" || exit 3
log="$out/controller.log"
bench_pid=
bench_start=
sampler_pid=
sampler_start=
debugger_pid=
debugger_start=
changed=0
mark() { printf '%s\n' "$*" | tee -a "$log"; }
record()
{
    name=$1
    shift
    "$@" >"$out/$name" 2>"$out/$name.stderr"
    record_rc=$?
    mark "CMD=$* RC=$record_rc"
    if [ "$record_rc" -eq 0 ]; then mark "DONE_$name"; else mark "FAIL_$name"; return 1; fi
}
snapshot()
{
    target=$1
    printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$target" || return 1
    d=/opt/usr/share/crash/livedump
    [ -d "$d" ] || return 0
    find "$d" -maxdepth 1 -type f -name '*.zip' >"$target.unsorted" || return 1
    LC_ALL=C sort "$target.unsorted" >"$target.sorted" || return 1
    while IFS= read -r file; do
        size=$(stat -c %s "$file") || return 1
        stamp=$(stat -c %Y "$file") || return 1
        hash=$(sha256sum "$file") || return 1
        printf '%s\t%s\t%s\t%s\n' "$file" "$size" "$stamp" "${hash%% *}" || return 1
    done <"$target.sorted" >>"$target"
    rm "$target.unsorted" "$target.sorted"
}
identity_of() { sed 's/^[^)]*) //' "/proc/$1/stat" | awk '{print $20}'; }
stop_owned()
{
    stop_pid=$1
    stop_start=$2
    for signal in TERM KILL; do
        if ! kill -0 "$stop_pid" 2>/dev/null; then wait "$stop_pid" 2>/dev/null || true; return 0; fi
        [ -n "$stop_start" ] && [ "$(identity_of "$stop_pid")" = "$stop_start" ] || return 1
        kill -"$signal" "$stop_pid" 2>/dev/null || true
        stop_limit=$(( $(date +%s) + 3 ))
        while kill -0 "$stop_pid" 2>/dev/null && [ "$(date +%s)" -lt "$stop_limit" ]; do sleep 0.1; done
    done
    if kill -0 "$stop_pid" 2>/dev/null; then mark "FAIL_OWN_PROCESS_STILL_PRESENT pid=$stop_pid"; return 1; fi
    wait "$stop_pid" 2>/dev/null || true
}
stop_sampler()
{
    if [ -n "$sampler_pid" ]; then
        # Unlink only our proxy symlink; never the target /proc directory.
        link="$out/proc/$bench_pid"
        if [ -L "$link" ] && [ "$(readlink "$link")" = "/proc/$bench_pid" ]; then rm "$link" || return 1; fi
        sampler_deadline=$(( $(date +%s) + 3 ))
        while kill -0 "$sampler_pid" 2>/dev/null && [ "$(date +%s)" -lt "$sampler_deadline" ]; do sleep 0.1; done
        if kill -0 "$sampler_pid" 2>/dev/null; then
            stop_owned "$sampler_pid" "$sampler_start" || true
            sampler_pid=
            return 1
        fi
        wait "$sampler_pid"; sampler_rc=$?
        sampler_pid=
        [ "$sampler_rc" -eq 0 ] || return 1
    fi
}
finish()
{
    finish_rc=$?
    trap - EXIT HUP INT TERM
    # Restoration comes before any process wait or evidence command.
    if [ "$changed" -eq 1 ]; then
        for n in 0 1 2 3; do printf '%s\n' schedutil >"/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor" || finish_rc=84; done
    fi
    if [ -n "$debugger_pid" ]; then
        stop_owned "$debugger_pid" "$debugger_start" || finish_rc=87
    fi
    if [ -n "$bench_pid" ] && [ "${cell%%_*}" != G4 ] && kill -0 "$bench_pid" 2>/dev/null; then
        stop_owned "$bench_pid" "$bench_start" || finish_rc=86
    fi
    stop_sampler || finish_rc=80
    record dmesg_after.txt dmesg || finish_rc=81
    record zram_after.txt cat /sys/block/zram0/mm_stat || finish_rc=82
    snapshot "$out/stability_after.tsv" || finish_rc=83
    for n in 0 1 2 3; do cat "/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor"; done >"$out/governor_after.txt"
    [ "$(grep -c '^schedutil$' "$out/governor_after.txt")" -eq 4 ] || finish_rc=85
    date +%s%N >"$out/end_ns.txt"
    printf 'bench_rc=%s\ncontroller_rc=%s\n' "${bench_rc:-NA}" "$finish_rc" >"$out/exit_status.txt"
    mark "RC=$finish_rc"
    if [ "$finish_rc" -eq 0 ]; then mark "DONE_CELL_$cell"; else mark "FAIL_CELL_$cell"; fi
    exit "$finish_rc"
}
trap finish EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
fail() { mark "FAIL_$1"; exit 1; }
wait_child()
{
    child=$1
    child_start=$2
    child_deadline=$(( $(date +%s) + $3 ))
    while kill -0 "$child" 2>/dev/null; do
        [ "$(identity_of "$child")" = "$child_start" ] || return 1
        [ "$(date +%s)" -lt "$child_deadline" ] || return 1
        sleep 0.1
    done
    wait "$child"
}
assert_target()
{
    [ "$(cat "/proc/$bench_pid/comm")" = enlightenment ] &&
    [ -n "$bench_start" ] && [ "$(identity_of "$bench_pid")" = "$bench_start" ]
}
run_gdb()
{
    debugger_name=$1
    shift
    assert_target || return 1
    gdb -p "$bench_pid" -batch "$@" >"$out/$debugger_name" 2>"$out/$debugger_name.stderr" &
    debugger_pid=$!
    debugger_start=$(identity_of "$debugger_pid")
    printf '%s %s\n' "$debugger_pid" "$debugger_start" >"$out/debugger_identity.txt" || return 1
    wait_child "$debugger_pid" "$debugger_start" 30
    debugger_rc=$?
    if [ "$debugger_rc" -ne 0 ]; then
        mark "FAIL_GDB RC=$debugger_rc"
        return 1
    fi
    debugger_pid=
    mark "DONE_GDB RC=0"
    assert_target
}
cover_post()
{
    coverage_end=$(cat "$out/points/$(printf '%02d' "$cycle")_post/meta.json") || return 1
    coverage_end=$(printf '%s\n' "$coverage_end" | sed 's/.*"end_ns":\([0-9]*\).*/\1/')
    coverage_deadline=$(( $(date +%s) + 5 ))
    while :; do
        if awk -F '\t' -v endpoint="$coverage_end" 'NR>1 && $3+0>=endpoint+0 {ok=1} END {exit !ok}' "$out/external_1s.tsv"; then return 0; fi
        kill -0 "$sampler_pid" 2>/dev/null || return 1
        [ "$(date +%s)" -lt "$coverage_deadline" ] || return 1
        sleep 0.05
    done
}
wait_marker()
{
    file=$1
    pattern=$2
    deadline=$(( $(date +%s) + 120 ))
    while ! grep -F "$pattern" "$file" >/dev/null 2>&1; do
        kill -0 "$bench_pid" 2>/dev/null || return 1
        [ "$(date +%s)" -lt "$deadline" ] || return 1
        sleep 0.05
    done
}
start_sampler()
{
    mkdir -p "$out/proc" || return 1
    ln -s "/proc/$bench_pid" "$out/proc/$bench_pid" || return 1
    PROC_ROOT="$out/proc" sh "$work/sample_smaps_1s.sh" "$bench_pid" "$out/external_1s.tsv" "$out/external_sampler_meta.txt" >"$out/sampler_stdout.txt" 2>"$out/sampler_stderr.txt" &
    sampler_pid=$!
    sampler_start=$(identity_of "$sampler_pid")
    printf '%s %s\n' "$sampler_pid" "$sampler_start" >"$out/sampler_identity.txt" || return 1
}
point()
{
    phase=$1
    directory="$out/points/$(printf '%02d' "$cycle")_$phase"
    sh "$work/capture_point.sh" "$bench_pid" "$directory" >>"$log" 2>&1 || return 1
}
printf '%s %s\n' "$$" "$(identity_of "$$")" >"$out/controller_identity.txt" || fail CONTROLLER_ID
record uname_r.txt uname -r || fail IDENTITY
grep -q rpi4 "$out/uname_r.txt" || fail IDENTITY
record uname_m.txt uname -m || fail IDENTITY
[ "$(cat "$out/uname_m.txt")" = armv7l ] || fail IDENTITY
record os_release.txt cat /etc/os-release || fail IDENTITY
grep -Fx 'BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l' "$out/os_release.txt" >/dev/null || fail IDENTITY
record glibc.txt rpm -q glibc || fail GLIBC
grep -Fx glibc-2.40-1.6.armv7l "$out/glibc.txt" >/dev/null || fail GLIBC
record meminfo_gate.txt cat /proc/meminfo || fail MEMTOTAL
awk '/^MemTotal:/ {ok=($2>=8036234 && $2<=8198582)} END {exit !ok}' "$out/meminfo_gate.txt" || fail MEMTOTAL
for n in 0 1 2 3; do
    p=/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor
    [ "$(cat "$p")" = schedutil ] || fail OCCUPIED_GOVERNOR
done
record dmesg_before.txt dmesg || fail HEALTH
record zram_before.txt cat /sys/block/zram0/mm_stat || fail HEALTH
snapshot "$out/stability_before.tsv" || fail HEALTH
changed=1
for n in 0 1 2 3; do printf '%s\n' performance >"/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor" || fail GOVERNOR; done
for n in 0 1 2 3; do cat "/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor"; done >"$out/governor_run.txt"
[ "$(grep -c '^performance$' "$out/governor_run.txt")" -eq 4 ] || fail GOVERNOR
date +%s%N >"$out/start_ns.txt"
case "$cell" in
    G[12]_*)
        profile=mixed; case "$cell" in G2_*) profile=medium-only;; esac
        arm=none; case "$cell" in *_trim_*) arm=valley;; esac
        mkfifo "$out/control.fifo" || fail FIFO
        exec 6<>"$out/control.fifo" || fail FIFO
        "$work/alloc_bench_observer.armv7l" --threads 4 --seed 20260814 --live-set 512 --idle-release 50 --release-order high --touch-full --cycles 2 --cycle-rise 3.4 --cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 --warmup 0 --profile "$profile" --trim-at "$arm" --outdir "$out/xml" 3>"$out/events.txt" 4<"$out/control.fifo" >"$out/result.json" 2>"$out/program_stderr.txt" &
        bench_pid=$!
        bench_start=$(identity_of "$bench_pid")
        printf '%s\n' "$bench_pid" >"$out/pid.txt"
        start_sampler || fail SAMPLER
        cycle=1
        while [ "$cycle" -le 2 ]; do
            wait_marker "$out/events.txt" "PRE $(printf '%02d' "$cycle")" || fail PRE_WAIT
            point pre || fail PRE_CAPTURE
            printf K >&6 || fail PRE_ACK
            wait_marker "$out/events.txt" "POST $(printf '%02d' "$cycle")" || fail POST_WAIT
            point post || fail POST_CAPTURE
            [ "$cycle" -ne 2 ] || cover_post || fail SAMPLER_COVERAGE
            printf K >&6 || fail POST_ACK
            cycle=$((cycle+1))
        done
        wait_child "$bench_pid" "$bench_start" 40; bench_rc=$?
        [ "$bench_rc" -eq 0 ] || fail BENCH
        ;;
    G3_*)
        arm=none; case "$cell" in *_trim_*) arm=trim-at-loop-release;; esac
        mkfifo "$out/control.fifo" || fail FIFO
        exec 6<>"$out/control.fifo" || fail FIFO
        "$work/gst_loop_decode.armv7l" "$work/small_320x240.mp4" 51 20 1 "$arm" control-stdin <"$out/control.fifo" >"$out/program_stdout.txt" 2>"$out/program_stderr.txt" &
        bench_pid=$!
        bench_start=$(identity_of "$bench_pid")
        printf '%s\n' "$bench_pid" >"$out/pid.txt"
        start_sampler || fail SAMPLER
        cycle=1
        while [ "$cycle" -le 51 ]; do
            wait_marker "$out/program_stdout.txt" "cycle=$cycle state=RELEASE_READY" || fail PRE_WAIT
            point pre || fail PRE_CAPTURE
            printf 'PRE_CAPTURED\n' >&6 || fail PRE_ACK
            wait_marker "$out/program_stdout.txt" "cycle=$cycle state=RELEASE_DONE" || fail POST_WAIT
            point post || fail POST_CAPTURE
            [ "$cycle" -ne 51 ] || cover_post || fail SAMPLER_COVERAGE
            printf 'POST_CAPTURED\n' >&6 || fail POST_ACK
            cycle=$((cycle+1))
        done
        wait_child "$bench_pid" "$bench_start" 40; bench_rc=$?
        [ "$bench_rc" -eq 0 ] || fail BENCH
        ;;
    G4_*)
        bench_pid=${2:?approved enlightenment PID required}
        case "$bench_pid" in ''|*[!0-9]*) fail PID;; esac
        [ "$(cat "/proc/$bench_pid/comm")" = enlightenment ] || fail TARGET
        bench_start=$(identity_of "$bench_pid")
        [ "$bench_start" = "${3:?approved enlightenment start tick required}" ] || fail TARGET_RESTARTED
        printf '%s\n' "$bench_pid" >"$out/pid.txt"
        start_sampler || fail SAMPLER
        printf '%s\n' "set \$fp=(void*)fopen(\"$out/malloc_info_pre.xml\",\"w\")" \
          'if $fp == 0' 'echo FAIL_NULL_FILE\n' 'detach' 'quit 1' 'end' \
          'set $mrc=(int)malloc_info(0,$fp)' 'set $crc=(int)fclose($fp)' \
          'if $mrc != 0 || $crc != 0' 'echo FAIL_M7_RETURN\n' 'detach' 'quit 1' 'end' \
          'detach' 'quit 0' >"$out/m7.gdb" || fail M7_COMMAND_FILE
        run_gdb gdb_m7.txt -x "$out/m7.gdb" || fail M7
        [ -s "$out/malloc_info_pre.xml" ] || fail M7
        record m7_xml_check.txt python3 -c 'import sys,xml.etree.ElementTree as E; assert E.parse(sys.argv[1]).getroot().tag == "malloc"; print("VALID_MALLOC_XML")' "$out/malloc_info_pre.xml" || fail M7_XML
        cycle=1
        point pre || fail PRE_CAPTURE
        date +%s%N >"$out/injection_start_ns.txt"
        run_gdb gdb_trim.txt -ex 'call (int)malloc_trim(0)' -ex detach || fail TRIM
        date +%s%N >"$out/injection_end_ns.txt"
        point post || fail POST_CAPTURE
        record idle_stat_start.txt cat "/proc/$bench_pid/stat" || fail IDLE
        date +%s%N >"$out/idle_start_ns.txt"
        # Guard above the frozen 120.000 s lower bound; verify actual nanoseconds on host.
        sleep 120.1
        record idle_stat_end.txt cat "/proc/$bench_pid/stat" || fail IDLE
        date +%s%N >"$out/idle_end_ns.txt"
        bench_rc=0
        ;;
esac
stop_sampler || fail SAMPLER_FINISH
exec 6>&-
[ ! -p "$out/control.fifo" ] || rm "$out/control.fifo" || fail FIFO_CLEANUP
exit 0
