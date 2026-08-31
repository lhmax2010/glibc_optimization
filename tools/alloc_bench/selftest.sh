#!/bin/sh
set -u

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TMP=${TMPDIR:-/tmp}/alloc_bench_selftest.$$
PASS_COUNT=0
FAIL_COUNT=0

mkdir -p "$TMP"

cleanup() {
    rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

say() {
    printf '%s\n' "$*"
}

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    say "PASS $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    say "FAIL $1"
}

run_cmd() {
    printf '+ %s\n' "$*" >&2
    "$@"
}

run_profile_asan() {
    profile=$1
    out=$2
    shift 2
    mkdir -p "$out"
    ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 \
        run_cmd ./alloc_bench.host-asan --profile "$profile" --threads 2 \
        --seed 77 --warmup 0 --ops-per-thread 2048 --idle 0 \
        --outdir "$out" "$@"
}

cd "$DIR" || exit 1

if run_cmd make host >"$TMP/make-host.log" 2>&1; then
    pass "build host"
else
    fail "build host"
    cat "$TMP/make-host.log"
    exit 1
fi

mkdir -p "$TMP/a1a" "$TMP/a1b"
if run_cmd ./alloc_bench.host --profile small-churn --threads 2 --seed 12345 --warmup 0 --ops-per-thread 4096 --idle 0 --outdir "$TMP/a1a" >"$TMP/a1a.json" 2>"$TMP/a1a.err" &&
   run_cmd ./alloc_bench.host --profile small-churn --threads 2 --seed 12345 --warmup 0 --ops-per-thread 4096 --idle 0 --outdir "$TMP/a1b" >"$TMP/a1b.json" 2>"$TMP/a1b.err" &&
   python3 - "$TMP/a1a.json" "$TMP/a1b.json" <<'PY'
import json, sys
a = json.load(open(sys.argv[1]))
b = json.load(open(sys.argv[2]))
assert a["thread_ops"] == b["thread_ops"], (a["thread_ops"], b["thread_ops"])
assert a["thread_size_hash"] == b["thread_size_hash"], (a["thread_size_hash"], b["thread_size_hash"])
assert a["schema"] == "alloc_bench_v1_1"
PY
then
    pass "A1 determinism"
else
    fail "A1 determinism"
    cat "$TMP/a1a.err" "$TMP/a1b.err" 2>/dev/null || true
fi

if run_cmd make host-asan >"$TMP/make-asan.log" 2>&1; then
    asan_ok=1
    for profile in small-churn mixed medium-only large-transient thread-churn; do
        if ! run_profile_asan "$profile" "$TMP/asan-$profile" >"$TMP/asan-$profile.json" 2>"$TMP/asan-$profile.err"; then
            asan_ok=0
            cat "$TMP/asan-$profile.err"
            break
        fi
    done
    if [ "$asan_ok" -eq 1 ] &&
       ! run_profile_asan burst-free-small "$TMP/asan-burst-free-small" --burst-size 512 --burst-hold-ops 512 >"$TMP/asan-burst-free-small.json" 2>"$TMP/asan-burst-free-small.err"; then
        asan_ok=0
        cat "$TMP/asan-burst-free-small.err"
    fi
    if [ "$asan_ok" -eq 1 ] &&
       ! run_profile_asan unsorted-drain "$TMP/asan-unsorted-drain" --unsorted-batch 512 >"$TMP/asan-unsorted-drain.json" 2>"$TMP/asan-unsorted-drain.err"; then
        asan_ok=0
        cat "$TMP/asan-unsorted-drain.err"
    fi
    if [ "$asan_ok" -eq 1 ]; then
        pass "A2 ASan+UBSan seven built-in profiles"
    else
        fail "A2 ASan+UBSan seven built-in profiles"
    fi
else
    fail "A2 ASan+UBSan build"
    cat "$TMP/make-asan.log"
fi

mkdir -p "$TMP/a3"
if run_cmd ./alloc_bench.host --profile small-churn --threads 2 --seed 99 --warmup 0 --ops-per-thread 4096 --idle 0 --outdir "$TMP/a3" >"$TMP/a3.json" 2>"$TMP/a3.err" &&
   python3 - "$TMP/a3.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
