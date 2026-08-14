#!/usr/bin/env bash
set -u

SDB=${SDB:-<USER_HOME>/tizen-studio/tools/sdb}
BOARD_IP=${BOARD_IP:-<TEST_BOARD_IP>}
OUT=${OUT:-board_results/batch1}
INV_SCRIPT=${INV_SCRIPT:-docs/tizen_memopt_inventory.sh}

RUNLOG="$OUT/host_run.log"
MEASURE_TSV="$OUT/measurements.tsv"
NOISE_TSV="$OUT/noise.tsv"
EXCEPTIONS="$OUT/exceptions.log"
RESTORE_LOG="$OUT/restore.log"
MAPPING_LOG="$OUT/unit_mapping.log"

mkdir -p "$OUT"
: > "$RUNLOG"
: > "$MEASURE_TSV"
: > "$NOISE_TSV"
: > "$EXCEPTIONS"
: > "$RESTORE_LOG"
: > "$MAPPING_LOG"

printf 'service\tgrid\tunit\tpid\te1\trss_median_kb\tpss_median_kb\tarena_count\tnote\tdir\n' > "$MEASURE_TSV"
printf 'service\tunit\trestart_round\tsample\tpid\trss_kb\tpss_kb\tfile\n' > "$NOISE_TSV"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$RUNLOG"
}

