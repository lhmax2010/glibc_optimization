> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# 项目总结报告独立评审 — Kimi

- 评审对象：`docs/glibc_memopt_program_status_report_zh.md` v1.0（2026-08-06）
- 证据基座：设计文档 v2.4、`board_results/batch2/run_summary.tsv`、`docs/board_ab_batch25_report.md` 数据表、`docs/pg0_decisive_probe.md`、侦察 2/3、上游 glibc 2.41/2.42 NEWS
- 核对方法：
  1. 全部量化结论用 `run_summary.tsv` / Batch 2.5 报告表**中位数口径**重算（v2.4 §0d 约定：所有 Δ 为 rep 中位数）；
  2. 源码疑点就地核对（`malloc/malloc.c`、`malloc/arena.c`、`elf/dl-tunables.list`、`elf/dl-tunables.c`）；
  3. 上游动态核对 glibc 2.41/2.42 官方 NEWS 全文；
  4. 同类方案检索限定"不换分配器"约束；替换分配器证据仅用于 Part D。

---

## Part A — 事实与结论核查

### A.1 量化结论逐条核对（重算口径：rep 中位数，KiB）

| 报告结论 | 裁决 | 重算与锚点 |
|---|---|---|
| L6 单次回收 **59.9 MB / 112 MB 进程** | **SUPPORTED** | Batch 2.5 Part D：per-rep（measure−idle）= 60,264 / 61,336 / 61,896 KiB，中位 **61,336 KiB = 59.9 MiB**；基线 measure RSS 中位 114,584 KiB ≈ **112 MiB**。数字精确吻合。 |
| L6 对照组"回收精确为 0" | **SUPPORTED（措辞略满）** | D-C0：idle−measure 中位 = **−40 KiB**；D-T-L3（钉阈值）：**+548 KiB**（idle 反而略高）。"精确为 0"在噪声带内成立，但 +548 KiB 说明措辞宜为"≈0（±0.5 MB 噪声带内）"。 |
| L2 超订比：1:1 免费（+1.0% / −1.6 MB） | **SUPPORTED** | mixed arena4：吞吐 +1.01%、RSS −1,628 KiB（−1.59 MB）；2:2 对照（mixed-t2 arena2）：+0.84%、−1,252 KiB。 |
| 4:3 −22%；4:2 −46% | **SUPPORTED（单档来源）** | mixed：−21.95% / −45.88%；thread-churn：−19.99% / −44.32%。报告取的是 mixed 档；跨档区间实为 −20~−22% / −44~−46%，建议在报告中给区间。 |
| churn 反转 +11~+21 MB | **SUPPORTED（中位口径），但 rep 极差未随文** | thread-churn 三档中位：+21.3 / +17.9 / +11.0 MB；**逐 rep 极差 +4.6~+43.9 MB**（n=5，CV≈15%）。v2.4 已补 median/range 双层表述，总结报告只用了中位层——读者会低估波动。 |
| R11 `tcache_count=0`：−5.7~−10.1%，内存 ≈0 | **SUPPORTED** | Batch 2 中位：small-churn **−10.11%**、mixed −8.20%、large-transient **−5.74%**、thread-churn −7.69%；ΔRSS −16 KiB ~ **+1,604 KiB**（不省反增）。 |
| R12 `mxfast=0`：−5.6% 换 −31 kB | **SUPPORTED** | 重算 −5.68% / −32 KiB（burst-free-small，n=3）。 |
| R13 `tcache_unsorted_limit` 无效果 | **SUPPORTED** | unsorted-drain：+0.11% / +216 KiB（138 MB 进程的 0.15%，噪声级）。 |
| L1：churn 档 −1.0 MB、代价 0.0% | **SUPPORTED** | thread-churn T-L1：+0.03% / **−1,036 KiB**。 |
| L3：≈0%（四档）；连续大块 churn −4.9%；收益 −0.9~1.6 MB | **SUPPORTED（有一处符号笔误）** | 四档：−0.14 / −0.07 / −4.95 / −0.23%；ΔRSS 0 / −1,680 / −944 / −208 KiB。"−0.9~1.6 MB"应为"**−0.9~−1.6 MB**"（缺负号）。 |
| L1+L3 组合 +0.1% / −2.43 MB | **SUPPORTED** | Part C vs Part A C0（中位）：+0.07% / −2,476 KiB（−2.42 MB）。 |
| Top-5 高 glibc 堆进程全部 AT_SECURE=1；10/10 复核一致 | **SUPPORTED** | `pg0_decisive_probe.md` §2：10/10 与侦察 3 冻结 TSV 一致；`elf/dl-tunables.c:299-301` 机制 + Batch 1 阴性对照设备实证。 |
| launchpad pool 无 systemd unit | **SUPPORTED** | PG0 §3.3：PID 255/241 不属于任何 loaded unit，父进程为 init.scope 下的 shell 脚本。注意这与 RPI4 侦察 2 的 `ServiceJ.service` 不同——**两板 launchpad 管理形态不同**，协议 v2 层 2 路径在 TV 上不成立，报告 §4 的更新是对的。 |
| R1 `top_pad`：实际默认 0，元数据 131072 是死值 | **SUPPORTED（源码三重确认）** | `malloc/malloc.c:937` `DEFAULT_TOP_PAD (0)`、`:1917` `.top_pad = DEFAULT_TOP_PAD`；`elf/dl-tunables.list:34-38` 声明 default 131072 仅入注册表（loader `--list-tunables` 实测报 `0x20000`，`e3_tunables.out:26`），不回调；显式设置会触发 `do_set_top_pad` 的 `no_dyn_threshold=1`（`malloc.c:5435-5441`）。 |
| R6 -Os 实证：libnss_optfiles 链接失败 | **SUPPORTED** | 侦察 3 §G3 构建偏差记录（隐藏符号 `__feof_unlocked`；打补丁后可构建）。 |

