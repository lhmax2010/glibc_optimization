#!/bin/sh
set -u

mode=${1:-}
shift 2>/dev/null || true
ip=
cache=
remote=/opt/usr/glibc_memopt/tizen_native_evidence_20260904/input
base=https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/tizen-base-toolchain_20260813.050338/repos/standard/packages/armv7l
packages='libgmp-4.2.1-1.6.armv7l.rpm gdbm-1.8.3-1.7.armv7l.rpm libpython3_141_0-3.14.2-1.6.armv7l.rpm python3-base-3.14.2-1.6.armv7l.rpm python3-3.14.2-1.5.armv7l.rpm gdb-16.3-1.1.armv7l.rpm'

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ip) ip=$2; shift 2 ;;
        --cache) cache=$2; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
[ "$mode" = install ] || [ "$mode" = remove ] || { echo "usage: $0 install|remove --ip <address> [--cache <dir>]" >&2; exit 2; }
[ -n "$ip" ] || exit 2
printf '%s\n' "$ip" | grep -Eq '^[A-Za-z0-9.-]+$' || exit 2
serial="$ip:26101"

sha_for()
{
    case "$1" in
        libgmp-4.2.1-1.6.armv7l.rpm) echo 32dd98f86f6bb1e42bb5c79e309f00a4de5f4837cbf23ac8dfaa962659ddd926 ;;
        gdbm-1.8.3-1.7.armv7l.rpm) echo b50094a73e0428e9747148406979e92418d02b5046978e989d4e363e903b656a ;;
        libpython3_141_0-3.14.2-1.6.armv7l.rpm) echo bf5e67b3ca80de1201c5ea43d3cc2aebe79b147a3a438a684e92a8672d906ea2 ;;
        python3-base-3.14.2-1.6.armv7l.rpm) echo 1fb82edadca233223af41e1490651b35b314ae8f1df75d414a7596629fef083c ;;
        python3-3.14.2-1.5.armv7l.rpm) echo 97cfa688e41c29012775818e79c35c95b454a1ceee17025cc3a43665abc64b68 ;;
        gdb-16.3-1.1.armv7l.rpm) echo 95d713691a0628ed0cc7fdf61cbe896f439135e4bb0b8c5690c2ef5010530165 ;;
        *) return 1 ;;
    esac
}

run_remote()
{
    mr_label=$1
    mr_body=$2
    command="$mr_body; rc=\$?; printf 'RC=%s\n' \"\$rc\"; if [ \"\$rc\" -eq 0 ]; then printf 'DONE_%s\n' '$mr_label'; else printf 'FAIL_%s\n' '$mr_label'; fi"
    output=$(sdb -s "$serial" shell "$command" </dev/null 2>&1)
    printf '%s\n' "$output"
    printf '%s\n' "$output" | tr -d '\r' | grep -Fx RC=0 >/dev/null 2>&1 || return 1
    printf '%s\n' "$output" | tr -d '\r' | grep -Fx "DONE_$mr_label" >/dev/null 2>&1
}

if [ "$mode" = remove ]; then
    names='gdb python3 python3-base libpython3_141_0 libgmp gdbm'
    run_remote GDB_REMOVE_TEST "rpm -e --test $names" || exit 1
    run_remote GDB_REMOVE "rpm -e $names" || exit 1
    run_remote GDB_REMOVE_VERIFY 'for p in gdb python3 python3-base libpython3_141_0 libgmp gdbm; do rpm -q "$p" >/dev/null 2>&1 && exit 1; done' || exit 1
    exit 0
fi

[ -n "$cache" ] || { echo "--cache is required for install" >&2; exit 2; }
case "$cache" in /|/home|/opt|/tmp) echo "refusing broad cache path" >&2; exit 2;; esac
mkdir -p "$cache" || exit 1
for rpm_file in $packages; do
    [ -f "$cache/$rpm_file" ] || curl -fL --retry 3 -o "$cache/$rpm_file" "$base/$rpm_file" || exit 1
    expected=$(sha_for "$rpm_file") || exit 1
    actual=$(sha256sum "$cache/$rpm_file" | awk '{print $1}') || exit 1
    [ "$actual" = "$expected" ] || { echo "SHA mismatch: $rpm_file" >&2; exit 1; }
done

available=$(sdb -s "$serial" shell "df -B1 / | awk 'NR==2 {print \\$4}'" </dev/null 2>/dev/null | tr -d '\r')
case "$available" in ''|*[!0-9]*) echo "cannot read root available bytes" >&2; exit 1;; esac
required_after=1288490189
installed_bytes=53010679
[ $((available - installed_bytes)) -ge "$required_after" ] || { echo "root-space budget would be violated" >&2; exit 1; }
run_remote GDB_STAGE "mkdir -p '$remote'" || exit 1
for rpm_file in $packages; do
    sdb -s "$serial" push "$cache/$rpm_file" "$remote/$rpm_file" </dev/null || exit 1
done
remote_rpms=
for rpm_file in $packages; do remote_rpms="$remote_rpms $remote/$rpm_file"; done
run_remote GDB_INSTALL_TEST "rpm -Uvh --test $remote_rpms" || exit 1
run_remote GDB_INSTALL "rpm -Uvh $remote_rpms" || exit 1
run_remote GDB_INSTALL_VERIFY 'test "$(rpm -q gdb)" = gdb-16.3-1.1.armv7l && gdb --version | grep -Fx "GNU gdb (GDB) 16.3"' || exit 1