record_exception() {
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

sdb_shell_text() {
  local cmd=$1
  log "CMD: $SDB shell $cmd"
  "$SDB" shell "$cmd" 2>&1 | tee -a "$RUNLOG"
  return "${PIPESTATUS[0]}"
}

get_pid() {
  local unit=$1
  "$SDB" shell "systemctl show -p MainPID --value $unit 2>/dev/null" | tr -d '\r' | awk 'NR==1 {print $1}'
}

apply_grid() {
  local unit=$1
  local grid=$2
  local tunables=$3
  local q_tunables
  q_tunables=$(printf "%s" "$tunables" | sed "s/'/'\\\\''/g")
  if [ "$grid" = "C0" ]; then
    sdb_shell_text "rm -f /etc/systemd/system/$unit.d/memopt.conf; rmdir /etc/systemd/system/$unit.d 2>/dev/null || true; systemctl daemon-reload; systemctl restart $unit; echo RESTART_RC=\$?"
  else
    sdb_shell_text "mkdir -p /etc/systemd/system/$unit.d; printf '%s\n' '[Service]' 'Environment=GLIBC_TUNABLES=$q_tunables' > /etc/systemd/system/$unit.d/memopt.conf; systemctl daemon-reload; systemctl restart $unit; echo RESTART_RC=\$?"
  fi
}

extract_rollup_value() {
  local file=$1
  local key=$2
  awk -v k="$key:" '$1 == k {print $2; exit}' "$file" | tr -d '\r'
}

median3() {
  printf '%s\n%s\n%s\n' "$1" "$2" "$3" | sort -n | sed -n '2p'
}

arena_count_from_maps() {
  local file=$1
  perl -ne '
    next unless /^([0-9a-f]+)-([0-9a-f]+)\s+rw.p\s+/;
    my @f = split;
    next if @f >= 6;
    my $start = hex($1);
    my $end = hex($2);
    my $size = $end - $start;
    $c++ if $size > 0 && $size <= 0x100000 && ($start % 0x100000) == 0;
    END { print (($c || 0) . "\n"); }
  ' "$file"
}

capture_rollup_sample() {
  local outfile=$1
  local svc=$2
  local unit=$3
  local grid=$4
  local pid=$5
  local sample=$6
  sdb_shell_capture "$outfile" "echo SERVICE=$svc; echo UNIT=$unit; echo GRID=$grid; echo PID=$pid; echo SAMPLE=$sample; date; uptime; free; echo ---SMAPS_ROLLUP---; cat /proc/$pid/smaps_rollup"
}

noise_for_service() {
  local svc=$1
  local unit=$2
  local dir="$OUT/$svc/C0_noise"
  mkdir -p "$dir"
  log "Noise calibration start: $svc ($unit)"
  local round sample idx pid file rss pss
  for round in 1 2 3; do
    sdb_shell_capture "$dir/restart_round${round}.txt" "rm -f /etc/systemd/system/$unit.d/memopt.conf; rmdir /etc/systemd/system/$unit.d 2>/dev/null || true; systemctl daemon-reload; systemctl restart $unit; echo RESTART_RC=\$?; sleep 3; systemctl is-active $unit; systemctl show -p MainPID --value $unit; systemctl status $unit --no-pager | sed -n '1,18p'"
    pid=$(get_pid "$unit")
    if ! printf '%s' "$pid" | grep -Eq '^[1-9][0-9]*$'; then
      record_exception "noise skip for $svc/$unit round $round: invalid pid '$pid'"
      continue
    fi
    log "Noise wait 60s: $svc round $round pid $pid"
    sleep 60
    for sample in 1 2 3; do
      idx=$(( (round - 1) * 3 + sample ))
      file="$dir/run${idx}.txt"
      capture_rollup_sample "$file" "$svc" "$unit" "C0_noise" "$pid" "$idx"
      rss=$(extract_rollup_value "$file" "Rss")
      pss=$(extract_rollup_value "$file" "Pss")
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$svc" "$unit" "$round" "$sample" "$pid" "${rss:-NA}" "${pss:-NA}" "$file" >> "$NOISE_TSV"
      if [ "$sample" -lt 3 ]; then
        sleep 15
      fi
    done
  done
}

run_grid_for_service() {
  local svc=$1
  local unit=$2
  local grid=$3
  local tunables=$4
  local dir="$OUT/$svc/$grid"
  mkdir -p "$dir"
  log "Grid start: $svc $grid ($unit)"

  apply_grid "$unit" "$grid" "$tunables" | tee "$dir/apply.txt"
  local pid
  pid=$(get_pid "$unit")
  if ! printf '%s' "$pid" | grep -Eq '^[1-9][0-9]*$'; then
    record_exception "grid skip after restart for $svc/$grid/$unit: invalid pid '$pid'"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$svc" "$grid" "$unit" "NA" "FAIL" "NA" "NA" "NA" "invalid-pid" "$dir" >> "$MEASURE_TSV"
    return 0
  fi

  sdb_shell_capture "$dir/e1_environ.raw" "cat /proc/$pid/environ"
  tr '\000' '\n' < "$dir/e1_environ.raw" | tr -d '\r' > "$dir/e1_environ.txt"
  local e1="FAIL"
  if [ "$grid" = "C0" ]; then
    if grep -q '^GLIBC_TUNABLES=' "$dir/e1_environ.txt"; then
      e1="PRESENT_UNEXPECTED"
    else
      e1="ABSENT"
    fi
  else
    if grep -Fxq "GLIBC_TUNABLES=$tunables" "$dir/e1_environ.txt"; then
      e1="PASS"
    fi
  fi

  log "Steady-state wait 60s: $svc $grid pid $pid"
  sleep 60

  local rss1 rss2 rss3 pss1 pss2 pss3 rssm pssm n file
  for n in 1 2 3; do
    file="$dir/run${n}.txt"
    capture_rollup_sample "$file" "$svc" "$unit" "$grid" "$pid" "$n"
    if [ "$n" -lt 3 ]; then
      sleep 15
    fi
  done
  rss1=$(extract_rollup_value "$dir/run1.txt" "Rss")
  rss2=$(extract_rollup_value "$dir/run2.txt" "Rss")
  rss3=$(extract_rollup_value "$dir/run3.txt" "Rss")
  pss1=$(extract_rollup_value "$dir/run1.txt" "Pss")
  pss2=$(extract_rollup_value "$dir/run2.txt" "Pss")
  pss3=$(extract_rollup_value "$dir/run3.txt" "Pss")
  rssm=$(median3 "${rss1:-0}" "${rss2:-0}" "${rss3:-0}")
  pssm=$(median3 "${pss1:-0}" "${pss2:-0}" "${pss3:-0}")

  sdb_shell_capture "$dir/maps.txt" "cat /proc/$pid/maps"
  local arenas
  arenas=$(arena_count_from_maps "$dir/maps.txt")

  local note="ok"
  if [ "$svc" = "pulseaudio" ]; then
    sdb_shell_capture "$dir/perf_sentinel.txt" "echo ---pactl---; t0=\$(date +%s); pactl list sinks short; rc=\$?; t1=\$(date +%s); echo PACTL_RC=\$rc; echo PACTL_ELAPSED_S=\$((t1-t0)); echo ---XRUN_JOURNAL---; journalctl -u pulseaudio.service --since '-3 min' --no-pager 2>&1 | grep -i xrun || true"
    note="perf_sentinel=$(basename "$dir/perf_sentinel.txt")"
  fi
  if [ "$e1" = "FAIL" ] || [ "$e1" = "PRESENT_UNEXPECTED" ]; then
    note="$note;e1=$e1"
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$svc" "$grid" "$unit" "$pid" "$e1" "$rssm" "$pssm" "$arenas" "$note" "$dir" >> "$MEASURE_TSV"
}

restore_board() {
  log "Restore start"
  {
    echo "RESTORE_DATE=$(date -Iseconds)"
    for unit in ServiceR.service central-ServiceS.service pass.service pulseaudio.service ac.service; do
      echo "--- cleanup $unit ---"
      "$SDB" shell "rm -f /etc/systemd/system/$unit.d/memopt.conf; rmdir /etc/systemd/system/$unit.d 2>/dev/null || true"
    done
    "$SDB" shell "systemctl daemon-reload"
    for unit in ServiceR.service central-ServiceS.service pass.service pulseaudio.service ac.service; do
      echo "--- restart $unit ---"
      "$SDB" shell "systemctl restart $unit; echo RESTART_RC=\$?; sleep 2; systemctl is-active $unit; systemctl show -p MainPID --value $unit"
    done
    echo "--- dropin check ---"
    "$SDB" shell "for unit in ServiceR.service central-ServiceS.service pass.service pulseaudio.service ac.service; do f=/etc/systemd/system/\$unit.d/memopt.conf; if [ -e \$f ]; then echo PRESENT:\$f; else echo ABSENT:\$f; fi; done"
    echo "--- active check ---"
    "$SDB" shell "for unit in ServiceR.service central-ServiceS.service pass.service pulseaudio.service ac.service; do printf '%s ' \$unit; systemctl is-active \$unit; done"
  } > "$RESTORE_LOG" 2>&1

  log "Restore inventory rescan start"
  sdb_capture "$OUT/push_inventory.log" push "$INV_SCRIPT" /tmp/tizen_memopt_inventory.sh
  sdb_shell_capture "$OUT/restore_inventory_run.log" "chmod +x /tmp/tizen_memopt_inventory.sh; sh /tmp/tizen_memopt_inventory.sh > /tmp/batch1_inventory.tsv 2> /tmp/batch1_inventory_summary.txt; echo EXIT=\$?"
  sdb_capture "$OUT/pull_restore_inventory_tsv.log" pull /tmp/batch1_inventory.tsv "$OUT/"
  [ -f "$OUT/batch1_inventory.tsv" ] && mv "$OUT/batch1_inventory.tsv" "$OUT/restore_inventory.tsv"
  sdb_capture "$OUT/pull_restore_inventory_summary.log" pull /tmp/batch1_inventory_summary.txt "$OUT/"
  [ -f "$OUT/batch1_inventory_summary.txt" ] && mv "$OUT/batch1_inventory_summary.txt" "$OUT/restore_inventory_summary.txt"
  sdb_shell_capture "$OUT/tmp_cleanup.log" "rm -f /tmp/tizen_memopt_inventory.sh /tmp/batch1_inventory.tsv /tmp/batch1_inventory_summary.txt /tmp/inventory.tsv /tmp/inventory_summary.txt; ls -l /tmp | sed -n '1,80p'"
}

log "Batch1 AB start"
sdb_capture "$OUT/sdb_version.txt" version
sdb_capture "$OUT/sdb_connect.txt" connect "$BOARD_IP"
sdb_capture "$OUT/sdb_devices.txt" devices
sdb_capture "$OUT/sdb_root_on.txt" root on
sdb_shell_capture "$OUT/root_id.txt" "id"
sdb_shell_capture "$OUT/os_release.txt" "cat /etc/os-release"
sdb_shell_capture "$OUT/uname.txt" "uname -a"

{
  echo "--- grep unit evidence ---"
  "$SDB" shell "systemctl list-units --type=service --all --no-pager | grep -E 'ServiceR|multi|ServiceS|pass|pulseaudio|ServiceV' || true"
  echo "--- ServiceV exact unit evidence ---"
  "$SDB" shell "systemctl show -p Id,MainPID,ExecStart,Description ac.service; echo ---; cat /proc/439/cgroup; echo ---; systemctl status 439 --no-pager || true"
  echo "--- multi-assistant evidence ---"
  "$SDB" shell "cat /proc/751/cgroup 2>&1; echo ---; systemctl status 751 --no-pager 2>&1 || true; echo ---; systemctl list-units --type=service --all --no-pager | grep -i -E 'multi|assistant|org.tizen' || true"
} > "$MAPPING_LOG" 2>&1

SERVICES=(
  "ServiceR|ServiceR.service|ServiceR"
  "ServiceS|central-ServiceS.service|ServiceS"
  "pass|pass.service|pass"
  "pulseaudio|pulseaudio.service|pulseaudio"
  "ServiceV|ac.service|ServiceV"
)

record_exception "skip AppV: no dedicated service from list-units grep; /proc/751/cgroup shows ServiceJ/user@5001, not a targetable per-app unit"

ACTIVE_SERVICES=()
for entry in "${SERVICES[@]}"; do
  IFS='|' read -r svc unit comm <<< "$entry"
  mkdir -p "$OUT/$svc"
  sdb_shell_capture "$OUT/$svc/rehearsal.txt" "systemctl restart $unit; echo RESTART_RC=\$?; sleep 3; systemctl is-active $unit; systemctl show -p MainPID --value $unit; systemctl status $unit --no-pager | sed -n '1,20p'"
  if grep -q '^RESTART_RC=0' "$OUT/$svc/rehearsal.txt" && grep -q '^active' "$OUT/$svc/rehearsal.txt"; then
    pid=$(get_pid "$unit")
    if printf '%s' "$pid" | grep -Eq '^[1-9][0-9]*$'; then
      ACTIVE_SERVICES+=("$entry")
      log "Rehearsal ok: $svc $unit pid $pid"
    else
      record_exception "rehearsal failed for $svc/$unit: invalid pid '$pid'"
    fi
  else
    record_exception "rehearsal failed for $svc/$unit; see $OUT/$svc/rehearsal.txt"
  fi
done

for entry in "${ACTIVE_SERVICES[@]}"; do
  IFS='|' read -r svc unit comm <<< "$entry"
  noise_for_service "$svc" "$unit"
done

for entry in "${ACTIVE_SERVICES[@]}"; do
  IFS='|' read -r svc unit comm <<< "$entry"
  run_grid_for_service "$svc" "$unit" "C0" ""
  if [ "$svc" = "ServiceV" ]; then
    run_grid_for_service "$svc" "$unit" "C3" "glibc.pthread.stack_cache_size=1048576:glibc.malloc.arena_max=2"
  else
    run_grid_for_service "$svc" "$unit" "C1" "glibc.pthread.stack_cache_size=1048576"
    run_grid_for_service "$svc" "$unit" "C2" "glibc.malloc.arena_max=2"
    run_grid_for_service "$svc" "$unit" "C3" "glibc.pthread.stack_cache_size=1048576:glibc.malloc.arena_max=2"
  fi
done

restore_board
log "Batch1 AB complete"
