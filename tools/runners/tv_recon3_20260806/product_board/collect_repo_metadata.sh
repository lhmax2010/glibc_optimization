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

out=/tmp/tv_recon3_product_board/g2_repo_metadata.out
{
    echo 'IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV'
    echo '--- installed glibc debug packages ---'
    rpm -qa 2>&1 | grep -E '^glibc-(debuginfo|debugsource)' || true
    echo '--- repo config directories ---'
    for d in /etc/zypp/repos.d /etc/yum.repos.d /etc/dnf/repos.d; do
        echo "DIR=$d"
        ls -la "$d" 2>&1
        if [ -d "$d" ]; then
            for f in "$d"/*; do
                [ -f "$f" ] || continue
                echo "FILE=$f"
                sed -n '1,160p' "$f"
            done
        fi
    done
    echo '--- package manager commands ---'
    for x in zypper dnf yum; do command -v "$x" 2>/dev/null || echo "MISSING:$x"; done
} >"$out" 2>"/tmp/tv_recon3_product_board/g2_repo_metadata.err"
echo $? >"/tmp/tv_recon3_product_board/g2_repo_metadata.rc"
