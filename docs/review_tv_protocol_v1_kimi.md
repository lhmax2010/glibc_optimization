> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# TV 阶段协议 v1 定稿前评审 — Kimi

**评审对象：** `docs/tv_phase_protocol_v1.md`（及 `_zh` 同构）、`docs/tizen_glibc_memopt_design_v2.md` v2.4、`docs/tv_board_recon_report.md`。  
**评审标准：** 执行时是否会导致返工、翻车或数据不可信。  
**总体结论：** **RISKY（附缓解）后可通过**，但 §3/§4/§5 若不在执行前补齐具体方法，极可能中途返工。

---

## Part A — 前置门与流程可执行性（逐节裁决）

| 章节 | 关键动作 | 裁决 | 依赖 / 缓解 | 关键发现 |
|---|---|---|---|---|
| §0.1 stdin 注入 | 通过 `sdb shell sh -s` 把脚本喂给已签名的 `/usr/bin/sh` | **EXECUTABLE with caveats** | 侦察已 PASS；脚本末尾必须显式 `exit`；所有输出重定向到 `/tmp/*.txt` 再 pull，不能依赖 stdout。 | 简单脚本稳定；多进程、`trap`、大输出、交互式提示会导致 sdb 会话挂起或输出混叠。协议只字未提这些边界。 |
| §0.1 tmpfs 气球 | `dd → /dev/shm/balloon`，增量追加，`rm` 释放 | **EXECUTABLE at low pressure; RISKY at target PSI band** | 侦察 64 MB 干净升降 PASS；但 TV 只有 1.6 GB，且 LMK 阈值未知。 | 气球本身可用，但把系统压到 PSI avg10 5–10 时可能先触发 LMK，杀掉目标或气球进程，污染 PSI 曲线。 |
| PG1 TV 分支 T1 重推导 | 对 TV 镜像 glibc 源码做 T1 级 diff | **BLOCKED until source available** | 需要 TV 产品分支源码或源码 RPM；当前工作树是 `-O2` 的 `tizen_base`，不是 `-Os` TV 分支。 | 若只能看二进制，无法确认 malloc/nptl/tunables/dlconf 机制漂移。协议未指定源码获取路径，这是整个协议信任前提的隐藏阻塞项。 |
| PG2 tunables 生效实证 | systemd drop-in + restart，比较 `malloc_info()` arena 数 | **RISKY** | 可改用 `/proc/<pid>/maps` 中 `rw-p` anon / `[heap]` 段数量近似 arena 数；`systemctl` 可用；root 可用。 | 目标进程未修改时无法安全调用 `malloc_info()`（无 gdb，无法签 helper）。协议写 "compare malloc_info()" 但没有给出调用路径。 |
| PG3 AT_SECURE 确认 | 对 §2 漏斗中的高价值目标逐个确认 secure 状态 | **EXECUTABLE** | 侦察已通过 stdin 注入完成 122 进程 inventory：23 secure / 99 non-secure。 | 高价值目标（如 `ServiceE`、DN_* app）已在 inventory 中，可直接查表。 |
| §2 目标漏斗 | 扩展 inventory：smaps_rollup Private_Dirty、maps arena 近似、task 两次采样算 turnover、实例数 | **EXECUTABLE** | 命令矩阵里 `awk/sed/cat/ps/sleep` 都有；`/proc` 可读。 | 脚本较长，但全部可用 POSIX 命令实现；需注意 `/proc/<pid>/cmdline` 对内核线程会报错（如侦察出现的 `4kbtin`），用 `2>/dev/null` 跳过。 |
| §3 TV Batch 1 (L1+L3±L2) | 写 systemd drop-in，restart，测 smaps_rollup + 场景延迟 | **RISKY / partially BLOCKED for non-systemd targets** | `/etc` 可写性未知，`/run/systemd/system/<unit>.d/` 是标准 fallback；`systemctl` 存在。 | **重大缺口：协议默认所有目标都是 systemd unit，但 TV 上大量高价值目标是 launchpad / appfw 启动的（如 `AppD`、`AppS`、`ServiceE` 可能是 systemd，但 DN_* .NET app 不是）。** 这些进程没有 `systemctl restart` 路径。 |
| §3 性能门（真实场景脚本） | 用 app switch / channel change / UI scroll 观测场景内延迟 | **RISKY — method not defined** | 需要可复现场景驱动（Tizen UI test / key injection / app launcher 脚本）和延迟读取点。 | 5%/10% 门在真实场景噪声下极难守住。板级教训：pass 进程噪声带 92 kB 即可淹没信号；TV 场景延迟的抖动通常大于 5%。 |
| §4 L6 试点 | UI app pause / ServiceR LMK 回调中插入 `malloc_trim(0)`；测 refault + 锁停顿 | **Landing EXECUTABLE; measurements RISKY** | 产品代码改动走正常 build+sign，不依赖 UEP 绕过。 | refault 和锁停顿只写“必测”，未给出可执行方法。缺少方法 = 执行时无法关闭 L6 的 "unmeasured cost"。 |
| §5 PSI north-star | 1 Hz 采样 `/proc/pressure/memory` + `/proc/vmstat`；气球注入；同场景 A/B 比 AUC | **Collection EXECUTABLE; attribution RISKY** | `/proc/pressure/memory` 已确认存在且可读；气球侦察可用。 | 气球曲线可复现性、LMK 干扰、场景与注入叠加、系统状态非稳态，都是协议未控制的混淆项。 |
| §6 rollout / rollback | 删 drop-in + restart；L6 随版本回滚 | **EXECUTABLE for systemd; RISKY for appfw** | 需要按 §3 的目标类型分类。 | 恢复后必须重新扫 inventory 确认无 LIVE `GLIBC_TUNABLES`；协议有提到，但缺少具体命令。 |

