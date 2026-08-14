#!/usr/bin/env bash
set -u

SDB=${SDB:-<USER_HOME>/tizen-studio/tools/sdb}
BOARD_IP=${BOARD_IP:-<TEST_BOARD_IP>}
OUT=${OUT:-board_results/batch2}
BIN=${BIN:-bench/alloc_bench/alloc_bench.armv7l}
INV=${INV:-docs/tizen_memopt_inventory.sh}
REMOTE_BIN=/tmp/alloc_bench.armv7l
REMOTE_ROOT=/tmp/alloc_bench_batch2
REMOTE_INV=/tmp/tizen_memopt_inventory.sh

RUNLOG="$OUT/host_run.log"
EXCEPTIONS="$OUT/exceptions.log"
SUMMARY="$OUT/run_summary.tsv"

mkdir -p "$OUT"
: > "$RUNLOG"
: > "$EXCEPTIONS"
printf 'profile\tgrid\trep\tattempt\texit_code\tthroughput_ops_per_s\tp50\tp99\tmeasure_rss_kb_median\tidle_rss_kb\ttemp_before\tjson_status\tlocal_dir\n' > "$SUMMARY"

RESTORED=0
SETUP_STARTED=0

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$RUNLOG"
}

exception() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$EXCEPTIONS" "$RUNLOG"
}

sdb_cmd() {
  log "CMD: $SDB $*"
  "$SDB" "$@" 2>&1 | tee -a "$RUNLOG"
  return "${PIPESTATUS[0]}"
}

sdb_capture() {
  local outfile=$1
  shift
  log "CMD: $SDB $* > $outfile 2>&1"
  "$SDB" "$@" > "$outfile" 2>&1
  local rc=$?
  log "RC=$rc for $outfile"
  return "$rc"
}

sdb_shell_capture() {
  local outfile=$1
  local cmd=$2
  log "CMD: $SDB shell $cmd > $outfile 2>&1"
  "$SDB" shell "$cmd" > "$outfile" 2>&1
  local rc=$?
  log "RC=$rc for $outfile"
  return "$rc"
}

