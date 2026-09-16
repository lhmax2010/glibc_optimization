# 逐条连接诊断原文（脱敏公开副本）

仅端点、host 路径与既有别名脱敏；空 stdout/stderr 单独标明，不补写为成功。

## ping

`ping -n -c 4 -W 2 '<PRODUCT_BOARD_IP>'`

2026-09-16T14:26:04.164264+00:00 → 2026-09-16T14:26:07.247548+00:00; host RC=0

stdout:

```text
PING <PRODUCT_BOARD_IP> (<PRODUCT_BOARD_IP>) 56(84) bytes of data.
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=1 ttl=63 time=0.400 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=2 ttl=63 time=0.725 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=3 ttl=63 time=1.47 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=4 ttl=63 time=0.557 ms

--- <PRODUCT_BOARD_IP> ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3078ms
rtt min/avg/max/mdev = 0.400/0.786/1.465/0.408 ms
```

stderr: 空（0 bytes）。

## tcp_26101

`python/socket '<PRODUCT_BOARD_IP>' 26101 connect-only`

2026-09-16T14:26:07.247741+00:00 → 2026-09-16T14:26:07.259546+00:00; host RC=1

stdout:

```text
{
  "address": "<PRODUCT_BOARD_IP>",
  "port": 26101,
  "sent_bytes": 0,
  "error_type": "ConnectionRefusedError",
  "error": "[Errno 111] Connection refused",
  "errno": 111,
  "tcp_connected": false,
  "elapsed_seconds": 0.011304451152682304
}
```

stderr: 空（0 bytes）。

## tcp_22

`python/socket '<PRODUCT_BOARD_IP>' 22 connect-only`

2026-09-16T14:26:07.259684+00:00 → 2026-09-16T14:26:07.260797+00:00; host RC=0

stdout:

```text
{
  "address": "<PRODUCT_BOARD_IP>",
  "port": 22,
  "sent_bytes": 0,
  "tcp_connected": true,
  "receive": "not requested",
  "elapsed_seconds": 0.0007515139877796173
}
```

stderr: 空（0 bytes）。

## tcp_local_26099_before

`python/socket 127.0.0.1 26099 connect-only`

2026-09-16T14:26:07.260898+00:00 → 2026-09-16T14:26:07.261345+00:00; host RC=0

stdout:

```text
{
  "address": "127.0.0.1",
  "port": 26099,
  "sent_bytes": 0,
  "tcp_connected": true,
  "receive": "not requested",
  "elapsed_seconds": 0.00011516199447214603
}
```

stderr: 空（0 bytes）。

## arp

`ip neigh show to '<PRODUCT_BOARD_IP>'`

2026-09-16T14:26:07.261439+00:00 → 2026-09-16T14:26:07.266452+00:00; host RC=0

stdout: 空（0 bytes）。

stderr: 空（0 bytes）。

## sdb_version

`sdb version`

2026-09-16T14:26:07.266554+00:00 → 2026-09-16T14:26:07.270117+00:00; host RC=0

stdout:

```text
Smart Development Bridge version 4.2.25
```

stderr: 空（0 bytes）。

## local_listener_before

`ss -ltnp 'sport = :26099'`

2026-09-16T14:26:07.270232+00:00 → 2026-09-16T14:26:07.298476+00:00; host RC=0

stdout:

```text
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      4            0.0.0.0:26099      0.0.0.0:*    users:(("sdb",pid=1949533,fd=5))
```

stderr: 空（0 bytes）。

## local_sdb_before

`pgrep -a -x sdb`

2026-09-16T14:26:07.298603+00:00 → 2026-09-16T14:26:07.315420+00:00; host RC=0

stdout:

```text
1949533 sdb fork-server server --only-detect-tizen
```

stderr: 空（0 bytes）。

## sdb_kill_server

`sdb kill-server`

2026-09-16T14:26:07.315570+00:00 → 2026-09-16T14:26:07.318312+00:00; host RC=0

stdout: 空（0 bytes）。

stderr: 空（0 bytes）。

## sdb_start_server

`sdb start-server`

2026-09-16T14:26:07.318450+00:00 → 2026-09-16T14:26:07.339465+00:00; host RC=0

stdout: 空（0 bytes）。

