#!/usr/bin/env bash
set -u

SDB=${SDB:-<USER_HOME>/tizen-studio/tools/sdb}
BOARD_IP=${BOARD_IP:-<TEST_BOARD_IP>}
OUT=${OUT:-board_results/batch25}
BIN=${BIN:-bench/alloc_bench/alloc_bench.armv7l}
INV=${INV:-docs/tizen_memopt_inventory.sh}
REMOTE_BIN=/root/alloc_bench.armv7l
REMOTE_ROOT=/root/alloc_bench_batch25
REMOTE_SMOKE=/root/alloc_bench_batch25_smoke
REMOTE_INV=/root/tizen_memopt_inventory.sh

RUNLOG="$OUT/host_run.log"
EXCEPTIONS="$OUT/exceptions.log"
SUMMARY="$OUT/run_summary.tsv"

mkdir -p "$OUT"
: > "$RUNLOG"
: > "$EXCEPTIONS"
printf 'part\tprofile\tactual_profile\tgrid\trep\tattempt\tthreads\textra_args\texit_code\tthroughput_ops_per_s\tp50\tp99\tmeasure_rss_kb_median\tidle_rss_kb\tidle_free_delta_kb\tidle_trim_ret\ttemp_before\tjson_status\tlocal_dir\n' > "$SUMMARY"

RESTORED=0
SETUP_STARTED=0

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$RUNLOG"
}

exception() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$EXCEPTIONS" "$RUNLOG"
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

quote_sh() {
  printf "%s" "$1" | sed "s/'/'\\\\''/g"
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
        safe_path=$(quote_sh "$path")
        safe_value=$(quote_sh "$value")
        "$SDB" shell "if [ -e '$safe_path' ]; then echo '$safe_value' > '$safe_path' 2>&1; echo RESTORE:$safe_path=\$(cat '$safe_path' 2>&1); else echo MISSING:$safe_path; fi"
      done < "$OUT/governor_original.tsv"
    else
      echo "no governor_original.tsv"
    fi
    echo "--- verify ---"
    "$SDB" shell "for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do [ -e \"\$f\" ] || continue; echo \"\$f=\$(cat \"\$f\" 2>&1)\"; done"
  } > "$OUT/restore/governor_restore.log" 2>&1
}

cleanup_board() {
  mkdir -p "$OUT/restore"
  sdb_shell_capture "$OUT/restore/root_cleanup.log" "rm -rf '$REMOTE_ROOT' '$REMOTE_SMOKE' '$REMOTE_BIN' '$REMOTE_INV' /root/batch25_pre_inventory.tsv /root/batch25_pre_inventory_summary.txt /root/batch25_post_inventory.tsv /root/batch25_post_inventory_summary.txt; echo ---ROOT---; ls -la /root | sed -n '1,160p'; echo ---TMP---; ls -la /tmp | sed -n '1,160p'"
}

on_exit() {
  local rc=$?
  if [ "$SETUP_STARTED" -eq 1 ]; then
    restore_governor || true
  fi
  exit "$rc"
}
trap on_exit EXIT INT TERM

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
  local part=$1 profile=$2 actual_profile=$3 grid=$4 rep=$5 attempt=$6 threads=$7 extra_args=$8 exit_code=$9 local_dir=${10}
  python3 - "$SUMMARY" "$part" "$profile" "$actual_profile" "$grid" "$rep" "$attempt" "$threads" "$extra_args" "$exit_code" "$local_dir" <<'PY'
import json
import pathlib
import sys

summary, part, profile, actual_profile, grid, rep, attempt, threads, extra_args, exit_code, local_dir = sys.argv[1:]
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
    "idle_free_delta_kb": "n/a",
    "idle_trim_ret": "n/a",
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
        if part == "D":
            measure_free = int(data.get("idle_free_bytes_measure", 0))
            idle_free = int(data.get("idle_free_bytes_idle", 0))
            vals["idle_free_delta_kb"] = f"{(idle_free - measure_free) / 1024.0:.3f}"
            vals["idle_trim_ret"] = str(data.get("idle_trim_ret", "NA"))
        json_status = "ok"
    except Exception as exc:
        json_status = "bad:" + type(exc).__name__

