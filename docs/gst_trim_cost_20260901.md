> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# GStreamer 并发解码目标的 trim 回收与业务代价

> **2026-09-03 验收语义修正：** §1.4 的 nearest-rank、三重复中位、none
> `max−min` 离散带与严格 `>` 规则保持不变；workflow 只把“规则是否正确执行”作为
> PASS/FAIL，所得 p99 方向改为 `REPORT_ONLY`。本批仍如实记录
> `visible=false`，但该方向不是交付验收通过条件；若复跑得到 `visible=true`，须保留
> 三重复原值、报告越过离散带的 margin，并作为批次业务代价发现上报。

- 日期：2026-09-01
- 板端：`<TEST_BOARD_IP>`（SDB/26101；禁止用地址判板）
- 状态：规格已在建连前冻结；6 格执行、完整性、健康与现场恢复门全部完成
- 目标：补齐 S4 遗留的真实多线程目标回收、再激活业务时延与全 arena 调用代价证据

## 1. 建连前冻结规格

本节于 `2026-09-01T20:53:36+08:00`、仓库 `ceb4115` 基线上写定；写定时尚未建立
本轮 SDB 连接。后续不得依据首轮结果调整参数、样本剔除、统计口径或判断阈值。

### 1.1 目标、资产与构建

- 目标：[`tools/gst_loop_decode/gst_loop_decode.c`](../tools/gst_loop_decode/gst_loop_decode.c)，
  继续使用 `filesrc → qtdemux → queue → mpeg4videoparse → avdec_mpeg4 → fakesink`
  的软解循环和 `PLAYING → NULL` 释放相位。
- 媒体资产：沿用 `l6_gst_release_phase_20260811` 的 `small_320x240.mp4`，冻结
  SHA-256 为 `3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d`；
  资产只进入 `/opt/usr` 固定工作目录。
- 本轮 instrumented 源码 SHA-256：
  `4b00e4ad7fb38c5e51c772e1ba0d8a7d7eb44045d45ec34978317ecaae5d9552`；
  ARMv7L 二进制 SHA-256：
  `204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6`。
- 分类器沿用 [`reclaim_probe`](../tools/reclaim_probe/reclaim_probe.c)，ARMv7L 二进制
  SHA-256 为 `3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7`。
- host 交叉构建固定使用同源 Tizen GCC `14.2.0`、`-std=c99 -O2 -g -Wall
  -Wextra -Werror`，只链接 `libgstreamer-1.0.so.0`、`libgobject-2.0.so.0`、
  `libglib-2.0.so.0`、pthread 与 libc。板上 `ldd`/smoke 是执行前硬门。

### 1.2 冻结矩阵与顺序

| arm | 触发语义 | 重复 | 每重复循环 |
|---|---|---:|---:|
| `none` | 每轮 NULL 释放后只做同口径 pre/post 采集，不调用 trim | 3 | 51 |
| `trim-at-loop-release` | 每轮 NULL 完成且 pre 采集结束后立即调用一次 `malloc_trim(0)` | 3 | 51 |

固定顺序为 `none-r1 → trim-r1 → trim-r2 → none-r2 → none-r3 → trim-r3`
（ABBAAB），用于抵消单向温漂/时序漂移；禁止改成分臂整块执行。每轮参数固定为：

```text
gst_loop_decode small_320x240.mp4 51 20 1 <arm> control-stdin
```

第 1 轮是首次进入负控，完整保留但不进入业务代价主统计；主统计固定使用第 2–51 轮
共 50 个“受上一轮 release/trim 影响的再激活”样本。每轮业务墙钟定义为本轮
`PLAYING_REQUEST` 前到 `NULL_DONE` 后的单调时钟差，包含 PLAYING/NULL 状态切换与固定
20 s PLAYING 窗口，不包含本轮 pre/post smaps 协调、trim 调用及 1 s valley。

### 1.3 冻结采集字段

每格必须同时取得：

- 51 轮 `business_elapsed_ns`，以及循环内 `minflt/majflt`；
- 51 次 action 记录；trim 臂保存每次 `malloc_trim(0)` 返回值与 `elapsed_ns`，none
  臂必须是未调用哨兵；