### A.2 夸大与限定遗漏

1. **§5.1 "这是平台当前正在损失的内存" — OVERSTATED。** 59.9 MB 是合成 50% 释放负载下的回收量；真实进程是否存在同等规模的可回收内部空闲页，报告自己在 §5.2 承认未确立。两句话在同一文档内自相矛盾。建议改为"证明了**存在性上限**：只要真实负载产生可比规模的相位释放，不主动回收这些页就永远不归还"。
2. **§6 "测试板可运行未签名二进制" — 边界 overstated。** 证据链：Batch 1/2/2.5 时代自建 alloc_bench 从 `/root` 跑通过（旧镜像）；recon2 新镜像 `/root` 只读，`/opt/usr/home` 只实测过**板上原生 ELF 的副本**（A3）；自建未签名 ELF 在新镜像该路径的可执行性**未实测**（recon2 F2：GBS 产物无签名，UEP 是否放行未知；协议 v2 A-1 把它列为待做任务）。shim 计划的第一步隐含依赖未闭环。
3. **组合关系误标（v2.4 遗留进报告）**：报告沿用"L2 在 Batch 2 测得 −45~−53%"系 4:2 超订——数字链正确，但 §3.2 Batch 2 行把 L2 表述为"争用悬崖"而未标超订比，读者会把 4:2 的代价当成 arena cap 本身的代价。建议统一加"（4:2 超订）"限定。
4. **L3 收益符号笔误**（见 A.1）。

### A.3 低估（已取得但报告没写出来的价值）

1. **PG0 的 env 继承事实**：pool→child 继承 83/84 变量、仅 `LD_USE_LOAD_BIAS` 被过滤（PG0 §3.2）。虽然 AT_SECURE 杀死了 Top-5 的 env 路线，但这个事实对未来**非 secure 的 launchpad 目标**仍是可用的注入面知识——报告只字未提。
2. **G3 构建指纹方法学**（侦察 3 §2.4）：对 stripped 产品 libc 判定优化等级的复合距离法（TV 距 O2 0.33% / 距 Os 13.45%）——可复用于任何"拿不到构建参数的产品二进制"场景，是一次方法学产出。
3. **产品板既有缺陷的发现权**：PG0 Q3 作废运行暴露了 `.NET TP Worker` 持续 SIG11（5 分钟窗口 150 行新增）。报告把它列在 §7 风险表里，但它的另一面是**本项目先于产品组发现了一个线上崩溃问题**——应作为交付价值登记，而不只是实验噪声。
4. **平台侦察资产**：UEP 绕行（stdin 注入、板内 ELF 落点）、tmpfs 气球压力法、decorate_maps 归因法、身份自检门——§3.1 只登记了 alloc_bench，这套 board-side 工具链同样是可复用资产。