### 0.1 绕行路线的脆弱性补充

1. **stdin 注入不是通用 shell 会话。** 侦察显示 `sdb shell sh -s` 会把脚本源码回显到 stdout，因此不能解析 stdout 做结构化数据。所有结构化结果必须写文件再 pull。若脚本内部 `&` 后台进程或 `read` 等待输入，sdb 会话不会自动结束，必须显式 `exit` 或 `kill`。协议应规定：
   - 脚本单遍执行，`set -e`；
   - 所有输出重定向到 `/tmp/tv_<step>_<pid>.tsv`；
   - 结尾 `exit 0`；
   - 禁止后台进程存活。

2. **气球注入的 LMK 风险。** TV 只有 `MemTotal 1.6 GB`，远小于 rpi4 的 4 GB。侦察中 64 MB 气球没有触发 PSI，说明要把 `MemAvailable` 压到 PSI 5–10 需要较大比例内存。TV 的 LMK（通常由 `lmkd` 或 `ServiceR` 实现）阈值未公开，可能在 PSI 升高之前就开始杀后台应用。协议必须在 step 0 验证：
   - 气球注入过程中 `/proc/<pid>/oom_score_adj` 是否变化；
   - `dmesg` / `journalctl` 是否出现 `lowmemorykiller` / `kill` 记录；
   - 目标进程是否在气球压力下存活。
   否则 A/B 的 PSI 差异可能来自“目标被杀了”而不是“压力响应”。

### 返工点（§8 未列出的隐藏假设）

| 假设 | 风险 | 建议 |
|---|---|---|
| 所有目标都是 systemd 服务 | 大量高价值目标是 appfw / launchpad 启动，drop-in 无效 | TV Batch 1 step 0 必须列出每个 top-N 进程的启动方式（检查 `/proc/<pid>/cgroup` 第 1 行、父进程、unit 文件存在性）。 |
| `malloc_info()` 可以从外部获得 | 无 gdb、无签 helper 时不可行 | 明确采用 `/proc/<pid>/maps` 段数做 arena 代理，或把 `malloc_info()` 调用写入目标 app 的测量分支。 |
| 真实场景延迟可手工复现 | 手动遥控电视不可复现 | 必须有自动化场景驱动；否则 5% 门无法执行。 |
| TV 分支源码可获取 | PG1 阻塞 | 在协议里写明 source RPM / build server 获取路径；若拿不到，T1 只能降级为运行时符号/行为对比。 |
| `/etc/systemd/system` 可写 | 侦察未覆盖 | 把 `/run/systemd/system/<unit>.d/` 作为第一选择（运行时 drop-in，重启失效），避免依赖持久分区。 |

---

## Part B — 度量有效性

### B1. 性能门的 TV 替代能否守住 M3 的 5%/10% 门？

**结论：能守住，但必须做大量协议目前没写的工程工作。**

