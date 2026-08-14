#!/bin/sh
set +e

OUT=/tmp/tv_recon2_llvm2218_20260806
mkdir -p "$OUT" "$OUT/A" "$OUT/B" "$OUT/C" "$OUT/D" "$OUT/E" "$OUT/smaps"

write_cmd()
{
  output_base="$1"
  shift
  printf '%s\n' "$*" > "$output_base.cmd"
}

run_cmd()
{
  output_base="$1"
  shift
  write_cmd "$output_base" "$*"
  sh -c "$*" > "$output_base.out" 2> "$output_base.err"
  printf '%s\n' "$?" > "$output_base.rc"
}

# Board identity and compiler/build flavor.
run_cmd "$OUT/E/e0_board_identity" 'cat /etc/os-release; uname -a; cat /proc/version; id; tty 2>&1 || true'

write_cmd "$OUT/E/e1_compiler_comments" 'resolve libc.so.6 and ld.so; readelf -p .comment on each actual ELF'
{
  echo '--- tool identity ---'
  command -v readelf 2>&1 || true
  readelf --version 2>&1 | head -2
  echo '--- libc ---'
  libc_path=$(readlink -f /usr/lib/libc.so.6 2>/dev/null)
  [ -n "$libc_path" ] || libc_path=/usr/lib/libc.so.6
  echo "LIBC_PATH=$libc_path"
  ls -l /usr/lib/libc.so.6 "$libc_path" 2>&1
  readelf -p .comment "$libc_path" 2>&1
  echo '--- dynamic linkers ---'
  for linker in /lib/ld-*.so* /usr/lib/ld-*.so*; do
    [ -e "$linker" ] || continue
    actual_linker=$(readlink -f "$linker" 2>/dev/null)
    [ -n "$actual_linker" ] || actual_linker="$linker"
    echo "LINKER_PATH=$linker ACTUAL=$actual_linker"
    ls -l "$linker" "$actual_linker" 2>&1
    readelf -p .comment "$actual_linker" 2>&1
  done
} > "$OUT/E/e1_compiler_comments.out" 2> "$OUT/E/e1_compiler_comments.err"
printf '%s\n' "$?" > "$OUT/E/e1_compiler_comments.rc"

write_cmd "$OUT/E/e2_rpm_provenance" "rpm -q glibc; rpm -q --qf '%{SOURCERPM}\\n' glibc; rpm -q --changelog glibc | head -40"
{
  echo '--- rpm package ---'
  rpm -q glibc
  echo '--- source rpm ---'
  rpm -q --qf '%{SOURCERPM}\n' glibc
  echo '--- changelog head ---'
  rpm -q --changelog glibc | head -40
  echo '--- package build fields ---'
  rpm -q --qf 'NAME=%{NAME}\nVERSION=%{VERSION}\nRELEASE=%{RELEASE}\nARCH=%{ARCH}\nBUILDTIME=%{BUILDTIME}\nBUILDHOST=%{BUILDHOST}\nVENDOR=%{VENDOR}\nPACKAGER=%{PACKAGER}\n' glibc
} > "$OUT/E/e2_rpm_provenance.out" 2> "$OUT/E/e2_rpm_provenance.err"
printf '%s\n' "$?" > "$OUT/E/e2_rpm_provenance.rc"

write_cmd "$OUT/E/e3_product_features" "strings libc.so.6 | grep counts for glibc.malloc.arena_max and tcache; ls /run/dlconf.dat"
{
  libc_path=$(readlink -f /usr/lib/libc.so.6 2>/dev/null)
  [ -n "$libc_path" ] || libc_path=/usr/lib/libc.so.6
  echo "LIBC_PATH=$libc_path"
  echo "ARENA_MAX_STRING_COUNT=$(strings "$libc_path" 2>/dev/null | grep -c 'glibc.malloc.arena_max')"
  echo "TCACHE_STRING_COUNT=$(strings "$libc_path" 2>/dev/null | grep -ci 'tcache')"
  echo '--- matching tunable strings ---'
  strings "$libc_path" 2>/dev/null | grep -E 'glibc\.(malloc|pthread)\.(arena_max|tcache|stack_cache_size|mmap_threshold|trim_threshold|mxfast)' | sort -u
  echo '--- dlconf ---'
  ls -l /run/dlconf.dat 2>&1
} > "$OUT/E/e3_product_features.out" 2> "$OUT/E/e3_product_features.err"
printf '%s\n' "$?" > "$OUT/E/e3_product_features.rc"

