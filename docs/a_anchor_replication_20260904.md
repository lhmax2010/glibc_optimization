# S4 A 锚点双 ELF 重复实验（2026-09-04）

> 本节在任何板端连接之前写定，但当时没有“合同提交 + 独立事前标签”的外部凭证，
> 因而按 2026-09-04 PM 终审裁决统一称为**固定合同重放**，不称预登记。执行前 `main` 为
> `01f9bb651e04ba3b0ad9a0d93cf5d044d51da4c8`；不得依据实测值改变矩阵、顺序、
> 阈值、聚合口径或旧观测的纳入范围。板地址在全部入库内容中记为
> `<TEST_BOARD_IP>`。

## 1. 固定合同重放规格

### 1.1 目的与不变量

本轮只复测 [S4 A 瞬时释放格](s4_reference_and_retention_trim_20260901.md#12-a-组新-llvm-镜像瞬时释放参考格2-格)，
解释 [GBS 重基线](gbs_rebaseline_20260903.md#41-a-组锚点各-n1分母为-pre-trim-heap) 中
唯一带外的 A/mixed。冻结参数逐字保持：

```text
--threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15
--idle-trim --post-trim-ops-per-thread 4096 --live-set 4096
--idle-release 50 --release-order high
```

profile 只允许 `mixed` 或仓库冻结的
[`medium_1k_16k.hist`](../tools/runners/s4_retention_20260901/medium_1k_16k.hist)；每格继续
采集内部 JSON、四相位 malloc_info XML、外部 1 s smaps 序列、pre/post glibc heap PD、
回收率、trim/refault 耗时与 faults、退出状态。全轮记录 dmesg、zram、swaps 与 governor。

两个 ELF 的预期 SHA 只读
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json)：

- frozen：`dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`；
- GBS：`88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa`。

### 1.2 12 格矩阵与固定顺序

严格按下表执行，ELF 来源逐格 frozen/GBS 交替；不允许补跑、换序或剔除样本。

| order | ELF | profile | rep |
|---:|---|---|---:|
| 01 | frozen | mixed | 1 |
| 02 | GBS | mixed | 1 |
| 03 | frozen | medium-only | 1 |
| 04 | GBS | medium-only | 1 |
| 05 | frozen | mixed | 2 |
| 06 | GBS | mixed | 2 |
| 07 | frozen | medium-only | 2 |
| 08 | GBS | medium-only | 2 |
| 09 | frozen | mixed | 3 |
| 10 | GBS | mixed | 3 |
| 11 | frozen | medium-only | 3 |
| 12 | GBS | medium-only | 3 |

### 1.3 二选一裁决算法

基本统计单位是 `{ELF × profile}` 的三个回收率
`(pretrim_glibc_pd_kb - posttrim_glibc_pd_kb) / pretrim_glibc_pd_kb × 100%`。
每组计算 `min / median / max / range=max-min`；两 ELF 的分布区间按闭区间
`[min,max]` 判断，端点相接也算交叠。数值比较使用未格式化的双精度值，报告显示值统一
四舍五入到 6 位小数。

- **H-L 分路径：** 四个 `{ELF × profile}` 组的 range 均 `≤1.5 pp`，且对 mixed、
  medium-only 两个 profile，frozen/GBS 中位数绝对差均 `>1.5 pp`，同时两个闭区间均
  不交叠。命中后发布 GBS 分 profile 的新锚点表，中心为本轮各 GBS 三重复中位数，
  半宽固定 `4 pp`；frozen 的现行锚点与 `49% ±4 pp` 带保持不变。
- **H-V 扩带：** 任一组 range `>1.5 pp`，或任一 profile 的 frozen/GBS 闭区间交叠。
  命中后按 profile 合并全部观测：本轮每路径各三次，加上此前 frozen/GBS 各一次的
  已登记 A 观测，共 `n=8/profile`；中心为合并中位数，半宽为
  `max(4 pp, 合并 max-min)`，两条构建路径共用。此前观测固定为 frozen
  `mixed 51.074077% / medium-only 50.387886%`，GBS
  `mixed 55.243785% / medium-only 50.535918%`，来源分别为
  [S4 A 表](s4_reference_and_retention_trim_20260901.md#3-a-组结果新镜像锚点)和
  [GBS A 表](gbs_rebaseline_20260903.md#41-a-组锚点各-n1分母为-pre-trim-heap)。
- **边缘情形：** H-L、H-V 均不满足时停止，只提交本轮数据与待裁报告；不改验收合同，
  不宣布 GBS 转正。

H-V 的“任一”优先保证两规则互斥：只要出现组内高方差或任一 profile 跨 ELF 交叠，
就不能同时归入 H-L。命中 H-L 或 H-V 后，再用对应新带复判此前 GBS 重基线的 A 项；
此前已通过的 deterministic、validity、B 和 gst 项不重跑、不改写。

### 1.4 身份、健康与停止门

- 身份门：`uname -r` 含 `rpi4`；`uname -m` 严格为 `armv7l`；BUILD_ID 严格为
  `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`。
- 环境门：`glibc-2.40-1.6.armv7l`，MemTotal 落在既有约 `8117408 kB` 的门限；
  `id -u=0`、4 核 governor 可写、`/opt/usr` 可写。
- 工作目录固定为 `/opt/usr/glibc_memopt/a_anchor_replication_20260904/`；所有板端命令
  必须用远端 `RC=...` 与 `DONE_*/FAIL_*` 判定，不信任 SDB 自身退出码。
- 初始 4 核 governor 必须为 `schedutil`，运行期统一为 `performance`，所有退出路径恢复
  `schedutil` 并复核。推送前后分别核验两个 ELF 和 histogram SHA。
- stability-monitor v2 的本轮临时登记：`cpu.relative`、进程 basename
  `alloc_bench.armv7l`、窗口严格属于上述 12 格、每格最多 1 个、总数最多 12 个；匹配项
  必须逐件归档、哈希核验、按精确路径清理并复核消失。超出窗口、单格多于 1 个、总数
  超过 12 个或可归属但理由不符，均为硬失败。无告警记 `REGISTERED/NOT-EVALUATED`。
- dmesg OOM/LMK、zram 三项增量、远端退出、JSON/XML 解析、拉取 manifest、工作目录清理
  或 governor 恢复任一失败，立即停止裁决与后续文档转正。

## 2. 执行记录

### 2.1 前置门与产物身份

正式执行仅一次，板端窗口为 `2026-09-04T12:01:16+0900` 至
`2026-09-04T12:09:29+0900`。三重身份门与环境门原文为：

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
0
RC=0
DONE_ROOT_UID
```

两件 host 输入与推送后板端文件的 SHA-256 均分别等于 manifest 登记值：frozen
`dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`，GBS
`88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa`。紧凑原文见
[`execution_gates.txt`](../data/raw/a_anchor_replication_20260904/execution_gates.txt)，身份链见
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json)。

### 2.2 顺序、采集与健康门

控制器逐格输出 `DONE_CELL_<cell>`，12/12 格 `bench_rc=0`、`sampler_rc=0`，每格外部
1 s 序列均为 41 点；执行顺序与 §1.2 完全一致，没有补跑、换序或剔除。拉回的完整
JSON、48 份相位 XML、外部序列、命令记录、dmesg 与 manifest 均通过解析、大小和哈希
检查；完整件留存在本地 `board_results`，可按请求提供。

| 健康项 | 实测 | 判定 |
|---|---:|---|
| dmesg 增量 / OOM-LMK 命中 | `0 / 0` | PASS |
| zram original/compressed/used 增量 | `0 / 0 / 0` | PASS |
| trim / refault majflt 最大值 | `0 / 0` | PASS |
| 回收量 4 KiB 对齐 | `12/12` | PASS |
| 结束 governor | `schedutil 4/4` | PASS |
| 工作目录 / 我方进程 / livedump | `ABSENT / 0 / 0` | PASS |

stability-monitor 从 `0` 增至 `12`：每个固定合同格恰好一个属于相应 PID/ELF 的
`cpu.relative` livedump，未超过“每格 1、合计 12”的临时上界。12 件全部归档并按精确
路径清除，复核剩余 `0`，故依 v2 known-alert waiver 记为 `EXPECTED`；这只证明触发理由、
窗口与 owner 可复现，不构成根因或无害性证明。健康汇总见
[`health.json`](../data/raw/a_anchor_replication_20260904/health.json)。

## 3. 12 格结果与裁决

### 3.1 格级结果

主回收率分母为 pre-trim glibc heap PD；完整字段含 released payload、回收/已释放、
trim/refault faults 与外部序列统计，见
[`a_cells.tsv`](../data/raw/a_anchor_replication_20260904/a_cells.tsv)。

| order | ELF | profile | rep | pre → post PD (KiB) | 回收 (KiB) | 回收/pre (%) | trim (ms) | refault min/majflt |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | frozen | mixed | 1 | 107336 → 50028 | 57308 | 53.391220 | 15.885352 | 1703 / 0 |
| 2 | GBS | mixed | 1 | 110296 → 52224 | 58072 | 52.651048 | 13.882167 | 1602 / 0 |
| 3 | frozen | medium-only | 1 | 104520 → 53280 | 51240 | 49.024110 | 12.433130 | 3045 / 0 |
| 4 | GBS | medium-only | 1 | 100608 → 47532 | 53076 | 52.755248 | 13.140815 | 3125 / 0 |
| 5 | frozen | mixed | 2 | 109396 → 51484 | 57912 | 52.937950 | 14.683315 | 1595 / 0 |
| 6 | GBS | mixed | 2 | 111132 → 53224 | 57908 | 52.107404 | 14.966092 | 1512 / 0 |
| 7 | frozen | medium-only | 2 | 105260 → 51152 | 54108 | 51.404142 | 13.671278 | 3073 / 0 |
| 8 | GBS | medium-only | 2 | 105268 → 51788 | 53480 | 50.803663 | 13.027408 | 3213 / 0 |
| 9 | frozen | mixed | 3 | 108404 → 53184 | 55220 | 50.939080 | 13.805778 | 1654 / 0 |
| 10 | GBS | mixed | 3 | 108324 → 50032 | 58292 | 53.812636 | 15.182352 | 1729 / 0 |
| 11 | frozen | medium-only | 3 | 100516 → 52432 | 48084 | 47.837160 | 12.318019 | 3095 / 0 |
| 12 | GBS | medium-only | 3 | 109304 → 53468 | 55836 | 51.083217 | 12.692926 | 3071 / 0 |

### 3.2 固定合同裁决

| ELF × profile | n | min (%) | median (%) | max (%) | 极差 (pp) |
|---|---:|---:|---:|---:|---:|
| frozen × mixed | 3 | 50.939080 | 52.937950 | 53.391220 | **2.452140** |
| GBS × mixed | 3 | 52.107404 | 52.651048 | 53.812636 | **1.705232** |
| frozen × medium-only | 3 | 47.837160 | 49.024110 | 51.404142 | **3.566982** |
| GBS × medium-only | 3 | 50.803663 | 51.083217 | 52.755248 | **1.951585** |

四组极差均 `>1.5 pp`，已经独立满足 H-V；此外两个 profile 的 frozen/GBS 闭区间也
都交叠。mixed 两路径中位差只有 `0.286902 pp`；medium-only 虽为 `2.059107 pp`，但区间
仍交叠。因此 H-L 的“二进制特定、低组内方差”前提不成立，按固定规则唯一裁决为
**H-V：A 锚点方差此前被低估**。机器裁决原文见
[`decision.json`](../data/raw/a_anchor_replication_20260904/decision.json)，四组派生见
[`group_summary.tsv`](../data/raw/a_anchor_replication_20260904/group_summary.tsv)。

### 3.3 v4 共同锚点带

按 profile 合并本轮 6 次与此前 frozen/GBS 各一次，共 `n=8/profile`。半宽取
`max(4 pp, 合并极差)`：

| profile | 合并 min–max (%) | 合并中位 (%) | 新半宽 (pp) | frozen/GBS 共用带 (%) |
|---|---:|---:|---:|---:|
| mixed | 50.939080–55.243785 | **52.794499** | **4.304705** | 48.489794–57.099204 |
| medium-only | 47.837160–52.755248 | **50.669791** | **4.918088** | 45.751703–55.587879 |

这是建连前写定的 H-V 分支在 12 格完整观测上的机械结果；但由于没有独立事前标签，
证据等级只记为固定合同重放。`acceptance_bands.json` 升为 v4；原“各 n=1 锚点”的
现行局限标注据此撤销，
原始 S4/GBS 报告中的历史单次值继续保留为时间线事实；该旧局限的登记来源见
[`review_fix_20260903.md` P1-7](review_fix_20260903.md#逐项闭环)。

## 4. 结论与文档同步

### 4.1 v4 校准带与 GBS 状态

用 v4 共同带重放 [GBS 全矩阵](gbs_rebaseline_20260903.md) 的已归档派生件：GBS A/mixed
`55.243785%` 落入 `52.794499% ±4.304705 pp`，A/medium-only `50.535918%` 落入
`50.669791% ±4.918088 pp`。此前已经通过的 released payload 字节、页对齐、majflt、
zram、dmesg、B 两档三重复中位、两类 trim 时延与 gst 规则执行均保持 PASS；gst p99
方向仍为 REPORT_ONLY。结构化复放会输出 `OVERALL PASS`，但这只说明同一建带样本
落在由自身参与标定的带内，不是独立验证。
紧凑复判表见
[`gbs_v4_recheck.tsv`](../data/raw/a_anchor_replication_20260904/gbs_v4_recheck.tsv)。

**2026-09-04 终审订正：撤回“GBS 重基线通过”和“GBS 为 HQ 首选 L2 路径”。**
GBS 观测参与了 v4 中心与半宽的构造，因此 v4 是校准带，不能再用同批观测证明 GBS
独立通过。RPM NVR → 三个 ELF SHA → manifest → 板上哈希的身份链仍成立；但路径优先级
保持冻结件为默认、GBS 为待 held-out 验证候选。带的数值不变。

### 4.2 合同变更边界

- 只改变 A 锚点回收率容差项；B、gst、deterministic、validity gates 和 stability-monitor
  v2 的常规登记均未改。
- A 回收字节仍不是确定性项；同 seed 不钉死 arena 指派。v4 使用固定合同重放的按 profile
  合并分布吸收布局/运行方差。
- 本轮 stability-monitor 的 12 件临时登记只适用于本报告的 12 格，不扩展到常规 S4
  workflow。

## 5. 复现

板端 harness 位于
[`tools/runners/a_anchor_replication_20260904/`](../tools/runners/a_anchor_replication_20260904/)，
顺序、历史观测、H-L/H-V 算法与告警窗口的机器源为
[`fixed_contract.json`](../tools/runners/a_anchor_replication_20260904/fixed_contract.json)。
冻结参数以 §1.1 为准。板上完整复现：

```sh
bash tools/runners/a_anchor_replication_20260904/run_a_anchor_host.sh \
  --ip <TEST_BOARD_IP> \
  --output board_results/a_anchor_replication_20260904/workflow \
  --frozen /path/to/frozen/alloc_bench.armv7l \
  --gbs /path/to/gbs/alloc_bench.armv7l
```

只用公开紧凑件可在 host 分钟内复算裁决并逐字节校验：

```sh
tmp=$(mktemp -d)
python3 tools/runners/a_anchor_replication_20260904/analyze_a_anchor.py \
  --replay data/raw/a_anchor_replication_20260904/a_cells.tsv --output "$tmp"
cmp "$tmp/group_summary.tsv" data/raw/a_anchor_replication_20260904/group_summary.tsv
cmp "$tmp/decision.json" data/raw/a_anchor_replication_20260904/decision.json
```

验收分两类：

- **确定性/有效性：** 执行身份、顺序、ELF SHA 与 RC/DONE 必须精确匹配；12 格均成功；
  回收量均 4 KiB 对齐；majflt、zram 三项增量与 OOM/LMK 均为 0；告警严格匹配临时窗口
  并归档清理；最终目录、进程、livedump 均不存在且 governor 为 `schedutil`。
- **容差/裁决：** 不要求 A 回收字节或单次回收率逐值一致；必须用未修改的 §1.3 规则
  重新裁决。当前 v4 共同带为 mixed `52.794499% ±4.304705 pp`、medium-only
  `50.669791% ±4.918088 pp`；A trim 仍须单次 `<20 ms`，且不作为钩子代价数字。
