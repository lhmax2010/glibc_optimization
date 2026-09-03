> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# 双轨执行协议 v2 定稿前评审 — Kimi

- 评审对象：`docs/tizen_glibc_protocol_v2_zh.md`（v2 草案）
- 证据基座：`docs/tv_recon2_report.md`（RPI4 `.25`）、`docs/tv_recon3_report.md`（TV `.26`）、`docs/tizen_glibc_memopt_design_v2.md` v2.4、`docs/review_tv_protocol_v1_{gpt5,claude-opus-4.8,kimi}.md`
- 核对方法：
  1. **源码核对**（workspace `tizen_base@8f08a7e`）：`elf/dl-tunables.list`、`sysdeps/unix/sysv/linux/setvmaname.c`、`malloc/arena.c`、`malloc/malloc.c`、`elf/tst-decorate-maps.c`；
  2. **原始数据重算**：对 `board_results/tv_recon3_20260806/product_board/final_pull/tv_recon3_product_board/C/smaps_retry/2556_AppProcB.smaps` 按 `parse_smaps.pl` 口径独立重算，并审查全部 1 MiB 对齐段；
  3. **侦察原文交叉**：侦察 2 B5、侦察 3 B4/B5/C 组、E3 tunables 输出；
  4. 不重算板级杠杆数字（v2.4 轮已验）。

## 总体裁决

**v1 三个硬伤：2 个 FIXED（漏斗指标、arena 归因），1 个 PARTIALLY-FIXED（PSI 设计）。**
协议可以冻结的条件：把 **层 2 env 继承假设**、**PSI 持续性证据缺口**、**场景埋点工具缺位** 三项写入 §8 已知未决并给出 step-0 验证动作。见 Top-3。

---

## Part A — v1 三个硬伤的修复裁决

### A1. 漏斗指标（glibc 堆+arena 私有脏页绝对量）— **FIXED，附两条口径边界**

指标本身成立。对 AppProcB 的独立重算（2556 行 smaps）确认：17 个 arena-like 段 PD 合计 7,596 kB + `[heap]` 7,276 kB = 14,872 kB，与侦察 3 表一致。

**关于 ".NET GC 堆 / JIT 区误计"的质询，实测否定**（`2556_AppProcB.smaps`）：
- 17 个命中段全部匿名 `rw-p`、1 MiB 对齐、4–1,024 kB，尺寸谱与 glibc arena heap 的 mprotect 增长形态（`malloc/arena.c:430-448`，新建堆只 mprotect 已用部分）吻合；其中 4 kB/8 kB 段是新建 arena 的 `heap_info` 头，是 glibc 特征而非 GC 特征；
- .NET 侧大段都不满足启发式：GC 候选段如 `0xb0400000`（2,776 kB）因 >1 MiB 被排除；线程栈被内核/runtime 命名为 `[tstack: ...]` 被名称过滤排除；JIT 代码页是 `r-xp` 被权限过滤排除；
- 结论：在已采样目标上，启发式的误差方向是**漏计**（VMA 合并可使相邻 heap 段并成 >1 MiB 段而逃逸，如 `0xb0400000` 无法定性），不是误计。漏计只会让 glibc 可达面被低估，漏斗排序方向保守、可用。

**两条必须写进协议的口径边界：**
1. **"arena 数"实为 arena heap 段数，不是 glibc arena 数。** armv7l/4 核默认 arena 上限为 8（v2.4 §0/L2 机制），而侦察 3 报出 11–17——这只能是 heap 段计数（每 arena 可含多个 ≤1 MiB heap）。不影响漏斗排序，但影响 PG2 判据表述与 B-2 的"arena 数"列含义。decorate_maps 同样是按 heap 标注（`arena.c:448` 每次 `new_heap` 调 `__set_vma_name`），两种方法都数不出 arena 数本身。
2. **PG2 判据仍成立但应按"段数→0"表述**：`arena_max=1` 消灭全部次级 arena heap，无论段/arena 口径，`[anon: glibc: malloc arena]` 段数应归零。建议把判据写成"命名段数从 N → 0"，避免 arena/heap 语义争议。

### A2. PSI 设计（开环固定注入）— **PARTIALLY-FIXED**

**开环决策本身正确**：v1 闭环稳水位确实构造性抵消杠杆收益（气球补上杠杆省下的内存），v2 改开环是对症的。