write_cmd "$OUT/E/e4_libc_size_sections" 'ls -l libc.so.6 and actual target; readelf -S; detect .symtab/.strtab'
{
  libc_path=$(readlink -f /usr/lib/libc.so.6 2>/dev/null)
  [ -n "$libc_path" ] || libc_path=/usr/lib/libc.so.6
  ls -ln /usr/lib/libc.so.6 "$libc_path" 2>&1
  echo '--- section table ---'
  readelf -W -S "$libc_path" 2>&1
  echo '--- symbol table presence ---'
  readelf -W -S "$libc_path" 2>/dev/null | grep -E '[[:space:]]\.(symtab|strtab)[[:space:]]' || true
} > "$OUT/E/e4_libc_size_sections.out" 2> "$OUT/E/e4_libc_size_sections.err"
printf '%s\n' "$?" > "$OUT/E/e4_libc_size_sections.rc"

# Group A.
write_cmd "$OUT/A/a2_proc_walk" 'for p in /proc/[0-9]*; do echo "$p $(cat $p/comm 2>/dev/null)"; done'
{
  for proc_path in /proc/[0-9]*; do
    printf '%s ' "$proc_path"
    cat "$proc_path/comm" 2>/dev/null || echo
  done
} > "$OUT/A/a2_proc_walk.out" 2> "$OUT/A/a2_proc_walk.err"
printf '%s\n' "$?" > "$OUT/A/a2_proc_walk.rc"

write_cmd "$OUT/A/a2_proc_walk_integrity" 'classify /proc/[0-9]* basenames as all-digit PID or non-PID'
{
  valid=0
  invalid=0
  for proc_path in /proc/[0-9]*; do
    base=${proc_path#/proc/}
    case "$base" in
      *[!0-9]*) invalid=$((invalid + 1)); echo "NON_PID_MATCH=$proc_path" ;;
      *) valid=$((valid + 1)) ;;
    esac
  done
  echo "VALID_PID_MATCHES=$valid"
  echo "NON_PID_MATCHES=$invalid"
} > "$OUT/A/a2_proc_walk_integrity.out" 2> "$OUT/A/a2_proc_walk_integrity.err"
printf '%s\n' "$?" > "$OUT/A/a2_proc_walk_integrity.rc"

write_cmd "$OUT/A/a3_uep_path" 'copy board-native /bin/true to /root and /opt/usr/home under two names, execute, then remove'
{
  echo SOURCE=/bin/true
  ls -l /bin/true 2>&1
  for target_dir in /root /opt/usr/home; do
    echo "--- DIR $target_dir ---"
    if [ ! -d "$target_dir" ]; then
      echo "MISSING_DIR=$target_dir"
      continue
    fi
    for target_name in tv_recon2_new_true_copy tv_recon2_new_true_renamed; do
      target_path="$target_dir/$target_name"
      rm -f "$target_path"
      cp -a /bin/true "$target_path" 2>&1
      copy_rc=$?
      chmod 755 "$target_path" 2>&1
      chmod_rc=$?
      "$target_path" > /dev/null 2> "$OUT/A/a3_exec.err.tmp"
      exec_rc=$?
      exec_stderr=$(cat "$OUT/A/a3_exec.err.tmp" 2>/dev/null)
      rm -f "$OUT/A/a3_exec.err.tmp" "$target_path"
      if [ -e "$target_path" ]; then cleanup=FAILED; else cleanup=ABSENT; fi
      echo "RESULT dir=$target_dir name=$target_name cp_rc=$copy_rc chmod_rc=$chmod_rc exec_rc=$exec_rc cleanup=$cleanup stderr=$exec_stderr"
    done
  done
} > "$OUT/A/a3_uep_path.out" 2> "$OUT/A/a3_uep_path.err"
printf '%s\n' "$?" > "$OUT/A/a3_uep_path.rc"

run_cmd "$OUT/A/a4_bg_tools" 'for x in systemd-run setsid nohup; do command -v "$x" || echo MISSING:"$x"; done'

