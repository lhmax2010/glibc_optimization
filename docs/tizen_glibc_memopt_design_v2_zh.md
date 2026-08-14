> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Tizen glibc 内存优化 — 设计提案 v2.4（冻结候选，中文版）

- 状态：已整合 — 吸收四家异构 AI 评审（Codex GPT-5、Claude Opus 4.8、Kimi、Gemini 2.5 Pro），全部评审冲突已对照 upstream `glibc-2.40` 完成源码仲裁，纳入 Q6 dlconf 抽查结论（`docs/review_dlconf_rss_spotcheck_codex.md`），以及两轮真机证据（Batch 1 服务 A/B：`docs/board_ab_batch1_report.md`；Batch 2 微基准曲线：`docs/board_ab_batch2_report.md`；Batch 2.5 knee/公平作用面/回收实验：`docs/board_ab_batch25_report.md`）
- 目标平台：Tizen TV，armv7l（主要，32 位）与 aarch64
- 审计基线：glibc 2.40，分支 `tizen_base`，commit `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- 取代：`tizen_glibc_memopt_design_v1.md`

## 0d. v2.3 → v2.4 变更记录（定稿前评审修正；四家评审对 §0c 全部数据断言一致 SUPPORTED）

- **§8 Plan B 与 v2.3 幸存杠杆集对齐**（原为过期状态，四家均抓到）：mallopt 仅覆盖 **L2、L3**；L11/L12 引用删除（已否决为 R12/R13）；L6 本身是代码改动，天然不受 AT_SECURE 影响。
- **L2 门可执行化**：(a) 安全下限升级为*构造性安全*——并发**运行中**的分配线程数 ≤ 在线核数，故 `arena_max = 核数` 在任何 SoC 上保证运行线程:arena ≤1:1（论证可移植，2:2/4:4 双对照实证）；(b) churn 分类器定义：周期采样 `/proc/<pid>/task`，task-ID 换手率持续 >0 ⇒ churn 类 ⇒ 禁用；(c) **更深 cap（低于核数）为按 SoC 发放的许可**——4:3=−22%/4:2=−46% 的中间曲线是 4 核数据，固定超订比下锁竞争随核数变陡。
- **churn 反转幅度口径修正**（中位数 vs 重复间范围）：各 cap 档中位数 +11~+21 MB；单次重复跨 +5~+44 MB。禁令建立在 15/15 方向上，不受影响。全文 Δ 数字均为重复中位数口径。
- **L6 未测代价清单扩充**：除 refault 外，全 arena 串行锁遍历（`malloc/malloc.c:5217-5226`）是在线程静止下测的——trim 期间并发分配线程的停顿为 TV 试点强制测量项。
- **新增 R14**（收尾项）：`glibc.malloc.hugetlb` 在 armv7l 上正式否决（原为 Q3 括注）。
- 记录 negative_fact：`glibc.pthread.mutex_spin_count` 内存中性——范围外，不再重提。

## 0c. v2.2 → v2.3 变更记录（Batch 2.5 结论——四个悬案闭环）

- **L2 门定量化——代价变量是线程:arena 超订比，不是 arena 数。** Batch 2.5 扫描（armv7l）：1:1 免费（mixed arena_max=4：+1.0%/−1.6 MB；2 线程:2 arena 对照 +0.8%/−1.2 MB 交叉印证）；4:3 付 −22%，4:2 付 −46%。低分配率 service 可低价吃激进 cap（large-transient arena_max=2 → −10.8 MB 仅付 −1.7%）。**churn 反转在全 cap 谱系 n=5 成立**（+11~+21 MB，15/15 重复高于基线）→ churn 型任意 cap 禁止。新规则：`arena_max ≥ 峰值并发分配线程数`（≈核数）为安全下限。
- **新增 R12/R13——L11/L12 在定制公平作用面上否决。** `mxfast=0`：在 `burst-free-small` 上 −5.6% 换 −31 kB（积压真实存在但仅数十 kB 级）。`tcache_unsorted_limit=3`：连 `unsorted-drain` 这个按其生效路径定制的负载都无效果。Batch 2 的 UNTESTED-EFFECT 已解决，补测义务履行完毕。
- **L6 晋升为优先试点杠杆——全项目最大单点内存数字。** 释放 50% 后一次 `malloc_trim(0)` 从 112 MB 进程回收 **59.9 MB**（armv7l）；不 trim 与钉阈值对照组回收精确为 0——同时确立真机滞留现象与 **L3 与回收的机制正交性**。未测代价已标记：trim 后再激活的 refault 延迟——TV 试点强制测量项。
- **首发包组合验证通过**：L1+L3 在 thread-churn 上 +0.1%/−2.43 MB，无相互作用惩罚。
- **新增 M6**：回收类杠杆采用 Batch 2.5 Part D 三格形态。

## 0b. v2.1 → v2.2 变更记录（Batch 1/2 真机结论）

- **L2 从 Tier 1 降级到 Tier 2，改为包络门控。** Batch 2（armv7l，4 线程持续分配）实测吞吐 −45~−53%、p99 ×20+（1.2 μs → 27 μs）；**新发现**：线程 churn 工况下 Rss **反转为 +8~+26 MB** 滞留碎片（跨代生命周期在仅存 2 个 arena 中交错），三重复方向一致且持续到 idle 相位。Batch 1 空闲守护进程的小赢（−28~−36 kB、零代价）在其低争用包络内仍成立。[证据：`docs/board_ab_batch2_report.md`；裁决：`docs/ab_batch2_adjudication_zh.md`]
- **新增 R11**：`tcache_count=0` 依真机证据否决——四档吞吐 −5.7~−10.1%（在其目标档触及 10% 硬上限），内存回报全档 ≈0。
- **L1 证据升级**：churn 档 −1.0 MB、代价 0.0%，真机确认；Tier 1 地位强化。
- **L3 定量化**：相位切换/small/mixed/churn 形态代价 ≈0%，连续大块 churn（其目标作用面）−4.9%；收益 −0.9~−1.6 MB。Tier 2 最强幸存者。
- **L11/L12 标记 UNTESTED-EFFECT**：live 池复用负载下零代价零效果——其作用面（不复用的突发释放）未被生成；降优先级待负载证据，非否决。
- **T2 升级为源码+设备双重验证**（Batch 1 阴性对照：ServiceV，AT_SECURE=1，env 在场、效果精确为零）。
- **定义首发包：L1 + L3**；含 `arena_max` 的任何组合撤回（继承 L2 争用悬崖：−38~−48%、churn +32 MB）。
- **M3 修订**：微基准敏感度曲线（`bench/alloc_bench`）为预筛门；真实服务 benchmark 仍为上线门。

## 0a. v2 → v2.1 变更记录（Q6 抽查结论）

- **Q6 关闭 — 单一评审者的 dlconf 结论被 REFUTED，附精化**：映射部分成立（配置/缓存映射确为瞬态、在声明的两处卸载点被 munmap），但 Tizen 的 dlconf 重构引入了两个缺陷：(a) **孤儿堆分配** — `dlconf_unload_cache()` free 每个 `struct caches` 节点时不释放其中的 `glibc_hwcaps_priorities` 数组；upstream 是故意把该数组留在静态全局中做有界复用（`_dl_unload_cache` 只清 `length`，upstream `dl-cache.c:508-519`），Tizen 的 per-cache 变体则彻底丢失指针，且随 dlopen 重复累积；(b) **未初始化字段** — `dlconf_find_cache` malloc 的 `struct caches` 未初始化四个 hwcaps 字段：垃圾 `allocated` 会跳过分配分支（`if (length > allocated)`，upstream `:93`），随后合并循环**经垃圾指针写入**（upstream `:115-135`）— 内存破坏级别，非泄漏级别。[发现者：codex-gpt5 抽查；upstream 生命周期精化：仲裁]
- **目标平台上的实际影响**：两个缺陷均以"被查询的 cache 含非空 `glibc-hwcaps` extension 段"为触发门；glibc 2.40 仅为 x86-64/POWER/s390 定义 hwcaps 子目录 — arm/aarch64 没有 — ARM TV 镜像处于休眠态。**R9 的实操结论因此存活**（见修订后 R9）；缺陷立项为正确性工作项（§9），不是优化杠杆。

## 0. v1 → v2 变更记录（仲裁结论）

- **G2 修正（部分 REFUTED）**：`MALLOC_PERTURB_` 在正常 libc 中是活的（`malloc/arena.c:301` `TUNABLE_GET(perturb,...)`、`malloc/malloc.c:5468` `do_set_perturb_byte`、env 别名见 `elf/dl-tunables.list:39-43`）；只有 `MALLOC_CHECK_`/`glibc.malloc.check` 是 stub。卫生清单已扩容。[发现者：codex-gpt5 + claude-opus；kimi 相反的 negative_fact 被源码推翻]
- **L4/L5 核算修正**：`tcache_init()` 无条件分配每线程 `tcache_perthread_struct`，不检查 `mp_.tcache_count`（`malloc/malloc.c:3241-3268`）。`tcache_count=0` 只省 cached chunks；armv7l 上 384 B 元数据只能靠 `USE_TCACHE=0` 重编移除。[发现者：codex-gpt5 + kimi，交叉印证]
- **L2 措辞修正**：`arena_max` 默认为 0；"32 位 2×核数 / 64 位 8×核数"是 `narenas > arena_test` 后按实际核数算出的**有效上限**（`malloc/arena.c:828-842`）。补充 armv7l heap 机制：每个二级 arena 预留 1 MiB VA（`HEAP_MAX_SIZE = 2×512 KiB`，`malloc/arena.c:28-31`）；回收走 `MADV_DONTNEED`（只降 RSS、VA 保留），除非 `vm.overcommit_memory==2`（`malloc/arena.c:516-525`、`sysdeps/unix/sysv/linux/malloc-sysdep.h:34-54`）。[发现者：kimi（默认机制）+ claude-opus（heap 机制），均经源码确认]
- **T1 信任边界扩写**：dlconf 显式纳入（见 §2）。[发现者：四家一致]
- **引入内存类型标签**：每个杠杆标注 RSS / PSS / VA / FLASH，防止度量协议用 Rss/Pss 指标误判 VA 杠杆。[发现者：claude-opus 挑战 C2]
- **新增杠杆 L11–L18；否决清单扩至 R8–R10**（static TLS surplus、dlconf-for-RSS、guard page — 均经源码仲裁）。
- **M 协议新增协变量**：`vm.overcommit_memory`、THP 模式。[发现者：claude-opus]
- **新增 AT_SECURE Plan B**（§8）。[发现者：claude-opus 挑战 C3]
- **v1 无删除项**：L1–L10 全部保留；除上述修正外均获 ≥3 家 CONFIRMED。

## 1. 目标与硬约束

与 v1 一致：北星 = 进程级 RSS/PSS（`smaps_rollup`）+ 系统 PSI memory stall；次要 = flash。性能硬预算：分配密集路径退化 ≤5%（目标）/ ≤10%（上限），逐 service、逐架构。按进程 opt-in 优先于全局默认；真机测量优先于源码估计。

## 2. 信任边界（修订）

- **T1（修订，四家确认）**：在 `malloc/ nptl/ sysdeps/nptl/ sysdeps/pthread/ elf/dl-tunables* locale/ iconv* csu/` 范围内，相对 `upstream/2.40` 的差异仅为一处代码 hunk — memalign CVE-2026-0861 防护（`malloc/malloc.c:5052`）加一个测试文件。因此本文档所有分配器/线程/tunables 机制断言均忠实于 upstream 2.40。**但**，最大的 Tizen 源码差异在上述路径之外：默认启用的 `dlconf` 加载器子系统（`elf/dlconf.c` +2641 行，钩子遍布 `dl-load.c`/`dl-cache.c`/`dl-open.c`/`rtld.c`；`packaging/glibc.spec:27-28,397-401` 启用）。一位评审者验证 dlconf 稳态 RSS 无害：配置/缓存映射在启动完成时（`elf/rtld.c:2003-2008`）和每次 `dlopen` 后（`elf/dl-open.c:919-921` → `elf/dlconf.c:2555-2584`）均被 munmap；常驻成本为 ld.so BSS 中不足 100 B。**待办**：这些 Tizen 特有锚点仅有单一评审者验证 — 已指派交叉抽查（见 Q6）。armv7l `kernel-features.h` 差异在 `--enable-kernel=2.6.16` 下行为中性。
- **T2（确认）**：`GLIBC_TUNABLES` 功能正常但对 `AT_SECURE` 进程静默忽略（`elf/dl-tunables.c:299-301`）。附注（仲裁副产品）：`AT_SECURE` 进程自动走释放 commit 的 `PROT_NONE` heap 收缩路径（`malloc-sysdep.h:41`）。**2026-07-08 设备验证**：Batch 1 阴性对照（ServiceV，AT_SECURE=1）env 字符串在场而 Rss/Pss/arena 效果精确为零（`docs/board_ab_batch1_report.md` §E3）。

## 3. 前置门（P0）

- G1. 逐 service 的 `AT_SECURE` 盘点。不变；现与 §8 Plan B 配对。
- G2（**重写**）。所有 service 启动器的环境卫生审计，分两类：
  - **在正常 libc 中生效（误设即静默灾难）**：`MALLOC_PERTURB_` / `glibc.malloc.perturb`（每次 alloc/free 都 memset，`malloc/malloc.c:1982-1994`）、`LD_PRELOAD`（含 `libc_malloc_debug.so.0`）、`LD_AUDIT`、`LD_PROFILE`（profiling 缓冲，`elf/dl-profile.c:180-235`）、`LD_DEBUG*`、`GCONV_PATH`（禁用 gconv cache、强制私有解析配置，`iconv/gconv_cache.c:54-58`、`iconv/gconv_conf.c:475-498`）、意外的 `GLIBC_TUNABLES`。
  - **无调试 preload 则无效（仍应审计）**：`MALLOC_CHECK_` / `glibc.malloc.check`（`do_set_mallopt_check` 为空操作 stub，`malloc/malloc.c:5464-5468`）。

## 4. 杠杆（分层；每个杠杆带内存类型标签）

### Tier 1 — 低风险，仅 env，第一批 A/B

| ID | 杠杆 | 类型 | 机制（证据） | 预期收益 | 性能风险 |
|---|---|---|---|---|---|
| L1 | `glibc.pthread.stack_cache_size` 40 MiB → 1–4 MiB（或 0） | **RSS** | 默认 41943040（`sysdeps/nptl/dl-tunables.list:26-29`、`nptl/nptl-stack.c:23`）；缓存为进程全局，入队的栈**不会**被 madvise — 脏页保留至超限 munmap（`nptl/nptl-stack.c:56-130`） | 线程 churn 型 service 可达数十 MiB；稳定线程池若从不触顶则 ≈0。**Batch 2 churn 档：−1.0 MB、代价 0.0%（真机确认）** | 通常 <5%；仅当请求路径上建/销线程才有风险 |
| L13 | `glibc.pthread.stack_hugetlb=0` | **RSS** | 默认 1（`sysdeps/nptl/dl-tunables.list:36-41`）；`=0` 对新栈发出 `MADV_NOHUGEPAGE`（`nptl/allocatestack.c:372-375`） | 内核 THP 为 `always` 时每线程最多 ~(2 MiB − 已触碰)；否则恰好为 0 — 以 Q3 为门（rpi4 开发板无 THP → 该板上空操作；TV 内核待查） | 可忽略；glibc 从不主动为栈请求 THP，此项只减不增 |

### Tier 2 — 中风险，仅 env，benchmark 强制

| ID | 杠杆 | 类型 | 机制（证据） | 预期收益 | 性能风险 |
|---|---|---|---|---|---|
| L2 | `glibc.malloc.arena_max=N` — **超订比门控**（v2.3 定量化） | **RSS**（依包络而定） | 机制不变（`malloc/arena.c:828-842`；二级 arena 1 MiB VA；收缩 `MADV_DONTNEED` 除非 `overcommit==2`）。**定量 knee（Batch 2.5 扫描，armv7l）**：代价随线程:arena 超订比——1:1 免费（+1.0%/−1.6 MB，2 线程对照交叉印证），4:3 −22%，4:2 −46%。低分配率 service：激进 cap 便宜（large-transient arena_max=2 → −10.8 MB 仅 −1.7%）。churn：任意 cap 下 Rss +11~+21 MB，n=5 | −1.6~−10.8 MB，取决于分配率与 cap 深度 | **可执行门（v2.4）**：`arena_max = 核数` 构造性安全（运行中分配线程 ≤ 核数 ⇒ 比例 ≤1:1；2:2/4:4 双对照实证）；churn 分类器 = `/proc/<pid>/task` 换手率采样，持续换手 ⇒ 禁用；更深 cap 为按 SoC 许可、需重测（4 核中间曲线不可移植）；延迟敏感排除 |
| L3 | 钉死 `mmap_threshold=131072` + `trim_threshold=131072` | **RSS** | setter 强制 `no_dyn_threshold=1`（`malloc/malloc.c:5422-5449`）；上浮门控在 `:3375-3388`；上浮天花板 32 位 512 KiB、64 位 32 MiB（`:945-958`） | 数百 KiB–MiB；armv7l 绝对空间较小（512 KiB 天花板），aarch64 更大 | 反复大块 alloc/free 的 mmap/munmap 与缺页代价；须 benchmark |
| L4 | `glibc.malloc.tcache_count=3`（**`=0` 已否决 → R11**） | **RSS** | setter `malloc/malloc.c:5508-5517`。**核算修正**：收益 = 仅 cached chunks；每线程结构无条件分配（`:3241-3268`），移除需 `USE_TCACHE=0` 重编 — 不在范围 | **Batch 2：≤0.6 MB、代价 −1.7~−2.3%** — 小众 | 预算内但回报弱；仅当 `malloc_info()` 证明 tcache 驻留量大时按例使用 |
| L5 | 做完尺寸直方图后降低 `glibc.malloc.tcache_max` | **RSS** | setter `:5494-5505`。注意：**不会**冲掉已缓存的超限 chunk；收益随线程/chunk 周转逐步兑现 | 每忙碌线程 KiB–数百 KiB | 热点尺寸恰在新上限之上则超预算 |

### Tier 3 — 应用/service 代码改动

| ID | 杠杆 | 类型 | 机制（证据） | 预期收益 | 性能风险 |
|---|---|---|---|---|---|
| L6 | 相位切换点主动 `malloc_trim(0)` — **优先试点杠杆（v2.3）** | **RSS** | consolidate 后内部整页 `MADV_DONTNEED`（`malloc/malloc.c:5151-5195`）+ `systrim`（`:5200-5202`）；全 arena 持锁遍历（`:5209-5228`）。**真机定量（Batch 2.5 Part D，armv7l）**：释放 50% 后一次调用从 112 MB 进程回收 **59.9 MB**；不 trim 与钉阈值对照回收精确为 0——内部释放不经它永不归还，且 L3 与回收机制正交 | 全项目实测最大杠杆；TV 对应物精确存在（场景切换/退后台 = 释放后静置相位） | 静默点低；热路径/定时器禁止。**未测（TV 试点强制项）：trim 后再激活 refault 延迟；trim 期间全 arena 锁对并发分配线程的停顿（Part D 为线程静止态）** |
| L14 | 降低默认线程栈（`pthread_setattr_default_np` / systemd `LimitSTACK=`） | **VA**（armv7l 为主）+ 少量 RSS | 默认栈尺寸继承自 `RLIMIT_STACK`（`sysdeps/nptl/pthread_early_init.h:30-54`）；栈按需分页 — RSS 只算已触碰页，MiB 级数字是 VA 预留而非常驻 | 若继承默认较大（如 8 MiB）而 512 KiB 够用，每线程省 MiB 级 VA | 深度验证过则无；需栈用量画像。与 L1 交互（缓存的栈保持原尺寸） |
| L15 | 对空闲/控制流用 `setvbuf` 校正 stdio 缓冲 | **RSS** | `BUFSIZ`=8192（`libio/stdio.h:100`），每个活跃缓冲 `FILE*` malloc 一份（`libio/filedoalloc.c:74-105`）；宽字符流额外 ~4×（`libio/wfiledoalloc.c`） | 每流 ~8 KiB（窄），宽流更多 | 取决于 I/O 吞吐；仅限空闲/控制流 |

### Tier 4 — flash / 打包 / 镜像构成

| ID | 杠杆 | 类型 | 证据 | 备注 |
|---|---|---|---|---|
| L7 | gconv 模块白名单 | **FLASH** | `iconvdata/Makefile:26-65,252-259`、`packaging/glibc.spec:813-823` | MiB 级；需产品编码清单（Q5） |
| L16 | gconv 裁剪后必须再生成 `gconv-modules.cache`；严禁下发 `GCONV_PATH` | **RSS+正确性** | cache 命中即早返（`iconv/gconv_conf.c:467-472`）；cache 为 `MAP_SHARED, PROT_READ` = 低 PSS（`iconv/gconv_cache.c:80`）；cache 失效/缺失将强制私有解析配置 | L7 的运维配套 [发现者：codex-gpt5] |
| L8 | NSS 打包拆分 — **范围修正** | **FLASH**（拆分）+ **RSS**（配置） | `libnss_files`/`libnss_dns` 是兼容 stub — `files`/`dns` 已内建、无 dlopen（`nss/nss_module.c:172-175`）；删 stub 省 ~0。真正的运行时成本：passwd/group 链上的 `compat`/`optfiles`/`securitymanager` 被 dlopen 且终身保留（`nss/nss_module.c:183,277`）— 每个用 `getpw*`/`getgr*` 的 service 数十 KB 私有 RSS | flash：把 `db`/`hesiod` 移出基础包。RSS：见 L17 |
| L17 | 产品政策允许处，将 `passwd`/`shadow` 改为内建 `files` | **RSS** | 避免每进程常驻 dlopen 共享 NSS 模块（`nss/nss_module.c:277`）；`group` 必须保留 `securitymanager` | 政策风险高；须先盘点 Tizen `optfiles`/`compat` 语义 [发现者：claude-opus] |
| L9 | 生产 `*.so*` 的 `.symtab`/`.strtab` strip 政策 | **FLASH** | `packaging/glibc.spec:529-538` | 需工具链 owner 签核；RSS ≈0 |
| L10 | 镜像包集合审计 — **扩容**：新增 `glibc-devel-utils`（`libmemusage.so`、`libpcprofile.so`、libthread_db 文件，`packaging/glibc.spec:911-918`） | **FLASH** | `packaging/glibc.spec:752-771,858-918` | [扩充：codex-gpt5] |
| L18 | 冷 DSO `-Os`（仅 gconv/NSS 模块，libc/ld.so/pthread 保持 `-O2`） | **FLASH** | 当前 spec 全局强制 `-O2`（`packaging/glibc.spec:329-356`） | 已否决 R6 的折中；观察项，需 spec 内分组件 CFLAGS [发现者：kimi] |
| L19 | 基础 CLI 工具子包化（`localedef`、`iconv`、`gencat`、`getent`…） | **FLASH** | 基础 `%files` 携带（`packaging/glibc.spec` §%files） | ~1 MB；须核实无启动脚本依赖 `getent`/`iconv` [发现者：claude-opus] |

### 推荐首发包（v2.2）

TV 阶段试点的保守默认：**L1 + L3**——**组合已验证**（Batch 2.5 Part C：thread-churn 上 +0.1%/−2.43 MB，无相互作用惩罚）。`arena_max=核数` 可在通过 L2 超订门后按 service 加入。L12 移出候补（R13）。

## 5. 已否决杠杆（扩充；无新证据不得重提）

R1–R7 与 v1 一致（四家全 CONFIRMED）。新增：

- **R8. static TLS surplus tunables（`glibc.rtld.optional_static_tls`、`glibc.rtld.nns`）作为 RSS 杠杆 — 否决。** 三家评审者的提案经源码仲裁推翻：`_dl_allocate_tls_init` 只 memset 各已加载模块的 TLS 块（`elf/dl-tls.c:638-641`）；surplus 区在线程创建时不被触碰、demand-zero → **RSS 为 0**。残余价值仅 ~1.6 KB VA/线程 — 相比每 arena 1 MiB 可忽略 — 却引入真实的 `dlopen` "cannot allocate memory in static TLS block" 失败风险。
- **R9（Q6 后修订）。为 RSS 禁用 dlconf — 在目标平台上作为 RSS 杠杆否决。** 映射部分成立：配置/缓存映射为瞬态、启动后与每次 dlopen 后均被 munmap；静态常驻仅 40 B（armv7l）/ 72 B（aarch64）BSS。Q6 抽查在 hwcaps 路径发现条件性稳态堆泄漏与未初始化字段破坏风险（见 §0a/§9），但两者的触发门是 ARM 镜像不会生成的 `glibc-hwcaps` cache extension 条目 — 目标平台休眠；且正确的补救是 §9 的补丁而非禁用 dlconf。dlconf 禁用的剩余价值为数十 KiB flash + 每次 dlopen 的 CPU（设计上每次 dlopen 都重新映射/读取 `/run/dlconf.dat` 与被查询的 cache 文件），且平台政策风险高 — 归平台 owner 决策，在本方案之外。
- **R11（v2.2 新增）。`glibc.malloc.tcache_count=0` — 依设备证据否决。** Batch 2 四档吞吐 −5.7% ~ −10.1%（在其目标档 small-churn 触及 10% 硬上限），而内存收益全档 ≈0 至 +1.6 MB——被逐出的 chunk 只是迁入 bins。付满性能，零内存回报。（`docs/board_ab_batch2_report.md`；裁决 `docs/ab_batch2_adjudication_zh.md`）
- **R12（v2.3 新增）。`glibc.malloc.mxfast=0` — 依公平作用面证据否决。** 在专为其积压场景定制的 `burst-free-small` 上：−5.6%（触 5% 目标线）换 −31 kB。积压真实（A6：~50 kB 残留）但仅数十 kB/进程量级。（`docs/board_ab_batch25_report.md` Part B）
- **R13（v2.3 新增）。`glibc.malloc.tcache_unsorted_limit` — 否决。** 连按其生效路径定制的 `unsorted-drain` 都无可测效果（Δtput +0.3%、ΔRss 噪声级）。（`docs/board_ab_batch25_report.md` Part B）
- **R14（v2.4 正式化）。`glibc.malloc.hugetlb` — armv7l 上否决。** `hugetlb>=2` 使 `heap_max_size()` 膨胀为 `hp_pagesize*4` = 32 位下 8 MiB/arena（`malloc/arena.c:53-56`、`malloc/malloc.c:5541-5558`）——反向杠杆；`=1` 由 THP 门控、归 Q3/L13 逻辑。negative_fact：`glibc.pthread.mutex_spin_count` 内存中性（仅性能）——范围外。
- **R10. 移除线程 guard page — 否决。** guard page 为 `PROT_NONE` = 0 RSS（`nptl/allocatestack.c:366`）；收益仅 4 KiB VA/线程，代价是失去溢出检测。仅在证实 VA 枯竭时重议。

## 6. 度量协议（修订）

- M1. 内存：每杠杆每 service 的 `smaps_rollup` Rss+Pss，≥3 轮；系统级 PSI memory `some`/`full`。**指标必须匹配杠杆的类型标签**：VA 杠杆（L14）以 `VmSize`/`maps` 差量度量而非 Rss — 纯 Rss 协议会错误否决它们。
- M2. 归因：前后 `malloc_info()`。
- M3. 性能：逐 service 分配 benchmark，armv7l + aarch64；上线门 ≤5%（目标）/ ≤10%（上限）。
- M4. 上线单元：按 service 的 systemd drop-in；严禁镜像级全局。
- **M5（新增）。每台测量主机记录协变量**：`vm.overcommit_memory`（决定 arena 收缩是经 `PROT_NONE` 重映射释放 commit 还是仅经 `MADV_DONTNEED` 降 RSS，`malloc/arena.c:516-525`）与 THP 模式（`/sys/kernel/mm/transparent_hugepage/enabled`，L13 之门）。协变量不同的主机之间结果不可比。
- M6（v2.3 新增）。回收类杠杆采用 Batch 2.5 Part D 三格形态——{仅释放、释放+trim、阈值对照}——一次实验分离滞留、主动回收与阈值机制。
- 注：系统级设 `vm.overcommit_memory=2` 会放大 L2/L6，但改变全镜像的分配失败语义 — 记录为**本方案范围之外**的系统级决策。

## 7. 开放问题

- Q1. 逐 service 的 `AT_SECURE` 盘点（所有 env 杠杆之门；若大面积 secure 则触发 §8）。
- Q2（部分回答）。板级量级已在档（Batch 1/2 裁决）；TV 级真实服务量级仍开放。
- Q3. 内核 THP 模式（L13 之门；另注意 `glibc.malloc.hugetlb>=2` 在 armv7l 上是反向杠杆：`heap_max_size()` 变为 `hp_pagesize*4` = 8 MiB/arena，`malloc/arena.c:53-56`、`malloc/malloc.c:5541-5558`）。
- Q4. 镜像最终包集合 + 设备 `nsswitch.conf`（L8/L10/L17 之门）。
- Q5. 产品编码白名单（L7/L16 之门）。
- ~~Q6~~ **已关闭** — 抽查报告已交付（`docs/review_dlconf_rss_spotcheck_codex.md`）：映射断言 CONFIRMED，"无任何保留"被 REFUTED（hwcaps 孤儿分配 + 未初始化字段，ARM 上休眠）。R9 已修订；补丁工作项立项于 §9。
- Q7（开发板已回答：0）。TV 镜像值仍开放（M5 协变量）。

## 8. AT_SECURE Plan B（新增）

若 G1 盘点显示目标 service 大面积 `AT_SECURE`，Tier 1–2 的 env 形式全部失效。回退顺序：
1. **service 代码内 `mallopt()`** — API 覆盖 `M_ARENA_MAX`、`M_MMAP_THRESHOLD`、`M_TRIM_THRESHOLD`、`M_MXFAST`、`M_ARENA_TEST`（`malloc/malloc.c:5584-5620`）；在**幸存**杠杆中可救活 **L2 与 L3**（一行代码）。tcache（L4/L5）与 pthread 类（L1/L13）无 mallopt 通道。**L6 本身即代码改动，天然不受 AT_SECURE 影响。**（M_MXFAST 作为 API 存在，但 mxfast 杠杆已否决——R12。）
2. **Tizen spec 默认值补丁** — 构建期修改 `elf/dl-tunables.list` 默认值（或 `mp_` 初始化器）以覆盖其余杠杆。这违反按进程 opt-in 原则、成为需全镜像验证的全局改动；作为最后手段，走独立评审周期。

## 9. 衍生工作项：dlconf hwcaps 生命周期补丁（正确性，非优化）

Tizen `dlconf` 的两个缺陷，触发门均为 `glibc-hwcaps` cache extension 条目（今天在 ARM 上休眠；对任何未来携带此类条目的架构/厂商 cache 为潜伏隐患）：

- **D1 — 孤儿分配**：`dlconf_unload_cache()` free 每个 `struct caches` 节点时不释放其 `glibc_hwcaps_priorities` 数组（`elf/dlconf.c:2567-2573`）；随 dlopen 可重复。修复：在 `free(node)` 前对每个节点调用 per-cache 版 `glibc_hwcaps_priorities_free()`，并保留 `_malloced` 守卫（rtld 最小 malloc 下 free 为空操作 — upstream `dl-cache.c:48-56` 语义）。
- **D2 — 未初始化字段（严重性 > D1：野写，内存破坏级别）**：`dlconf_find_cache` malloc `struct caches` 时未初始化四个 hwcaps 字段（`elf/dlconf.c:2410-2440`、`elf/dlconf.h:51-62`）。修复：改用 `calloc` 分配（物理强制 — 对该结构体现在和将来的未初始化字段问题整类消除），而非逐字段 memset。

验收：复现/回归测试需要一个含非空 `glibc-hwcaps` extension 段的合成 cache 文件（x86-64 上对 `glibc-hwcaps/x86-64-v2` 库跑 ldconfig，或手工构造 cache）；验证 (a) 重复 dlopen 下无分配增长（valgrind/massif 或 `malloc_info()` 差量），(b) ASan + 敌意未初始化分配器下无野访问。补丁走标准多 AI 评审门；此项独立于内存优化 rollout 交付。

## 10. 评审溯源

完整评审见 `docs/review_glibc_memopt_{codex_gpt5,claude-opus-4.8,kimi,Gemini-Code-Assist}.md`。冲突仲裁（perturb、tcache 元数据、arena 默认机制、static TLS surplus、HEAP_MAX_SIZE）对照 upstream `glibc-2.40` 源码完成；真机证据：`docs/board_inventory_run_report.md`、`docs/board_ab_batch1_report.md`（+裁决）、`docs/board_ab_batch2_report.md`（+裁决），工具 `bench/alloc_bench/`（v1.1a）、`docs/board_ab_batch25_report.md`（+裁决）；相关路径的 Tizen 树等价性由两次独立 `git diff` 推导确立（T1）。
