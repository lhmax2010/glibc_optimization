# 系统级前后对照补测（2026-09-08）

当日续跑最终状态：**STOP_G4_M7_ASSIGNMENT**。G1/G2/G3 共 18 格通过，G4 首格在
M7 的 GDB 赋值处失败，后续两格未执行。第 2、3 段不执行，不切 demo-v12，当前有效
交付仍为 demo-v11。目录/包登记/辅助进程/governor 清理检查通过，但目标内部可能的
FILE*/FD 残留未获排除；不能称现场内部状态完全恢复。完整时间线与边界见 §6。

2026-09-08 续跑追注（执行前）：PM 确认 `<TEST_BOARD_IP>` 当前专供本 glibc 项目，
无其他人在用；PID 26799（pts/0）与 27105（pts/1）为残留登录会话，批准清除。
此裁决闭合 §3 的归属未知项，不覆盖身份/环境及其他健康门。清除前后原文分别留存，
只在 PID、启动 tick、cmdline、TTY 与获批对象一致时发送 TERM；如有出入停止。
沿用原 annotated tag `system-before-after-contract-20260908`，合同与 analyzer 不改字节，
不重新打 tag。下文原停止记录保留；执行器安全测试闭合前不启动任何正式格。

首次执行状态（历史保留）：**STOP_OCCUPANCY_UNRESOLVED**。身份/环境自动检查通过，但两个已有交互会话归属未明，不能排除共享占用；当时实验格执行 **0/21**，未产生新的前后对照测量，第 2、3 段未执行。既有数据、验收带与技术结论不变。续跑占用处置见 §5；完整矩阵与交付门通过前，当前有效交付快照仍为 `demo-v11`。

## 1. 事前合同

本节与 [机器合同](../tools/runners/system_level_before_after_20260908/contract.json)、[派生分析器](../tools/runners/system_level_before_after_20260908/analyze_system_level.py) 同批提交，annotated tag 为 `system-before-after-contract-20260908`。记录推送完成时间，至少间隔 600 s 后才允许任何板连接。结果另行提交；不得按结果改变参数、窗口、汇总口径或追加择优重复。

### 1.1 前置、停止门与占用纪律

地址仅用于路由，报告统一为 `<TEST_BOARD_IP>`；重新核验 `uname -r` 含 `rpi4`、`uname -m` 严格 `armv7l`、BUILD_ID 为 `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`。glibc 必须 `glibc-2.40-1.6.armv7l`，MemTotal 为基线约 8117408 KiB（±1%），root、四核 governor 可写、`/opt/usr` 可写，详见 [基线](board_baseline_llvm_image_20260831.md) 与 [S4 前置](s4_reference_and_retention_trim_20260901.md)。

连通失败、身份/环境门不符、可观察到他人任务或占用状态不明确即停止。不重启 sdb server，不执行 root on，不重启板，不抢占任务。四核初始非 `schedutil`、遗留非空实验目录、其他 alloc/gst/gdb/采样进程、其他已建立 sdb 客户端或可辨识外部测试负载均视为占用/未知，不擅自清理。IP、内核与镜像指纹不是硬件唯一序列号，也不构成独占证明；本轮同板性只支持同一连续会话和未变的观测指纹。

工作目录固定 `/opt/usr/glibc_memopt/system_level_before_after_20260908/`，要求可用空间至少 512 MiB。需要 gdb 时沿用 [B2 官方快照六包与安装/卸载流程](../tools/runners/tizen_native_evidence_b2_20260904/manage_gdb_official_snapshot.sh) 的精确版本和哈希，根分区安装后至少 1.2 GiB；本轮实现不继承其重试次数。只卸载本轮安装的包，已有包不卸载。命令逐条远端 `RC` 与 `DONE/FAIL`，不得信任 sdb 自身 RC；单操作最多一次重试，不因测得数字重跑。

### 1.2 冻结矩阵与顺序

每格三个重复。G1=mixed、G2=medium-only；两臂 trim/none。每个重复保持 [S4 B 冻结参数](s4_reference_and_retention_trim_20260901.md) 不变：

```text
--threads 4 --seed 20260814 --live-set 512 --idle-release 50
--release-order high --touch-full --cycles 2 --cycle-rise 3.4
--cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20 --warmup 0
--profile mixed|medium-only --trim-at valley|none --outdir <cell/xml>
```

