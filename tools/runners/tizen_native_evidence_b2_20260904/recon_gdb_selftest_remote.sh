#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/tizen_native_evidence_20260905
selftest="$work/selftest"
bench="$selftest/alloc_bench.armv7l"
trim="$selftest/trim_via_gdb.sh"
pid=

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    exit "$rc"
}
trap finish EXIT HUP INT TERM

fail()
{
    echo "reason=$1"
    echo RC=1
    echo FAIL_GDB_SELFTEST
    exit 1
}

test "$(sha256sum "$bench" | awk '{print $1}')" = \
    88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa || fail bench_sha
test -x "$bench" || fail bench_executable
test -x "$trim" || fail trim_script_executable

"$bench" --profile mixed --threads 4 --seed 20260814 --live-set 256 \
    --idle-release 50 --release-order high --touch-full --cycles 1 \
    --cycle-rise 3 --cycle-peak 5 --release-duration 0 --cycle-valley 120 \
    --trim-at none --warmup 0 >"$selftest/alloc.json" 2>"$selftest/alloc.stderr" &
pid=$!
echo "pid=$pid"
sleep 10
kill -0 "$pid" 2>/dev/null || fail bench_not_alive
"$trim" "$pid" >"$selftest/gdb_trim.txt" 2>&1
trim_rc=$?
echo "trim_rc=$trim_rc"
grep -Eq '^\$[0-9]+ = [01]$' "$selftest/gdb_trim.txt" || fail missing_trim_return
[ "$trim_rc" -eq 0 ] || fail trim_rc
kill -0 "$pid" 2>/dev/null || fail bench_died_after_detach
kill "$pid" 2>/dev/null || fail bench_kill
wait "$pid" 2>/dev/null || true
pid=
echo RC=0
echo DONE_GDB_SELFTEST
