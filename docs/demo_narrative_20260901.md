> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# 第 1 周 Demo 叙事：从自动归还反信号到表型门控 trim

- 日期：2026-09-01
- 结论边界：这是机制、候选面和测试板代价的决策材料，不是产品收益承诺
- HQ 入口：[`demo_reproduction_guide_20260901.md`](demo_reproduction_guide_20260901.md)

## 1. 问题定位：TV 内存压力与 glibc 层机会

项目目标是在不改 ABI、可逐进程启停和可回滚的前提下，降低 Tizen TV 进程的
RSS/PSS 与系统内存压力。glibc/ptmalloc 不是全部内存的 owner：托管堆、文件映射、
图形缓冲和自带分配器都在作用域外；但对确由 ptmalloc 持有、应用已经 free、页面仍
驻留的那一部分，`malloc_trim(0)` 提供了明确的归还路径。项目定位和完整杠杆地图见
[`状态报告 §1`](glibc_memopt_program_status_report_zh.md#1-项目定位) 与
[`状态报告 §2`](glibc_memopt_program_status_report_zh.md#2-方案调研全景)。

真正的决策问题不是“哪个进程内存大”，而是“哪个相位同时满足：页面尚未自动离开
Private_Dirty、allocator 内确有已释放驻留、回收后的再激活与并发停顿在预算内”。

## 2. 核心发现一：自动归还是反信号

`ServiceA` 的周期 glibc-heap Private_Dirty 峰谷中位为 **6.07 MiB**，精确复算为
`6212 KiB`（[证据 TSV](../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv)；
[HQ 复算](demo_reproduction_guide_20260901.md#l1-servicea)）。但峰谷下降期间：

- glibc-heap PD 与 total PD 同步实跌；
- 全局 zram 没有正向增长；
- 进程 majflt 首末恒定；
- other-anon 没有与 glibc 方向相反、近等幅的镜像迁移。

决定性链的逐轮值和质量门见
[`cyclic_rounds.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv)
与 [HQ 归因复算](demo_reproduction_guide_20260901.md#l1-servicea)。因此换出、进程
重启和分类桶迁移都不能解释这段下降；最稳妥的聚合结论是：这批 glibc 分类页面已经
自动离开 Private_Dirty。聚合采样不能继续区分 `systrim`、`heap_trim`、arena discard
或应用直接 `madvise`/`munmap` 的具体占比。

此前把 **19.7 s** 当成“下降沿”的说法来自尾窗最小值落点，精确旧中位为
`19.683240 s`；它是推导伪影，不是释放时长
（[证据 JSON](../data/raw/cyclic_fall_attribution_20260901/summary.json)；
[HQ 复算](demo_reproduction_guide_20260901.md#l1-servicea)）。修正口径是峰后首次进入
valley ±5% 带的 `5.223693–8.910626 s`，且它仍是 1 s 采样上界。教训很直接：观察到
PD 下降时，应先判定页面是否已经自动归还，不能再把这段下降当作等待主动 trim 的收益。

## 3. 核心发现二：滞留表型才是作用面

表型普查使用分量级标签，`a` 不再覆盖同一目标上仍存在的 `b` floor。精简示例如下，
完整字段见
[`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv)、
[`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)
和 [HQ 表型复算](demo_reproduction_guide_20260901.md#l1-phenotypes)。

| 标签 | 含义 | 示例 | 决策 |
|---|---|---|---|
| a | 自回收分量 | `ServiceA` 周期分量 | 反信号，排除该分量 |
| b | retained floor / 平台 | `buxton2d_worker` | 进入 M7 候选队列 |
| c | PD 逐字节无响应 | `ServiceE` | 维持排除 |
| N | 有波动但低于冻结响应门 | `AppProcD` | 不建立作用面 |
| U | PID、swap/fault 或跨探针形态混杂 | `ServiceB` | 不硬归类，先补质量证据 |

两张表不跨表合并计数：`ServiceD` 在 release-ratio 表为 `b-retention`，在
plateau/cyclic 表为 `N-subthreshold`。这是已披露的跨表分类冲突，须保留各自采样窗口与
冻结门，不能择一覆盖；见
[`归因 v2 §5`](cyclic_fall_mechanism_attribution_v2_20260901.md#5-十目标表型普查)。

当前候选登记是：

- `enlightenment` 的 retained floor 为 **+1736 KiB**，同时已有自动归还能力告警；只排除
  自动下降分量，floor 仍进候选（[证据 TSV](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-phenotypes)）。
- `ServiceH[ServiceK]` 的平台可见高度 **2360 KiB（2.30 MiB）** 只作为上界；独立时序还留下
  **+868 KiB / +580 KiB** floor，且 PID 分段、探针代号边界必须保留
  （[plateau/cyclic 证据 TSV](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)、
  [release-ratio 证据 TSV](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-phenotypes)）。
- `ServiceA` 只保留谷底缓升 **+788 KiB** 残渣；smaps 无法判断其 live/bin 属性
  （[证据 TSV](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-phenotypes)）。
- 批量处理释放相位类已有 M7 证据：来自 `<TEST_IMAGE_B>` / `glibc-2.40-2.8` 的相容性
  对照为单进程 **48.9% / 1.36 MiB**、同一表型扩展到 **8 个进程**；它不是冻结矩阵
  （[证据 TSV](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-batch-release)）。

这些都是“待用 M7 判 live/bin”的候选面，不是可以直接相加的产品收益。

## 4. 门控链与测试板实证

门控链是：**反信号排除 → M7 确认 rest/unsorted 驻留 → valley trim → 同批记录调用、
faults 与健康门。** S4 在新 LLVM 镜像上把这条链对合成滞留表型闭合：

- 预登记双 ELF 复测后，瞬时释放共同锚点带为 **mixed
  52.794499% ±4.304705 pp / medium-only 50.669791% ±4.918088 pp**（每档合并
  `n=8`，分母为 pre-trim heap）；旧 `51.07% / 50.39%` 保留为历史单次值
  （[裁决 JSON](../data/raw/a_anchor_replication_20260904/decision.json)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-a-anchor-replication)）。
- valley trim 回收已释放 payload 的逐周期范围为 **80.18%–85.45%**
  （[证据 TSV](../data/raw/s4_retention_20260901/b_cycles.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-s4)）。
- 调用耗时按档中位为 **mixed 1.233269 ms / medium-only 1.218361 ms**
  （[证据 TSV](../data/raw/s4_retention_20260901/b_cycles.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-s4)）。
- 下一周期相对 none 增加 **+1351 / +1465 minflt**，`majflt=0`
  （[证据 TSV](../data/raw/s4_retention_20260901/b_cells.tsv)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-s4)）。
- zram 三项增量与 OOM/LMK 命中均为 **0**
  （[证据 JSON](../data/raw/s4_retention_20260901/health.json)；
  [HQ 复算](demo_reproduction_guide_20260901.md#l1-s4)）。

这组数字证明“驻留表型门控 trim”在测试板合成代理上成立；它没有证明任一产品候选
的 floor 都是 allocator 空闲页，也没有给出产品业务延迟。

## 5. 决策门：何时 trim，何时不 trim

文字流程如下：

`相位结束` → `观察 PD 是否已经自动下降` → 若是，则把该下降分量标成反信号并结束；
若否 → `检查目标是否由 glibc/ptmalloc 管理` → 若为自带分配器或 ownership 不明，则结束；
若是 → `在释放前后取得 M7` → 若 rest/unsorted 没有确认驻留，则不 trim；若确认驻留 →
`检查调用耗时、再激活 faults、并发锁停顿预算` → 任一超预算则不启用；全部过门才允许
在已冻结的相位钩子上执行 trim，并保留回滚开关。

简写为：**自动下降不 trim；无驻留不 trim；非 glibc ownership 不 trim；代价未过门不
trim。只有“未自动下降 + M7 驻留 + 代价过门”同时成立才 trim。**

## 6. 边界与未决

合成代理不等于产品结论，仍有三条硬缺口：

- 产品候选的 M7 live/bin 分解未取得；现有 smaps floor 只能登记候选，不能换算收益。
- 测试板 S4 只有单进程合成调用时间与 faults；真实并发目标上的全 arena 锁停顿、业务
  p99/帧时延和能耗未测。
- 测试板与产品板的镜像、内存环境和工作负载不同；测试板百分比只能说明机制与量级，
  产品收益必须在产品侧按同一门控合同重新建立。

产品侧下一步和硬前置见
[`product_landing_recommendation_20260901.md`](product_landing_recommendation_20260901.md)。
