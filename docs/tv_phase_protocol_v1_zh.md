> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc 内存优化 — TV 阶段协议 v1（中文版）

- 状态：草案 — 待评审后与设计文档 v2.4 一并冻结
- 上游：设计文档 v2.4（冻结候选）、TV 板侦察 `docs/tv_board_recon_report.md`、三家评审 Part C 收敛建议
- 目标平台：真实 TV 镜像，<PRODUCT_IMAGE> TV，armv7l，kernel 5.4.261，**GCC -Os 构建**，glibc 2.40
- 定位：板级（rpi4）阶段回答"什么可能有效"；本协议回答"在真机上怎么证明并安全推上去"

## 0. 环境基线（侦察落定，作为全协议协变量）

| 维度 | TV 板 | rpi4（板级阶段） | 对协议的影响 |
|---|---|---|---|
| glibc | 2.40（同版本） | 2.40 | 源码结论主携带性成立；TV 分支补丁 delta 待 §1 重推导 |
| 构建 | **-Os** | -O2 | 性能绝对值不可跨镜像比；A/B 同镜像内相对差有效；记为 M5 协变量 |
| PSI | **存在** | 存在 | 北星可实测（§5） |
| smaps_rollup / auxv | 存在 | 存在 | 度量与盘点可采 |
| THP | **不存在** | 不存在 | L13 对本目标正式退役（R 化候选） |
| 内核 | 5.4.261 | 6.12 | MGLRU（需 6.1+）本代 TV 不可用；相邻轨道仅留 zram/KSM/overcommit |
| cgroup | v1 | — | PSI 采集走 `/proc/pressure/memory`，非 cgroup v2 memory.pressure |
| 执行策略 | **UEP 签名强制** | 无 | 见 §0.1 |
| 核数 | 侦察记录值 | 4 | L2 门 `arena_max=核数` 按 TV 实际核数取值 |

### 0.1 UEP 绕行（已验证，`docs/tv_board_recon_report.md` UEP 章节）

- 脚本：**stdin 管道注入** `sdb shell sh -s`（执行体是板上已签名 sh；payload 末尾追加 `exit` 确保 EOF 退出）。
- 压力注入：**tmpfs 气球** `dd → /dev/shm/balloon`，增量 append 控速率，`rm` 释放（免二进制，已验证降 64MB 干净恢复）。
- alloc_bench 不上 TV：微基准是板级预筛，TV 阶段门是真实服务；如需校准另走 develkey 签名/develmode，不阻塞协议。

## 1. 前置门（协议启动前必须完成）

- **PG1. TV 分支 T1 重推导**：TV 镜像 glibc 虽同为 2.40，但源自 -Os 产品分支，与审计基线 `tizen_base@8f08a7e`（-O2）可能补丁集不同。对 TV 分支的 glibc source 重跑 T1 级 diff（malloc/nptl/tunables 路径 + dlconf），确认机制结论无偏移。**这是全协议的信任前置**。
- **PG2. tunables 生效性实证**：TV 上 alloc_bench 不可用，改用已签名进程验证——挑一个非 secure 目标，注入 `GLIBC_TUNABLES=glibc.malloc.arena_max=1` 经 systemd drop-in 重启，对比 `malloc_info()` 的 arena 数变化，证明 tunables 在 TV 镜像上确实生效（板级 T2 结论的 TV 侧确认）。
- **PG3. AT_SECURE 目标确认**：§2 漏斗产出的高价值目标，逐个确认 AT_SECURE 状态（盘点已给全量分布：99 非 secure/122）——secure 目标走 Plan B（v2.4 §8），非 secure 走 env。

## 2. 目标进程漏斗（122 → 5~10）

单次采集，`sdb shell sh -s` 注入扩展版盘点脚本，对全部进程采集：

- 基础（现有脚本已有）：AT_SECURE / elf_class / threads / Rss / Pss / env 黑名单
- 新增：`smaps_rollup` 的 **Private_Dirty**（真实私有脏页，L6 收益上界）
- 新增：**arena 数近似** = `/proc/pid/maps` 中 `rw-p` 匿名段 / `[heap]` 段计数（L2/L6 相关性）
- 新增：`/proc/pid/task` 计数与**二次采样换手率**（L2 churn 分类器，v2.4 门要求）
- 新增：实例数（TV launchpad fork 共享页，按副本数加权）

**排序**：`Private_Dirty(Pss) × 实例数`（launchpad 型多副本进程加权）。
**分层**取 Top-N：
- 高线程 + 稳定 task 数（换手率≈0）→ L1/L2 候选
- 高 arena 数 + 高 heap Rss → L6 候选
- churn 型（换手率>0 持续）→ L2 禁用、仅 L1/L3/L6
- secure → Plan B 通道

