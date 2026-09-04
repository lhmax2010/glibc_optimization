# GBS 产物板上重基线（2026-09-03）

> **停止门结论：未通过，不转正。** 在 `<TEST_BOARD_IP>` 上，以 GBS RPM 提取的三个
> ELF 完整执行 S4 + gst workflow 后，S4 A/mixed 锚点为 `55.243785%`，超出固定合同
> `49% ±4 pp` 的上界 `53%`。验收器的结构化结论为 `FAIL`。本轮不重跑、不改验收带，
> GBS 路径继续保持“host 构建已闭合、板上重基线待裁决”，冻结件仍是 L2 正式基线。

本报告只登记停止门之前已经完成的执行、workflow 缺陷修复和现场恢复。完整板端原始件
留存在本地 `board_results/gbs_rebaseline_20260903/`，可按请求提供；因停止门触发，未向
`data/raw/` 新增本轮紧凑测量件，也未修改 README、复现指南或 manifest 的路径优先级。

## 1. 冻结合同与执行入口

本轮没有改动规格和统计口径：

- 执行前 `main` 为 `0aa1a3d09959b4b1bc37cf31524a7c1e8edd8f8f`；
- S4 A/B 格沿用 [S4 冻结规格](s4_reference_and_retention_trim_20260901.md#1-执行前冻结规格)；
- gst 两臂三重复沿用 [gst 冻结规格](gst_trim_cost_20260901.md#1-建连前冻结规格)；
- 验收以 [`acceptance_bands.json` v3](../tools/reproduce/acceptance_bands.json) 为唯一机器合同；
- GBS RPM 构建身份来自 [`deliverables_manifest.json` v2](../tools/reproduce/deliverables_manifest.json)，
  构建来源另见 [`build_summary.json`](../data/raw/gbs_package_20260903/build_summary.json)；
- 唯一正式执行入口是 [`reproduce.sh board`](../tools/reproduce/reproduce.sh)，本轮选择
  `gbs_build_sha256`：

```sh
bash tools/reproduce/reproduce.sh board \
  --ip <TEST_BOARD_IP> \
  --output <LOCAL_BOARD_RESULTS>/workflow_retry2 \
  --artifact-dir <LOCAL_GBS_BUNDLE> \
  --artifact-source gbs
```

`workflow_retry2` 是修复现场暴露的 workflow 缺陷后首次走完全矩阵并产生验收结果的执行；
前两次没有产生可用于裁决的完整验收结果，见 §3。

## 2. 前置门与产物身份链

### 2.1 身份与环境门原文

```text
6.12.80-arm-rpi4-v7l
RC=0
DONE_UNAME_R

armv7l
RC=0
DONE_UNAME_M

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

glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC_RPM

MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
```

附加 preflight 硬门也全部通过：`id -u=0`、4 个 governor 文件可写、`/opt/usr`
可写；S4、gst controller 及各格均回显 `RC=0` 和对应 `DONE_*` 标志。

### 2.2 RPM → ELF → manifest

| 层级 | 身份 | 本轮推送前核验 |
|---|---|---:|
| RPM | `glibc-memopt-tools-1.0.0-1.armv7l`，`32956 B` | SHA-256 `efad4a0d202785f8c201977fd8aef35752af1bddde163f1063151621e0ac4e0e` |
| `alloc_bench.armv7l` | RPM `/usr/bin/alloc_bench` | `88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa` |
| `gst_loop_decode.armv7l` | RPM `/usr/bin/gst_loop_decode` | `7549f309fd26da2d2aff3e36772fecdceb9394931b0f74d597788dc645fcc034` |
| `reclaim_probe.armv7l` | RPM `/usr/bin/reclaim_probe` | `e71d4aa59dffe9027ec58c2cef88a899facdbf295df82a882a58e611daef4d31` |
| `small_320x240.mp4` | 本地留存媒体，非 RPM 内容 | `3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d` |

三个 ELF 均与 manifest 的 `gbs_build_sha256` 逐字节一致，媒体与 manifest 的
`frozen_sha256` 一致；workflow 推送后再次按同一预期 SHA 在板端核验。RPM 对应源码
提交为 `20ab8c80d7b357254542dd841212ed8d7e7085c8`，buildroot 为
`clang-22.1.8-1.6.armv7l` / `glibc-2.40-1.6.armv7l`。以上登记值均来自
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json)，不是本轮改写。

## 3. Workflow 执行记录与一等发现

| 执行 | 覆盖范围 | 结果与现场恢复 | 根因与修复 |
|---|---|---|---|
| `workflow` | S4 全格完成；在 S4 stability snapshot 停止 | 自动恢复 `RC=0 / DONE_WORKFLOW_RECOVERY`；两个 S4 A livedump 先拉回验哈希再按精确路径清理 | **D1**：远端 `awk` 引号错误；改为 shell 参数展开截取 SHA。**D2**：解析器只接受 ZIP 根目录成员，而实件是带前缀的 `*.dump_reason` / `*.info.json`；增加后缀匹配且仍要求唯一成员。 |
| `workflow_retry1` | S4 全格完成；已知告警分类时失败，gst 首格启动后人工中止 | 自动恢复成功；一个已归档但漏删的 livedump 按精确路径补清，复核不存在 | **D3**：循环内调用的 `sdb` 继承清理清单 stdin，吞掉下一路径；所有 `sdb` 调用统一重定向 `</dev/null`。**D5**：S4 stability 失败只在全部 workload 结束后汇总；现改为 S4 清理与 governor 恢复后立即硬停。中止避免在已知 S4 健康门失败后继续约两小时无效工作，不是数据挑选。 |
| `workflow_retry2` | 首次完整完成 S4 10 格与 gst 6 格并生成 JSON 验收 | 两个 S4 A 登记告警均归档、清理、复核；gst 无新告警；全部工作目录清理、governor 恢复 | 验收 JSON 正确给出 `FAIL`，但顶层脚本误打印 `OVERALL PASS` 并返回 0。**D4**：POSIX 管道返回 `tee` 状态，掩盖验收器非零状态；改为先捕获命令状态并落盘/回显，再原样返回。 |

D1–D5 均有 host 回归覆盖：非空 livedump 目录快照、真实 Tizen 前缀 ZIP、清理循环
stdin 隔离、S4 stability 失败先于 gst 开始的顺序门，以及“已输出内容但退出 7”的命令
状态保真。D4 的原始矛盾证据为同一日志先出现
`OVERALL FAIL`、随后误追加 `OVERALL PASS`；裁决始终以
`acceptance_result.json` 的 `outcome: FAIL` 和修复后的退出语义为准。

## 4. S4 逐格结果与 acceptance v3

### 4.1 A 组锚点（各 `n=1`，分母为 pre-trim heap）

发布值来自 [S4 A 组结果](s4_reference_and_retention_trim_20260901.md#3-a-组结果新镜像锚点)，
验收带来自 [`s4_a_anchor_reclaim_pct`](../tools/reproduce/acceptance_bands.json)。

| profile | 发布锚点 | GBS 实测 pre → post / 回收 | GBS 回收率 | 固定合同带 | trim | 判定 |
|---|---:|---:|---:|---:|---:|---|
| mixed | `51.074077%` | `112476 → 50340 / 62136 KiB` | **`55.243785%`** | `45%–53%` | `13.573371 ms` | **FAIL：超上界 2.243785 pp** |
| medium-only | `50.387886%` | `105240 → 52056 / 53184 KiB` | `50.535918%` | `45%–53%` | `12.762907 ms` | PASS |

A 组两次 trim 均低于 `<20 ms` 的非钩子时延门。mixed 的失败不能用“历史不可比值”或
事后调带覆盖；它单独足以触发本轮停止门。

### 4.2 B 组逐格

发布中心和逐周期参考来自 [S4 B 组表](s4_reference_and_retention_trim_20260901.md#4-b-组结果trim-效果与代价)
及公开 [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)。正式 profile 门是
三重复中位 `mixed 81.661264% ±5 pp`、`medium-only 84.446566% ±5 pp`；`none`
是对照，不触发 trim。

| profile / arm | rep | 两周期回收 `KiB` | 重复中位回收/释放 | trim 中位 `ms` | 下一周期 minflt / majflt | 逐周期发布值 `±1024 KiB` |
|---|---:|---:|---:|---:|---:|---|
| mixed / valley | 1 | `4496 / 5332` | `81.661264%` | `1.425260` | `1678 / 0` | PASS |
| mixed / valley | 2 | `4496 / 5332` | `81.661264%` | `1.439907` | `1678 / 0` | PASS |
| mixed / valley | 3 | `4472 / 5320` | `81.353708%` | `1.238139` | `1678 / 0` | PASS |
| mixed / none | 1 | `0 / 0` | `0%` | `0` | `327 / 0` | 对照 |
| medium-only / valley | 1 | `5124 / 5252` | `84.446566%` | `1.238445` | `1557 / 0` | PASS |
| medium-only / valley | 2 | `5124 / 5252` | `84.446566%` | `1.161315` | `1557 / 0` | PASS |
| medium-only / valley | 3 | `5120 / 5144` | `83.535378%` | `1.121796` | `1557 / 0` | PASS |
| medium-only / none | 1 | `0 / 0` | `0%` | `0` | `92 / 0` | 对照 |

三重复中位分别为 `81.661264%` 和 `84.446566%`，均与发布中心一致；12 次有效
回收全部 `4096 B` 对齐，释放点 trim 最大值 `1.587648 ms < 5 ms`。

确定性 payload 也逐字节通过：mixed 两周期为 `5742256 / 6566672 B`，medium-only
为 `6288384 / 6293504 B`，与 [`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)
登记值一致。回收字节本身按 v3 是 banded reference，不属于确定性项。

## 5. gst 逐格结果

发布批逐重复值见公开 [`repetitions.tsv`](../data/raw/gst_trim_cost_20260901/repetitions.tsv)，
固定合同判别法见 [gst 冻结规则](gst_trim_cost_20260901.md#1-建连前冻结规格)。本轮每重复仍取
cycle 2–51 的 50 个主样本，p99 为 nearest-rank。

为避免 20 秒固定循环时长遮蔽臂间差异，下表业务墙钟写成“绝对值减 `20 s`”的毫秒偏移；
原始绝对值仍保存在本地逐循环件中。

| arm | rep | p50 / p95 / p99 相对 `20 s` 的偏移 `ms` | trim p50 / p95 / p99 / max `ms` | 回收中位 `KiB` | primary minflt / majflt | 判定 |
|---|---:|---:|---:|---:|---:|---|
| none | 1 | `7.049951 / 10.065025 / 17.562914` | `0 / 0 / 0 / 0` | `0` | `2260 / 0` | 完整 |
| trim | 1 | `8.874247 / 13.667248 / 19.063377` | `0.675148 / 0.865148 / 1.278518 / 1.278518` | `1056` | `22217 / 0` | 完整 |
| trim | 2 | `8.825229 / 15.748488 / 18.623025` | `0.689740 / 0.921481 / 1.052759 / 1.052759` | `968` | `22801 / 0` | 完整 |
| none | 2 | `7.031506 / 12.807395 / 15.886636` | `0 / 0 / 0 / 0` | `0` | `3989 / 0` | 完整 |
| none | 3 | `7.112858 / 11.887192 / 13.919007` | `0 / 0 / 0 / 0` | `0` | `3207 / 0` | 完整 |
| trim | 3 | `8.886414 / 14.440284 / 15.371526` | `0.657760 / 0.790111 / 0.942037 / 0.942037` | `1012` | `22486 / 0` | 完整 |

153 次 release-point trim 的合并 p50/p95/p99/max 为
`0.670648 / 0.874537 / 1.052759 / 1.278518 ms`，满足单次 `<5 ms`。业务规则独立
重算结果为：trim/none 的三重复 p99 中位差 `2.736389 ms`，none 重复离散带
`3.643907 ms`，故 `visible=false`；规则执行 PASS，方向按 v3 仅记
`REPORT_ONLY`，不能用于抵消 S4 A/mixed 的失败。作为非验收描述，trim 三次首循环
回收为 `1320 / 1316 / 1316 KiB`（`51.482059% / 51.406250% / 51.326053%`）。

## 6. Validity、健康门与现场恢复

| 项目 | S4 | gst | 判定 |
|---|---:|---:|---|
| majflt | next-cycle `0` | primary-cycle `0` | PASS |
| zram `orig/compressed/mem_used_total` Δ | `0 / 0 / 0` | `0 / 0 / 0` | PASS |
| dmesg OOM/LMK | `0` | `0` | PASS |
| 回收页对齐 | `12/12` 为 4096 B 整数倍 | 不适用该 S4 gate | PASS |
| stability-monitor v2 | 2 个 A 格 `cpu.relative`，窗口/PID/数量匹配；已归档、清理、复核 | 无新增告警 | `EXPECTED` / `REGISTERED/NOT-EVALUATED` |

两条 S4 告警分别落在 `A/mixed/rep1` 与 `A/medium-only/rep1`，满足已登记“总数至多
2 个”的 known-alert waiver；该结论仅说明触发理由、窗口、归属、数量和处置合同匹配，
不声称已证明根因。

workflow 清理原文均为 `RC=0 / DONE_WORKDIR_CLEANUP`、
`RC=0 / DONE_EMPTY_PARENT_CLEANUP` 和 `RC=0 / DONE_GOVERNOR_FINAL`。停止后又做一次
只读现场审计：4 核 governor 全为 `schedutil`，`/opt/usr/glibc_memopt`、S4/gst 固定目录
均不存在，无 `alloc_bench`、`gst_loop_decode` 或采样脚本进程，无 livedump；结尾为
`RC=0 / DONE_FINAL_FIELD_AUDIT`。

## 7. 裁决与待 PM 项

1. **GBS 重基线未通过。** 唯一带外项是 S4 A/mixed `55.243785%`；其余 deterministic、
   validity gates、B 组三重复中位、trim 时延、gst 规则执行及健康门均通过。
2. **GBS 路径不转正。** [`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json)
   的状态继续是 `built_host_only_pending_board_rebaseline`；README/指南继续以冻结件作为
   板上正式判定基线。
3. **不做事后动作。** 本轮没有改变 `49% ±4 pp`、没有重跑刷数，也没有把 n=1 A 锚点
   改成别的聚合口径。PM 后续可裁决是否接受该单格偏移、另立事前合同复测轮或修订协议；
   本报告不替 PM 选择。
4. **Workflow 可修缺陷已闭环。** D1–D5 是执行器正确性问题，修复不改变冻结参数、
   分析器或验收带；尤其 D4 确保今后任一验收器 FAIL 会使 board workflow 非零退出。

## 8. 复现

### 8.1 Harness 与冻结参数

- 编排入口：[`tools/reproduce/reproduce.sh`](../tools/reproduce/reproduce.sh)；
- board 实现：[`board_workflow.sh`](../tools/reproduce/board_workflow.sh)；
- S4 harness：[`tools/runners/s4_retention_20260901/`](../tools/runners/s4_retention_20260901/)；
- gst harness：[`tools/runners/gst_trim_cost_20260901/`](../tools/runners/gst_trim_cost_20260901/)；
- 冻结参数和手工等价流程：[`demo_reproduction_guide_20260901.md` L2](demo_reproduction_guide_20260901.md#l2-run)；
- GBS 产物身份与获取：[`demo_reproduction_guide_20260901.md` GBS 小节](demo_reproduction_guide_20260901.md#l2-gbs-build)。

取得与 manifest 匹配的三个 GBS ELF 和媒体后，使用 §1 的命令。**当前正式复现不应把
本轮 GBS bundle 当成已通过基线**；若为定位带外项而再次测量，必须先由 PM 冻结新轮次、
重复数和裁决口径，不能直接复用本轮命令刷数。

### 8.2 两类验收判据

- **确定性项：** 同 profile/cycle 的 released payload 字节必须与
  [`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json) 逐值一致。
- **Validity gates：** 回收量 4096 B 对齐、majflt=0、zram 三项 Δ=0、dmesg 零
  OOM/LMK；远端 RC/DONE、JSON/XML 可解析、manifest 完整和现场恢复也必须通过。
- **容差/规则项：** A 为 `49% ±4 pp`；B 为分档三重复中位、各自发布中心 `±5 pp`；
  S4 B 和 gst release-point 单次 trim `<5 ms`，S4 A 单次 `<20 ms`；gst p99 只硬校验
  nearest-rank/重复中位/离散带/严格大于规则，方向为 `REPORT_ONLY`。
- **Stability-monitor v2：** 未观测登记项记 `REGISTERED/NOT-EVALUATED`；只有理由、
  窗口、归属、数量全部匹配并完成归档、清理、复核时才记 `EXPECTED`。

本轮结果展示了 workflow 在带外时应有的正确行为：保留结构化证据、返回失败并停止，
而不是自动将 GBS 路径转正。

## 9. 2026-09-04 A2 固定合同重放追注

本报告 §7 的“未通过/不转正”是 2026-09-03 在 v3 合同下的历史裁决，保留不改写。
随后按固定合同的 12 格双 ELF 重放执行（该轮没有独立事前提交/tag 凭证）
[`A2 报告`](a_anchor_replication_20260904.md)：四个 `{ELF × profile}` 组的极差均
`>1.5 pp`，且两个 profile 的 frozen/GBS 分布都交叠，故命中固定的 **H-V**，而不是
二进制特定的 H-L。按 profile 合并此前两次与本轮六次观测后，v4 共同带为：

- mixed：`52.794499% ±4.304705 pp`（`n=8`）；
- medium-only：`50.669791% ±4.918088 pp`（`n=8`）。

以 v4 复判本轮完整归档：A/mixed `55.243785%` 与 A/medium-only `50.535918%` 均
PASS，§4–§6 已通过项保持不变，结构化结果为 `OVERALL PASS`。

**2026-09-04 终审订正：** GBS 观测参与了上述 v4 中心与半宽的构造，故这里的
`OVERALL PASS` 是校准样本内重放，不能作为 GBS 独立通过证据。撤回“GBS 重基线通过”
与“GBS 路径转正为 HQ 首选”；冻结件恢复为当前默认，GBS 等待 held-out 验证。数值带
保持不变。

## 10. 2026-09-04 held-out 独立验证追注

§9 的终审订正保留为当时状态：同一建带样本不能证明自身通过。随后在连接板之前，
四格 GBS-only 合同与分析器由提交 `1b6304c583a7ed2e03790ffe5308dabf158eb30c`
和轻量标签 `gbs-heldout-contract-20260904` 固定；结果不并入校准样本。mixed 两格为
`49.492012% / 54.266910%`，medium-only 两格为 `51.806724% / 49.656064%`，4/4
独立落入现行 v4 闭区间，健康与清理门全过。

因此按事前规则，**GBS 重基线通过，GBS 恢复为 HQ 默认 L2 路径，冻结件为备选**。
校准带的中心、半宽、分类与 `n=8/profile` 建带样本均不变。完整证据与边界见
[`gbs_heldout_validation_20260904.md`](gbs_heldout_validation_20260904.md)。
现行机器合同见
[`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)，紧凑 A2 证据见
[`data/raw/a_anchor_replication_20260904/`](../data/raw/a_anchor_replication_20260904/)。
