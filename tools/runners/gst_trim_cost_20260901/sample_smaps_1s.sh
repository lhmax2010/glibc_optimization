#!/bin/sh
set -u

pid=$1
out=$2
meta=$3
proc_root=${PROC_ROOT:-/proc}
sample=0
overruns=0
sampler_rc=0
failure_reason=none
start_ns=$(date +%s%N)
start_iso=$(date -Ins)

printf 'sample\ttimestamp\tepoch_ns\telapsed_s\tpid\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\n' >"$out" || exit 2

while [ -r "$proc_root/$pid/smaps" ]; do
    deadline_ns=$((start_ns + sample * 1000000000))
    now_ns=$(date +%s%N)
    if [ "$now_ns" -lt "$deadline_ns" ]; then
        wait_ns=$((deadline_ns - now_ns))
        wait_s=$(awk -v n="$wait_ns" 'BEGIN { printf "%.3f", n/1000000000 }')
        sleep "$wait_s"
    elif [ "$sample" -gt 0 ]; then
        overruns=$((overruns + 1))
    fi
    [ -r "$proc_root/$pid/smaps" ] || break

    stamp_ns=$(date +%s%N)
    stamp_iso=$(date -Ins)
    elapsed=$(awk -v s="$start_ns" -v e="$stamp_ns" 'BEGIN {printf "%.6f", (e-s)/1000000000}')
    stat_payload=$(sed 's/^[^)]*) //' "$proc_root/$pid/stat" 2>/dev/null)
    stat_rc=$?
    if [ "$stat_rc" -ne 0 ]; then
        [ ! -d "$proc_root/$pid" ] && break
        sampler_rc=4; failure_reason=stat-read; break
    fi
    faults=$(printf '%s\n' "$stat_payload" | awk '{print $8, $10}')
    set -- $faults
    if [ "$#" -ne 2 ]; then
        [ ! -d "$proc_root/$pid" ] && break
        sampler_rc=5; failure_reason=stat-parse; break
    fi
    minflt=$1; majflt=$2
    case "$minflt:$majflt" in *[!0-9:]*) sampler_rc=5; failure_reason=stat-parse; break;; esac
    classes=$(awk '
      function flush_mapping(  len,anon) {
        if (!have_mapping) return
        len=end-start
        anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
        if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) g+=pd
        else if (substr(perms,2,1)=="w" && anon) o+=pd
        else f+=pd
        mappings++; have_mapping=0
      }
      /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
        flush_mapping(); split($1,a,"-"); start=("0x" a[1])+0; end=("0x" a[2])+0; perms=$2
        name=""; for (i=6;i<=NF;i++) name=name (i==6?"":" ") $i
        pd=0; have_mapping=1; next
      }
      /^Private_Dirty:/ { pd=$2; next }
      END { flush_mapping(); printf "%d %d %d %d %d",g,o,f,g+o+f,mappings }
    ' "$proc_root/$pid/smaps" 2>/dev/null)
    classes_rc=$?
    set -- $classes
    if [ "$classes_rc" -ne 0 ] || [ "$#" -ne 5 ] || [ "$5" -le 0 ]; then
        [ ! -d "$proc_root/$pid" ] && break
        sampler_rc=6; failure_reason=smaps-parse; break
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$sample" "$stamp_iso" "$stamp_ns" "$elapsed" "$pid" "$1" "$2" "$3" "$4" "$minflt" "$majflt" >>"$out" || exit 3
    sample=$((sample + 1))
done

if [ "$sample" -eq 0 ] && [ "$sampler_rc" -eq 0 ]; then sampler_rc=7; failure_reason=zero-samples; fi
end_ns=$(date +%s%N); end_iso=$(date -Ins)
{
    printf 'start_iso=%s\nend_iso=%s\nstart_ns=%s\nend_ns=%s\n' "$start_iso" "$end_iso" "$start_ns" "$end_ns"
    printf 'samples=%s\ndeadline_overruns=%s\nfailure_reason=%s\nRC=%s\n' "$sample" "$overruns" "$failure_reason" "$sampler_rc"
    if [ "$sampler_rc" -eq 0 ]; then printf 'DONE_EXTERNAL_SAMPLER\n'; else printf 'FAIL_EXTERNAL_SAMPLER\n'; fi
} >"$meta"
exit "$sampler_rc"
