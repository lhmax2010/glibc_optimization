# P0 第七次续跑：pagemap 与三次 trim（本地留存）

本轮完成。仅对同一 enlightenment 进程执行三次 trim；未重做字符串扫描、符号确认或 zram 侦察，未重新下载 RPM。
H1–H4 在本次观测范围内均成立，不外推到其他目标或运行阶段。
所有材料仅本地留存，未 git add / commit / push。

## 0. 身份、权限与空间原文

三重身份表明本次为 RPI4 / armv7l 的 Tizen 11 Unified 开发镜像，不能以连接 IP 判定身份。

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
10696.60 42100.55

RC=0
DONE
```

### MemTotal

```text
MemTotal:        3976468 kB

RC=0
DONE
```

### df -k /opt/usr

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mmcblk0p5       116404224    982792 115421432   1% /opt/usr

RC=0
DONE
```

### /opt/usr 挂载属性

```text
/dev/mmcblk0p5 /opt/usr f2fs rw,lazytime,relatime,background_gc=on,nogc_merge,discard,discard_unit=block,user_xattr,inline_xattr,acl,inline_data,inline_dentry,flush_merge,barrier,extent_cache,mode=adaptive,active_logs=6,alloc_mode=default,checkpoint_merge,fsync_mode=posix,memory=normal,errors=continue 0 0

RC=0
DONE
```

/opt/usr 为 mmcblk0p5、rw、无 noexec，可用空间满足 >=500 MB；重连次数 0，通道失败 0。

## 1. 预测、工具归档与时间顺序

预测文件 prediction.txt 沿用不变，SHA-256：`ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14`。

预测写入时间：2026-11-09T19:17:02.673081+08:00；用户登记时间为 2026-11-09 19:17:02（UTC+8）。

本次首次板端观测（uname -r）请求开始：2026-11-09T23:04:18.141129+08:00；epoch ns 1794236658141128874。

本次首次 heap 测量请求开始：2026-11-09T23:05:43.874437+08:00；epoch ns 1794236743874437246。均晚于预测写入；时间来自 host 请求日志。

复用 resume6_gdbroot.tar：54579200 字节，SHA-256 `ab4f53de6506a3597479008510b80e870de140e9b995a527c08b8288b146e736`，与 resume6 报告一致。未下载 RPM、未装卸包。

指定源码 commit：7289a47b9d24791944cd3b02c00f24b8cb76aa3b；当前仓库为全克隆，两份复用工具源码与 git show 对应字节一致。

每次 GDB 调用先读取 /opt/usr/p0/environment，设置本轮指定的 PATH、LD_LIBRARY_PATH、PYTHONHOME 和 EXPECTED_BUILD_ID；该文件仅在允许目录中，随收尾删除。XML 命令文件严格沿用指定函数的五行内容，仅替换 XML 路径。

### gdb show version

```text
GNU gdb (GDB) 16.3
Copyright (C) 2024 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>

RC=0
DONE
```

共 89 次 sdb 调用（上限150），最短相邻间隔 0.500071355 s，最大 shell payload 189 字节。CPU 固定0/1、CPUQuota=200%、MemoryMax=2000000000、MemorySwapMax=0，调用串行。

## 2. 目标与 AT_SECURE

目标 enlightenment，PID=555，starttime=1581 时钟滴答，与 resume6 的 PID555/starttime1581 一致，未观测到重启。

### 目标 stat 原文

```text
555 (enlightenment) S 1 555 555 0 -1 4194560 5670 0 129 0 2457 1537 0 0 20 0 8 0 1581 193613824 4704 4294967295 4743168 6440068 3201621088 0 0 0 2561 4096 92679 0 0 0 17 0 0 0 0 0 0 6443008 6479004 13180928 3201621389 3201621412 3201621412 3201621989 0

RC=0
DONE
```

### 选择目标时 uptime

```text
10771.29 42384.35

RC=0
DONE
```

AT_SECURE（type23）=0。原始 auxv：resume7_auxv_a0.bin；解析：resume7_auxv.json。

## 3. 三次完整测量

单位：PD/Rss/Swap 为内核 kB（1024字节）；页为4096字节。reclaimed_bytes 只取 heap Private_Dirty 的前后差×1024。

