> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Tizen glibc 内存优化项目总结报告独立评审

## 评审头部

- **评审者**：GPT-5（Codex）
- **日期**：2026-08-06
- **基线**：`tizen_base`，`8f08a7e30396822a8d969d357822a6ffd56b43fb`
- **对象**：`docs/glibc_memopt_program_status_report_zh.md`
- **方法**：从 Batch 1/2/2.5 原始逐次表重算中位数、配对差值和范围；交叉核对三轮 recon、PG0、历轮裁决、`alloc_bench` v1.1a 与本树 malloc/rtld 源码；上游部分核对 glibc 2.41、2.42 标签及当前 master 提交。KiB 到 MiB 按 1024 换算。

## 总体裁决

报告对板级机制筛选的主干叙述基本可靠，但尚不适合作为“9 月可交付能力”的无条件摘要。最严重的问题不是板级算术，而是把**合成负载上的可回收上限**写成平台正在损失的内存，以及把实际上受 `AT_SECURE` 阻断的 `LD_PRELOAD` 当作首选 Demo 注入路径。另有两处证据强度被抬高：`L1+L3` 没有同批因子格，不能证明“无交互”；“全部内存 tunable 已闭合”混淆了优化杠杆、测量功能和安全/诊断项。

## Part A - 事实与结论核查

