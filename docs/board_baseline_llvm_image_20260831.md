# RPI4 LLVM 新镜像通道恢复与环境基线

- 采集日期：2026-08-31（host CST；板端 KST）
- 目标：恢复 RPI4 的 SDB 通道，建立新 LLVM unified 镜像基线，为后续 S2/S3 板上实验做准备
- 板地址：全文按既有映射记为 `<TEST_BOARD_IP>`；不以 IP 判板
- 执行边界：板端全程只读；未推送文件、未运行 `alloc_bench` 或其他负载、未安装/删除包、未修改配置、未执行 `sdb root on`，也未在板上创建临时文件
- 本机变更：仅按要求重启本机 SDB server，并在本地工作区新增本报告；采集完成时先本地保存，后经授权以 GitHub PR 供 PM review

## 1. 结论摘要

1. **通道恢复成功。** `<TEST_BOARD_IP>` 的 ICMP 与 TCP/26101 均可达；本机 26099 在操作前没有监听残留。`sdb kill-server` / `start-server` 后成功连接，结束复核时设备仍为 `device` 状态。
2. **三重身份门通过。** `uname -r` 为 `6.12.80-arm-rpi4-v7l`，包含 `rpi4`；`uname -m` 严格为 `armv7l`；系统为 Tizen 11 Unified，BUILD_ID 为 `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`。
3. **镜像来源符合预期但不是不可变快照证明。** `/etc/os-release` 没有 `LLVM` 字面字段；其 BUILD_ID 的 `tizen-unified-toolchain` 与 glibc RPM 的 `DISTRIBUTION=Tizen-Base-Toolchain`，和 `llvm_inline_development/config/gbs_llvm.conf` 指向的 Tizen Base Toolchain / Tizen Unified Toolchain `reference` 仓库一致。配置使用移动的 `reference` URL，因此这里能确认同一发行源族，不能仅凭 URL 证明字节级同一快照。
4. **glibc 机制版本仍是 2.40，但 RPM build 已变化。** 新镜像是 `glibc-2.40-1.6.armv7l`、GCC 14.2.0；2026-08-14 前的同类 LLVM 板记录是 `glibc-2.40-2.8.armv7l`、GCC 14.2.0。故与既有结论的上游机制基线一致，但不是同一个包构建。
5. **S2/S3 可在下一次获准执行负载的窗口直接开跑。** 身份、glibc 主版本、armv7l ABI、动态解释器/依赖库和磁盘容量门均通过；S2/S3 的 `alloc_bench` 路径本身不依赖 LLDB。当前系统未安装 LLDB，若另一个实验步骤依赖 LLDB，则该能力另行补齐，不能把它视为本轮已具备。
6. **旧 S4 参考格失去同板/同镜像可比性，必须补跑。** 当前 MemTotal 与 zram 均约为旧记录的 2.04 倍，glibc RPM release 和 kernel build 也变化；历史 `mixed / 50% / high = 53.55%`、`medium-only / 50% / high = 50.60%` 只能保留为历史参照，不能直接作为新镜像 S3 的 S4 对照基准。

## 2. 通道时间线与原始输出

除把实际地址统一替换为 `<TEST_BOARD_IP>` 外，以下保留命令输出原文。`*_EXIT` 是 host 包装层在命令后记录的退出状态，不是板端输出。

| Host 时间（CST） | 事件 | 结果 |
|---|---|---|
| 16:11:25 | ping 与 `/dev/tcp` 26101 探测 | 两项成功 |
| 16:11:50 | 记录 SDB 版本，检查本机 26099 | SDB 4.2.25；无监听残留 |
| 16:12:06 | 重启本机 SDB server，连接并枚举设备 | 连接成功，状态 `device` |
| 16:12 后 | 依次执行三重身份门 | 三项通过 |
| 16:12–16:19 | 只读采集环境、磁盘和能力位 | 完成 |
| 16:19:21 | `sdb devices` 收尾复核 | 仍在线 |

### 2.1 网络探测

