#!/bin/sh

# Mandatory identity gate: never collect RPI4/unified-dev data as TV product data.
kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel" in
    *rpi4*) echo "IDENTITY_ABORT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
case "$os_release" in
    *unified-dev*) echo "IDENTITY_ABORT_UNIFIED_DEV" >&2; exit 98 ;;
esac

out=/tmp/tv_recon3_product_board
mkdir -p "$out" || exit 99
log="$out/b5_psi_balloon.out"
err="$out/b5_psi_balloon.err"
balloon=/dev/shm/.tv_recon3_balloon_$$

cleanup()
{
    rm -f "$balloon"
}
trap cleanup 0 1 2 15

exec >"$log" 2>"$err"
echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
echo "kernel=$kernel"

if [ ! -r /proc/pressure/memory ]; then
    echo PSI_UNAVAILABLE
    exit 3
fi
if [ ! -d /dev/shm ]; then
    echo SHM_UNAVAILABLE
    exit 4
fi

avail_kb=$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo)
shm_free_kb=$(df -k /dev/shm 2>/dev/null | awk 'NR==2 {print $4; exit}')
max_mb=$((avail_kb * 40 / 100 / 1024))
limit60_mb=$((avail_kb * 60 / 100 / 1024))
echo "BASE_MEMAVAILABLE_KB=$avail_kb"
echo "SHM_FREE_KB=${shm_free_kb:-NA}"
echo "MAX_TARGET_MB=$max_mb"
echo "LIMIT60_MB=$limit60_mb"
df -k /dev/shm
cat /proc/pressure/memory

if [ -n "$shm_free_kb" ] && [ $((max_mb * 1024)) -gt "$shm_free_kb" ]; then
    echo "SKIP_SHM_CAPACITY target_kb=$((max_mb * 1024)) free_kb=$shm_free_kb"
    exit 5
fi
if [ "$max_mb" -gt "$limit60_mb" ]; then
    echo "SAFETY_ABORT target_mb=$max_mb limit60_mb=$limit60_mb"
    exit 6
fi

lmk_pattern='Killed process|Out of memory|low memory|lowmemory|[[:space:]]lmk|LMK'
lmk_before=$(dmesg 2>/dev/null | grep -Eic "$lmk_pattern" || true)
echo "LMK_MATCHES_BASE=$lmk_before"

previous_mb=0
for pct in 10 20 30 40; do
    target_mb=$((avail_kb * pct / 100 / 1024))
    delta_mb=$((target_mb - previous_mb))
    echo "=== LEVEL pct=$pct target_mb=$target_mb delta_mb=$delta_mb ==="
    echo '--- before ---'
    grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
    cat /proc/pressure/memory
    dd if=/dev/zero of="$balloon" bs=1M count="$delta_mb" seek="$previous_mb" conv=notrunc 2>&1
    dd_rc=$?
    if [ "$dd_rc" -ne 0 ]; then
        echo "DD_FAILED pct=$pct rc=$dd_rc"
        break
    fi
    previous_mb=$target_mb
    echo '--- after ---'
    ls -l "$balloon"
    grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
    cat /proc/pressure/memory
    echo '--- dmesg tail ---'
    dmesg 2>&1 | tail -40
    lmk_now=$(dmesg 2>/dev/null | grep -Eic "$lmk_pattern" || true)
    echo "LMK_MATCHES_NOW=$lmk_now"
    if [ "$lmk_now" -gt "$lmk_before" ]; then
        echo "LMK_TRIGGERED_STOP pct=$pct before=$lmk_before now=$lmk_now"
        break
    fi
done

rm -f "$balloon"
trap - 0 1 2 15
echo '=== CLEANUP ==='
if [ -e "$balloon" ]; then
    echo BALLOON_CLEANUP_FAILED
    exit 7
fi
echo BALLOON_CLEANUP_OK
grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
cat /proc/pressure/memory
