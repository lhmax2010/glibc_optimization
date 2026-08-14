#!/bin/sh

# Mandatory identity gate before deleting the single recon temporary directory.
kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel" in
    *rpi4*) echo "IDENTITY_ABORT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
case "$os_release" in
    *unified-dev*) echo "IDENTITY_ABORT_UNIFIED_DEV" >&2; exit 98 ;;
esac

echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
if [ -d /tmp/tv_recon3_product_board ]; then
    rm -r /tmp/tv_recon3_product_board || exit 7
fi
if [ -e /tmp/tv_recon3_product_board ]; then
    echo RECON_TMP_CLEANUP_FAILED
    exit 8
fi
echo RECON_TMP_CLEAN

set -- /dev/shm/.tv_recon3_balloon_*
if [ "$1" = '/dev/shm/.tv_recon3_balloon_*' ]; then
    echo BALLOON_CLEAN
else
    echo "BALLOON_LEFTOVER:$*"
    exit 9
fi

for p in /tmp/.tv_recon3_true_* /root/.tv_recon3_true_* /opt/usr/home/.tv_recon3_true_*; do
    if [ -e "$p" ]; then
        echo "SIGNED_TRUE_PROBE_LEFTOVER:$p"
        exit 10
    fi
done
echo SIGNED_TRUE_PROBES_CLEAN
