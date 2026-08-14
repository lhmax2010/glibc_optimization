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

out=/tmp/tv_recon3_product_board/C/c4_units.out
{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    for unit in issue_report_agent.service ServiceG.service ac.service pulseaudio.service ServiceR.service; do
        echo "=== UNIT $unit ==="
        systemctl show "$unit" \
            -p Id -p MainPID -p ControlPID -p ActiveState -p SubState \
            -p Restart -p StartLimitBurst -p StartLimitIntervalSec \
            -p StartLimitIntervalUSec -p StartLimitInterval \
            -p WatchdogSec -p WatchdogUSec 2>&1
    done
} >"$out" 2>"/tmp/tv_recon3_product_board/C/c4_units.err"
echo $? >"/tmp/tv_recon3_product_board/C/c4_units.rc"
