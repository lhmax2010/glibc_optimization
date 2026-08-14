> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# v2.2 评审汇总仲裁（2026-07-09）

- 输入：四份评审（Codex GPT-5 / Claude Opus 4.8 / Kimi / Gemini 2.5 Pro）
- 仲裁基准：Batch 1/2 原始报告（本方独立解析过 99 行全表）+ alloc_bench 源码 + 既有源码仲裁记录

## 0. 前置裁定：Gemini 评审整体无效（Part A）

Gemini 断言 Batch 2 "smoke 失败、矩阵未运行、结论来自幽灵实验"。经核对原始报告：99/99 行有效数据、全部退出码 0；它引用的 EXIT=126 与 smoke 格式失败在报告异常清单中**明确标注为"预跑归档、不属于 99 行矩阵"**。Gemini 只读了异常节就否定全部数据，其 Part A 全表（UNVERIFIABLE×4 + 对 L2 的 OVERREACHING 论证）作废；且再次日期错误（2024-07-30）、R11 对象写错（tcache_max ≠ tcache_count）。**连续两轮实质错误，裁定将 Gemini 移出评审池**（其 Part B/C 的可用内容与他家重叠，无独有损失）。

## 1. 三家有效评审的共识与仲裁

### 1.1 L2 降级：方向维持，四点修正全部采纳

- **C1（Claude，OVERREACHING 成立）**：v2.2 把 L2 的内存面写成"空闲守护进程内小而免费；包络之外为负"是错的——持续分配稳态（mixed/large-transient）下 L2 实测 **−9 MB**（arena 5→2 坍缩，Claude 用板上 malloc_info XML 确认归因）。正确表述：L2 在持续分配下**内存为正、性能为灾**；churn 下双输；空闲下小赢免费。
- **C2（三家一致，最强共识）**：**arena_max=3/4 从未被测**。悬崖发生在 4 线程:2 arena 的 2:1 超订上；arena_max=核数可能以远小于 10% 的代价收下那 −9 MB。补测 arena_max∈{3,4} 是 Batch 2.5 第一优先格。
- **C3（Kimi）**：悬崖数字有档依赖（small-churn 仅 −2.2%），v2.2 引用时应带档标注；threads=核数是争用上界（Claude），真实服务代价必然更低。
- **C4（n=3 问题，Codex/Claude/Kimi 共识）**：churn Rss 反转**方向**成立（3/3 反转，C0 噪声 0.1 MB，malloc_info 显示 2 arena 内 retained-free 9.3→29.8 MB 摆动——机制被板上归因数据直接证实），**幅度**（+8~+26 MB）离散过大，v2.3 引用时改为"方向确认、幅度待 n≥5"。

### 1.2 R11（tcache_count=0）：维持，附重开条件

Codex 认为"全局否决"外推过强（数据只覆盖 live 池复用类负载）；Claude 认为机制性成立（快路径移除的代价与负载无关，内存零回报因 chunk 迁入 bins 也是机制性的）。仲裁：**R11 维持**——四档异构负载全部为负、机制解释自洽；但采纳 Codex 的范围修正，R11 措辞加重开条件："仅当某真实进程的 malloc_info 证明 tcache 驻留构成显著 RSS 且该进程分配频度极低时，可按例重审"。

### 1.3 L11/L12：UNTESTED-EFFECT 维持，补测义务成立

三家一致：这是工具属性（live 池均匀替换结构性不产生 fastbin/unsorted 积压），且补测便宜。采纳 Kimi 的两个具体 profile（`burst-free-small`、`unsorted-drain`）+ Gemini 的跨 fastbin 边界尺寸混合思路，进 alloc_bench v1.1。**在补测完成前 L11/L12 不得进入任何否决清单。**

### 1.4 首发包：加"组合未验证"标注（Codex）

L1+L3 各自验证过、组合从未同格实测。Batch 2.5 加一个 L1+L3 组合格。

### 1.5 工具偏差清单（Part B 汇总，全部采纳进 alloc_bench v1.1）

| 偏差 | 影响方向 | 修正 |
|---|---|---|
| live 池均匀替换、无突发释放 | L11/L12 系统性显零 | 新增 burst-free-small / unsorted-drain 档 |
| 大块仅触碰首尾 128 B（Claude 抓到） | 大块 RSS 贡献失真，**低估 L3** | 新增 `--touch-full` 选项，large-transient 档默认全触碰大块 |
| idle 相位持池不释放 | 回收面（trim/收缩）从未被测：99 行 idle_rss≈measure_rss | 新增可选 `--idle-release N%`：idle 前释放 N% 池，观察回收 |
| threads=核数 = 争用上界 | L2 悬崖是最坏情形 | arena sweep + 线程数减半对照格 |
| Rss 仅相位末采样 | 错过峰值形态 | measure 相位内周期采样，报告中位+p95（Gemini/Kimi） |
| churn 全量同步换代 | 或高估 L1 | 低优先级：加 stagger 选项，暂不阻塞 |

### 1.6 Part C 新方向仲裁

- **采纳-立即**：arena_max knee 扫描（§1.1-C2）；L2 前置门可执行化——用 malloc_info 时间序列（Claude 方案，零依赖）为主、perf 锁剖析（Gemini C4）为辅。
- **采纳-新工作流**：内核侧杠杆（MGLRU——板内核 6.12 支持、zram+zstd、KSM、overcommit=2）三家收敛且直击 PSI 北星，但属系统级边界决策（Kimi Top-3 第 3 条成立：不应只当协变量）——在 v2.3 开独立章节"内核侧相邻轨道"，与 glibc 轨道分开排期评审。
- **采纳-方法**：PSI 至今没对任何杠杆实测过（Claude 点破北星指标空转）——TV 阶段协议必须含 PSI 压力注入项。
- **存疑-要求先验证**：Full RELRO/bind-now 的 PSS 收益（Gemini C1，Claude 也提及）机制可疑——GOT 页在重定位时无论 RELRO 与否都会被写脏成私有页，RELRO 改的是保护位不是共享性，"可像 .text 一样共享"的说法大概率不成立。要求提案方先用 pmap/smaps 在单库上实证私有脏页差值，否则不进杠杆清单。
- **采纳-校准**：jemalloc/mimalloc LD_PRELOAD 对照（Gemini C3/Claude），定位为"碎片率天花板校准"非替换方案——这本来就是最初方案里的第 5 条，回归。

## 2. 行动序列（依赖排序）

1. **alloc_bench v1.1**（§1.5 修正 + 两个新档）——Codex 实现任务；
2. **Batch 2.5 矩阵**：arena_max{3,4} × 4 档、burst 两档 × {C0,L11,L12}、L1+L3 组合格、churn 敏感格 n≥5；
3. **v2.3 文档**：吸收本仲裁全部修正 + 内核侧相邻轨道章节（数据依赖项等 Batch 2.5）；
4. TV 阶段协议草案（含 PSI 注入、L2 争用画像门的可执行定义）。

## 3. 评审池调整

Codex（R11 范围修正+组合格漏洞）与 Claude（malloc_info 归因、−9 MB 翻案、四偏差清单、PSI 空转）本轮质量最高；Kimi 的重算与补测 profile 具体可用；Gemini 移出（§0）。后续三家制。