G1/G2 顺序：G1 none1/trim1 → G2 none1/trim1 → G1 trim2/none2 → G2 trim2/none2 → G1 none3/trim3 → G2 none3/trim3。每格独立进程，不复用堆状态。

G3 沿用 [gst 冻结定义](gst_trim_cost_20260901.md)：`gst_loop_decode.armv7l small_320x240.mp4 51 20 1 none|trim-at-loop-release control-stdin`；顺序 none1 → trim1 → trim2 → none2 → none3 → trim3。业务比较沿用 2–51 轮 nearest-rank 与 p99 REPORT_ONLY，不将方向当作通过门。

G4 随后依次 r1/r2/r3，每次对同一常驻 enlightenment PID 注入一次 `malloc_trim(0)`；先获取 malloc_info，再采 pre、注入、post。不加 UI 活动、不重启目标；注入起点实际间隔至少 120.000 s，每次另记后续 120 s 静置 faults。G4 没有业务周期、没有 none 臂；不得填造下周期或 none 净效应。

### 1.3 观测实现及影响

原 alloc_bench 没有释放点外部握手；本轮以 [构建脚本](../tools/runners/system_level_before_after_20260908/build_observer.py) 从原源文件生成测量专用副本，只加入栈缓冲区 read/write 握手，不改分配/释放逻辑、线程数、seed、相位时长或 trim 计时区间。PRE 在 valley XML 后、trim 分支前；POST 在 trim 与 posttrim XML 后、valley 等待前；none 臂相同位置。观察引入相位间停顿，必须单列采样窗口，不声称与旧 ELF 逐字节相同或新一次 GBS 重基线。

测量 ELF SHA-256：`a9a93336dbb1f69482bf2ac9a634407d947cd676c35a1e24934b712ab66c9677`。trim/none 共用这一 ELF，运行时开关不改变二进制大小。G3/probe 使用 manifest 中 GBS ELF，媒体使用既有留存件；四个哈希固定在机器合同，推送前后均复核。构建来源与编译器记录在 [build_identity.json](../data/raw/system_level_before_after_20260908/build_identity.json)。

G3 直接复用既有 RELEASE_READY/DONE 握手；观测开销不计入 gst 业务墙钟，也不计入 trim 调用耗时。G4 耗时含 gdb/ptrace，不作为约毫秒级钩子代价。

每点依序取时间戳、proc stat、VmRSS、reclaim_probe 分类、MemAvailable/MemFree/Cached、zram 三项、同 PID memps 原文、proc stat 复核与结束时间戳。这是短窗口顺序采样而非原子快照；记录 PID/starttime 恒定与窗口长度。memps 的 P(DATA)/[heap] 按其标签保留，不假定与 glibc 分类逐值相等。外部 1 s smaps 全程伴随，保留全部内部 JSON/XML/业务周期记录。

### 1.4 派生、汇总与边界

主汇总固定为每个 group/arm **首个释放点**的三个重复中位与极差（max−min）；全部后续周期另表保留。RSS、glibc 堆 PD 下降 = pre−post，百分比以该项 pre 为分母；MemAvailable 变化 = post−pre。none 校正净效应 = 同组/重复号/周期号的 trim 变化−none 变化；错时相位匹配不是同时整机实验，背景活动及观测器内存均可能影响净差。保留负数，不截断、不平滑、不用后续周期补缺失首轮。

内核 `kB` 按 KiB；同时输出 MiB（KiB/1024）和十进制 MB（KiB×1024/1000000），不混用标签。G1/G2 下周期 faults 用下一 rise；G3 用下一 CYCLE_METRIC；最后一轮填 NA。G4 静置 faults 独立标注。

只陈述测试板合成/官方工具负载量级，不等于产品收益。常驻守护的三次探针有状态累积，不作三个独立重启样本；不得由 system MemAvailable 短时涨幅外推整机/产品收益。业务代价依据预先存在的统计规则报告，不能预先保证“无影响”。

### 1.5 健康与清理

逐格 dmesg 增量必须零 OOM/LMK；记录 zram 三项、faults、stability-monitor 前后清单/计数。新可归因本轮 PID/二进制的告警为硬失败；原 S4 A 的 cpu.relative 已知告警登记保留但**不适用于本轮 B-cycle/G3/G4**，不新增注入豁免。他人告警只归档/报告，不删除。任何格不完整、健康门失败或数据自相矛盾即停止所有后续段，归档已完成部分，不刷数。