|次数|present 前→后|swapped 前→后|PD 前→后 kB|Rss 前→后 kB|Swap 前→后 kB|reclaimed_bytes|Rss 差字节|minflt/majflt 增量|trim 返回|注入耗时 ms|pre XML|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|848→840|0→0|3392→3360|3392→3360|0→0|32768|32768|0/0|1|1560.724471|已采，XML解析通过|
|2|840→840|0→0|3360→3360|3360→3360|0→0|0|0|0/0|1|1900.282497|已采，XML解析通过|
|3|840→840|0→0|3360→3360|3360→3360|0→0|0|0|0/0|1|1569.708798|已采，XML解析通过|

注入方式：指定 demo-v14 的 trim_via_gdb.sh + 便携 GDB16.3。耗时为 host 发出至收到完整输出，包含 sdb、脚本身份检查与 gdb/ptrace 开销，不是 malloc_trim 函数自身耗时。三个返回值均为1；不能仅凭返回1推断 heap 有回收。

三次之间未施加负载、未重启目标；没有通道中断、没有作废或替换目标。必需字段与三个可选字段均存在，没有“该内核无此字段”项。六份 pagemap 的长度均为 COUNT×8，逐页 bit63/bit62 在宿主解析。

采集按请求顺序执行，smaps、pagemap、XML、stat 并非同时冻结的原子快照。minflt/majflt 增量按每次 pre XML 之后的 stat 到 post stat 计算，不覆盖更早的 XML 注入；目标 stat 的历史 majflt=129 不代表本轮新增。

### 第 1 次 trim 完整输出

```text
IDENTITY_OK=RPI4_UNIFIED_TOOLCHAIN
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l
pid=555
[New LWP 736]
[New LWP 731]
[New LWP 730]
[New LWP 729]
[New LWP 722]
[New LWP 690]
[New LWP 652]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/libthread_db.so.1".
0xb6874918 in __GI___poll (fds=0x13ee428, nfds=18, timeout=-1) at ../sysdeps/unix/sysv/linux/poll.c:29

warning: 29	../sysdeps/unix/sysv/linux/poll.c: No such file or directory
$1 = 1
[Inferior 1 (process 555) detached]

RC=0
DONE
```

### 第 2 次 trim 完整输出

```text
IDENTITY_OK=RPI4_UNIFIED_TOOLCHAIN
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l
pid=555
[New LWP 736]
[New LWP 731]
[New LWP 730]
[New LWP 729]
[New LWP 722]
[New LWP 690]
[New LWP 652]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/libthread_db.so.1".
0xb6874918 in __GI___poll (fds=0x13ee428, nfds=18, timeout=-1) at ../sysdeps/unix/sysv/linux/poll.c:29

warning: 29	../sysdeps/unix/sysv/linux/poll.c: No such file or directory
$1 = 1
[Inferior 1 (process 555) detached]

RC=0
DONE
```

### 第 3 次 trim 完整输出

```text
IDENTITY_OK=RPI4_UNIFIED_TOOLCHAIN
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l
pid=555
[New LWP 736]
[New LWP 731]
[New LWP 730]
[New LWP 729]
[New LWP 722]
[New LWP 690]
[New LWP 652]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/libthread_db.so.1".
0xb6874918 in __GI___poll (fds=0x13ee428, nfds=18, timeout=-1) at ../sysdeps/unix/sysv/linux/poll.c:29

warning: 29	../sysdeps/unix/sysv/linux/poll.c: No such file or directory
$1 = 1
[Inferior 1 (process 555) detached]

RC=0
DONE
```

GDB 的原始输出包含缺少 poll.c 源码文件的 warning，未出现调用失败；XML 中 malloc_info/fclose 返回0且均 detach。所有输出原样保留，未以此修改实验。

## 4. 三次 pre smaps 块原文

### 第1次 pre

```text
00c92000-014c4000 rw-p 00000000 00:00 0          [heap]
Size:               8392 kB
KernelPageSize:        4 kB
MMUPageSize:           4 kB
Rss:                3392 kB
Pss:                3392 kB
Pss_Dirty:          3392 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:         0 kB
Private_Dirty:      3392 kB
Referenced:         3392 kB
Anonymous:          3392 kB
KSM:                   0 kB
LazyFree:              0 kB
AnonHugePages:         0 kB
ShmemPmdMapped:        0 kB
FilePmdMapped:         0 kB
Shared_Hugetlb:        0 kB
Private_Hugetlb:       0 kB
Swap:                  0 kB
SwapPss:               0 kB
Locked:                0 kB
THPeligible:           0
VmFlags: rd wr mr mw me ac
```

### 第2次 pre

