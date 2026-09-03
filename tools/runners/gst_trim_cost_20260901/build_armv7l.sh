#!/bin/sh
set -eu

# Build the instrumented loop decoder with the glibc-2.40 toolchain while
# taking GStreamer headers and link inputs from a separate compatible sysroot.
# No board connection is made by this script.

usage() {
    echo "usage: TOOLCHAIN_ROOT=/path/to/scratch.armv7l.0 GST_SYSROOT=/path/to/scratch.armv7l.0 $0 [output]" >&2
    exit 2
}

toolchain_root=${TOOLCHAIN_ROOT:-}
gst_sysroot=${GST_SYSROOT:-}
output=${1:-gst_loop_decode.armv7l}

[ -n "$toolchain_root" ] || usage
[ -n "$gst_sysroot" ] || usage
[ -x "$toolchain_root/emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc" ] || usage
[ -f "$gst_sysroot/usr/include/gstreamer-1.0/gst/gst.h" ] || usage
[ -f "$gst_sysroot/usr/lib/libgstreamer-1.0.so.0" ] || usage
command -v bwrap >/dev/null 2>&1 || usage

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
src=tools/gst_loop_decode/gst_loop_decode.c
build_dir=${GST_BUILD_DIR:-$repo/.build/armv7l/gst_loop_decode}
build_output=$build_dir/gst_loop_decode.armv7l

case "$output" in
    /*) ;;
    *) output="$(pwd)/$output" ;;
esac

mkdir -p "$(dirname -- "$output")" "$build_dir"
cd "$repo"

bwrap \
    --tmpfs / \
    --dir /home --bind /home /home \
    --dir /tmp --bind /tmp /tmp \
    --ro-bind "$toolchain_root/usr" /usr \
    --ro-bind "$toolchain_root/lib" /lib \
    --proc /proc \
    --ro-bind "$toolchain_root/emul" /emul \
    "$toolchain_root/emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc" \
    -B/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/ \
    -std=c99 -O2 -g -Wall -Wextra -Werror \
    "-fdebug-prefix-map=$repo=." \
    "-fdebug-prefix-map=$toolchain_root=/toolchain" \
    "-fdebug-prefix-map=$gst_sysroot=/gst-sysroot" \
    -I"$gst_sysroot/usr/include/gstreamer-1.0" \
    -I"$gst_sysroot/usr/include/glib-2.0" \
    -I"$gst_sysroot/usr/lib/glib-2.0/include" \
    -o "$build_output" "$src" \
    -L"$gst_sysroot/usr/lib" \
    -Wl,-rpath-link,"$gst_sysroot/usr/lib" \
    -Wl,--allow-shlib-undefined \
    -l:libgstreamer-1.0.so.0 -l:libgobject-2.0.so.0 \
    -l:libglib-2.0.so.0 -pthread

cp "$build_output" "$output"

file "$output"
sha256sum "$src" "$output"
