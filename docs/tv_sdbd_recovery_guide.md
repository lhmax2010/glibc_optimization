> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# TV sdbd Recovery Guide

## Scope

This guide documents the SDB recovery performed on the TV image at `<PRODUCT_BOARD_IP>` on 2026-07-10 Asia/Shanghai. It is intended for developers who can SSH to the TV as `root`.

Known access used during recovery:

```sh
ssh root@<PRODUCT_BOARD_IP>
# password: <REDACTED>
```

## Symptoms

From the host:

```sh
sdb connect <PRODUCT_BOARD_IP>
# error: failed to connect to remote target '<PRODUCT_BOARD_IP>'

sdb devices
# List of devices attached
```

Network checks showed the board was reachable, but SDB was not usable:

```sh
ping <PRODUCT_BOARD_IP>       # OK
/dev/tcp/<PRODUCT_BOARD_IP>/22    # open
/dev/tcp/<PRODUCT_BOARD_IP>/26101 # initially refused, later failed after socket start-limit
```

## Root Cause

Two conditions caused the failure:

1. TV developer-mode vconf gates were disabled:

```text
db/sdk/develop/mode = 0
db/sdk/develop/ip   = 0.0.0.0
```

The TV `libsdbd_plugin.so` contains the launch/IP gate strings `db/sdk/develop/mode`, `db/sdk/develop/ip`, `verify sdbd launch`, and `Verifying ip to connect`. With developer mode disabled or the wrong host IP, `sdbd` does not accept the host.

2. A local service override had been tried and was incompatible with the socket unit:

```text
/etc/systemd/system/sdbd.service.d/fix-type.conf
```

One attempted form used direct listening:

```ini
[Service]
Type=simple
User=
Group=
SmackProcessLabel=
ExecStart=
ExecStart=/usr/sbin/sdbd -l 26101
```

That fails because this TV `sdbd-3.0.50` rejects short `-l` even though help mentions it:

```text
/usr/sbin/sdbd: invalid option -- 'l'
```

Also, direct `--listen-port=26101` did not leave a running listener in this image. The working path is the stock systemd socket-activation path plus the correct developer-mode vconf values.

## One-Time Fix Applied

Run on the TV over SSH as root.

### 1. Back up current SDB service state

```sh
STAMP=$(date +%Y%m%d_%H%M%S)
BK=/root/sdbd_repair_$STAMP
mkdir -p "$BK"
systemctl cat sdbd.service sdbd_tcp.socket > "$BK/before-systemctl-cat.txt" 2>&1 || true
systemctl status sdbd.service sdbd_tcp.socket -l --no-pager > "$BK/before-status.txt" 2>&1 || true
vconftool get db/sdk/develop/mode > "$BK/before-vconf-mode.txt" 2>&1 || true
vconftool get db/sdk/develop/ip > "$BK/before-vconf-ip.txt" 2>&1 || true
```

### 2. Remove local broken service override, if present

Keep a copy, but make systemd ignore it. Only files ending in `.conf` are loaded as drop-ins.

```sh
if [ -f /etc/systemd/system/sdbd.service.d/fix-type.conf ]; then
    cp -a /etc/systemd/system/sdbd.service.d/fix-type.conf "$BK/fix-type.conf.before"
    mv /etc/systemd/system/sdbd.service.d/fix-type.conf \
       /etc/systemd/system/sdbd.service.d/fix-type.conf.disabled
fi
```

The expected effective service after this step should be the stock unit plus `restart-on-fail.conf`, not `fix-type.conf`.

### 3. Enable TV developer-mode vconf for the host IP

Use the host IP as seen by the TV network. In this recovery, the host route source was `<HOST_IP>`.

On the host, find the source IP if needed:

```sh
ip route get <PRODUCT_BOARD_IP>
# ... src <HOST_IP> ...
```

On the TV:

```sh
vconftool set -f -t int db/sdk/develop/mode 1
vconftool set -f -t string db/sdk/develop/ip <HOST_IP>
```

Verify:

```sh
vconftool get db/sdk/develop/mode
vconftool get db/sdk/develop/ip
```

Expected:

```text
db/sdk/develop/mode, value = 1 (Int32)
db/sdk/develop/ip, value = <HOST_IP> (String)
```

### 4. Reset failed state and start the SDB TCP socket

```sh
systemctl daemon-reload
systemctl reset-failed sdbd.service sdbd_tcp.socket || true
systemctl stop sdbd.service sdbd_tcp.socket || true
systemctl start sdbd_tcp.socket
```

Before a host connects, expected status is:

```text
sdbd_tcp.socket: active (listening), Listen: [::]:26101
sdbd.service: inactive (dead), TriggeredBy: sdbd_tcp.socket
```

### 5. Connect from the host

```sh
sdb kill-server
sdb start-server
sdb connect <PRODUCT_BOARD_IP>
sdb devices
```

Expected:

```text
connecting to <PRODUCT_BOARD_IP>:26101 ...
connected to <PRODUCT_BOARD_IP>:26101

List of devices attached
<PRODUCT_BOARD_IP>:26101    device    0
```

