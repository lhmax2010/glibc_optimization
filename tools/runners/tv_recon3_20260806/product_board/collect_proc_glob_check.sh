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

out=/tmp/tv_recon3_product_board/proc_glob_check.out
{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    echo '--- exact entry ---'
    ls -ld /proc/4kbtin 2>&1
    echo '--- numeric-prefix nonnumeric proc entries ---'
    for d in /proc/[0-9]*; do
        base=${d#/proc/}
        case "$base" in *[!0-9]*) ls -ld "$d" 2>&1;; esac
    done
} >"$out" 2>"/tmp/tv_recon3_product_board/proc_glob_check.err"
echo $? >"/tmp/tv_recon3_product_board/proc_glob_check.rc"
