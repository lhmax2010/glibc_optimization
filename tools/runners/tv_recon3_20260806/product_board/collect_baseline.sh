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

out=/tmp/tv_recon3_product_board
mkdir -p "$out" || exit 99

{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    echo '--- uname-r ---'
    printf '%s\n' "$kernel"
    echo '--- os-release ---'
    printf '%s\n' "$os_release"
    echo '--- uname-a ---'
    uname -a
    echo '--- proc-version ---'
    cat /proc/version
} >"$out/identity.out" 2>"$out/identity.err"
echo $? >"$out/identity.rc"

{
    echo '--- libc candidates ---'
    ls -l /usr/lib/libc.so.6 /lib/libc.so.6 /usr/lib/libc-*.so /lib/libc-*.so 2>&1
    libc=
    for p in /usr/lib/libc.so.6 /lib/libc.so.6; do
        if [ -e "$p" ]; then libc=$p; break; fi
    done
    echo "LIBC_PATH=$libc"
    echo '--- execute libc ---'
    [ -n "$libc" ] && "$libc" 2>&1
    echo '--- rpm q ---'
    rpm -q glibc 2>&1
    echo '--- source rpm ---'
    rpm -q --qf '%{SOURCERPM}\n' glibc 2>&1
    echo '--- optflags ---'
    rpm -q --qf '%{OPTFLAGS}\n' glibc 2>&1
    echo '--- rpm qi ---'
    rpm -qi glibc 2>&1
    echo '--- changelog head ---'
    rpm -q --changelog glibc 2>&1 | head -40
} >"$out/e1_e2_package.out" 2>"$out/e1_e2_package.err"
echo $? >"$out/e1_e2_package.rc"

{
    echo '--- loader candidates ---'
    ls -l /usr/lib/ld-*.so* /lib/ld-*.so* 2>&1
    loader=
    for p in /usr/lib/ld-linux.so.3 /lib/ld-linux.so.3; do
        if [ -e "$p" ]; then loader=$p; break; fi
    done
    echo "LOADER_PATH=$loader"
    echo '--- list tunables ---'
    [ -n "$loader" ] && "$loader" --list-tunables 2>&1
    echo '--- requested tunables ---'
    [ -n "$loader" ] && "$loader" --list-tunables 2>&1 |
        grep -E 'glibc\.malloc\.(arena_max|mmap_threshold|trim_threshold)|glibc\.pthread\.stack_cache_size'
} >"$out/e3_tunables.out" 2>"$out/e3_tunables.err"
echo $? >"$out/e3_tunables.rc"

{
    libc=
    loader=
    for p in /usr/lib/libc.so.6 /lib/libc.so.6; do [ ! -e "$p" ] || { libc=$p; break; }; done
    for p in /usr/lib/ld-linux.so.3 /lib/ld-linux.so.3; do [ ! -e "$p" ] || { loader=$p; break; }; done
    echo '--- artifacts ---'
    [ -z "$libc" ] || ls -l "$libc"
    [ -z "$loader" ] || ls -l "$loader"
    [ -z "$libc" ] || sha256sum "$libc" 2>&1
    [ -z "$loader" ] || sha256sum "$loader" 2>&1
    echo '--- dlconf ---'
    ls -l /run/dlconf.dat 2>&1
    echo '--- installed debuginfo ---'
    rpm -q glibc-debuginfo 2>&1
    echo '--- symtab proxy: stripped command if present ---'
    command -v file >/dev/null 2>&1 && { [ -z "$libc" ] || file "$libc"; }
} >"$out/e4_artifacts.out" 2>"$out/e4_artifacts.err"
echo $? >"$out/e4_artifacts.rc"