### A.4 否决清单审查（14 项是否有错杀）

逐项复核后**没有错杀**，两项需要加"作用域限定"备注：

| 项 | 复核结论 |
|---|---|
| R12 `mxfast=0` | 结论方向正确，但**实验包络要写明**：fastbin 积压是在 4 线程 rpi4 上测的数十 kB 级；55 线程 .NET 进程的积压上限可能更高。否决理由应表述为"在已测包络内收益 kB 级、代价触 5% 门"，给未来高线程负载留重开条件。 |
| R1 `top_pad` | 源码确认无误（A.1）。补一句：`top_pad` 调大只会增加驻留，**任何方向都不是内存杠杆**，否决是完备的。 |
| R4 `mmap_max` | 默认 65,536 远超实际并发 mmap chunk 数；调小只会把大块逼进 arena 加剧碎片。否决正确。 |
| R8/R10/R14 | 机制核对无误（demand-zero / PROT_NONE / 8 MiB heap 放大）。 |
| R11/R13 | 公平作用面实验设计完备，无误杀疑点。 |

**一个地图完备性缺陷（报告层面，非技术路线错误）**：报告 §2.2/§2.3 两表合起来**漏列了 L4、L5、L13、L14、L15、L16、L17**——这些在 v2.4 里是存活杠杆（L4/L5 niche、L13 因 TV 无 THP 事实退休、L14/L15 Tier 3、L16/L17 Tier 4），既不在存活表也不在否决表，与 §2.1"无遗漏项"的声明直接矛盾。冻结前必须补齐或显式标注"本报告仅列 TV 相关子集"。

---

## Part B — 技术路线完整性

### B.1 旋钮覆盖闭合性

对照 `elf/dl-tunables.list` + `sysdeps/nptl/dl-tunables.list` 全量枚举：**内存相关旋钮已闭合**。逐项映射：check/perturb→G2 卫生项；top_pad→R1；mmap/trim_threshold→L3；mmap_max→R4；arena_max/test→L2/R2；tcache_max/count/unsorted_limit→L5/L4+R11/R13；mxfast→R12；hugetlb→R14；rtld.nns/optional_static_tls→R8；stack_cache_size→L1；stack_hugetlb→L13（TV 退休）；rseq/mutex_spin_count→非内存（negative_fact 登记）；elision/gmon/mem.tagging/decorate_maps/dynamic_sort→性能/剖析/测量用，非内存杠杆。glibc 2.40 范围内无遗漏。**缺口在报告呈现（A.4），不在路线本身。**

### B.2 上游动态（2.41 / 2.42 NEWS 全文核对）

