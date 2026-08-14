#!/bin/sh
set -u

base=/root/l6_curve
matrix=$base/matrix.tsv
bench=$base/alloc_bench.armv7l
results=$base/results/matrix

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

mkdir -p "$results" || exit 3
dmesg >"$results/dmesg_before.txt" 2>&1
date -Ins >"$results/matrix_start.txt"
awk '/^Mem(Total|Available):/{print}' /proc/meminfo >>"$results/matrix_start.txt"
cat /proc/swaps >>"$results/matrix_start.txt"

tail -n +2 "$matrix" | while IFS="$(printf '\t')" read -r cell factor profile release_pct live_set release_order repetitions; do
    [ -n "$cell" ] || continue
    case "$profile" in
        external:*) profile_arg="external:$base/${profile#external:}" ;;
        *) profile_arg=$profile ;;
    esac

    rep=1
    while [ "$rep" -le "$repetitions" ]; do
        out=$results/$cell/rep$rep
        mkdir -p "$out" || exit 4
        mem_pre=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
        {
            date -Ins
            echo "cell=$cell"
            echo "factor=$factor"
            echo "profile=$profile"
            echo "release_pct=$release_pct"
            echo "live_set=$live_set"
            echo "release_order=$release_order"
            echo "rep=$rep"
            echo "MemAvailable_pre_kB=$mem_pre"
            echo "CMD=$bench --threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15 --idle-trim --post-trim-ops-per-thread 4096 --profile $profile_arg --live-set $live_set --idle-release $release_pct --release-order $release_order --outdir $out"
        } >"$out/run.txt"

        echo "START cell=$cell rep=$rep mem_kB=$mem_pre $(date -Ins)"
        "$bench" \
            --threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15 \
            --idle-trim --post-trim-ops-per-thread 4096 \
            --profile "$profile_arg" --live-set "$live_set" \
            --idle-release "$release_pct" --release-order "$release_order" \
            --outdir "$out" >"$out/result.json" 2>"$out/stderr.txt"
        rc=$?
        mem_post=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
        {
            echo "EXIT=$rc"
            echo "MemAvailable_post_kB=$mem_post"
            date -Ins
        } >>"$out/run.txt"
        free >"$out/free_after.txt" 2>&1
        for f in /sys/block/zram*/mm_stat; do
            [ -e "$f" ] && echo "$f=$(cat "$f")"
        done >"$out/zram_after.txt" 2>&1
        dmesg | tail -120 >"$out/dmesg_tail.txt" 2>&1
        echo "DONE cell=$cell rep=$rep exit=$rc mem_kB=$mem_post $(date -Ins)"
        sleep 5
        rep=$((rep + 1))
    done
done

dmesg >"$results/dmesg_after.txt" 2>&1
{
    date -Ins
    awk '/^Mem(Total|Available):/{print}' /proc/meminfo
    cat /proc/swaps
    echo MATRIX_DONE
} >"$results/matrix_end.txt"
echo MATRIX_DONE