**但"30% 档已足"的证据是采样窗口未刷新的假象，不是真平台水平**（侦察 3 B5）：
- 侦察 3 的采集是逐档 `dd` 追加后立即读取 PSI；`dd` 写速 329 MB/s（侦察 1 气球节），96 MiB 档间隔仅 ~0.3 s；
- 30% 档与 40% 档的 `some avg2=6.95`、`full avg2=6.32` **逐位相同**，在连续两次间隔不足 1 s 的读取中，2 s 窗口尚未刷新——这只能证明"dd 填充瞬间产生了 reclaim stall"，**不能证明 30% 保持态存在 6.95% 的持续 PSI**；
- tmpfs 气球是 shmem 页，swappiness=100 且 zram 空闲 991 MB（侦察 3 B1）——静态保持期间气球页可被换入 zram，MemAvailable 回升、压力衰减。开环"一次性到位并保持"的"保持"是不成立的，只是衰减速度未测。

**zram 混淆项评估**：30% 档 MemAvailable=695 MB，高于 `ThresholdSwap=300 MB`（侦察 3 B4）2.3 倍，静态气球本身不会触发 swap；但场景分配的叠加、以及气球页自身被换出（方向相反：压力衰减），都是未控变量。zram 压缩率变化本身不是主要混淆（695 MB 水位下 zram 不活跃），**压力衰减才是**。

**修复建议（小改）**：
- 注入后持续记录 `MemAvailable(t)` 与 `/proc/vmstat pswpout`，若保持期 MemAvailable 回升 >5% 或 pswpout 显著非零，判定该轮压力衰减超标、作废；
- B-0 必须先做一次"30% 气球保持 5 min 无场景"空跑，实测 PSI 衰减曲线——若衰减到 ≈0，则 PSI AUC 的有效性依赖于场景自身产生 stall，须在协议中写明这一前提；
- AUC 计算窗口对齐场景起止，而不是整个保持期。

### A3. arena 归因（decorate_maps）— **FIXED，产品分支行为待 PG2 实证（协议已含）**

源码核对全部通过：
- tunable 存在：`elf/dl-tunables.list:146-150`，`glibc.mem.decorate_maps`，INT_32，0–1；
- 命名格式与协议一致：`malloc/arena.c:448` `__set_vma_name (p2, size, " glibc: malloc arena")`，maps 呈现为 `[anon: glibc: malloc arena]`（`elf/tst-decorate-maps.c:80`）；大块 mmap chunk 与非连续主堆标 `[anon: glibc: malloc]`（`malloc/malloc.c:2432,2519`）；线程栈标 `[anon: glibc: pthread stack:]`；
- 关闭时零开销：`setvmaname.c:34-47` 先查 tunable，EINVAL 时原子置位永久跳过；
- 内核要求 5.17+：TV 6.12.60、RPI4 6.12.80 均满足；
- **TV 产品 loader 已注册该 tunable**：`board_results/tv_recon3_20260806/product_board/final_pull/tv_recon3_product_board/e3_tunables.out:28` 列出 `glibc.mem.decorate_maps: 0 (min: 0, max: 1)`。

**一个操作性陷阱**：启发式解析器以"无名 anon 段"为条件（`parse_smaps.pl:24`），decorate_maps=1 后 arena 段有了名字，**同一口径下启发式会数出 0**。A-2 校准必须在**未开装饰**的进程上对比两种方法，或给解析器加"无名或 `[anon: glibc:` 前缀"分支。协议未写明这一点，执行时容易产出"decorate 后 arena 消失"的假告警。

**兜底充分性**：TV release `1.12` 补丁集未知（§8 已列），但 loader 注册 + 同版本上游源码 + RPI4 产品 libc 与 workspace 字节同构（侦察 3 G3：仅 24 字节差异），该特性缺失概率低；缺失时 1 MiB 启发式在已采样目标上误伤方向保守（见 A1）。兜底够用。

---

## Part B — v2 新引入项

### B1. 层 2 组级注入（launchpad pool env 继承）— **主收益面建立在未验证假设上**

推理链拆解：
- "exe 与父不同 ⇒ 确实 exec ⇒ `__tunables_init` 重新解析" —— **成立**。侦察 3 C1/C3 实测子进程 exe 为 `/usr/bin/ServiceH`、`/usr/bin/wrt` 等，与父 `/usr/bin/ServiceJ` 不同；exec 后 glibc 重新初始化，AT_SECURE=0（侦察 3 C0：91/111 非 secure）时 tunables 重新解析。这一半是实的。
- "env 从 pool 继承到 app" —— **未验证**。侦察证据只证明 exec 边界存在，不证明 env 内容。launchpad/appfw 若对 app 环境做白名单过滤或 `clearenv` 后重建，链即断。本协议主收益面（Top-5 全在层 2）悬于这一环。注意 RPI4 侦察 2 C1 还观察到反例形态：`AppUIA.dll` 父链同 exe（fork/load 无新 exec），说明该框架内"exec 边界"并非普适。

