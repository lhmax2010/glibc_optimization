#!/bin/sh
set +e
OUT=/tmp/tv_recon2
rm -rf "$OUT"
mkdir -p "$OUT" "$OUT/A" "$OUT/B" "$OUT/C" "$OUT/D" "$OUT/smaps"

write_cmd() { f="$1"; shift; printf '%s\n' "$*" > "$f.cmd"; }
run_cmd() {
  f="$1"; shift
  write_cmd "$f" "$*"
  sh -c "$*" > "$f.out" 2> "$f.err"
  echo $? > "$f.rc"
}

# Group A
write_cmd "$OUT/A/a2_proc_walk" 'for p in /proc/[0-9]*; do echo "$p $(cat $p/comm 2>/dev/null)"; done'
{
  for p in /proc/[0-9]*; do
    printf '%s ' "$p"
    cat "$p/comm" 2>/dev/null || echo
  done
} > "$OUT/A/a2_proc_walk.out" 2> "$OUT/A/a2_proc_walk.err"
echo $? > "$OUT/A/a2_proc_walk.rc"

write_cmd "$OUT/A/a3_uep_path" 'cp -a /bin/true to /tmp, /root, /opt/usr/home if present; execute copied and renamed copies; remove copies'
{
  echo SOURCE=/bin/true
  ls -l /bin/true 2>&1
  for d in /tmp /root /opt/usr/home; do
    echo "--- DIR $d ---"
    if [ ! -d "$d" ]; then echo "MISSING_DIR $d"; continue; fi
    for n in tv_recon2_true_copy tv_recon2_true_renamed; do
      dst="$d/$n"
      rm -f "$dst"
      cp -a /bin/true "$dst" 2>&1
      cp_rc=$?
      chmod 755 "$dst" 2>&1
      chmod_rc=$?
      ls -l "$dst" 2>&1
      "$dst" >/dev/null 2>"$OUT/A/a3_${n}_stderr.tmp"
      exec_rc=$?
      stderr=$(cat "$OUT/A/a3_${n}_stderr.tmp" 2>/dev/null)
      rm -f "$OUT/A/a3_${n}_stderr.tmp"
      echo "RESULT dir=$d name=$n cp_rc=$cp_rc chmod_rc=$chmod_rc exec_rc=$exec_rc stderr=$stderr"
      rm -f "$dst"
      echo "CLEANUP dir=$d name=$n left=$(ls "$dst" 2>&1)"
    done
  done
} > "$OUT/A/a3_uep_path.out" 2> "$OUT/A/a3_uep_path.err"
echo $? > "$OUT/A/a3_uep_path.rc"

run_cmd "$OUT/A/a4_bg_tools" 'for x in systemd-run setsid nohup; do command -v "$x" || echo MISSING:"$x"; done'

# Group B
run_cmd "$OUT/B/b1_swap" 'cat /proc/swaps; echo ---free---; free; echo ---swappiness---; cat /proc/sys/vm/swappiness'
run_cmd "$OUT/B/b2_smaps_rollup_proc1" 'cat /proc/1/smaps_rollup'
run_cmd "$OUT/B/b3_dev_shm" 'df /dev/shm 2>&1; echo ---ls---; ls -la /dev/shm 2>&1; echo ---du---; du -sk /dev/shm 2>&1'
write_cmd "$OUT/B/b4_ServiceR_lmk" 'ls /etc/ServiceR; find /etc -name *.conf | grep memory/lmk/oom; grep excerpts from ServiceR configs'
{
  echo ---command-v---
  command -v find 2>&1 || true
  command -v dmesg 2>&1 || true
  echo ---ls-etc-ServiceR---
  ls -la /etc/ServiceR 2>&1
  echo ---ls-usr-etc-ServiceR---
  ls -la /usr/etc/ServiceR 2>&1
  echo ---candidate-conf-files---
  if command -v find >/dev/null 2>&1; then
    find /etc /usr/etc -name '*.conf' 2>/dev/null | while read f; do
      grep -l -i 'memory\|lmk\|oom' "$f" 2>/dev/null
    done | head -80
  else
    echo FIND_MISSING
  fi
  echo ---ServiceR-grep---
  grep -R -n -i 'memory\|lmk\|oom\|threshold\|available\|critical\|swap' /etc/ServiceR /usr/etc/ServiceR 2>/dev/null | head -240
  echo ---etc-conf-excerpts---
  if command -v find >/dev/null 2>&1; then
    find /etc /usr/etc -name '*.conf' 2>/dev/null | while read f; do
      grep -n -i 'memory\|lmk\|oom' "$f" 2>/dev/null | sed "s#^#$f:#"
    done | head -240
  fi
} > "$OUT/B/b4_ServiceR_lmk.out" 2> "$OUT/B/b4_ServiceR_lmk.err"
echo $? > "$OUT/B/b4_ServiceR_lmk.rc"

