> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Tizen glibc 内存优化 Batch 1 A/B 实验执行报告

## 1. 头部

- 日期：2026-07-08（主机时区 Asia/Shanghai）
- 执行窗口：[2026-07-08T18:53:20+08:00] Batch1 AB start -> [2026-07-08T19:45:32+08:00] Batch1 AB complete
- Board IP：<TEST_BOARD_IP>
- sdb：`<USER_HOME>/tizen-studio/tools/sdb`
- sdb version：
```text
Smart Development Bridge version 4.2.25
```
- root：已获得
```text
uid=0(root) gid=0(root) groups=0(root),29(audio),44(video),201(display),1901(log),6505(pulse-access),6506(pulse-rt),6525(usb_device),10001(priv_externalstorage),10013(priv_tee_client),10014(priv_peripheralio),10212(priv_platform),10501(priv_camera),10502(priv_mediastorage),10503(priv_recorder),10704(priv_internet),10705(priv_network_get),10711(priv_tethering_admin),10901(priv_email),10903(priv_message_read),11103(priv_mapservice),11201(priv_appdebugging) context="User::Shell"
```
- device：
```text
List of devices attached 
<TEST_BOARD_IP>:26101	device    	rpi4
```
- os-release：
```text
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=<TEST_IMAGE_C>
```
- uname：
```text
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Fri Jul  3 10:06:01 UTC 2026 armv7l GNU/Linux
```

### 动过的 unit 清单

| 矩阵 service | systemd unit | 状态 |
| --- | --- | --- |
| ServiceR | ServiceR.service | touched |
| ServiceS | central-ServiceS.service | touched |
| pass | pass.service | touched |
| pulseaudio | pulseaudio.service | touched |
| ServiceV | ac.service | touched; verified by MainPID/ExecStart/cgroup |

完整命令流水见 `board_results/batch1/host_run.log`。unit 映射原文见 `board_results/batch1/unit_mapping.log`。

## 2. 噪声带表

| service | unit | 样本数 | 9 个 Rss 样本(kB) | Rss 极差(kB) |
| --- | --- | --- | --- | --- |
| ServiceR | ServiceR.service | 9 | 8408,8408,8408,8408,8408,8408,8404,8404,8404 | 4 |
| ServiceS | central-ServiceS.service | 9 | 9036,9036,9036,9028,9028,9028,9036,9036,9036 | 8 |
| pass | pass.service | 9 | 5148,5148,5148,5240,5240,5240,5204,5204,5204 | 92 |
| pulseaudio | pulseaudio.service | 9 | 7116,7116,7116,7116,7116,7116,7116,7116,7116 | 0 |
| ServiceV | ac.service | 9 | 10352,10352,10352,10424,10424,10424,10424,10424,10424 | 72 |

## 3. 主数据表

| service | 格 | 新 pid | E1 | Rss 中位数(kB) | Pss 中位数(kB) | 相对 C0 差值 | E2 arena 近似计数 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ServiceR | C0 | 16150 | ABSENT | 8404 | 3589 | Rss +0 / Pss +0 | 2 | ok |
| ServiceR | C1 | 18245 | PASS | 8404 | 3589 | Rss +0 / Pss +0 | 2 | ok |
| ServiceR | C2 | 20354 | PASS | 8368 | 3556 | Rss -36 / Pss -33 | 0 | ok |
| ServiceR | C3 | 22447 | PASS | 8372 | 3560 | Rss -32 / Pss -29 | 0 | ok |
| ServiceS | C0 | 24541 | ABSENT | 9036 | 4604 | Rss +0 / Pss +0 | 2 | ok |
| ServiceS | C1 | 26632 | PASS | 9028 | 4596 | Rss -8 / Pss -8 | 1 | ok |
| ServiceS | C2 | 28722 | PASS | 9000 | 4575 | Rss -36 / Pss -29 | 0 | ok |
| ServiceS | C3 | 30820 | PASS | 9000 | 4575 | Rss -36 / Pss -29 | 0 | ok |
| pass | C0 | 511 | ABSENT | 5204 | 2487 | Rss +0 / Pss +0 | 3 | ok |
| pass | C1 | 2714 | PASS | 5232 | 2532 | Rss +28 / Pss +45 | 3 | ok |
| pass | C2 | 4812 | PASS | 5216 | 2516 | Rss +12 / Pss +29 | 0 | ok |
| pass | C3 | 6909 | PASS | 5228 | 2538 | Rss +24 / Pss +51 | 0 | ok |
| pulseaudio | C0 | 9011 | ABSENT | 7116 | 4592 | Rss +0 / Pss +0 | 1 | perf_sentinel=perf_sentinel.txt |
| pulseaudio | C1 | 11114 | PASS | 7116 | 4592 | Rss +0 / Pss +0 | 1 | perf_sentinel=perf_sentinel.txt |
| pulseaudio | C2 | 13226 | PASS | 7084 | 4560 | Rss -32 / Pss -32 | 0 | perf_sentinel=perf_sentinel.txt |
| pulseaudio | C3 | 15342 | PASS | 7088 | 4564 | Rss -28 / Pss -28 | 1 | perf_sentinel=perf_sentinel.txt |
| ServiceV | C0 | 17445 | ABSENT | 10424 | 5284 | Rss +0 / Pss +0 | 1 | ok |
| ServiceV | C3 | 19578 | PASS | 10424 | 5284 | Rss +0 / Pss +0 | 1 | ok |

