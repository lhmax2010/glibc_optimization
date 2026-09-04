#!/bin/sh
set -u

p=$(pidof enlightenment | awk '{print $1}')
[ -n "$p" ] || { echo RC=3; echo FAIL_ENLIGHTENMENT_IDLE_60S; exit 3; }
start=$(sed 's/^[^)]*) //' "/proc/$p/stat" | awk '{print $20}')
echo "sample epoch_ns pid starttime glibc_heap_pd_kb other_anon_pd_kb total_pd_kb"
i=0
while [ "$i" -le 60 ]; do
    kill -0 "$p" 2>/dev/null || {
        echo RC=4; echo FAIL_ENLIGHTENMENT_IDLE_60S; exit 4
    }
    now_start=$(sed 's/^[^)]*) //' "/proc/$p/stat" | awk '{print $20}')
    [ "$now_start" = "$start" ] || {
        echo RC=5; echo FAIL_ENLIGHTENMENT_IDLE_60S; exit 5
    }
    values=$(awk '
      function flush_mapping(  len,anon) {
        if (!have_mapping) return
        len=end-start
        anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
        if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) g+=pd
        else if (substr(perms,2,1)=="w" && anon) o+=pd
        have_mapping=0
      }
      /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
        flush_mapping(); split($1,a,"-"); start=("0x" a[1])+0; end=("0x" a[2])+0; perms=$2
        name=""; for (j=6;j<=NF;j++) name=name (j==6?"":" ") $j
        pd=0; have_mapping=1; next
      }
      /^Private_Dirty:/ {pd=$2; next}
      END {flush_mapping(); printf "%d %d %d",g,o,g+o}
    ' "/proc/$p/smaps") || {
        echo RC=6; echo FAIL_ENLIGHTENMENT_IDLE_60S; exit 6
    }
    echo "$i $(date +%s%N) $p $start $values"
    [ "$i" -eq 60 ] || sleep 1
    i=$((i + 1))
done
echo RC=0
echo DONE_ENLIGHTENMENT_IDLE_60S