真实场景脚本的问题不是“不能测”，而是“噪声会把 5% 效应淹没”。板级已经见识过：pass 进程带来的 92 kB 抖动可以把小杠杆的信号完全吃掉；TV 真实场景的延迟抖动（输入事件、渲染管线、compositor、网络、I/O）通常远大于 5%。

**提高信噪比的具体建议：**

1. **不要测“完整用户旅程”，测分配密集型子操作。** 例如：
   - 连续 20 次应用冷启动到首屏；
   - 连续 20 次频道切换；
   - 连续 20 次进入/退出同一菜单。
   把镜头对准“分配/释放密集且其他变量少”的片段。

2. **使用应用/框架自带时间戳。** 优先读取：
   - Tizen appfw 的 launch / resume / first-frame 日志；
   - `journalctl -u <unit>` 中的 `Started` / `Stopped`；
   - 目标进程自己通过 `appcore` / `ecore` 事件打印的 `pause`/`resume` 时间。
   避免用秒表或外部摄像头。

3. **配对随机化 A/B。** 每个实验单元不要连续跑 C0 再连续跑 treatment；而是随机交错（C0/T/C0/T…），消除随时间漂移（温度、缓存、后台任务）。

4. **设置一个与治疗无关的“控制指标”。** 例如同时记录一次固定网络请求的 RTT 或 UI 中一个不涉及分配的动画帧时间。若控制指标抖动 >5%，本轮数据作废。

5. **用 CPU 时间做辅助代理。** 对纯分配路径，`/proc/<pid>/stat` 的 `utime+stime` 在重复子操作中的方差比 wall-clock  latency 小，可单独作为一个低噪声信号。

6. **样本量。** 每个单元至少 20 次有效重复；报告 p50/p95/p99，而不是只报均值。

### B2. PSI AUC 方法的混淆项

**核心问题：AUC 不是“气球大小”的函数，而是“系统内存状态 × 气球曲线 × 场景行为 × 杠杆 RSS 变化”的叠加。**

| 混淆项 | 影响 | 缓解 |
|---|---|---|
| **系统状态非稳态** | 两次运行初始 `MemAvailable` 不同，同一气球大小产生的 PSI 不同。 | 实验前标准化：冷启动或固定后台应用集合；记录 `MemAvailable` 基线；用气球把起点拉到同一目标值。 |
| **气球曲线不可复现** | `dd` 追加速度受 CPU 调度影响，`MemAvailable` 不会严格按预设曲线走。 | 改为闭环控制：每秒读 `/proc/meminfo` 的 `MemAvailable`，按比例追加/删除气球，使 `MemAvailable` 跟踪目标轨迹。 |
| **场景与气球叠加** | app switch 本身会分配大量内存，可能把 `MemAvailable` 进一步压低， Lever 又改变了 RSS，导致压力水平不同。 | 记录完整的 `MemAvailable(t)` 曲线；事后按实际压力水平分层（bin）比较 PSI；不能只比 AUC。 |
| **LMK 提前杀人** | 气球未到 PSI 阈值时，LMK 可能先杀掉后台进程，降低后续 PSI。 | 实验前检查 `dmesg` / `journalctl` 有无 `lmkd` kill；若出现，该次运行作废。 |
| **overcommit=1 的 PSI 语义** | `vm.overcommit_memory=1` 下分配不会失败，PSI some 主要反映 reclaim stall，不是 allocation stall。 | 同时记录 `pgmajfault`、`workingset_refault`、`pswpin/out`，作为 PSI 的物理页证据。 |

**建议把 PSI AUC 计算升级为“按实际 MemAvailable 归一化的事件 PSI”**：在场景触发前后 ±5 s 窗口内，对 PSI avg10 做积分，并除以该窗口内 `MemAvailable` 低于某阈值的时间比例。这样不同运行的压力强度才可比。

### B3. L6 三格 + 双代价的可执行测法

协议只说 refault 和锁停顿“必测”，但没写方法。下面是可落地的方法：

#### refault 延迟

**首选（需要目标代码改动）：**
- 在 app 的 `app_pause` / `onPause` 回调中记录 `T0 = clock_gettime(CLOCK_MONOTONIC)`，调用 `malloc_trim(0)`，返回。
- 在 `app_resume` / `onResume` 回调中记录 `T1`。
- 记录“首帧可交互”时间 `T2`：
  - 若 app 使用 EFL/ECore，可监听 `Ecore_Evas` 的 first-frame callback；
  - 否则用 appfw 日志中 resume 完成到首屏渲染的已知标记；
  - 最差情况下用 `/proc/<pid>/smaps_rollup` 的 Rss 稳定点作为 refault 代理（Rss 停止快速增长 ≈ 主要工作集已拉回）。