write_cmd "$OUT/B/b5_psi_balloon" 'controlled /dev/shm balloon 64/128/192/256 MiB, record MemAvailable, PSI, LMK/OOM log count, cleanup'
{
  BALL=/dev/shm/tv_recon2_balloon
  rm -f "$BALL"
  base_avail=$(awk '/MemAvailable:/ {print $2; exit}' /proc/meminfo)
  limit_mb=$((base_avail * 60 / 100 / 1024))
  echo "BASE_MemAvailable_kB=$base_avail"
  echo "LIMIT_60pct_MB=$limit_mb"
  echo "Dmesg_command=$(command -v dmesg 2>/dev/null)"
  lmk_count() { dmesg 2>/dev/null | grep -Ei 'lowmemory|lmk|oom|out of memory|Killed process|kill process|ServiceR' | wc -l; }
  base_lmk=$(lmk_count)
  echo "BASE_LMK_RELEVANT_COUNT=$base_lmk"
  for m in 64 128 192 256; do
    if [ "$m" -gt "$limit_mb" ]; then echo "SKIP_LEVEL_MB=$m reason=over_60pct_limit"; break; fi
    seek=$((m - 64))
    echo "=== LEVEL_MB=$m ==="
    dd if=/dev/zero of="$BALL" bs=1M count=64 seek="$seek" conv=notrunc 2>&1
    dd_rc=$?
    echo "DD_RC=$dd_rc"
    sleep 1
    echo ---meminfo---
    grep -E 'MemAvailable|MemFree|Cached|SwapTotal|SwapFree' /proc/meminfo
    echo ---free---
    free
    echo ---psi---
    cat /proc/pressure/memory 2>&1
    cur_lmk=$(lmk_count)
    echo "LMK_RELEVANT_COUNT=$cur_lmk"
    echo ---lmk-tail---
    dmesg 2>/dev/null | grep -Ei 'lowmemory|lmk|oom|out of memory|Killed process|kill process|ServiceR' | tail -20
    if [ "$cur_lmk" -gt "$base_lmk" ]; then
      echo "LMK_NEW=1 stopping_after_level=$m"
      rm -f "$BALL"
      break
    else
      echo "LMK_NEW=0"
    fi
  done
  echo === CLEANUP ===
  rm -f "$BALL"
  echo "RM_RC=$?"
  ls -l "$BALL" 2>&1 || true
  echo ---final-meminfo---
  grep -E 'MemAvailable|MemFree|Cached|SwapTotal|SwapFree' /proc/meminfo
  echo ---final-psi---
  cat /proc/pressure/memory 2>&1
} > "$OUT/B/b5_psi_balloon.out" 2> "$OUT/B/b5_psi_balloon.err"
echo $? > "$OUT/B/b5_psi_balloon.rc"

