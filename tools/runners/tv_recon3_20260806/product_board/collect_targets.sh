#!/bin/sh

# Mandatory identity gate: never collect RPI4/unified-dev data as TV product data.
kernel=$(uname -r 2>/dev/null || echo UNKNOWN)
os_release=$(cat /etc/os-release 2>/dev/null || echo MISSING)
case "$kernel" in
    *rpi4*) echo "IDENTITY_ABORT_RPI4 kernel=$kernel" >&2; exit 97 ;;
esac
case "$os_release" in
    *unified-dev*) echo "IDENTITY_ABORT_UNIFIED_DEV" >&2; exit 98 ;;
esac

out=/tmp/tv_recon3_product_board/C
mkdir -p "$out/smaps" || exit 99
pids='2556 562 572 3772 265 1048 4042 1595 669 613 654 1309 2899'

{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    echo "SNAPSHOT_PIDS=$pids"
    for pid in $pids; do
        echo "=== PID $pid ==="
        if [ ! -d "/proc/$pid" ]; then
            echo PROCESS_VANISHED
            continue
        fi
        comm=$(cat "/proc/$pid/comm" 2>/dev/null || echo UNKNOWN)
        echo "comm=$comm"
        echo -n 'exe='; readlink "/proc/$pid/exe" 2>&1
        echo -n 'ppid='; awk '/^PPid:/ {print $2}' "/proc/$pid/status"
        echo -n 'uid='; awk '/^Uid:/ {print $2}' "/proc/$pid/status"
        echo -n 'threads='; awk '/^Threads:/ {print $2}' "/proc/$pid/status"
        echo '--- cgroup ---'; cat "/proc/$pid/cgroup" 2>&1
        echo '--- cmdline ---'; tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null; echo
        echo '--- parent chain ---'
        current=$pid
        depth=0
        while [ "$current" -gt 0 ] 2>/dev/null && [ "$depth" -lt 12 ]; do
            parent=$(awk '/^PPid:/ {print $2}' "/proc/$current/status" 2>/dev/null)
            pc=$(cat "/proc/$current/comm" 2>/dev/null || echo VANISHED)
            pe=$(readlink "/proc/$current/exe" 2>/dev/null || echo NA)
            echo "depth=$depth pid=$current ppid=${parent:-NA} comm=$pc exe=$pe"
            [ -n "$parent" ] || break
            [ "$parent" -ne "$current" ] || break
            current=$parent
            depth=$((depth + 1))
        done
        echo '--- systemctl status pid ---'
        SYSTEMD_PAGER=cat systemctl status "$pid" --no-pager 2>&1 | head -16
        echo '--- systemctl show pid ---'
        systemctl show "$pid" -p Id -p MainPID -p ControlPID -p Restart -p StartLimitBurst -p StartLimitIntervalSec -p WatchdogSec 2>&1
        safe=$(printf '%s' "$comm" | sed 's/[^A-Za-z0-9_.-]/_/g')
        cp "/proc/$pid/smaps" "$out/smaps/${pid}_${safe}.smaps" 2>"$out/smaps/${pid}_${safe}.err"
        echo "smaps_copy_rc=$?"
    done
} >"$out/c1_targets.out" 2>"$out/c1_targets.err"
echo $? >"$out/c1_targets.rc"

{
    echo '--- active/all service list ---'
    SYSTEMD_PAGER=cat systemctl list-units --type=service --all --no-legend --no-pager 2>&1
    echo '--- service MainPID map ---'
    SYSTEMD_PAGER=cat systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null |
        awk '{print $1}' |
        while IFS= read -r unit; do
            [ -n "$unit" ] || continue
            values=$(systemctl show "$unit" -p MainPID -p ControlPID 2>/dev/null | tr '\n' ' ')
            echo "$unit $values"
        done
} >"$out/c3_unit_map.out" 2>"$out/c3_unit_map.err"
echo $? >"$out/c3_unit_map.rc"

echo DONE >"$out/done"
