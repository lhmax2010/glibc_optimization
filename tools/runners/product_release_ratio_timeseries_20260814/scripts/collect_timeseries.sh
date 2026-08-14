#!/bin/sh
set -u

out=/tmp/product_release_ratio_20260814
kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) echo "ABORT: this is RPI4, not product board" >&2; exit 97;; esac
grep -qi '<PRODUCT_IMAGE>' /etc/os-release || { echo "ABORT: not TV product image" >&2; exit 98; }
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: unexpected arch=$arch" >&2; exit 96;; esac

mkdir -p "$out" || exit 3
targets="$out/targets.tsv"
cat >"$targets" <<'EOF'
target	comm	baseline_pid
AppProcD	AppProcD	424
ServiceE	ServiceE	404
AppProcB	AppProcB	896
ServiceH	ServiceH	2869
cynara	cynara	205
AppProcA	AppProcA	2724
systemd	systemd	1
enlightenment	enlightenment	258
buxton2d_worker	buxton2d_worker	229
ServiceD	ServiceD	1037
EOF

tsv="$out/timeseries.tsv"
meta="$out/collection_meta.txt"
printf 'sample\ttimestamp\tepoch_ns\ttarget\tcomm\tpid\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\tMemAvailable_kb\tzram_used_kb\tzram_orig_bytes\tzram_compr_bytes\tzram_mem_used_bytes\n' >"$tsv"

start_ns=$(date +%s%N)
start_iso=$(date -Ins)
samples=${SAMPLES:-300}
overruns=0
sample=0
while [ "$sample" -lt "$samples" ]; do
    deadline_ns=$((start_ns + sample * 2000000000))
    now_ns=$(date +%s%N)
    if [ "$now_ns" -lt "$deadline_ns" ]; then
        wait_ns=$((deadline_ns - now_ns))
        wait_s=$(awk -v n="$wait_ns" 'BEGIN { printf "%.3f", n/1000000000 }')
        sleep "$wait_s"
    else
        if [ "$sample" -gt 0 ]; then overruns=$((overruns + 1)); fi
    fi

    stamp_ns=$(date +%s%N)
    stamp_iso=$(date -Ins)
    mem=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    zused=$(awk '$1 ~ /zram/ {print $4; found=1} END {if (!found) print 0}' /proc/swaps)
    set -- $(cat /sys/block/zram0/mm_stat 2>/dev/null || echo 'NA NA NA')
    zorig=${1:-NA}; zcompr=${2:-NA}; zmem=${3:-NA}

    row_prefix="$out/.row_${sample}_"
    idx=0
    {
      IFS= read -r header
      while IFS='	' read -r target comm baseline_pid; do
        idx=$((idx + 1))
        (
          pid=$(pgrep -x "$comm" 2>/dev/null | head -1)
          if [ -z "$pid" ] || [ ! -r "/proc/$pid/smaps" ]; then
            printf '%s\t%s\tNA\tNA\tNA\tNA\tNA\tNA\tNA\n' "$target" "$comm"
            exit 0
          fi
          faults=$(sed 's/^[^)]*) //' "/proc/$pid/stat" 2>/dev/null | awk '{print $8, $10}')
          set -- $faults
          minflt=${1:-NA}; majflt=${2:-NA}
          awk -v target="$target" -v comm="$comm" -v pid="$pid" -v minflt="$minflt" -v majflt="$majflt" '
            function flush_mapping(  len,anon) {
              if (!have_mapping) return
              len=end-start
              anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
              if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) {
                g+=pd
              } else if (substr(perms,2,1)=="w" && anon) {
                o+=pd
              } else {
                f+=pd
              }
              have_mapping=0
            }
            /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
              flush_mapping()
              split($1,a,"-"); start=strtonum("0x" a[1]); end=strtonum("0x" a[2]); perms=$2
              name=""; for (i=6;i<=NF;i++) name=name (i==6?"":" ") $i
              pd=0; have_mapping=1; next
            }
            /^Private_Dirty:/ { pd=$2; next }
            END {
              flush_mapping()
              printf "%s\t%s\t%s\t%d\t%d\t%d\t%d\t%s\t%s\n",target,comm,pid,g,o,f,g+o+f,minflt,majflt
            }
          ' "/proc/$pid/smaps"
        ) >"${row_prefix}${idx}" &
      done
    } <"$targets"
    wait
    snapshot=$(
      i=1
      while [ "$i" -le "$idx" ]; do
        cat "${row_prefix}${i}"
        rm -f "${row_prefix}${i}"
        i=$((i + 1))
      done
    )
    printf '%s\n' "$snapshot" | while IFS='	' read -r target comm pid g o f total minflt majflt; do
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$sample" "$stamp_iso" "$stamp_ns" "$target" "$comm" "$pid" "$g" "$o" "$f" "$total" \
        "$minflt" "$majflt" "$mem" "$zused" "$zorig" "$zcompr" "$zmem" >>"$tsv"
    done
    sample=$((sample + 1))
done

end_ns=$(date +%s%N)
end_iso=$(date -Ins)
{
    echo IDENTITY_OK
    echo "kernel=$kernel"
    echo "arch=$arch"
    grep -E '^(PRETTY_NAME|BUILD_ID)=' /etc/os-release
    echo "start_iso=$start_iso"
    echo "end_iso=$end_iso"
    echo "start_ns=$start_ns"
    echo "end_ns=$end_ns"
    echo "elapsed_seconds=$(awk -v s="$start_ns" -v e="$end_ns" 'BEGIN {printf "%.3f", (e-s)/1000000000}')"
    echo "requested_samples=$samples"
    echo "data_rows=$(($(wc -l <"$tsv")-1))"
    echo "deadline_overruns=$overruns"
} >"$meta"
echo TIMESERIES_DONE