rss = d["memory"]["measure_rss_kb_median"]
floor = d["theoretical_live_kb"]
assert rss >= floor, (rss, floor)
PY
then
    pass "A3 RSS lower-bound sanity"
else
    fail "A3 RSS lower-bound sanity"
    cat "$TMP/a3.err" 2>/dev/null || true
fi

if python3 -m json.tool "$TMP/a1a.json" >/dev/null; then
    pass "A4 JSON parse"
else
    fail "A4 JSON parse"
fi

if run_cmd make armv7l >"$TMP/make-armv7l.log" 2>&1 &&
   file ./alloc_bench.armv7l >"$TMP/file-armv7l.log" 2>&1 &&
   grep -q 'ELF 32-bit' "$TMP/file-armv7l.log" &&
   grep -q 'ARM' "$TMP/file-armv7l.log" &&
   grep -qi 'dynamically linked' "$TMP/file-armv7l.log"; then
    pass "A5 armv7l ELF 32-bit ARM dynamic"
else
    fail "A5 armv7l ELF 32-bit ARM dynamic"
    cat "$TMP/make-armv7l.log" "$TMP/file-armv7l.log" 2>/dev/null || true
fi

mkdir -p "$TMP/a6"
if run_cmd ./alloc_bench.host --profile burst-free-small --threads 1 --seed 20260709 --warmup 0 --ops-per-thread 3456 --idle 0 --outdir "$TMP/a6" >"$TMP/a6.json" 2>"$TMP/a6.err" &&
   python3 - "$TMP/a6.json" <<'PY'
import json, sys, xml.etree.ElementTree as ET
d = json.load(open(sys.argv[1]))
xml_path = d["memory"]["malloc_info_measure"]
root = ET.parse(xml_path).getroot()
direct = [int(x.attrib.get("size", "0")) for x in root.findall("total") if x.attrib.get("type") == "fast"]
fast_bytes = direct[-1] if direct else 0
if fast_bytes == 0:
    total = 0
    for elem in root.findall(".//size"):
        to = int(elem.attrib.get("to", "0"))
        if to <= 80:
            total += int(elem.attrib.get("total", "0"))
    fast_bytes = total
