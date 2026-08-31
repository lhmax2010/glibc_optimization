> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# TV Phase Protocol v1 Pre-freeze Review (GPT-5 Codex)

## 评审头部

- Reviewer: GPT-5 Codex
- Date: 2026-07-10
- Commit: `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Materials: `docs/tv_phase_protocol_v1.md`, `docs/tizen_glibc_memopt_design_v2.md` v2.4, `docs/tv_board_recon_report.md`, Batch 1/2/2.5 reports, `bench/alloc_bench/`.
- Method: cross-checked every protocol step against TV recon constraints: UEP signature enforcement, stdin injection behavior, command matrix, cgroup v1, PSI, smaps/auxv, `/dev/shm` balloon, and TV inventory top processes. This review does not recompute Batch numeric claims.
- External anchors: Linux PSI docs for `some/full/avg*/total` semantics and cgroup2 PSI scope: https://docs.kernel.org/accounting/psi.html ; Linux procfs docs for `smaps` RSS/PSS/Private_Dirty semantics: https://docs.kernel.org/filesystems/proc.html.

## Part A: 前置门与流程可执行性

| Section | Verdict | 执行性审查 | 返工风险 / 缓解 |
|---|---|---|---|
| §0.1 stdin 注入 | RISKY | 已验证最小 smoke 和完整 inventory 可通过 `sdb shell sh -s` 跑通，但 plain EOF 不会自动退出，必须尾随 `exit`；完整注入时 `sdb shell` stdout 会回显脚本文本，只有重定向到 TV 侧文件后再 pull 才干净。证据: `docs/tv_board_recon_report.md:401-428`。 | 对复杂脚本、多后台采样器、trap、大 stdout 不应默认稳定。要求: 所有脚本 `stdout/stderr/rc` 分文件落 `/tmp`；显式 `exit`; 分阶段小脚本；禁止依赖交互 stdout；每阶段 pull 后校验行数/RC/SHA；cleanup 脚本也用 stdin 注入。 |
| §0.1 tmpfs balloon | RISKY | `/dev/shm` 存在且 64 MiB balloon 成功，MemAvailable 下降约 65 MiB 后恢复；PSI 可读。但该 smoke 没制造压力: PSI avg 仍 0，`total` 只增 1 us。证据: `docs/tv_board_recon_report.md:473-522`。 | tmpfs 文件不是可被 OOM kill 释放的匿名进程内存；若压过 LMK/OOM 阈值，可能杀目标进程或留下 balloon 文件污染后续运行。要求: 先做 pressure-only staircase，设置 MemAvailable 硬下限和 abort 条件，记录每秒 MemAvailable+PSI+目标 PID 存活，失败时先 `rm /dev/shm/balloon*` 再裁决；不要把 64 MiB smoke 当 PSI 校准。 |
| PG1 TV 分支 T1 重推导 | BLOCKED | 这是主机/源码门，不依赖 TV shell；但当前材料只有 runtime `glibc-2.40-1.7.armv7l` 和 `tizen_base`，没有 TV 产品分支源码/SRPM/SHA。协议只说"重跑 diff"，没定义如何绑定到实际 TV 包。证据: runtime 包和 build id 在 `docs/tv_board_recon_report.md:10-12`, `:92-103`; v2.4 T1 范围在 `docs/tizen_glibc_memopt_design_v2.md:57-60`。 | 冻结前补依赖: 获取与 `glibc-2.40-1.7.armv7l` 对应的 source rpm 或产品分支 commit，记录 exact build flags/spec，按 T1 路径 diff。否则后续所有机制结论仍是 baseline-portability 假设。 |
| PG2 tunables 生效实证 | BLOCKED as written | `GLIBC_TUNABLES` drop-in + restart 可尝试，但"compare `malloc_info()` arena count"对任意真实 signed process 没有外部接口；TV 上 alloc_bench/unsigned ELF 被 UEP 拦截，PG2 quick probe 未跑。证据: `docs/tv_board_recon_report.md:229-262`, `:300-309`。 | 必须二选一: A) 产品/工程 build 给目标进程加 `malloc_info()` dump endpoint/signal handler；B) 将 PG2 降级为 `/proc/<pid>/maps` arena/heap segment proxy，并明确它只证明 env 进入+粗略 arena 变化。没有 A/B 之一，PG2 不能作为 precondition。 |
| PG3 AT_SECURE 分流 | EXECUTABLE | stdin 注入 inventory 已拿到 122 行: AT_SECURE=1 为 23, AT_SECURE=0 为 99, unknown=0, live env hit=0。证据: `docs/tv_board_recon_report.md:429-449`。 | 对高价值目标必须"就地重查": restart/场景切换后 PID 会变，AT_SECURE/env 需要在每个 A/B cell 启动后重新读取。Top RSS 前五均为 secure，普通 env 路线不会覆盖最高内存目标。证据: `docs/tv_board_recon_report.md:451-464`。 |
| §2 target funnel | RISKY | 基础字段可跑；`smaps_rollup`、auxv、task count、maps 都可读，命令矩阵足够。证据: `docs/tv_board_recon_report.md:105-164`。但现有 inventory 脚本只输出 AT_SECURE/threads/RSS/PSS/env/cmdline，不含 Private_Dirty、Pss_Anon、arena proxy、task turnover、instance grouping。证据: `docs/tizen_memopt_inventory.sh:18-24`, `:55-63`, `:89-90`。 | 漏斗脚本本身是新增实现项，不是已验证件。要求先在 TV 上 dry-run extended inventory，校验列完整、行数稳定、/proc race 只影响少量 PID。另补 target->control-plane 映射: systemd unit / AUL app / launchpad pool / product code owner；否则 §3 无法给 top-N 施加 lever。 |
| §3 TV Batch 1 | RISKY; BLOCKED for AUL/app targets until injection path is defined | `systemctl`/`journalctl` 存在，service drop-in 在 service-backed daemon 上原则可行。证据: command matrix `docs/tv_board_recon_report.md:137-140`。但 TV top targets 多为 app/loader/AUL 进程，未必有 dedicated systemd unit；rpi4 Batch 1 曾跳过 launchpad pool 因无 targetable per-app unit。证据: `docs/board_ab_batch1_report.md:125`; TV top rows at `docs/tv_board_recon_report.md:451-464`。 | §3 需要先把目标分为 systemd-service、AUL/app、launchpad-loader、secure Plan B。对非 systemd 目标，drop-in 不成立；要定义 app launcher env 注入、code path, 或排除。重启前必须 `systemctl show` 记录 `Restart`, `WatchdogSec`, `Requires/Wants/PartOf`, cgroup, MainPID，并有恢复命令。 |
| §4 L6 pilot | RISKY | 产品代码路径可绕开 UEP，三格设计正确；但协议只说"必测" refault/lock stall，没有具体测法。证据: `docs/tv_phase_protocol_v1.md:67-75`; glibc all-arena lock walk in `malloc/malloc.c:5209-5228`。 | "ServiceR memory-pressure/LMK-event-driven trim"表述危险: `malloc_trim(0)`只 trim 调用进程自己的 heap，ServiceR 不能替别的目标释放 RSS，除非目标进程内有 handler/IPC。首个 pilot 应选拥有大 heap 且有 pause/resume hook 的 app/runtime；ServiceR 只能作为触发器，不是替代执行者。 |
| §5 PSI | RISKY | `/proc/pressure/memory` 存在，cgroup v2 不存在，所以只能做 system-wide PSI。证据: `docs/tv_board_recon_report.md:148-159`, `:285-290`。Linux PSI docs说明 `total` 是绝对 stall time，avg10/60/300 是平滑窗口；cgroup PSI 需要 cgroup2。 | avg10 AUC 对短场景有 carry-over 和平滑混淆。要求主裁决用 `total` delta/AUC，avg10 只作展示；每个 A/B 前做 cooldown 直到 avg10 接近基线；同时记录 MemAvailable 曲线并要求曲线相似，否则 PSI 差异不可归因。 |

## Part B: 度量有效性发现

| Area | Finding | Required fix before execution |
|---|---|---|
| M3 real-scenario perf gate | 真实场景脚本可以作为 shipping gate，但不能自动守住 5%/10%。TV 上 UI、network、GC/JIT、background daemon、launchpad pool 都会放大噪声；Batch 1 已有 `pass` Rss 噪声 92 kB 吞掉小效应的先例 (`docs/board_ab_batch1_report.md:52-58`)。 | 每个 scenario 先做 C0 noise audit: 至少 10 次，ABBA/随机顺序，固定输入内容和网络状态，记录 median/MAD/CI。若 95% CI 覆盖 +/-5%，该 scenario 不能裁决 5% perf gate，只能报 inconclusive。 |
| Scenario latency observation | §3 没规定 latency marker。没有第一帧、channel-ready、app-switch-complete 的明确事件，`date` 包 shell 包围只能测脚本/IPC，不是用户可感知 latency。 | 每个 scenario 必须定义 start/end marker 来源: app/framework journal marker、compositor/first-frame marker、或产品 instrumentation。没有 marker 的 target 不进入 M3 shipping gate。 |
| M2 attribution | `malloc_info()` 对真实服务不可达是协议最大测量缺口。`/proc` 能给 RSS/PSS/maps，但不能给 fast/rest/tcache/arena free bytes。 | 对 L6/PG2/疑难目标提供工程 build dump hook: signal handler 或 debug IPC 调用 `malloc_info()` 到 `/tmp/<pid>.xml`；否则报告中把 M2 标为 missing，不能声称 allocator attribution。 |
| PSI AUC confounders | 同一注入曲线很难保证: tmpfs 写入吞吐、page cache/shmem reclaim、zram、后台服务、场景自身分配都会改变 MemAvailable 和 PSI。64 MiB recon smoke没有实际 pressure，说明还未校准到 PSI band。 | 增加 pressure-only cell: {no scenario, scenario-only, pressure-only, pressure+scenario}. A/B 比较前要求 balloon bytes/time curve 和 MemAvailable AUC 在阈值内，例如 <5% 偏差；否则重跑。所有 runs 监控目标 PID 是否重启/被杀，journal/dmesg 是否有 LMK/OOM。 |
| PSI metric choice | avg10 AUC 对几十秒以内场景有滞后和前次 run 残留。Kernel docs同时给出 `total` 绝对 stall time，适合自定义窗口。 | 主指标改为 `some.total`/`full.total` 在场景窗口内的 delta；avg10/avg60 只作为趋势和 sanity。采样频率 1 Hz 可保留，但 start/end 必须和 scenario marker 对齐。 |
| L6 refault latency | "refault"不能只看 system-wide `workingset_refault`。需要映射到用户恢复体验。 | 对 background-no-trim vs background+trim: 记录 app pause -> trim -> resume -> first-frame/first-response 的 wall time；同时读取目标 `/proc/<pid>/stat` minflt/majflt delta、`/proc/vmstat` `workingset_refault`/`pgmajfault` delta、目标 RSS/PSS。裁决用 first-frame p95/p99 + fault deltas。 |
| L6 lock stall | 不改 glibc 时，从 shell 外部看不到 malloc arena mutex wait。 | 因 L6 本身是产品代码改动，可在同一工程 build 加低侵入 instrumentation: trim 线程记录 `malloc_trim()` wall time；活跃 allocator 线程在 trim 前后记录 malloc/free latency gap 或 heartbeat gap，输出 max/p99/p999。若目标在 pause 后没有 active allocating threads，可声明 lock-stall N/A but proven by thread quiescence log。 |

## Part C: 缺失项与风险

| Missing / Risk | Why it matters | Proposed addition |
|---|---|---|
| Lever combination matrix on TV | Board only combo-verified L1+L3. TV Batch 1 plans L1+L3 then `+L2`, but L6 may be piloted on top of L3/L2 and change reclaim/refault behavior. | Per target measure C0, L1+L3, L1+L3+L2 when allowed, L6 alone, L6+surviving env bundle. Do not infer additive savings. |
| Target control-plane mapping | Top memory targets include secure app/loader processes (`DN_*`, `ServiceE`, `ServiceH`) and non-secure app processes; systemd drop-in may not affect their environment. | Add a §2.5 mapping table: PID/cmd -> unit or launcher -> env injection route -> restart route -> owner -> Plan B/env eligibility. |
| Service restart safety | Restarting TV UI, app launcher, ServiceR, network, or SDB-adjacent services can cascade, trigger watchdogs, or lose test access. SDB itself recently required recovery. Evidence: `docs/tv_sdbd_recovery_guide.md:34-72`, `:135-148`. | Before any restart: snapshot `systemctl cat/status/show`, dependencies, `WatchdogSec`, `Restart`, cgroup, PIDs; define denylist; run in maintenance window; verify UI/SDB/network after each cell; keep rollback command in the artifact. |
| Runtime drop-in semantics | Protocol says `/run/systemd/...` if `/etc` is read-only, but does not verify path, daemon-reload, or whether unit accepts Environment overrides. | Add step 0: create harmless test drop-in on a disposable unit or chosen unit with `Environment=TV_MEMOPT_PROBE=1`; restart; verify `/proc/<pid>/environ`; remove; restart; verify absent. |
| Data artifact contract | Protocol says produce adjudication but not artifact schema. Without raw curves and run IDs, PSI/perf disputes will be unreplayable. | Require per run directory with payload script, stdout/stderr/rc, inventory before/after, meminfo/psi/vmstat time series, smaps snapshots, unit state, journal window, SHA256, and notes on aborted runs. |
| Rollout gap | §7 marks lever x target shippable, but not the jump from one target to product/default scope. Multiple per-service wins may interact through boot time, PSI, LMK, and shared page accounting. | Add "production rollout gate": all selected services enabled together on full image, cold boot xN, 24h idle/usage soak, pressure scenario, rollback package, telemetry counters, and canary criteria. Keep per-service opt-in unless image-wide gate passes. |
| Security discipline | stdin injection and tmpfs balloon are lab bypasses. Leaving `/tmp` scripts, `/dev/shm` files, or drop-ins changes the system under test. | End every run with cleanup audit: no `GLIBC_TUNABLES` live hits except intended cell, no `/dev/shm/balloon*`, no memopt drop-ins, target units restored, SDB still connected. |

## Top-3 likely TV返工点

1. **`malloc_info()` attribution is not executable for real TV services as written.** PG2, M2, L6 thresholding, and "arena count" validation all lean on a capability the recon did not establish. Add a product diagnostic hook or downgrade claims to `/proc/maps` proxies.

2. **Target control path is underspecified.** The high-memory targets are mostly AT_SECURE app/loader processes, not simple systemd daemons. Without a PID -> unit/launcher/code-owner map, §3 will fail mid-run or test the wrong process.

3. **PSI/perf gates can produce non-adjudicable data.** The tmpfs balloon has not yet shown nonzero PSI, avg10 AUC is smoothed/carry-over-prone, and real-scenario latency has no marker/noise protocol. This can burn TV time and still return "inconclusive."

## negative_facts

- TV root SDB is available now, but only after a separate SDB recovery; developer-mode/IP gating is real (`docs/tv_sdbd_recovery_guide.md:34-72`).
- TV runtime is Tizen 10 TV, armv7l, kernel 5.4.261, glibc 2.40 package `glibc-2.40-1.7.armv7l` (`docs/tv_board_recon_report.md:35-57`, `:92-95`).
- Command set lacks BusyBox and `hostname`, but has `sh/od/awk/sed/tr/grep/cut/sort/head/tail/wc/date/sleep/cat/ls/rm/chmod/mkdir/df/free/pgrep/pkill/ps/top/systemctl/journalctl/rpm/pmap` (`docs/tv_board_recon_report.md:105-146`).
- TV has PSI and `smaps_rollup`; cgroup v2 controllers are absent, so per-cgroup `memory.pressure` is unavailable (`docs/tv_board_recon_report.md:148-159`).
- Unsigned `/tmp` scripts and ELFs are blocked by UEP; alloc_bench cannot run on TV by simple push+exec (`docs/tv_board_recon_report.md:213-263`, `:300-309`).
- stdin inventory bypass succeeded and produced 122 TV process rows with AT_SECURE=23/99/0 and live env hits=0 (`docs/tv_board_recon_report.md:427-449`).
- Top TV RSS/PSS targets are dominated by AT_SECURE app/loader processes: `AppProcD`, `AppProcB`, `ServiceE`, `AppProcE`, `ServiceH` (`docs/tv_board_recon_report.md:451-464`).
- 64 MiB tmpfs balloon was reversible but did not create meaningful PSI pressure in the smoke (`docs/tv_board_recon_report.md:484-522`).

## cannot-verify

- Exact TV product glibc source delta for `glibc-2.40-1.7.armv7l`; PG1 depends on source/SRPM/commit not present in this checkout.
- Whether `/etc/systemd/system` is writable and whether `/run/systemd/system` runtime drop-ins are sufficient on this image.
- Whether high-value app/loader targets can receive per-process env tunables through AUL/launchpad without product code changes.
- Whether any target already exposes a safe `malloc_info()` or allocator diagnostic endpoint.
- LMK/OOM thresholds and whether tmpfs balloon can be calibrated to PSI 5-10 without killing targets.
- Availability of first-frame/channel-ready/app-switch latency markers in TV product logs.
- L6 product source ownership, signing path, and acceptable lifecycle hook for the selected pilot app/runtime.
- Combined full-image behavior when several per-service levers are enabled together.
