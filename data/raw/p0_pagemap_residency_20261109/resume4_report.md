# P0 两项测量与 zram 侦察：第四次续跑停止报告

执行日期：2026-11-09（Asia/Shanghai）。全部材料仅本地保存。

## 第 0 步：提权、三重身份与 uptime 原文

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
3085.29 12119.36

RC=0
DONE
```

镜像判定：RPI4 / armv7l / Tizen 11 Unified，
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l。
依据三重身份原文，不以 IP 判板。授权提权后 UID=0。
/proc/uptime 为 3085.29 12119.36，第一项为开机以来的秒数；尚未选择目标进程，无目标 starttime。

## 工具盘点与明确硬停依据

### 板端 command -v gdb dd grep pgrep ps 2>&1 原文

```text
/usr/bin/dd
/usr/bin/grep
/usr/bin/pgrep
/usr/bin/ps

RC=0
DONE
```

dd、grep、pgrep、ps 均有可执行路径；组合 command -v 返回 0，不能据此误判 gdb 存在。
对缺失的 gdb 单独查询原文：

```text

RC=1
FAIL
```

当前 shell PATH 中没有找到 gdb。没有扩大搜索、安装包或自行更换注入方案。

### demo-v14 仓库端原文

完整克隆核验：is-shallow-repository=false。
指定 commit 已核验：7289a47b9d24791944cd3b02c00f24b8cb76aa3b。

tools/reclaim_probe/trim_via_gdb.sh 的依赖判断与调用原文：

```sh
if ! command -v gdb >/dev/null 2>&1; then
    echo "GDB_UNAVAILABLE"
    exit 127
fi
```

该文件最终执行 exec gdb -p "$pid" -batch，并调用 malloc_trim(0) 后 detach；
并非不依赖 gdb 的自带注入器。完整原文保存在 resume4_source_trim_via_gdb.sh。

tools/runners/system_level_before_after_20260908/g4_m7.py 原文：

```python
"""Sourced by GDB, not a standalone Python CLI. No register convenience variables."""
import gdb
```

该工具的 XML 与 trim 路径依赖 GDB 模块及 gdb.parse_and_eval / gdb.execute，
没有可脱离 GDB 运行的注入实现。完整原文保存在 resume4_source_g4_m7.py。

tools/runners/tizen_native_evidence_20260904/README.md 原文：

> The helper fetches only the six SHA-pinned ARM RPMs from the official Base
> Toolchain `20260813.050338` snapshot.

原 README 的 GDB install and removal 节提供单独安装 GDB 包的流程；
这证明依赖需要另外安装，不代表本轮获准安装。完整原文保存在 resume4_source_README.md。

据本轮新增规则，板端无可用 gdb 且仓库所选注入工具也依赖 gdb，命中：
HARD_STOP_GDB_MISSING_AND_DEMO_V14_REQUIRES_GDB。
在第 0 步工具盘点结束时停止，不进入第 1–3 项。
本轮不是因 readelf 缺失而停止；grep 筛选与宿主 readelf 替代路线尚未执行。

## 收尾原文

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

已恢复 UID=5001。没有推送、执行脚本或写入板端结果文件。
本轮 mkdir -p /tmp/p0 尚未执行；上轮留下的空目录没有在本轮复查。
未遇到签名拒绝，不能据此判定镜像是否强制签名。

## 预测文件、时间与调用预算

沿用 prediction.txt，未重写、未新建。SHA-256 校验通过：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

原预测写入完成：2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端观测（uname -r）请求开始：2026-11-09T20:57:29.642625+08:00，host epoch ns 1794229049642624675。uptime 请求开始：2026-11-09T20:57:32.164179+08:00。均晚于预测文件写入。

时间来自开发机请求记录，不是板端时钟读数。
正式符号/堆测量尚未开始，没有首次 trim/pagemap 测量时间，不以身份查询冒充。
本轮 sdb 共 11 次调用（包含收尾），0 次重连、0 次通道失败；每次只有一个一次性调用。
实际相邻调用间隔（前次结束到下次开始）：0.500090274–0.500219492 秒，均 >=0.5 秒；最大 shell payload 为 100 字节。

## 第 1 项：符号扫描

未执行板端 grep 筛选，未拉取 ELF，未运行宿主 readelf。
libc.so.6 阳性对照：未检验，不能判通过或方法失效。
调用方/定义方命中清单、字符串误命中清单、重点目标 ls -l 均未采集。
不能写成“除 libc 外零命中”。

## 第 2 项：逐页驻留态与 trim

目标 PID、starttime 未采集；AT_SECURE 未读取；没有作废的 trim。

| 次序 | present 前/后 | swapped 前/后 | Private_Dirty 前/后 | Rss 前/后 | reclaimed_bytes | minflt/majflt 增量 | trim 返回值 | 注入耗时 | 注入方式 | XML |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |

H1：无法判定（未测量）。
H2：无法判定（未测量）。
H3：无法判定（未测量）。
H4：无法判定（未测量）。
没有实际值或差额，不填写虚构的 0。

## 第 3 项：zram 只读侦察

全部未执行：swaps、swappiness、meminfo、zram、PSI、cgroup、resourced 无本轮原始读数。
未采集不等于不存在。没有施压或启动实验负载。

## 资源、仓库与文件完整性

任务 scope 固定 CPU 0、1，cpu.max=200000 100000；
memory.max=1999998976（不超过 2 GB），memory.swap.max=0。全程串行。
未安装包、修改配置、attach、注入、kill、reboot 或运行实验负载。
本轮只执行授权提权及收尾、身份/uptime/工具查询。

本地目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

新增文件统一使用 resume4_ 前缀。所有旧文件的 SHA-256 与 mtime 均与续跑前一致，
包括 prediction.txt、report.md、FILES.tsv 及所有先前续跑材料。
git diff 与暂存区检查通过，git status --porcelain 输出为空；本目录仍被 local_review/ 忽略。
未 add、commit、push，未改动已跟踪文件。

全部文件路径、字节数与 SHA-256 见 resume4_FILES.tsv；
校验入口 resume4_SHA256SUMS（清单自身不纳入自身哈希）。
