# 周期下降机理归因独立复核：停止门分歧报告

- 日期：2026-08-31
- 范围：host-only；本轮未建立任何板端连接
- 状态：**STOPPED AT STEP 2**
- 输入：公开脱敏原始件 `product_cyclic_target_probe_20260814/raw/timeseries.tsv` 与 `key_timeline.tsv`
- 独立实现：[`recompute_cyclic.py`](../data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py)

## 1. 停止门结论

PM 的主数值链中，以下三项复算一致：

1. `ServiceA` 八轮 glibc-heap Private_Dirty 峰减谷为 `4032–9796 kB`，中位数 `6212 kB`；
2. 全窗口 zram `orig` 只发生一次 `-262144 B` 变化，`used` 同步 `-256 kB`，没有任何正向增长；
3. `ServiceA` 的 `majflt` 全窗口严格为 `167 -> 167`，八轮峰到谷及整轮增量均为 0。

因此，“这些下降不是由观测到的 zram 换出造成”的排除链成立。

但 PM 的辅证“每轮上升沿有 1.1–2.1 万 minflt”与实际 wall-clock 重分段不一致：

- 每个实际 60 s 轮次的**全轮** minflt 增量仅为 `11197–12660`；
- 按 PD excursion 的 10%→90% 定义，**上升沿** minflt 增量为 `698–10613`；
- 轮次边界→峰值的更宽上界也只有 `857–10652`。

`20967` 来自原始 nominal `stage=R1` 的首末相减。由于 smaps overrun，nominal R1 已延伸到实际 R2 上升段并包含 R2 峰值点；nominal R8 则只得到 `1` 个 minflt。该口径不能解释为“八轮各自的上升沿”。这是明确分歧，故按任务纪律停止：**未执行十目标表型普查，未修订状态报告至 v2.7，未写入 C1–C4，也未更新项目结论索引。**

## 2. 独立复算口径

解析器没有读取旧派生表或旧分析脚本。处理步骤为：

1. 从按键表的 `actual_epoch_ns - target_offset_s - lateness_ms` 独立重建 collector 计划起点；
2. 以冻结的 `60,120,...,480 s` offset 划分 R1–R8，每轮带入边界前最后一个样本作为起点；
3. 峰值取轮内 glibc PD 首个最大值，谷底取峰后首个最小值；
4. zram、minflt、majflt 均用同一行的累计计数器做端点差，不跨 PID；
5. 上升沿 faults 另按“达到 excursion 10% 前最后一点→首次达到 90%”计算。

公开输入与本地完整原始件的行数和除 `target/comm` 别名外的全部字段逐行一致。公开输入 SHA-256：

```text
fc0d39e4e8a4ddc7fdc068291fdb82310b53939cc43fb94123f262a4e38776ae  timeseries.tsv
ec676e9abac5fb8951f2805df62ae14c394d00902fd8cf14b7a98718749f6344  key_timeline.tsv
```

## 3. ServiceA 逐轮复算

zram 与 faults 均为对应轮次峰值→其后谷底的增量；“整轮 minflt”是实际 wall-clock 60 s 轮次的边界→轮末增量。

| 轮次 | peak / valley / P-V (kB) | zram orig Δ (B) | zram used Δ (kB) | majflt Δ | minflt 10%→90% | 整轮 minflt |
|---|---:|---:|---:|---:|---:|---:|
| R1 | 13272 / 3476 / 9796 | 0 | 0 | 0 | 10613 | 11531 |
| R2 | 10068 / 3824 / 6244 | 0 | 0 | 0 | 9339 | 12660 |
| R3 | 12612 / 3992 / 8620 | 0 | 0 | 0 | 698 | 11538 |
| R4 | 10708 / 4032 / 6676 | 0 | 0 | 0 | 959 | 11197 |
| R5 | 8176 / 4144 / 4032 | 0 | 0 | 0 | 1082 | 11434 |
| R6 | 10392 / 4212 / 6180 | -262144 | -256 | 0 | 768 | 11783 |
| R7 | 8396 / 4064 / 4332 | 0 | 0 | 0 | 9615 | 11816 |
| R8 | 10044 / 4252 / 5792 | 0 | 0 | 0 | 5477 | 11496 |