{
    echo '--- signed /bin/true relocation test ---'
    for d in /tmp /root /opt/usr/home; do
        echo "PATH_TEST=$d"
        if [ ! -d "$d" ]; then echo MISSING_DIR; continue; fi
        probe="$d/.tv_recon3_true_$$"
        if cp /bin/true "$probe" 2>&1; then
            ls -l "$probe"
            "$probe"; echo "EXEC_RC=$?"
            rm -f "$probe"; echo "REMOVE_RC=$?"
        else
            echo "COPY_RC=$?"
        fi
    done
} >"$out/a2_uep_paths.out" 2>"$out/a2_uep_paths.err"
echo $? >"$out/a2_uep_paths.rc"

{
    for x in systemd-run setsid nohup awk sed grep od dd rpm systemctl journalctl pmap readelf nm; do
        command -v "$x" 2>/dev/null || echo "MISSING:$x"
    done
} >"$out/a3_commands.out" 2>"$out/a3_commands.err"
echo $? >"$out/a3_commands.rc"

{
    probe=/etc/.tv_recon3_wtest_$$
    if touch "$probe" 2>&1; then
        echo ETC_WRITE_OK
        rm -f "$probe"
        echo "REMOVE_RC=$?"
    else
        echo "ETC_WRITE_FAILED rc=$?"
    fi
} >"$out/a4_etc_write.out" 2>"$out/a4_etc_write.err"
echo $? >"$out/a4_etc_write.rc"

{
    echo '--- meminfo ---'
    grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
    echo '--- swaps ---'
    cat /proc/swaps
    echo '--- free ---'
    free
    echo '--- swappiness ---'
    cat /proc/sys/vm/swappiness
    echo '--- zram ---'
    ls -ld /sys/block/zram* 2>&1
} >"$out/b1_memory_swap.out" 2>"$out/b1_memory_swap.err"
echo $? >"$out/b1_memory_swap.rc"

cat /proc/1/smaps_rollup >"$out/b2_pid1_smaps_rollup.out" 2>"$out/b2_pid1_smaps_rollup.err"
echo $? >"$out/b2_pid1_smaps_rollup.rc"

{
    echo '--- overcommit ---'; cat /proc/sys/vm/overcommit_memory
    echo '--- thp ---'; ls -la /sys/kernel/mm/transparent_hugepage/ 2>&1
    echo '--- cpu ---'; command -v nproc >/dev/null 2>&1 && nproc; grep -c '^processor' /proc/cpuinfo; cat /sys/devices/system/cpu/online
    echo '--- governors ---'; for p in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$p=$(cat "$p" 2>&1)"; done
    echo '--- available governors ---'; for p in /sys/devices/system/cpu/cpu*/cpufreq/scaling_available_governors; do echo "$p=$(cat "$p" 2>&1)"; done
    echo '--- thermal entries ---'; ls -la /sys/class/thermal/
    echo '--- thermal values ---'; for z in /sys/class/thermal/thermal_zone*; do echo "$z type=$(cat "$z/type" 2>&1) temp=$(cat "$z/temp" 2>&1)"; done
    echo '--- pressure memory ---'; cat /proc/pressure/memory 2>&1
    echo '--- shm ---'; df /dev/shm 2>&1; ls -la /dev/shm 2>&1
} >"$out/b3_kernel_cpu_thermal.out" 2>"$out/b3_kernel_cpu_thermal.err"
echo $? >"$out/b3_kernel_cpu_thermal.rc"

{
    echo '--- ServiceR dir ---'
    ls -la /etc/ServiceR/ 2>&1
    echo '--- memory-related config files ---'
    find /etc -type f -name '*.conf' -print 2>/dev/null |
        while IFS= read -r f; do
            grep -l -i -E 'memory|lmk|oom' "$f" 2>/dev/null
        done | head -80
    echo '--- matching ServiceR config lines ---'
    find /etc/ServiceR -type f -print 2>/dev/null |
        while IFS= read -r f; do
            grep -Hn -i -E 'memory|lmk|oom|threshold' "$f" 2>/dev/null
        done
} >"$out/b4_lmk.out" 2>"$out/b4_lmk.err"
echo $? >"$out/b4_lmk.rc"

echo DONE >"$out/done"