| 项目 | 裁决 | 原始数据重算 | 评审意见 |
|---|---|---|---|
| L6 `malloc_trim(0)` 59.9 MB | **SUPPORTED（数字）/ OVERSTATED（外推）** | 三次 `measure -> idle`：`60264/61336/61896 KiB`，即 `58.85/59.90/60.45 MiB`；配对中位数 `59.90 MiB`。trim 前 RSS 中位数 `114792 KiB = 112.10 MiB`。两个无 trim 控制格均为 `+40 KiB`，不是“精确为零”。 | 数字准确，但仅来自 mixed、50% 释放、n=3、线程静止的微基准。报告第 5 节把它称为“平台当前白白损失”不成立；它只是该构造负载的瞬时可回收上限，尚无真实 service、驻留时长、refault 或锁停顿证据。 |
| L3 固定 mmap/trim threshold | **SUPPORTED（板级格）** | small/mixed/large/churn 吞吐 `-0.145/-0.073/-4.947/-0.226%`；RSS `0/-1680/-944/-208 KiB`，即 `0/-1.641/-0.922/-0.203 MiB`。 | “四档约 0%，large -4.9%”和 `-0.9~1.6 MB` 的有效收益范围算术正确，但后者略去两个接近零的 profile；也尚未证明真实 service 的阈值自适应确有问题。 |
| L1 stack cache 40 MiB -> 1 MiB | **SUPPORTED（单一作用面）** | thread-churn：`1895265.335 -> 1895780.165 ops/s`，`+0.027%`；RSS `73784 -> 72748 KiB`，`-1036 KiB = -1.012 MiB`。 | 报告数字正确。只在固定 4 线程 churn 上成立；长期稳定线程不会释放到 stack cache，收益面需要真实线程生命周期画像。 |
| L2 超订比曲线 | **SUPPORTED（观测点）/ OVERSTATED（规则）** | mixed 4T：4 arena `+1.01%/-1.59 MiB`，3 arena `-21.96%/-4.04 MiB`，2 arena `-45.88%/-5.75 MiB`；mixed 2T/2 arena `+0.84%/-1.22 MiB`。large-transient 4T/2 arena `-1.75%/-10.75 MiB`。churn n=5：4/3/2 arena 吞吐 `-5.97/-20.00/-44.32%`，RSS `+11.00/+17.86/+21.31 MiB`。15 个处理重复的 RSS 全高于 5 个基线重复。 | 4 核板上的方向坚实，报告的 `+11~21 MB` 是中位数差的合理四舍五入。但 `arena_max=线程数/核数` 只是上限，arena 按竞争惰性创建；“1:1 天然安全”不是跨 SoC 定律。真实进程应以峰值并发 malloc 线程数和实际 arena 数作门，而非仅 CPU 核数。 |
| R11 `tcache_count=0` | **OVERSTATED** | small/mixed/large/churn 吞吐分别 `-10.11/-8.20/-5.74/-7.69%`；RSS `-16/+168/+420/+1604 KiB`。 | “性能损失 6~10%”成立；“零内存回报”不精确，结果从微小节省到 `+1.57 MiB` 恶化。更重要的是仅覆盖 live-pool/churn 型负载，不能推出所有低内存进程均无收益。AOSP 的低内存 jemalloc 配置曾明确关闭 tcache 以节省 PSS，说明该机制在特定线程/对象寿命分布下有真实作用面。应否决“全局默认关闭”，不应永久禁止按服务复测。 |
| R12 `mxfast=0` | **SUPPORTED（默认否决）/ OVERSTATED（全局否决）** | burst-free-small：吞吐 `10534439.088 -> 9944215.511 ops/s`，`-5.60%`；RSS `1464 -> 1432 KiB`，`-32 KiB`。 | 作为 2.40 的默认 RSS 优化项不值得推进；但 n=3、单一人工 fastbin profile 不证明所有生产积压形态无效。报告写 `-31 kB` 与原始表的 `-32 KiB` 有轻微单位/舍入偏差。 |
| R13 `tcache_unsorted_limit=3` | **SUPPORTED（RSS 候选否决）/ OVERSTATED（“无效”）** | unsorted-drain：吞吐 `+0.288%`；RSS `138484 -> 138768 KiB`，`+284 KiB`。 | 此值在该作用面没有内存收益，足以否决当前候选；但只测一个阈值和一个定制 profile。该 tunable 本质还可约束一次 tcache refill 扫描工作量，不能据此否定其尾延迟用途。 |
| L1+L3 组合 | **SUPPORTED（数值）/ OVERSTATED（无交互）** | Batch 2.5 churn：C0 n=5 中位数 `1783898.127 ops/s, 72708 KiB`；组合 n=3 为 `1785091.975, 70224 KiB`，即 `+0.067%/-2484 KiB = -2.426 MiB`。 | 报告的 `+0.1%/-2.43 MB` 正确。Batch 2.5 没有同日、同随机块的 L1-only 与 L3-only 格，不能估计交互项；跨 Batch 2 拼单格也不能证明“无交互惩罚”。 |
| AT_SECURE 10/10 复核 | **SUPPORTED（值）/ OVERSTATED（glibc 可达量）** | PG0 的 10 个 PID 与 recon3 全部一致；Top-5 proxy heap 为 `14872+10080+7912+4960+3412 = 41236 KiB`，且 5/5 为 `AT_SECURE=1`。 | 10/10 复核成立。但排序量是 `[heap] + 1 MiB 对齐匿名段 Private_Dirty` 的 proxy，可能混入 CoreCLR GC 堆/JIT；不能直接称为 41.2 MiB 的“glibc heap 可优化面”。 |
| Batch 1 secure 阴性对照 | **SUPPORTED（窄结论）/ OVERSTATED（“精确”）** | `ServiceV` C0/C3 均为 RSS `10424 KiB`、PSS `5284 KiB`、arena `1`；C3 的 `/proc/<pid>/environ` 可见 tunable 字符串，C0 九次 RSS 噪声极差为 `72 KiB`。 | 设备证据支持该 secure 目标未产生可见效果，但只有一个进程、每格三次快照。“效果精确为零”应改为“观测差为零且低于 72 KiB 噪声带”；源码才支撑 secure tunable 的一般过滤机制。 |

本表原始锚点：`docs/board_ab_batch2_report.md:143-243`、`docs/board_ab_batch25_report.md:92-173`、`docs/board_ab_batch1_report.md:62-106`、`docs/pg0_decisive_probe.md:36-53`。百分比均由表中未舍入吞吐中位数重算；L6 同时计算“配对差中位数”和“前后中位数之差”，两者均四舍五入为 59.9 MiB。

### 夸大、遗漏与否决边界

1. **最大夸大**：报告一面承认没有真实负载绝对收益，另一面又把 L6 的 59.9 MiB 写成平台正在损失的内存。这两个表述冲突，应统一为“受控负载中的机制上限”。
2. **第二处夸大**：Batch 1 的 service RSS 信号多为 `28~36 KiB`，接近或低于噪声，不应与 Batch 2.5 的机制效应并列暗示产品收益。
3. **已经取得但低估的价值**：PG0 已证明 Top-5 均受 secure-exec 环境过滤约束，这比多一个微基准数字更直接地改变部署架构；另发现 `dlconf` 路径的 hwcaps 泄漏和未初始化字段风险，属于正确性/内存安全价值，报告仅作为普通否决项带过。
4. **14 项否决不应视为同等永久**：R6 “全 libc `-Os`”实际是受构建与范围约束的 parked 项，不能写成机制无效；R11/R12/R13 只支持否决当前默认提案；R14 应区分 `hugetlb=1` 的 THP madvise 路径和 `>=2` 的显式 huge page 路径。当前 armv7/无 THP 平台上前者无效，后者可能放大内部碎片。
5. **可维持硬否决的核心**：R2 `arena_test` 不是 arena cap；R3 `rseq` 不构成 RSS 杠杆；R8/R10 主要改变虚拟地址或 `PROT_NONE`，不是常驻页；R5 `libc_freeres` 是退出清理接口，不是运行期回收策略。

