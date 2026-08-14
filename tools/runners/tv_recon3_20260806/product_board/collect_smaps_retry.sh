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

out=/tmp/tv_recon3_product_board/C/smaps_retry
mkdir -p "$out" || exit 99
pids='2556 562 572 3772 265 1048 4042 1595 669 613 654 1309 2899'

{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    for pid in $pids; do
        if [ ! -r "/proc/$pid/smaps" ]; then
            echo "pid=$pid status=VANISHED_OR_UNREADABLE"
            continue
        fi
        comm=$(cat "/proc/$pid/comm" 2>/dev/null || echo UNKNOWN)
        safe=$(printf '%s' "$comm" | sed 's/[^A-Za-z0-9_.-]/_/g')
        target="$out/${pid}_${safe}.smaps"
        cat "/proc/$pid/smaps" >"$target" 2>"$out/${pid}_${safe}.err"
        rc=$?
        bytes=$(wc -c <"$target" 2>/dev/null || echo 0)
        echo "pid=$pid comm=$comm rc=$rc bytes=$bytes target=$target"
    done
} >"$out/status.out" 2>"$out/status.err"
echo $? >"$out/status.rc"
