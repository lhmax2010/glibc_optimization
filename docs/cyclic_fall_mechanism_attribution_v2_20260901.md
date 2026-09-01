> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# 周期下降机理归因 v2：伪影修正与产品表型普查

- 定稿日期：2026-09-01
- 范围：host-only；本轮未建立任何板端连接
- 输入：三套公开脱敏原始时序及其已发表分析器；release-ratio 公开集缺少 S1 基线，按任务授权从本地完整原始件提取 10 行 alias/PID/glibc 基线到紧凑证据，不公开其他字段
- 独立实现：[`analyze_attribution.py`](../tools/runners/cyclic_fall_attribution_20260901/analyze_attribution.py)、[`audit_phenotypes.py`](../tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py)
- 历史衔接：v1 的 minflt 停止门记录保留在 [`cyclic_fall_mechanism_attribution_20260831.md`](cyclic_fall_mechanism_attribution_20260831.md)；F2/F3 首轮数值分歧保留在 [`cyclic_fall_f2_f3_validation_disagreement_20260901.md`](cyclic_fall_f2_f3_validation_disagreement_20260901.md)

> **2026-09-01 C3 复核追注：** `enlightenment` 同时越过 a 门和 b 门：冻结
> 10% 门为 `79.2 kB`，自动回撤 `120 kB`，而同 PID 段 retained floor 为
> `+1736 kB`；回撤仅为 retained 的 `6.912442%`。因此修正原 a 优先分类为
> **a+b 双标签**：`120 kB` 自动回撤分量按反信号排除，`+1736 kB` floor 进入
> L6 候选登记。`同量级` 在分类器中固定为回撤达到 floor 的 10%（相差不满
> 一个十进数量级）；`6.912442%` 未达到。同步附“已证实自动归还能力”告警，进入 trim 前仍必须用 M7
> 证明 floor 中确有 allocator 空闲驻留。原单标签表述保留在 Git 历史中。

## 1. 裁决摘要

1. `ServiceA` 八轮 glibc-heap Private_Dirty 下降为 `4032–9796 kB`，中位 `6212 kB`；同窗没有 zram `orig` 正增长，进程 `majflt` 始终为 `167`。换出路径被排除。
2. 32 个 `|Δglibc_heap_pd| >= 100 kB` 相邻步中没有与 other-anon 方向相反且近等幅的镜像互补；14/14 个释放步的 total PD 同步实跌。桶迁移解释被排除。
3. 已发表 `fall_edge` 把“首次跌出 90% 峰值带”到“尾窗最小值落点”的等待时间当成下降沿。`4.166497–24.460553 s`、中位 `19.683240 s` 是该定义的结果，不是释放时长。
4. 正式替代口径为 peak 后首次观测进入 `valley + 5% × (peak-valley)` 带的延迟：`5.223693–8.910626 s`，中位 `8.179733 s`。它是标称 1 s 时序的**首次观测上界**；采集 overrun 使实际相邻空档最长为 `6.077082 s`，不得升级成精确机制时长。
5. `ServiceA` 的周期分量是 L6 反信号：页已在峰后至多约 9 s 的首次观测内基本消失。唯一仍可作为 L6 候选的是谷底从 P0 `3464 kB` 到 R8 `4252 kB` 的 `+788 kB` 残渣；smaps 不能区分其中 live/bin 属性。

## 2. 决定性归因链

### 2.1 八轮峰谷与换出排除

zram 和 faults 均取同一轮 peak 到其后 valley 的累计计数器差值。

| 轮次 | peak / valley / P-V (kB) | zram orig Δ (B) | zram used Δ (kB) | majflt Δ |
|---|---:|---:|---:|---:|
| R1 | 13272 / 3476 / 9796 | 0 | 0 | 0 |
| R2 | 10068 / 3824 / 6244 | 0 | 0 | 0 |
| R3 | 12612 / 3992 / 8620 | 0 | 0 | 0 |
| R4 | 10708 / 4032 / 6676 | 0 | 0 | 0 |
| R5 | 8176 / 4144 / 4032 | 0 | 0 | 0 |
| R6 | 10392 / 4212 / 6180 | -262144 | -256 | 0 |
| R7 | 8396 / 4064 / 4332 | 0 | 0 | 0 |
| R8 | 10044 / 4252 / 5792 | 0 | 0 | 0 |

R6 的唯一 zram 变化是 `orig` 与 `used` 同向减少，不支持 swap-out；全窗口无 zram 正向步进。`ServiceA` PID 恒定、660 点无 `NA`、sample 0–659 连续，排除了进程重启和缺行造成的假下降。PM 已撤回“每轮上升沿 1.1–2.1 万 minflt”说法；正式保留的 10%→90% 上升沿值为 `698–10613`，不再把整轮窗口 minflt 当作上升沿辅证。

