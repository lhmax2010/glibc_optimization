> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Tizen glibc 内存优化 — 双轨执行协议 v2（中文版）

- 状态：草案 — 待三家评审后与设计文档 v2.4 一并冻结
- 取代：`tv_phase_protocol_v1.md`（v1 经四家评审判定不合格：漏斗指标错、PSI 自我抵消、malloc_info 不可达；本版逐条重构）
- 事实基座：`docs/tv_recon2_report.md`（RPI4 `.25`）、`docs/tv_recon3_report.md`（TV `.26`）、设计文档 v2.4、板级 Batch 1/2/2.5

## 0. 双轨定义与移交规则

| | 轨 A：RPI4 `.25` | 轨 B：TV `.26` |
|---|---|---|
| 镜像 | Tizen 11 unified-dev，内核 6.12.80 | Tizen 10 TV 产品，内核 6.12.60 |
| glibc | 2.40-3.12，GCC 14.2.0 **-O2** | 2.40-1.12，GCC 14.2.0 **-O2** |
| 平台其余包 | LLVM **-Os** | GCC **-O2** |
| CPU flags | cortex-a8 / armv7-a | **cortex-a53 / armv8-a+crc** |
| 内存 | 8.1 GB，zram 3.2G 未用，overcommit=0 | **1.6 GB**，zram 1G 已用 48M，swappiness=100，overcommit=1 |
| 能力 | 可编包安装、可跑自建二进制、可改 glibc | **只读探测 + env 注入**，不能装包 |
| 角色 | 机制验证、工具、glibc 侧改动 | 真实画像、最终裁决 |
| UEP 可执行落点 | `/opt/usr/home`（`/root` 只读） | **`/root`**（`/tmp`、`/opt/usr/home` 被拒） |

**移交规则（硬约束，违反即数据作废）**
- **可移交 A→B**：glibc 内部机制成立性、测量方法学、脚本与工具、代价的数量级与方向。
- **不可移交**：任何百分比、任何绝对 MB、任何"某 service 用哪个杠杆"的结论。理由有三且互相独立：平台包构建口味不同（LLVM -Os vs GCC -O2）、CPU 调优不同（a8/armv7 vs a53/armv8+crc）、内存与回收环境不同（8.1G/overcommit=0 vs 1.6G/overcommit=1/zram 在用）。
- **glibc 同构是唯一的可比锚**：三方 glibc 均 GCC 14.2.0 -O2，RPI4 产品 libc 与 workspace O2 产物仅差 24 字节（Build ID + debuglink CRC）。分配器内部行为可比，调用方行为不可比。

**板子身份自检（所有脚本强制）**：首条采集前读 `uname -r` + `/etc/os-release`，断言目标板身份，不符即退出。历史教训：两板轮换曾致数据采错板。

## 1. 前置门

- **PG1（部分关闭）**：构建口味风险已解除（组 G 直接证据：TV RPM `%{OPTFLAGS}` 含 `-O2`，指纹距 O2 0.33%、距 Os 13.45%）。**剩余项**：TV release `1.12` 的产品分支/补丁集仍未知（RPM 元数据未暴露 commit）。处置：不阻塞执行，改为**行为验证替代源码验证**——由 PG2 与 §4 的机制实证承担；若某杠杆在 TV 上行为与机制预期不符，再回头追补丁集。
- **PG2（TV 侧 tunables 生效实证，方法已重写）**：v1 用 `malloc_info()` 不可行（进程内 API）。改用二级方法：
  - 首选 **`glibc.mem.decorate_maps=1`**——TV 内核 6.12.60 ≥ 5.17，支持 `PR_SET_VMA_ANON_NAME`，arena VMA 会被标注 `" glibc: malloc arena"`，`/proc/pid/maps` 可**精确识别** arena（取代启发式）。
  - 兜底 **1 MiB 对齐 anon 段计数**（侦察 3 已用，口径与 `parse_smaps.pl` 一致）。
  - 判据：对某目标注入 `arena_max=1` 重启后，arena 数应降至最小；这同时证明 tunables 在 TV 产品镜像上生效。
- **PG3（注入面确认）**：见 §2 分层，逐目标确认 AT_SECURE（侦察 3：20 secure / 91 非 secure）与注入通道。

## 2. 目标漏斗（推翻 v1，按实测重排）

**v1 的假设被证伪**：Top 进程虽是 .NET/WRT 系，但 glibc 堆占私有脏页 **28~45%**，是可观的作用面；反而原生小 service 占比更低（15% 级）。故排序指标定为 **glibc 堆+arena 私有脏页绝对量**（不是占比，也不是总 RSS）。

侦察 3 实测排序（TV `.26`）：

