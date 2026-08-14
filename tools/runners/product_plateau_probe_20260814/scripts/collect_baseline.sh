#!/bin/sh
set -u

out=/tmp/product_plateau_probe_20260814
kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) echo "ABORT: this is RPI4, not product board" >&2; exit 97;; esac
grep -qi '<PRODUCT_IMAGE>' /etc/os-release || { echo "ABORT: not TV product image" >&2; exit 98; }
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: unexpected arch=$arch" >&2; exit 96;; esac
command -v vk_send >/dev/null || { echo "ABORT: vk_send not found" >&2; exit 95; }

mkdir -p "$out" || exit 3
tmp="$out/all_process_baseline.unsorted.tsv"
printf 'timestamp\tpid\tcomm\texe\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tglibc_segments\tother_anon_segments\tfile_backed_segments\tminflt\tmajflt\n' >"$tmp"

for proc in /proc/[0-9]*; do
    pid=${proc#/proc/}
    [ -r "$proc/smaps" ] || continue
    vals=$(awk '
      function flush(  len,anon) {
        if (!have) return
        len=end-start
        anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
        if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) {
          g+=pd; gs++
        } else if (substr(perms,2,1)=="w" && anon) {
          o+=pd; os++
        } else {
          f+=pd; fs++
        }
        have=0
      }
      /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
        flush()
        split($1,a,"-"); start=strtonum("0x" a[1]); end=strtonum("0x" a[2]); perms=$2
        name=""; for (i=6;i<=NF;i++) name=name (i==6?"":" ") $i
        pd=0; have=1; next
      }
      /^Private_Dirty:/ { pd=$2; next }
      END { flush(); printf "%d\t%d\t%d\t%d\t%d\t%d\t%d",g,o,f,g+o+f,gs,os,fs }
    ' "$proc/smaps" 2>/dev/null) || continue
    [ -n "$vals" ] || continue
    comm=$(cat "$proc/comm" 2>/dev/null | tr '\t\n' '  ')
    exe=$(readlink "$proc/exe" 2>/dev/null || true)
    stat=$(cat "$proc/stat" 2>/dev/null || true)
    tail=${stat##*) }
    set -- $tail
    minflt=${8:-NA}
    majflt=${10:-NA}
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -Ins)" "$pid" "$comm" "$exe" "$vals" "$minflt" "$majflt" >>"$tmp"
done

{
    head -1 "$tmp"
    tail -n +2 "$tmp" | sort -t '	' -k5,5nr
} >"$out/all_process_baseline.tsv"
echo "BASELINE_ROWS=$(($(wc -l <"$out/all_process_baseline.tsv")-1))"
echo BASELINE_DONE