R6 的唯一 zram 变化发生在同一采样间隔，`orig` 和 `used` 同向减少；全窗口没有 zram 正向步进。该负向变化可能来自 swap-in 或 swap slot 释放，但不支持 PD 被换出；方向与 swap-out 所需证据相反。

## 4. 三个对照目标逐轮复算

下面列出每轮 `P-V / 整轮 minflt / 整轮 majflt`。ChannelLoader 与 ServiceB 的峰→谷 zram 增量同样只有 R6 为 `-262144 B / -256 kB`；WebRuntime 各轮峰谷点重合，峰→谷 zram 增量均为 0。全局负步进仍是同一个 sample 339→340 事件。

| 目标 | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 |
|---|---|---|---|---|---|---|---|---|
| `ChannelLoader` | 420/4823/0 | 588/4521/0 | 380/4535/0 | 424/4715/0 | 448/5217/0 | 380/4510/0 | 564/4471/0 | 388/4404/0 |
| `ServiceB` | 100/224/0 | 4/359/0 | 36/218/0 | 16/375/0 | 0/89/0 | 40/103/0 | 0/154/1 | 12/151/0 |
| `WebRuntime` | 0/0/0 | 0/0/0 | 0/11/0 | 0/1/0 | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |

`ServiceB` 的唯一一次 majflt 增量位于 R7 整轮，但该轮 glibc PD `P-V=0`，峰→谷 majflt 仍为 0；它不能解释 `ServiceA` 的周期下降。`WebRuntime` 的 glibc PD 在 660 个点上逐字节不变。

完整 32 行端点、rise/peak/valley faults 与 zram 差值见 [`cyclic_rounds.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv)。

## 5. 混杂因素排查

| 混杂因素 | 独立检查 | 结果 |
|---|---|---|
| zram 毛刺 | 扫描 659 个相邻样本差分 | 0 个正向步进；仅一个 `orig=-262144 B / used=-256 kB` 的负向步进 |
| NA / 样本缺失 | 检查 2640 行、四目标各 660 行、sample 0–659 连续 | `NA=0`，sample 编号无缺口 |
| PID 变化 | 对每个目标逐行比较非 NA PID | 四目标均为单一 PID，变化 0 |
| 进程重启假下降 | PID 恒定且 counters 未重置 | 排除 |
| nominal stage 漂移 | 用实际 epoch 与计划 offset 重分段 | 存在；collector 报告 555 次 overrun，最大相邻间隔 `6.077082 s` |
| zram 与目标行不同步 | 同一样本四目标的系统计数器逐行核对 | 一致；系统计数器只需取任一目标行 |

采集没有丢失 nominal sample，但高 overrun 使“按 sample 数量切 stage”失去 wall-clock 轮次含义；这正是 minflt 分歧的来源。完整质量摘要见 [`cyclic_quality.json`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json)。

## 6. 机理裁决的证据边界

本轮可以裁决的是：`ServiceA` 的 glibc-heap 代理 PD 下降没有伴随 zram 增长或该进程 majflt，因此观测到的下降不是 swap-out 形成的。

本轮不能只凭聚合 smaps 序列唯一定位到 `systrim`、`heap_trim` 或某个具体 glibc 调用。现有分类把 `[heap]` 与 arena 形态的匿名映射合并为 glibc-heap 代理；稳定 PID 排除了重启，但只读聚合数据仍不能区分 brk 收缩、secondary-heap discard、应用直接 `madvise`/`munmap` 或分类内映射生命周期。把“非换出”进一步写成“已直接证明由某一 glibc 自动归还路径造成”，证据强度过高。

因此当前裁决为：

- **换出排除链：成立；**
- **minflt 每轮上升沿 1.1–2.1 万：不成立；**
- **glibc 自动归还：最符合现有代理证据的解释，但尚不是具体函数路径的直接证明；**
- **后续结论修订：按停止门不执行。**

## 7. 紧凑证据

- [`recompute_cyclic.py`](../data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py)：独立解析器；
- [`cyclic_rounds.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv)：四目标、八轮完整复算；
- [`serviceA_fault_boundary_comparison.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/serviceA_fault_boundary_comparison.tsv)：实际轮次、上升沿与 nominal stage 的 faults 对照；
- [`cyclic_quality.json`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json)：NA、PID、采样间隔、zram 步进与全窗口 faults。