| 目标 | glibc 堆+arena | 占比 | arena 数 | 注入通道 |
|---|---:|---:|---:|---|
| `AppProcB` | 14,872 kB | 44.5% | 17 | launchpad pool（组级） |
| `AppProcD` | 10,080 kB | 28.4% | 13 | launchpad pool（组级） |
| `ServiceE` | 7,912 kB | 40.6% | 11 | launchpad pool（组级） |
| `AppProcA` | 4,960 kB | 37.3% | 12 | launchpad pool（组级） |
| `ServiceH` | 3,412 kB | 31.2% | 11 | launchpad pool（组级） |
| `enlightenment` | 2,936 kB | 20.4% | 6 | init.scope，无 unit |
| `ServiceD` | 1,948 kB | 25.5% | 5 | launchpad pool（组级） |
| `ServiceC` | 1,072 kB | 15.7% | 5 | **`ServiceG.service`** |
| `ServiceF` | 996 kB | 14.9% | 4 | **`issue_report_agent.service`** |
| `ServiceV` | 928 kB | 33.0% | 6 | `ac.service` |

**注入分层（v1 缺失，本版新增）**
- **层 1｜独立 systemd unit**：`ServiceG`、`issue_report_agent`、`ac`、`pulseaudio`、`ServiceR`。可逐 service drop-in，收益小但可控——**用作方法学验证与噪声标定**。
- **层 2｜launchpad pool 组级**：Top-5 全在此。侦察 3 证实这些进程 **exe 与父不同（确实 exec）**，故 tunables 会重新解析，**env 通过 `ServiceJ` 继承可达**。代价：无法逐 app 区分，只能整组 A/B。**这是本协议的主收益面。**
- **层 3｜无 unit 且非 launchpad**（如 `enlightenment` 父为 PID 1 却在 init.scope）：注入路径待探，暂不列入首批。

## 3. 轨 A（RPI4）任务：机制与工具

轨 A 只产出方法与机制，不产出上线数字。

- **A-1 仪器回归**：alloc_bench 推至 `/opt/usr/home` 执行（UEP 落点已实测），确认确定性性能仪器可用。
- **A-2 decorate_maps 验证**：在 RPI4（内核 6.12.80）验证 `glibc.mem.decorate_maps=1` 确实标注 arena VMA，并校准"1 MiB 对齐启发式"与精确标注的偏差——**校准结果随方法一起移交轨 B**。
- **A-3 L6 代价测量法开发**：v2.4 强制的两项未测代价在此开发方法：
  - refault：`/proc/pid/stat` 的 **minflt** 增量为主；**但 TV 有 zram 且 swappiness=100，major fault/swap-in 不能排除**，故同时采 `pgmajfault` 与 `/proc/vmstat` 的 zram 相关项。
  - trim 期锁停顿：哨兵线程法（进程内高频 `malloc(32)/free`，测 `malloc_trim` 期间循环耗时尖峰）。alloc_bench 加一个 `--trim-during-load` 模式实现。
- **A-4 glibc 侧改动验证通道**：GBS 出包已验证（9:46 出 15 RPM）。§9 dlconf 补丁与未来任何 libc 改动在此验证正确性与不回归。
- **A-5 负面事实登记**：纯 `-Os` 构建在 Tizen 树上 `libnss_optfiles.so` 链接失败（隐藏符号 `__feof_unlocked`）——R6 的实证补强，进 v2.5。

## 4. 轨 B（TV）任务：真实裁决

### 4.1 Batch B-0：方法学与噪声标定（先行，不产出裁决）
- 层 1 取一个低风险 unit（`issue_report_agent`，Restart=always、watchdog=0、StartLimitBurst=5）做 **C0 vs C0 空跑**（≥5 轮），确立 Rss/Pss 与场景指标的噪声带。**板级教训：`pass` 进程 92 kB 噪声带吞掉一切效应。**
- 每轮 restart 前 `systemctl reset-failed`（StartLimitBurst=5，重复实验必触发）。
- drop-in 落点：`/etc` 实测可写，但**默认用 `/run/systemd/system/<unit>.d/`**（重启即消失，实验更安全）；需持久时才落 `/etc`。

### 4.2 Batch B-1：层 1 逐 service（L1+L3 首发包）
| 格 | GLIBC_TUNABLES |
|---|---|
| C0 | 基线 |
| L1+L3 | `glibc.pthread.stack_cache_size=1048576:glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072` |
| +L2 | 追加 `glibc.malloc.arena_max=4`（核数=4；仅对通过 churn 分类器的目标） |

churn 分类器（v2.4 要求，v1 曾误降级为 task 计数）：**1 Hz 采 `/proc/pid/task` 的 TID 集合，持续 ≥60 s，换手率 = |新增 ∪ 消失| / 时长**；>0 持续即 churn 类 → L2 禁用。

