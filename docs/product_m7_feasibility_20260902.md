> Public archive note: application/process names are aliases. Board identifiers,
> image delivery paths, and local filesystem paths are sanitized.

# 产品候选 M7 可行性评估

- 日期：2026-09-02
- 范围：host-only 证据组织与方案评估；未连接板端、未做新测量
- 决策对象：如何把产品候选 retained floor 分解为 live 数据与 allocator bin 驻留
- 前置合同：[`产品侧落点建议的三条件硬门`](product_landing_recommendation_20260901.md#1-启用门清单)

## 1. 结论先行

推荐顺序是 **A 目标 owner 受控构建 → C 测试板代理并行校准 → B 调试器注入仅作有审批的
条件性备选**。

- 路径 A 是唯一同时保留真实产品生命周期、真实 allocator ownership 和可审计发布链的
  正式路线，证据最适合进入产品启用门。
- 路径 C 可以立即复用现有 `alloc_bench`，用于校准 M7、外部 PD、trim 与 faults 的采集
  合同，但只能证明代理表型，不会把产品 floor 自动升级为 bin。
- 路径 B 若获准，能直接取得一次性产品 M7；但 attach 会暂停进程，表达式调用可能与
  allocator 锁相互作用，且当前产品执行策略和当前测试板工具状态都不支持把它当默认
  路径。它不能提供可信业务代价。

若 A 无法取得 owner、签名构建和合规落盘位置，产品候选的 M7 门继续保持关闭。C 可以
继续做机制演示；B 未经产品安全与调试纪律书面批准不得用来绕过该停止门。

## 2. 需要回答的问题与现有边界

产品普查只建立了 retained surface：`enlightenment +1736 kB`、
`ServiceH[ServiceK]` 的平台上界与两个 floor、`ServiceA +788 kB` 谷底残渣。smaps 能说明
Private_Dirty 形态，但不能区分 live 对象和已经 free 后留在 bins 的字节；候选清单及其
不可相加边界见
[`周期下降归因 v2 §5–§6`](cyclic_fall_mechanism_attribution_v2_20260901.md#5-十目标表型普查)。

M7 的当前合同是在业务 free 前后、trim 前取得 `malloc_info`，检查全局 `rest` 与各 arena
的 `unsorted` 是否出现与释放相位一致的空闲驻留。它不导出 tcache，因此阴性不能证明
allocator 内绝对没有空闲字节；本项目按保守门把阴性处理为“不启用”。定义和降级规则见
[`产品侧落点建议 §1 门 B`](product_landing_recommendation_20260901.md#门-bm7-驻留确认)。

已有正向参照有两类：S2 的合成驻留周期在 XML 中出现 MB 级 `rest/unsorted`
([XML 摘录](../data/raw/cyclic_profile_replication_s2_20260831/m7_xml_excerpts.txt))；S4 把同一
表型的 M7、trim 回收与 faults 放在同批矩阵中
([紧凑证据说明](../data/raw/s4_retention_20260901/README.md))。二者都不是产品候选的
live/bin 分解。

## 3. 统一评估口径

三条路径都按相同问题评估：

1. **前置**：需要谁、什么构建或权限，以及能否按产品纪律执行。
2. **成本**：代码/工具改动、审批与采集成本，以及对业务的可能扰动。
3. **证据强度**：是否直接观察产品目标、是否相位对齐、是否能和外部 PD/faults 交叉。
4. **三门覆盖**：反信号排除、M7 驻留确认、调用/再激活/并发锁停顿预算分别覆盖到哪一步。

“覆盖”只表示该路径能提供该门所需输入，不表示门已经通过。

## 4. 路径 A：目标 owner 受控构建内调用 `malloc_info`

### 4.1 前置与建议采集形态

前置是目标 owner 能定位真实释放相位，并提供走正常签名链的受控构建。产品主收益面受
签名强制、不可安装包、不可运行自建二进制约束；状态报告已据此把正式路径收敛到代码级
注入而不是配置或临时工具
([平台约束](glibc_memopt_program_status_report_zh.md#4-平台约束实测发现))。

建议只在自然低频周期加入诊断钩子：

```text
相位前标记
  → malloc_info pre
  → 业务完成释放
  → malloc_info post-release
  → 外部只读 PD/zram/faults 对齐
  → 文件拉回并校验
  → 清理诊断产物
```

`malloc_info` 应在非关键线程执行，单独记录调用墙钟、XML 大小、返回码和相位时间戳；
XML 解析失败、超时或相位错位时整轮无效。运行时低频自检和失败降级原则沿用
[`落点建议 §3`](product_landing_recommendation_20260901.md#3-钩子形态建议)，本轮不写实现。

### 4.2 改动面与审批链

建议审批链依次为：目标 owner 确认相位与 allocator ownership；安全/隐私负责人确认 XML
字段和落盘目录；构建/签名 owner 产出诊断包；测试负责人冻结动作、轮数、有效轮和清理
门；证据通过脱敏后才进入仓库。代码改动只围绕诊断入口、相位标记、受控输出和总开关，
不在同一首轮加入 trim，以免把 M7 归因和效果 A/B 混在一起。

产品落盘必须使用应用获批的私有目录，限制文件数和生命周期；不得把 XML 写入共享或
公开日志。拉回后按大小或哈希校验，完成后由同一构建的诊断清理路径删除并复核。

### 4.3 扰动、证据与三门覆盖

`malloc_info` 会遍历 allocator 状态并生成 XML，本身可能拿锁、分配或产生 I/O。应把
“无诊断钩子 / 只打相位标记 / 打标记并导出 M7”做同动作配对，先量化诊断自身扰动，再
解释业务时延。已有落点建议已经要求记录 XML 生成和解析成本，不能把它混入 trim 时间
([成本与降级](product_landing_recommendation_20260901.md#3-钩子形态建议))。

| 启用门 | 覆盖程度 | 说明 |
|---|---|---|
| 反信号排除 | 强 | 同一产品构建可同时对齐 PD、zram、majflt、total PD 与 other-anon；仍需外部只读采集 |
| M7 驻留确认 | **强，直接产品证据** | 应用内、相位对齐、无需 debugger 表达式；能区分 rest/unsorted 变化，但仍看不到 tcache |
| 代价预算 | 部分 | 能测 M7 诊断扰动；trim 调用、再激活 faults 和并发锁停顿要在后续受控 A/B 单独补齐 |

证据强度评为最高。主要成本不是代码行数，而是 owner 协作、签名构建、合规落盘与一次
诊断包发布周期。

## 5. 路径 B：产品板 `gdb/lldb attach` 触发 `malloc_info`

### 5.1 前置与纪律限制

该路径需要产品板允许 ptrace、目标处于可调试域、板上或一次性工具包中有 ABI 匹配的
`gdb/lldb`，并取得产品安全、目标 owner 和测试窗口的明确授权。产品板不得通过安装包、
改配置或运行未签名自建程序来临时制造这些条件；现有产品执行策略明确禁止这类做法
([平台执行策略](glibc_memopt_program_status_report_zh.md#4-平台约束实测发现))。

当前新 LLVM 测试板也没有现成 LLDB：`rpm -q lldb` 为未安装、`command -v lldb` 无结果
([基线原文](board_baseline_llvm_image_20260831.md#44-用户lldbptrace-与-abi-原文))。历史测试板
曾通过未安装 RPM的一次性官方 LLDB 完成 attach、`malloc_info` 和 trim，但报告明确把
attach/回溯/XML/trim/detach 的整体包络与函数独立耗时分开
([历史注入证据](l6_gst_release_phase_probe.md#14-lldb)、
[包络边界](l6_gst_release_phase_probe.md#42-t2t4-与再次-playing))。这证明 permissive
测试环境中技术上可做，不证明当前产品板获准或工具就绪。

### 5.2 风险与采集约束

- attach 会暂停业务线程，直接污染现场墙钟和尾延迟；因此该路径只能回答一次性状态，
  不能用来核算业务代价。
- debugger 表达式在选中线程调用 `malloc_info` 时需要取得 allocator 锁；如果其他被暂停
  线程正持锁，可能挂住注入。历史探针先检查线程栈没有命中 malloc/free/arena，只是
  风险降低措施，不是一般性无死锁证明
  ([历史线程门](l6_gst_release_phase_probe.md#42-t2t4-与再次-playing))。
- 必须先导出线程/栈、选中安全相位，给表达式设置超时；超时、目标退出、PID 变化、detach
  后不存活或 XML 不完整均判整轮失败。禁止在信号 handler 内直接调用 `malloc_trim`，其
  非 async-signal-safe 风险已有专项审计
  ([注入风险审计](review_program_status_gpt5.md#c1-ld_preload-shim-的关键陷阱))。
- XML 仍需落入获批目录并在拉回校验后删除；不得把 debugger 临时工具或表达式脚本遗留
  在产品板。

| 启用门 | 覆盖程度 | 说明 |
|---|---|---|
| 反信号排除 | 中到强 | 可与外部只读序列配对，但 attach 暂停会切断自然时间轴 |
| M7 驻留确认 | **强但一次性** | 直接观察产品进程 allocator；相位与锁风险必须通过纪律门 |
| 代价预算 | 弱 | debugger 包络掩盖业务延迟，不能用于 trim 调用或并发锁停顿预算 |

证据强度对“当时是否存在 rest/unsorted”较高，对产品启用判断整体仅为中等。它适合筛选
目标，不适合上线性能结论。

## 6. 路径 C：测试板可注入代理复刻产品表型

### 6.1 现有能力映射

`alloc_bench` 已支持受控 cycles、paced rise/release/valley、release order、
`malloc_info` 四相位摘要、trim 时间、下一周期 faults 和外部 PD；完整接口见
[`工具 README`](../tools/alloc_bench/README.md#controlled-cycles)。它还支持
`--profile external:<file>` 的 `size_bytes weight` 直方图
([格式](../tools/alloc_bench/README.md#external-histogram-format))。

因此代理可以冻结：候选规模、线程数、对象尺寸直方图、释放比例、释放顺序、相位时长和
是否 trim；再用 external 1 s 采样检查 PD 是否形成与候选相似的 floor，用 M7 验证代理中
的 rest/unsorted，最后测回收和 faults。S2/S4 已证明这条采集链对合成 bins 驻留表型可用
([S2 定位](cyclic_fall_mechanism_attribution_v2_20260901.md#c4s2-新定位)、
[S4 判断](s4_reference_and_retention_trim_20260901.md#62-表型门控-trim))。

### 6.2 external histogram 能逼近什么

如果 owner 能提供脱敏的分配尺寸直方图和释放相位，external profile 可以逼近对象大小
混合；如果只能拿到 smaps floor，高度和时间形态可以通过 live-set、释放比例和 paced
周期对齐，但这只是输出形状校准。smaps 不含对象尺寸、寿命、跨线程 ownership 或
live/bin 标签，所以不能从 `+1736/+868/+580/+788 kB` 这些 floor 反推出唯一 histogram。

代理最多回答“哪类分配/释放机制能产生相似外部表型，以及在测试板上 M7/trim/faults
如何变化”。它不能回答“产品 floor 中有多少字节已 free”，也不能覆盖 secure 产品的
实际线程、插件、生命周期和发布路径。

| 启用门 | 覆盖程度 | 说明 |
|---|---|---|
| 反信号排除 | 代理内强，产品候选弱 | 能验证代理是否自动下降，不能替代产品同相位 zram/majflt/PD 链 |
| M7 驻留确认 | 代理内强，产品候选**不覆盖** | XML 能证明代理 bins，不证明产品 floor 的 live/bin 比例 |
| 代价预算 | 部分 | 可测测试板 trim、faults 和代理延迟；产品线程锁停顿、帧时延、能耗仍需产品或真实目标证据 |

证据强度对机制和 harness 校准为中等，对产品启用门为弱。优点是无需产品板即可推进，且
失败不会改变产品状态。

## 7. 路径对照与推荐排序

| 路径 | 关键前置 | 组织/执行成本 | 产品证据强度 | 主要不可替代价值 | 主要停止条件 |
|---|---|---|---|---|---|
| A owner 受控构建 | owner、签名诊断包、获批落盘与采集窗口 | 高 | **最高** | 真实相位、真实 allocator、可进入正式发布链 | 无 owner/签名链/合规输出目录 |
| C 测试板代理 | 已有工具链；最好有 owner 提供的 histogram/相位 | 低到中 | 低 | 立即校准采集器、M7 和机制边界 | 试图把形状匹配写成产品 live/bin 结论 |
| B debugger attach | ptrace/debug 域、ABI 匹配工具、产品安全书面授权 | 高且风险集中 | 中 | 无源码改动时的一次性产品 M7 | 未授权、工具缺失、锁/超时门失败、需业务代价结论 |

推荐执行方式：

1. **A 作为正式主线。** 先只做 M7 诊断包，闭合候选 live/bin；阳性后另立 trim A/B，
   不把两次审批和两类结论混在首轮。
2. **C 与 A 的等待期并行。** 使用已有 S2/S4 合同验证 XML 解析、错误门和候选形状的
   可复刻范围；报告标题必须带“代理”，不登记产品收益。
3. **B 只在 A 暂时不可用且产品安全明确批准时启用。** 它只产出一次性 M7 和目标筛选，
   不产出业务代价；当前测试板 LLDB 缺失也不得通过现场安装绕过。

## 8. 对落点建议三门的最终影响

本轮没有让任何产品候选通过 M7。它只给出取得 M7 的可行顺序：A 能完整建立产品候选的
门 B 输入；B 能在严格纪律下提供一次性门 B 辅证；C 只能验证代理。无论选择哪条路径，
反信号门和代价门仍需独立同批证据。三门缺一时，继续沿用“默认不调用”的降级策略
([启用门总则](product_landing_recommendation_20260901.md#1-启用门清单))。