**板上最小验证实验（只读，无需重启 pool，可先做）**：
1. 现在就读 `/proc/<pool-pid>/environ` 与任一 launchpad 子进程 `/proc/<app-pid>/environ`，求差集。若子进程 environ 含有只能来自 pool 环境的变量（如 pool unit 特有的 `XDG_*`/`LD_*`），则继承链当下即被证实；若子进程 environ 是重建白名单（仅含少量标准变量），假设即被证伪——**零注入即可判别**。
2. 若差集判别不了，再做注入版：给 pool unit 的 drop-in 加 `MEMOPT_PROBE=1`（非 glibc 变量，无副作用），整机重启，检查存活 app 的 environ 是否含该标记。

**协议必须修改**：§2 层 2 的"env 通过 `ServiceJ` 继承可达"应降级为"待验证假设"，并把上面实验 1 列为 B-0 之前的第一动作。这是全协议最高返工点。

### B2. 双轨移交规则 — **方向正确，"同构锚"措辞过度**

- 三条不可比理由之外，补充两条：(a) **governor 不同**——RPI4 `schedutil`（侦察 2 D1）vs TV `performance` 且唯一可用（侦察 3 B3），同一代码路径的时延分布形态不同；(b) **PSI 窗口语义不同**——TV 内核 PSI 输出 `avg2/avg6/avg10`（侦察 3 B5；旧 5.4 内核亦然，属 vendor patch），RPI4 为标准 `avg10/avg60/avg300`（侦察 2 B5），即使机制可比，AUC 的窗口标度也不同。既然百分比本就不移交，这两条只影响"方法学移交"的细则，应在移交规则中注明。
- **"glibc 内部机制可比"的锚基本成立，但"同构"一词只覆盖 RPI4↔workspace**。TV libc 尺寸 1,453,496 B、Build ID、`release 1.12` 均与另两方不同（侦察 3 §8 三方对照），TV 侧是"同版本同编译器主版本、不同产品分支"，机制可比性是**假设+逐项实证**（PG2/§4 的行为验证），不是既有事实。措辞建议改为"glibc 机制行为是唯一可比锚，逐项以 TV 行为实证为准"。
- **a53/armv8+crc vs a8/armv7 对 glibc 内部的影响：机制层无，速度层有**。依据：glibc 2.40 的 hwcaps 子目录仅 x86-64/POWER/s390 定义，ARM 无 ifunc 选路（v2.4 §0a/Q6 仲裁结论）；32 位 ARM 无 LSE，两 arch 的原子实现同为 LDREX/STREX 系；memcpy 等 string 例程在 ARM 上为编译期选择。故 arena/tunable/锁机制行为同构，差异仅体现在 codegen 速度——已由"百分比不移交"覆盖。锚不过度，但依赖 TV 产品分支未在这些路径打补丁（PG1 剩余项，行为验证兜底）。

### B3. M3 统计判据（配对交替 n≥20、CI 上界落门内）— **层 1 可行，层 2 在现有注入约束下实际不可执行**

- **层 1**：unit restart + 场景脚本，每对 A/B 约 1–3 min，20 对 ≈ 1 h/目标/杠杆，可行。
- **层 2**：§6 禁 restart `ServiceJ`，改格须整机重启。TV 产品板启动 60–120 s + 场景时间，**严格交替 20 对 = 40 次重启 ≈ 1.5–3 h 纯重启开销**，且每次冷启动的 app 集/预载状态有漂移，配对的前提（同分布）被重启本身破坏。这不是统计问题，是工程设计冲突。
- **建议**：层 2 改为"格内连续 n=20 + 格间重启"（2 次重启），以格内顺序位置做配对，外加每格首尾各插一次 C0 探针监测漂移；或退化为交替每 5 对重启一次（8 次重启）。协议应明文二选一，不要让执行者现场发明。
- **B-0 噪声底样本量不自洽**：§4.1 噪声标定 ≥5 轮，而 §5 M3 要求 CI 上界判据——5 轮估不出可用 CI。噪声底实验应与判据同量级（n≥20），层 1 成本可接受。
- **时间成本与稳定性总账**：层 1 三格 × 3–5 目标 ≈ 半天；层 2 两格（C0、bundle）× n=20 + 重启 ≈ 半天–一天；L6 三格另计。协议无时间预算章节，建议补，避免执行期被砍样本量。