### 2.2 F2：分类桶迁移排除

| 检查项 | 复算值 |
|---|---:|
| `|Δglibc| >= 100 kB` 相邻步 | 32 |
| 上升 / 释放步 | 18 / 14 |
| `Δother-anon` 方向相反 | 2 |
| 两个反向步的 `|Δother|/|Δglibc|` | 0.023729 / 0.047414 |
| ±20% / ±50% 近等幅互补 | 0 / 0 |
| 释放步中 `Δtotal_pd < 0` | 14 / 14 |

所以 glibc 分类下降不是同一批页镜像迁入 other-anon。聚合 smaps 可以支持“分类内页面确实消失、且不是换出或桶迁移”，但不能在 `systrim`、`heap_trim`、arena 内 discard、应用直接 `madvise`/`munmap` 之间唯一判函数路径。本文把“glibc 自动归还”用于机制类别，不声称已直接观测某个具体调用。

## 3. F3：下降沿伪影与正式替代口径

已发表脚本的定义是：`fall_start` 为 peak 后首次低于 90% excursion 的样本；`valley` 为从该点到轮窗末尾的最小值；`fall_edge = valley_time - fall_start_time`。逐轮复算如下。

| 轮次 | peak / fall_start / valley (kB) | fall_start 时已释放比例 | 原定义 fall_edge (s) | 首次观测入谷底 5% 带延迟上界 (s) |
|---|---:|---:|---:|---:|
| R1 | 13272 / 3512 / 3476 | 99.632503% | 18.615723 | 5.429566 |
| R2 | 10068 / 3844 / 3824 | 99.679693% | 19.662990 | 6.077082 |
| R3 | 12612 / 4564 / 3992 | 93.364269% | 5.744246 | 8.590703 |
| R4 | 10708 / 6772 / 4032 | 58.957460% | 24.460553 | 8.698081 |
| R5 | 8176 / 6248 / 4144 | 47.817460% | 4.166497 | 8.497841 |
| R6 | 10392 / 8372 / 4212 | 32.686084% | 19.703490 | 7.861624 |
| R7 | 8396 / 4128 / 4064 | 98.522622% | 20.949599 | 5.223693 |
| R8 | 10044 / 6820 / 4252 | 55.662983% | 22.639416 | 8.910626 |

塌落形态逐轮异质：在旧 `fall_start` 点，R1/R2/R3/R7 已释放约 93.4%–99.7%，R4/R5/R6/R8 只有约 32.7%–59.0%。因此不再使用“一步塌回”表述；共同事实是八轮都在 peak 后**首次观测 ≤约 9 s**达到 `PD <= valley + 5% × (peak−valley)`。末列受离散采样约束，只是完成时间上界。

## 4. 伪影影响面审计

### 4.1 cyclic 分析器

| 已发表量 | 判定 | 依据与处理 |
|---|---|---|
| glibc peak、valley 数值及 P-V | 稳健 | peak 是轮内最大、valley 是峰后最小；F3 改变的是最小值落点的时长解释，不改变观测幅度。`6212 kB` 中位和 `4032–9796 kB` 范围保留。 |
| valley 水平与 P0→R8 `+788 kB` | 稳健 | 依赖 valley 数值而非把 valley 时刻当完成点；R7 回落也保留，趋势仍是非严格单调。 |
| rise edge `3.406 s` 中位 | 不受该伪影污染 | 只用 low/high entry，不读 `fall_start` 后尾窗；仍受离散采样上界限制。 |
| peak 时刻及其前序 key 关联 | 不受该伪影污染 | peak 选择发生在 fall/valley 之前。 |
| `fall_edge` 逐轮值与 `19.683240 s` 中位 | **撤销时长解释** | 尾窗最小值定位把谷底等待计入下降沿。数值仅保留为旧算法复算记录。 |
| `peak_band` 逐轮值与 `4.682 s` 中位 | **受污染** | 右边界是首次跌出 90% 的离散样本；样本可能已跨过大段塌落，不能解释为真实峰值驻留时长。 |
| valley elapsed/timestamp | 数值可复核、语义受限 | 它是轮窗最小值落点，不是释放完成时刻。 |
| `other_at_glibc_valley`、同刻 other 下降与两类占比 | 数值可复核、机理解释受限 | 对齐的是较晚的 glibc 最小值落点；不能据此描述真实塌落完成瞬间。other-anon 自身极差不依赖该落点，保留。 |

