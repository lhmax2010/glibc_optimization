# P0 两项测量与 zram 侦察：第二次续跑停止报告

执行日期：2026-11-09（Asia/Shanghai）。仅本地保存，不提交。

## 第 0 步：身份原文与 root 门

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
5001

RC=0
DONE
```

镜像判定：RPI4 / armv7l / Tizen 11 Unified，BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l。
依据 uname 与 os-release 原文，不使用 IP 判板。当前 UID=5001，不是 root；上次续跑记录的 UID=0 不能沿用。
停止原因：STOP_ROOT_REQUIRED 5001。没有执行 sdb root on，不自行提权。

## 连接、调用预算与预测文件

本次只有首次连接，没有通道失败，没有重连，没有并行 sdb。每个命令均使用一次性 shell。
sdb 总调用次数：5（连接一次、身份与 UID 四次），上限 150。
重连次数：0；重连原因清单为空，原因是没有发生通道失败。
实际相邻调用间隔（上次结束到下次开始）为 0.500160615–0.500337062 秒，均 >=0.5 秒。最大 shell payload 83 字节。

原 prediction.txt 未重写、未新建。SHA-256 与指定值精确一致：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

预测文件写入完成：2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端读取（身份查询 uname -r）请求开始：2026-11-09T20:19:01.335595+08:00，host epoch ns 1794226741335595320，严格晚于预测写入。UTC 原始时间为 2026-11-09T12:19:01.335575+00:00。
这是主机记录的板端身份读取请求时刻，不是板端时钟读数。第 1–3 项实验测量尚未开始，无首次 trim/pagemap 测量时间，不能伪造。

## 第 1 项：导入符号扫描

未执行；malloc_trim 命中清单、readelf 失败文件清单及重点目标 ls -l 均未采集。
不能写成“零命中”。未创建 /tmp/p0，未写入、拉取任何板端文件。

## 第 2 项：三次 trim 与判据

| 次序 | present 前/后 | swapped 前/后 | Private_Dirty 前/后 | Rss 前/后 | reclaimed_bytes | minflt/majflt 增量 | trim 返回值 | 注入耗时 | 注入方式 | XML |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |

H1：无法判定（未测量）。
H2：无法判定（未测量）。
H3：无法判定（未测量）。
H4：无法判定（未测量）。
没有作废的 trim，没有选定目标进程。AT_SECURE 未读取。

## 第 3 项：zram 只读侦察

全部未执行，无 swaps/swappiness/meminfo/zram/PSI/cgroup/resourced 输出。
未采集不等于“不存在”。

## 本地来源与资源限制

完整克隆核验：git rev-parse --is-shallow-repository = false。
demo-v14^{commit} = 7289a47b9d24791944cd3b02c00f24b8cb76aa3b。
该提交的 trim_via_gdb.sh 已只读导出为 resume2_demo_v14_trim_via_gdb.sh，未修改、推送或执行。
本地驱动为 resume2_driver.py，无新注入器。
本轮没有触发签名校验，不能判断镜像是否强制签名。

任务 scope 固定 CPU 0、1，cpu.max=200000 100000，memory.max=1999998976（不超过 2 GB），memory.swap.max=0。
全部执行串行，没有安装、配置更改、注入、attach、kill、重启或负载。

## 本地证据与仓库

目录：/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/
本轮新文件统一 resume2_ 前缀。原有全部文件的字节哈希与 mtime 均保持不变，包括原预测文件、report.md、FILES.tsv 及 resume1_ 材料。
git diff、暂存区检查通过；git status --porcelain 输出为空；目录仍被 local_review/ 排除规则忽略。
未执行 git add、commit、push，未修改已跟踪文件。

全部文件（包含此前两次停止记录）的字节数与 SHA-256 见 resume2_FILES.tsv；
校验入口为 resume2_SHA256SUMS。清单自身不纳入自身哈希。
下一步阻塞：须先满足用户明确要求的 root 硬门。未自行调整方案或继续任何后续项目。
