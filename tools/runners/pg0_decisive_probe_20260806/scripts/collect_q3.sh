#!/bin/sh

# PG0 TV .26 identity gate. Abort before touching tmpfs on a wrong board.
kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
if [ "$kernel" != "6.12.60" ]; then
    echo "IDENTITY_ABORT_KERNEL expected=6.12.60 actual=$kernel" >&2
    exit 97
fi
case "$os_release" in
    *rpi4*|*unified-dev*) echo "IDENTITY_ABORT_RPI4_OR_UNIFIED_DEV" >&2; exit 98 ;;
esac
case "$os_release" in
    *"<PRODUCT_IMAGE>"*) ;;
    *) echo "IDENTITY_ABORT_NOT_TIZEN10_TV" >&2; exit 99 ;;
esac

out=/tmp/pg0_decisive_probe
mkdir -p "$out" || exit 96
log="$out/q3.out"
err="$out/q3.err"
zero=/dev/shm/.pg0_zero_$$
random=/dev/shm/.pg0_random_$$
stop_file="$out/q3_safety_stop"

cleanup()
{
    rm -f "$zero" "$random"
}
trap cleanup 0 1 2 15
exec >"$log" 2>"$err"

echo 'IDENTITY_OK=PRODUCT_BOARD'
echo "kernel=$kernel"
date -u +START_UTC=%Y-%m-%dT%H:%M:%SZ

if [ ! -r /proc/pressure/memory ]; then
    echo PSI_UNAVAILABLE
    exit 3
fi
if [ ! -d /dev/shm ]; then
    echo SHM_UNAVAILABLE
    exit 4
fi

fatal_pattern='Killed process|Out of memory|low memory|lowmemory|[[:space:]]lmk|LMK|fatal signal|segfault|SIGSEGV|signal 11|SIG11|\.NET TP Worker'
dmesg 2>/dev/null >"$out/q3_dmesg_before.txt"
fatal_base=$(grep -Eic "$fatal_pattern" "$out/q3_dmesg_before.txt" 2>/dev/null || true)
echo "FATAL_LMK_BASE_COUNT=$fatal_base"

check_safety()
{
    label=$1
    dmesg 2>/dev/null >"$out/q3_dmesg_${label}.txt"
    now=$(grep -Eic "$fatal_pattern" "$out/q3_dmesg_${label}.txt" 2>/dev/null || true)
    echo "SAFETY label=$label base=$fatal_base now=$now"
    if [ "$now" -gt "$fatal_base" ]; then
        echo "SAFETY_STOP_NEW_LMK_OOM_FATAL label=$label base=$fatal_base now=$now"
        grep -Ei "$fatal_pattern" "$out/q3_dmesg_${label}.txt" | tail -20 >"$stop_file"
        cleanup
        return 1
    fi
    return 0
}

sample_state()
{
    label=$1
    echo "=== SAMPLE $label ==="
    date -u +UTC=%Y-%m-%dT%H:%M:%SZ
    awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/{print}' /proc/meminfo
    echo '--- swaps ---'
    cat /proc/swaps
    echo '--- zram mm_stat ---'
    if [ -r /sys/block/zram0/mm_stat ]; then
        cat /sys/block/zram0/mm_stat
    else
        echo ZRAM_MM_STAT_UNAVAILABLE
    fi
    echo '--- PSI ---'
    cat /proc/pressure/memory
}

avail_kb=$(awk '/^MemAvailable:/{print $2; exit}' /proc/meminfo)
shm_free_kb=$(df -k /dev/shm 2>/dev/null | awk 'NR==2{print $4; exit}')
target_mb=$((avail_kb * 30 / 100 / 1024))
limit40_mb=$((avail_kb * 40 / 100 / 1024))
echo "BASE_MEMAVAILABLE_KB=$avail_kb"
echo "SHM_FREE_KB=${shm_free_kb:-NA}"
echo "TARGET_30PCT_MB=$target_mb"
echo "LIMIT_40PCT_MB=$limit40_mb"
if [ "$target_mb" -gt "$limit40_mb" ]; then
    echo SAFETY_ABORT_TARGET_GT_40PCT
    exit 5