---

## Part C — 缺口与风险

### C1. 协议未覆盖、执行必撞的缺口

1. **层 2 整机重启 A/B 的可行性与耗时**（见 B3）：40 次重启对真实产品板还有次生风险——journal 磨损、启动漂移、人工值守成本；且 TV 是**有人使用的形态**，每次重启都是用户可见事件。需要维护窗口纪律，协议未提。
2. **TV 不能装包对 L6 的实际约束**：§4.4 自认"L6 需随产品版本出"——这意味 L6 试点依赖产品构建+签名+发布链，周期以周计，且 §7 把 L6 列为完成判据。**整条 L6 完成判据悬于协议控制范围之外的发布通道**。需要：明确 develkey/develmode 是否可在该板装测试包（侦察 2 F2 已证 GBS 产物无签名、未验证上板），否则 L6 应从 TV 完成判据降级为"随版本试点"，TV 阶段只交付方法与预算。
3. **场景埋点工具仍缺位**：§5 M3 补强写了统计判据，但"有明确时间戳的埋点"是什么、由谁产生（appfw 日志？ecore 回调？`journalctl` 时间戳？）仍未命名。这是 v1 被判不合格的同类缺口在 v2 的残留——统计框架搭好了，测量仪器仍没有。
4. **层 2 组级度量的进程集漂移**：组级指标是 Top-5 Rss/Pss 之和，app 启停/LMK/用户操作都会改变集合构成。协议要求"汇总目标集之和"但未要求**每轮断言进程集不变**（快照 PID+comm 集合，集合变化即作废该轮）。
5. **数据留存与可审计**：重启 40 次的实验若无逐轮原始文件（smaps_rollup/PSI/vmstat/场景时间戳）命名与归档规范，三家复核无法回溯。v1 评审已提过，v2 仍未补。

### C2. 安全评估（30% 气球 vs ServiceR 阈值）

- **静态余量**：30% 档 MemAvailable=695 MB，距 `ThresholdSwap=300 MB` 2.3 倍、距 `ThresholdLow=160 MB` 4.3 倍（侦察 3 B4），静态安全。
- **叠加余量不足**：场景分配叠加在气球之上，若场景峰值分配 >395 MB 即破 `ThresholdSwap`、>535 MB 破 `ThresholdLow`。TV 上 app 冷启动分配峰值可达百 MB 级，余量没有看起来大。护栏"出现 LMK kill 即作废"是事后检测，应在每轮**开始前**断言 `MemAvailable > 气球 + 场景峰值预算`。
- **`startPSIKillAt=250` 语义无法从现有材料确认**：与 `psiTriggerPercent=55`、`psiWindowSize=2000000`（μs）同节，疑似"PSI 达 25.0%（×10 表示）开启 PSI 杀死"，但无代码/文档证据。若语义属实，6.95% 的实测水平距触发很远；若语义是别的（如 250 次事件），结论反转。**必须列入 cannot-verify，并在 B-0 空跑中观测是否出现 PSI-KILLING 相关 journal**。
- **zram 双面性**：swappiness=100 下气球页可能被换出（压力衰减，见 A2）；同时 zram 已用 48 MB 说明系统常态有换出，PSI 基线可能非零——AUC 必须先测无气球基线并扣除。
- **`memory_product.conf` VIP 名单**：LMK/PSI-KILLING 若保护 Top-5 目标而杀非目标进程，则"目标存活但系统其他部分被杀"的污染不会发生，但**北星指标会被 VIP 保护稀释**——被保护进程的 stall 减少恰恰可能是配置所致而非杠杆。需要求记录实验期全部 ServiceR journal 并纳入裁决上下文。

### C3. §8 之外未列的隐含假设