stderr:

```text
error: protocol fault: no status
```

## local_listener_after

`ss -ltnp 'sport = :26099'`

2026-09-16T14:26:07.339607+00:00 → 2026-09-16T14:26:07.364704+00:00; host RC=0

stdout:

```text
State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
```

stderr: 空（0 bytes）。

## local_sdb_after

`pgrep -a -x sdb`

2026-09-16T14:26:07.364828+00:00 → 2026-09-16T14:26:07.381629+00:00; host RC=1

stdout: 空（0 bytes）。

stderr: 空（0 bytes）。

## tcp_local_26099_after

`python/socket 127.0.0.1 26099 connect-only`

2026-09-16T14:26:07.381737+00:00 → 2026-09-16T14:26:07.382103+00:00; host RC=1

stdout:

```text
{
  "address": "127.0.0.1",
  "port": 26099,
  "sent_bytes": 0,
  "error_type": "ConnectionRefusedError",
  "error": "[Errno 111] Connection refused",
  "errno": 111,
  "tcp_connected": false,
  "elapsed_seconds": 0.00011237198486924171
}
```

stderr: 空（0 bytes）。

## sdb_connect_default

`sdb connect '<PRODUCT_BOARD_IP>'`

2026-09-16T14:26:07.382171+00:00 → 2026-09-16T14:26:10.388678+00:00; host RC=0

stdout:

```text
* Server is not running. Start it now on port 26099 *
* Server has started successfully *
error: failed to connect to remote target '<PRODUCT_BOARD_IP>'
```

stderr: 空（0 bytes）。

## sdb_devices

`sdb devices`

2026-09-16T14:26:10.388849+00:00 → 2026-09-16T14:26:10.394325+00:00; host RC=0

stdout:

```text
List of devices attached 
```

stderr: 空（0 bytes）。

## sdb_connect_explicit

`sdb connect '<PRODUCT_BOARD_IP>:26101'`

2026-09-16T14:26:10.394486+00:00 → 2026-09-16T14:26:10.400116+00:00; host RC=0

stdout:

```text
error: failed to connect to remote target '<PRODUCT_BOARD_IP>'
```

stderr: 空（0 bytes）。

## ssh_uname_a

`ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=5 -o ConnectionAttempts=1 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o UpdateHostKeys=no -o ControlMaster=no 'root@<PRODUCT_BOARD_IP>' 'uname -a'`

2026-09-16T14:26:10.400219+00:00 → 2026-09-16T14:26:10.729421+00:00; host RC=255

stdout: 空（0 bytes）。

stderr:

```text
Warning: Permanently added '<PRODUCT_BOARD_IP>' (ED25519) to the list of known hosts.
root@<PRODUCT_BOARD_IP>: Permission denied (publickey,keyboard-interactive).
```

## route_to_target

`ip route get '<PRODUCT_BOARD_IP>'`

2026-09-16T14:27:00.969094+00:00 → 2026-09-16T14:27:00.972502+00:00; host RC=0

stdout:

```text
<PRODUCT_BOARD_IP> via <INTERNAL_ENDPOINT> dev enp128s31f6 src <INTERNAL_ENDPOINT> uid 1000 
    cache 
```

stderr: 空（0 bytes）。

## local_listener_final

`ss -ltnp 'sport = :26099'`

2026-09-16T14:27:00.972662+00:00 → 2026-09-16T14:27:00.997352+00:00; host RC=0

stdout:

```text
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      4            0.0.0.0:26099      0.0.0.0:*    users:(("sdb",pid=1960524,fd=5))
```

stderr: 空（0 bytes）。

## local_sdb_final

`pgrep -a -x sdb`

2026-09-16T14:27:00.997486+00:00 → 2026-09-16T14:27:01.011781+00:00; host RC=0

stdout:

```text
1960524 sdb fork-server server --only-detect-tizen
```

stderr: 空（0 bytes）。

## sdb_executable

`readlink -f '<USER_HOME>/.local/bin/sdb'`

2026-09-16T14:27:01.011905+00:00 → 2026-09-16T14:27:01.013520+00:00; host RC=0

stdout:

```text
<USER_HOME>/tizen-studio/tools/sdb
```

stderr: 空（0 bytes）。