fi
if [ -n "$shm_free_kb" ] && [ $((target_mb * 1024)) -gt "$shm_free_kb" ]; then
    echo SAFETY_ABORT_SHM_TOO_SMALL
    exit 6
fi

sample_state baseline_before_zero
check_safety baseline_before_zero || exit 40
echo '=== ZERO_WRITE ==='
dd if=/dev/zero of="$zero" bs=1M count="$target_mb" 2>&1
zero_rc=$?
echo "ZERO_DD_RC=$zero_rc"
[ "$zero_rc" -eq 0 ] || exit 7
sample_state zero_at_30pct
check_safety zero_at_30pct || exit 41
rm -f "$zero"
echo ZERO_BALLOON_REMOVED
sleep 30
sample_state after_zero_remove_30s
check_safety after_zero_remove_30s || exit 42

# Recompute against the post-zero baseline while retaining the original 30% cap.
random_base_kb=$(awk '/^MemAvailable:/{print $2; exit}' /proc/meminfo)
random_target_mb=$((random_base_kb * 30 / 100 / 1024))
[ "$random_target_mb" -le "$limit40_mb" ] || random_target_mb=$target_mb
echo "RANDOM_BASE_MEMAVAILABLE_KB=$random_base_kb"
echo "RANDOM_TARGET_MB=$random_target_mb"
sample_state baseline_before_random
check_safety baseline_before_random || exit 43
echo '=== RANDOM_WRITE ==='
dd if=/dev/urandom of="$random" bs=1M count="$random_target_mb" 2>&1
random_rc=$?
echo "RANDOM_DD_RC=$random_rc"
[ "$random_rc" -eq 0 ] || exit 8
sample_state random_at_30pct
check_safety random_at_30pct || exit 44

echo '# elapsed_s utc memavailable_kb swap_used_kb zram_orig_data_size zram_compr_data_size zram_mem_used_total psi_some_avg10 psi_some_avg60 psi_some_avg300 psi_some_total psi_full_avg10 psi_full_avg60 psi_full_avg300 psi_full_total' >"$out/q3_timeseries.tsv"
i=0
while [ "$i" -le 30 ]; do
    elapsed=$((i * 10))
    utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    memavail=$(awk '/^MemAvailable:/{print $2; exit}' /proc/meminfo)
    swap_used=$(awk 'NR>1{s+=$4} END{print s+0}' /proc/swaps)
    if [ -r /sys/block/zram0/mm_stat ]; then
        set -- $(cat /sys/block/zram0/mm_stat)
        zorig=${1:-NA}; zcompr=${2:-NA}; zmem=${3:-NA}
    else
        zorig=NA; zcompr=NA; zmem=NA
    fi
    some=$(awk '$1=="some"{print $2, $3, $4, $5}' /proc/pressure/memory)
    full=$(awk '$1=="full"{print $2, $3, $4, $5}' /proc/pressure/memory)
    set -- $some
    savg10=${1#avg10=}; savg60=${2#avg60=}; savg300=${3#avg300=}; stotal=${4#total=}
    set -- $full
    favg10=${1#avg10=}; favg60=${2#avg60=}; favg300=${3#avg300=}; ftotal=${4#total=}
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$elapsed" "$utc" "$memavail" "$swap_used" "$zorig" "$zcompr" "$zmem" \
        "$savg10" "$savg60" "$savg300" "$stotal" \
        "$favg10" "$favg60" "$favg300" "$ftotal" >>"$out/q3_timeseries.tsv"
    cat /proc/pressure/memory >"$out/q3_psi_${elapsed}s.txt"
    check_safety "hold_${elapsed}s" || exit 45
    [ "$i" -eq 30 ] && break
    sleep 10
    i=$((i + 1))
done

rm -f "$random"
echo RANDOM_BALLOON_REMOVED
sleep 30
sample_state after_random_remove_30s
check_safety after_random_remove_30s || exit 46
trap - 0 1 2 15
if [ -e "$zero" ] || [ -e "$random" ]; then
    echo BALLOON_CLEANUP_FAILED
    exit 9
fi
echo BALLOON_CLEANUP_OK
date -u +FINISH_UTC=%Y-%m-%dT%H:%M:%SZ
echo DONE >"$out/q3_done"