预期高价值目标类：web-runtime、媒体管线、launcher/EFL 常驻、资源管理器（ServiceR）。

## 3. 首发实验批（TV Batch 1）

以 v2.4 首发包 **L1+L3**（组合已验证）为主，逐目标：

| 格 | GLIBC_TUNABLES（env，systemd drop-in） |
|---|---|
| C0 | 基线 |
| L1+L3 | `glibc.pthread.stack_cache_size=1048576:glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072` |
| +L2 | 追加 `glibc.malloc.arena_max=<核数>`（仅对通过 §2 门的非 churn 目标） |

- 注入：`/etc/systemd/system/<unit>.d/memopt.conf`（经 stdin 注入写入，或若持久分区只读则用 systemd 的 runtime drop-in 路径 `/run/systemd/...`，侦察未覆盖该点——TV Batch 1 首步先探分区可写性）。
- 度量：M1（smaps_rollup Rss+Pss ≥3 轮中位）+ M2（malloc_info 前后）+ **M5 协变量**（记录 -Os、overcommit、核数、无 THP）。
- 性能门：TV 无 alloc_bench，用**真实场景脚本**（应用切换、频道切换、UI 滚动）配合场景内延迟观测；≤5% 目标/≤10% 上限仍为上线门（M3）。

## 4. L6 试点（优先，v2.4 明星杠杆）

- **落点（三家共识）**：优先 UI app 的 `pause`/`app_pause` 生命周期回调（退后台 = 释放后静置，与板级 Part D 形态精确对应）；次选 ServiceR 的内存压力/LMK 事件驱动 trim（把 L6 直接绑到 PSI 北星）。
- **必测代价（v2.4 强制项）**：
  1. **前台恢复 refault 延迟**——退后台 trim 后重新前台的首屏/首响应时延；
  2. **trim 期间全 arena 锁停顿**——若目标在 trim 时仍有活跃分配线程，测停顿（板级 Part D 是线程静止态，此项 TV 首测）。
- 落地形态：产品代码改动，走正常构建+签名链（不受 UEP 影响）。
- 度量三格（M6，板级 Part D 形态）：{仅退后台不 trim / 退后台+trim / L3钉阈值对照}，隔离滞留、主动回收、阈值机制。

## 5. PSI 北星实测（至今空转，本阶段必须落地）

- 采集：1 Hz 读 `/proc/pressure/memory`（some/full avg10/avg60）+ `/proc/vmstat` 的 `workingset_refault`/`pgmajfault`，对齐 smaps_rollup 时间线。
- 注入：tmpfs 气球（§0.1，已验证），增量 append 把系统 `MemAvailable` 稳定压到目标水位（校准到 PSI some avg10 落在 5~10 区间）。
- A/B：同一注入曲线 + 同一代表性 TV 场景（应用切换/频道切换），对目标 service 有无杠杆包两组，比 **PSI some/full avg10 的曲线下面积（AUC）** + refault 计数。
- 前置：侦察已确认 PSI 存在；协议首步复核 `/proc/pressure/memory` 在压力下数值确实响应（气球验证时已见响应）。

## 6. 上线单元与回滚

- env 杠杆：per-service systemd drop-in，永不镜像级全局；回滚 = 删 drop-in + restart。
- L6：产品代码，随版本发布/回滚。
- 每目标独立 A/B 独立裁决，不捆绑上线。
- 实验后恢复现场纪律沿用板级各轮（删配置、复扫盘点确认零 LIVE 命中）。

## 7. 阶段完成判据

- PG1–PG3 通过；§2 漏斗产出确定的 Top 目标集；
- TV Batch 1（L1+L3±L2）逐目标有 Rss/PSS + 场景性能数据 + PSI AUC；
- L6 至少一个试点有回收量 + refault + 锁停顿三项数据；
- 每杠杆每目标满足 M3 双门方可标记"可上线"，否则留在实验态。
- 产出 TV 阶段裁决 → 决定量产 rollout 范围。

## 8. 已知未决（诚实清单）

- TV 分区可写性（drop-in 落 /etc vs /run）——TV Batch 1 首步探明。
- -Os 下 L2 中间档代价曲线与 rpi4（-O2）的偏移量——TV 实测，不外推。
- L6 refault 与锁停顿的真机量级——本阶段首测。
- TV 分支 glibc 补丁 delta（PG1 输出）。