### 6. Verify root and shell

```sh
sdb root on
sdb shell id
```

Expected from this TV image:

```text
Switched to 'root' account mode
uid=0(root) gid=0(root) ... context="User::Shell"
```

### 7. Verify service state after connection

```sh
sdb shell 'systemctl status sdbd.service sdbd_tcp.socket -l --no-pager'
```

Expected:

```text
sdbd.service: active (running)
Main PID: ... (sdbd)
CGroup: /system.slice/sdbd.service
        ... /usr/sbin/sdbd

sdbd_tcp.socket: active (running)
Listen: [::]:26101 (Stream)
```

## Current Verified State After Repair

Host-side verification:

```text
List of devices attached 
<PRODUCT_BOARD_IP>:26101	device    	0

Switched to 'root' account mode
uid=0(root) gid=0(root) ... context="User::Shell"
```

TV-side verification:

```text
db/sdk/develop/mode, value = 1 (Int32)
db/sdk/develop/ip, value = <HOST_IP> (String)

sdbd.service - sdbd
Active: active (running)
Main PID: 2630 (sdbd)

sdbd_tcp.socket - sdbd: TCP socket
Active: active (running)
Listen: [::]:26101 (Stream)
```

Effective unit after repair:

```ini
# /usr/lib/systemd/system/sdbd.service
[Service]
User=sdk
Group=sdk
SmackProcessLabel=System
EnvironmentFile=-/run/sdbd-env
Type=notify
ExecStart=/usr/sbin/sdbd $SDBD_CMDLINE

# /usr/lib/systemd/system/sdbd.service.d/restart-on-fail.conf
[Service]
RemainAfterExit=no
Restart=on-failure

# /usr/lib/systemd/system/sdbd_tcp.socket
[Socket]
ListenStream=26101
Service=sdbd.service
```

## Rollback

If this repair must be reverted:

```sh
# On TV
vconftool set -f -t int db/sdk/develop/mode 0
vconftool set -f -t string db/sdk/develop/ip 0.0.0.0

# Restore the previous local override if needed.
# Replace <backup-dir> with the backup printed during repair, for example:
# /root/sdbd_repair_20260709_235100
if [ -f <backup-dir>/fix-type.conf.before ]; then
    mkdir -p /etc/systemd/system/sdbd.service.d
    cp -a <backup-dir>/fix-type.conf.before /etc/systemd/system/sdbd.service.d/fix-type.conf
fi

systemctl daemon-reload
systemctl reset-failed sdbd.service sdbd_tcp.socket || true
systemctl stop sdbd.service sdbd_tcp.socket || true
```

## Troubleshooting Checklist

Use this order; it separates host networking, TV developer-mode gating, and systemd service failures.

### Host side

```sh
command -v sdb
sdb version
ping -c 2 <PRODUCT_BOARD_IP>
sdb kill-server
sdb start-server
sdb connect <PRODUCT_BOARD_IP>
sdb devices
```

Port check:

```sh
for p in 22 26101; do
  timeout 2 bash -c "</dev/tcp/<PRODUCT_BOARD_IP>/$p" >/dev/null 2>&1
  echo "$p rc=$?"
done
```

Interpretation:

- `22 open`, `26101 refused`: TV network is alive, SDB socket is not listening.
- `26101 open`, but `sdb connect` fails: socket may be listening, but `sdbd.service` fails when triggered or developer-mode IP check rejects the host.
- `sdb devices` shows `device`: transport is working.

### TV side

```sh
systemctl status sdbd.service sdbd_tcp.socket -l --no-pager
systemctl cat sdbd.service sdbd_tcp.socket
vconftool get db/sdk/develop/mode
vconftool get db/sdk/develop/ip
ps -ef | grep '[s]dbd'
```

Known bad states:

```text
db/sdk/develop/mode, value = 0
db/sdk/develop/ip, value = 0.0.0.0
```

```text
sdbd.service: failed (Result: protocol)
sdbd_tcp.socket: failed (Result: service-start-limit-hit)
```

```text
/etc/systemd/system/sdbd.service.d/fix-type.conf overrides ExecStart to /usr/sbin/sdbd -l 26101
```

Known good state:

```text
db/sdk/develop/mode, value = 1
db/sdk/develop/ip, value = <host source IP>
sdbd_tcp.socket: active (listening/running)
sdbd.service: active (running) after host connects
```

## Notes

- Do not use `/usr/sbin/sdbd -l 26101` on this TV image. Although help lists `-l`, the binary rejects the short option.
- Direct `/usr/sbin/sdbd --listen-port=26101` did not leave a running listener during this recovery.
- The working path is stock systemd socket activation plus correct `db/sdk/develop/*` vconf values.
- The local host source IP matters. If the developer machine IP changes, update `db/sdk/develop/ip` accordingly.
- Backups from this repair were left under `/root/sdbd_repair_*` on the TV for audit/rollback.