## Part B - 技术路线完整性

### B1. glibc 2.40 覆盖闭合性

对照 `elf/dl-tunables.list` 和 `sysdeps/nptl/dl-tunables.list`，报告的“全部内存相关 tunable 已闭合”按字面是 **WRONG**，但 ptmalloc RSS 优化主集合接近闭合：

| 遗漏/分类问题 | 结论 |
|---|---|
| `glibc.mem.tagging` | 未进入 L/R。当前 armv7 无作用，但未来 aarch64 上同时影响内存、性能与安全。应列为“平台安全能力，非优化候选”，不能为省内存而默认关闭。 |
| `glibc.mem.decorate_maps` | 未进入 L/R，合理定位应是“观测工具”。它不降低 RSS，却是验证 arena 归因的重要前置能力。 |
| `malloc.check`、`malloc.perturb`、`rtld.enable_secure` | 有内存或运行时副作用，但属于诊断/安全语义，不应塞进“存活/否决”二分法。建议增加 `OUT-OF-SCOPE/MEASUREMENT/SECURITY` 分类。 |
| `mutex_spin_count` 等 NPTL 项 | 对同步性能有影响，未发现可信的 RSS/PSS 杠杆；可记录为 negative fact。 |

源码锚点：`elf/dl-tunables.list:26-151`、`sysdeps/nptl/dl-tunables.list:18-42`、`malloc/arena.c:300-314`。结论应改为“2.40 ptmalloc 的可部署 RSS tunable 候选已基本闭合”，而不是所有 memory tunable 已闭合。

### B2. glibc 2.41/2.42 与近期 upstream

