#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/tizen_native_evidence_20260905
asset="$work/small_320x240.mp4"
out="$work/recon_gst_sequence.tsv"
pid=

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    exit "$rc"
}
trap finish EXIT HUP INT TERM

fail()
{
    echo "reason=$1"
    echo RC=1
    echo FAIL_GST_SEQUENCE_RECON
    exit 1
}

test "$(sha256sum "$asset" | awk '{print $1}')" = \
    3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d || fail asset_sha
printf 'cell\tstart_ns\talive_30s_ns\tend_ns\tduration_s\tbuffer_messages\texit_code\terror_lines\n' >"$out"
sequence_start=$(date +%s%N)
i=1
while [ "$i" -le 5 ]; do
    log="$work/recon_gst_${i}.log"
    begin=$(date +%s%N)
    gst-launch-1.0 -m -v filesrc location="$asset" ! decodebin ! \
        identity name=counter silent=false ! fakesink sync=true >"$log" 2>&1 &
    pid=$!
    sleep 30
    alive=$(date +%s%N)
    kill -0 "$pid" 2>/dev/null || fail "cell_${i}_not_alive_at_30s"
    wait "$pid"
    cell_rc=$?
    pid=
    end=$(date +%s%N)
    buffers=$(grep -c 'last-message = chain' "$log" 2>/dev/null || true)
    errors=$(grep -c 'ERROR' "$log" 2>/dev/null || true)
    elapsed=$(awk -v a="$begin" -v b="$end" 'BEGIN {printf "%.9f",(b-a)/1000000000}')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$i" "$begin" "$alive" "$end" "$elapsed" "$buffers" "$cell_rc" "$errors" >>"$out"
    [ "$cell_rc" -eq 0 ] || fail "cell_${i}_exit"
    [ "$buffers" -gt 0 ] || fail "cell_${i}_no_buffers"
    [ "$errors" -eq 0 ] || fail "cell_${i}_error_log"
    echo "DONE_GST_RECON_CELL_${i} duration_s=$elapsed buffers=$buffers"
    i=$((i + 1))
done
sequence_end=$(date +%s%N)
sequence_elapsed=$(awk -v a="$sequence_start" -v b="$sequence_end" 'BEGIN {printf "%.9f",(b-a)/1000000000}')
echo "sequence_elapsed_s=$sequence_elapsed"
awk -v value="$sequence_elapsed" 'BEGIN {exit !(value >= 300.0)}' || fail sequence_under_300s
echo RC=0
echo DONE_GST_SEQUENCE_RECON