majflt 零门覆盖前后采样、alloc rise/再激活、gst 第 2–51 轮及下周期、G4 静置窗。gst 首轮冷启动 faults 沿用既有合同只记录，不混入 warm-cycle 硬门；不是事后看到非零才另开豁免。

trap 恢复四核 schedutil 并复核；只停止本轮进程。所有原始件拉回本地 `board_results/system_level_before_after_20260908/` 并逐件 SHA/大小核验，再清除准确归属的工作目录、归档过的我方 livedump 和本轮新增包，逐项复核。不清理未知目录/文件。完整原始件本地留存，可按请求提供。

## 2. 复现

合同与 analyzer 在上述 annotated tag 固定；后续运行遵循同一参数与 10 分钟事前间隔。派生入口：

```sh
python3 -m unittest tools/runners/system_level_before_after_20260908/test_host.py
python3 tools/runners/system_level_before_after_20260908/analyze_system_level.py \
  --raw <verified-local-raw-directory> --output-dir <derived-directory>
```

确定性项沿用 payload 字节；有效性门为页对齐、majflt、zram、OOM/LMK 与告警归因。旧 S4/gst 容差带仅作上下文对照，不为本轮绝对 RSS 或整机内存差预造验收区间，不改原带。新的 before/after 数字必须来自完整矩阵，部分数据不进入 Demo 头条。运行结果、推送时间与实际间隔待执行后追加，不提前填写。

## 3. 实际执行：只读前置门后停止

### 3.1 时间线

| 事件 | 实际值 / 结果 | 证据 |
|---|---|---|
| 合同提交 | `54ee2ba8d2819014f3e5656de023ffaf283b4a4a` | [事前合同](../tools/runners/system_level_before_after_20260908/contract.json) |
| Annotated tag | `system-before-after-contract-20260908`，对象 `0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3` | [时间/停止证据](../data/raw/system_level_before_after_20260908/stop_evidence.json) |
| origin 推送完成确认 | `2026-09-08T04:55:52.140217+00:00` | 同上 |
| 前置检查开始 / 结束（host UTC） | `05:06:11.703742` / `05:06:16.326055` | 同上、[逐命令记录](../data/raw/system_level_before_after_20260908/preflight_commands.json) |
| 推送确认至检查间隔 | `619.572023306 s`，满足至少 `600 s` | 同上；UTC 与 monotonic 双检，不依赖板端时钟 |
| 只读占用追加核查 | 两个 `sh -l` 自 `Sep04` 在 `pts/0`、`pts/1` 等待；归属未明 | [命令](../data/raw/system_level_before_after_20260908/occupancy_followup_commands.json)、[原文摘录](../data/raw/system_level_before_after_20260908/occupancy_excerpt.txt) |
| 最终门 | `STOP_OCCUPANCY_UNRESOLVED` | [判定证据](../data/raw/system_level_before_after_20260908/stop_evidence.json) |

自动检查原输出 `PASS_READONLY_AVAILABILITY` **原样保留，不代表独占使用已获确认**。
人工复核发现它只计 sdb TCP 连接，不能辨识同连接多路复用的逻辑 shell；最终占用判定优先。
没有把“进程 sleeping”或“当前没有高负载”偷换成无人占用，也没有声称已证明另一人正在运行测试。

### 3.2 身份与环境原文

以下逐字取自 [只读原文](../data/raw/system_level_before_after_20260908/preflight_raw.txt)（换行归一化；路由地址按映射编辑）。

```text
6.12.80-arm-rpi4-v7l

RC=0
DONE_UNAME_R

armv7l

RC=0
DONE_UNAME_M

NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l

RC=0
DONE_OS_RELEASE

glibc-2.40-1.6.armv7l

RC=0
DONE_GLIBC
```

同一原文中 MemTotal=`8117408 kB`、UID=`0`、四核均 `schedutil`；`/opt/usr/glibc_memopt` 为 `ABSENT`。
根分区可用 `1789104 KiB`，`/opt/usr` 可用 `115421396 KiB`；memps 存在，gdb 未安装。
这些是前置观察，不是 G1–G4 回收结果；未据空间预算安装任何包。

### 3.3 占用证据与停止理由

[占用原文摘录](../data/raw/system_level_before_after_20260908/occupancy_excerpt.txt) 显示：

