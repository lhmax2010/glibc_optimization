#!/bin/sh

# PG0 TV .26 identity gate. Abort before collecting anything on a wrong board.
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

out=/tmp/pg0_decisive_probe
rm -rf "$out"
mkdir -p "$out/q2_env" || exit 96

{
    echo "IDENTITY_OK=PRODUCT_BOARD"
    echo "kernel=$kernel"
    printf '%s\n' "$os_release"
} >"$out/identity.out" 2>"$out/identity.err"
echo 0 >"$out/identity.rc"

get_at_secure()
{
    pid=$1
    cls=$(od -An -j4 -N1 -tu1 "/proc/$pid/exe" 2>/dev/null | tr -d ' ')
    case "$cls" in
        1) fmt=u4; elf=elf32 ;;
        2) fmt=u8; elf=elf64 ;;
        *) echo "unknown NA"; return ;;
    esac
    val=$(od -An -v -t$fmt "/proc/$pid/auxv" 2>/dev/null |
        tr -s ' ' '\n' | sed '/^$/d' |
        awk 'NR%2==1{k=$1} NR%2==0{if(k==23){print $1; found=1; exit}} END{if(!found)print "NA"}')
    echo "$elf $val"
}

targets='AppProcB AppProcD ServiceE AppProcA ServiceH ServiceD ServiceL enlightenment ServiceF ServiceC'
{
    echo '# target	pid	elf_class	at_secure	ppid	uid	exe	cgroup'
    for target in $targets; do
        found=0
        for d in /proc/[0-9]*; do
            pid=${d#/proc/}
            case "$pid" in *[!0-9]*) continue ;; esac
            comm=$(cat "$d/comm" 2>/dev/null || true)
            [ "$comm" = "$target" ] || continue
            found=1
            set -- $(get_at_secure "$pid")
            elf=$1
            secure=$2
            ppid=$(awk '/^PPid:/{print $2}' "$d/status" 2>/dev/null)
            uid=$(awk '/^Uid:/{print $2}' "$d/status" 2>/dev/null)
            exe=$(readlink "$d/exe" 2>/dev/null || echo NA)
            cgroup=$(tr '\n' ';' < "$d/cgroup" 2>/dev/null)
            printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
                "$target" "$pid" "$elf" "$secure" "${ppid:-NA}" \
                "${uid:-NA}" "$exe" "$cgroup"
        done
        [ "$found" -eq 1 ] || printf '%s\tNA\tNA\tNA\tNA\tNA\tNA\tNA\n' "$target"
    done
} >"$out/q1_current.tsv" 2>"$out/q1_current.err"
echo $? >"$out/q1_current.rc"

pool_pid=
for d in /proc/[0-9]*; do
    pid=${d#/proc/}
    case "$pid" in *[!0-9]*) continue ;; esac
    exe=$(readlink "$d/exe" 2>/dev/null || true)
    if [ "$exe" = /usr/bin/ServiceJ ]; then
        pool_pid=$pid
        break
    fi
done

{
    echo "pool_pid=${pool_pid:-NOT_FOUND}"
    if [ -n "$pool_pid" ]; then
        pool_ppid=$(awk '/^PPid:/{print $2}' "/proc/$pool_pid/status" 2>/dev/null)
        echo "pool_ppid=${pool_ppid:-NA}"
        echo "pool_comm=$(cat "/proc/$pool_pid/comm" 2>/dev/null || echo NA)"
        echo "pool_exe=$(readlink "/proc/$pool_pid/exe" 2>/dev/null || echo NA)"
        echo -n 'pool_cmdline='; tr '\000' ' ' < "/proc/$pool_pid/cmdline" 2>/dev/null; echo
        echo '--- pool cgroup ---'; cat "/proc/$pool_pid/cgroup" 2>&1
        if [ -n "$pool_ppid" ] && [ -d "/proc/$pool_ppid" ]; then
            echo "parent_comm=$(cat "/proc/$pool_ppid/comm" 2>/dev/null || echo NA)"
            echo "parent_exe=$(readlink "/proc/$pool_ppid/exe" 2>/dev/null || echo NA)"
            echo -n 'parent_cmdline='; tr '\000' ' ' < "/proc/$pool_ppid/cmdline" 2>/dev/null; echo
            echo '--- parent cgroup ---'; cat "/proc/$pool_ppid/cgroup" 2>&1
        fi
        tr '\000' '\n' < "/proc/$pool_pid/environ" 2>/dev/null | LC_ALL=C sort >"$out/q2_env/pool_${pool_pid}.env"
        echo '--- pool GLIBC_/LD_ variables ---'
        grep -E '^(GLIBC_|LD_)' "$out/q2_env/pool_${pool_pid}.env" 2>/dev/null || echo NONE
    fi
} >"$out/q2_pool.out" 2>"$out/q2_pool.err"
echo $? >"$out/q2_pool.rc"