- **glibc 2.41（2025-01）：无 malloc 内存相关改动。** NEWS 新增项为 DNS resolver、sched_setattr、iconv 原地转换、Unicode 16、rseq 扩展 ABI、aarch64 GCS、`glibc.rtld.execstack` 等——与本项目无关。[glibc 2.41 NEWS（bminor 镜像）](https://raw.githubusercontent.com/bminor/glibc/release/2.41/master/NEWS)
- **glibc 2.42（2025-07）：一项必须登记的前瞻风险——tcache 支持大块缓存**，由 `glibc.malloc.tcache_max` 控制（上限放宽到 4,194,304）；小块 tcache 路径同时显著加速。[glibc 2.42 发布公告](https://lists.gnu.org/archive/html/info-gnu/2025-07/msg00011.html)。影响：平台若升 2.42，**被 free 的大块可驻留 tcache 而不再走 munmap**，L3（阈值钉死）与 L5（tcache_max）之间的权衡面整体改变；届时 L5 需要按 2.42 语义重新实验。另：2.42 的 pthread 栈 guard 页改用 `MADV_GUARD_INSTALL` 轻量机制，涉及 L1/R10 的 VA 记账口径。
- 结论：2.40 基线上路线无上游缺口；2.42 的 tcache 语义变化应写入风险登记，作为"平台升级触发重验"的钩子。

### B.3 同类方案（不换分配器约束内）

| 做法 | 锚点 | 对我们路线的关系 |
|---|---|---|
| **PSI 驱动的主动回收（TMO, Meta, ASPLOS'22）** | [TMO 论文](https://www.cs.cmu.edu/~dskarlat/publications/tmo_asplos22.pdf)：内核 PSI + 用户态 Senpai 闭环，冷页卸入 zram，生产部署报告两位数内存节省 | **我们的 PSI 北星与气球法与 TMO 同源**；TV 内核 6.12.60 具备 PSI/zram 全部要素，TMO 是"系统级相邻轨道"的最强先例 |
| **MGLRU**（kernel 6.1+） | TV 内核 6.12.60 支持（协议 v2 §8 已重开）；rpi4 6.12.80 同 | 替代 LRU 的冷页识别，与 L6 的"进程内归还"互补：一个管 page cache/匿名冷页，一个管 allocator 内部空闲页 |
| **生命周期驱动的分级释放（Android `onTrimMemory`/`ComponentCallbacks2`）** | Android API 将后台/不可见/临界分档通知 app 释放 | **L6 的设计同构**：退后台回调 = 释放-静止相位点。业界已把"相位点主动归还"做成平台契约，L6 不孤立 |
| **后台触发 allocator purge（Chrome PartitionAlloc MemoryPurgeManager）** | Chromium 在 renderer 退后台/内存压力时 purge 分配器线程缓存 | 替换分配器阵营也在用**同一相位驱动回收模式**——说明该模式与分配器选型正交，是我们路线的独立佐证 |
| **PSI 用户态策略（Meta oomd / systemd-oomd）** | PSI 作为 kill/调控触发器已工业化 | ServiceR 的 PSI-KILLING 同族；我们的 PSI 测量协议与其兼容 |
| **容器场景 `MALLOC_ARENA_MAX` 收敛（Red Hat KB 实践）** | 容器内 arena 膨胀的标准解法 | 与 L2 超订比门控同机制；我们的贡献是把"何时安全"定量化了（1:1 免费 / 超订付费） |
| **分配画像驱动的参数自适应** | 未找到生产先例；学术侧 autotuning 分配器研究零散 | **诚实的空白**：业界没有成熟的"画像→tunable 自动映射"实践可抄；我们的六档负载模型 + churn 分类器已是该方向的最小可行形态 |

---

## Part C — 三周 Demo 计划可行性

### C.1 `LD_PRELOAD` shim 的技术陷阱（按严重度排序）

1. **【致命逻辑矛盾】shim 的卖点自相矛盾。** §6 称 shim"绕过 AT_SECURE 限制"——但 **`LD_PRELOAD` 本身也被 AT_SECURE 过滤**：secure-exec 模式下 glibc 忽略普通 preload（例外仅为可信目录中带 set-user-ID 标记的库）。Top-5 目标恰是 AT_SECURE=1（PG0），所以：
   - 在 TV 产品板上，shim 对主收益面**根本加载不进去**（连同不能装包一起，双死）；
   - 在测试板上，若目标 AT_SECURE=0，则普通 env drop-in 等效且更便宜，**shim 没有增量价值**；
   - shim 唯一有意义的演示形态是：**在 AT_SECURE=1 的目标上、用可信目录+setuid 标记的 preload 变体**，证明"代码级 `mallopt` 在 env 失效处生效"。报告目前写的版本（普通 preload + AT_SECURE=0 目标）证明不了这个主张。**这是第 1 周动工前必须先纠正的设计错误。**
2. **信号驱动 trim 的异步安全性。** `malloc_trim` **不是 async-signal-safe**：它做全 arena 锁遍历（`malloc/malloc.c:5209-5228`），信号处理器内直接调用会在"被打断线程持有 arena 锁"时死锁。必须采用 **self-pipe / signalfd + 专用 trim 线程**（handler 只写字节，线程在普通上下文调 trim）。另外信号号选择要防撞（.NET runtime、EFL 都有自有信号用途），用 `SIGRTMIN+n` 并在加载时校验未被占用。更干净的做法是**取消信号、改用 Unix socket/事件 fd 命令通道**。
3. **构造函数时机：基本够用，两条边界。**
   - preload 构造函数在 ld.so 完成 libc 初始化后、目标 `main()` 前运行，`mallopt` 生效于后续全部分配——时机足够早；
   - 但 **`M_ARENA_MAX` 只约束未来 arena 创建**，不回收已存在 arena；对在构造函数前已建线程/arena 的进程无效（main 前罕见，可接受，但要在 README 写明）；
   - 多 preload 共存时构造函数按依赖序执行，shim 内部若先分配再 `mallopt` 无妨（阈值是持续状态）。
4. **对已 dlopen 的库：生效。** `mallopt` 写的是进程全局 `mp_`，对之后任何 DSO 的分配统一生效。**但作用面封顶**：.NET/WRT 目标的 GC 堆走 raw mmap，不经 glibc——glibc 可达面就是漏斗测出的 28–45%（PG0/侦察 3 口径）。Demo 数字必须按这个上限解读，不能对总 RSS 宣称。
5. **对 .NET/CoreCLR 的特有风险。** `arena_max=4` 用在 55 线程 .NET 进程上：TP worker 的 marshaling/native buffer 分配是 glibc 路径，若并发分配线程数 >4 即进入超订付费区（−22%/−46% 量级）。**对 .NET 目标 L2 应默认不上**（churn 分类器先判），shim 矩阵里把 .NET 目标限定为 L3+L6-only，除非实测证明其 glibc 并发分配线程 ≤4。

### C.2 三周能否产出可信数字

能，但**最可能超期/产出不可裁决数据的是第 2 周**，三个原因：

1. **场景驱动工具依然缺位**——v1/v2 协议评审连续两轮指出的同一缺口，本计划仍未列出用什么驱动"启动多个应用→切换→退后台"（按键注入？`app_launcher` CLI？EFL 事件？）。没有可复现驱动，n≥20 配对统计无从谈起。
2. **PSI 腿在测试板上大概率不可行**：recon2 B5 实测 8.1 GB 镜像在 ≤256 MB 气球下 PSI 全程无响应；要在 8 GB 板上造出 PSI 需 GB 级气球，压力区间与 TV（1.6 GB）完全不同，**Demo 的"PSI 变化"一项要么降格为"方法演示"，要么明确推迟到 TV**。建议 Demo 北星改为 RSS/PSS + refault，PSI 只做存在性展示。
3. **噪声底未先标定**：第 2 周直接上 A/B，没有先做 C0/C0 空跑噪声带（协议 v2 B-0 的教训）。

建议的计划修正：第 1 周加入"场景驱动工具 + C0/C0 噪声底"两个先行项，宁可压缩目标数量。

### C.3 真实负载脚本设计要点

- **进程集断言**：每轮开跑前快照目标 PID+comm 集合，集合中途变化（app 自杀/LMK）整轮作废；
- **确定性输入**：固定脚本序列 + 固定间隔（`uinput` 按键注入或平台 launcher CLI），禁止人工遥控；
- **冷/热态分离**：冷启动与热切换分开统计，不混在一个分布里；
- **配对交替 A-B-A-B，n≥20，中位数 + 非参检验**，上线判据用 CI 上界（沿用协议 v2 M3）；
- **控制指标**：每轮同测一个与分配器无关的指标（如固定 I/O 延迟），漂移 >5% 整轮作废；
- **协变量**：.25 的 governor 是 `schedutil`（recon2 D1）——实验期要么钉 `performance` 要么逐轮记录频率；rpi4 有 thermal zone，记录温度；
- **归档**：每轮原始 `smaps_rollup`/时间戳/vmstat 落盘 + hash，三家复核可回溯。

### C.4 比 LD_PRELOAD 更快拿到可信数字的路径

**gdb 注入**（测试板可装包）：`gdb -p PID -batch -ex 'call (int)mallopt(...)' -ex 'call (int)malloc_trim(0)'`——
- 不需要 preload、不需要重启、没有构造函数时机问题、没有信号异步安全问题；
- 对已运行的真实进程**当天**就能出"trim 前后 RSS 差 + resume refault"数字；
- gdb call 是 stop-the-world，恰好给 trim 创造了 quiesced 环境（代价测量要注明这一点）；
- `arena_max` 中途设置只影响未来 arena——与 shim 同边界。
取舍：gdb 法适合"先拿数字"，shim（修正为可信目录变体后）适合"演示产品形态"。两者不互斥，gdb 法可把第 2 周的有效时间省出一半。

---

## Part D — 竞争力判断（内部判断，不进入对报告的修改建议）

### D.1 两条路线的固有优劣

**我们（调 ptmalloc + 主动回收）的优势：**
- **零 ABI/链接风险**：替换分配器静态进 glibc 落在符号互置雷区——libc 内部走 `__libc_malloc` 系列隐藏符号，静态链接的 jemalloc 只接管公开 API 时会出现**两个分配器共存**（内部路径仍 ptmalloc），内存被两套元数据分账，RSS 可能更差；glibc 2.39 NEWS 还明确记了替换分配器与动态 TLS 的无限递归坑。
- **回滚粒度**：删 drop-in / 回退一行代码 vs 重新出包换 libc。
- **基线即生产**：性能回归风险被 tunable delta 天然限制在小邻域。
- **证据链已校准**：负载模型、噪声带、判据全部现成。

**我们的劣势：**
- **收益上限**：ptmalloc 无压缩（Robson 界），跨代交错碎片（churn 反转）是机制固有的，trim 只能还"已空闲"的页；
- **作用面封顶**：.NET/WRT 目标 glibc 堆占 Private_Dirty 28–45%，GC 堆任何 glibc 层方案都碰不到；
- **依赖生命周期埋点**：L6 需要每个 app 的相位点接入，规模化慢。
- **对方路线的对应弱点**：jemalloc 默认 `dirty_decay_ms=10000` 即"故意驻留 10 s"，其唯一候选调优项（decay_ms:0）本质是**每次 free→alloc 循环都付 madvise/refault 代价**——与我们 L6 的 refault 问题是同一代价族，但我们在相位点付一次，他们在热路径反复付。

### D.2 紧内存设备上 thread-cache 分配器更高 RSS/碎片的第三方证据

- **机制层（最强）**：jemalloc 手册 `opt.dirty_decay_ms`/`muzzy_decay_ms` 默认 10,000 ms——驻留是设计而非缺陷；TCMalloc 官方设计/调优文档明示"以内存换速度"，per-CPU 缓存驻留，专门提供 `ReleaseMemoryToSystem()` 作为泄压阀。
- **学术实测**：[Mesh (PLDI 2019, arXiv:1902.04738)](https://arxiv.org/abs/1902.04738)：对 Firefox/Redis，非压缩式 SOTA 分配器基线存在 16%/39% 的可压缩冗余——证明 thread-cache 世代分配器普遍携带碎片税（该结论同样适用于 ptmalloc，需诚实呈现）。
- **诚实的反证据（两条，必须放在手上）**：
  1. Redis 反例：Redis 因 glibc malloc 碎片选择捆绑 jemalloc——长驻服务负载下替换分配器**可以**赢；
  2. Android 反例：Android 11 用 Scudo 换 jemalloc 是**安全驱动**而非内存驱动（[LLVM Scudo 文档](https://llvm.org/docs/ScudoHardenedAllocator.html)、[WOOT'24](https://nebelwelt.net/files/24WOOT.pdf)），且低内存 Svelte 配置**保留** jemalloc——"紧内存设备上 jemalloc 必然更费"在业界并无干净共识。
- 结论：能站稳的表述是"thread-cache 分配器的**默认驻留策略**（decay/缓存）在紧内存设备上需要付费调优，而调优代价（decay_ms:0 的反复 refault）与我们 L6 的代价同族"——不要说"jemalloc 在嵌入式必然更费"。

### D.3 9 月前最该补的一项数据

**一个真实形态目标进程在压力下的 L6 端到端数字：同图给出"退后台 trim 回收的 RSS + 回前台首帧 refault 代价 + trim 期锁停顿"。**
理由：59.9 MB 是本项目最大的数，其两项代价是全项目仅剩的未测风险；而对方路线的唯一候选调优项（decay_ms:0）赌的是**同一个权衡**（归还速度 vs refault 代价）。谁先把这个权衡在真实目标上量化，谁就赢得 9 月的比较——这恰好也是我们路线声称的差异化（相位点付费 vs 热路径付费）能被一张图证明或证伪的地方。

---

## Top-3（最该立刻处理）

1. **修正 shim 设计错误**：普通 LD_PRELOAD 在 AT_SECURE=1 目标上同样被过滤——"绕过 AT_SECURE"的主张在当前方案下不成立。要么改为可信目录+setuid 标记的 preload 变体并在 secure 目标上演示，要么把 Demo 定位改为"机制演示"并删掉绕过主张。这决定第 1 周做什么。
2. **把"场景驱动工具 + C0/C0 噪声底"提到第 1 周**：它是第 2 周一切数据的前置，且已连续三轮（v1/v2/本计划）被遗漏；同时用 gdb 注入法先拿 L6 数字，给第 2 周兜底。
3. **重定 Demo 北星**：8 GB 测试板 PSI 在百 MB 级气球下无响应（recon2 B5），PSI 腿在测试板不可行也不可比——Demo 改为 RSS/PSS + refault 为主指标，PSI 仅存在性展示或推迟到 TV。附：报告存活/否决两表补齐 L4/L5/L13–L17 缺位（A.4）。

---

## negative_facts

1. `LD_PRELOAD` 与 `GLIBC_TUNABLES` 一样受 AT_SECURE 过滤（secure-exec 规则，例外仅可信目录 setuid 标记库）——shim 对 Top-5 主收益面在产品板上同样不可达。
2. `malloc_trim` 非 async-signal-safe（全 arena 锁遍历，`malloc/malloc.c:5209-5228`）——信号处理器内直接调用可死锁。
3. 测试板（.25, 8.1 GB）在 ≤256 MB 气球下 PSI 全程无响应（recon2 B5）——该板做不出与 TV 同区间的 PSI 数据。
4. `mallopt(M_ARENA_MAX)` 只约束未来 arena 创建，不缩减既有 arena（机制：`arena.c` reuse/attach 路径）。
5. loader `--list-tunables` 报告的 `top_pad=0x20000` 是注册表死值；分配器实际默认 0（`malloc/malloc.c:937,1917` vs `e3_tunables.out:26`）。
6. .NET/WRT 目标的 GC 堆走 raw mmap，不经 glibc——任何 glibc 层方案（含对方路线静态进 glibc 的公开 API 互置）都只覆盖 28–45% 的 Private_Dirty。
7. glibc 2.41 无 malloc 内存相关改动；2.42 引入大块 tcache（`tcache_max` ≤ 4 MiB）——平台升级时 L3/L5 权衡面改变，需重验。
8. PG0 Q3 已作废：5 分钟保持曲线 + 随机/零页对比因持续 `.NET TP Worker` SIG11（150 行新增）不满足安全门——**TV 上 PSI 保持态至今没有有效测量**，报告 §4 PSI 相关结论均不应引用该轮。

## cannot-verify

1. 自建未签名 ELF 在 .25 新镜像 `/opt/usr/home` 的可执行性（recon2 A3 只测了板内原生副本；F2 证 GBS 产物无签名；协议 v2 A-1 待执行）。
2. TV app 能否装到 .25 unified-dev（不同 profile；不能装包的是 TV，但跨 profile 兼容性无证据）。
3. launchpad pool 对 `GLIBC_TUNABLES` 是否有专项过滤（PG0：零注入观察不能判定；`LD_USE_LOAD_BIAS` 个案消失提示存在选择性过滤）。
4. TMO 论文的分负载精确节省区间（本评审只取到摘要/结论级表述）。
5. 对方路线（jemalloc 静态进 glibc）在 target 上的真实行为——其内部 `__libc_malloc` 路径是否也被接管，需拿到其构建产物实测。
6. .NET runtime 在 TV 目标上的信号占用清单（shim 信号选号的防撞依据）。
7. ServiceR `[PSI-KILLING] startPSIKillAt=250` 的确切语义（沿用 v2 协议评审遗留）。
