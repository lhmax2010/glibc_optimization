# P0 第五次续跑：zram 侦察完成，字符串筛选异常停止

执行日期：2026-11-09（Asia/Shanghai）。全部材料仅本地保存。

本轮使用 resume5_，开始时该前缀未占用，无需改用 resume6_。
停止原因：按原样执行 /usr/bin/* 字符串筛选时返回 RC=2 / FAIL。
该命令带 2>/dev/null，错误文本被原命令丢弃，无法从现有证据定位具体失败文件或原因。
没有重试、没有修改扫描命令。停止后执行了全部适用收尾项，未安装任何包。

## 0. root、身份、堆年龄与文件系统原文

### sdb root on

```text
Switched to 'root' account mode
```

### uname -r

```text
6.12.80-arm-rpi4-v7l

RC=0
DONE
```

### uname -m

```text
armv7l

RC=0
DONE
```

### cat /etc/os-release

```text
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l

RC=0
DONE
```

### id -u

```text
0

RC=0
DONE
```

### cat /proc/uptime

```text
5135.46 20201.65

RC=0
DONE
```

### command -v dd grep pgrep ps tar rpm 2>&1

```text
/usr/bin/dd
/usr/bin/grep
/usr/bin/pgrep
/usr/bin/ps
/usr/bin/tar
/usr/bin/rpm

RC=0
DONE
```

### df -k / /tmp（开始）

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mmcblk0p2         1115180   1082504      4180 100% /
tmpfs                  1988232        24   1988208   1% /tmp

RC=0
DONE
```

### grep -E " / | /tmp " /proc/mounts

```text
/dev/mmcblk0p2 / ext4 ro,relatime 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,noexec 0 0

RC=0
DONE
```

镜像判定：RPI4 / armv7l / Tizen 11 Unified，
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l；
依据三重身份，不以 IP 判板。授权提权后 UID=0。

根分区 / 为 ext4、ro，可用 4180 KiB；/tmp 为 tmpfs、rw,nosuid,nodev,noexec。
本轮没有 remount，也没有绕过 noexec。未进入 GDB 安装或兜底验证阶段，
所以不能称 3c/3d 已试过或判其验证结果。

## 1. 预测文件与时间、调用预算

沿用原 prediction.txt，不重写、不新建。校验值与指定值一致：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

原写入完成：2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端观测（uname -r）开始：2026-11-09T21:31:39.751914+08:00，host epoch ns 1794231099751913560。
本次首次 zram 侦察读取（cat /proc/swaps）开始：2026-11-09T21:31:47.926114+08:00；库字符串扫描开始：2026-11-09T21:31:56.819689+08:00。均晚于预测文件写入。
这些是主机记录的请求开始时刻，不是板端时钟读数；没有首次 trim/pagemap 测量时间。
本轮共 39 次 sdb 调用，0 次重连、0 次通道失败；全部一次性串行调用。
相邻调用间隔（上次结束到下次开始）为 0.500080660–0.760548365 秒，均 >=0.5 秒。最大 shell payload 为 171 字节。

## 2. 装 GDB 前的 zram 只读侦察：全部原文

### cat /proc/swaps

```text
Filename				Type		Size		Used		Priority
/dev/zram0                              partition	2584700		768		-2

RC=0
DONE
```

### cat /proc/sys/vm/swappiness

```text
60

RC=0
DONE
```

### grep -E "MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree" /proc/meminfo

```text
MemTotal:        3976468 kB
MemFree:         3271060 kB
MemAvailable:    3453924 kB
SwapTotal:       2584700 kB
SwapFree:        2583932 kB

RC=0
DONE
```

### ls /sys/block/ | grep zram

```text
zram0

RC=0
DONE
```

### cat /sys/block/zram0/disksize

```text
2646736896

RC=0
DONE
```

### cat /sys/block/zram0/mm_stat

```text
  700416   700416   700416        0   700416        0        0      171      171        0        0        0

RC=0
DONE
```

### cat /sys/block/zram0/comp_algorithm

```text
lz4 [zstd] 

RC=0
DONE
```

### cat /proc/pressure/memory

```text
some avg10=0.00 avg60=0.00 avg300=0.00 total=5260
full avg10=0.00 avg60=0.00 avg300=0.00 total=1753

RC=0
DONE
```

### grep cgroup /proc/filesystems

```text
nodev	cgroup
nodev	cgroup2

RC=0
DONE
```

### ls /sys/fs/cgroup/

```text
blkio  cpu,cpuacct  cpuset   freezer  net_cls	systemd
cpu    cpuacct	    devices  memory   net_prio	watchdog

RC=0
DONE
```

### find /sys/fs/cgroup -maxdepth 2（memory.max / memory.limit_in_bytes）

```text
/sys/fs/cgroup/memory/memory.limit_in_bytes

RC=0
DONE
```

### pgrep -l resourced

```text
426 resourced

RC=0
DONE
```

### ls /etc/resourced/ 2>&1

```text
limiter.conf  monitor.conf  optimizer.conf  process.conf  vip-process.d

RC=0
DONE
```

### cat /etc/resourced/*.conf

```text
[MemoryLevelThreshold]
MediumLevel=       25%
LowLevel=          15%
CriticalLevel=     10%
OomLevel=           7%
#LmkThresholdLeave= 14%
#ProactiveThreshold= 10%
#ProactiveThresholdLeave= 14%
#LmkMaxVictimPerOom= 10
OomPopup=           no

[MemoryAppTypeLimit]
ServicePerAppLimitAction=128MB
#WidgetPerAppLimitAction=160MB
#GUIPerAppLimitAction=1024MB
#WebPerAppLimitAction=512MB

[MemoryAppStatusLimit]
#BackgroundPerAppLimitAction=768MB

[MemoryBackgroundLru]
BackgroundLruLimit=  80%

[MemoryLMKGovernor]
ForegroundAppListPostGovernor=no
WorkingSetSizePostGovernor=no

[MemoryLimitTrigger]
MemoryLimitTrigger=oom
#MemoryLimitTrigger=threshold
#MemoryLimitTrigger=others

[WatchdogFailAction]
FailOnce=/usr/sbin/reboot silent
FailTwice=/usr/sbin/reboot silent
FailOther=/usr/sbin/reboot silent

[CpuThrottling]
#CpuSched=idle
#CpuNice=19
#CpuShare=64
#CpuCFSRuntime=50ms
#CpuCFSPeriod=1s
[HEART]
BATTERY=ON
CPU=ON
MEMORY=OFF
STORAGE=OFF

[BATTERY_POWER_MODE]
POWER_NORMAL_MODE=676
POWER_SAVING_MODE=750
ULTRA_SAVING_MODE=1947

[BATTERY_2600]
LOGIC_V2=1
DISCHARGE_FAST=700
DISCHARGE_SLOW=12000
AVERAGE_PWR=35.0
OCV_SOC_POLY_COEF=6 3402.664 42.031 -1.76745 0.034798 -0.00030516 0.0000010116

[BATTERY_1500]
LOGIC_V2=1
DISCHARGE_FAST=200
DISCHARGE_SLOW=7000
AVERAGE_PWR=35.0
OCV_SOC_POLY_COEF=6 3402.664 42.031 -1.76745 0.034798 -0.00030516 0.0000010116

[BATTERY]
LOGIC_V2=0
DISCHARGE_FAST=0
DISCHARGE_SLOW=0
AVERAGE_PWR=0.0
[MemorySwap]
SwapEnable=no
ReclaimAtBoot=yes
SwapType=zram
BackgroundLruSwappiness=80

[MemoryZram]
CompAlgorithm=zstd
ZramRatio=0.4

[MemoryZswap]
PoolRatio=40
PoolType=z3fold

[MemoryDedup]
DedupAtBoot=yes
ScanOnLowmem=yes

[MemoryKsm]
KsmMode=oneshot
#KsmMode=periodic

PagesToScan=100
PagesToScanWithBoost=1000

[MemoryCompaction]
FragLevel=800

[MemoryBackgroundReclaim]
# Unset this option if it causes any unexepcted issue (e.g. jerky animation).
AfterScreenDim=yes

[CpuSched]
CpuSchedFeature=no_rt_runtime_share
CpuRTRuntime=950ms
CpuRTPeriod=1000ms

[CpuAffinity]
#ForegroundApps=1,2,4-6

[CpuBoostingLevelStrong]
CpuSched=rr
CpuRTPriority=50

[CpuBoostingLevelMedium]
CpuSched=rr
CpuRTPriority=1

[CpuBoostingLevelWeak]
CpuSched=other
CpuNice=-20 # Priority=100

[CpuBoostingStallGovernor]
CpuBoostingStallGovernor=no
[APPUSAGE]
APPUSAGE=ON

[BLOCK]
activate=TRUE
mode=WRITE
include=DOWNLOADABLE
exclude=SLP_debug
exclude_proc=mtp-responder
logging=5

RC=0
DONE
```

记录解释仅限已读事实：zram0 存在，当前算法选择为 [zstd]；全局 swappiness 为 60。
内核支持 cgroup 与 cgroup2；本次找到的内存限制接口为 v1 路径
/sys/fs/cgroup/memory/memory.limit_in_bytes。
resourced 正在运行，PID=426。/etc/resourced/*.conf 的原样合并输出如上，
来自 limiter.conf、monitor.conf、optimizer.conf、process.conf；没有改动配置。
配置文本与实际内核计数并列保留，不推断其中差异原因。

## 3. 装 GDB 前的 malloc_trim 字符串筛选

### grep -l malloc_trim /usr/lib/lib*.so* 2>/dev/null > /tmp/p0/hits_lib.txt

```text

RC=0
DONE
```

### grep -l malloc_trim /usr/bin/* 2>/dev/null > /tmp/p0/hits_bin.txt

```text

RC=2
FAIL
```

库扫描 RC=0。可执行文件扫描 RC=2，属于本次停止点；
因错误输出被命令按要求重定向到 /dev/null，不能补写不存在的错误明细。
下面的清单在停止后的收尾归档中拉回并在 host 解出，未额外重跑扫描。

### 库清单（原文）

```text
/usr/lib/libamd.so.1
/usr/lib/libamd.so.1.82.15
/usr/lib/libapp-core-cpp.so.1
/usr/lib/libapp-core-cpp.so.1.28.10
/usr/lib/libappcore-common.so.1
/usr/lib/libappcore-common.so.1.28.10
/usr/lib/libbluetooth.default.so
/usr/lib/libbluetooth.default.so.1
/usr/lib/libbluetooth.default.so.1.0.0
/usr/lib/libc.so.6
/usr/lib/libc_malloc_debug.so.0
/usr/lib/liblaunchpad.so.0
/usr/lib/liblaunchpad.so.0.51.7
/usr/lib/libmuse-server.so.0
/usr/lib/libmuse-server.so.0.6.1
/usr/lib/libnntrainer.so
/usr/lib/libpipewire-0.3.so.0
/usr/lib/libpipewire-0.3.so.0.1600.0
/usr/lib/libpkgmgr-info-server.so.0
/usr/lib/libpkgmgr-info-server.so.0.37.5
/usr/lib/libscim-1.0.so.8
/usr/lib/libscim-1.0.so.8.2.3
/usr/lib/libscl-core.so
/usr/lib/libtrackrenderer.so
```

### 可执行文件部分清单（原文；不可视为完整扫描）

```text
/usr/bin/bt-service
/usr/bin/contacts-service-ipcd
/usr/bin/isf
/usr/bin/isf-panel-efl
/usr/bin/media-server
/usr/bin/pushd
/usr/bin/resourced
/usr/bin/tizen-watcherd
```

库字符串清单 24 条路径，包含 /usr/lib/libc.so.6，故阳性对照通过；可执行文件部分清单 8 条路径。
这些只是字符串命中路径，包含符号链接与带版本文件名，不能当作不同调用方的数量。
尚未执行重点目标 ls -l，尚未测量命中文件总字节数、拉取 ELF 或运行 host readelf。
因此没有 UND/定义符号行，也没有可确认的“字符串误命中”清单，不能写成调用方零命中。
libappcore-common 与 resourced 出现在字符串清单中，但其 malloc_trim 导入/定义属性仍未核实。

## 4. GDB 包处理状态

为满足“任一步停止也必须对比包集合”，在第 1 步侦察之前提前保存了完整 RPM 基线，
此前没有进行包操作。尚未进入第 3a 候选逐包查询及 3b 依赖解析。
候选包存在状态：未查询；--test 轮数：0；下载 RPM 数量：0；repodata 比对：未执行。
没有复用任何 GBS-ROOT 或其他 session 的 RPM 缓存。
没有走 3c，也没有走 3d；没有 installed_by_p0.txt，因为没有任何本轮安装。
gdb show version 未执行；收尾的 command -v gdb 结果见下。
没有 rpm -i、rpm -U 或 rpm -e 操作，没有升级、重装或卸载任何原有包。

## 5. pagemap 与三次 trim

目标 PID、starttime 尚未采集。/proc/uptime 原文见第 0 节；
不能将系统 uptime 当作目标堆年龄。AT_SECURE 未读取，没有发生 trim 或作废的 trim。

| 次序 | present 前/后 | swapped 前/后 | Private_Dirty 前/后 | Rss 前/后 | reclaimed_bytes | minflt/majflt 增量 | trim 返回值 | 注入耗时 | XML |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未采 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未采 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未采 |

H1、H2、H3、H4 分别均为“无法判定：未测量”，不判成立/不成立，不填写虚构实际值或差额。

## 6. 无论成败的收尾回执

没有新装包，故 rpm -e --test 与 rpm -e 不适用、未执行。
rpm -qa 前后各 1234 行，文件逐字节一致；resume5_rpmqa.diff 为 0 字节。

### rpm -qa | sort > /tmp/p0/rpmqa_after.txt

```text

RC=0
DONE
```

前后全量文件为 resume5_rpmqa_before.txt 与 resume5_rpmqa_after.txt。

### command -v gdb 2>&1（收尾）

```text

RC=1
FAIL
```

### 归档全部已生成数据（排除 rpms/、gdbroot/）

```text

RC=0
DONE
```

### rm -rf /tmp/p0

```text

RC=0
DONE
```

### ls /tmp/p0 2>&1（删除复核）

```text
ls: cannot access /tmp/p0: No such file or directory

RC=2
FAIL
```

### df -k / /tmp（收尾）

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mmcblk0p2         1115180   1082504      4180 100% /
tmpfs                  1988232        24   1988208   1% /tmp

RC=0
DONE
```

### sdb root off

```text
Switched to 'sdk user' account mode
```

### id -u（收尾）

```text
5001

RC=0
DONE
```

/tmp/p0 已确认不存在，UID 已恢复 5001。
ls 的 RC=2 与 gdb 查询的 RC=1 是预期缺失项，不是隐瞒错误。
收尾状态 complete=true，错误列表为空。没有自行补救或修改包集合。

## 7. 源码、资源与本地文件

指定 demo-v14 commit 已核验为 7289a47b9d24791944cd3b02c00f24b8cb76aa3b；
现有仓库 is-shallow-repository=false。
已只读导出 trim_via_gdb.sh 和 run_b2_remote.sh 原文，包含 inject_malloc_info
生成的 set pagination off / fopen / malloc_info / fclose / detach 命令；
未修改或执行注入脚本，没有另写注入器。

执行 scope 固定 CPU 0、1，cpu.max=200000 100000，
memory.max=1999998976（不超过 2 GB），memory.swap.max=0；执行串行。
板端只进行授权 root on/off、查询、字符串筛选、/tmp/p0 内证据写入与清理。
未安装包、施加负载、attach、注入、kill、reboot、remount 或修改配置。
本轮未推送或执行脚本，不能判断签名强制策略。

本地目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

本轮新增材料使用 resume5_ 前缀，包括 resume5_boarddata/ 下的归档解出文件。
全部旧文件的哈希及 mtime 均保持不变，原 prediction.txt、report.md、FILES.tsv 未改。
已跟踪文件及暂存区无变化，git status --porcelain 输出为空；本目录仍被忽略。
未 git add、commit、push。全部原始文件、大小与 SHA-256 见 resume5_FILES.tsv，
可用 resume5_SHA256SUMS 校验。清单自身不纳入自身哈希。
