#!/bin/sh

kernel=$(uname -r)
case "$kernel" in
    *rpi4*) ;;
    *) echo "ABORT: not RPI4, kernel=$kernel" >&2; exit 97 ;;
esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo 'ABORT: TV product image' >&2
    exit 98
fi

root=/root/l6uirelease

capture_point()
{
    pid=$1
    point=$2
    out=$3
    {
        echo "point=$point pid=$pid epoch=$(date +%s.%N) uptime=$(cut -d ' ' -f1 /proc/uptime)"
        if kill -0 "$pid" 2>/dev/null; then echo ALIVE=1; else echo ALIVE=0; fi
        echo '## profile'
        "$root/reclaim_probe" profile "$pid"
        echo '## smaps_rollup'
        cat "/proc/$pid/smaps_rollup"
        echo '## stat'
        cat "/proc/$pid/stat"
        echo '## stat_fields'
        awk '{print "state=" $3 " minflt=" $10 " majflt=" $12 " utime=" $14 " stime=" $15}' "/proc/$pid/stat"
        echo '## zram_mm_stat'
        cat /sys/block/zram0/mm_stat
        echo '## free'
        free
    } >"$out/${point}.txt" 2>&1
}

lldb_inspect()
{
    pid=$1
    label=$2
    out=$3
    LD_LIBRARY_PATH="$root/lldb/lib" "$root/lldb/bin/lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread list' \
        -o 'bt all' \
        -o 'detach' >"$out/lldb_${label}_inspect.txt" 2>&1
}

# The UI targets' thread #1 is the event-loop thread. Every call first records
# all stacks, then records thread #1 again immediately before evaluating.
malloc_info_capture()
{
    pid=$1
    phase=$2
    out=$3
    xml="$out/malloc_info_${phase}.xml"
    xml_runtime="/tmp/l6_ui_mi_${pid}_${phase}.xml"
    rm -f "$xml_runtime"
    lldb_inspect "$pid" "$phase" "$out" || return $?
    LD_LIBRARY_PATH="$root/lldb/lib" "$root/lldb/bin/lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread list' \
        -o 'bt all' \
        -o 'thread select 1' \
        -o 'bt' \
        -o "expr -t 5000000 -- void *\$fp = (void *)fopen(\"$xml_runtime\", \"w\")" \
        -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
        -o 'expr -t 5000000 -- (int)fflush($fp)' \
        -o 'expr -t 5000000 -- (int)fclose($fp)' \
        -o 'detach' >"$out/lldb_${phase}_malloc_info.txt" 2>&1
    rc=$?
    if test "$rc" -eq 0 && test -s "$xml_runtime"; then
        cp "$xml_runtime" "$xml"
    else
        rc=1
    fi
    rm -f "$xml_runtime"
    return "$rc"
}

trim_capture()
{
    pid=$1
    out=$2
    lldb_inspect "$pid" trim "$out" || return $?
    before=$(cut -d ' ' -f1 /proc/uptime)
    LD_LIBRARY_PATH="$root/lldb/lib" "$root/lldb/bin/lldb" -b \
        -o "process attach --pid $pid" \
        -o 'thread list' \
        -o 'bt all' \
        -o 'thread select 1' \
        -o 'bt' \
        -o 'platform shell date +%s.%N' \
        -o 'expr -t 5000000 -- (int)malloc_trim(0)' \
        -o 'platform shell date +%s.%N' \
        -o 'detach' >"$out/lldb_trim.txt" 2>&1
    rc=$?
    after=$(cut -d ' ' -f1 /proc/uptime)
    echo "lldb_rc=$rc uptime_before=$before uptime_after=$after" >>"$out/lldb_trim.txt"
    return "$rc"
}

malloc_info_totals()
{
    xml=$1
    awk '
        /<unsorted / {
            if (match($0, /total="[0-9]+"/))
                unsorted += substr($0, RSTART + 7, RLENGTH - 8)
        }
        /<total type="fast"/ {
            if (match($0, /size="[0-9]+"/))
                fast = substr($0, RSTART + 6, RLENGTH - 7)
        }
        /<total type="rest"/ {
            if (match($0, /size="[0-9]+"/))
                rest = substr($0, RSTART + 6, RLENGTH - 7)
        }
        /<heap nr=/ { arenas++ }
        END {
            printf "unsorted_bytes=%d fast_bytes=%d rest_bytes=%d arenas=%d\n", unsorted, fast, rest, arenas
        }
    ' "$xml"
}

health_snapshot()
{
    out=$1
    {
        date -Ins
        systemctl is-active display-manager
        systemctl show display-manager -p MainPID -p NRestarts -p Result
        app_launcher -S
        dmesg | tail -300 | grep -Ei 'lmk|oom|out of memory|killed process|fatal|sig(segv|11)' || true
    } >"$out" 2>&1
}
