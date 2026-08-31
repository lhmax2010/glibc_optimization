#!/bin/sh

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
if [ -d "$out" ]; then
    rm -r "$out"
fi

echo 'IDENTITY_OK=PRODUCT_BOARD'
echo "kernel=$kernel"
if [ -e "$out" ]; then
    echo PG0_TMP_CLEANUP_FAILED
    exit 2
fi
echo PG0_TMP_CLEAN

left=0
for f in /dev/shm/.pg0_zero_* /dev/shm/.pg0_random_*; do
    if [ -e "$f" ]; then
        echo "BALLOON_LEFTOVER=$f"
        left=1
    fi
done
[ "$left" -eq 0 ] || exit 3
echo PG0_BALLOONS_CLEAN