因此正式撤销“下降沿 19.683 s”作为释放时长的解读，也撤销 v2.5 的“操作结束后延迟约 20 s 触发 trim”钩子建议。替代说法是：**释放在峰后 ≤约 9 s 内基本完成（标称 1 s 序列的首次观测上界）**。

### 4.2 plateau 与 release-ratio 分析器

| 分析器 | 是否有 min-over-tail / 极值落点边沿 | 已发表数字处理 |
|---|---|---|
| `product_plateau_probe_20260814/analyze_plateau.py` | 否。用各 stage 的 glibc peak、相邻轮峰差和 5% 门判平台 | 不撤销同型数字；`ServiceH[ServiceK]` 的 `2360 kB` 仍只作为平台高度**上界**。2 s 粗采样、154 次 overrun、最大间隔 `7.576596 s` 继续限制短峰和轮内下降解释。 |
| `product_release_ratio_timeseries_20260814/analyze_timeseries.py` | 否。按稳定 PID 段维护 running peak/trough，以 10% 基线门形成 drawdown event；未从 trough 时间推导边沿时长 | 不撤销同型数字；段内 min/max、阶梯/锯齿标签保留。`ServiceH` 的 PID 切换仍强制分段，不能跨 PID 拼接。 |

不受本次 F3 伪影影响，不等于没有数据质量限制：plateau 是 2 s 多目标粗采样；release-ratio 的代表性动作覆盖有限。这两套证据用于表型筛选，不用于精确释放时长。

## 5. 十目标表型普查

严格判别器保留三类原语义：

- `a` 自回收：达到探针既有响应门的 PD 下降，且同窗 zram `orig` 无正增长、`majflt=0`；这是 L6 反信号。
- `b` 滞留：达到响应门的 retained floor / 平台；若同时存在 a 分量，两者按分量组合标注，而不是用 a 优先级抹除剩余 floor。`同量级` 固定为自动下降达到 retained floor 的 10%（相差不满一个十进数量级）；达到该门时不能把整体当成稳定 b 面。
- `c` 无响应：PD 逐字节恒定；维持排除。

为避免强行归类，另保留 `N`（有非零波动，但低于冻结响应门）和 `U`（PID、zram/majflt 或跨探针形态混杂）。release-ratio 沿用 S1 基线 10% 门（重启后无 S1 的新 PID 才用段首），retained 高度只取同 PID 段末减段首；plateau 沿用 P0 末值 5% 门。没有根据结果调门槛。

### 5.1 release-ratio 主筛十目标

| 目标 | 分类 | retained / 最大下降 (kB) | zram orig Δ / majflt Δ（最大下降窗） | 结论 |
|---|---|---:|---:|---|
| `AppProcD` | N | +56 / 36 | -2523136 B / +7 | 低于 10% 门，不建立 L6 面 |
| `ServiceE` | c | 0 / 0 | 0 / 0 | 300 点逐字节不变，排除 |
| `AppProcB` | N | +280 / 8 | 0 / 0 | 低于门 |
| `ServiceH` | b | +580 / 8 | 0 / 0 | PID 重启后仅在新 PID 段内成立；不跨 PID 比较 |
| `cynara` | N | -4 / 4 | -10903552 B / 0 | 低于门 |
| `AppProcA` | N | 0 / 4 | 0 / 0 | 低于门 |
| `systemd` | N | +24 / 0 | 0 / 0 | 单调但低于门 |
| `enlightenment` | **a + b** | **+1736 / 120** | -1761280 B / 0 | `120 kB` 自动回撤仅为 retained 的 `6.912442%`：回撤分量排除，`+1736 kB` floor 入候选；告警：已证实自动归还能力 |
| `buxton2d_worker` | b | +376 / 0 | 0 / 0 | 阶梯滞留候选 |
| `ServiceD` | b | +408 / 0 | 0 / 0 | 阶梯滞留候选 |

### 5.2 plateau 全目标交叉核验（2 s 粗采样）

