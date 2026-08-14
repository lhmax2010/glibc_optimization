#!/bin/sh
set -u

out=/tmp/product_plateau_probe_20260814
kernel=$(uname -r); arch=$(uname -m)
case "$kernel" in *rpi4*) echo "ABORT: this is RPI4, not product board" >&2; exit 97;; esac
grep -qi '<PRODUCT_IMAGE>' /etc/os-release || { echo "ABORT: not TV product image" >&2; exit 98; }
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: unexpected arch=$arch" >&2; exit 96;; esac
command -v vk_send >/dev/null || { echo "ABORT: vk_send not found" >&2; exit 95; }

i=0
while [ ! -s "$out/start_ns.txt" ] && [ "$i" -lt 100 ]; do
    sleep 0.1
    i=$((i + 1))
done
[ -s "$out/start_ns.txt" ] || { echo "ABORT: collector start time unavailable" >&2; exit 94; }
start_ns=$(cat "$out/start_ns.txt")
log="$out/key_timeline.tsv"
printf 'round\tsequence\ttarget_offset_s\tactual_timestamp\tactual_epoch_ns\tkey\tkey_name\tvk_exit\tlateness_ms\n' >"$log"

wait_until()
{
    target_second=$1
    deadline_ns=$((start_ns + target_second * 1000000000))
    now_ns=$(date +%s%N)
    if [ "$now_ns" -lt "$deadline_ns" ]; then
        wait_ns=$((deadline_ns - now_ns))
        wait_s=$(awk -v n="$wait_ns" 'BEGIN {printf "%.3f", n/1000000000}')
        sleep "$wait_s"
    fi
}

send_key()
{
    round=$1; sequence=$2; target_second=$3; key=$4; key_name=$5
    wait_until "$target_second"
    actual_ns=$(date +%s%N)
    actual_iso=$(date -Ins)
    vk_send "$key" >/dev/null 2>&1
    rc=$?
    late_ms=$(awk -v a="$actual_ns" -v s="$start_ns" -v t="$target_second" 'BEGIN {printf "%.3f", (a-s-t*1000000000)/1000000}')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$round" "$sequence" "$target_second" "$actual_iso" "$actual_ns" "$key" "$key_name" "$rc" "$late_ms" >>"$log"
}

run_round()
{
    round=$1; base=$2
    send_key "$round" 1 "$base"       73  KEY_CH_LIST
    send_key "$round" 2 "$((base+3))" 116 KEY_DOWN
    send_key "$round" 3 "$((base+4))" 116 KEY_DOWN
    send_key "$round" 4 "$((base+5))" 116 KEY_DOWN
    send_key "$round" 5 "$((base+6))" 182 KEY_EXIT
    send_key "$round" 6 "$((base+9))" 96  KEY_CHUP
    send_key "$round" 7 "$((base+13))" 96 KEY_CHUP
    send_key "$round" 8 "$((base+17))" 95 KEY_CHDOWN
    send_key "$round" 9 "$((base+21))" 95 KEY_CHDOWN
    send_key "$round" 10 "$((base+25))" 138 KEY_GUIDE
    send_key "$round" 11 "$((base+29))" 182 KEY_EXIT
    wait_until "$((base+35))"
    {
      printf 'STATE\t%s\t' "$round"
      date -Ins
      aul_test get_app_lifecycle AppC 2>&1 || true
      aul_test get_status AppC 2>&1 || true
    } >>"$out/round_state.log"
}

run_round R1 90
run_round R2 150
run_round R3 210
run_round R4 270
run_round R5 330
run_round R6 510
wait_until 570
echo VK_ROUNDS_DONE