- 每轮 release 的 pre/post `reclaim_probe profile` JSON，派生 glibc-heap PD 回收量；
- bench 全程 1 s 外部序列，分类口径与 S2/S4 相同；
- bench/sampler/controller 退出码与远端 `RC=0`、`DONE_*`；
- 全轮前后 dmesg、zram `mm_stat`、swap、四核 governor 与时间记录。

### 1.4 冻结统计量与判断规则

- 单重复业务墙钟的 p50/p95/p99 使用 nearest-rank：排序后取
  `ceil(p × n)`，主样本 `n=50`；因此 p99 是该重复主样本的最大观测值，报告必须保留
  这一有限样本限制。
- 每个 arm 先报告三个重复各自的 p50/p95/p99，再报告三个重复统计量的中位数与
  `max−min` 离散带。臂间差固定为 `median(trim) − median(none)`。
- 业务代价可见性方向的预登记计算规则：
  `Δp99 = median(trim 三重复 p99) − median(none 三重复 p99)`；仅当
  `Δp99 > max(none p99) − min(none p99)` 时判“可见”，否则判“未越过本批基线重复
  离散带”。依据是先要求臂间位移严格大于同批 none 的 run-to-run 抖动；不使用结果后
  选择的固定百分比门。交付验收只校验该计算是否正确执行，方向结果
  `REPORT_ONLY`；该结果不是等价性或产品 SLA 证明。
- trim 耗时报告 p50/p95/p99/max 和逐重复分布；回收报告每轮 kB、每重复中位及范围；
  faults 报每轮和每重复汇总，majflt 必须单列。
- 与历史 `48.9451% / 1.359375 MiB` 只做不同镜像、不同注入方式的相容性对照，不设
  强制相等门。

### 1.5 身份、健康、空间与停止门

- 身份/环境硬门同 S4 §1.1：kernel 含 `rpi4`、架构严格为 `armv7l`、BUILD_ID 为
  `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`、glibc 为
  `glibc-2.40-1.6.armv7l`、MemTotal 在 S4 冻结带内。任一失败立即停止。
- 工作目录固定为 `/opt/usr/glibc_memopt/gst_trim_cost_20260901`；根分区不放资产或结果。
- 能力侦察只读。缺包时先取得候选包精确名称/版本/安装大小和依赖预算；只有预估安装后
  根分区可用空间仍不少于 `1.2 GiB` 才允许安装。预算不足或无法形成可审计事务即停止，
  不现场切换 ffmpeg 方案。
- controller 只接受初始四核均为 `schedutil`，随后切到 `performance`；所有退出路径
  恢复 `schedutil`。dmesg 增量必须零 OOM/LMK，zram 前后原值完整保留。
- 拉回后必须逐文件 hash/size 校验并解析全部 JSON；随后才删除精确板端目录并复核不存在。

## 2. 能力侦察与安装记录

### 2.1 身份与环境门原文

```text
$ uname -r
6.12.80-arm-rpi4-v7l
RC=0
DONE_UNAME_R

$ uname -m
armv7l
RC=0
DONE_UNAME_M

$ cat /etc/os-release
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l
RC=0
DONE_OS_RELEASE

$ rpm -q glibc
glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC_RPM

$ grep '^MemTotal:' /proc/meminfo
MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
```

三重身份门及环境未漂移门均通过。SDB 客户端为 `4.2.25`；连接与设备列表只以通道
可达性证据使用，判板只依赖上述 kernel/arch/BUILD_ID 三项。

### 2.2 GStreamer、插件与空间

`gst-launch-1.0` 与 `gst-inspect-1.0` 均可执行，版本均为 `1.24.11`。冻结 pipeline
所需 element 与 RPM 归属如下：

| element | 插件文件 | 已安装 RPM |
|---|---|---|
| `filesrc` / `queue` / `fakesink` | `libgstcoreelements.so` | `gstreamer-1.24.11-38.armv7l` |
| `qtdemux` | `libgstisomp4.so` | `gst-plugins-good-1.24.11-38.armv7l` |
| `mpeg4videoparse` | `libgstvideoparsersbad.so` | `gst-plugins-bad-1.24.11-38.armv7l` |
| `avdec_mpeg4` | `libgstlibav.so` | `gst-libav-1.24.11-38.armv7l` |