# Group C process inventory
write_cmd "$OUT/C/c0_process_table" 'iterate /proc, collect pid/comm/rss/pss/private_dirty/threads/cmdline/exe; sort by rss desc'
{
  echo 'pid	comm	rss_kb	pss_kb	private_dirty_kb	threads	cmdline	exe'
  for p in /proc/[0-9]*; do
    pid=${p#/proc/}
    [ -r "$p/smaps_rollup" ] || continue
    comm=$(cat "$p/comm" 2>/dev/null)
    rss=$(awk '/^Rss:/ {print $2; exit}' "$p/smaps_rollup" 2>/dev/null)
    pss=$(awk '/^Pss:/ {print $2; exit}' "$p/smaps_rollup" 2>/dev/null)
    pd=$(awk '/^Private_Dirty:/ {print $2; exit}' "$p/smaps_rollup" 2>/dev/null)
    th=$(ls "$p/task" 2>/dev/null | wc -l)
    cmd=$(tr '\000' ' ' < "$p/cmdline" 2>/dev/null)
    exe=$(readlink "$p/exe" 2>/dev/null)
    [ -n "$rss" ] || rss=0
    [ -n "$pss" ] || pss=0
    [ -n "$pd" ] || pd=0
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$pid" "$comm" "$rss" "$pss" "$pd" "$th" "$cmd" "$exe"
  done
} > "$OUT/C/c0_process_table.unsorted" 2> "$OUT/C/c0_process_table.err"
{ head -1 "$OUT/C/c0_process_table.unsorted"; tail -n +2 "$OUT/C/c0_process_table.unsorted" | sort -t '        ' -k3,3nr 2>/dev/null || tail -n +2 "$OUT/C/c0_process_table.unsorted" | sort -k3,3nr; } > "$OUT/C/c0_process_table.out"
echo $? > "$OUT/C/c0_process_table.rc"

# Build target pid list: top 10 plus named native services if present.
tail -n +2 "$OUT/C/c0_process_table.out" | head -10 | awk '{print $1}' > "$OUT/C/target_pids.tmp"
for name in ServiceR pulseaudio ServiceV ServiceC enlightenment ServiceE ServiceH; do
  pgrep -x "$name" 2>/dev/null >> "$OUT/C/target_pids.tmp"
done
sort -n "$OUT/C/target_pids.tmp" | awk 'NF && !seen[$1]++ {print $1}' > "$OUT/C/target_pids.txt"
rm -f "$OUT/C/target_pids.tmp"

write_cmd "$OUT/C/c1_targets" 'for target pids: readlink exe, cmdline, cgroup, rw-p maps count'
{
  while read pid; do
    [ -n "$pid" ] || continue
    echo "### PID $pid"
    echo "comm=$(cat /proc/$pid/comm 2>/dev/null)"
    echo "cmdline=$(tr '\000' ' ' < /proc/$pid/cmdline 2>/dev/null)"
    echo "exe=$(readlink /proc/$pid/exe 2>/dev/null)"
    echo "rw_p_count=$(grep -c 'rw-p' /proc/$pid/maps 2>/dev/null)"
    echo "---cgroup---"
    cat /proc/$pid/cgroup 2>/dev/null
    echo "---systemctl-status-pid-head---"
    systemctl status "$pid" 2>&1 | head -3
  done < "$OUT/C/target_pids.txt"
} > "$OUT/C/c1_targets.out" 2> "$OUT/C/c1_targets.err"
echo $? > "$OUT/C/c1_targets.rc"

write_cmd "$OUT/C/c4_pid_unit_mapping" 'map top target pids to service units via cgroup and systemctl status; list matching services'
{
  echo ---service-units-all---
  systemctl list-units --type=service --all --no-legend --no-pager 2>&1
  echo ---pid-mapping---
  while read pid; do
    [ -n "$pid" ] || continue
    comm=$(cat /proc/$pid/comm 2>/dev/null)
    cg=$(cat /proc/$pid/cgroup 2>/dev/null)
    unit=$(echo "$cg" | sed -n 's#.*\/\([^/]*\.service\).*#\1#p' | head -1)
    [ -n "$unit" ] || unit=NONE
    printf 'PID=%s COMM=%s UNIT_FROM_CGROUP=%s\n' "$pid" "$comm" "$unit"
  done < "$OUT/C/target_pids.txt"
  echo ---candidate-service-grep---
  systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | grep -Ei 'ServiceR|pulse|ServiceV|tvs|enlightenment|wrt|dotnet|menu|ServiceT|search|home|viewer|issue|multi' || true
} > "$OUT/C/c4_pid_unit_mapping.out" 2> "$OUT/C/c4_pid_unit_mapping.err"
echo $? > "$OUT/C/c4_pid_unit_mapping.rc"

# Copy smaps/maps for C2/C3 target pids.
while read pid; do
  [ -n "$pid" ] || continue
  comm=$(cat /proc/$pid/comm 2>/dev/null | tr -c 'A-Za-z0-9_.-' '_')
  [ -n "$comm" ] || comm=unknown
  cat "/proc/$pid/smaps" > "$OUT/smaps/${pid}_${comm}.smaps" 2> "$OUT/smaps/${pid}_${comm}.smaps.err"
  cat "/proc/$pid/maps" > "$OUT/smaps/${pid}_${comm}.maps" 2> "$OUT/smaps/${pid}_${comm}.maps.err"
done < "$OUT/C/target_pids.txt"

# Group D
run_cmd "$OUT/D/d1_cpu_governor" 'echo ---nproc---; nproc 2>&1 || grep -c ^processor /proc/cpuinfo; echo ---online---; cat /sys/devices/system/cpu/online 2>&1; echo ---governors---; for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$f=$(cat $f 2>&1)"; done'
run_cmd "$OUT/D/d2_thermal" 'ls -la /sys/class/thermal 2>&1; echo ---zones---; for z in /sys/class/thermal/thermal_zone*; do [ -e "$z" ] || continue; echo "### $z"; cat "$z/type" 2>&1; cat "$z/temp" 2>&1; done'
run_cmd "$OUT/D/d3_vm_mem" 'echo ---overcommit---; cat /proc/sys/vm/overcommit_memory; echo ---memtotal---; grep MemTotal /proc/meminfo; echo ---memavailable---; grep MemAvailable /proc/meminfo'
write_cmd "$OUT/D/d4_restart_safety" 'systemctl show candidate units for StartLimitBurst/StartLimitIntervalSec/Restart/WatchdogSec'
{
  # Units from target cgroups.
  while read pid; do
    cat /proc/$pid/cgroup 2>/dev/null | sed -n 's#.*\/\([^/]*\.service\).*#\1#p'
  done < "$OUT/C/target_pids.txt"
  # Units matching native/high-RSS candidate names.
  systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' | grep -Ei 'ServiceR|pulse|ServiceV|tvs|enlightenment|wrt|dotnet|menu|ServiceT|search|home|viewer|issue|multi' || true
} | sort -u > "$OUT/D/d4_candidate_units.txt"
{
  cat "$OUT/D/d4_candidate_units.txt"
  echo ---show---
  while read u; do
    [ -n "$u" ] || continue
    echo "### $u"
    systemctl show "$u" -p StartLimitBurst -p StartLimitIntervalSec -p Restart -p WatchdogSec 2>&1
  done < "$OUT/D/d4_candidate_units.txt"
} > "$OUT/D/d4_restart_safety.out" 2> "$OUT/D/d4_restart_safety.err"
echo $? > "$OUT/D/d4_restart_safety.rc"

# Cleanup verification for transient probes.
write_cmd "$OUT/cleanup_verify" 'verify no A3 copies or B5 balloon remain'
{
  for f in /tmp/tv_recon2_true_copy /tmp/tv_recon2_true_renamed /root/tv_recon2_true_copy /root/tv_recon2_true_renamed /opt/usr/home/tv_recon2_true_copy /opt/usr/home/tv_recon2_true_renamed /dev/shm/tv_recon2_balloon; do
    ls -l "$f" 2>&1
  done
} > "$OUT/cleanup_verify.out" 2> "$OUT/cleanup_verify.err"
echo $? > "$OUT/cleanup_verify.rc"

echo DONE > "$OUT/collector.done"
