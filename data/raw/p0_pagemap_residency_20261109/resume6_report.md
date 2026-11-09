# P0 第六次续跑报告

执行日期：2026-11-09（Asia/Shanghai）。全部材料仅本地保存。

第 1 步 ELF 符号确认完成；第 2 步六包校验、便携 GDB 解包和依赖/版本验证完成。
第 3 步在首次 pre 的 heap 字段完整性检查处停止：固定 grep -A20 输出缺少 SwapPss。
未扩展读取范围、未改判据，未执行 XML 注入或任何 malloc_trim。
全部收尾通过，/opt/usr/p0 已删除，UID 已恢复 5001。

## 0. 提权、三重身份与分区盘点原文

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

### cat /proc/uptime（开始）

```text
7494.36 29489.78

RC=0
DONE
```

### grep MemTotal /proc/meminfo

```text
MemTotal:        3976468 kB

RC=0
DONE
```

### command -v dd grep pgrep ps tar 2>&1

```text
/usr/bin/dd
/usr/bin/grep
/usr/bin/pgrep
/usr/bin/ps
/usr/bin/tar

RC=0
DONE
```

### df -k /opt/usr（开始）

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mmcblk0p5       116404224    982792 115421432   1% /opt/usr

RC=0
DONE
```

### grep " /opt/usr " /proc/mounts

```text
/dev/mmcblk0p5 /opt/usr f2fs rw,lazytime,relatime,background_gc=on,nogc_merge,discard,discard_unit=block,user_xattr,inline_xattr,acl,inline_data,inline_dentry,flush_merge,barrier,extent_cache,mode=adaptive,active_logs=6,alloc_mode=default,checkpoint_merge,fsync_mode=posix,memory=normal,errors=continue 0 0

RC=0
DONE
```

镜像判定为 RPI4 / armv7l / Tizen 11 Unified，
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l。
依据三重身份原文，不使用 IP 判板。提权后 UID=0。
/opt/usr 是 /dev/mmcblk0p5 的 f2fs 挂载，rw、无 noexec，
可用 115421432 KiB，满足 500 MB 门。本轮未写 /tmp，未 remount，未执行任何 RPM 安装/卸载。

## 1. 预测文件、时间与调用预算

原 prediction.txt 未重写、未新建，SHA-256 校验值：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

原预测写入完成于 2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端观测（uname -r）请求开始：2026-11-09T22:10:58.578776+08:00，host epoch ns 1794233458578775617。
本次首次 heap 测量请求开始：2026-11-09T22:19:23.353877+08:00，host epoch ns 1794233963353876398。两者均严格晚于预测写入。
时间为开发机记录的请求开始时刻，不是板端时钟读数。
共 40 次 sdb 调用，0 次重连、0 次通道失败；相邻调用实测间隔（结束到下次开始）0.500067571–264.492442536 秒，均 >=0.5 秒。最大 shell payload 170 字节。

本轮未重做 resume5 的 zram 侦察或字符串筛选，按指令复用两个命中清单。
其中可执行文件输入来自 resume5 的 RC=2 部分结果，因此本轮是对“这份给定清单”的符号确认，
不是重新完成了全平台枚举。libc.so.6 阳性对照沿用 resume5 已通过的证据，本轮按指令从清单删除该定义方。

## 2. 逐文件 readelf 确认

31 条路径全部成功拉回并由宿主 readelf 解析：30 条 UND 导入路径，1 条定义路径；
字符串误命中 0，readelf 失败 0，归档缺失文件 0。
路径计数包含 .so 链接名与其版本实体名，不能等同于独立二进制数量。
UND 说明静态导入，不证明本轮运行时实际调用过 malloc_trim。

### hits_tar.err 原文

```text
tar: Removing leading '/' from member names
```

该 tar 提示仅说明归档成员名去掉前导 /；不是文件缺失。归档拉回后做了逐文件 readelf 与哈希。

| 板端路径 | 符号行原文 | 判定 |
|---|---|---|
| /usr/bin/bt-service | <code>   474: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/bin/contacts-service-ipcd | <code>   157: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/bin/isf | <code>   306: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/bin/isf-panel-efl | <code>   306: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/bin/media-server | <code>   128: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/bin/pushd | <code>   233: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/bin/resourced | <code>   250: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/bin/tizen-watcherd | <code>   278: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libamd.so.1 | <code>   259: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libamd.so.1.82.15 | <code>   259: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libapp-core-cpp.so.1 | <code>    69: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libapp-core-cpp.so.1.28.10 | <code>    69: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libappcore-common.so.1 | <code>    45: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libappcore-common.so.1.28.10 | <code>    45: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libbluetooth.default.so | <code>   202: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libbluetooth.default.so.1 | <code>   202: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libbluetooth.default.so.1.0.0 | <code>   202: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libc_malloc_debug.so.0 | <code>    71: 00007178   104 FUNC    GLOBAL DEFAULT   13 malloc_trim@GLIBC_2.4</code> | 定义方 |
| /usr/lib/liblaunchpad.so.0 | <code>    85: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/liblaunchpad.so.0.51.7 | <code>    85: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libmuse-server.so.0 | <code>   180: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/lib/libmuse-server.so.0.6.1 | <code>   180: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/lib/libnntrainer.so | <code>   439: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (5)</code> | 调用方（UND 导入） |
| /usr/lib/libpipewire-0.3.so.0 | <code>   112: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libpipewire-0.3.so.0.1600.0 | <code>   112: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)</code> | 调用方（UND 导入） |
| /usr/lib/libpkgmgr-info-server.so.0 | <code>   261: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libpkgmgr-info-server.so.0.37.5 | <code>   261: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libscim-1.0.so.8 | <code>   153: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libscim-1.0.so.8.2.3 | <code>   153: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)</code> | 调用方（UND 导入） |
| /usr/lib/libscl-core.so | <code>    40: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)</code> | 调用方（UND 导入） |
| /usr/lib/libtrackrenderer.so | <code>   144: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (6)</code> | 调用方（UND 导入） |

### 四个重点目标

**/usr/bin/resourced：调用方（UND）**

```text
   250: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (2)
