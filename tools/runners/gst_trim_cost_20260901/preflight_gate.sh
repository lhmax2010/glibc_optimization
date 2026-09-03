#!/bin/sh
set -u

serial=${SDB_SERIAL:?set SDB_SERIAL to the reviewed board serial/address}
outdir=${1:?usage: preflight_gate.sh OUTPUT_DIR}
mkdir -p "$outdir" || exit 2
command_log="$outdir/commands.log"
: >"$command_log" || exit 3

run_remote()
{
    label=$1
    body=$2
    output="$outdir/$3"
    remote="$body; rc=\$?; printf 'RC=%s\n' \"\$rc\"; if [ \"\$rc\" -eq 0 ]; then printf 'DONE_%s\n' '$label'; else printf 'FAIL_%s\n' '$label'; fi"
    printf '+ sdb -s <TEST_BOARD_IP>:26101 shell %s\n' "$remote" >>"$command_log"
    sdb -s "$serial" shell "$remote" >"$output" 2>&1
    tr -d '\r' <"$output" | grep -Fx 'RC=0' >/dev/null 2>&1 || return 1
    tr -d '\r' <"$output" | grep -Fx "DONE_$label" >/dev/null 2>&1 || return 1
}

run_remote UNAME_R 'uname -r' uname_r.txt || exit 10
grep -F 'rpi4' "$outdir/uname_r.txt" >/dev/null 2>&1 || exit 11

run_remote UNAME_M 'uname -m' uname_m.txt || exit 12
first_arch=$(sed -n '1p' "$outdir/uname_m.txt" | tr -d '\r')
[ "$first_arch" = armv7l ] || exit 13

run_remote OS_RELEASE 'cat /etc/os-release' os_release.txt || exit 14
tr -d '\r' <"$outdir/os_release.txt" | grep -Fx 'BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l' >/dev/null 2>&1 || exit 15

run_remote GLIBC_RPM 'rpm -q glibc' glibc_rpm.txt || exit 16
tr -d '\r' <"$outdir/glibc_rpm.txt" | grep -Fx 'glibc-2.40-1.6.armv7l' >/dev/null 2>&1 || exit 17

run_remote MEMTOTAL "awk '/^MemTotal:/ {print}' /proc/meminfo" memtotal.txt || exit 18
memtotal=$(awk '/^MemTotal:/ {print $2; exit}' "$outdir/memtotal.txt")
case "$memtotal" in ''|*[!0-9]*) exit 19;; esac
[ "$memtotal" -ge 8036234 ] && [ "$memtotal" -le 8198582 ] || exit 20

run_remote ROOT_UID 'test "$(id -u)" = 0 && id -u' root_uid.txt || exit 21
first_uid=$(sed -n '1p' "$outdir/root_uid.txt" | tr -d '\r')
[ "$first_uid" = 0 ] || exit 22

run_remote GOVERNOR_WRITABLE 'n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do test -w "$p" && n=$((n+1)); done; printf "writable=%s\n" "$n"; test "$n" -eq 4' governor_writable.txt || exit 23
run_remote OPT_USR_WRITABLE 'test -d /opt/usr && test -w /opt/usr && printf "writable=/opt/usr\n"' opt_usr_writable.txt || exit 24

printf 'IDENTITY_AND_ENV_GATE_PASS\n' | tee "$outdir/gate_verdict.txt"
