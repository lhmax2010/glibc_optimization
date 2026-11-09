# P0 两项测量与 zram 侦察：连接门停止报告

执行日期：2026-11-09，时区 Asia/Shanghai。全部材料仅本地保存。

## 第 0 步：身份与 root 门

| 要求 | 原始输出 / 状态 |
| --- | --- |
| uname -r | 未执行：连接失败 |
| uname -m | 未执行：连接失败 |
| cat /etc/os-release | 未执行：连接失败 |
| id -u | 未执行：连接失败 |
| 镜像判定 | 无法判定；未用 IP 判板 |

本轮仅发起一次 sdb connect，没有建立任何 sdb shell 会话，没有重试连接。
连接请求的原始输出保存在 connect.raw，内容如下：

```text
error: failed to connect to remote target '<TEST_BOARD_IP>'
```

sdb 进程退出码为 0，但错误文本明确表示失败，因此按失败处理，停止全部后续板端操作。
现有证据不足以区分网络、服务、协议或授权问题，不猜测故障原因。

## 预测文件与先后顺序

prediction.txt 包含用户要求的 H1–H4 四条原文，没有更改判据。
SHA-256：ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14。

| 事件 | UTC | 本地时间（UTC+8） | host epoch ns |
| --- | --- | --- | --- |
| 预测文件写入完成 | 2026-11-09 11:17:02.673094 | 2026-11-09 19:17:02.673094 | 1794223022673093996 |
| 首次连接请求开始 | 2026-11-09 11:18:52.843151 | 2026-11-09 19:18:52.843151 | 1794223132843147348 |
| 连接失败、停止 | 2026-11-09 11:18:53.867316 | 2026-11-09 19:18:53.867316 | 1794223133867314701 |

时间戳由同一开发机记录，分别见 preflight.json、connect.json、state.json。
预测文件先于首次连接请求；本轮没有首次板上测量事件，不能伪造其时间戳。

## 未执行项

第 1 项没有开始。malloc_trim 命中清单与 readelf 失败清单均为未采集，不能写成“零命中”。

| trim 次序 | present 前/后 | swapped 前/后 | heap Private_Dirty 前/后 | reclaimed_bytes | minflt/majflt 增量 | 注入耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |
| 2 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |
| 3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 | 未执行 |

H1、H2、H3、H4 均为“无法判定：无测量数据”，不判成立或不成立。
AT_SECURE 未读取。malloc_info XML 未采集。
第 3 项 zram、swappiness、meminfo、PSI、cgroup、resourced 侦察全部未执行，无板端原文。

## 本地准备与资源约束

使用现有完整克隆：git rev-parse --is-shallow-repository 输出 false。
demo-v14^{commit} 实测为 7289a47b9d24791944cd3b02c00f24b8cb76aa3b，与指定值一致。
只读查看了该 commit 的 tools/reclaim_probe/trim_via_gdb.sh；未改写或执行注入器。
host_session.py 仅为本地连接/取证驱动，不是注入器；每个远端请求发送前检查完整 payload 不超过 200 字节，无自动重连。

资源门第一次读取用户 cgroup 的 cpuset.cpus.effective 时因该文件不存在退出；没有连接板子。
仅进行一次本地资源门重试：taskset 固定 CPU 0、1，实际限制核验如下：

```json
{"cpu.max":"200000 100000","memory.max":"2147483648","memory.swap.max":"0","affinity":[0,1]}
```

通过后，本地准备、sdb connect 与后续归档命令均在该受限 scope 的进程树中串行执行。
没有并行 sdb 会话，没有高频短连接，没有向板子推送/写入文件。
没有执行 root on、attach、trim、安装、配置修改、负载或 reboot。

## 仓库与原始件

目录：/home/linhao/Toolchain/development/glibc_optimization/local_review/p0_pagemap_zram_20261109_191702/

git diff --quiet 与 git diff --cached --quiet 均返回 0；git status --porcelain 输出为空。
本目录命中 .git/info/exclude 第 7 行 local_review/；见 final_git_checks.json。
未执行 git add、commit、push，未修改已跟踪文件。

全部本地文件的字节数与 SHA-256 见 FILES.tsv；可用 SHA256SUMS 校验。
停止原因：STOP connect: transport failed。须恢复连接后才能继续，未自行更换连接方式或方案。
