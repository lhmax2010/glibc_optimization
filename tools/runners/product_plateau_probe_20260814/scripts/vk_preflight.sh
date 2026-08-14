#!/bin/sh
set -u

out=/tmp/product_plateau_probe_20260814
kernel=$(uname -r); arch=$(uname -m)
case "$kernel" in *rpi4*) echo "ABORT: this is RPI4, not product board" >&2; exit 97;; esac
grep -qi '<PRODUCT_IMAGE>' /etc/os-release || { echo "ABORT: not TV product image" >&2; exit 98; }
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: unexpected arch=$arch" >&2; exit 96;; esac
command -v vk_send >/dev/null || { echo "ABORT: vk_send not found" >&2; exit 95; }

log="$out/vk_preflight.txt"
{
    echo IDENTITY_OK
    echo BEFORE
    date -Ins
    app_launcher -r AppC 2>&1 || true
    pgrep -a -x AppProcA 2>&1 || true
    echo SEND_73
    date -Ins
    vk_send 73 2>&1
    echo "VK73_EXIT=$?"
    sleep 4
    echo AFTER_73
    date -Ins
    app_launcher -r AppC 2>&1 || true
    pgrep -a -x ServiceH 2>&1 || true
    dlogutil -v time -d 2>&1 | grep -Ei 'ServiceK|CH_LIST|Keycode|vk_send' | tail -30 || true
    echo SEND_182
    date -Ins
    vk_send 182 2>&1
    echo "VK182_EXIT=$?"
    sleep 4
    echo AFTER_182
    date -Ins
    app_launcher -r AppC 2>&1 || true
    pgrep -a -x ServiceH 2>&1 || true
    dlogutil -v time -d 2>&1 | grep -Ei 'ServiceK|CH_LIST|Keycode|vk_send' | tail -30 || true
} >"$log" 2>&1
echo VK_PREFLIGHT_DONE
