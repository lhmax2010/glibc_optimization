# P0 两项测量与 zram 侦察：第三次续跑停止报告

执行日期：2026-11-09（Asia/Shanghai）。全部材料仅本地保存。

## 提权、三重身份与堆年龄上下文原文

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
2016.87 7906.97

RC=0
DONE
```

镜像判定：RPI4 / armv7l / Tizen 11 Unified，BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l。
依据以上三项原文，不依据 IP 或设备列表名称。按本轮明确授权执行 root on 后，实测 UID=0。
/proc/uptime 原文为 2016.87 7906.97；第一项为开机后经过的秒数，第二项为累计空闲时间。
尚未选取目标进程，故无目标 PID 或第 22 字段 starttime，不估算目标进程年龄。

## 停止门与收尾

mkdir -p /tmp/p0 成功，随后 ls -la 显示只有 . 与 ..。扫描前检查 command -v readelf，远端原文：

```text

RC=1
FAIL
```

远端 RC=1 / FAIL，当前 shell 的 PATH 中未找到 readelf。
这不等于证明全盘不存在该文件；本轮不扩大搜索、不更换工具、不安装包，按工具错误停止。
尚未执行用户指定的四条扫描循环，不把未执行记作“零命中”。
sdb 主机退出码不足以判成功，本轮以远端 RC/DONE/FAIL 及错误文本判定。

停止后只撤销本轮提权并核验 UID，未继续实验：

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

已恢复 UID=5001。板上保留本轮建立的空目录 /tmp/p0；没有生成扫描、脚本或测量文件。

## 预测文件、时间与调用预算

沿用原 prediction.txt，未重写、未新建。SHA-256 校验值：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

原预测写入完成于 2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端观测（uname -r）请求开始：2026-11-09T20:39:41.276903+08:00，host epoch ns 1794227981276902625。首次堆年龄上下文采集（/proc/uptime）请求开始：2026-11-09T20:39:43.785370+08:00。二者均严格晚于预测文件写入。

时间均为开发机记录的请求时间，非板端时钟读数；第 1–3 项正式实验测量尚未开始，没有首次 trim/pagemap 测量时间。
sdb 总调用 12 次（包括 root off 和 UID 收尾核验），上限 150；重连 0 次，通道失败 0 次。
每次新连接均执行 root on 与三重身份/UID 检查；本轮仅一次连接，没有遗漏的重连身份记录。
相邻调用实测间隔（上次结束至下次开始）0.500077594–47.364656808 秒，均 >=0.5 秒；实际最大 shell payload 为 83 字节。

## 第 1 项

malloc_trim 命中清单、readelf 逐文件失败清单、重点目标 libappcore/libcapi-appfw/resourced 的 ls -l 均未采集。
阻塞发生在 readelf 工具可用性门，不是某个 ELF 的扫描失败；不可生成虚假的“零命中”或失败文件列表。

## 第 2 项

| 次序 | present 前/后 | swapped 前/后 | Private_Dirty 前/后 | Rss 前/后 | reclaimed_bytes | minflt/majflt 增量 | trim 返回值 | 注入耗时 | 注入方式 | XML |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 | 未测量 | 未使用 | 未采 |

H1：无法判定（无测量数据）。
H2：无法判定（无测量数据）。
H3：无法判定（无测量数据）。
H4：无法判定（无测量数据）。
目标 PID、starttime 未采集；AT_SECURE 未读取；没有发生 trim，也没有作废的 trim。

## 第 3 项

swaps、swappiness、MemTotal/MemFree/MemAvailable/SwapTotal/SwapFree、zram、PSI、cgroup、resourced 全部未采集。
未采集不等于“不存在”。未施压、未改配置、未启动实验负载。

## 来源、资源与仓库约束

完整克隆核验：is-shallow-repository=false。
demo-v14 commit：7289a47b9d24791944cd3b02c00f24b8cb76aa3b；未改写、推送或执行注入工具。
新驱动 resume3_driver.py 仅编排串行 SDB 调用，不包含新注入器。
未触发签名校验，不能据此判断该镜像是否强制签名。

资源 scope：CPU 固定 0、1，cpu.max=200000 100000，memory.max=1999998976（不超过 2 GB），memory.swap.max=0。
所有 SDB 调用串行，没有交互式长会话或并发会话。
除了授权的 root on/off、身份/uptime/工具查询与建立空目录，没有任何其他板端实验操作。
没有安装/删除包、attach、kill、reboot 或 trim。

材料目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

本轮全部新文件使用 resume3_ 前缀；此前所有文件（包括 prediction.txt、report.md、FILES.tsv 与 resume1_/resume2_ 文件）的哈希及 mtime 保持不变。
git diff 与暂存区检查通过，git status --porcelain 输出为空；本目录继续被 local_review/ 排除规则忽略。
未 git add、commit、push；未改动已跟踪文件。

全部文件的字节数与 SHA-256 见 resume3_FILES.tsv；校验入口为 resume3_SHA256SUMS（清单自身不纳入自身哈希）。
需用户决定如何满足 readelf 工具前置；本轮未自行调整方案。
