#!/bin/sh

kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
if [ "$kernel" != "6.12.60" ]; then
    echo "IDENTITY_ABORT_KERNEL expected=6.12.60 actual=$kernel" >&2
    exit 97
fi
case "$os_release" in
    *rpi4*|*unified-dev*) echo "IDENTITY_ABORT_RPI4_OR_UNIFIED_DEV" >&2; exit 98 ;;
esac
case "$os_release" in
    *<PRODUCT_IMAGE>*) ;;
    *) echo "IDENTITY_ABORT_NOT_TIZEN10_TV" >&2; exit 99 ;;
esac

out=/tmp/reclaim_ceiling_product_board
mkdir -p "$out" || exit 96
{
    echo IDENTITY_OK=PRODUCT_BOARD
    echo "kernel=$kernel"
    printf '%s\n' "$os_release"
} >"$out/identity.out" 2>"$out/identity.err"

{
    for d in /proc/[0-9]*; do
        pid=${d#/proc/}
        case "$pid" in *[!0-9]*) continue ;; esac
        cmdline=$(tr '\000' ' ' <"$d/cmdline" 2>/dev/null)
        [ -n "$cmdline" ] || continue
        rss=$(awk '/^Rss:/{print $2; exit}' "$d/smaps_rollup" 2>/dev/null)
        [ -n "$rss" ] || continue
        comm=$(cat "$d/comm" 2>/dev/null || echo NA)
        printf '%s\t%s\t%s\n' "$rss" "$pid" "$comm"
    done
} | sort -t '	' -k1,1nr | head -5 >"$out/top5.tsv"

profile_one()
{
    pid=$1
    comm=$2
    awk -v pid="$pid" -v comm="$comm" '
        function hex(c) {
            c = tolower(c)
            return index("0123456789abcdef", c) - 1
        }
        function hexdec(s,    i, n) {
            n = 0
            for (i = 1; i <= length(s); i++) n = n * 16 + hex(substr(s, i, 1))
            return n
        }
        function flush(    len, c) {
            if (!have) return
            len = end - start
            if (name == "[heap]" ||
                (perms == "rw-p" && name == "" && start % 1048576 == 0 && len > 0 && len <= 1048576))
                c = "g"
            else if (substr(perms, 2, 1) == "w" && (name == "" || name ~ /^\[.*\]$/))
                c = "a"
            else
                c = "f"
            seg[c]++
            virt[c] += len
            rss[c] += map_rss * 1024
            pd[c] += map_pd * 1024
        }
        $1 ~ /^[0-9a-fA-F]+-[0-9a-fA-F]+$/ {
            flush()
            split($1, addr, "-")
            start = hexdec(addr[1]); end = hexdec(addr[2]); perms = $2
            name = ""
            if (NF >= 6) {
                name = $6
                for (i = 7; i <= NF; i++) name = name " " $i
            }
            map_rss = 0; map_pd = 0; have = 1
            next
        }
        $1 == "Rss:" { map_rss = $2; next }
        $1 == "Private_Dirty:" { map_pd = $2; next }
        END {
            flush()
            printf("{\"schema\":\"reclaim_probe.shell.v1\",\"command\":\"profile\",\"pid\":%d,\"comm\":\"%s\",", pid, comm)
            printf("\"classes\":{\"glibc-heap\":{\"segments\":%d,\"virtual_bytes\":%.0f,\"rss_bytes\":%.0f,\"private_dirty_bytes\":%.0f},", seg["g"], virt["g"], rss["g"], pd["g"])
            printf("\"other-anon\":{\"segments\":%d,\"virtual_bytes\":%.0f,\"rss_bytes\":%.0f,\"private_dirty_bytes\":%.0f},", seg["a"], virt["a"], rss["a"], pd["a"])
            printf("\"file-backed\":{\"segments\":%d,\"virtual_bytes\":%.0f,\"rss_bytes\":%.0f,\"private_dirty_bytes\":%.0f}},", seg["f"], virt["f"], rss["f"], pd["f"])
            printf("\"total\":{\"segments\":%d,\"rss_bytes\":%.0f,\"private_dirty_bytes\":%.0f}}\n", seg["g"]+seg["a"]+seg["f"], rss["g"]+rss["a"]+rss["f"], pd["g"]+pd["a"]+pd["f"])
        }
    ' "/proc/$pid/smaps"
}

: >"$out/top5_profiles.jsonl"
while IFS='	' read -r rss pid comm; do
    if [ -r "/proc/$pid/smaps" ]; then
        profile_one "$pid" "$comm" >>"$out/top5_profiles.jsonl" 2>>"$out/top5_profiles.err"
    else
        echo "PROCESS_VANISHED pid=$pid comm=$comm" >>"$out/top5_profiles.err"
    fi
done <"$out/top5.tsv"

{
    echo -n 'gdb='; command -v gdb 2>/dev/null || echo MISSING
    echo -n 'date='; date -u +%Y-%m-%dT%H:%M:%SZ
} >"$out/capabilities.out" 2>"$out/capabilities.err"
echo DONE >"$out/done"
