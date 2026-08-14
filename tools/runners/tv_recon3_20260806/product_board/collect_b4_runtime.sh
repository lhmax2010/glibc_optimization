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

out=/tmp/tv_recon3_b4_runtime
mkdir -p "$out" || exit 99
{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    echo '--- ServiceR journal memory/threshold lines ---'
    SYSTEMD_PAGER=cat journalctl -u ServiceR.service --no-pager 2>&1 |
        grep -i -E 'memory|threshold|swap|reclaim|lmk|psi|profile' | tail -240
    echo '--- ServiceR command line/status ---'
    tr '\000' ' ' < /proc/$(systemctl show ServiceR.service -p MainPID --value)/cmdline 2>&1
    echo
    systemctl status ServiceR.service --no-pager 2>&1 | head -40
} >"$out/b4_runtime.out" 2>"$out/b4_runtime.err"
echo $? >"$out/b4_runtime.rc"