row = [
    part, profile, actual_profile, grid, rep, attempt, threads, extra_args,
    exit_code, vals["throughput_ops_per_s"], vals["p50"], vals["p99"],
    vals["measure_rss_kb_median"], vals["idle_rss_kb"],
    vals["idle_free_delta_kb"], vals["idle_trim_ret"],
    temp_before, json_status, local_dir,
]
with open(summary, "a", encoding="utf-8") as f:
    f.write("\t".join(row) + "\n")
PY
}

run_one_attempt() {
  local part=$1 profile=$2 actual_profile=$3 grid=$4 rep=$5 attempt=$6 tunable=$7 threads=$8 extra_args=$9 local_dir=${10} remote_dir=${11}
  local q_remote q_tunable cmdline env_prefix run_cmd
  q_remote=$(quote_sh "$remote_dir")
  q_tunable=$(quote_sh "$tunable")

  thermal_gate "$profile" "$grid" "$rep" "$attempt"

  sdb_shell_capture "$local_dir/mkdir_remote.log" "rm -rf '$q_remote'; mkdir -p '$q_remote'"
  record_temps_remote "$remote_dir" "BEFORE"

  if [ -z "$tunable" ]; then
    env_prefix="env -u GLIBC_TUNABLES"
    cmdline="$env_prefix $REMOTE_BIN --threads $threads --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile $actual_profile $extra_args --outdir $remote_dir"
    run_cmd="$env_prefix '$REMOTE_BIN' --threads '$threads' --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile '$actual_profile' $extra_args --outdir '$q_remote' > '$q_remote/result.json' 2> '$q_remote/stderr.txt'"
  else
    env_prefix="env GLIBC_TUNABLES=$tunable"
    cmdline="$env_prefix $REMOTE_BIN --threads $threads --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile $actual_profile $extra_args --outdir $remote_dir"
    run_cmd="env GLIBC_TUNABLES='$q_tunable' '$REMOTE_BIN' --threads '$threads' --seed 20260708 --warmup 5 --duration 30 --idle 10 --profile '$actual_profile' $extra_args --outdir '$q_remote' > '$q_remote/result.json' 2> '$q_remote/stderr.txt'"
  fi
  if [ "$part" = "D" ]; then
    cmdline=${cmdline/--idle 10/--idle 20}
    run_cmd=${run_cmd/--idle 10/--idle 20}
  fi

  "$SDB" shell "{
    echo DATE=\$(date);
    echo PART='$part';
    echo PROFILE='$profile';
    echo ACTUAL_PROFILE='$actual_profile';
    echo GRID='$grid';
    echo REP='$rep';
    echo ATTEMPT='$attempt';
    echo THREADS='$threads';
    echo EXTRA_ARGS='$extra_args';
    echo GLIBC_TUNABLES='${q_tunable:-<unset>}';
    echo COMMAND='$cmdline';
  } > '$q_remote/cmd.txt'" >/dev/null 2>&1 || true

  log "RUN part=$part profile=$profile grid=$grid rep=$rep attempt=$attempt threads=$threads"
  "$SDB" shell "$run_cmd; rc=\$?; echo \$rc > '$q_remote/exit_code.txt'; exit \$rc" > "$local_dir/sdb_run_stdout.txt" 2> "$local_dir/sdb_run_stderr.txt"
  local rc=$?
  record_temps_remote "$remote_dir" "AFTER"
  pull_remote_dir "$remote_dir" "$local_dir"
  append_summary "$part" "$profile" "$actual_profile" "$grid" "$rep" "$attempt" "$threads" "$extra_args" "$rc" "$local_dir"
  return "$rc"
}

