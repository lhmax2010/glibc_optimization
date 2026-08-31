#!/bin/sh
set -u

out=/root/chromium_url_entry/results/b2_domain_probe
mkdir -p "$out"

kernel=$(uname -r)
arch=$(uname -m)
case "$kernel" in *rpi4*) ;; *) echo "ABORT: not rpi4, kernel=$kernel" >&2; exit 97;; esac
case "$arch" in armv7l|armv7*) ;; *) echo "ABORT: not armv7l, arch=$arch" >&2; exit 96;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image" >&2
    exit 98
fi

runuser -u '<USER>' -g users -G display -- /bin/sh -c '
  id
  printf "attr_current="; cat /proc/self/attr/current
  printf "shm_write="
  if : > /dev/shm/chromium_url_entry_runuser_probe; then
    echo PASS
    rm -f /dev/shm/chromium_url_entry_runuser_probe
  else
    echo FAIL
  fi
' >"$out/runuser.txt" 2>&1
echo "RUNUSER_EXIT=$?" >>"$out/runuser.txt"

systemd-run --wait --pipe --collect --unit=chromium-url-entry-label-probe \
  --uid='<USER>' --gid=users -p SupplementaryGroups=display \
  -E XDG_RUNTIME_DIR=/run/user/5001 -E WAYLAND_DISPLAY=wayland-0 \
  /bin/sh -c '
    id
    printf "attr_current="; cat /proc/self/attr/current
    printf "shm_write="
    if : > /dev/shm/chromium_url_entry_systemd_probe; then
      echo PASS
      rm -f /dev/shm/chromium_url_entry_systemd_probe
    else
      echo FAIL
    fi
  ' >"$out/systemd_run.txt" 2>&1
echo "SYSTEMD_RUN_EXIT=$?" >>"$out/systemd_run.txt"

systemctl status chromium-url-entry-label-probe >"$out/unit_after.txt" 2>&1 || true
ls -l /dev/shm/chromium_url_entry_*_probe >"$out/shm_leftovers.txt" 2>&1 || true
echo B2_DOMAIN_PROBE_DONE