expected = (d["burst_size"] // 2) * 40
threshold = expected * 0.50
print(f"A6_FAST_BYTES={fast_bytes} EXPECTED_BYTES={expected} THRESHOLD_BYTES={threshold:.0f}")
assert fast_bytes >= threshold, (fast_bytes, threshold)
PY
then
    pass "A6 burst-free-small fastbin residual"
else
    fail "A6 burst-free-small fastbin residual"
    cat "$TMP/a6.err" 2>/dev/null || true
fi

mkdir -p "$TMP/a7a"
if run_cmd ./alloc_bench.host --profile mixed --threads 2 --seed 20260709 --warmup 1 --duration 3 --idle 1 --idle-release 50 --outdir "$TMP/a7a" >"$TMP/a7a.json" 2>"$TMP/a7a.err" &&
   python3 - "$TMP/a7a.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
m = d["memory"]
release_bytes = d["theoretical_live_kb"] * 1024.0 * 0.50
free_delta = d["idle_free_bytes_idle"] - d["idle_free_bytes_measure"]
free_threshold = release_bytes * 0.70
rss_delta_kb = abs(m["idle_rss_kb"] - m["measure_rss_kb_median"])
rss_threshold_kb = (release_bytes / 1024.0) * 0.10
print(f"A7A_FREE_DELTA_BYTES={free_delta} RELEASE_BYTES={release_bytes:.0f} FREE_THRESHOLD_BYTES={free_threshold:.0f} RSS_DELTA_KB={rss_delta_kb:.1f} RSS_THRESHOLD_KB={rss_threshold_kb:.1f}")
assert free_delta >= free_threshold, (free_delta, free_threshold)
assert rss_delta_kb < rss_threshold_kb, (rss_delta_kb, rss_threshold_kb)
assert d["idle_trim"] is False
assert d["idle_trim_ret"] == -1
PY
then
    pass "A7a mixed idle-release retained free bytes"
else
    fail "A7a mixed idle-release retained free bytes"
    cat "$TMP/a7a.err" 2>/dev/null || true
fi

mkdir -p "$TMP/a7b"
if run_cmd ./alloc_bench.host --profile mixed --threads 2 --seed 20260709 --warmup 1 --duration 3 --idle 1 --idle-release 50 --idle-trim --outdir "$TMP/a7b" >"$TMP/a7b.json" 2>"$TMP/a7b.err" &&
   python3 - "$TMP/a7b.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
m = d["memory"]
release_kb = d["theoretical_live_kb"] * 0.50
reclaimed_kb = m["measure_rss_kb_median"] - m["idle_rss_kb"]
threshold = release_kb * 0.30
print(f"A7B_RECLAIMED_KB={reclaimed_kb:.1f} RELEASE_KB={release_kb:.1f} THRESHOLD_KB={threshold:.1f} IDLE_TRIM_RET={d['idle_trim_ret']}")
assert d["idle_trim"] is True
assert d["idle_trim_ret"] >= 0
assert reclaimed_kb >= threshold, (reclaimed_kb, threshold)
PY
then
    pass "A7b mixed idle-release idle-trim OS reclaim"
else
    fail "A7b mixed idle-release idle-trim OS reclaim"
    cat "$TMP/a7b.err" 2>/dev/null || true
fi

mkdir -p "$TMP/a8a" "$TMP/a8b" "$TMP/a8c" "$TMP/a8d"
if run_cmd ./alloc_bench.host --profile burst-free-small --threads 2 --seed 333 --warmup 0 --ops-per-thread 3456 --idle 0 --outdir "$TMP/a8a" >"$TMP/a8a.json" 2>"$TMP/a8a.err" &&
   run_cmd ./alloc_bench.host --profile burst-free-small --threads 2 --seed 333 --warmup 0 --ops-per-thread 3456 --idle 0 --outdir "$TMP/a8b" >"$TMP/a8b.json" 2>"$TMP/a8b.err" &&
   run_cmd ./alloc_bench.host --profile unsorted-drain --threads 2 --seed 333 --warmup 0 --ops-per-thread 1536 --idle 0 --unsorted-batch 512 --outdir "$TMP/a8c" >"$TMP/a8c.json" 2>"$TMP/a8c.err" &&
   run_cmd ./alloc_bench.host --profile unsorted-drain --threads 2 --seed 333 --warmup 0 --ops-per-thread 1536 --idle 0 --unsorted-batch 512 --outdir "$TMP/a8d" >"$TMP/a8d.json" 2>"$TMP/a8d.err" &&
   python3 - "$TMP/a8a.json" "$TMP/a8b.json" "$TMP/a8c.json" "$TMP/a8d.json" <<'PY'
import json, sys
pairs = [(sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])]
for left, right in pairs:
    a = json.load(open(left))
    b = json.load(open(right))
    assert a["thread_ops"] == b["thread_ops"], (a["profile"], a["thread_ops"], b["thread_ops"])
    assert a["thread_size_hash"] == b["thread_size_hash"], (a["profile"], a["thread_size_hash"], b["thread_size_hash"])
PY
then
    pass "A8 new-profile determinism"
else
    fail "A8 new-profile determinism"
    cat "$TMP/a8a.err" "$TMP/a8b.err" "$TMP/a8c.err" "$TMP/a8d.err" 2>/dev/null || true
fi

if python3 - "$DIR" "$TMP" <<'PY'
import json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
expected_hist = {
    "small-churn": [(16,1),(32,1),(64,1),(128,1),(256,1)],
    "mixed": [(16,8),(64,12),(256,18),(1024,24),(4096,18),(16384,12),(32768,6),(65536,2)],
    "large-transient": [(16,8),(64,12),(256,18),(1024,24),(4096,18),(16384,12),(32768,6),(65536,2)],
    "thread-churn": [(16,8),(64,12),(256,18),(1024,24),(4096,18),(16384,12),(32768,6),(65536,2)],
}
old_fields = [
    "profile", "mode", "threads", "seed", "warmup_s", "duration_s",
    "idle_s", "ops_per_thread", "live_set_per_thread",
    "churn_period_ms", "large_period_ops", "large_hold_ops",
    "avg_size_bytes", "theoretical_live_kb", "histogram",
    "measure_elapsed_s", "measure_ops", "throughput_ops_per_s",
    "thread_ops", "thread_size_hash", "op_hash_fn", "latency_ns",
    "memory",
]
for profile in expected_hist:
    outdir = tmp / f"a9-{profile}"
    outdir.mkdir(exist_ok=True)
    json_path = tmp / f"a9-{profile}.json"
    cmd = [
        str(root / "alloc_bench.host"), "--profile", profile,
        "--threads", "2", "--seed", "444", "--warmup", "0",
        "--ops-per-thread", "1024", "--idle", "0", "--outdir", str(outdir),
    ]
    subprocess.check_call(cmd, stdout=json_path.open("w"))
    d = json.load(json_path.open())
    assert d["schema"] == "alloc_bench_v1_1"
    for field in old_fields:
        assert field in d, (profile, field)
    got = [(x["size"], x["weight"]) for x in d["histogram"]]
    assert got == expected_hist[profile], (profile, got)
    assert d["touch_policy"] in ("ge128k_full_else_edge64", "full")