```text
$ ping -c 4 -W 2 <TEST_BOARD_IP>
PING <TEST_BOARD_IP> (<TEST_BOARD_IP>) 56(84) bytes of data.
64 bytes from <TEST_BOARD_IP>: icmp_seq=1 ttl=63 time=0.483 ms
64 bytes from <TEST_BOARD_IP>: icmp_seq=2 ttl=63 time=0.751 ms
64 bytes from <TEST_BOARD_IP>: icmp_seq=3 ttl=63 time=0.714 ms
64 bytes from <TEST_BOARD_IP>: icmp_seq=4 ttl=63 time=0.729 ms

--- <TEST_BOARD_IP> ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3059ms
rtt min/avg/max/mdev = 0.483/0.669/0.751/0.108 ms
PING_EXIT=0
```

```text
$ timeout 3 bash -c 'exec 3<>/dev/tcp/<TEST_BOARD_IP>/26101; exec 3>&-; exec 3<&-'
(no stdout/stderr)
DEV_TCP_26101_EXIT=0
```

### 2.2 本机 SDB 客户端与 26099

```text
$ sdb version
Smart Development Bridge version 4.2.25
SDB_VERSION_EXIT=0
```

```text
$ ss -ltnp 'sport = :26099'
State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
SS_26099_EXIT=0
```

只有表头、没有监听行，因此操作前本机 26099 没有残留 SDB server 冲突。

```text
$ sdb kill-server
info: Server is not running
SDB_KILL_SERVER_EXIT=0

$ sdb start-server
* Server is not running. Start it now on port 26099 *
* Server has started successfully *
SDB_START_SERVER_EXIT=0

$ sdb connect <TEST_BOARD_IP>
connecting to <TEST_BOARD_IP>:26101 ...
connected to <TEST_BOARD_IP>:26101
SDB_CONNECT_EXIT=0

$ sdb devices
List of devices attached
<TEST_BOARD_IP>:26101 device     rpi4
SDB_DEVICES_EXIT=0
```

连接一次成功，因此没有触发“失败后限时 3 秒 banner 探测并停止”的分支。

收尾复核：

```text
HOST_TIME=2026-08-31 16:19:21 +0800 (CST)
List of devices attached
<TEST_BOARD_IP>:26101 device     rpi4
FINAL_SDB_DEVICES_EXIT=0
```

## 3. 三重身份门

### 3.1 硬门 A：kernel release 必须包含 `rpi4`

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell uname -r
6.12.80-arm-rpi4-v7l
IDENTITY_A_EXIT=0
```

判定：**PASS**，包含 `rpi4`。

### 3.2 硬门 B：架构必须严格为 `armv7l`

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell uname -m
armv7l
IDENTITY_B_EXIT=0
```

判定：**PASS**，严格等于 `armv7l`。

### 3.3 镜像门 C：`/etc/os-release` 全文

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell cat /etc/os-release
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l
IDENTITY_C_EXIT=0
```

判定：**PASS**。系统是 Tizen 11 Unified，BUILD_ID 明确属于 2026-08-14 的 unified toolchain headed armv7l 镜像。`/etc/os-release` 本身没有 `LLVM` 字面字段；LLVM 同源性需结合下述 GBS 配置判断，而不是从该文件单独推导。

配置来源核对使用 sibling 工作区中的 `llvm_inline_development/config/gbs_llvm.conf`；当前 `glibc_optimization` 工作树自身没有 `config/` 目录。相关配置原文为：

```ini
[repo.base-standard]
url=https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/reference/repos/standard/packages/