# Group B.
run_cmd "$OUT/B/b1_swap" 'cat /proc/swaps; free; cat /proc/sys/vm/swappiness'
run_cmd "$OUT/B/b2_smaps_rollup_proc1" 'cat /proc/1/smaps_rollup'
run_cmd "$OUT/B/b3_dev_shm" 'df /dev/shm 2>&1; ls -la /dev/shm 2>&1; du -sk /dev/shm 2>&1'

write_cmd "$OUT/B/b4_ServiceR_lmk" 'list ServiceR config and capture memory/LMK/OOM threshold lines'
{
  echo '--- /etc/ServiceR ---'
  ls -la /etc/ServiceR 2>&1
  echo '--- /usr/etc/ServiceR ---'
  ls -la /usr/etc/ServiceR 2>&1
  echo '--- matching config files ---'
  if command -v find > /dev/null 2>&1; then
    find /etc /usr/etc -name '*.conf' 2>/dev/null | while read config_file; do
      grep -l -i 'memory\|lmk\|oom' "$config_file" 2>/dev/null
    done | head -120
  else
    echo FIND_MISSING
  fi
  echo '--- ServiceR threshold excerpts ---'
  grep -R -n -i 'memory\|lmk\|oom\|threshold\|available\|critical\|swap' /etc/ServiceR /usr/etc/ServiceR 2>/dev/null | head -400
} > "$OUT/B/b4_ServiceR_lmk.out" 2> "$OUT/B/b4_ServiceR_lmk.err"
printf '%s\n' "$?" > "$OUT/B/b4_ServiceR_lmk.rc"

write_cmd "$OUT/B/b5_psi_balloon" 'grow one /dev/shm balloon by 64 MiB at 64/128/192/256 MiB; record full PSI, MemAvailable and new LMK/OOM evidence; enforce 60% limit; remove'
{
  balloon=/dev/shm/tv_recon2_new_balloon
  rm -f "$balloon"
  base_available=$(awk '/MemAvailable:/ {print $2; exit}' /proc/meminfo)
  limit_mib=$((base_available * 60 / 100 / 1024))
  echo "BASE_MemAvailable_kB=$base_available"
  echo "LIMIT_60pct_MiB=$limit_mib"
  dmesg_pattern='low.?memory|lmk|oom|out of memory|killed process|kill process'
  baseline_lmk=$(dmesg 2>/dev/null | grep -Ei "$dmesg_pattern" | wc -l)
  echo "BASE_LMK_RELEVANT_COUNT=$baseline_lmk"
  echo '--- baseline pressure ---'
  cat /proc/pressure/memory 2>&1
  echo '--- baseline dmesg tail ---'
  dmesg 2>&1 | tail -40
  current_mib=0
  for level_mib in 64 128 192 256; do
    if [ "$level_mib" -gt "$limit_mib" ]; then
      echo "SKIP_LEVEL_MiB=$level_mib reason=over_60pct_limit"
      break
    fi
    echo "=== LEVEL_MiB=$level_mib ==="
    dd if=/dev/zero of="$balloon" bs=1M count=64 seek="$current_mib" conv=notrunc 2>&1
    dd_rc=$?
    current_mib=$level_mib
    echo "DD_RC=$dd_rc"
    sleep 2
    grep -E 'MemAvailable|MemFree|Cached|SwapTotal|SwapFree' /proc/meminfo
    echo '--- pressure full ---'
    cat /proc/pressure/memory 2>&1
    now_lmk=$(dmesg 2>/dev/null | grep -Ei "$dmesg_pattern" | wc -l)
    echo "LMK_RELEVANT_COUNT=$now_lmk"
    echo '--- dmesg tail ---'
    dmesg 2>&1 | tail -40
    echo '--- journal lmk tail ---'
    journalctl --no-pager -n 200 2>&1 | grep -Ei 'low.?memory|lmk|oom|out of memory|killed process|kill process|ServiceR' | tail -40
    if [ "$now_lmk" -gt "$baseline_lmk" ]; then
      echo "LMK_NEW=1 stop_after_level_MiB=$level_mib"
      rm -f "$balloon"
      break
    fi
    echo 'LMK_NEW=0'
  done
  echo '=== CLEANUP ==='
  rm -f "$balloon"
  if [ -e "$balloon" ]; then echo BALLOON_CLEANUP=FAILED; else echo BALLOON_CLEANUP=ABSENT; fi
  grep -E 'MemAvailable|MemFree|Cached|SwapTotal|SwapFree' /proc/meminfo
  cat /proc/pressure/memory 2>&1
} > "$OUT/B/b5_psi_balloon.out" 2> "$OUT/B/b5_psi_balloon.err"
printf '%s\n' "$?" > "$OUT/B/b5_psi_balloon.rc"