restore_governor() {
  [ "$RESTORED" -eq 1 ] && return 0
  RESTORED=1
  mkdir -p "$OUT/restore"
  {
    echo "RESTORE_DATE=$(date -Iseconds)"
    if [ -f "$OUT/governor_original.tsv" ]; then
      while IFS='	' read -r path value; do
        [ -z "${path:-}" ] && continue
        [ "$path" = "NO_CPUFREQ" ] && continue
        safe_path=${path//\'/\'\\\'\'}
        safe_value=${value//\'/\'\\\'\'}
        "$SDB" shell "if [ -e '$safe_path' ]; then echo '$safe_value' > '$safe_path' 2>&1; echo RESTORE:$safe_path=\$(cat '$safe_path' 2>&1); else echo MISSING:$safe_path; fi"
      done < "$OUT/governor_original.tsv"
    else
      echo "no governor_original.tsv"
    fi
    echo "--- verify ---"
    "$SDB" shell "for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do [ -e \"\$f\" ] || continue; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done"
  } > "$OUT/restore/governor_restore.log" 2>&1
}

cleanup_board_tmp() {
  mkdir -p "$OUT/restore"
  sdb_shell_capture "$OUT/restore/tmp_cleanup.log" "rm -rf '$REMOTE_ROOT' '$REMOTE_BIN' '$REMOTE_INV' /tmp/batch2_pre_inventory.tsv /tmp/batch2_pre_inventory_summary.txt /tmp/batch2_post_inventory.tsv /tmp/batch2_post_inventory_summary.txt /tmp/alloc_batch2_smoke; ls -l /tmp | sed -n '1,120p'"
}

on_exit() {
  local rc=$?
  if [ "$SETUP_STARTED" -eq 1 ]; then
    restore_governor || true
  fi
  exit "$rc"
}
trap on_exit EXIT INT TERM

quote_sh() {
  printf "%s" "$1" | sed "s/'/'\\\\''/g"
}

read_max_temp() {
  "$SDB" shell "max=NA; for f in /sys/class/thermal/thermal_zone*/temp; do [ -e \"\$f\" ] || continue; v=\$(cat \"\$f\" 2>/dev/null || echo NA); case \"\$v\" in ''|*[!0-9-]*) ;; *) if [ \"\$max\" = NA ] || [ \"\$v\" -gt \"\$max\" ]; then max=\$v; fi ;; esac; done; echo \$max" 2>/dev/null | tr -d '\r' | awk 'NF{print $1; exit}'
}

record_temps_remote() {
  local remote_dir=$1
  local label=$2
  "$SDB" shell "{
    echo '$label DATE='\"\$(date)\";
    max=NA;
    for f in /sys/class/thermal/thermal_zone*/temp; do
      [ -e \"\$f\" ] || continue;
      v=\$(cat \"\$f\" 2>/dev/null || echo NA);
      echo '$label '\"\$f=\$v\";
      case \"\$v\" in ''|*[!0-9-]*) ;; *) if [ \"\$max\" = NA ] || [ \"\$v\" -gt \"\$max\" ]; then max=\$v; fi ;; esac;
    done;
    echo '${label}_MAX='\"\$max\";
  } >> '$remote_dir/thermal.txt'" >/dev/null 2>&1
}

thermal_gate() {
  local profile=$1 grid=$2 rep=$3 attempt=$4
  local temp
  temp=$(read_max_temp)
  [ -z "$temp" ] && temp=NA
  if printf '%s' "$temp" | grep -Eq '^[0-9]+$' && [ "$temp" -gt 70000 ]; then
    exception "thermal wait before $profile/$grid/rep$rep attempt$attempt: temp=${temp}mC > 70000"
    local wait_log="$OUT/thermal_waits.log"
    printf '[%s] START %s %s rep%s attempt%s temp=%s\n' "$(date -Iseconds)" "$profile" "$grid" "$rep" "$attempt" "$temp" >> "$wait_log"
    while :; do
      sleep 10
      temp=$(read_max_temp)
      [ -z "$temp" ] && temp=NA
      printf '[%s] POLL %s %s rep%s attempt%s temp=%s\n' "$(date -Iseconds)" "$profile" "$grid" "$rep" "$attempt" "$temp" >> "$wait_log"
      if ! printf '%s' "$temp" | grep -Eq '^[0-9]+$'; then
        break
      fi
      [ "$temp" -lt 65000 ] && break
    done
    exception "thermal wait ended before $profile/$grid/rep$rep attempt$attempt: temp=${temp}mC"
  fi
}

pull_remote_dir() {
  local remote_dir=$1
  local local_parent=$2
  mkdir -p "$local_parent"
  sdb_capture "$local_parent/pull.log" pull "$remote_dir" "$local_parent/"
}

append_summary() {
  local profile=$1 grid=$2 rep=$3 attempt=$4 exit_code=$5 local_dir=$6
  python3 - "$SUMMARY" "$profile" "$grid" "$rep" "$attempt" "$exit_code" "$local_dir" <<'PY'
import json
import pathlib
import sys

summary, profile, grid, rep, attempt, exit_code, local_dir = sys.argv[1:]
path = pathlib.Path(local_dir) / "result.json"
temp_path = pathlib.Path(local_dir) / "thermal.txt"
temp_before = "NA"
if temp_path.exists():
    for line in temp_path.read_text(errors="replace").splitlines():
        if line.startswith("BEFORE_MAX="):
            temp_before = line.split("=", 1)[1].strip()
            break

vals = {
    "throughput_ops_per_s": "NA",
    "p50": "NA",
    "p99": "NA",
    "measure_rss_kb_median": "NA",
    "idle_rss_kb": "NA",
}
json_status = "missing"
if path.exists():
    try:
        data = json.loads(path.read_text())
        vals["throughput_ops_per_s"] = str(data["throughput_ops_per_s"])
        vals["p50"] = str(data["latency_ns"]["p50"])
        vals["p99"] = str(data["latency_ns"]["p99"])
        vals["measure_rss_kb_median"] = str(data["memory"]["measure_rss_kb_median"])
        vals["idle_rss_kb"] = str(data["memory"]["idle_rss_kb"])
        json_status = "ok"
    except Exception as exc:
        json_status = "bad:" + type(exc).__name__

row = [
    profile, grid, rep, attempt, exit_code,
    vals["throughput_ops_per_s"], vals["p50"], vals["p99"],
    vals["measure_rss_kb_median"], vals["idle_rss_kb"],
    temp_before, json_status, local_dir,
]
with open(summary, "a", encoding="utf-8") as f:
    f.write("\t".join(row) + "\n")
PY
}

run_one_attempt() {
  local profile=$1 grid=$2 rep=$3 attempt=$4 tunable=$5 local_dir=$6 remote_dir=$7
  local q_remote q_tunable cmdline run_cmd
  q_remote=$(quote_sh "$remote_dir")
  q_tunable=$(quote_sh "$tunable")

  thermal_gate "$profile" "$grid" "$rep" "$attempt"

  sdb_shell_capture "$local_dir/mkdir_remote.log" "rm -rf '$q_remote'; mkdir -p '$q_remote'"
  record_temps_remote "$remote_dir" "BEFORE"

  if [ -z "$tunable" ]; then
    cmdline="env -u GLIBC_TUNABLES $REMOTE_BIN --threads 4 --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile $profile --outdir $remote_dir"
    run_cmd="env -u GLIBC_TUNABLES '$REMOTE_BIN' --threads 4 --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile '$profile' --outdir '$q_remote' > '$q_remote/result.json' 2> '$q_remote/stderr.txt'"
  else
    cmdline="env GLIBC_TUNABLES=$tunable $REMOTE_BIN --threads 4 --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile $profile --outdir $remote_dir"
    run_cmd="env GLIBC_TUNABLES='$q_tunable' '$REMOTE_BIN' --threads 4 --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile '$profile' --outdir '$q_remote' > '$q_remote/result.json' 2> '$q_remote/stderr.txt'"
  fi

  "$SDB" shell "{
    echo DATE=\$(date);
    echo PROFILE='$profile';
    echo GRID='$grid';
    echo REP='$rep';
    echo ATTEMPT='$attempt';
    echo GLIBC_TUNABLES='${q_tunable:-<unset>}';
    echo COMMAND='$cmdline';
  } > '$q_remote/cmd.txt'" >/dev/null 2>&1 || true

  log "RUN $profile/$grid/rep$rep attempt$attempt"
  "$SDB" shell "$run_cmd; rc=\$?; echo \$rc > '$q_remote/exit_code.txt'; exit \$rc" > "$local_dir/sdb_run_stdout.txt" 2> "$local_dir/sdb_run_stderr.txt"
  local rc=$?
  record_temps_remote "$remote_dir" "AFTER"
  pull_remote_dir "$remote_dir" "$local_dir"
  append_summary "$profile" "$grid" "$rep" "$attempt" "$rc" "$local_dir"
  return "$rc"
}

pre_inventory() {
  mkdir -p "$OUT/precheck"
  sdb_capture "$OUT/precheck/push_inventory.log" push "$INV" "$REMOTE_INV"
  sdb_shell_capture "$OUT/precheck/inventory_run.log" "chmod +x '$REMOTE_INV'; sh '$REMOTE_INV' > /tmp/batch2_pre_inventory.tsv 2> /tmp/batch2_pre_inventory_summary.txt; echo EXIT=\$?"
  sdb_capture "$OUT/precheck/pull_inventory_tsv.log" pull /tmp/batch2_pre_inventory.tsv "$OUT/precheck/"
  sdb_capture "$OUT/precheck/pull_inventory_summary.log" pull /tmp/batch2_pre_inventory_summary.txt "$OUT/precheck/"
  if grep -q 'processes with LIVE env blacklist hits: 0' "$OUT/precheck/batch2_pre_inventory_summary.txt"; then
    log "pre-inventory LIVE hits 0"
  else
    exception "pre-inventory did not report LIVE hits 0; see $OUT/precheck/batch2_pre_inventory_summary.txt"
  fi
}

post_inventory() {
  mkdir -p "$OUT/restore"
  sdb_capture "$OUT/restore/push_inventory.log" push "$INV" "$REMOTE_INV"
  sdb_shell_capture "$OUT/restore/inventory_run.log" "chmod +x '$REMOTE_INV'; sh '$REMOTE_INV' > /tmp/batch2_post_inventory.tsv 2> /tmp/batch2_post_inventory_summary.txt; echo EXIT=\$?"
  sdb_capture "$OUT/restore/pull_inventory_tsv.log" pull /tmp/batch2_post_inventory.tsv "$OUT/restore/"
  sdb_capture "$OUT/restore/pull_inventory_summary.log" pull /tmp/batch2_post_inventory_summary.txt "$OUT/restore/"
}

setup_board() {
  SETUP_STARTED=1
  sdb_capture "$OUT/sdb_version.txt" version
  sdb_capture "$OUT/sdb_connect.txt" connect "$BOARD_IP"
  sdb_capture "$OUT/sdb_devices.txt" devices
  sdb_capture "$OUT/sdb_root_on.txt" root on
  sdb_shell_capture "$OUT/root_id.txt" "id"
  sdb_shell_capture "$OUT/os_release.txt" "cat /etc/os-release"
  sdb_shell_capture "$OUT/uname.txt" "uname -a"
  sdb_capture "$OUT/push_binary.log" push "$BIN" "$REMOTE_BIN"
  sdb_shell_capture "$OUT/chmod_binary.log" "chmod +x '$REMOTE_BIN'; ls -l '$REMOTE_BIN'; file '$REMOTE_BIN' 2>/dev/null || true"

  mkdir -p "$OUT/governor"
  sdb_shell_capture "$OUT/governor/original_raw.txt" "found=0; for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do [ -e \"\$f\" ] || continue; found=1; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done; [ \$found -eq 1 ] || echo NO_CPUFREQ"
  if grep -q '^NO_CPUFREQ' "$OUT/governor/original_raw.txt"; then
    printf 'NO_CPUFREQ\tNA\n' > "$OUT/governor_original.tsv"
    exception "no cpufreq scaling_governor nodes found"
  else
    sed 's/=/	/' "$OUT/governor/original_raw.txt" > "$OUT/governor_original.tsv"
    sdb_shell_capture "$OUT/governor/set_performance.log" "for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do [ -e \"\$f\" ] || continue; echo performance > \"\$f\" 2>&1; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done"
  fi
  sdb_shell_capture "$OUT/governor/after_set.log" "for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do [ -e \"\$f\" ] || continue; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done"

  mkdir -p "$OUT/initial"
  sdb_shell_capture "$OUT/initial/covariates.txt" "echo ---overcommit---; cat /proc/sys/vm/overcommit_memory; echo ---free---; free; echo ---uptime---; uptime; echo ---thermal---; for f in /sys/class/thermal/thermal_zone*/temp; do [ -e \"\$f\" ] || continue; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done"
  pre_inventory
}

smoke_test() {
  mkdir -p "$OUT/smoke"
  sdb_shell_capture "$OUT/smoke/run.log" "rm -rf /tmp/alloc_batch2_smoke; mkdir -p /tmp/alloc_batch2_smoke; env -u GLIBC_TUNABLES '$REMOTE_BIN' --profile small-churn --threads 2 --seed 1 --warmup 0 --ops-per-thread 1000 --idle 0 --outdir /tmp/alloc_batch2_smoke > /tmp/alloc_batch2_smoke/result.json 2> /tmp/alloc_batch2_smoke/stderr.txt; echo EXIT=\$? > /tmp/alloc_batch2_smoke/exit_code.txt; cat /tmp/alloc_batch2_smoke/exit_code.txt"
  sdb_capture "$OUT/smoke/pull.log" pull /tmp/alloc_batch2_smoke "$OUT/smoke/"
  if [ ! -f "$OUT/smoke/alloc_batch2_smoke/result.json" ]; then
    exception "smoke failed: result.json missing"
    return 1
  fi
  if ! python3 -m json.tool "$OUT/smoke/alloc_batch2_smoke/result.json" > "$OUT/smoke/result.pretty.json" 2> "$OUT/smoke/json_tool.err"; then
    exception "smoke failed: JSON parse failed"
    return 1
  fi
  if [ -s "$OUT/smoke/alloc_batch2_smoke/stderr.txt" ]; then
    exception "smoke stderr non-empty; see $OUT/smoke/alloc_batch2_smoke/stderr.txt"
  fi
  if ! grep -q '^0$' "$OUT/smoke/alloc_batch2_smoke/exit_code.txt"; then
    exception "smoke failed: exit code $(cat "$OUT/smoke/alloc_batch2_smoke/exit_code.txt")"
    return 1
  fi
  log "smoke ok"
}

run_matrix() {
  local profiles=(small-churn mixed large-transient thread-churn)
  local grid_names=(C0 T-L3 T-L4a T-L4b T-L11 T-L12 T-L2 T-B1)
  local grid_vals=(
    ""
    "glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072"
    "glibc.malloc.tcache_count=3"
    "glibc.malloc.tcache_count=0"
    "glibc.malloc.mxfast=0"
    "glibc.malloc.tcache_unsorted_limit=3"
    "glibc.malloc.arena_max=2"
    "glibc.malloc.arena_max=2:glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072:glibc.malloc.tcache_unsorted_limit=3"
  )
  for profile in "${profiles[@]}"; do
    for idx in "${!grid_names[@]}"; do
      local grid=${grid_names[$idx]}
      local tunable=${grid_vals[$idx]}
      for rep in 1 2 3; do
        local local_dir="$OUT/$profile/$grid/rep$rep"
        local remote_dir="$REMOTE_ROOT/$profile/$grid/rep$rep"
        mkdir -p "$local_dir"
        run_one_attempt "$profile" "$grid" "$rep" 1 "$tunable" "$local_dir" "$remote_dir"
        local rc=$?
        if [ "$rc" -ne 0 ]; then
          exception "run failed: $profile/$grid/rep$rep attempt1 rc=$rc; retrying once"
          local fail_dir="$OUT/$profile/$grid/rep${rep}_failed_attempt1"
          rm -rf "$fail_dir"
          mv "$local_dir" "$fail_dir"
          mkdir -p "$local_dir"
          run_one_attempt "$profile" "$grid" "$rep" 2 "$tunable" "$local_dir" "$REMOTE_ROOT/$profile/$grid/rep${rep}_retry1"
          rc=$?
          if [ "$rc" -ne 0 ]; then
            exception "run failed: $profile/$grid/rep$rep attempt2 rc=$rc; continuing"
          fi
        fi
        sleep 5
      done
    done
    if [ "$profile" = "thread-churn" ]; then
      local grid=T-L1
      local tunable="glibc.pthread.stack_cache_size=1048576"
      for rep in 1 2 3; do
        local local_dir="$OUT/$profile/$grid/rep$rep"
        local remote_dir="$REMOTE_ROOT/$profile/$grid/rep$rep"
        mkdir -p "$local_dir"
        run_one_attempt "$profile" "$grid" "$rep" 1 "$tunable" "$local_dir" "$remote_dir"
        local rc=$?
        if [ "$rc" -ne 0 ]; then
          exception "run failed: $profile/$grid/rep$rep attempt1 rc=$rc; retrying once"
          local fail_dir="$OUT/$profile/$grid/rep${rep}_failed_attempt1"
          rm -rf "$fail_dir"
          mv "$local_dir" "$fail_dir"
          mkdir -p "$local_dir"
          run_one_attempt "$profile" "$grid" "$rep" 2 "$tunable" "$local_dir" "$REMOTE_ROOT/$profile/$grid/rep${rep}_retry1"
          rc=$?
          if [ "$rc" -ne 0 ]; then
            exception "run failed: $profile/$grid/rep$rep attempt2 rc=$rc; continuing"
          fi
        fi
        sleep 5
      done
    fi
  done
}

main() {
  log "Batch2 alloc_bench start"
  setup_board
  if ! smoke_test; then
    exception "smoke failed; stopping before matrix"
    cleanup_board_tmp
    post_inventory
    log "Batch2 alloc_bench stopped after smoke failure"
    return 1
  fi
  run_matrix
  restore_governor
  post_inventory
  cleanup_board_tmp
  log "Batch2 alloc_bench complete"
}

main "$@"