[repo.unified-standard]
url=https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified-Toolchain/reference/repos/standard/packages/
```

## 4. 新镜像基线

| 类别 | 项目 | 新镜像实测 | 判断 |
|---|---|---|---|
| 系统 | kernel | `6.12.80-arm-rpi4-v7l #1 SMP Fri Aug 14 10:46:17 UTC 2026` | RPI4 armv7l |
| 系统 | OS / BUILD_ID | Tizen 11 Unified / `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l` | LLVM unified 源族符合 |
| glibc | RPM | `glibc-2.40-1.6.armv7l` | 主版本仍为 2.40，release 已变化 |
| glibc | libc 输出 | GNU libc 2.40；GNU CC 14.2.0 | 与既有机制/编译器基线一致 |
| glibc | Build 来源 | vendor `tizen`；distribution `Tizen-Base-Toolchain`；source RPM `glibc-2.40-1.6.src.rpm` | 与 GBS base-toolchain repo 一致 |
| glibc | Build 元数据完整性 | `BUILDHOST=(none)`、`PACKAGER=(none)`、`BUILDTIME_EPOCH=0` | 镜像 RPM 未保留有效 build host/time；1970 显示只是 epoch 0，不是真实构建日 |
| 内存 | MemTotal | `8,117,408 kB`（约 7.74 GiB） | 约为旧记录 2.04 倍 |
| CPU | governor | cpu0–cpu3 全部 `schedutil` | 未修改 |
| zram | disksize | `3,324,891,136 B`；`/proc/swaps` 为 `3,246,960 kB` | 约 3.10 GiB |
| zram | 使用量 / `mm_stat` | Used `0 kB`；`4096 74 4096 0 4096 0 0 0 0` | 空闲，未施加压力 |
| 时间 | 板端时间 | `Mon Aug 31 17:15:50 KST 2026` | 与 host CST 相差时区 1 小时 |
| 运行态 | uptime / load | `up 3 days, 1:25`；load `0.27, 0.14, 0.10` | 仅记录，不据此做性能结论 |
| 磁盘 | `/` | 2.9G 总量，1.2G 已用，1.8G 可用，41% | 足够容纳 `<50 MB` |
| 磁盘 | `/opt` / `/hal` | 分别 1.3G / 207M 可用 | 足够容纳 `<50 MB` |
| 磁盘 | `/opt/usr` | 112G 总量，111G 可用，1% | 容量非常充足 |
| 权限 | 当前 shell 身份 | `uid=0(root)`，Smack context `User::Shell` | SDB 当前即为 root；本轮未执行 `sdb root on` |
| 调试 | LLDB | RPM 未安装；PATH 中不存在 `lldb` | LLDB 能力未就绪 |
| 调试 | yama | `/proc/sys/kernel/yama/ptrace_scope` 不存在 | 无该 sysctl 可记录值 |
| ABI | loader / DSO | `/lib/ld-linux.so.3`、`libc.so.6`、`libpthread.so.0` 均存在 | 与本地 armv7l `alloc_bench` 的动态依赖匹配 |

### 4.1 glibc 版本与构建原文

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell rpm -q glibc
glibc-2.40-1.6.armv7l
RPM_Q_GLIBC_EXIT=0
```

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell /lib/libc.so.6
GNU C Library (GNU libc) stable release version 2.40.
Copyright (C) 2024 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.
There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.
Compiled by GNU CC version 14.2.0.
libc ABIs: UNIQUE ABSOLUTE
Minimum supported kernel: 3.2.0
For bug reporting instructions, please see:
<https://www.gnu.org/software/libc/bugs.html>.
LIBC_VERSION_EXIT=0
```

最终采用的无转义 queryformat 原文：

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell "rpm -q --queryformat 'NAME=%{NAME};VERSION=%{VERSION};RELEASE=%{RELEASE};ARCH=%{ARCH};BUILDHOST=%{BUILDHOST};BUILDTIME_EPOCH=%{BUILDTIME};PACKAGER=%{PACKAGER};VENDOR=%{VENDOR};DISTRIBUTION=%{DISTRIBUTION};SOURCERPM=%{SOURCERPM}' glibc"
NAME=glibc;VERSION=2.40;RELEASE=1.6;ARCH=armv7l;BUILDHOST=(none);BUILDTIME_EPOCH=0;PACKAGER=(none);VENDOR=tizen;DISTRIBUTION=Tizen-Base-Toolchain;SOURCERPM=glibc-2.40-1.6.src.rpm
RPM_BUILDINFO_QUOTED_EXIT=0
```

采集时有两次 queryformat 引号/转义格式重试，均只读且没有产生板端文件。为保持审计完整性，原文如下：

```text
NAME=glibcnVERSION=2.40nRELEASE=1.6nARCH=armv7lnBUILDHOST=(none)nBUILDTIME=Thu Jan  1 09:00:00 1970nPACKAGER=(none)nVENDOR=tizennDISTRIBUTION=Tizen-Base-ToolchainnSOURCERPM=glibc-2.40-1.6.src.rpmnRPM_BUILDINFO_EXIT=0
```

```text
rpm: no arguments given for query
/bin/sh: glibc: command not found