## 4. 阴性对照：ServiceV 原始证据

### E1 原始证据

ServiceV/C0 `/proc/<pid>/environ` 中 GLIBC_TUNABLES 行：
```text
<no GLIBC_TUNABLES>
```

ServiceV/C3 `/proc/<pid>/environ` 中 GLIBC_TUNABLES 行：
```text
GLIBC_TUNABLES=glibc.pthread.stack_cache_size=1048576:glibc.malloc.arena_max=2
```

### E3 原始组件

| service | 格 | pid | E1 | Rss 中位数(kB) | Pss 中位数(kB) | arena | 目录 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ServiceV | C0 | 17445 | ABSENT | 10424 | 5284 | 1 | board_results/batch1/ServiceV/C0 |
| ServiceV | C3 | 19578 | PASS | 10424 | 5284 | 1 | board_results/batch1/ServiceV/C3 |

- ServiceV 9 个噪声 Rss 样本(kB)：10352,10352,10352,10424,10424,10424,10424,10424,10424
- ServiceV 噪声 Rss 极差(kB)：72
- ServiceV C3 相对 C0：Rss +0 kB / Pss +0 kB
- 原始文件：`board_results/batch1/ServiceV/C0/`, `board_results/batch1/ServiceV/C3/`, `board_results/batch1/ServiceV/C0_noise/`
- 复扫 TSV 中 ServiceV 行：
```text
22084	ServiceV	elf32	1	301	15	10420	5276	-	/usr/bin/ServiceV
```

## 5. pulseaudio 性能哨兵原始计数

| service | 格 | pactl rc | elapsed_s | xrun journal lines | 文件 |
| --- | --- | --- | --- | --- | --- |
| pulseaudio | C0 | 0 | 0 | 0 | board_results/batch1/pulseaudio/C0/perf_sentinel.txt |
| pulseaudio | C1 | 0 | 0 | 0 | board_results/batch1/pulseaudio/C1/perf_sentinel.txt |
| pulseaudio | C2 | 0 | 0 | 0 | board_results/batch1/pulseaudio/C2/perf_sentinel.txt |
| pulseaudio | C3 | 0 | 0 | 0 | board_results/batch1/pulseaudio/C3/perf_sentinel.txt |

## 6. 异常记录

```text
[2026-07-08T18:53:21+08:00] skip AppV: no dedicated service from list-units grep; /proc/751/cgroup shows ServiceJ/user@5001, not a targetable per-app unit
```

restart 演练文件：
```text
board_results/batch1/ServiceV/rehearsal.txt
board_results/batch1/ServiceS/rehearsal.txt
board_results/batch1/pass/rehearsal.txt
board_results/batch1/pulseaudio/rehearsal.txt
board_results/batch1/ServiceR/rehearsal.txt
```

## 7. 恢复现场证据

### drop-in 删除与服务 active

```text
RESTORE_DATE=2026-07-08T19:45:09+08:00
--- cleanup ServiceR.service ---
--- cleanup central-ServiceS.service ---
--- cleanup pass.service ---
--- cleanup pulseaudio.service ---
--- cleanup ac.service ---
--- restart ServiceR.service ---
RESTART_RC=0
active
21772
--- restart central-ServiceS.service ---
RESTART_RC=0
active
21853
--- restart pass.service ---
RESTART_RC=0
active
21942
--- restart pulseaudio.service ---
RESTART_RC=0
active
22014
--- restart ac.service ---
RESTART_RC=0
active
22084
--- dropin check ---
ABSENT:/etc/systemd/system/ServiceR.service.d/memopt.conf
ABSENT:/etc/systemd/system/central-ServiceS.service.d/memopt.conf
ABSENT:/etc/systemd/system/pass.service.d/memopt.conf
ABSENT:/etc/systemd/system/pulseaudio.service.d/memopt.conf
ABSENT:/etc/systemd/system/ac.service.d/memopt.conf
--- active check ---
ServiceR.service active
central-ServiceS.service active
pass.service active
pulseaudio.service active
ac.service active
```