```

**/usr/lib/libappcore-common.so.1：调用方（UND）**

```text
    45: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (4)
```

**/usr/lib/libapp-core-cpp.so.1：调用方（UND）**

```text
    69: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)
```

**/usr/lib/liblaunchpad.so.0：调用方（UND）**

```text
    85: 00000000     0 FUNC    GLOBAL DEFAULT  UND malloc_trim@GLIBC_2.4 (3)
```

ELF 位于 resume6_elf/extracted/usr/，逐个 readelf 全输出为 resume6_readelf_XX.raw；
结构化结果为 resume6_symbols.json。没有把 ELF 放入 Git。

## 3. 六个 RPM 的来源与校验

六包均从本轮唯一指定的 Base Toolchain 20261030.120529 官方仓库重新下载，
缓存目录为本轮新建的 resume6_rpms/；未使用 GBS-ROOT 或其他 session 的 RPM 缓存。
由指定 packages/armv7l/ 索引定位到同仓库 packages/repodata/，保存了索引与 HTTP 请求记录。
repodata revision：1793378577。repomd.xml SHA-256：e432f1c6ab0d1278222e4ca24035bcd828289385ef28594877913f75a62365ac。
primary 元数据 URL：http://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/tizen-base-toolchain_20261030.120529/repos/standard/packages/repodata/b3ec543a10f9d593f50a226248910b1f7fd205e118e878014b3a405570f907aa-primary.xml.gz。
primary 校验值（sha256）：b3ec543a10f9d593f50a226248910b1f7fd205e118e878014b3a405570f907aa，与 repomd.xml 一致。

| RPM 文件 | 字节数 | 下载 SHA-256（与 primary.xml 记录精确一致） | 判定 |
|---|---:|---|---|
| gdb-16.3-1.2.armv7l.rpm | 2658309 | 3faf73b5fcad87e4d5f32220a0b7c95ad209749adc97f5937d1bcabb2a93eb1a | PASS |
| libgmp-4.2.1-1.13.armv7l.rpm | 104317 | 5a3445861b9f548c1e746d5539ac9d1bc4bf102ab43ac9cdfd12b1ece79455a7 | PASS |
| gdbm-1.8.3-1.16.armv7l.rpm | 22389 | 2a7bb048072ad2c8a019a0076472bea67c7709e429d371efc29f9f0ef0edb6da | PASS |
| libpython3_141_0-3.14.2-1.11.armv7l.rpm | 1196761 | 1728d49d13b673d3e5a64872eb1c4020b457b1491222ca408b98dab1ec10704d | PASS |
| python3-base-3.14.2-1.11.armv7l.rpm | 7167269 | 331e0ff8fb9f1be2c65eaf3671b6906e8f0b84a432d46be23de32e411c322c25 | PASS |
| python3-3.14.2-1.12.armv7l.rpm | 1971789 | 45baa1a16f125566ee93c920ee20d087082538f78a695ec48e44e67cb2d0d317 | PASS |

每包预期/实际哈希与大小分别保存于 resume6_rpm_verification.json，原 metadata 选择结果见 resume6_rpm_metadata_selected.json。

### 宿主独立解包与 tar

六个 RPM 按指定顺序用 rpm2cpio | cpio -idm 解到本轮独立空目录 resume6_gdb_build/gdbroot/；两端退出码均为 0。未安装 RPM。
gdbroot.tar：54579200 字节，SHA-256 ab4f53de6506a3597479008510b80e870de140e9b995a527c08b8288b146e736。宿主文件名为 resume6_gdbroot.tar。

### GDB 加载器依赖检查原文

### LD_TRACE_LOADED_OBJECTS=1 LD_LIBRARY_PATH=/opt/usr/p0/gdbroot/usr/lib /opt/usr/p0/gdbroot/usr/bin/gdb 2>&1

```text
	linux-vdso.so.1 (0xbef5c000)
	libexpat.so.1 => /lib/libexpat.so.1 (0xb6f4b000)
	libtinfow.so.6 => /lib/libtinfow.so.6 (0xb6f2c000)
	libncursesw.so.6 => /lib/libncursesw.so.6 (0xb6f0d000)
	libpython3.14.so.1.0 => /opt/usr/p0/gdbroot/usr/lib/libpython3.14.so.1.0 (0xb6b8f000)
	libm.so.6 => /lib/libm.so.6 (0xb6b41000)
	libstdc++.so.6 => /lib/libstdc++.so.6 (0xb69a3000)
	libgcc_s.so.1 => /lib/libgcc_s.so.1 (0xb6988000)
	libc.so.6 => /lib/libc.so.6 (0xb6826000)
	/lib/ld-linux.so.3 (0xb6f77000)

