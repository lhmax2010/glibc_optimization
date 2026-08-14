#!/bin/sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 LABEL ELF [DEBUG_ELF]" >&2
    exit 2
fi

label=$1
elf=$2
debug_elf=${3-}

echo "label=$label"
stat -c 'path=%n file_size=%s' "$elf"
sha256sum "$elf"
file "$elf"
readelf -n "$elf" 2>&1 | grep -m1 'Build ID:' || true

echo '--- section_sizes_hex ---'
objdump -h "$elf" | awk '$2 ~ /^\./ { print $2, $3 }'

echo '--- section_headers_raw ---'
readelf -W -S "$elf"

echo '--- dynamic_function_distribution ---'
nm -D -S --size-sort --defined-only "$elf" 2>&1 |
    perl -ane '
        next unless @F >= 4 && $F[2] =~ /^[TtWw]$/;
        $n++; $sum += hex($F[1]);
        END {
            printf "function_count=%d\nsize_sum=%d\naverage_size=%.3f\n",
                $n || 0, $sum || 0, $n ? $sum / $n : 0;
        }
    '

echo '--- characteristic_dynamic_symbols ---'
nm -D -S --size-sort --defined-only "$elf" 2>&1 |
    grep -E ' (__libc_malloc|malloc|_int_malloc|_int_free|__libc_free|free|__libc_calloc|calloc|memcpy|strlen)(@@[^ ]+)?$' || true

echo '--- plain_nm_status ---'
nm -S --size-sort "$elf" 2>&1 | tail -5 || true

if [ -n "$debug_elf" ]; then
    echo '--- debug_file ---'
    stat -c 'path=%n file_size=%s' "$debug_elf"
    echo '--- characteristic_full_symbols ---'
    nm -S --size-sort "$debug_elf" 2>&1 |
        grep -E ' (__libc_malloc|malloc|_int_malloc|_int_free|__libc_free|free|__libc_calloc|calloc|memcpy|strlen)$' || true
    echo '--- dwarf_producer_first5 ---'
    readelf --debug-dump=info "$debug_elf" 2>/dev/null |
        grep -m5 'DW_AT_producer' || true
fi