| 已安装包 | 版本 | `rpm SIZE` (B) |
|---|---|---:|
| `gstreamer` | `1.24.11-38.armv7l` | 1,975,188 |
| `gstreamer-utils` | `1.24.11-38.armv7l` | 144,435 |
| `gst-plugins-good` | `1.24.11-38.armv7l` | 3,599,200 |
| `gst-plugins-bad` | `1.24.11-38.armv7l` | 3,718,818 |
| `gst-libav` | `1.24.11-38.armv7l` | 206,683 |

能力门时 `/` 可用 `1,832,374,272 B`（`1.8G`），`/opt/usr` 可用
`118,190,792,704 B`（`111G`）。所有必需组件已经存在，故本轮**未安装任何包**；安装
后空间预算没有被触发，卸载命令清单为“不适用”。板上缺少可选 `python3`/`jq`，不参与
执行硬门；全部 JSON 在完整拉回后由 host Python 强制解析。

### 2.3 资产完整性

五个文件推入 `/opt/usr/glibc_memopt/gst_trim_cost_20260901/` 后逐项在板上重算
SHA-256，均与 host 一致：bench、分类 probe、媒体资产三项分别为 §1.1 冻结值；远端
controller 与 1 s sampler 分别为
`12dc839c252402b5d3f9f1a303249ab6f4ecb65a9deef52d24c263b9d0a62478` 与
`e1a72b57db9d6162e7fa21f9d9d9edc44b533e8a2ab250f56aee722e363a357f`。

执行后发现 controller 的附加 capture-meta `majflt` 使用了 POSIX sh 的 `$10`，实际得到
`$1`（进程状态 `S`）加字面 `0`，因此本批 306 对、612 个附加值均为 `S0`。该字段不作为
结果证据；目标内 `getrusage` 的逐循环 majflt 与外部 1 s `/proc/<pid>/stat` majflt 两条
独立来源均完整。发布 harness 已机械修正为 `${10}`，当前 controller SHA-256 为
`93fd3953739d88362bc3d4460cabbae8e411fc4f22367bac5a3657cecd74657c`；分析器要求本批
`S0` 缺陷 306/306 对一致并将其显式写成 `NA`，不会伪造为零。

### 2.4 执行时间线

| 阶段 | 原始结果 |
|---|---|
| controller start/end | `2026-09-01T22:04:54.048+09:00` → `23:53:25.836+09:00` |
| governor | cpu0–3 `schedutil → performance → schedutil`，controller 与 host 复核均通过 |
| `none-r1` | 51 cycle、51/51 pre/post JSON、1085 个 1 s 样本、bench/sampler `0/0` |
| `trim-r1` | 51 cycle、51/51 pre/post JSON、1085 个 1 s 样本、bench/sampler `0/0` |
| `trim-r2` | 51 cycle、51/51 pre/post JSON、1084 个 1 s 样本、bench/sampler `0/0` |
| `none-r2` | 51 cycle、51/51 pre/post JSON、1085 个 1 s 样本、bench/sampler `0/0` |
| `none-r3` | 51 cycle、51/51 pre/post JSON、1086 个 1 s 样本、bench/sampler `0/0` |
| `trim-r3` | 51 cycle、51/51 pre/post JSON、1086 个 1 s 样本、bench/sampler `0/0` |

PLAYING 阶段的只读辅证快照为 `Threads: 8`、`task_count=8`、`RC=0/
DONE_AUX_THREAD_SNAPSHOT`；它证明负载是多线程 pipeline，但不等价于测得 trim 调用瞬间
仍有 8 个线程在业务临界区。

## 3. 逐臂、逐重复结果

精确派生见 [`repetitions.tsv`](../data/raw/gst_trim_cost_20260901/repetitions.tsv) 与
[`arm_summary.tsv`](../data/raw/gst_trim_cost_20260901/arm_summary.tsv)。下表每个分位仅用
cycle 2–51 的 50 个预登记业务样本；nearest-rank p99 因而就是该重复的最大观测值。