| 版本/提交 | 变化 | 对本项目的影响 |
|---|---|---|
| 2.41 [`226e3b0a4136`](https://github.com/bminor/glibc/commit/226e3b0a413673c0d6691a0ae6dd001fe05d21cd) | `calloc` 增加 tcache 路径。 | 升级后 R11/L4 的成本收益曲线会变，必须重跑 calloc-heavy profile。 |
| 2.41 [`e2436d6f5aa4`](https://github.com/bminor/glibc/commit/e2436d6f5aa47ce8da80c2ba0f59dfb9ffde08f3) | 释放的小 chunk 直接进入 smallbin，改变 unsorted-bin 行为。 | R13 的 2.40 微基准不能直接迁移到 2.41+。 |
| 2.42 [`cbfd7988107b`](https://github.com/bminor/glibc/commit/cbfd7988107b27b9ff1d0b57fa2c8f13a932e508) | tcache 扩到 large chunk，现有 `tcache_max` 可提高到 4 MiB。 | 不是新 tunable，却显著扩大每线程驻留上限；升级时应重开 L5/R11，并把 RSS 与吞吐一起测。见 [2.42 NEWS](https://github.com/bminor/glibc/blob/glibc-2.42/NEWS)。 |
| post-2.42 [`bb5a4f5295ce`](https://github.com/bminor/glibc/commit/bb5a4f5295ced26532939703867c35f2ce8c149b) | fastbin 被移除，`M_MXFAST` 退化为兼容 no-op。 | R12 将变成版本过时项，不应作为长期机制结论。 |
| post-2.42 [`0b9210bd760b`](https://github.com/bminor/glibc/commit/0b9210bd760b5281f2e9f3e6640368ccb5f4a7ae) | 默认 tcache fill count 从 7 增到 16。 | 默认常驻缓存上限上升，低内存 TV 升级前应重测 L4/R11。 |
| post-2.42 [`05a14648e92c`](https://github.com/bminor/glibc/commit/05a14648e92c3da5fa44bdd24e6b56f8d9f38b1a)、[`321e1fc73f53`](https://github.com/bminor/glibc/commit/321e1fc73f53081d92ba357cdd48c56b79292020) | secondary arena THP 支持及 AArch64 2 MiB THP 默认。 | 未来 aarch64 TV 上可能改变吞吐、RSS 与内部碎片，不能沿用当前 armv7 R14 结论。 |

未发现 2.41/2.42 新增 ptmalloc decay/自动 trim tunable，也未发现两版本间 `malloc_trim` 获得新的回收语义。真正需要建立的是**版本迁移重开规则**，因为既有 tunable 的实现和默认值正在变化。

### B3. 不替换分配器的补充方向

| 方向 | 可行性与预期 | 验证成本/锚点 |
|---|---|---|
| 生命周期分级回收 | **高**。后台化或大场景退出时 trim，短时切后台仅轻量回收，设置 cooldown/hysteresis；收益应以 `MiB*s` 而非瞬时 RSS 表达。比信号盲触发更贴近可回收相位。 | 1 个 service 约 3-5 天接钩子与 A/B；Android 同样建议在 UI hidden/background 回收可重建内存：[官方内存指南](https://developer.android.com/topic/performance/memory)。 |
| 分配画像驱动的 per-service 参数 | **中高**。用实际场景的分配大小、线程和寿命画像选择 L2/L3/L4/L5，不追求全局默认。研究中自动调 glibc 参数可降低平均 heap，峰值未必下降。 | 约 1 周完成采样、回放和 2-3 个候选；GreenMalloc 报告最高约 4.1% 平均 heap 改善：[论文](https://arxiv.org/abs/2510.21405)、[artifact](https://zenodo.org/records/17182847)。 |
| 请求/事件计数触发 trim | **中**。适合长期驻留 daemon：累计 N 次任务且进入空闲窗口时回收，避免周期 timer 在热路径抖动。 | 2-4 天/服务；OpenResty 曾采用按请求数触发 `malloc_trim` 并讨论真实流量副作用：[issue](https://github.com/openresty/lua-nginx-module/issues/872)。 |
| 与 zram/内核回收协同 | **中**。用户态先丢弃已 free 的页，可避免它们进入 zram；DAMON/MGLRU 只能看到冷热页，不知道 allocator free/live，适合作为压力侧对照而非替代 L6。 | 约 1 周，需同步采 `zram mm_stat`、swap、fault、PSI 和 refault；[DAMON_RECLAIM 文档](https://www.kernel.org/doc/html/latest/admin-guide/mm/damon/reclaim.html)。当前 TV 是否启用 MGLRU 尚未验证。 |

## Part C - 三周 Demo 计划可行性

### C1. `LD_PRELOAD` shim 的关键陷阱

1. **它不能绕过 `AT_SECURE`**。`elf/rtld.c:178-192,2606-2613` 与 `elf/dl-load.c:1851-1869` 明确限制 secure-exec 的 preload：带路径的 DSO 被拒，受信目录中的对象还需满足 secure 模式要求。报告第 6 节把 preload 当作 Top-5 secure 目标的免改包路径，是 **WRONG**。它最多用于非 secure RPI 机制探索；也不能附着到已经运行的进程，必须经真实 launcher 重启并先证明 preload 环境没有被过滤。
2. constructor 只早于 `main`，不早于依赖 DSO 的 constructor；这些 constructor 已可能创建 arena。`mallopt(M_ARENA_MAX)` 只改 `mp_.arena_max`（`malloc/malloc.c:5487-5491`），不会删除既有 arena；`malloc/arena.c:822-862` 还缓存 arena limit。非 secure 实验若坚持 shim，应拦截 `__libc_start_main`，在调用真实入口前设置，并用 maps/malloc_info 证明时序。
3. 对之后 `dlopen` 且使用 libc malloc 的库，mallopt 是进程全局的，原则上生效；但自带 allocator、私有 heap 或 CoreCLR GC heap 不受 ptmalloc trim 支配。
4. **信号 handler 不能调用 `malloc_trim`**：它不是 async-signal-safe，若打断 malloc/arena lock 可死锁。handler 只做 `write` 到 self-pipe/eventfd，由专用线程或主循环在安全相位调用。控制组也必须加载同一 shim/线程并执行 no-op，消除注入开销。
5. `malloc_trim` 会遍历并锁住所有 arena（`malloc/malloc.c:5217-5226`）；Batch 2.5 在线程静止时测得 59.9 MiB，未覆盖并发暂停。CoreCLR 目标还需先核对信号占用、GC 相位与 native heap 占比，禁止只在处理组强制 GC。

### C2. 三周能否产出可信数字

三周内可以完成“一个非 secure 目标的一项机制验证”，或“一个 secure Top-5 目标的源码钩子 A/B”；无法可信完成报告当前暗示的多个产品目标、完整 PSI、L2/L3/L6 联合上线判断。最可能超期的是**secure 目标的签名构建/部署路径**，最可能产出不可裁决数据的是**真实场景噪声与 phase 未对齐**。RPI 的内存规模和 PSI 响应与产品板不等价；产品 PG0 压力测试又因持续 SIGSEGV 失效，不能用它补齐北星结论。

### C3. 真实负载协议最低要求

- 固定离线素材、网络状态、初始缓存、前后台路径和 dwell；冷启动、热启动分层，不混算。
- 先做 C0/C0 配对估噪，再做 ABAB/随机块 n>=20；同一热状态和开机阶段配对，报告配对差与置信区间。
- 用应用内时间戳锁定 launch、场景峰值、background、trim、resume；固定时点采 RSS/PSS/Private_Dirty、named arena、fault、zram/swap 和 PSI total。
- L6 至少三格：同 shim no-op、释放无 trim、释放+trim。结果同时给内存时间收益 `MiB*s`、resume p95/p99、minor/major fault 与卡顿。
- crash、LMK、PID 变化、场景步骤失败均预注册为无效轮；不能静默剔除慢轮。

### C4. 更快拿到可信数字的路径

最可信的首选不是 preload，而是给一个 Top-5 secure service 加极小源码钩子：在真实 background/scene-exit 回调调用 `malloc_trim(0)`，通过正常签名链部署。它虽然有一次构建成本，却直接回答产品可达性、真实收益和恢复代价。

在此之前，可在允许 ptrace 的测试目标上由 gdb attach 后于已确认空闲点调用 `malloc_trim(0)`，快速测“一次性可回收上限”；该结果只能用于选目标，不能当性能或上线证据。非 secure RPI 可用 `__libc_start_main` shim 验证早期 mallopt，但不得外推 secure 产品可部署性。

## Part D - 竞争力判断

### D1. 固有优势与劣势

| 维度 | ptmalloc 调优 + 主动回收 | 替换分配器路线 |
|---|---|---|
| ABI/启动风险 | 保持 libc malloc ABI 与现有启动路径，改动可限制到单 service。 | 静态替换进入 glibc 会触及早期启动、跨 DSO 分配/释放、`mallopt`/`malloc_info` 语义及调试工具兼容，boot/runtime 验证面更大。 |
| 回滚粒度 | 可按 service、按钩子或参数回滚。 | 通常以 libc/RPM/镜像为单位，粒度更粗。 |
| 收益上限 | 不能搬移 live object，主要回收页对齐的空闲区域；对内部碎片和长期混合寿命堆上限有限。 | arena、size class、decay、后台 purge 设计可能取得更高碎片/吞吐上限。 |
| 紧内存适配 | 无额外第二套元数据/线程 cache；可在明确生命周期点先于 zram/LMK 丢弃 free 页。 | 默认多 arena、thread/per-CPU cache 可能增加常驻量，必须专门收紧；`decay=0` 也可能提高 fault 与 CPU。 |
| 运行时代价 | L2 过低有锁竞争；L6 有全 arena 锁与 refault；依赖应用相位钩子。 | 可能降低竞争与碎片，但集成错误的爆炸半径更大，且后台清理线程也有 CPU/调度成本。 |

### D2. thread-cache 在紧内存设备上的证据

- AOSP 的 low-memory jemalloc 配置明确采用单 arena 并关闭 tcache “to save PSS”，说明移动端工程实践确认 thread cache 可能以常驻内存换吞吐：[提交](https://android.googlesource.com/platform/external/jemalloc/+/08795324eae5f68d211dc5483746af51203dc661^!/)。后续 Android 构建配置也注明 tcache slot 越多 PSS 越高：[Android.bp](https://android.googlesource.com/platform/external/jemalloc_new/+/172b1f3f9e117546f00aeeaa5358439c1ed3392c/Android.bp)。
- jemalloc 自身面向极端节省内存的建议是 `narenas:1,tcache:false,dirty_decay_ms:0,muzzy_decay_ms:0`：[TUNING.md](https://android.googlesource.com/platform/external/jemalloc_new/+/refs/heads/master/TUNING.md)。
- TCMalloc 官方设计说明 per-thread cache 随线程数扩张，per-CPU 模式也按 CPU 保留 slab/cache；统计文档给出的默认 per-CPU 上限为约 1.5 MiB：[design](https://google.github.io/tcmalloc/design.html)、[stats](https://google.github.io/tcmalloc/stats.html)。

这些证据证明“存在更高 RSS/PSS 的机制风险”，不证明替换分配器必然比 ptmalloc 更差。最终只能由同板、同目标、同场景、同统计门的 A/B 判断。

### D3. 9 月前最该补的一项数据

在 **1.6 GB 真实 TV** 上选择一个 Top-5 `AT_SECURE` service，通过正常签名源码钩子，在真实“前台重负载 -> 后台驻留 -> 恢复”生命周期做 n>=20 配对 A/B。唯一主指标建议为：

> 每次后台驻留净节省的 PSS/RSS 内存时间（MiB*s），以及对应恢复 p95/CI、major/minor fault、zram/swap 与崩溃率代价。

这一个结果同时关闭目前最致命的四个空白：产品可注入、glibc 可达面、真实收益持续时间、refault/体验成本；也能与另一技术路线使用同一计分板公平比较。

## Top-3：应立即处理

1. **删除“LD_PRELOAD 绕过 AT_SECURE”的实施假设**，本周内锁定一个 secure Top-5 服务的签名源码钩子路径；否则三周计划会在第一步失效。
2. **把 L6 的主张从 59.9 MiB 瞬时 RSS 改成真实服务的净 `MiB*s + resume cost`**，并完成一个 n>=20 产品板 A/B；这是 9 月前最有说服力的数据。
3. **重写证据分级与版本边界**：区分微基准机制、产品收益、默认否决和特定负载可重开；同时记录 2.41/2.42 的 tcache/unsorted-bin 语义变化，避免冻结结论在升级后失真。

## negative_facts

- Batch 2.5 没有完整的 L1 × L3 因子设计，不能计算交互项。
- 无 trim 控制格 RSS 为 `+40 KiB`；可以说“未观测到回收”，不能说“精确为零”。
- `arena_max` 是上限，不等于运行时一定创建的 arena 数；核数不是并发 malloc 线程数。
- `malloc_trim` 自 glibc 2.8 起会处理所有 arena，但它不能回收仍被占用或无法形成可丢弃页的碎片：[malloc_trim(3)](https://www.man7.org/linux/man-pages/man3/malloc_trim.3.html)。
- `LD_PRELOAD` 不是 secure-exec 的通用旁路；Top-5 的 `AT_SECURE=1` 反而是其直接阻断条件。
- `malloc_info`/`mallinfo2` 是 ptmalloc 观测接口，不能原样复用来评估替换分配器；smaps、fault、PSI 和场景框架才是可复用部分。
- glibc 2.41/2.42 没有新增自动 decay/周期 trim 机制；现有 tunable 的语义变化比“新旋钮”更值得警惕。
- 当前证据不支持任何真实 Tizen service 已取得 59.9 MiB、5% 或其他绝对产品收益。

## cannot-verify

- 无法从离线材料确认产品分支是否启用 `glibc.mem.decorate_maps`、MGLRU、DAMON 或相关内核配置。
- 无法确认 Top-5 proxy heap 中 ptmalloc、CoreCLR GC、JIT 与其他匿名映射各自占比；必须用 named VMA、进程内观测或针对性源码探针拆分。
- 无法确认产品签名/打包流水线在三周窗口内能否交付单 service 实验包。
- 无法确认 launchpad/pool 对 `GLIBC_TUNABLES` 的逐项环境白名单行为；PG0 只证明一般环境变量大多继承，没有直接证明该变量可达。
- PG0 产品 PSI 压力实验受持续 SIGSEGV 与安全逻辑缺陷污染，不能验证产品压力曲线、LMK 护栏或 L6 在压力下的净收益。
- 无真实 service 的 refault、全 arena 锁暂停、恢复首帧/首屏、长期碎片和稳定性数据。
- 上游 post-2.42 提交属于后续发布候选；在产品选定升级版本前，不能假定它们必然进入目标 glibc。