| 目标 | 综合分类 | P0 / 5% 门 (kB) | 最大上涨 / 末值-P0 / 最大下降 (kB) | 主证据解释 |
|---|---|---:|---:|---|
| `AppProcD` | N | 30036 / 1501.8 | 244 / -252 / 1120 | 非逐字节恒定，但全部低于 5% 门 |
| `AppProcC` | N | 15348 / 767.4 | 0 / -340 / 352 | 低于门 |
| `AppProcB` | N | 10540 / 527.0 | 4 / -340 / 376 | 低于门，且下降窗含 zram/majflt 增长 |
| `ServiceA` | a + b 残渣 | 2932 / 146.6 | 8828 / +340 / 8736 | 1 s cyclic 主证据确认周期自回收；仅 P0→R8 valley `+788 kB` 作为候选 |
| `ServiceD` | N | 9512 / 475.6 | 136 / +136 / 0 | 单调但低于门 |
| `ServiceE` | c | 8772 / 438.6 | 0 / 0 / 0 | plateau 与 cyclic 均逐字节不变 |
| `ServiceL` | N | 6436 / 321.8 | 32 / -44 / 76 | 低于门 |
| `ServiceH[ServiceK]` | b | 11240 / 562.0 | **2360 / +1864 / 792** | 平台高度 `2360 kB` 为候选上界；1 s cyclic floor 仍净增 `+868 kB` |
| `ServiceB` | U | 3508 / 175.4 | 1420 / +380 / 1040 | plateau 下降窗含 zram `+1085440 B`、majflt `+31`；cyclic 又无稳定 retained floor，不硬归类 |
| `ServiceC` | N | 3932 / 196.6 | 80 / +44 / 44 | 低于门 |

公开代号在不同探针中只按各自采集合同解释；除有 cyclic 定向证据的四个目标外，不把相同字符串自动当成跨探针同一生命周期。完整逐目标字段见 [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) 与 [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)。

## 6. C1–C4 定稿

### C1：周期峰谷归因

`ServiceA` 周期峰谷属于 glibc-heap 分类页面的自动归还类别：PD 实跌、zram 无正增长、majflt 恒零、total PD 同步下降、other-anon 无镜像迁入。释放在 peak 后首次观测 `≤约 9 s` 内基本完成；各轮塌落形态异质，不再称“一步塌回”。聚合口径不能进一步唯一判定 `systrim`、`heap_trim`、arena discard 或 `munmap` 的具体占比。v2.5 §5.3“free 后大概率留在 bin 内”的周期峰谷旁证撤销。

### C2 / C2b：反信号与时长修正

PD 可见下降沿是 L6 反信号：该周期分量已经离开私有脏页集合，不能再当成等待主动 trim 的驻留量。S3 原语义作废，先前两个待裁选项均不采纳。`19.683240 s` 只保留为旧算法的尾窗极值落点统计，撤销其“释放时长”解释和“延迟约 20 s 触发 trim”建议；替换为“释放在峰后 `≤约 9 s` 内完成（采样上界）”。

### C3：L6 产品侧候选面迁移

候选面改为：

1. 滞留型表型：release-ratio 的阶梯/retained floor，以及 `ServiceH[ServiceK]` 的平台高度；其中 `enlightenment +1736 kB` 是 a+b 双标签 floor（已证实另有 `120 kB` 自动回撤能力），`ServiceH[ServiceK] 2.36 MB` 是平台可见上界，二者都不等同于 allocator 空闲字节。
2. `ServiceA` 谷底残渣：P0 `3464` → R8 `4252 kB`，`+788 kB`；smaps 无法区分 live/bin，只能作为待 M7 验证的候选。
3. 既有批量处理释放相位类：以 `malloc_info` 已确认 free 进入 unsorted/rest、且 PD 未自动下降的相位为主证据。

撤销“单个 `ServiceA` 周期分量即超过此前全部 Top-5 保守估计”的说法；周期峰谷不是可相加的 L6 驻留量。

### C4：S2 新定位

S2 两档冻结负载保留为**bin 驻留表型的板上基线**：约 6.4 MiB 每周期进入 rest/unsorted、16/16 周期无 PD 自动下降。它不再承担复现产品 `ServiceA` PD 峰谷的合同，也不再用旧 `19.683 s` 指标判成败。S3 若恢复，必须围绕已确认的驻留面和新的 M7/代价合同重新立项，不能沿用原语义直接开跑。

## 7. 紧凑证据

- [`serviceA_large_steps.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_large_steps.tsv)：F2 的 32 个大步；
- [`serviceA_fall_recheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv)：逐轮 fall_start 已释放比例、旧 fall_edge 与新上界；
- [`summary.json`](../data/raw/cyclic_fall_attribution_20260901/summary.json)：F2/F3 汇总和输入哈希；
- [`definition_audit.json`](../data/raw/cyclic_fall_attribution_20260901/definition_audit.json)：三套分析器定义与哈希；
- [`release_ratio_baselines.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_baselines.tsv)：从本地完整件提取的 10 行脱敏 S1 基线；
- [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv)、[`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)：十目标主筛与 plateau/cyclic 交叉核验。