{
    echo '# target	pid	ppid	direct_pool_child	env_file'
    for target in AppProcB AppProcD ServiceE AppProcA ServiceH ServiceD ServiceL; do
        for d in /proc/[0-9]*; do
            pid=${d#/proc/}
            case "$pid" in *[!0-9]*) continue ;; esac
            comm=$(cat "$d/comm" 2>/dev/null || true)
            [ "$comm" = "$target" ] || continue
            ppid=$(awk '/^PPid:/{print $2}' "$d/status" 2>/dev/null)
            direct=no
            [ -n "$pool_pid" ] && [ "$ppid" = "$pool_pid" ] && direct=yes
            safe=$(printf '%s' "$target" | sed 's/[^A-Za-z0-9_.-]/_/g')
            env_file="child_${pid}_${safe}.env"
            tr '\000' '\n' < "$d/environ" 2>/dev/null | LC_ALL=C sort >"$out/q2_env/$env_file"
            printf '%s\t%s\t%s\t%s\t%s\n' "$target" "$pid" "${ppid:-NA}" "$direct" "$env_file"
            echo "--- $target pid=$pid GLIBC_/LD_ variables ---" >&2
            grep -E '^(GLIBC_|LD_)' "$out/q2_env/$env_file" >&2 2>/dev/null || echo NONE >&2
        done
    done
} >"$out/q2_children.tsv" 2>"$out/q2_children_relevant_env.out"
echo $? >"$out/q2_children.rc"

{
    echo '--- list-units launchpad ---'
    SYSTEMD_PAGER=cat systemctl list-units --all --no-pager 2>&1 | grep -i launchpad || echo NONE
    echo '--- list-unit-files launchpad ---'
    SYSTEMD_PAGER=cat systemctl list-unit-files --no-pager 2>&1 | grep -i launchpad || echo NONE
    echo '--- status ServiceJ patterns ---'
    SYSTEMD_PAGER=cat systemctl status 'ServiceJ*' --no-pager 2>&1
    echo '--- cat ServiceJ patterns ---'
    SYSTEMD_PAGER=cat systemctl cat 'ServiceJ*' --no-pager 2>&1
    if [ -n "$pool_pid" ]; then
        echo '--- status pool PID ---'
        SYSTEMD_PAGER=cat systemctl status "$pool_pid" --no-pager 2>&1
        echo '--- show pool PID ---'
        systemctl show "$pool_pid" -p Id -p Names -p FragmentPath -p DropInPaths -p MainPID -p ControlPID 2>&1
    fi
    if [ -n "${pool_ppid:-}" ]; then
        echo '--- status pool parent PID ---'
        SYSTEMD_PAGER=cat systemctl status "$pool_ppid" --no-pager 2>&1
        echo '--- show pool parent PID ---'
        systemctl show "$pool_ppid" -p Id -p Names -p FragmentPath -p DropInPaths -p MainPID -p ControlPID 2>&1
    fi
    echo '--- service MainPID/ControlPID matches ---'
    SYSTEMD_PAGER=cat systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null |
        awk '{print $1}' |
        while IFS= read -r unit; do
            [ -n "$unit" ] || continue
            main=$(systemctl show "$unit" -p MainPID --value 2>/dev/null)
            control=$(systemctl show "$unit" -p ControlPID --value 2>/dev/null)
            if [ "$main" = "${pool_pid:-X}" ] || [ "$control" = "${pool_pid:-X}" ] ||
               [ "$main" = "${pool_ppid:-X}" ] || [ "$control" = "${pool_ppid:-X}" ]; then
                echo "$unit MainPID=$main ControlPID=$control"
            fi
        done
    echo '--- loginctl list-sessions ---'
    loginctl list-sessions --no-legend --no-pager 2>&1
    echo '--- loginctl show-user 5001 ---'
    loginctl show-user 5001 2>&1
} >"$out/q2_unit_loginctl.out" 2>"$out/q2_unit_loginctl.err"
echo $? >"$out/q2_unit_loginctl.rc"

date -u +%Y-%m-%dT%H:%M:%SZ >"$out/q1_q2_finished_utc.txt"
echo DONE >"$out/q1_q2_done"