RC=0
DONE
```

没有 not found，也没有 Permission denied。

### GDBENV gdb -nx -nh -batch -ex "show version" 2>&1 | head -3

```text
GNU gdb (GDB) 16.3
Copyright (C) 2024 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>

RC=0
DONE
```

包含 GNU gdb (GDB) 16.3，版本门通过。
为使完整 shell payload（含 RC/DONE/FAIL 回执）不超过 200 字节，
把指定 PATH、LD_LIBRARY_PATH、PYTHONHOME 和 EXPECTED_BUILD_ID 原值写入
/opt/usr/p0/environment，每次实际 GDB 调用用 . /opt/usr/p0/environment 设置该调用的环境；
没有更改这些值或系统配置。原文件内容保存在 resume6_gdb_environment.txt。

## 4. 目标、首次 heap 片段与停止证据

目标：enlightenment，PID=555；按 pgrep -x enlightenment 选择，未使用替代目标。
stat 第 22 字段 starttime=1581 时钟滴答。目标选择时 /proc/uptime 原文：7994.74 31451.11。
目标选择时累计 minflt=5670、majflt=129；这是生命周期累计计数，不是 trim 增量。

### cat /proc/555/stat（目标年龄原始记录）

```text
555 (enlightenment) S 1 555 555 0 -1 4194560 5670 0 129 0 1848 1164 0 0 20 0 8 0 1581 193613824 4704 4294967295 4743168 6440068 3201621088 0 0 0 2561 4096 92679 0 0 0 17 2 0 0 0 0 0 6443008 6479004 13180928 3201621389 3201621412 3201621412 3201621989 0

RC=0
DONE
```

### cat /proc/uptime（目标选择时）

```text
7994.74 31451.11

RC=0
DONE
```

### grep -A20 "\[heap\]" /proc/555/smaps（经 tee 同时保存为数据文件）

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

RC=0
DONE
```

