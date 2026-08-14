#!/bin/sh
set -u

out=/tmp/product_cyclic_target_probe_20260814
kernel=$(uname -r); arch=$(uname -m)
case "$kernel" in *rpi4*) echo "ABORT: this is RPI4, not product board" >&2; exit 97;; esac
grep -qi '<PRODUCT_IMAGE>' /etc/os-release || { echo "ABORT: not TV product image" >&2; exit 98; }
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: unexpected arch=$arch" >&2; exit 96;; esac
command -v vk_send >/dev/null || { echo "ABORT: vk_send not found" >&2; exit 95; }

mkdir -p "$out" || exit 3
{
    echo IDENTITY_OK
    date -Ins
    echo BEFORE
    aul_test get_app_lifecycle AppC 2>&1 || true
    aul_test get_status AppC 2>&1 || true
    vk_send 73 >/dev/null 2>&1; echo "KEY=73 RC=$?"; sleep 3
    echo AFTER_73
    date -Ins
    aul_test get_app_lifecycle AppC 2>&1 || true
    aul_test get_status AppC 2>&1 || true
    vk_send 182 >/dev/null 2>&1; echo "KEY=182 RC=$?"; sleep 3
    echo AFTER_182
    date -Ins
    aul_test get_app_lifecycle AppC 2>&1 || true
    aul_test get_status AppC 2>&1 || true
} >"$out/vk_preflight.txt"

echo VK_PREFLIGHT_DONE
