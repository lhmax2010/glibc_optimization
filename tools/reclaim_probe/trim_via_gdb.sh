#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel" in
    *rpi4*) ;;
    *) echo "IDENTITY_ABORT_NOT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
case "$os_release" in
    *unified-dev*) ;;
    *) echo "IDENTITY_ABORT_NOT_UNIFIED_DEV" >&2; exit 98 ;;
esac

case "${1:-}" in
    ''|*[!0-9]*) echo "usage: trim_via_gdb.sh <pid>" >&2; exit 2 ;;
esac
pid=$1
if ! command -v gdb >/dev/null 2>&1; then
    echo "GDB_UNAVAILABLE"
    exit 127
fi
if [ ! -d "/proc/$pid" ]; then
    echo "PROCESS_NOT_FOUND pid=$pid" >&2
    exit 3
fi

echo "IDENTITY_OK=RPI4_UNIFIED_DEV"
echo "pid=$pid"
exec gdb -p "$pid" -batch \
    -ex 'call (int)malloc_trim(0)' \
    -ex detach