- **指标：** `T2 - T1`（trim 组 vs no-trim 组），以及 `T2 - T0`（总暂停-恢复周期）。

**次选（无代码改动时）：**
- 通过 `sdb shell` 发送 `SIGSTOP/SIGCONT` 或 appfw 的 background/foreground 命令，外部用 `sdb shell` 轮询 `/proc/<pid>/smaps_rollup` 的 Rss，直到连续 3 次采样变化 <1%，作为 refault 完成代理。精度低，只能做相对 A/B。

#### 锁停顿（trim-time all-arena lock stall）

**唯一可靠方法是在测量构建中 instrument `malloc_trim` 调用点：**
- 产品代码中包裹：
  ```c
  struct timespec t0, t1;
  clock_gettime(CLOCK_MONOTONIC, &t0);
  malloc_trim(0);
  clock_gettime(CLOCK_MONOTONIC, &t1);
  // 上报 trim_duration_ms
  ```
- 同时记录 trim 时刻各线程 CPU 时间快照：读取 `/proc/<pid>/task/<tid>/stat` 的 `utime+stime`，trim 后再次读取。若其他线程在 trim 期间 CPU 时间几乎为 0，而 trim 持续数 ms，说明它们被锁阻塞。
- **并发分配压力测试：** 在测量构建中增加一个后台线程，在 trim 前后持续 `malloc/free` 固定大小。通过对比“有压力线程” vs “无压力线程”的 trim 持续时间，量化锁停顿。该压力线程只在测量构建中存在，正式版关闭。

**不改 glibc 的间接方法（辅助）：**
- 高频率采样 `/proc/<pid>/task/*/stat` 的 `state` 字段，看 trim 期间是否有线程长时间处于 `D` 或 `S`。但用户态 mutex 竞争通常不表现为 `D`，可靠性差，只能做定性参考。

---

## Part C — 缺失项与风险

### C1. 多杠杆叠加的 TV 验证

协议在 §3 只组合了 **L1+L3**，然后“±L2”。但量产时一个 service 很可能同时拿到 **L1+L3+L2+L6**。板级只验证了 L1+L3；L6 与 L3 的机制正交性已在板级 Part D 验证；但 **L6 与 L2 的交互没有验证**：
- `arena_max` 减少后，堆碎片形态改变，`malloc_trim(0)` 能回收的量可能不同；
- L1 降低 stack cache 后，线程创建/销毁成本变化，可能影响 churn 类 service 的行为。

**建议：** 在 TV 阶段末尾增加一个“full-bundle validation”单元：对至少 2 个非 churn 目标跑 `{C0, L1+L3, L1+L3+L2, L1+L3+L2+L6}` 四格，确认无负向相互作用。

### C2. 真实系统 service restart 的安全/稳定性风险

协议 §6 轻描淡写“rollback = delete drop-in + restart”，但没评估 restart 本身的破坏力。TV 上 restart 某些进程会：
- 重启 `enlightenment` / `ServiceC`：可能导致 UI 重启或看门狗触发；
- 重启 `ServiceR`：可能释放其管理的 LMK 策略，导致误判；
- 重启 `ServiceE`：影响所有 Web 应用；
- 重启 systemd 管理的底层服务：可能触发依赖它的服务级联重启。

**建议增加一个“restart 风险分级”前置动作：**
| 等级 | 含义 | 处理方式 |
|---|---|---|
| 绿 | 独立 service，无硬依赖 | 可直接 restart |
| 黄 | 有依赖，但可接受短暂不可用 | 在实验窗口内操作，准备 rollback |
| 红 | UI/看门狗/关键守护 | **不许直接 restart**，必须用克隆环境或 devel image 验证 |

同时要求每次 restart 前：
- `systemctl show <unit> --property=Requires,Wants,After,Before`；
- 记录 `journalctl -u <unit> --since=-1h`；
- 若 restart 后 30 s 内 unit 进入 failed，立即 `systemctl reset-failed` 并回滚。

### C3. 从“单目标可上线”到“量产镜像默认开启”的决策缺口