| arm | rep | p50 (ms) | p95 (ms) | p99/max (ms) | min–max (ms) |
|---|---:|---:|---:|---:|---:|
| none | 1 | 20006.962433 | 20011.052933 | 20013.565747 | 20006.341136–20013.565747 |
| none | 2 | 20007.049026 | 20011.546673 | 20016.408137 | 20006.406210–20016.408137 |
| none | 3 | 20006.875099 | 20017.504506 | 20020.349914 | 20006.333062–20020.349914 |
| trim | 1 | 20008.871340 | 20014.596951 | 20028.415340 | 20008.293563–20028.415340 |
| trim | 2 | 20008.781192 | 20011.997933 | 20015.223136 | 20008.076062–20015.223136 |
| trim | 3 | 20008.832895 | 20010.868544 | 20022.636748 | 20007.990469–20022.636748 |

| 聚合统计 | none：三重复统计量中位 / range | trim：三重复统计量中位 / range | trim − none 中位 |
|---|---:|---:|---:|
| p50 | 20006.962433 / 0.173927 ms | 20008.832895 / 0.090148 ms | +1.870462 ms |
| p95 | 20011.546673 / 6.451573 ms | 20011.997933 / 3.728407 ms | +0.451260 ms |
| p99 | 20016.408137 / **6.784167 ms** | 20022.636748 / 13.192204 ms | **+6.228611 ms** |

预登记规则要求 `Δp99 > 6.784167 ms`；实测 `6.228611 ms`，margin 为
`0.555556 ms`，达到门槛的 `91.8%`，故
[`comparison.json`](../data/raw/gst_trim_cost_20260901/comparison.json) 的正式裁决为
`business_cost_visible=false`。方向按交付验收记 `REPORT_ONLY`；这只表示本批没有越过
none 重复离散，不证明等价，也不外推为产品 SLA。作为灵敏度披露，同样规则若用于 p50，
`+1.870462 ms > 0.173927 ms`，会判“可见”。

## 4. trim 并发耗时、回收与 faults

### 4.1 `malloc_trim(0)` 调用分布

| trim rep | calls | p50 (ms) | p95 (ms) | p99/max (ms) |
|---:|---:|---:|---:|---:|
| 1 | 51 | 0.676167 | 0.829481 | 0.839518 |
| 2 | 51 | 0.666500 | 0.767833 | 0.780870 |
| 3 | 51 | 0.664296 | 0.819129 | 0.856944 |
| 153 次合并 | 153 | **0.671556** | **0.818315** | **0.842185 / 0.856944** |

153/153 次调用均返回 1。合并中位、p95、p99 和最大值都低于 S4 合成单线程格约
`1.2 ms` 的中位量级；本目标没有显示更长的 trim 调用尾部。但这里的“并发”是目标在
PLAYING 阶段有 8 个线程；trim 位于 pipeline 完成 NULL release 之后，并未直接测量仍在
并发执行的业务线程被全 arena 锁阻塞多久。

### 4.2 glibc heap PD 回收

