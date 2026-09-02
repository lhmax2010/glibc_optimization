#!/bin/sh
set -eu

: "${SDB_SERIAL:?set SDB_SERIAL to <TEST_BOARD_IP>:26101}"
output=${1:?usage: read_only_board_audit.sh OUTPUT_DIR}
mkdir -p "$output"

run_remote()
{
    name=$1
    marker=$2
    body=$3
    path="$output/$name.txt"
    sdb -s "$SDB_SERIAL" shell "$body; remote_rc=\$?; echo RC=\$remote_rc; if [ \$remote_rc -eq 0 ]; then echo DONE_$marker; else echo FAIL_$marker; fi" \
        2>&1 | tee "$path"
    tr -d '\r' < "$path" | grep -Fx 'RC=0' >/dev/null
    tr -d '\r' < "$path" | grep -Fx "DONE_$marker" >/dev/null
}

sdb version 2>&1 | tee "$output/sdb_version.txt"
sdb devices 2>&1 | tee "$output/sdb_devices.txt"

run_remote identity_uname_r UNAME_R 'uname -r'
run_remote identity_uname_m UNAME_M 'uname -m'
run_remote identity_os_release OS_RELEASE 'cat /etc/os-release'
run_remote env_glibc GLIBC 'rpm -q glibc'
run_remote env_memtotal MEMTOTAL 'grep "^MemTotal:" /proc/meminfo'

uname_r=$(tr -d '\r' < "$output/identity_uname_r.txt" | sed -n '1p')
uname_m=$(tr -d '\r' < "$output/identity_uname_m.txt" | sed -n '1p')
glibc_rpm=$(tr -d '\r' < "$output/env_glibc.txt" | sed -n '1p')
memtotal=$(tr -d '\r' < "$output/env_memtotal.txt" | sed -n '1p')
case "$uname_r" in *rpi4*) ;; *) echo "identity gate failed: kernel=$uname_r" >&2; exit 20 ;; esac
[ "$uname_m" = armv7l ] || { echo "identity gate failed: arch=$uname_m" >&2; exit 21; }
tr -d '\r' < "$output/identity_os_release.txt" | \
    grep -Fx 'BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l' >/dev/null || {
        echo 'identity gate failed: BUILD_ID mismatch' >&2
        exit 22
    }
[ "$glibc_rpm" = glibc-2.40-1.6.armv7l ] || { echo "environment gate failed: $glibc_rpm" >&2; exit 23; }
[ "$memtotal" = 'MemTotal:        8117408 kB' ] || { echo "environment gate failed: $memtotal" >&2; exit 24; }
printf '%s\n' IDENTITY_AND_ENV_GATE_PASS | tee "$output/gate_verdict.txt"

run_remote work_root_audit WORK_ROOT_AUDIT '
echo WORK_ROOT=/opt/usr/glibc_memopt
if [ -e /opt/usr/glibc_memopt ]; then
    ls -ladn /opt/usr/glibc_memopt
    find /opt/usr/glibc_memopt -xdev -maxdepth 6 -exec ls -ldn {} \;
else
    echo WORK_ROOT_ABSENT
fi'

run_remote top_level_audit TOP_LEVEL_AUDIT '
for directory in /tmp /home/ /opt/usr; do
    echo TOP_LEVEL=$directory
    ls -lan "$directory" || exit $?
done'

run_remote candidate_hash_audit CANDIDATE_HASH_AUDIT '
for directory in /tmp /home/ /opt/usr; do
    find "$directory" -xdev -mindepth 1 -maxdepth 1 -type f \
        \( -name "*alloc_bench*" -o -name "*gst_loop_decode*" -o -name "*reclaim_probe*" \
        -o -name "*.mp4" -o -name "*.tsv" -o -name "*.json" -o -name "*.xml" \
        -o -name "*.hist" -o -name "*.sh" \) -exec sha256sum {} \; || exit $?
done
if [ -d /opt/usr/glibc_memopt ]; then
    find /opt/usr/glibc_memopt -xdev -maxdepth 6 -type f -exec sha256sum {} \;
fi'

run_remote process_audit PROCESS_AUDIT 'ps -ef'
run_remote governor_audit GOVERNOR_AUDIT '
for path in /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor \
            /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor \
            /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor \
            /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor; do
    printf "%s=" "$path"
    cat "$path" || exit $?
done'
run_remote zram_mm_stat_audit ZRAM_MM_STAT_AUDIT 'cat /sys/block/zram0/mm_stat'
run_remote swaps_audit SWAPS_AUDIT 'cat /proc/swaps'
run_remote mem_idle_audit MEM_IDLE_AUDIT 'grep -E "^(MemTotal|MemAvailable):" /proc/meminfo'
run_remote time_audit TIME_AUDIT 'date; date_rc=$?; uptime; uptime_rc=$?; [ $date_rc -eq 0 ] && [ $uptime_rc -eq 0 ]'

run_remote rpm_last_audit RPM_LAST_AUDIT '
package_rows=$(rpm -qa --last)
rpm_rc=$?
printf "%s\n" "$package_rows" | sed -n "1,40p"
[ $rpm_rc -eq 0 ]'
run_remote df_audit DF_AUDIT 'df -h / /opt/usr; human_rc=$?; df -B1 / /opt/usr; byte_rc=$?; [ $human_rc -eq 0 ] && [ $byte_rc -eq 0 ]'

run_remote crash_content_audit CRASH_CONTENT_AUDIT '
for directory in /opt/usr/share/crash /var/crash /var/lib/systemd/coredump \
                 /opt/usr/home/owner/share/crash /opt/usr/data/crash /opt/usr/share/coredump; do
    if [ -e "$directory" ]; then
        echo CRASH_PATH=$directory
        find "$directory" -xdev -maxdepth 4 -exec ls -ldn {} \;
    else
        echo CRASH_PATH_ABSENT=$directory
    fi
done'
run_remote dmesg_event_audit DMESG_EVENT_AUDIT '
dmesg_text=$(dmesg)
dmesg_rc=$?
printf "%s\n" "$dmesg_text" | grep -Ei "Out of memory:|Killed process [0-9]|lowmemorykiller|low memory killer|(^|[^[:alnum:]_])LMK([^[:alnum:]_]|$)|segfault at|segmentation fault|general protection fault"
event_match_rc=$?
echo EVENT_MATCH_RC=$event_match_rc
[ $dmesg_rc -eq 0 ]'

printf '%s\n' READ_ONLY_HYGIENE_AUDIT_DONE | tee "$output/audit_verdict.txt"