RPM_BUILDINFO_RETRY_EXIT=0
```

这里也暴露出本机 `sdb shell` 进程退出码不能可靠代表远端子命令退出码：第二次重试的远端命令明显失败，但 host 仍记录 0。后续实验必须同时检查结构化结果/DONE 标志，不能只看 `sdb` 自身退出码。

### 4.2 kernel、内存、CPU 与 zram 原文

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell uname -a
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Fri Aug 14 10:46:17 UTC 2026 armv7l GNU/Linux
UNAME_A_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell "grep '^MemTotal:' /proc/meminfo"
MemTotal:        8117408 kB
MEMTOTAL_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell "grep . /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor"
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor:schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor:schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor:schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor:schedutil
GOVERNOR_EXIT=0
```

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell cat /sys/block/zram0/disksize
3324891136
ZRAM_DISKSIZE_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell cat /sys/block/zram0/mm_stat
    4096       74     4096        0     4096        0        0        0        0
ZRAM_MM_STAT_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell cat /proc/swaps
Filename                                Type            Size            Used            Priority
/dev/zram0                              partition       3246960         0               0
PROC_SWAPS_EXIT=0
```

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell date
Mon Aug 31 17:15:50 KST 2026
BOARD_DATE_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell uptime
 17:15:50 up 3 days,  1:25,  1 user,  load average: 0.27, 0.14, 0.10
UPTIME_EXIT=0
```

### 4.3 磁盘原文与容量判断

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell df -h
Filesystem            Size  Used Avail Use% Mounted on
devtmpfs              3.8G  8.0K  3.8G   1% /dev
/dev/mmcblk0p6         19M  4.0M   15M  22% /usr/lib/modules
/dev/mmcblk0p2        2.9G  1.2G  1.8G  41% /
/dev/mmcblk0p3        1.3G   46M  1.3G   4% /opt
/dev/mmcblk0p10       232M   23M  207M  10% /hal
tmpfs                 3.9G  252K  3.9G   1% /dev/shm
tmpfs                 3.9G  3.3M  3.9G   1% /run
tmpfs                 3.9G     0  3.9G   0% /sys/fs/cgroup
tmpfs                 3.9G   24K  3.9G   1% /tmp
/dev/mmcblk0p9        3.5M   52K  2.9M   2% /mnt/inform
/dev/mmcblk0p5        112G  960M  111G   1% /opt/usr
/dev/loop0            8.6M   32K  8.4M   1% /opt/usr/home/owner/subsession/__template_fixed__
tmpfs                 3.9G     0  3.9G   0% /opt/media
/dev/loop1            8.6M   32K  8.4M   1% /opt/usr/home/owner/subsession/.profiles/__template_fixed__
tmpfs                 793M     0  793M   0% /run/user/5001
/dev/mmcblk0p5        112G  960M  111G   1% /opt/usr/home/owner/media
DF_H_EXIT=0
```

容量判断：本地候选 `alloc_bench.armv7l` 只有 176,680 B；即使把 S2/S3 的 JSON、每阶段 `malloc_info` XML 和日志全部计入，协议预估仍 `<50 MB`。根分区可用 1.8G，约为需求上限的 36 倍；`/opt/usr` 可用 111G。因此当前不存在磁盘容量阻塞。由于本轮禁止板端写入，没有用实际落盘测试验证目录权限，也没有创建结果目录。

### 4.4 用户、LLDB、ptrace 与 ABI 原文

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell id
uid=0(root) gid=0(root) groups=0(root),29(audio),44(video),201(display),1901(log),6505(pulse-access),6506(pulse-rt),6525(usb_device),10001(priv_externalstorage),10013(priv_tee_client),10014(priv_peripheralio),10212(priv_platform),10501(priv_camera),10502(priv_mediastorage),10503(priv_recorder),10704(priv_internet),10705(priv_network_get),10711(priv_tethering_admin),10901(priv_email),10903(priv_message_read),11103(priv_mapservice),11201(priv_appdebugging) context="User::Shell"
ID_EXIT=0
```

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell rpm -q lldb
package lldb is not installed
RPM_Q_LLDB_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell which lldb
/bin/sh: which: command not found
WHICH_LLDB_EXIT=0