run_with_retry() {
  local part=$1 profile=$2 actual_profile=$3 grid=$4 rep=$5 tunable=$6 threads=$7 extra_args=$8
  local safe_profile=${profile// /_}
  safe_profile=${safe_profile//\//_}
  local safe_grid=${grid// /_}
  safe_grid=${safe_grid//\//_}
  local local_dir="$OUT/$safe_profile/$safe_grid/rep$rep"
  local remote_dir="$REMOTE_ROOT/$safe_profile/$safe_grid/rep$rep"
  mkdir -p "$local_dir"
  run_one_attempt "$part" "$profile" "$actual_profile" "$grid" "$rep" 1 "$tunable" "$threads" "$extra_args" "$local_dir" "$remote_dir"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    exception "run failed: part=$part profile=$profile grid=$grid rep=$rep attempt1 rc=$rc; retrying once"
    local fail_dir="$OUT/$safe_profile/$safe_grid/rep${rep}_failed_attempt1"
    rm -rf "$fail_dir"
    mv "$local_dir" "$fail_dir"
    mkdir -p "$local_dir"
    run_one_attempt "$part" "$profile" "$actual_profile" "$grid" "$rep" 2 "$tunable" "$threads" "$extra_args" "$local_dir" "$REMOTE_ROOT/$safe_profile/$safe_grid/rep${rep}_retry1"
    rc=$?
    if [ "$rc" -ne 0 ]; then
      exception "run failed: part=$part profile=$profile grid=$grid rep=$rep attempt2 rc=$rc; continuing"
    fi
  fi
  sleep 5
}

pre_inventory() {
  mkdir -p "$OUT/precheck"
  sdb_capture "$OUT/precheck/push_inventory.log" push "$INV" "$REMOTE_INV"
  sdb_shell_capture "$OUT/precheck/inventory_run.log" "chmod +x '$REMOTE_INV'; sh '$REMOTE_INV' > /root/batch25_pre_inventory.tsv 2> /root/batch25_pre_inventory_summary.txt; echo EXIT=\$?"
  sdb_capture "$OUT/precheck/pull_inventory_tsv.log" pull /root/batch25_pre_inventory.tsv "$OUT/precheck/"
  sdb_capture "$OUT/precheck/pull_inventory_summary.log" pull /root/batch25_pre_inventory_summary.txt "$OUT/precheck/"
  if grep -q 'processes with LIVE env blacklist hits: 0' "$OUT/precheck/batch25_pre_inventory_summary.txt"; then
    log "pre-inventory LIVE hits 0"
  else
    exception "pre-inventory did not report LIVE hits 0; see $OUT/precheck/batch25_pre_inventory_summary.txt"
  fi
}

post_inventory() {
  mkdir -p "$OUT/restore"
  sdb_capture "$OUT/restore/push_inventory.log" push "$INV" "$REMOTE_INV"
  sdb_shell_capture "$OUT/restore/inventory_run.log" "chmod +x '$REMOTE_INV'; sh '$REMOTE_INV' > /root/batch25_post_inventory.tsv 2> /root/batch25_post_inventory_summary.txt; echo EXIT=\$?"
  sdb_capture "$OUT/restore/pull_inventory_tsv.log" pull /root/batch25_post_inventory.tsv "$OUT/restore/"
  sdb_capture "$OUT/restore/pull_inventory_summary.log" pull /root/batch25_post_inventory_summary.txt "$OUT/restore/"
  if grep -q 'processes with LIVE env blacklist hits: 0' "$OUT/restore/batch25_post_inventory_summary.txt"; then
    log "post-inventory LIVE hits 0"
  else
    exception "post-inventory did not report LIVE hits 0; see $OUT/restore/batch25_post_inventory_summary.txt"
  fi
}

setup_board() {
  SETUP_STARTED=1
  sdb_capture "$OUT/sdb_version.txt" version
  sdb_capture "$OUT/sdb_connect.txt" connect "$BOARD_IP"
  sdb_capture "$OUT/sdb_devices.txt" devices
  if ! grep -Eq '[[:space:]]device([[:space:]]|$)' "$OUT/sdb_devices.txt"; then
    exception "sdb devices did not show a usable device; stopping"
    return 1
  fi
  sdb_capture "$OUT/sdb_root_on.txt" root on
  sdb_shell_capture "$OUT/root_id.txt" "id"
  if ! grep -q 'uid=0(root)' "$OUT/root_id.txt"; then
    exception "root unavailable; stopping"
    return 1
  fi
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

smoke_one() {
  local profile=$1
  local remote_dir="$REMOTE_SMOKE/$profile"
  local local_dir="$OUT/smoke/$profile"
  mkdir -p "$local_dir"
  sdb_shell_capture "$local_dir/run.log" "rm -rf '$remote_dir'; mkdir -p '$remote_dir'; env -u GLIBC_TUNABLES '$REMOTE_BIN' --profile '$profile' --threads 2 --seed 1 --warmup 0 --ops-per-thread 1000 --idle 0 --outdir '$remote_dir' > '$remote_dir/result.json' 2> '$remote_dir/stderr.txt'; rc=\$?; echo \$rc > '$remote_dir/exit_code.txt'; echo EXIT=\$rc"
  sdb_capture "$local_dir/pull.log" pull "$remote_dir" "$local_dir/"
  if [ ! -f "$local_dir/result.json" ]; then
    exception "smoke failed for $profile: result.json missing"
    return 1
  fi
  if ! python3 -m json.tool "$local_dir/result.json" > "$local_dir/result.pretty.json" 2> "$local_dir/json_tool.err"; then
    exception "smoke failed for $profile: JSON parse failed"
    return 1
  fi
  if [ -s "$local_dir/stderr.txt" ]; then
    exception "smoke stderr non-empty for $profile; see $local_dir/stderr.txt"
  fi
  if ! grep -q '^0$' "$local_dir/exit_code.txt"; then
    exception "smoke failed for $profile: exit code $(cat "$local_dir/exit_code.txt")"
    return 1
  fi
  log "smoke ok for $profile"
}

smoke_tests() {
  smoke_one burst-free-small || return 1
  smoke_one unsorted-drain || return 1
}

run_matrix() {
  local arena_grids=(C0 arena2 arena3 arena4)
  local arena_vals=(
    ""
    "glibc.malloc.arena_max=2"
    "glibc.malloc.arena_max=3"
    "glibc.malloc.arena_max=4"
  )

  log "Matrix note: prompt approximate total says 89; table expansion executed here is 80 formal runs."
  exception "matrix count note: prompt says approximately 89, table expansion is 80; executing table rows only"

  # Part A n>=5 thread-churn runs first while the board is coolest.
  for idx in "${!arena_grids[@]}"; do
    for rep in 1 2 3 4 5; do
      run_with_retry A thread-churn thread-churn "${arena_grids[$idx]}" "$rep" "${arena_vals[$idx]}" 4 ""
    done
    sleep 10
  done

  for profile in mixed large-transient; do
    for idx in "${!arena_grids[@]}"; do
      for rep in 1 2 3; do
        run_with_retry A "$profile" "$profile" "${arena_grids[$idx]}" "$rep" "${arena_vals[$idx]}" 4 ""
      done
    done
  done

  for idx in 0 1; do
    for rep in 1 2 3; do
      run_with_retry A mixed-t2 mixed "${arena_grids[$idx]}" "$rep" "${arena_vals[$idx]}" 2 ""
    done
  done

  local burst_grids=(C0 mxfast0 tcache_unsorted3)
  local burst_vals=(
    ""
    "glibc.malloc.mxfast=0"
    "glibc.malloc.tcache_unsorted_limit=3"
  )
  for profile in burst-free-small unsorted-drain; do
    for idx in "${!burst_grids[@]}"; do
      for rep in 1 2 3; do
        run_with_retry B "$profile" "$profile" "${burst_grids[$idx]}" "$rep" "${burst_vals[$idx]}" 4 ""
      done
    done
  done

  for rep in 1 2 3; do
    run_with_retry C thread-churn thread-churn L1_L3 "$rep" "glibc.pthread.stack_cache_size=1048576:glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072" 4 ""
  done

  for rep in 1 2 3; do
    run_with_retry D mixed mixed D-C0 "$rep" "" 4 "--idle-release 50"
  done
  for rep in 1 2 3; do
    run_with_retry D mixed mixed D-C0-idle-trim "$rep" "" 4 "--idle-release 50 --idle-trim"
  done
  for rep in 1 2 3; do
    run_with_retry D mixed mixed D-T-L3 "$rep" "glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072" 4 "--idle-release 50"
  done
}

main() {
  log "Batch2.5 alloc_bench start"
  setup_board || {
    exception "setup failed; stopping before smoke"
    return 1
  }
  if ! smoke_tests; then
    exception "smoke failed; stopping before matrix"
    restore_governor
    post_inventory
    cleanup_board
    log "Batch2.5 alloc_bench stopped after smoke failure"
    return 1
  fi
  run_matrix
  restore_governor
  post_inventory
  cleanup_board
  log "Batch2.5 alloc_bench complete"
}

main "$@"