固定 -A20 输出为 [heap] 头部加 20 行，止于 Swap；未包含任务要求的 SwapPss。
这是采集截断造成的字段不完整，不能推断内核没有该字段。
本轮未扩大行数、未补读后续字段，按测量异常停止。
已知片段：Size=8392 kB，Rss=Pss=Private_Dirty=3392 kB，Swap=0 kB。
没有读取 pagemap，因此不能用 smaps 的 Swap=0 代替 H4 的 bit62 验证。

### 逐次 trim 表

| 次序 | present 前/后 | swapped 前/后 | Private_Dirty 前/后（kB） | Rss 前/后（kB） | reclaimed_bytes | minflt/majflt 增量 | trim 返回值 | 注入耗时 | XML |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 未测/未测 | 未测/未测 | 3392/未测（pre 不完整） | 3392/未测（pre 不完整） | 无法计算 | 未测 | 未执行 | 未测 | 未采 |
| 2 | 未测/未测 | 未测/未测 | 未测/未测 | 未测/未测 | 未测 | 未测 | 未执行 | 未测 | 未采 |
| 3 | 未测/未测 | 未测/未测 | 未测/未测 | 未测/未测 | 未测 | 未测 | 未执行 | 未测 | 未采 |

三个 XML 命令文件已按指定 demo-v14 inject_malloc_info 的五行模板生成并推送，
只有 XML 路径改为 /opt/usr/p0/data/tN_pre.xml；原 trim_via_gdb.sh 也已按指定 commit 推送。
因停止发生在首次 smaps 字段检查，以上注入命令均未执行；没有 attach 或 trim，
没有发生“trim 已发出但 post 未完成”的作废情形。

H1：无法判定，无完整 pre/post 与 pagemap。
H2：无法判定，没有执行三次 trim。
H3：无法判定，没有 present_pages 数据。
H4：无法判定，没有 pagemap bit62 数据。
该停止不等于任一假设被证伪。

### AT_SECURE

AT_SECURE（auxv type 23）实测值为 **0**，原始文件 resume6_auxv_a0.bin，解析结果 resume6_auxv.json。

auxv 的原始 type 6=4096、type 17=100 同样保存在解析文件中；未用假定时钟频率计算目标年龄。

## 5. 收尾复核原文

### cd /opt/usr/p0 && tar cf data.tar data

```text

RC=0
DONE
```

### rm -rf /opt/usr/p0

```text

RC=0
DONE
```

### ls /opt/usr/p0 2>&1

```text
ls: cannot access /opt/usr/p0: No such file or directory

RC=2
FAIL
```

### df -k /opt/usr（收尾）

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

### id -u（收尾）

```text
5001

RC=0
DONE
```

收尾 complete=true、错误列表为空。/opt/usr/p0 确认不存在，UID=5001。
data.tar 已拉回并解到 resume6_data_extracted/，保留 auxv.bin 与不完整的 t1_pre_smaps.txt。
本轮没有执行任何 RPM 安装或卸载；没有写 /tmp、没有 remount。
板端命令的显式写入目标全部位于 /opt/usr/p0/，包含便携 GDB、命令文件和采集文件。

## 6. 本地文件、来源与仓库纪律

目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

源码来自完整克隆的 demo-v14 commit 7289a47b9d24791944cd3b02c00f24b8cb76aa3b，
未改动已跟踪文件。原预测和此前全部文件的字节哈希与 mtime 保持不变。
git diff / 暂存区检查通过，git status --porcelain 输出为空；
目录仍命中 local_review/ 本地忽略规则，未执行 git add、commit 或 push。

执行 scope 固定 CPU 0、1，cpu.max=200000 100000，
memory.max=1999998976（不超过 2 GB），memory.swap.max=0；SDB 调用全部串行。
没有其他负载、进程重启或板端配置更改。

全部普通文件（含旧证据、ELF、RPM、解包产物）的本地相对路径、字节数与 SHA-256
见 resume6_FILES.tsv；配合本节目录即得到绝对路径，可由 resume6_SHA256SUMS 校验。
解包树中的符号链接单独记录在 resume6_SYMLINKS.json，记录链接文本而不跟随到外部路径。
清单文件自身不纳入自身哈希。