$ sdb -s <TEST_BOARD_IP>:26101 shell "command -v lldb || printf 'LLDB_NOT_FOUND_IN_PATH\\n'"
LLDB_NOT_FOUND_IN_PATH
COMMAND_V_LLDB_EXIT=0
```

`which` 本身不存在，因此用 POSIX shell 的 `command -v` 完成了 PATH 复核。`rpm` 原文和 `command -v` 一致表明 LLDB 未就绪；不能被 SDB 包装层的 0 退出码误导。

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell "if [ -e /proc/sys/kernel/yama/ptrace_scope ]; then cat /proc/sys/kernel/yama/ptrace_scope; else printf 'ABSENT\\n'; fi"
ABSENT
PTRACE_SCOPE_EXIT=0
```

本地候选二进制的动态依赖与板端现有路径复核：

```text
$ readelf -d temp/sync_20260831/validation/alloc_bench/alloc_bench.armv7l | rg 'NEEDED'
 0x00000001 (NEEDED)                     Shared library: [libpthread.so.0]
 0x00000001 (NEEDED)                     Shared library: [libc.so.6]

$ sdb -s <TEST_BOARD_IP>:26101 shell ls -l /lib/ld-linux.so.3 /lib/libc.so.6 /lib/libpthread.so.0
-rwxr-xr-x 1 root root  187668 Aug 14 15:06 /lib/ld-linux.so.3
-rwxr-xr-x 1 root root 1429532 Aug 14 15:07 /lib/libc.so.6
-rwxr-xr-x 1 root root   13608 Aug 14 15:07 /lib/libpthread.so.0
ABI_PATHS_EXIT=0
```

这只是静态依赖路径检查；本轮没有把候选二进制推到板上，也没有执行它。

## 5. 与 2026-08-14 前旧镜像记录的差异

旧值取自 2026-08-12/13 的同类 RPI4 Tizen Unified LLVM 板记录，主要依据 `docs/l6_ui_release_phase.md`、`docs/l6_applicability_curve.md` 和 `docs/rpi4_graphics_install.md`。IP 不参与身份或同板判断；旧 BUILD_ID 继续使用既有脱敏名 `<TEST_IMAGE_B>`。

| 项目 | 旧镜像记录（2026-08-14 前） | 新镜像（本轮） | 差异与影响 |
|---|---|---|---|
| 身份硬门 | RPI4；`armv7l`；Tizen 11 Unified | 相同三项 | 设备类别一致 |
| kernel | `6.12.80-arm-rpi4-v7l`，Jul 28 build | 同 release，Aug 14 build | kernel 包构建已更新 |
| BUILD_ID | `<TEST_IMAGE_B>` | `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l` | 镜像构建不同 |
| glibc RPM | `glibc-2.40-2.8.armv7l` | `glibc-2.40-1.6.armv7l` | 主版本相同，RPM release 不同；不能称为相同二进制基线 |
| libc 编译器 | GNU CC 14.2.0 | GNU CC 14.2.0 | 相同 |
| MemTotal | `3,976,480 kB` | `8,117,408 kB` | 新值约 2.04 倍；实体板/内存配置不能假定相同 |
| governor（静置基线） | cpu0–3 均 `schedutil` | cpu0–3 均 `schedutil` | 相同；历史 53.55%/50.60% 正式格则是在 `performance` 下取得 |
| zram disksize | `1,590,588 kB` | `3,246,960 kB` | 新值约 2.04 倍 |
| zram Used | `0 kB` | `0 kB` | 相同 |
| zram `mm_stat` 起始值 | `4096 74 4096`（其余未在摘要记录） | `4096 74 4096 0 4096 0 0 0 0` | 已知前三项相同 |
| rootfs | 2.9G 总量，约 1.6G 可用 | 2.9G 总量，1.8G 可用 | 新镜像余量略大；两者都足够 `<50 MB` |
| 系统 LLDB | 旧实验使用临时 LLDB 22.1.8，不是系统常驻能力 | RPM/PATH 均无 LLDB | 当前仍不能假定 LLDB 可用 |
| yama `ptrace_scope` | 旧摘要未记录 | 文件不存在 | 只能记录本轮事实 |