```text
00c92000-014c2000 rw-p 00000000 00:00 0          [heap]
Size:               8384 kB
KernelPageSize:        4 kB
MMUPageSize:           4 kB
Rss:                3360 kB
Pss:                3360 kB
Pss_Dirty:          3360 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:         0 kB
Private_Dirty:      3360 kB
Referenced:         3360 kB
Anonymous:          3360 kB
KSM:                   0 kB
LazyFree:              0 kB
AnonHugePages:         0 kB
ShmemPmdMapped:        0 kB
FilePmdMapped:         0 kB
Shared_Hugetlb:        0 kB
Private_Hugetlb:       0 kB
Swap:                  0 kB
SwapPss:               0 kB
Locked:                0 kB
THPeligible:           0
VmFlags: rd wr mr mw me ac
```

### 第3次 pre

```text
00c92000-014c2000 rw-p 00000000 00:00 0          [heap]
Size:               8384 kB
KernelPageSize:        4 kB
MMUPageSize:           4 kB
Rss:                3360 kB
Pss:                3360 kB
Pss_Dirty:          3360 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:         0 kB
Private_Dirty:      3360 kB
Referenced:         3360 kB
Anonymous:          3360 kB
KSM:                   0 kB
LazyFree:              0 kB
AnonHugePages:         0 kB
ShmemPmdMapped:        0 kB
FilePmdMapped:         0 kB
Shared_Hugetlb:        0 kB
Private_Hugetlb:       0 kB
Swap:                  0 kB
SwapPss:               0 kB
Locked:                0 kB
THPeligible:           0
VmFlags: rd wr mr mw me ac
```

## 5. 原预测与判据核验

### prediction.txt 原文（未重写）

```text
H1：对每一次 trim，reclaimed_bytes == (present_pages_pre − present_pages_post) × 4096，精确相等。
H2：在同一进程上短时间内连续 trim 三次，第二、三次的 Δpresent_pages 与 reclaimed_bytes 均 ≤ 1 页。
H3：present_pages_pre × 4096 与同时刻 [heap] 的 Private_Dirty 相等，允许 ±2 页误差。
H4：[heap] 范围内 pagemap bit62（swapped）置位的页数为 0。
```

|判据|本次结果|实际核验|
|---|---|---|
|H1|三次均成立|32768=(848−840)×4096；0=(840−840)×4096；0=(840−840)×4096；差额均0字节。|
|H2|成立|第二、三次 Δpresent_pages 均0页，reclaimed_bytes 均0字节，均≤1页。|
|H3|三次均成立|848×4096 − 3392×1024 = 0字节；840×4096 − 3360×1024 = 0字节；840×4096 − 3360×1024 = 0字节；均在±8192字节内。|
|H4|成立|六次 pre/post 的 bit62 置位页数全部为0。|

## 6. 收尾复核原文

### 归档 data

```text

RC=0
DONE
```

### rm -rf /opt/usr/p0

```text

RC=0
DONE
```

### ls /opt/usr/p0

```text
ls: cannot access /opt/usr/p0: No such file or directory

RC=2
FAIL
```

### df -k /opt/usr

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mmcblk0p5       116404224    982792 115421432   1% /opt/usr

RC=0
DONE
```

### sdb root off

```text
Switched to 'sdk user' account mode
```

### id -u

```text
5001

RC=0
DONE
```

目录确认不存在；ls 的 RC=2/FAIL 对应预期的不存在结果。降权复核 UID=5001，收尾错误列表为空。

## 7. 原始文件与仓库约束

本地目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702

新原始文件及复用输入的路径、字节数、SHA-256 见 resume7_FILES.tsv；可用 resume7_SHA256SUMS 从该目录校验。三个 pre XML、六份 smaps/maps/stat/pagemap、auxv、完整 sdb 日志、状态与命令时间戳均保留；板端 data.tar 已回收并解到 resume7_data_extracted/。

读取命令 stderr 单独落在 data/*.err，18 个均为空；原样内容见 resume7_final_checks.json 的 stderr_files 与归档内各 .err 文件。

既有 2751 个普通文件的字节哈希与 mtime 均未变；git diff、暂存区均无改动，git status --porcelain 为空，local_review/ 仍由 .git/info/exclude 忽略。未 add/commit/push；未改任何已跟踪文件。板端本轮显式写入均位于 /opt/usr/p0/，未写 /tmp、未 remount、未安装或卸载 RPM。
