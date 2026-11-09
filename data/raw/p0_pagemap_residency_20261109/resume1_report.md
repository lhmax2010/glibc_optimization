# P0 测量与 zram 侦察续跑：工作会话断开

执行日期：2026-11-09，Asia/Shanghai。全部材料仅本地保存。

## 第 0 步原文

### uname -r

```text
6.12.80-arm-rpi4-v7l
```

### uname -m

```text
armv7l
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
```

### id -u

```text
0
```

镜像判定：RPI4 / armv7l / Tizen 11 Unified，BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l。依据三项原文，不依据 IP 或设备列表名称。UID=0；未执行提权。四项均收到 RC=0 DONE。

## 预测文件与时间证据

沿用 prediction.txt，未重写或新建预测文件。SHA-256 校验通过：

ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14

原预测写入完成：2026-11-09 19:17:02.673094（UTC+8），host epoch ns 1794223022673093996。
本次首次板端读取为身份查询 uname -r：请求开始于 2026-11-09 19:40:47.223409（UTC+8），host epoch ns 1794224447223408927；完整回执收到于 19:40:47.437580。
时间来自 host，见 resume1_uname_r.json；严格晚于预测文件写入。
第 1–3 项实验测量均尚未开始，不能将身份查询时间冒充首次 trim/pagemap 测量时间。

## 停止原因

连接成功，只建立一个 sdb shell 工作会话。身份与 UID 查询成功后，在 19:41:36.724737 尝试发送 command -v readelf；写入会话 stdin 报错：

```text
[Errno 32] Broken pipe
```

未收到该命令的远端 RC/DONE；是否到达或执行无法确认。
工作会话主机退出码为 0，但不能据此判成功。停止，不重连、不重跑。
session.raw 未包含能解释断开原因的明确错误，不推断网络、板端或 host 根因。
见 resume1_state.json、resume1_session_end.json、resume1_commands.jsonl。

## 第 1 项

未开始符号扫描。命中清单、readelf 失败文件清单均未采集，不得记作零命中。
未推送或执行板端脚本，未遇到签名拒绝；不能据此判定镜像是否强制签名。

## 第 2 项

| 次序 | present 前/后 | swapped 前/后 | heap Private_Dirty 前/后 | reclaimed_bytes | minflt/majflt 增量 | 注入耗时 |
|---|---|---|---|---|---|---|
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |

H1、H2、H3、H4 均无法判定（无数据），不判成立/不成立。
目标尚未选择；AT_SECURE 未读取；没有 malloc_info XML 或 trim 返回值。

## 第 3 项

zram、swaps、swappiness、meminfo、PSI、cgroup、resourced 全部未执行，无可报告的原样输出。

## 约束与证据

开发机任务 scope：cpu.max=200000 100000；affinity=[0,1]；
memory.max=1999998976（不超过 2 GB）；memory.swap.max=0。串行执行。
每条已提交/尝试提交的板端请求为 125–139 字节（含标志），均不超过 200 字节。
现有仓库是完整克隆（is-shallow-repository=false），demo-v14 commit 核验为
7289a47b9d24791944cd3b02c00f24b8cb76aa3b。没有执行或改写注入工具。
没有任何实验负载、安装、配置修改、注入、attach、kill、reboot 或板端文件传输/创建命令。

本地目录：
/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

续跑新文件使用 resume1_ 前缀。原有全部 10 个文件（包括 prediction.txt、report.md、FILES.tsv）
逐文件哈希与续跑前一致。已跟踪文件及暂存区无变化，git status --porcelain 输出为空，
目录仍命中 local_review/ 排除规则。未执行 git add/commit/push。

本地归档时另遇到 PTY 长输入截断导致 JSON 解析失败；没有执行该次报告写入，
已改用受同等资源限制的非 PTY 命令完成归档。不涉及板端重试或改变实验方案。

全部文件字节数与 SHA-256 见 resume1_FILES.tsv，校验清单为 resume1_SHA256SUMS；
清单自身不包含自己的哈希。