§7 的完成标准只到“决定 production rollout scope”，但没有回答：
- 需要多少个 service 验证通过才考虑镜像默认？
- 默认开启的杠杆集合是什么？
- 是否需要 A/B cohort（小批量机型/年份）？
- 回滚触发条件（crash 率、perf 投诉、OOM 增加）是什么？

**建议：** 在 §7 后增加“量产升级阶段”小节，至少包含：
1. Lab 单目标 shippable；
2. 限定机型 cohort（e.g. 2026 T-KSU2EJAKUC）1000 台灰度，监控 crash 率、RSS 中位数、PSI 指标；
3. 全型号默认开启，保留 per-service opt-out 开关。

### C4. 其他隐藏假设

- **`-Os` 与 `-O2` 的性能偏移：** 协议作为 M5 covariate 记录，但 TV 阶段不会重跑板级 full 曲线。若 `-Os` 让 allocator 热路径本来就慢了 5%，则 5% 门被天然压缩。建议至少用板级 `-Os` 对比样例或 TV 上一个简单 micro 样例（如果未来能签 helper）做一次 sanity。
- **armv7l vs aarch64：** 协议目标写 armv7l，但未说明 aarch64 TV 是否同步。若产品同时有两架构，是否需要复制 TV 阶段？应在协议开头明确范围。
- **数据留存与可审计：** 协议没规定实验日志、原始 `smaps_rollup`/`malloc_info`/PSI 文件的命名、保存期限、hash。大规模执行后若没有可审计数据，评审无法复现。

---

## Top-3 最可能导致 TV 阶段返工的点

1. **§3 真实场景性能门缺少自动化场景驱动和统计协议。** 如果执行时只能手动遥控电视、肉眼读秒，5%/10% 门将无法可信判定，所有 env lever 的 shippable 结论都会悬置。
2. **§5 气球 PSI 曲线可能被 LMK 或系统状态非稳态污染。** 若 A/B 之间目标进程被 LMK 杀掉，或 MemAvailable 起点不同，AUC 差异将不可归因于杠杆，整个 north-star 证据链会崩塌。
3. **§4 L6 的 refault / 锁停顿没有写入可执行方法。** 协议把这两项列为“必测”，但没有 instrument 方案。执行团队要么报“测不了”导致 L6 卡在未关闭风险，要么用不可信代理强行关闭，留下上线后患。

---

## negative_facts（已确认不会如协议假设那样工作）

1. **UEP 会阻止 `/tmp` 下未签名脚本/ELF 执行。** 侦察明确：`[uep][bash] the file is NOT signed!!` 和 `/tmp/alloc_bench.armv7l: Operation not permitted`。协议不能依赖推送任何未签名 helper 到 `/tmp` 并执行。
2. **stdout 不是干净的数据通道。** `sdb shell sh -s` 会把脚本源码回显到 stdout，且末尾需要显式 `exit`。任何依赖 stdout 解析的协议步骤都会失败。
3. **THP 在 TV 内核上不存在。** `/sys/kernel/mm/transparent_hugepage/` 路径缺失，L13 退休。
4. **MGLRU 不可用。** kernel 5.4，`<6.1`，TV 阶段只能围绕 zram/KSM/overcommit 做系统级 adjacent track。
5. **`malloc_info()` 不能从外部注入到未修改目标。** 没有 gdb，没有签名 helper；要么改目标代码，要么用 `/proc/pid/maps` 代理。
6. **alloc_bench 不能上 TV。** 侦察已证；TV 阶段所有 gate 必须是真实 service。

---

## cannot_verify（执行前必须补齐的信息）

1. TV 产品分支 glibc 源码是否可获取（PG1 阻塞项）。
2. top-N 目标进程中哪些是 systemd unit、哪些是 appfw/launchpad 启动。
3. `/root` 或其他路径是否允许未签名执行（侦察只测了 `/tmp`）。
4. TV 的 LMK / `lmkd` / `ServiceR` 触发阈值与日志位置。
5. 是否有可用的 Tizen UI 自动化框架或场景驱动工具。
6. 目标 app 是否已有 `pause`/`resume` 生命周期日志或首帧标记。
7. `/etc/systemd/system` 与 `/run/systemd/system` 的实际可写性。
8. 出厂 TV 是否启用 watchdog，以及 restart 关键 service 是否会触发 reboot。
