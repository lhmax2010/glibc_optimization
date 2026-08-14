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

out=/tmp/tv_recon3_b4_full
mkdir -p "$out" || exit 99
{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    for f in /etc/ServiceR/memory.conf /etc/ServiceR/memory_product.conf /etc/ServiceR/proc.conf /etc/ServiceR/proc_product.conf; do
        echo "=== FILE $f ==="
        sed -n '1,420p' "$f" 2>&1
    done
} >"$out/b4_ServiceR_configs.out" 2>"$out/b4_ServiceR_configs.err"
echo $? >"$out/b4_ServiceR_configs.rc"