| PID | 命令 / 起始日期 | PPID / 状态 | 标准输入输出 | 判定 |
|---|---|---|---|---|
| 26799 | `/bin/sh -l` / `Sep04` | `1` / sleeping，`wchan=wait_woken` | `/dev/pts/0` | 已有交互会话，归属未明，不动 |
| 27105 | `/bin/sh -l` / `Sep04` | `1` / sleeping，`wchan=wait_woken` | `/dev/pts/1` | 已有交互会话，归属未明，不动 |

PPID=1 可能是历史/孤儿会话，但不证明失去交互终端或归属本项目；本轮没有创建这两个 PID。
按 §1.1 事前“占用/未知即停止”门，停止全部后续段。只做了一次只读归属追加核查；未关闭
这些 shell、未断开共享连接、未杀 server、未重启板，也没有为得到可用板结论反复探测。

### 3.4 零实验执行与现场状态

| 项目 | 本轮实际状态 |
|---|---|
| G1 / G2 / G3 / G4 | 全部 `NOT_EXECUTED`，不存在可用于中位/极差的测量样本 |
| 推送二进制/媒体/脚本 | 0；所有准备件仅在 host |
| 安装/卸载包 | 0；gdb 保持未安装 |
| governor 修改 / trim 注入 | 0 / 0；未启动需恢复的执行路径 |
| 新建/删除板上工作目录或临时文件 | 0 / 0；无本轮文件需要清理 |
| dmesg 增量、zram 变化、周期健康门 | 无正式格，`NOT-EVALUATED`，不能填零假装通过 |
| 第 2、3 段 | `NOT_EXECUTED_STOP_GATE`；未更新 Demo 数字，未切 demo-v12 |

只读命令不可避免会产生系统自身的审计/瞬时活动；“零写入”在此特指未显式推送、建文件、
改配置/包或产生实验产物，不声称系统日志位级不变。停止后不再连板补“清理复核”，避免
把无需清理的只读会话扩展为新操作。

## 4. Host 准备件与未闭合项

事前分析器 10 项测试、观测握手 smoke 1 项通过；既有 verify `OVERALL PASS`。独立
预提交核对促使分析器补齐缺失源件/业务墙钟/G4 间隔/负faults拒绝，不将行数齐全等同于
证据完整。以上属于 host 功能测试，不是性能数字。