# Group C process table, top targets, maps and smaps.
write_cmd "$OUT/C/c0_process_table" 'numeric /proc PID walk; collect comm/RSS/PSS/Private_Dirty/threads/cmdline/exe; sort by RSS descending'
{
  printf 'pid\tcomm\trss_kb\tpss_kb\tprivate_dirty_kb\tthreads\tcmdline\texe\n'
  for proc_path in /proc/[0-9]*; do
    pid=${proc_path#/proc/}
    case "$pid" in *[!0-9]*) continue ;; esac
    [ -r "$proc_path/smaps_rollup" ] || continue
    comm=$(cat "$proc_path/comm" 2>/dev/null)
    rss=$(awk '/^Rss:/ {print $2; exit}' "$proc_path/smaps_rollup" 2>/dev/null)
    pss=$(awk '/^Pss:/ {print $2; exit}' "$proc_path/smaps_rollup" 2>/dev/null)
    private_dirty=$(awk '/^Private_Dirty:/ {print $2; exit}' "$proc_path/smaps_rollup" 2>/dev/null)
    threads=$(ls "$proc_path/task" 2>/dev/null | wc -l)
    cmdline=$(tr '\000' ' ' < "$proc_path/cmdline" 2>/dev/null)
    exe=$(readlink "$proc_path/exe" 2>/dev/null)
    [ -n "$rss" ] || rss=0
    [ -n "$pss" ] || pss=0
    [ -n "$private_dirty" ] || private_dirty=0
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$pid" "$comm" "$rss" "$pss" "$private_dirty" "$threads" "$cmdline" "$exe"
  done
} > "$OUT/C/c0_process_table.unsorted" 2> "$OUT/C/c0_process_table.err"
{
  head -1 "$OUT/C/c0_process_table.unsorted"
  tail -n +2 "$OUT/C/c0_process_table.unsorted" | sort -t '	' -k3,3nr
} > "$OUT/C/c0_process_table.out"
printf '%s\n' "$?" > "$OUT/C/c0_process_table.rc"

tail -n +2 "$OUT/C/c0_process_table.out" | head -10 | awk '{print $1}' > "$OUT/C/target_pids.tmp"
for process_name in ServiceR pulseaudio ServiceV ServiceC enlightenment ServiceE ServiceH; do
  pgrep -x "$process_name" 2>/dev/null >> "$OUT/C/target_pids.tmp"
done
sort -n "$OUT/C/target_pids.tmp" | awk 'NF && !seen[$1]++ {print $1}' > "$OUT/C/target_pids.txt"
rm -f "$OUT/C/target_pids.tmp"

write_cmd "$OUT/C/c1_targets" 'for selected PIDs: comm, cmdline, exe, cgroup, rw-p map count, systemctl status by PID'
{
  while read pid; do
    [ -n "$pid" ] || continue
    echo "### PID $pid"
    echo "comm=$(cat /proc/$pid/comm 2>/dev/null)"
    echo "cmdline=$(tr '\000' ' ' < /proc/$pid/cmdline 2>/dev/null)"
    echo "exe=$(readlink /proc/$pid/exe 2>/dev/null)"
    echo "rw_p_count=$(grep -c 'rw-p' /proc/$pid/maps 2>/dev/null)"
    echo '--- cgroup ---'
    cat "/proc/$pid/cgroup" 2>/dev/null
    echo '--- systemctl status PID ---'
    systemctl status "$pid" 2>&1 | head -4
  done < "$OUT/C/target_pids.txt"
} > "$OUT/C/c1_targets.out" 2> "$OUT/C/c1_targets.err"
printf '%s\n' "$?" > "$OUT/C/c1_targets.rc"