### inventory 复扫摘要

```text
/tmp/tizen_memopt_inventory.sh: line 49: /proc/22238/cmdline: No such file or directory
/tmp/tizen_memopt_inventory.sh: line 49: /proc/22239/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=52  AT_SECURE=1: 11  AT_SECURE=0: 41  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

### /tmp 清理后列表

```text
total 8
-rw-r--r-- 1 location  location 28 Jan  1  1970 dump_gps.log
drwxrwxrwx 2 <USER>    users    80 Jan  1  1970 focus
prw-rw-rw- 1 pulse     pulse     0 Jan  1  1970 keytone
drwxrwxrwt 2 root      users    40 Jan  1  1970 pkgmgr
-rw-r--r-- 1 root      root      0 Jan  1  1970 rsc_mgr_ready
-rw-r----- 1 root      root      0 Jan  1  1970 sm-cleanup-tmp-flag
drwx------ 3 root      root     60 Jan  1  1970 systemd-private-b2a783b8ff4443e3a14b4e722dc1dd0e-systemd-logind.service-g4fihM
-rw-rw-r-- 1 system_fw users     8 Jan  1  1970 ttrace_tag
```

复扫 TSV：`board_results/batch1/restore_inventory.tsv`

## 8. 原始采样文件路径

### smaps_rollup run*.txt

```text
board_results/batch1/ServiceV/C0/run1.txt
board_results/batch1/ServiceV/C0/run2.txt
board_results/batch1/ServiceV/C0/run3.txt
board_results/batch1/ServiceV/C0_noise/run1.txt
board_results/batch1/ServiceV/C0_noise/run2.txt
board_results/batch1/ServiceV/C0_noise/run3.txt
board_results/batch1/ServiceV/C0_noise/run4.txt
board_results/batch1/ServiceV/C0_noise/run5.txt
board_results/batch1/ServiceV/C0_noise/run6.txt
board_results/batch1/ServiceV/C0_noise/run7.txt
board_results/batch1/ServiceV/C0_noise/run8.txt
board_results/batch1/ServiceV/C0_noise/run9.txt
board_results/batch1/ServiceV/C3/run1.txt
board_results/batch1/ServiceV/C3/run2.txt
board_results/batch1/ServiceV/C3/run3.txt
board_results/batch1/ServiceS/C0/run1.txt
board_results/batch1/ServiceS/C0/run2.txt
board_results/batch1/ServiceS/C0/run3.txt
board_results/batch1/ServiceS/C0_noise/run1.txt
board_results/batch1/ServiceS/C0_noise/run2.txt
board_results/batch1/ServiceS/C0_noise/run3.txt
board_results/batch1/ServiceS/C0_noise/run4.txt
board_results/batch1/ServiceS/C0_noise/run5.txt
board_results/batch1/ServiceS/C0_noise/run6.txt
board_results/batch1/ServiceS/C0_noise/run7.txt
board_results/batch1/ServiceS/C0_noise/run8.txt
board_results/batch1/ServiceS/C0_noise/run9.txt
board_results/batch1/ServiceS/C1/run1.txt
board_results/batch1/ServiceS/C1/run2.txt
board_results/batch1/ServiceS/C1/run3.txt
board_results/batch1/ServiceS/C2/run1.txt
board_results/batch1/ServiceS/C2/run2.txt
board_results/batch1/ServiceS/C2/run3.txt
board_results/batch1/ServiceS/C3/run1.txt
board_results/batch1/ServiceS/C3/run2.txt
board_results/batch1/ServiceS/C3/run3.txt
board_results/batch1/pass/C0/run1.txt
board_results/batch1/pass/C0/run2.txt
board_results/batch1/pass/C0/run3.txt
board_results/batch1/pass/C0_noise/run1.txt
board_results/batch1/pass/C0_noise/run2.txt
board_results/batch1/pass/C0_noise/run3.txt
board_results/batch1/pass/C0_noise/run4.txt
board_results/batch1/pass/C0_noise/run5.txt
board_results/batch1/pass/C0_noise/run6.txt
board_results/batch1/pass/C0_noise/run7.txt
board_results/batch1/pass/C0_noise/run8.txt
board_results/batch1/pass/C0_noise/run9.txt
board_results/batch1/pass/C1/run1.txt
board_results/batch1/pass/C1/run2.txt
board_results/batch1/pass/C1/run3.txt
board_results/batch1/pass/C2/run1.txt
board_results/batch1/pass/C2/run2.txt
board_results/batch1/pass/C2/run3.txt
board_results/batch1/pass/C3/run1.txt
board_results/batch1/pass/C3/run2.txt
board_results/batch1/pass/C3/run3.txt
board_results/batch1/pulseaudio/C0/run1.txt
board_results/batch1/pulseaudio/C0/run2.txt
board_results/batch1/pulseaudio/C0/run3.txt
board_results/batch1/pulseaudio/C0_noise/run1.txt
board_results/batch1/pulseaudio/C0_noise/run2.txt
board_results/batch1/pulseaudio/C0_noise/run3.txt
board_results/batch1/pulseaudio/C0_noise/run4.txt
board_results/batch1/pulseaudio/C0_noise/run5.txt
board_results/batch1/pulseaudio/C0_noise/run6.txt
board_results/batch1/pulseaudio/C0_noise/run7.txt
board_results/batch1/pulseaudio/C0_noise/run8.txt
board_results/batch1/pulseaudio/C0_noise/run9.txt
board_results/batch1/pulseaudio/C1/run1.txt
board_results/batch1/pulseaudio/C1/run2.txt
board_results/batch1/pulseaudio/C1/run3.txt
board_results/batch1/pulseaudio/C2/run1.txt
board_results/batch1/pulseaudio/C2/run2.txt
board_results/batch1/pulseaudio/C2/run3.txt
board_results/batch1/pulseaudio/C3/run1.txt
board_results/batch1/pulseaudio/C3/run2.txt
board_results/batch1/pulseaudio/C3/run3.txt
board_results/batch1/ServiceR/C0/run1.txt
board_results/batch1/ServiceR/C0/run2.txt
board_results/batch1/ServiceR/C0/run3.txt
board_results/batch1/ServiceR/C0_noise/run1.txt
board_results/batch1/ServiceR/C0_noise/run2.txt
board_results/batch1/ServiceR/C0_noise/run3.txt
board_results/batch1/ServiceR/C0_noise/run4.txt
board_results/batch1/ServiceR/C0_noise/run5.txt
board_results/batch1/ServiceR/C0_noise/run6.txt
board_results/batch1/ServiceR/C0_noise/run7.txt
board_results/batch1/ServiceR/C0_noise/run8.txt
board_results/batch1/ServiceR/C0_noise/run9.txt
board_results/batch1/ServiceR/C1/run1.txt
board_results/batch1/ServiceR/C1/run2.txt
board_results/batch1/ServiceR/C1/run3.txt
board_results/batch1/ServiceR/C2/run1.txt
board_results/batch1/ServiceR/C2/run2.txt
board_results/batch1/ServiceR/C2/run3.txt
board_results/batch1/ServiceR/C3/run1.txt
board_results/batch1/ServiceR/C3/run2.txt
board_results/batch1/ServiceR/C3/run3.txt
```

### 辅助原始文件

```text
board_results/batch1/ServiceV/C0/apply.txt
board_results/batch1/ServiceV/C0/e1_environ.raw
board_results/batch1/ServiceV/C0/e1_environ.txt
board_results/batch1/ServiceV/C0/maps.txt
board_results/batch1/ServiceV/C0_noise/restart_round1.txt
board_results/batch1/ServiceV/C0_noise/restart_round2.txt
board_results/batch1/ServiceV/C0_noise/restart_round3.txt
board_results/batch1/ServiceV/C3/apply.txt
board_results/batch1/ServiceV/C3/e1_environ.raw
board_results/batch1/ServiceV/C3/e1_environ.txt
board_results/batch1/ServiceV/C3/maps.txt
board_results/batch1/ServiceV/rehearsal.txt
board_results/batch1/ServiceS/C0/apply.txt
board_results/batch1/ServiceS/C0/e1_environ.raw
board_results/batch1/ServiceS/C0/e1_environ.txt
board_results/batch1/ServiceS/C0/maps.txt
board_results/batch1/ServiceS/C0_noise/restart_round1.txt
board_results/batch1/ServiceS/C0_noise/restart_round2.txt
board_results/batch1/ServiceS/C0_noise/restart_round3.txt
board_results/batch1/ServiceS/C1/apply.txt
board_results/batch1/ServiceS/C1/e1_environ.raw
board_results/batch1/ServiceS/C1/e1_environ.txt
board_results/batch1/ServiceS/C1/maps.txt
board_results/batch1/ServiceS/C2/apply.txt
board_results/batch1/ServiceS/C2/e1_environ.raw
board_results/batch1/ServiceS/C2/e1_environ.txt
board_results/batch1/ServiceS/C2/maps.txt
board_results/batch1/ServiceS/C3/apply.txt
board_results/batch1/ServiceS/C3/e1_environ.raw
board_results/batch1/ServiceS/C3/e1_environ.txt
board_results/batch1/ServiceS/C3/maps.txt
board_results/batch1/ServiceS/rehearsal.txt
board_results/batch1/pass/C0/apply.txt
board_results/batch1/pass/C0/e1_environ.raw
board_results/batch1/pass/C0/e1_environ.txt
board_results/batch1/pass/C0/maps.txt
board_results/batch1/pass/C0_noise/restart_round1.txt
board_results/batch1/pass/C0_noise/restart_round2.txt
board_results/batch1/pass/C0_noise/restart_round3.txt
board_results/batch1/pass/C1/apply.txt
board_results/batch1/pass/C1/e1_environ.raw
board_results/batch1/pass/C1/e1_environ.txt
board_results/batch1/pass/C1/maps.txt
board_results/batch1/pass/C2/apply.txt
board_results/batch1/pass/C2/e1_environ.raw
board_results/batch1/pass/C2/e1_environ.txt
board_results/batch1/pass/C2/maps.txt
board_results/batch1/pass/C3/apply.txt
board_results/batch1/pass/C3/e1_environ.raw
board_results/batch1/pass/C3/e1_environ.txt
board_results/batch1/pass/C3/maps.txt
board_results/batch1/pass/rehearsal.txt
board_results/batch1/pulseaudio/C0/apply.txt
board_results/batch1/pulseaudio/C0/e1_environ.raw
board_results/batch1/pulseaudio/C0/e1_environ.txt
board_results/batch1/pulseaudio/C0/maps.txt
board_results/batch1/pulseaudio/C0/perf_sentinel.txt
board_results/batch1/pulseaudio/C0_noise/restart_round1.txt
board_results/batch1/pulseaudio/C0_noise/restart_round2.txt
board_results/batch1/pulseaudio/C0_noise/restart_round3.txt
board_results/batch1/pulseaudio/C1/apply.txt
board_results/batch1/pulseaudio/C1/e1_environ.raw
board_results/batch1/pulseaudio/C1/e1_environ.txt
board_results/batch1/pulseaudio/C1/maps.txt
board_results/batch1/pulseaudio/C1/perf_sentinel.txt
board_results/batch1/pulseaudio/C2/apply.txt
board_results/batch1/pulseaudio/C2/e1_environ.raw
board_results/batch1/pulseaudio/C2/e1_environ.txt
board_results/batch1/pulseaudio/C2/maps.txt
board_results/batch1/pulseaudio/C2/perf_sentinel.txt
board_results/batch1/pulseaudio/C3/apply.txt
board_results/batch1/pulseaudio/C3/e1_environ.raw
board_results/batch1/pulseaudio/C3/e1_environ.txt
board_results/batch1/pulseaudio/C3/maps.txt
board_results/batch1/pulseaudio/C3/perf_sentinel.txt
board_results/batch1/pulseaudio/rehearsal.txt
board_results/batch1/ServiceR/C0/apply.txt
board_results/batch1/ServiceR/C0/e1_environ.raw
board_results/batch1/ServiceR/C0/e1_environ.txt
board_results/batch1/ServiceR/C0/maps.txt
board_results/batch1/ServiceR/C0_noise/restart_round1.txt
board_results/batch1/ServiceR/C0_noise/restart_round2.txt
board_results/batch1/ServiceR/C0_noise/restart_round3.txt
board_results/batch1/ServiceR/C1/apply.txt
board_results/batch1/ServiceR/C1/e1_environ.raw
board_results/batch1/ServiceR/C1/e1_environ.txt
board_results/batch1/ServiceR/C1/maps.txt
board_results/batch1/ServiceR/C2/apply.txt
board_results/batch1/ServiceR/C2/e1_environ.raw
board_results/batch1/ServiceR/C2/e1_environ.txt
board_results/batch1/ServiceR/C2/maps.txt
board_results/batch1/ServiceR/C3/apply.txt
board_results/batch1/ServiceR/C3/e1_environ.raw
board_results/batch1/ServiceR/C3/e1_environ.txt
board_results/batch1/ServiceR/C3/maps.txt
board_results/batch1/ServiceR/rehearsal.txt
```