print("A9_OLD_FIELD_STRUCTURES_OK=4")
PY
then
    pass "A9 v1 profile old-field compatibility"
else
    fail "A9 v1 profile old-field compatibility"
fi

a10_ok=1
for order in high low random interleave; do
    mkdir -p "$TMP/a10-$order"
    if ! run_cmd ./alloc_bench.host --profile mixed --threads 2 --seed 20260813 \
        --warmup 0 --ops-per-thread 4096 --idle 0 --live-set 512 \
        --idle-release 50 --release-order "$order" --idle-trim \
        --post-trim-ops-per-thread 256 --outdir "$TMP/a10-$order" \
        >"$TMP/a10-$order.json" 2>"$TMP/a10-$order.err"; then
        a10_ok=0
        cat "$TMP/a10-$order.err"
    fi
done
if [ "$a10_ok" -eq 1 ] &&
   python3 - "$TMP" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for order in ("high", "low", "random", "interleave"):
    d = json.load((root / f"a10-{order}.json").open())
    m = d["memory"]
    assert d["release_order"] == order
    assert d["idle_released_objects"] == 512
    assert d["idle_released_bytes"] > 0
    assert d["post_trim_ops_per_thread"] == 256
    assert d["idle_trim_ret"] >= 0
    assert m["trim_elapsed_ns"] > 0
    assert m["faults"]["minflt_postrefault"] >= m["faults"]["minflt_posttrim"]
    assert m["malloc_info_stats"]["release"]["rest_bytes"] >= 0
    for key in ("malloc_info_release", "malloc_info_posttrim"):
        assert pathlib.Path(m[key]).is_file(), (order, key)
print("A10_RELEASE_ORDERS_AND_EXTENDED_FIELDS_OK=4")
PY
then
    pass "A10 release orders and applicability instrumentation"
else
    fail "A10 release orders and applicability instrumentation"
fi

mkdir -p "$TMP/a11"
if run_cmd ./alloc_bench.host --profile mixed --threads 2 --seed 20260814 \
    --warmup 0 --live-set 64 --idle-release 50 --release-order high \
    --cycles 2 --cycle-rise 0.1 --cycle-peak 0.05 \
    --release-duration 0.4 --cycle-valley 0.05 --trim-at valley \
    --outdir "$TMP/a11" >"$TMP/a11.json" 2>"$TMP/a11.err" &&
   python3 - "$TMP/a11.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["schema"] == "alloc_bench_v1_1"
assert d["mode"] == "cyclic"
assert d["cycles"] == 2
for c in d["cycle_data"]:
    checkpoints = c["release_progress_ns"]
    expected = [100_000_000, 200_000_000, 300_000_000, 400_000_000]
    for got, want in zip(checkpoints, expected):
        assert want * 0.75 <= got <= want * 1.35, (checkpoints, expected)
    assert checkpoints == sorted(checkpoints), checkpoints
    assert c["release_elapsed_ns"] >= 380_000_000, c["release_elapsed_ns"]
    assert c["released_objects"] == 64, c["released_objects"]
    assert c["trim_return"] >= 0
    for stage in ("peak", "fall_mid", "valley", "posttrim"):
        assert stage in c["malloc_info_stats"]
print("A11_RELEASE_PROGRESS_NS=" + repr(d["cycle_data"][0]["release_progress_ns"]))
PY
then
    pass "A11 cyclic progressive-release timing"
else
    fail "A11 cyclic progressive-release timing"
    cat "$TMP/a11.err" 2>/dev/null || true
fi

say "SUMMARY PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
