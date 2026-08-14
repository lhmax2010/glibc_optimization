#!/bin/sh
# tizen_memopt_inventory.sh — G1/G2/Q7 on-device inventory for the glibc
# memory-optimization plan (design doc v2.1, gates G1 G2, questions Q1 Q3 Q7).
# Run as root on the target board. Pure POSIX sh + od; no python required.
#
# Collects:
#   [Q7/M5] vm.overcommit_memory, THP mode (covariates)
#   [G1/Q1] per-process AT_SECURE from /proc/PID/auxv (ground truth)
#   [G2]    per-process env blacklist hits (vars live in normal libc)
#   [extra] Threads / Rss / Pss per process (feeds A/B matrix narrowing)
#
# Output: TSV on stdout (one row per process) + summary on stderr.
# Usage:  ./tizen_memopt_inventory.sh > inventory_$(hostname)_$(date +%Y%m%d).tsv

BLACKLIST_LIVE="GLIBC_TUNABLES MALLOC_PERTURB_ LD_PRELOAD LD_AUDIT LD_PROFILE LD_DEBUG LD_DEBUG_OUTPUT GCONV_PATH MALLOC_TOP_PAD_ MALLOC_MMAP_THRESHOLD_ MALLOC_TRIM_THRESHOLD_ MALLOC_MMAP_MAX_ MALLOC_ARENA_MAX MALLOC_ARENA_TEST"
BLACKLIST_INERT="MALLOC_CHECK_"   # stub without debug preload; still report

# ---------- covariates (Q7 / M5) ----------
oc=$(cat /proc/sys/vm/overcommit_memory 2>/dev/null || echo NA)
thp=$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo NA)
echo "# host=$(hostname 2>/dev/null || echo unknown) date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" 
echo "# covariate vm.overcommit_memory=$oc"
echo "# covariate thp_enabled=$thp"
echo "# columns: pid	comm	elf_class	at_secure	uid	threads	rss_kb	pss_kb	env_hits	cmdline"

secure_cnt=0; insecure_cnt=0; unknown_cnt=0; envhit_cnt=0; total=0

# ---------- AT_SECURE from auxv ----------
# auxv = array of (ulong key, ulong value); AT_SECURE key = 23.
# Word size follows the process ELF class (byte 4 of exe: 1=ELF32, 2=ELF64).
get_at_secure() {
  pid=$1
  cls=$(od -An -j4 -N1 -tu1 "/proc/$pid/exe" 2>/dev/null | tr -d ' ')
  case "$cls" in
    1) fmt=u4 ;;
    2) fmt=u8 ;;
    *) echo "unknown NA"; return ;;
  esac
  # Emit one integer per line, then walk key/value pairs.
  val=$(od -An -v -t$fmt "/proc/$pid/auxv" 2>/dev/null | tr -s ' ' '\n' | sed '/^$/d' | \
    awk 'NR%2==1{k=$1} NR%2==0{if(k==23){print $1; found=1; exit}} END{if(!found)print "NA"}')
  case "$cls" in 1) echo "elf32 $val";; 2) echo "elf64 $val";; esac
}

# ---------- per-process walk ----------
for d in /proc/[0-9]*; do
  pid=${d#/proc/}
  # skip kernel threads (empty cmdline)
  cmdline=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)
  [ -z "$cmdline" ] && continue
  # skip self
  [ "$pid" = "$$" ] && continue
  total=$((total+1))

  comm=$(cat "$d/comm" 2>/dev/null || echo NA)
  uid=$(awk '/^Uid:/{print $2}' "$d/status" 2>/dev/null || echo NA)
  threads=$(awk '/^Threads:/{print $2}' "$d/status" 2>/dev/null || echo NA)
  if [ -r "$d/smaps_rollup" ]; then
    rss=$(awk '/^Rss:/{print $2}' "$d/smaps_rollup")
    pss=$(awk '/^Pss:/{print $2}' "$d/smaps_rollup")
  else
    rss=NA; pss=NA
  fi

  set -- $(get_at_secure "$pid")
  cls=$1; sec=$2
  case "$sec" in
    1) secure_cnt=$((secure_cnt+1));;
    0) insecure_cnt=$((insecure_cnt+1));;
    *) unknown_cnt=$((unknown_cnt+1));;
  esac

  # G2: environment blacklist scan
  hits=""
  if [ -r "$d/environ" ]; then
    envs=$(tr '\0' '\n' < "$d/environ" 2>/dev/null)
    for v in $BLACKLIST_LIVE; do
      case "$envs" in *"$v="*) hits="$hits$v(LIVE);";; esac
    done
    for v in $BLACKLIST_INERT; do
      case "$envs" in *"$v="*) hits="$hits$v(inert);";; esac
    done
  else
    hits="ENVIRON_UNREADABLE"
  fi
  [ -n "$hits" ] && [ "$hits" != "ENVIRON_UNREADABLE" ] && envhit_cnt=$((envhit_cnt+1))
  [ -z "$hits" ] && hits="-"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$pid" "$comm" "$cls" "$sec" "$uid" "$threads" "$rss" "$pss" "$hits" "$cmdline"
done

# ---------- summary (stderr) ----------
{
  echo "=== G1/G2/Q7 inventory summary ==="
  echo "overcommit_memory=$oc  thp=$thp"
  echo "processes=$total  AT_SECURE=1: $secure_cnt  AT_SECURE=0: $insecure_cnt  unknown: $unknown_cnt"
  echo "processes with LIVE env blacklist hits: $envhit_cnt"
  if [ "$secure_cnt" -gt "$insecure_cnt" ]; then
    echo "VERDICT HINT: majority AT_SECURE -> Plan B (design doc s8) likely required"
  else
    echo "VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable"
  fi
} >&2