逐循环值见
[`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv)。none 的 153/153 次
pre/post 均为 `0 kB` 回收；trim 的 153/153 次回收均为 4 kB 页粒度且返回 1。

| trim rep | 每格回收中位 (kB) | 范围 (kB) | `回收/pre` 中位 |
|---:|---:|---:|---:|
| 1 | 980 | 768–1308 | 35.714286% |
| 2 | 1052 | 824–1316 | 37.252125% |
| 3 | 1020 | 840–1316 | 36.585366% |
| 153 次合并 | **1020** | **768–1316** | **36.585366%** |

历史 `48.9451% / 1.359375 MiB` 是无前序 trim 的首次 release 参考，因此正式相容性比较
使用各重复 cycle 1，而不是把已受上一轮 trim 影响的稳态循环混入：

| rep | cycle 1 pre→post (kB) | 回收 | 比例 | 相对历史 |
|---:|---:|---:|---:|---:|
| 1 | 2564→1256 | 1308 kB / 1.277344 MiB | 51.014041% | +2.068941 pp；绝对量 −6.03% |
| 2 | 2564→1248 | 1316 kB / 1.285156 MiB | 51.326053% | +2.380953 pp；绝对量 −5.46% |
| 3 | 2560→1244 | 1316 kB / 1.285156 MiB | 51.406250% | +2.461150 pp；绝对量 −5.46% |

cycle 2–51 的 150 次稳态重复中位降为 `988 kB / 36.461794%`，范围
`768–1212 kB / 30.188679–42.318436%`。这是每轮都先承接上一轮 trim 后低水位的口径，
不能替代 cycle 1 与历史首次 release 的同语义比较。

### 4.3 下一循环 faults

| arm | rep | cycle 2–51 minflt 总和 | majflt 总和 | 外部全程 minflt Δ | 外部全程 majflt Δ |
|---|---:|---:|---:|---:|---:|
| none | 1 | 4759 | 0 | 6070 | 4 |
| none | 2 | 4640 | 0 | 5984 | 0 |
| none | 3 | 2974 | 0 | 4286 | 0 |
| trim | 1 | 22498 | 0 | 23802 | 0 |
| trim | 2 | 22604 | 0 | 23911 | 0 |
| trim | 3 | 23431 | 0 | 24718 | 0 |

主统计窗口的三重复 minflt 总和中位为 none `4640`、trim `22604`，差
`+17964/50 cycles`，即约 `+359 minflt/循环`；合并逐循环中位为
`90.5 → 454.0`，差 `+363.5 minflt/cycle`（另一种聚合口径）。
150/150 个 trim 后再激活主循环与 150/150 个 none 主循环的 majflt 均为 0。外部序列
唯一的 majflt 增量是矩阵第一格首次冷启动在 elapsed `6.015 s` 出现的 `0→4`，同格
cycle 1 的目标内计数也为 4；它发生在任何 trim 之前，cycle 2–51 为零，不归因于 trim。

## 5. 健康门与现场恢复

| 门 | 结果 |
|---|---|
| zram `orig/compressed/mem_used_total` | `4096/74/4096 → 4096/74/4096 B`，三项 Δ=0 |
| dmesg | after 以 before 为完整前缀；增量 0 行；OOM/LMK 0 命中 |
| 外部采样 | 6511 行，6 格 PID 各自恒定，deadline overrun 6/6 为 0 |
| 退出/JSON | 6/6 bench、sampler 为 0；controller `RC=0/DONE_GST_TRIM_CONTROLLER`；612/612 profile JSON parse |
| 拉回完整性 | 1920 个 manifest SHA、1921 行 size 记录全部通过；完整目录 1922 文件、3,484,746 B |
| governor | 初值 4×`schedutil`，运行 4×`performance`，controller/host 末态均 4×`schedutil` |
| 清理 | 精确路径校验后删除板端工作目录，复核不存在；`RC=0/DONE_FINAL_CLEANUP` |

附加 capture-meta majflt 的 `S0` 缺陷见 §2.3 和
[`health.json`](../data/raw/gst_trim_cost_20260901/health.json)；它没有被计作零。逐循环目标内
majflt 与外部 1 s majflt 均为合法单调数值并已纳入 §4.3。完整原始件只保留在本地
`board_results/gst_trim_cost_20260901/`，公开仓库只收紧凑派生证据。

## 6. 判断

### a) 每循环 release trim 的业务代价是否可见

**方向结果：`REPORT_ONLY`，本批按规则未检出可见。** trim 相对 none 的三重复 p99 中位差为
`+6.228611 ms`，没有严格超过 none p99 的 `6.784167 ms` 重复离散带，差门槛
`0.555556 ms`，达到门槛的 `91.8%`。p50/p95 的描述性差分别为
`+1.870462/+0.451260 ms`；同规则在 p50 会因 `+1.870462 > 0.173927 ms` 判可见。
由于每重复只有
50 个主样本、p99 即最大值，本结论是“本批未检出”，不是零代价或 SLA 等价证明。

### b) 与 S4 单线程约 1.2 ms 的关系

本轮 153 次调用的 p50/p95/p99/max 为
`0.671556/0.818315/0.842185/0.856944 ms`，没有出现高于 S4 约 1.2 ms 中位量级的调用
尾部。它支持“在该 release 点调用本身仍为亚毫秒至约 1 ms 量级”，但不证明任意并发
分配时的全 arena 锁停顿也相同。

### c) 与既有 `48.9% / 1.36 MiB` 的相容性

**首次 release 相容。** 三个 cycle 1 为 `51.014041–51.406250%`、
`1.277344–1.285156 MiB`，比例高历史 `2.07–2.46 pp`，绝对量低约 `5.5–6.0%`，仍处于
同一约半数/约 1.3 MiB 机制量级。后续每轮重复 trim 的稳态中位降到
`36.461794% / 988 kB`，语义不同，不据此推翻首次 release 结论。

### d) 是否填上“并发线程代价未知”

**部分填上，但不足以整格关闭。** 已补齐的数字是：真实 8 线程 PLAYING pipeline 的
下一循环 p50/p95/p99、153 次 release-point trim 的完整耗时分布、每轮 PD 回收、额外
minflt 与零 trim 后 majflt，以及健康门。仍缺：

1. trim 调用瞬间工作线程数与 arena 数；本轮只在 PLAYING 阶段取得 8 线程快照。
2. 在其他业务线程仍分配/解码时，每线程被全 arena 锁阻塞的直接 stall/帧时延；本轮
   在 NULL release 后调用，下一轮墙钟只能观测后效，不能定位调用瞬间停顿。
3. 更大样本的尾部分位或产品 SLA 带；当前每重复 n=50，p99 是最大值，只能执行本批
   可见性门。

因此落点建议中的“真实目标再激活代价”可以标为已有测试板证据；“并发分配中的全
arena 锁停顿”仍应保留为未关闭前置，不宜用本轮替代。

## 7. 复现

可执行合同为
[`tools/runners/gst_trim_cost_20260901/`](../tools/runners/gst_trim_cost_20260901/)：
`preflight_gate.sh` 复核身份/环境，`capability_probe.sh` 只读检查 GStreamer/RPM/空间，
`build_armv7l.sh` 重建 instrumented ARM ELF，`run_gst_trim_cost_remote.sh` 固定 ABBAAB
矩阵并负责 governor trap/健康采集，`sample_smaps_1s.sh` 取得外部序列，
`analyze_gst_trim_cost.py` 执行强制完整性校验和派生。冻结参数与统计门只引用本报告
[§1](#1-建连前冻结规格)，不得编辑 controller 后再称同规格复跑。

host 构建入口：

```sh
TOOLCHAIN_ROOT=/path/to/toolchain/scratch.armv7l.0 \
GST_SYSROOT=/path/to/gstreamer/scratch.armv7l.0 \
  tools/runners/gst_trim_cost_20260901/build_armv7l.sh \
  /tmp/gst_loop_decode.armv7l
```

完整的建连、能力门、推送、运行、manifest、拉回、分析与精确目录清理命令见
[`HQ 复现指南 L2`](demo_reproduction_guide_20260901.md#l2-gst-trim-cost)。核心运行命令固定为：

```text
gst_loop_decode small_320x240.mp4 51 20 1 <arm> control-stdin
```

### 7.1 流程完整性与 validity gates

- 三个核心资产 SHA 与 §1.1 一致；同一构建批次的源码/ELF SHA 应逐字节一致。
- 6 格严格按 §1.2 顺序，每格 51 轮；业务主统计固定取 cycle 2–51 共 50 个样本。
- none 臂全部 `trim_return=-1/elapsed=0`；trim 臂每格恰有 51 个正耗时调用记录。
- 共 306 组 pre/post profile JSON 全部可解析、同格 PID 恒定，逐文件 SHA/size 清单通过。
- bench、sampler、controller 均退出 0 并具备远端 `RC=0/DONE_*`；dmesg OOM/LMK 零命中。
- controller/host 两次复核 cpu0–3 最终均为 `schedutil`；精确板端工作目录已删除。
- zram 三列必须取得同批前后值并报告 delta；绝对值不要求跨批次相同。

### 7.2 容差与 `REPORT_ONLY` 裁决项

- 业务代价不设事后百分比阈值，只复用 §1.4；workflow 对规则执行作硬校验，所得 p99
  方向始终为 `REPORT_ONLY`。若判可见，保留三重复、量化超带 margin 并上报。
- 回收量与 `48.9451% / 1.359375 MiB` 只作机制相容性对照，不要求逐值一致；该值来自
  `<TEST_IMAGE_B>` / `glibc-2.40-2.8`，非本轮冻结矩阵。
- trim 必须报告 p50/p95/p99/max 全分布并与 S4 合成格合并中位 `1.233269 ms` 比较；
  释放点单次调用验收带为 `<5 ms`，不用单点绝对相等。
- kernel 小版本或 MemTotal 小幅变化必须记为协变量；glibc 必须仍属 2.40 系，否则停止
  沿用本批判据，并按状态报告 §2.5 的版本告警重审。
