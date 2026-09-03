> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc 双轨执行协议 v2 定稿前评审 - GPT-5

- 评审者：Codex / GPT-5
- 日期：2026-08-06
- 代码基线：`tizen_base@8f08a7e30396822a8d969d357822a6ffd56b43fb`
- 核对方法：逐行读取 `docs/tizen_glibc_protocol_v2_zh.md`、`docs/tv_recon2_report.md`、`docs/tv_recon3_report.md`、v1 评审、v2.4 设计；用 `rg/nl/head/perl` 核对 glibc 源码、`parse_smaps.pl`、TV 原始 inventory/smaps/PSI 输出。外部语义锚点仅用官方/手册资料：Linux PSI docs <https://docs.kernel.org/accounting/psi.html>、`smaps_rollup` ABI <https://www.kernel.org/doc/Documentation/ABI/testing/procfs-smaps_rollup>、`PR_SET_VMA_ANON_NAME`/maps 手册 <https://man7.org/linux/man-pages/man2/pr_set_vma.2const.html> / <https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html>。

## Part A - v1 三个硬伤是否修好

| v1 硬伤 | 裁决 | 证据与攻击点 | 执行前修正 |
|---|---|---|---|
| 漏斗指标 | **PARTIALLY-FIXED** | v2 改为 `[heap] + 1 MiB 对齐匿名 rw-p arena-like` 的 Private_Dirty 绝对量，方向比 v1 的 RSS/总 Private_Dirty 更对。重算 `product_board/C_glibc_heap_ratios.tsv`：协议 Top-5 glibc 面合计 **41,236 kB**，Top-10 合计 **49,116 kB**；表内 14,872/10,080/7,912/4,960/3,412 kB 与原始 TSV 一致。源码也支持这个 signature：armv7l `HEAP_MAX_SIZE=1024*1024`，arena heap 起始按该值对齐（`malloc/arena.c:28-64`）。但该指标仍是代理，不是所有权证明；`parse_smaps.pl:23-27` 只看形状，不能排除同形状 .NET/JIT/运行时匿名段。更致命的是，原始 inventory 显示协议 Top-5 均 `AT_SECURE=1`：`AppProcB`、`AppProcD`、`ServiceE`、`AppProcA`、`ServiceH`，而 glibc 在 AT_SECURE 下直接忽略 tunables（`elf/dl-tunables.c:299-301`）。因此“按 glibc 面排序”可作为侦察漏斗，但不能支持“层 2 env 是主收益面”。 | 漏斗必须先过滤或分层：`AT_SECURE=0 && env 可达`、`AT_SECURE=1 需 mallopt/产品代码/默认补丁`、`不可达`。对启发式结果必须在 A 轨用 `decorate_maps` 校准，并在 B 轨 PG2 上至少用一个非 secure 目标闭环。 |
| PSI 设计 | **PARTIALLY-FIXED** | v2 废掉闭环稳水位，修掉了 v1 的构造性自抵消。TV `.26` 的 30%/40% 气球确实出现非零 PSI 且未匹配 LMK：30% `MemAvailable=695,676 kB`，40% `598,552 kB`（`docs/tv_recon3_report.md:136-144`）。但原始曲线不支持把 `some/full avg2 AUC` 作为主裁决：10%/20% 时 `avg*=0` 但 `some.total` 已增加 **116,075 us / 83,512 us**；30%/40% 的 `avg2/6/10` 数值完全相同，cleanup 后仍保持同值（`b5_psi_balloon.out:151-263`），像平滑窗口/采样刷新假象或写入期瞬态，而非稳态压力平台。zram 也已在用 48,268 kB，swappiness=100（`docs/tv_recon3_report.md:124-126`），A/B 的压缩率、swap-in/out、后台 reclaim 都会混入系统级 PSI。 | 主指标改成场景窗口内 `some.total`/`full.total` delta；`avg2/6/10` 只做展示。每轮保留四格：scenario-only、pressure-only、pressure+scenario C0、pressure+scenario T；要求 balloon bytes、MemAvailable AUC、SwapFree/zram 曲线对齐，否则不可裁决。30% 可作初始档，40% 先禁用到安全复核完成。 |
| arena 归因 / `malloc_info()` 替代 | **PARTIALLY-FIXED** | 源码核对确认 `glibc.mem.decorate_maps` 在 glibc 2.40 存在（`elf/dl-tunables.list:146-149`），`__set_vma_name` 受该 tunable 控制并调用 `prctl(PR_SET_VMA, PR_SET_VMA_ANON_NAME, ...)`（`sysdeps/unix/sysv/linux/setvmaname.c:40-43`），arena 标注字符串为 `" glibc: malloc arena"`（`malloc/arena.c:448`），普通 mmap malloc 标注为 `" glibc: malloc"`（`malloc/malloc.c:2432,2519`）。Linux maps 显示格式应为 `[anon: glibc: malloc arena]`，与协议描述一致。问题是 TV 产品 `2.40-1.12` 补丁集未知，当前 B 轨没有实际启用验证；现有 TV smaps 中未出现 `[anon: glibc...]` 标签，因为 baseline 未开 tunable。fallback 只能给 arena count proxy，不能替代 `malloc_info()` 的 bin/tcache/free-byte 归因。 | PG2 目标必须选 `AT_SECURE=0`。通过标准应同时满足：`/proc/PID/environ` 可见 sentinel/GLIBC_TUNABLES、maps 出现 `[anon: glibc: malloc arena]`、`arena_max=1` 后 arena-like/label 数下降。若产品分支缺该特性，fallback 报告只能写“arena proxy”，不能写“精确识别”。 |