1. **pool env 继承可达**（B1）——最大遗漏，应进 §8 首位。
2. **user 级 systemd drop-in 落点与生效**：§8 列了"路径待探明"，但未列"user manager 是否读取 `/run/systemd/user/` drop-in、是否需 `systemctl --user daemon-reload`、root 注入 user 级 unit 的权限模型"。
3. **PSI 窗口为 vendor patch 格式**（avg2/avg6/avg10）——采集与 AUC 工具按标准格式（avg10/60/300）写就会解析失败或语义错位。
4. **重启后 app 集确定性**：预载 app 集合是否跨启动一致，决定了层 2 组级度量的分母稳定性。
5. **decorate_maps 在 TV libc 的行为存在性**：loader 注册 tunable ≠ libc 内调用点存在（release 1.12 补丁集未知）；PG2 第一步应先跑一次装饰验证再依赖它做归因。
6. **B-0 噪声底的可迁移性**：用 `issue_report_agent`（原生小服务）标定的噪声底外推到 launchpad app 组（.NET/WRT 大进程）是假设，组级噪声应在层 2 单独标定（§4.3 有提，但应在完成判据里显式化）。
7. **侦察快照时效**：侦察 3 的进程拓扑是某次启动后某一时刻的 111 进程快照；TV 交互状态下 Top 集会变。漏斗应规定执行前重扫。

---

## Top-3（最可能导致返工）

1. **层 2 的 env 继承假设未验证 + 换格需整机重启**：若 launchpad 对 app 环境做白名单重建，主收益面（Top-5）整章作废；若继承成立，严格交替 n≥20 需 40 次重启，判据实际不可执行。任一方向都是执行中段返工。**冻结前必须把"只读 environ 差集判别实验"加为 B-0 前置动作。**
2. **PSI 北星的持续压力证据是采样假象 + 气球会被 zram 换出**：侦察 3 的 30%/40% 同值只证明 dd 瞬态，保持态 PSI 未测；tmpfs 气球在 swappiness=100 下会漏进 zram。若 B-0 空跑发现 PSI 衰减到 ≈0，§4.5 的 AUC 设计产出双侧近零的不可裁决数据。
3. **场景埋点仪器缺位（v1 残留）**：M3 统计判据完备，但"贴近分配行为的埋点"无具体产生者；没有仪器，B-1/B-2 的性能门与 L6 的 refault 都停在纸面，与 v1 被判不合格的是同一根因。

---

## negative_facts

1. **侦察 3 的 30%/40% 档 PSI 同值（6.95/6.32）是采样窗口未刷新的假象**（dd 间隔 ~0.3 s < avg2 窗口 2 s），不能作为"30% 保持态 PSI≈7%"的证据。
2. **侦察 3 表中的"arena 数"是 arena heap 段数，不是 glibc arena 数**——11–17 超出 armv7l/4 核的 arena 上限 8，口径必然如此；PG2 判据应按"段数→0"表述。
3. **decorate_maps=1 时现有启发式解析器会数出 0 个 arena**（`parse_smaps.pl:24` 的名称过滤），两法不可在同一进程同一时刻混用而不改解析器。
4. **tmpfs 气球页在 swappiness=100 下可被换入 zram**，开环"一次性到位并保持"的保持态压力随时间衰减，不是固定水位。
5. **RPI4（轨 A）在 8.1 GB 镜像上 256 MB 气球内 PSI 全程无响应**（侦察 2 B5）——轨 A 不能承担任何 PSI 相关工作，PSI 方法学只能在 TV 上就地开发。
6. **"glibc 同构"只适用于 RPI4↔workspace**（24 字节差异，侦察 3 G3）；TV libc 与两者均不同（尺寸/Build ID/release 1.12），TV 侧机制可比性必须逐项行为实证，不是既有事实。
7. **RPI4 侦察 2 C1 存在反例拓扑**：`AppUIA.dll` 父链同 exe（fork/load 无 exec），"launchpad 后代必然 exec"不普适——层 2 注入前必须逐目标验 exec 边界，不能只凭"父为 pool"。

## cannot-verify

1. launchpad/appfw 对 app 子进程环境的传递策略（白名单/clearenv/全继承）——workspace 无 appfw 源码。
2. `[PSI-KILLING] startPSIKillAt=250` 的确切语义与触发条件（侦察 3 B4 仅配置文本，无代码/文档）。
3. ServiceR 运行时实际生效的 Memory 档（§8 已列，确认仍开）。
4. TV release `1.12` 产品分支补丁集（§8 已列；本评审确认 RPM/ELF 均无法恢复 commit）。
5. user 级 `ServiceJ.service` 的 drop-in 落点与 daemon-reload 语义（§8 已列）。
6. TV 板 develkey/develmode 是否允许安装测试包（L6 通道前提；侦察 2 F2 仅证 GBS 产物未签名）。
7. TV 重启后 launchpad 预载 app 集合的确定性。
8. zram 在 TV 压力下的实际压缩率与换出速度（影响气球衰减速率与 L6 refault 归因）。