### 4.3 Batch B-2：层 2 launchpad 组级（主收益面）
- 注入点：`ServiceJ` 的 unit drop-in（user 级，具体路径首步探明）。
- 影响面：全部 app 子进程，整组度量——汇总 Top-5 目标的 Rss/Pss 之和 + 各自 arena 数。
- **必须先在 B-0 标定组级噪声**（app 启停会造成天然波动）。
- 格同 B-1；`arena_max=4` 对 arena 数 11~17 的目标是显著收紧，属重点观察项。

### 4.4 L6 试点
- 落点：TV app 生命周期 `pause`/退后台回调（与板级 Part D 形态精确对应）；次选 ServiceR 内存事件驱动。
- 形态：产品代码改动，走正常构建签名链（不受 UEP 影响；**注意 TV 不能装包,故 L6 需随产品版本出**）。
- 三格（M6）：{退后台不 trim / 退后台+trim / L3 钉阈值对照}。
- 强制代价：refault（minflt 为主 + zram/major fault 兼采）、trim 期锁停顿（轨 A 开发的哨兵法）。

### 4.5 PSI 北星实测（v1 自我抵消设计已废）
- **开环固定注入**，不做闭环稳水位（v1 的闭环设计会让气球精确补上杠杆省下的内存，A/B 构造性为零）。
- 注入曲线：气球按 MemAvailable 的 **30%** 一次性到位并保持（侦察 3 实测该档 `some avg2=6.95`、无 LMK；40% 档同值，30% 已足）。
- 采集：1 Hz `/proc/pressure/memory` + `/proc/vmstat`（`pgmajfault`、`workingset_refault`、zram 项），`systemd-run`/`setsid` 脱离 SSH 会话。
- A/B：同一注入曲线 + 同一场景脚本，有无杠杆包两组，比 **PSI some/full avg2 的 AUC** 与 refault 计数。
- **护栏**：任一轮出现 LMK kill（对照 `ServiceR` 阈值 `ThresholdLow=160MB`、`[PSI-KILLING] startPSIKillAt=250`）即作废该轮并记录，不纳入统计。

## 5. 度量与判据

- M1 内存：`smaps_rollup` Rss+Pss+Private_Dirty（TV 实测可用），≥3 轮取中位；组级实验汇总目标集之和。
- M2 归因：**arena 数（decorate_maps 精确法，兜底 1 MiB 启发式）+ 堆/arena 私有脏页**，取代不可达的 `malloc_info()`。
- M3 性能双门：轨 A 微基准曲线为预筛门；轨 B **真实场景指标**为上线门（≤5% 目标 / ≤10% 上限）。
- **M3 补强（v1 评审要求）**：场景指标须为**贴近分配行为的埋点**（app 启动耗时、场景切换耗时等有明确时间戳者），不用宏观模糊指标；采用**配对交替 A-B-A-B、n≥20、中位数 + 非参检验**，且**上线判据是效应的置信区间上界落在门内**，噪声底由 B-0 的 C0/C0 空跑确定。
- M5 协变量（每次记录）：板身份、glibc release、平台构建口味、CPU flags、overcommit、zram 使用量与 swappiness、governor、MemAvailable、场景。
- M6 回收类三格形态（同 4.4）。

## 6. 安全与恢复

- restart 前置：目标 unit 先单独 restart 一次演练；`Restart=always` 且 StartLimitBurst=5 的单元每轮 `reset-failed`。
- **restart 禁列**：`ServiceJ`（重启会牵动全部 app）、`display-manager`、任何 watchdog≠0 的 unit（侦察 3 实测均为 0，但每次执行前复核）。层 2 实验若需生效,优先整机重启而非 restart pool。
- 气球护栏：≤MemAvailable 40%，出现 LMK 即停;每轮结束 `rm` 并验证。
- 恢复：删除全部 drop-in（`/run` 者重启自动消失）、复扫 inventory 确认 LIVE 命中为 0、确认气球与临时文件清空。

## 7. 完成判据

- PG2 通过（tunables 在 TV 生效有实证）；
- B-0 给出各层噪声底；
- B-1/B-2 每目标有 Rss/Pss/arena + 场景性能 + PSI AUC；
- L6 至少一个试点有回收量 + refault + 锁停顿三项；
- 每杠杆×目标过 M3 双门方可标记"可上线"；
- 产出轨 B 裁决 → 决定量产 rollout 范围（rollout 决策本身在本协议范围外）。

## 8. 已知未决

- TV release `1.12` 产品分支/补丁集未知（PG1 剩余项，以行为验证替代）。
- 层 2 注入的具体 drop-in 路径（user 级 launchpad pool）待首步探明。
- 层 3（`enlightenment` 类无 unit 非 launchpad）注入路径未定。
- TV 侧 `ServiceR` 运行时实际生效的 Memory 档未确认（配置有多档，journal 未打印）。
- MGLRU：TV 内核 6.12.60 已支持（v1 时代因 5.4 判死，现重开）——列入相邻轨道，本协议不执行。