## Part B - v2 新机制是否站得住

| 项 | 裁决 | 发现 |
|---|---|---|
| 层 2 组级注入 | **RISKY / 主收益面未站住** | “子 exe 与父不同 => exec => tunables 重新解析”这一半成立：新 ELF exec 会重新跑 loader，`_dl_sysdep_start` 调 `__tunables_init(_environ)`（`sysdeps/unix/sysv/linux/dl-sysdep.c:100-112`）。但 v2 把后半句也当成事实了：env 从 `ServiceJ` 继承到 app，且目标非 AT_SECURE。侦察 3 只证明 Top-10 有 7 个 launchpad 后代、无 per-app unit（`docs/tv_recon3_report.md:177-179`），没有证明 pool drop-in 存在、环境未被 `clearenv`/白名单过滤、或 child 会保留 `GLIBC_TUNABLES`。更硬的是原始 inventory 显示 Top-5 glibc 面全是 `AT_SECURE=1`，按源码即使 env 传到也会被忽略。 |
| 层 2 最小验证实验 | **必须前置** | 选择一个 `AT_SECURE=0` 的 launchpad 子进程作正例，如 `ServiceD` 或 `ServiceL`，另保留当前 Top-5 secure 目标作负例。给 `ServiceJ` 启动点注入 `Environment=TV_MEMOPT_SENTINEL=<runid>` 与 `GLIBC_TUNABLES=glibc.mem.decorate_maps=1:glibc.malloc.arena_max=1`。若不能安全 restart pool，则用 `/etc` 持久 drop-in 后整机重启；注意 `/run` drop-in 会在 reboot 消失。新 app 出生后采 `/proc/PID/auxv`、`/proc/PID/environ`、`/proc/PID/maps`、arena count。通过条件：非 secure child 有 sentinel，maps 有 glibc arena 标签或 arena 数降至最小；secure child 应无效果，作为 AT_SECURE 负控。 |
| 双轨移交规则 | **PARTIALLY-SUPPORTED** | v2 禁止跨轨转移百分比/MB/服务结论是正确的。遗漏的不可比理由还有：TV/RPI glibc release 与 Build ID 不同、TV `.text` 尺寸不同、`/run/dlconf.dat` 状态不同（TV 无，RPI 有）、UEP 执行落点相反、launchpad/AT_SECURE 分布与目标进程集不同（`docs/tv_recon3_report.md:204-219`）。CPU flags 也不能只当“调用方性能”差异：ARM 源码有 hwcap/IFUNC memcpy 选择（`sysdeps/arm/armv7/multiarch/ifunc-memcpy.h:25-36`）和 GCC 后端原子实现分支（`sysdeps/arm/atomic-machine.h:25-40`）。建议把可移交锚收窄为“malloc/tunables 机制存在性和测试工具”，不要写“glibc 内部行为”泛可比。 |
| M3 统计判据 | **RISKY but directionally right** | 配对交替、n>=20、CI 上界落门内，是 v1 后最小可接受统计框架。但 TV 真实场景的执行成本未预算：每个 treatment 至少 20 对 A/B = 40 次场景；若层 2 需要整机重启而不是 pool restart，单个格可能变成 40 次 reboot，时间和漂移都会爆。场景指标必须有机器可读 timestamp；人工遥控/肉眼时延无法裁决 5% 门。先跑 B-0 C0/C0 n>=20，若 95% CI 宽度已经超过 5%，该场景只能给 inconclusive，不能上线。 |

## Part C - 缺口与风险

