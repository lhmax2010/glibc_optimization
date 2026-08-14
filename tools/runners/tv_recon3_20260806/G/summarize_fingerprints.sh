#!/bin/bash
set -euo pipefail

if (( $# < 2 || $# % 2 != 0 )); then
    echo "usage: $0 LABEL ELF [LABEL ELF ...]" >&2
    exit 2
fi

printf 'label\tfile_size\ttext_size\trodata_size\tdyn_func_count\tdyn_func_size_sum\tdyn_func_avg\tmalloc\tfree\tcalloc\tmemcpy\tstrlen\n'

while (( $# )); do
    label=$1
    elf=$2
    shift 2

    file_size=$(stat -c '%s' "$elf")
    text_hex=$(objdump -h "$elf" | awk '$2 == ".text" {print $3; exit}')
    rodata_hex=$(objdump -h "$elf" | awk '$2 == ".rodata" {print $3; exit}')
    text_size=$((16#$text_hex))
    rodata_size=$((16#$rodata_hex))

    read -r fn_count fn_sum fn_avg < <(
        nm -D -S --size-sort --defined-only "$elf" 2>&1 |
            perl -ane '
                next unless @F >= 4 && $F[2] =~ /^[TtWw]$/;
                $n++; $sum += hex($F[1]);
                END { printf "%d %d %.3f\n", $n || 0, $sum || 0,
                    $n ? $sum / $n : 0; }
            '
    )

    sizes=()
    for symbol in malloc free calloc memcpy strlen; do
        hex=$(nm -D -S --defined-only "$elf" 2>/dev/null |
            awk -v s="$symbol" '$4 ~ ("^" s "(@@|$)") {print $2; exit}')
        if [[ -n $hex ]]; then sizes+=("$((16#$hex))"); else sizes+=(NA); fi
    done

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$label" "$file_size" "$text_size" "$rodata_size" \
        "$fn_count" "$fn_sum" "$fn_avg" "${sizes[@]}"
done
