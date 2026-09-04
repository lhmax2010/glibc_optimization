#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
arch=$(uname -m 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
expected_build_id=${EXPECTED_BUILD_ID:-tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l}
build_id=$(printf '%s\n' "$os_release" | awk -F= '/^BUILD_ID=/{print $2; exit}')
case "$kernel" in
    *rpi4*) ;;
    *) echo "IDENTITY_ABORT_NOT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
[ "$arch" = armv7l ] || { echo "IDENTITY_ABORT_NOT_ARMV7L arch=$arch" >&2; exit 96; }
[ "$build_id" = "$expected_build_id" ] || {
    echo "IDENTITY_ABORT_BUILD_ID build_id=$build_id expected=$expected_build_id" >&2
    exit 98
}

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

echo "IDENTITY_OK=RPI4_UNIFIED_TOOLCHAIN"
echo "BUILD_ID=$build_id"
echo "pid=$pid"
exec gdb -p "$pid" -batch \
    -ex 'call (int)malloc_trim(0)' \
    -ex detach