| 缺口 | 风险 | 建议 |
|---|---|---|
| Top-5 `AT_SECURE=1` 未进入 §8 未决 | v2 的“主收益面”可能在 env-only 路线下全失效；PG3 被列为确认项，却没有反馈到 §2/§4 的首批目标和 Plan B。 | 冻结前把 Top target 表加 `AT_SECURE` 列。Top-5 只能进入 code/mallopt/default-patch 轨；env 首批应转向非 secure launchpad 或 systemd 目标。 |
| launchpad pool unit/drop-in 未证实 | `cgroup` 证据显示 app 与 pool 在 `init.scope`，`c3_unit_map.out` 未出现 `ServiceJ.service`。协议的 user-level drop-in 路径仍是猜测。 | 增加首步 `systemctl status/cat/show ServiceJ*`、`loginctl/user@5001`、父 PID 241/255 的 unit 反查。无 unit 时改找启动脚本 `/usr/bin/ServiceJ.sh` 的 env 入口或判定层 2 env blocked。 |
| `/run` drop-in 与整机重启互斥 | 协议默认 `/run/systemd/...`，又说层 2 优先 full reboot；reboot 会清掉 `/run` drop-in，导致 treatment 实际未生效。 | B-1 用 `/run`；B-2 若需要 reboot，必须用 `/etc` 持久 drop-in，并在每次 boot 后验证 `/proc/PID/environ`/maps。 |
| PSI 40% 档安全信号不干净 | 原始 dmesg 在 40% 档窗口出现 `send signal from KERNEL, SIG : 11, .NET TP Worker(3602)`，虽非 LMK，但足以污染“无异常”判断。 | 护栏从“LMK kill”扩展为 dmesg/journal fatal signal、target PID restart、crash/service failure 全部作废；默认只跑 30%，40% 需单独安全复核。 |
| `startPSIKillAt=250` 语义未明 | 当前 `avg2=6.95` 看似低于 `psiTriggerPercent=55`，但 `startPSIKillAt=250` 的单位和触发字段未知；ServiceR 实际 Memory 档也未确认。 | 在 pressure-only 阶段采 ServiceR verbose/journal、配置解析结果、kill counters；把 `startPSIKillAt` 语义列为 B-0 前置门。 |
| L6 受产品版本约束 | TV 不能装包；L6 必须随产品构建签名链，无法像 env tunables 那样快速 A/B。 | 把 L6 从“同轮 TV 快速试点”拆成产品工程分支任务：明确 owner、app hook、签名/OTA/回滚路径、feature flag。 |
| artifact contract 仍不够硬 | PSI/perf 争议无法复盘，尤其是系统级 PSI、启动顺序、场景 marker。 | 每轮目录必须含：run manifest、exact drop-in、identity、unit state、pre/post inventory、per-second meminfo/psi/vmstat、target PID liveness、smaps/maps、journal/dmesg window、scenario markers、SHA256。 |

## Top-3 最可能导致返工的点

1. **主收益面 env 不可达**：协议 Top-5 glibc 面目标全是 `AT_SECURE=1`，而源码确认 tunables 在 AT_SECURE 下直接忽略。即使 launchpad exec 与 env 继承都成立，env lever 仍不会作用于这些目标。
2. **PSI 仍可能不可裁决**：开环修掉自抵消，但 `avg2` 在 30/40/cleanup 不刷新的形态、`total` 与 avg 不一致、zram/swappiness=100、系统级 PSI 稀释和 40% 档 SIG11 都会让 A/B 数据难以归因。
3. **层 2 执行路径未闭环**：pool unit/path、env 继承、restart vs reboot、`/run` drop-in 持久性都未验证；若执行中才发现 pool 不能 restart 或 drop-in 不生效，B-2 会整体返工。

## negative_facts

- `malloc_info()` 仍是进程内 API；v2 的 maps/decorate 替代只能给 arena/heap 归因，不能给 tcache/bin/free-byte 归因。
- TV `.26` 当前原始 maps/smaps 未出现 `[anon: glibc:*]` 标签；`decorate_maps` 需要先注入并验证。
- TV `.26` Top-5 glibc heap targets 在原始 inventory 中均为 `AT_SECURE=1`；`GLIBC_TUNABLES` env 路线对它们按源码无效。
- `parse_smaps.pl` 的 1 MiB 对齐规则是 allocator-owned proxy，不是所有权证明；可用于排序，不能单独用于上线归因。
- cgroup v1 环境没有 per-service PSI；协议 PSI 是 system-wide 指标。
- `/etc` 写探针通过；`/run/systemd/system` 写探针未见证据。
- RPI4/TV 的 release、Build ID、CPU flags、内存/zram/overcommit、dlconf 运行态、UEP 落点不同；任何 MB/%/服务结论不可跨轨。
- TV 不能安装包；GBS/外部 ELF 通过产品签名链上 TV 未验证。
- 40% balloon 档出现非 LMK 的 kernel SIG11 日志，不能被“LMK=0”自动视为安全。

## cannot-verify

- TV `glibc-2.40-1.12` 产品分支/补丁集与 workspace `tizen_base` 的精确源码等价性。
- `glibc.mem.decorate_maps=1` 在 TV 产品镜像上实际是否产出 `[anon: glibc: malloc arena]`。
- `ServiceJ` 的真实 systemd/user-unit/drop-in 路径，以及是否支持无副作用 restart。
- launchpad spawn 链是否保留 `GLIBC_TUNABLES`，是否有 `clearenv` 或 env whitelist。
- `ServiceR` 当前运行时 Memory 档，以及 `[PSI-KILLING] startPSIKillAt=250` 的单位/触发语义。
- TV 场景驱动是否可自动化到足以支撑 n>=20 配对统计和 5% 性能门。
- L6 试点的产品 owner、签名链、feature flag、回滚路径和可部署节奏。