## 6. 对后续 S2/S3/S4 的明确判断

### 6.1 glibc 基线与 S2/S3

**判断 A：机制版本一致，包构建不一致；S2/S3 的环境门已通过，可在下一次获准执行的窗口直接开跑。**

- 状态报告 §2.5 的既有结论基于 glibc 2.40；本轮 `/lib/libc.so.6` 与 RPM 都确认仍是 2.40。因此从 malloc 机制版本看，S2/S3 不需要先做 2.41 迁移重验。
- 新 RPM 是 `2.40-1.6`，旧 RPM 是 `2.40-2.8`，所以新 S2/S3 必须作为新镜像实验批次，不得与旧批次混写成相同 build 的重复样本。
- 状态报告 §2.5 的两个 2.41 影响项本轮**未触发**：`e2436d6f5a`（free 的小 chunk 改走 smallbin）与 `226e3b0a41`（calloc 增加 tcache 路径）只在升级到 2.41+ 时要求重验 R13 与 R11/L4。
- armv7l loader、`libpthread.so.0`、`libc.so.6` 存在，根分区空间充足；当前 S2/S3 的自包含 `alloc_bench` 不要求 LLDB。正式运行前仍应按实验协议锁定候选二进制 SHA-256、记录 governor，并在结束后清理板端产物；这些动作不属于本轮只读授权。

### 6.2 历史瞬时释放值与 S4

**判断 B：历史瞬时释放参考值已经失去同板/同镜像可比性，S4 必须在新镜像补跑参考格。**

- 历史参考：`mixed / 50% / high = 53.55%`；`medium-only / 50% / high = 50.60%`。
- 新镜像同时变化了 BUILD_ID、kernel build、glibc RPM release、MemTotal 和 zram 容量；其中 RAM/zram 约 2.04 倍的差异尤其不能视为轻微噪声。
- 三重身份门只能证明这是 RPI4 armv7l Tizen Unified 目标类别，不能证明它就是旧记录的同一实体板；IP 明确不用于这一判断。
- 因此 S4 应在本轮新镜像上，用与 S2/S3 相同的二进制、governor、线程数、seed、live-set、release 比例/顺序和 touch 口径，至少补跑 `mixed / 50% / high` 与 `medium-only / 50% / high` 的瞬时释放参考格，再与渐进释放/trim 时机格做同批次派生。旧 53.55% / 50.60% 只作历史 sanity range，不作为通过阈值或同板复现值。

## 7. 本轮边界复核

- 没有执行 `sdb root on`；`id` 显示的 root 是当前 SDB shell 既有状态。
- 没有执行 `sdb push`、重定向到板端文件、`tee`、包管理写操作、配置写操作或删除操作。
- 没有执行 `alloc_bench`、LLDB、压力工具或应用负载。
- `/dev/tcp` 只建立并关闭连接；SDB 连接成功，因此没有发送 banner 探测数据。
- 所有板端命令仅读取 kernel/sysfs/procfs、RPM 数据库、现有动态库元数据或文件系统容量；板上没有产生临时文件。