等待期间的板端控制器草稿从未推送/执行。其失败码保存和限时恢复路径已做静态修正，但
尚有 stability 管道错误传播、G4 fopen/PID 安全门、路径边界及故障注入测试待闭合；故
[两份草稿](../tools/runners/system_level_before_after_20260908/README.md#未执行准备件不可作为可用复现入口)
已加无条件 RC=2 阻断，保留来源，不作为已完成 harness 或 HQ 操作入口。不得直接解除阻断运行。

需要后续明确的是两条已有会话的归属/是否可用的实验时段；本轮不向 PM 临时索取许可继续，
不自行清理、不另换负载或板。本次无人值守任务在此终止，完整汇总见
[晨间汇总](overnight_summary_20260908.md)。

## 5. PM 裁决后续跑：占用处置与执行器闭合

### 5.1 授权与逐项处置

裁决人 PM，日期 2026-09-08；依据为板当前专供本项目、无其他用户，两条登录会话已确认为残留。
这解决的是外部归属信息，未修改 §1 合同或改变任何测量参数。原停止记录与 tag 均保留。

| 核验/动作 | 原文结论 | 证据 |
|---|---|---|
| 新一轮身份/环境门 | PASS；仍为 rpi4 / armv7l / 既定 BUILD_ID，glibc-2.40-1.6.armv7l，MemTotal 8117408 KiB | [检查回执](../data/raw/system_level_before_after_20260908/resume/preflight/verdict.json)、[命令](../data/raw/system_level_before_after_20260908/resume/preflight/commands.json) |
| PID 26799 清除前 | `/bin/sh -l`，start tick 60331272，pts/0，cwd `/root`；启动时间板端原文 `Fri Sep 4 15:25:49 2026` | [完整 PID 快照](../data/raw/system_level_before_after_20260908/resume/occupancy/PID_26799_SNAPSHOT.txt) |
| PID 27105 清除前 | `/bin/sh -l`，start tick 60337550，pts/1，cwd `/root`；启动时间板端原文 `Fri Sep 4 15:26:52 2026` | [完整 PID 快照](../data/raw/system_level_before_after_20260908/resume/occupancy/PID_27105_SNAPSHOT.txt) |
| 清除 | 两者均先 TERM、等待未退出，再复核 start tick/cmdline/TTY 后各一次 KILL；均 `VERIFIED_ABSENT` | [26799 动作](../data/raw/system_level_before_after_20260908/resume/occupancy/CLOSE_26799.txt)、[27105 动作](../data/raw/system_level_before_after_20260908/resume/occupancy/CLOSE_27105.txt)、[二次确认](../data/raw/system_level_before_after_20260908/resume/occupancy_recheck/VERIFY_APPROVED_ABSENT.txt) |
| 清除后占用复核 | 没有其他非系统交互会话；明确排除采集器 PID 14494 及其子孙 14496/14497，不按“相同 PTY”整体排除 | [ps 全行](../data/raw/system_level_before_after_20260908/resume/occupancy_recheck/PS_RECHECK.txt)、[最终重判](../data/raw/system_level_before_after_20260908/resume/occupancy_recheck/closure_corrected.json) |

清理使两条残留会话不可恢复，但未删除其文件；完整快照已归档。首次 parser 只按 `pts/` 搜索，
把采集命令自身误报为占用；一次只读复核后发现 sdb RC 包装还产生嵌套子 shell。最终按已采集
PID/PPID 树离线重判，未再探测或清除新增 PID。两份原 `STOP` parser 回执不覆写，
[修正器与回归测试](../tools/runners/system_level_before_after_20260908/test_session_cleanup.py)明确覆盖此形态。

时间线（host UTC）：续跑身份检查 `05:39:53.769147`–`05:39:58.356788`；清理过程
`05:40:58.091063`–`05:41:14.647555`；只读复核 `05:43:44.843060`–`05:43:45.147751`。
板端 ps 日历原文独立保留，不把板/host 时钟混用。合同原推送完成时间与 tag 对象仍以 §3.1 为准。

### 5.2 执行器安全闭合（host，不是测量数字）

解除旧草稿阻断的必要实现包括：逐段传播快照失败、严格 cell/phase 与父目录 symlink 检查、
PID/starttime 所有权、限时 bench/sampler/gdb 清理、信号退出先恢复 governor、G4 NULL FILE*
与有效 XML/身份复核、末点外部采样覆盖、跨格复用冻结 analyzer 的完整有效性检查。
host 编排区分内外 RC 标志，拉取 tar 与逐件 SHA 均核验，工作目录以本轮 owner token 保护；
仅卸载本轮新增六包，拉取/归属/清理失败均不删除未证实归档完整的工作目录。

对应 [shell 安全测试](../tools/runners/system_level_before_after_20260908/test_executor_safety.py)、
[host 编排测试](../tools/runners/system_level_before_after_20260908/test_executor_host.py)、
[冻结字节测试](../tools/runners/system_level_before_after_20260908/test_stopped_round.py)。
这些不替代板上健康或效果证据；运行一次完整矩阵前，先提交该实现与测试，不重打合同 tag。

## 6. 当日续跑结果：G4 首格停止，不进入 Demo 集成

### 6.1 实际时间线与覆盖

执行器使用已提交的干净快照 `06799668543c014b0552a23720ca7e79304f4346`；安全闭合提交
为 `d0c4247`，随后补入 host 检查原文。合同和冻结 analyzer 与原 tag 的字节均未改变。
以下时间均为 host UTC，来自 [执行回执](../data/raw/system_level_before_after_20260908/execution/execution.json)
和 [逐命令时间线](../data/raw/system_level_before_after_20260908/execution/commands.json)，不与板端日历混算。

| 事件 | UTC / 结果 |
|---|---|
| 原合同推送确认 | 2026-09-08 04:55:52.140217；原 annotated tag 不重打 |
| 续跑执行器启动 | 06:05:53.362393；距原推送 4201.242326624 s，超过事前下限 |
| G1/G2 完成 | 12/12；首格开始与逐格收尾见命令记录 |
| G3 开始 | 06:26:06.042705；按 none1/trim1/trim2/none2/none3/trim3 顺序 |
| G3 最后格拉取 | 08:15:59.047309；随后完成校验，6/6，未重跑任何格 |
| G4 首格 | 08:15:59.773103 启动；首次 M7 命令失败，08:16:02.496803 已进入整轮健康与恢复路径 |
| 终态记录 | 08:16:11.304636；verdict=STOP，已检查范围 cleanup=PASS |

| 合同组 | 完成 / 计划 | 已完成释放点 | 状态 |
|---|---:|---:|---|
| G1 mixed：trim/none ×3 | 6/6 | 12 | 退出码、源件完整性及冻结有效性门通过 |
| G2 medium-only：trim/none ×3 | 6/6 | 12 | 同上 |
| G3 gst：trim/none ×3 | 6/6 | 306 | 同上；冷启动/暖周期口径保持合同原定义 |
| G4 enlightenment | 0/3 | 0 | r1 尝试在 M7 失败；r2/r3 不执行 |

已完成 **330 个释放点**的逐点转录、原件/归档 SHA 与
[逐周期派生 TSV](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)
以 **STOP_INCOMPLETE_MATRIX** 归档，见
[公开输入及覆盖声明](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json)。
这是完整 G1/G2/G3 前缀，不是完整 21 格合同；不补 G4，不生成整轮三重复头条表，
不将部分测量集成进 HTML、叙事、双语 README 或验收带。

### 6.2 G4 失败证据与覆盖缺口

[GDB stderr 原文](../data/raw/system_level_before_after_20260908/execution/raw/G4_trim_r1/gdb_m7.txt.stderr)：

```text
/opt/usr/glibc_memopt/system_level_before_after_20260908/G4_trim_r1/m7.gdb:1: Error in sourced command file:
Left operand of assignment is not an lvalue.
```

[生成命令](../data/raw/system_level_before_after_20260908/execution/raw/G4_trim_r1/m7.gdb)首行为
`set $fp=(void*)fopen(...)`；[控制器原文](../data/raw/system_level_before_after_20260908/execution/CELL_G4_trim_r1.txt)
记录 `FAIL_GDB RC=1` → `FAIL_M7` → `WRAPPER_RC_CELL_G4_trim_r1=1`。
[GDB stdout](../data/raw/system_level_before_after_20260908/execution/raw/G4_trim_r1/gdb_m7.txt)
记录 PID 505 已 detach。未进入后续 malloc_info、显式 fclose、trim 或正式 pre/post 采集。

这是执行器遗漏既有兼容性约束的回归，不是板身份漂移或测得收益不理想：
[旧原生实证 §3.1](tizen_native_evidence_20260904.md#31-workflow-缺陷与数据采用规则)
已记录 ARM `$fp` 帧指针名赋值问题，并改用 `$stream`；
[旧回归测试](../tools/runners/tizen_native_evidence_20260904/test_host.py)也禁止 `set $fp`。
本轮直接观测确定的是第 1 行的 lvalue 错误，与旧问题同型；没有追加板端诊断来重新验证
寄存器实现细节。新 [安全测试](../tools/runners/system_level_before_after_20260908/test_executor_safety.py)
只检查生成文本和 stub GDB 的 NULL/返回码/超时分支，未执行真实 ARM GDB 的赋值语义，
还把 `$fp` 文本当成正控。因此 host 测试通过不能表述为 G4 执行链已验证。

停止后不修改运行器补跑、不改合同、不把失败格移除后宣布整体成功。后续若恢复，须先
处理这一兼容性测试缺口及下节的目标内部状态；原 G4 数据保持缺失，不倒填。

### 6.3 健康、归档和现场恢复边界

| 核验项 | 实际结果 / 限定 | 原文 |
|---|---|---|
| 18 个完成格 | 退出码均 0，逐格 OOM/LMK、新增归属告警均 0，zram 三项前后相同 | [逐格原文选集](../data/raw/system_level_before_after_20260908/execution/manifest.json)、[逐格 health](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json) |
| 整轮健康 | OOM/LMK 0，stability 0→0，新增归属告警 0；zram 三项 Δ=[0,0,0] | [回执](../data/raw/system_level_before_after_20260908/execution/execution.json)、[before](../data/raw/system_level_before_after_20260908/execution/ROUND_BEFORE_ZRAM.txt)、[after](../data/raw/system_level_before_after_20260908/execution/ROUND_AFTER_ZRAM.txt) |
| 原始拉取 | 完成格与失败 G4 原件均拉回；19 个归档及逐文件 SHA 通过；公开字段保留这些清单 | [完成/失败清单](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json) |
| governor | 四核 schedutil | [恢复](../data/raw/system_level_before_after_20260908/execution/RESTORE_GOVERNORS.txt)、[最终复核](../data/raw/system_level_before_after_20260908/execution/FINAL_REVIEW.txt) |
| 我方辅助进程 | 已检查 executable 路径、脚本及记录的 PID/start tick 均无残留；扫描中瞬态 /proc 消失警告保留 | [进程](../data/raw/system_level_before_after_20260908/execution/OWN_PROCESS_ABSENT.txt)、[辅助进程](../data/raw/system_level_before_after_20260908/execution/OWN_HELPER_ABSENT.txt) |
| 工作目录 | 本轮精确目录删除并复核，空父目录一并 rmdir | [清理](../data/raw/system_level_before_after_20260908/execution/WORKDIR_REMOVE.txt) |
| 本轮安装包 | 六包安装后按逆序卸载，rpm 查询均已缺席；卸载命令包含 msm/ldconfig 警告，不能据 RC=0 声称全系统缓存/标签已复核 | [安装](../data/raw/system_level_before_after_20260908/execution/GDB_INSTALL.txt)、[卸载及警告](../data/raw/system_level_before_after_20260908/execution/GDB_REMOVE.txt) |
| 根分区 / opt 分区 | 最终可用 1789104 / 115421376 KiB | [df 原文](../data/raw/system_level_before_after_20260908/execution/FINAL_REVIEW.txt) |
| 守护进程 | GDB 报 detach；最终 ps 仍为 PID 505、Aug28 启动的 enlightenment；未杀/重启该目标 | [最终 ps](../data/raw/system_level_before_after_20260908/execution/FINAL_REVIEW.txt) |

新增六包为 libgmp-4.2.1-1.6、gdbm-1.8.3-1.7、libpython3_141_0-3.14.2-1.6、
python3-base-3.14.2-1.6、python3-3.14.2-1.5、gdb-16.3-1.1（均 armv7l），大小预算、
逐件 SHA 与安装/卸载命令见 [命令记录](../data/raw/system_level_before_after_20260908/execution/commands.json)
及 [预算原文](../data/raw/system_level_before_after_20260908/execution/GDB_SPACE.txt)。

**内部状态不确定项**：`malloc_info_pre.xml` 实际为 0 B，其原件 SHA 是空文件 SHA，
收录在 completed_points.json 的 failed_cell_files。新目录内出现该文件说明首行 fopen
至少发生过文件创建/打开尝试；返回指针未成功保存，后续 fclose 未执行。没有目标 FD
前后清单，不能排除 enlightenment 内 FILE*/FD 残留。detach、unlink 和删除目录都不能
证明目标内部流已关闭。因此回执 cleanup PASS 仅指上表已检查项，不代表目标内部状态
完全恢复；这项不确定性只发生在 G1/G2/G3 完成之后，不反向改写它们的原始值。
停止后未再次 attach、猜测指针关闭流或重启守护进程，留待 PM 裁决恢复方案。
回执 round_health 的 after 快照采于测量停止后、卸包/目录清理前；未另采清理后的
dmesg/zram/stability 快照，不能把该健康记录外推为卸包警告已被独立排除。

### 6.4 停止件复核与下一步

完整原始件位于本地 `board_results/system_level_before_after_20260908/resume/measurement/`，
可按请求提供。公开内容是未舍入的逐点字段、原始日志选集及哈希引用，不冒充全部原件。
原文编辑仅 CR 换行规范化、路由 IP 与 host home 映射；板端路径保留。

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
python3 tools/runners/system_level_before_after_20260908/publish_stopped_measurement.py \
  --run /path/to/verified-stopped-run --output-dir /path/to/new-completed-prefix
python3 tools/runners/system_level_before_after_20260908/publish_execution_log.py \
  --run /path/to/verified-stopped-run --output-dir /path/to/new-log-publication \
  --board-address <TEST_BOARD_IP> --host-home /path/to/host-home
```

这些是 host 归档命令，不是重跑授权；完整矩阵发布器仍拒绝 STOP。
本轮 host 测试 88 项通过、既有 verify OVERALL PASS（提交前显式 dirty override），
相关链接与哈希核验通过，见 [收尾检查](../data/raw/system_level_before_after_20260908/closing_checks.tsv)。
这些检查不覆盖尚未修复的 ARM GDB 赋值语义，不将 host PASS 写成 G4 可用。
G4 必须待执行器兼容性与目标内状态恢复方案明确后再议，不采用当前不完整数据生成
新的三重复 Demo 头条。第 2、3 段均停止，当前有效交付保持 demo-v11。