write_cmd "$OUT/C/c4_pid_unit_mapping" 'derive PID to .service mapping from cgroup; capture matching units'
{
  echo '--- PID mapping ---'
  while read pid; do
    [ -n "$pid" ] || continue
    comm=$(cat "/proc/$pid/comm" 2>/dev/null)
    cgroup_text=$(cat "/proc/$pid/cgroup" 2>/dev/null)
    unit=$(echo "$cgroup_text" | sed -n 's#.*\/\([^/]*\.service\).*#\1#p' | head -1)
    [ -n "$unit" ] || unit=NONE
    printf 'PID=%s COMM=%s UNIT_FROM_CGROUP=%s\n' "$pid" "$comm" "$unit"
  done < "$OUT/C/target_pids.txt"
  echo '--- candidate service units ---'
  systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | grep -Ei 'ServiceR|pulse|ServiceV|tvs|enlightenment|wrt|dotnet|menu|ServiceT|search|home|viewer|issue|multi' || true
} > "$OUT/C/c4_pid_unit_mapping.out" 2> "$OUT/C/c4_pid_unit_mapping.err"
printf '%s\n' "$?" > "$OUT/C/c4_pid_unit_mapping.rc"

while read pid; do
  [ -n "$pid" ] || continue
  comm=$(cat "/proc/$pid/comm" 2>/dev/null | tr -c 'A-Za-z0-9_.-' '_')
  [ -n "$comm" ] || comm=unknown
  cat "/proc/$pid/smaps" > "$OUT/smaps/${pid}_${comm}.smaps" 2> "$OUT/smaps/${pid}_${comm}.smaps.err"
  cat "/proc/$pid/maps" > "$OUT/smaps/${pid}_${comm}.maps" 2> "$OUT/smaps/${pid}_${comm}.maps.err"
done < "$OUT/C/target_pids.txt"

# Group D.
run_cmd "$OUT/D/d1_cpu_governor" 'nproc 2>&1 || grep -c ^processor /proc/cpuinfo; cat /sys/devices/system/cpu/online; for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$f=$(cat $f 2>&1)"; done'
run_cmd "$OUT/D/d2_thermal" 'ls -la /sys/class/thermal 2>&1; for z in /sys/class/thermal/thermal_zone*; do [ -e "$z" ] || continue; echo "ZONE=$z"; cat "$z/type" 2>&1; cat "$z/temp" 2>&1; done'
run_cmd "$OUT/D/d3_vm_mem" 'cat /proc/sys/vm/overcommit_memory; grep MemTotal /proc/meminfo; grep MemAvailable /proc/meminfo'

write_cmd "$OUT/D/d4_restart_safety" 'systemctl show candidate units with restart/start-limit/watchdog properties; no restart'
{
  while read pid; do
    cat "/proc/$pid/cgroup" 2>/dev/null | sed -n 's#.*\/\([^/]*\.service\).*#\1#p'
  done < "$OUT/C/target_pids.txt"
  systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' | grep -Ei 'ServiceR|pulse|ServiceV|tvs|enlightenment|wrt|dotnet|menu|ServiceT|search|home|viewer|issue|multi' || true
} | sort -u > "$OUT/D/d4_candidate_units.txt"
{
  cat "$OUT/D/d4_candidate_units.txt"
  echo '--- show ---'
  while read unit; do
    [ -n "$unit" ] || continue
    echo "### $unit"
    systemctl show "$unit" -p StartLimitBurst -p StartLimitIntervalSec -p StartLimitIntervalUSec -p Restart -p WatchdogSec -p WatchdogUSec 2>&1
  done < "$OUT/D/d4_candidate_units.txt"
} > "$OUT/D/d4_restart_safety.out" 2> "$OUT/D/d4_restart_safety.err"
printf '%s\n' "$?" > "$OUT/D/d4_restart_safety.rc"

write_cmd "$OUT/cleanup_verify" 'verify A3 copies and B5 balloon are absent'
{
  for transient in /root/tv_recon2_new_true_copy /root/tv_recon2_new_true_renamed /opt/usr/home/tv_recon2_new_true_copy /opt/usr/home/tv_recon2_new_true_renamed /dev/shm/tv_recon2_new_balloon; do
    if [ -e "$transient" ]; then echo "PRESENT=$transient"; else echo "ABSENT=$transient"; fi
  done
} > "$OUT/cleanup_verify.out" 2> "$OUT/cleanup_verify.err"
printf '%s\n' "$?" > "$OUT/cleanup_verify.rc"

echo DONE > "$OUT/collector.done"
