# 系统级前后对照补测（2026-09-08）

2026-09-11 host 闭合追注：PM 方向二已落实，合同固定 commit/两文件哈希的严格校验
在 full、无 tag、浅克隆可达对象下通过；板端事前门不变。四个非空目录现按 PM
裁决登记为已知非阻断残留，不清除非我方文件。未再连接板或重跑任何格。
见[修复与交付验收](demo_v12_delivery_20260911.md)；下文各次 STOP 按历史保留。

**2026-09-11 06:39 UTC 最新状态：延期收尾审计完成，21 格验收组合完成。**
四个目录均非空，依 PM 裁决保留为“待查残留”，不构成停止门；镜像目录未动。
一次提权后完成受限处置与核验，root off 首次成功、结束 UID=5001。没有删除目录、
重跑测量或修改合同。当前是“收尾通过、非零残留”，不是“全部残留已清除”。
见 [§12.1](#121-实际处置与收尾结果) 与 [§13](#13-已验收矩阵合成与优化效果)。
后续 Demo host 交付测试命中无 tag 克隆依赖停止门；原始数据组合与 HTML/L1 已保存，
当时不切 demo-v12，demo-v11 保持有效。见[独立阻塞记录](demo_v12_delivery_blocker_20260911.md)
及[两日汇总](twoday_summary_20260910.md)；不影响本次板端收尾已完成的判定。

2026-09-11 05:04 UTC 前次状态（保留）：受限 root 进程/告警核验通过，残留目录处置仍 STOP。
全系统 ps 含 PID 1 与原 enlightenment；root off 首次成功，UID=5001。2570 条包路径已
逐项查完：2565 不存在，5 个 GDB 相关目录存在且无当前 RPM 归属；内容/创建来源/是否空
尚未证明，未删除。包清单无变动、六包未安装、已采健康量无异常；这不是卸包失败或
测量失败。21 格保留，不重跑；第 3–5 段不执行，demo-v11 有效。见 [§11.1](#111-执行结果与原文)。

2026-09-11 03:00 UTC 前次状态（保留）：21 格验收保留、未重跑；单项收尾因非 root 进程列表不完整 STOP。
新方法的完整请求体严格不超过 200 字节；本次 12 条正文 70–106 字节，均有远端标志，
没有再次触发长度错误。但 `ps` RC=0 的列表缺少 PID 1，不能证明占用/残留检查完整。
未提权，结束 UID=5001；第 3–5 段停止，demo-v11 继续有效。见 [§10](#10-2026-09-11-单项收尾进程清单完整性-stop)。

2026-09-11 前次状态（保留）：21 格已由 PM 验收保留，未重跑；只补收尾再次 STOP。
首条分批查询的服务请求为 3474 字节，仍被 SDB 拒绝；不是发现了残留。
本次已核验的身份/包清单/目录/进程/governor 与读前健康快照原文见 [§9](#9-2026-09-11-只补收尾再次停止)。
root-off 首次成功，回到 UID=5001；未继续 Demo 集成或切 demo-v12，demo-v11 有效。
以下旧终态按日期保留，不改写为新结果。

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

## 7. 两日批量续跑（2026-09-09）

### 7.1 授权、历史与不变项

PM 于 2026-09-08 明确板专供项目，并报告已手动重启，旧 FILE*/FD 残留恢复事项由该次
重启闭合。§6 原始失败、不确定性和卸包警告原样保留；新的“现场恢复”判断只依据本次
首次连接后的原文核验，不把 PM 陈述冒充现场观测。执行器无 reboot/poweroff 权限，旧
两个 PID 的清除授权不再使用。裁决人/批准人 PM；见[裁决台账](pm_decisions.md#2026-09-08-两日续跑裁决2026-09-09-落地)。

本次仍对应 `system-before-after-contract-20260908`，tag 对象
`0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3`、合同提交
`54ee2ba8d2819014f3e5656de023ffaf283b4a4a`。contract.json 与 analyze_system_level.py
逐字节不改；G1/G2/G3 的 18 格、330 对采样已验收，禁止重跑。只执行剩余 G4 三格，
重启前 18 格与重启后 G4 分开保存环境/健康/执行回执，不能描述为一次连续运行。

### 7.2 Host 执行器闭合

- 原 `$fp` 回归先由失败测试证实，再改为 GDB Python 变量接收 FILE*，不使用寄存器
  convenience name；NULL 不调用 malloc_info/fclose，非 NULL 在 finally 中仅关闭一次。
  malloc_info、关闭或 detach 失败均拒绝成功；未知 inferior-call 状态仍如实报告，不猜指针。
- M7 与 trim 都在 attach 后、inferior 调用前核对 PID/start tick/comm；shell 保留有界
  debugger 清理、目标不杀死、异常恢复 governor、路径/符号链接门与逐文件完整性门。
- 新[续跑入口](../tools/runners/system_level_before_after_20260908/execute_g4_resume.py)
  只允许 G4_trim_r1/r2/r3，只推 reclaim_probe；连板前重验已发布 18 格回执/归档/原件哈希，
  并要求执行提交已在 origin/main。旧 21 格入口是历史复现代码，不是本次执行命令。
- 新鲜占用检查包含完整 PTY 进程表与 boot_id；任何其他交互会话即停，不清除。
  全轮告警枚举/元数据失败不再落成空表；缺 owner proof 时保留目录但仍尝试恢复 governor。
- rpm 查询故障不得当作“未安装”；卸包前后成功取得的完整清单必须一致。卸包警告和
  包路径残留观察保留；清理后另取 dmesg/zram/stability/boot 核验，不扩大旧回执覆盖范围。

### 7.3 复现与分段门

第 1 段 host 验证：本轮执行器 114 项测试通过，既有 verify OVERALL PASS（提交前显式
`REPRODUCE_ALLOW_DIRTY=1`），相关文档链接 217 项通过；合同/analyzer 与 tag 逐字节一致。
见[紧凑检查回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv)。
这不代替 G4 板上执行和首次重启后卫生门。

以下是本次 G4-only 续跑形式；不得重新运行 G1/G2/G3。完整原始件本地留存，可按请求提供。
先完成 host 测试并推 main，再运行只读门；核验原文后，使用另一个全新 host 输出目录执行：

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
python3 tools/runners/system_level_before_after_20260908/execute_g4_resume.py \
  --preflight-only --ip <TEST_BOARD_IP> --output-dir /path/to/new-readonly-gate \
  --accepted-run /path/to/accepted-18-run \
  --contract-receipt /path/to/contract_push_receipt.json \
  --probe /path/to/reclaim_probe.armv7l --gdb-cache /path/to/official-six-rpm-cache
python3 tools/runners/system_level_before_after_20260908/execute_g4_resume.py \
  --ip <TEST_BOARD_IP> --output-dir /path/to/new-g4-only-run \
  --accepted-run /path/to/accepted-18-run \
  --contract-receipt /path/to/contract_push_receipt.json \
  --probe /path/to/reclaim_probe.armv7l --gdb-cache /path/to/official-six-rpm-cache
```

确定性/有效性项：合同/资产 SHA、原 18 格保留、三格相同目标身份、≥120.000 s 间隔、
零 OOM/LMK/major fault、zram 三项 Δ=0、无新增归属告警、拉取完整与清理复核。
容差/报告项：常驻进程的回收量和含 ptrace 耗时只报告实测，不以历史 272/36 KiB 为通过带；
静置 faults 与业务下周期 faults 分列。任一失败停止所有后续段，不重跑刷数、不切 v12。

### 7.4 本次终态：UID 门 STOP，G4 NOT_EXECUTED

第 1 段修复已推 main：`ff2442ef0b2b8779646a08408fab9bf5bc3e7488`。
随后首次只读门于 2026-09-09 03:09:54.998761 UTC 开始 sdb 客户端检查，
03:09:55.043316 UTC 执行 connect；03:09:58.111178 UTC 以 STOP 结束。
对应原合同推送至本次执行启动间隔 80042.85845797 s，未重打合同 tag。
时间线、精确命令和原文 SHA 见[commands](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/commands.json)、
[execution](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/execution.json)、
[原文清单](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/manifest.json)。

| 门 | 原文结果 | 判定/出处 |
|---|---|---|
| 内核 | `6.12.80-arm-rpi4-v7l` | PASS；[UNAME_R](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/UNAME_R.txt) |
| 架构 | `armv7l` | PASS；[UNAME_M](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/UNAME_M.txt) |
| BUILD_ID | `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l` | PASS；[os-release 全文](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/OS_RELEASE.txt) |
| glibc | `glibc-2.40-1.6.armv7l` | PASS；[GLIBC](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/GLIBC.txt) |
| MemTotal | `8117408 kB` | PASS；[MEMINFO](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/MEMINFO.txt) |
| 当前 UID | `5001` | **STOP**；合同要求 0，禁止 root-on；[UID 原文](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/UID.txt) |

UID 命令的原文如下；`RC=0` 仅指 id 成功返回，不是 UID 硬门通过：

```text
5001

WRAPPER_RC_UID=0
DONE_REMOTE_UID
```

未执行 `sdb root on`、重启、权限替代尝试或再次连接。工作目录/进程/占用/governor/df/
stability/包清单等位于失败门之后，**NOT_EVALUATED**；因此本次不能写“现场已恢复”或
“无其他使用者”。PM 手动重启的事实记录保留，但不能据此填入未采集的 boot_id 或卫生项。

本次推送文件、安装/卸载包、governor 修改、注入和新测量格均为 0；
cleanup=`NO_BOARD_FILES_CREATED`，不是清理动作完成的 PASS。旧卸包警告仍见 §6.3；
本次因未安装包，无新的卸包警告，也未越过 UID 门重新查询包清单。
G4 三格均 **NOT_EXECUTED**，上轮失败尝试仍在 §6 保留。G1/G2/G3 的原 18 格未重跑、
未改写。第 3–5 段全部停止，不改 HTML/README/指南头条，不切 demo-v12，
有效交付仍为 **demo-v11**。周五需 PM 裁决满足 UID=0 后如何恢复 G4，或是否缺 G4 发布；
历史 B/B2 的 272 KiB / 36 KiB 仅作[替代背景证据](tizen_native_evidence_20260904.md)，
不冒充本合同 G4 数据。汇总见[两日记录](twoday_summary_20260910.md)。

原文 `devices.txt` 首行末尾空格按源输出保留，未为消除 whitespace 提示而编辑证据；
清单中的公开 SHA 对应此保留版本。除约定的 CR/IP/host 路径替换外，不改原文。

## 8. PM 方案 A 授权续跑：三格已观测，收尾 STOP

### 8.1 授权、时间与合同

PM 消息裁决日期为 **2026-09-10**；本次工具实录的 host UTC 日期为 **2026-09-09**，
两者分别记录，不把裁决日期或目录名当测量日期。原 §6/§7 的失败及重启前 FILE*/FD
不确定性保留。重启恢复事实由 PM 陈述，当前现场以本节新核验为准。

本轮使用原 annotated tag `system-before-after-contract-20260908`，对象
`0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3`；contract/analyzer 字节不变、未重打 tag。
原推送确认 2026-09-08 04:55:52.140217 UTC；本次入口检查时距其
88230.090509 s，满足原等待门。授权包装层先提交并推至
`cdab1dbf0d24afefe05c4db1039f58ffde6911b9`，再执行任何板端命令。
见[最终执行回执](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/execution.json)、
[命令时间线](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/commands.json)和
[PM 台账](pm_decisions.md#2026-09-10-g4-单轮提权授权方案-a)。

**重启后会话为 UID=5001，经 PM 授权提权至 root。** 授权只用于本轮 G4 和收尾，
不成为默认 harness 行为；未执行 reboot/poweroff、未清除任何旧会话。G1/G2/G3 已验收
18 格未推送、未调度、未重跑，其原回执/归档/逐文件哈希在运行前后均通过原公开证据比对。

| 事件 | host UTC（2026-09-09） | 原文/结果 |
|---|---|---|
| 提权前 id | 05:26:22.665468–22.804532 | UID=5001；[全文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/AUTH_ID_BEFORE.txt) |
| root on / 提权后 id | 05:26:22.805090–22.995012 | UID=0；[root on](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/AUTH_ROOT_ON.txt)、[id 全文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/AUTH_ID_AFTER_ON.txt) |
| G4 r1 | 05:26:50.751240–05:28:56.519708 | 完成、拉回、哈希及原 analyzer 校验通过 |
| G4 r2 | 05:28:57.621373–05:31:03.156525 | 完成、拉回、哈希及原 analyzer 校验通过 |
| G4 r3 | 05:31:04.232256–05:33:09.819405 | 完成、拉回、哈希及原 analyzer 校验通过 |
| 卸包 | 05:33:16.235115–18.438349 | 六包均不存在，警告按裁决不阻断 |
| 残留审计 STOP | 05:33:19.358971–19.409860 | `error: service name too long`，无远端 RC/DONE |
| root off / 最终 id | 05:33:19.411112–19.602955 | 首次成功，UID=5001；[root off](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/AUTH_ROOT_OFF_1.txt)、[id 全文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/AUTH_ID_AFTER_OFF_1.txt) |

板端纳秒时间戳和 host UTC 分开保留；注入间隔只在同一板端时钟内计算，不跨时钟相减。

### 8.2 提权后完整前置门

| 核验项 | 实测/判定 | 原文 |
|---|---|---|
| 内核/架构 | `6.12.80-arm-rpi4-v7l` / `armv7l`，PASS | [uname -r](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/UNAME_R.txt)、[uname -m](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/UNAME_M.txt) |
| BUILD_ID | `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`，PASS | [os-release 全文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/OS_RELEASE.txt) |
| glibc / MemTotal | `glibc-2.40-1.6.armv7l` / `8117408 kB`，PASS | [rpm](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GLIBC.txt)、[meminfo](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/MEMINFO.txt) |
| UID / governor | 0 / 四核均 schedutil 且可写，PASS | [UID](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/UID.txt)、[governor](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GOVERNORS.txt) |
| 工作目录/占用 | 原工作目录不存在；无其他交互会话或匹配负载 | [目录](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/WORKDIR.txt)、[完整 ps](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/POSTREBOOT_SESSIONS.txt)、[进程命令行](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/PROCESSES.txt) |
| 空间 | `/` 可用 1789104 KiB；`/opt/usr` 可用 115421416 KiB；安装预算通过 | [df](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/SPACE.txt)、[安装前预算](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GDB_SPACE.txt) |
| 目标/启动身份 | enlightenment PID=498，start tick=1489；本次三格恒定 | [启动身份](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/TARGET_STAT.txt)、[boot_id](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/POSTREBOOT_BOOT_ID.txt) |
| stability / zram | 告警 0；三项 4096/74/4096 B | [快照](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/raw/round_health/stability_postreboot.tsv)、[mm_stat](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/raw/round_health/zram_postreboot.txt) |

reclaim_probe SHA-256 为 `e71d4aa59dffe9027ec58c2cef88a899facdbf295df82a882a58e611daef4d31`，
推送前/后均与合同相同；[远端复核](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/SHA_reclaim_probe.armv7l.txt)。
六个 GDB RPM 仍为 §6 的固定集合，未改版本/来源；[安装原文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GDB_INSTALL.txt)、
[安装后版本](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GDB_VERIFY.txt)、
[GDB Python 能力](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GDB_PYTHON_CAPABILITY.txt)均通过。

### 8.3 三格已观测数据（STOP 下保留，不是完整轮通过）

来源：[逐格 TSV](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_cycles.tsv)、
[三重复汇总](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_summary.tsv)、
[解析输入/健康/归档与逐文件哈希](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_points.json)。
三份归档共 243 个原始文件逐件校验；完整原始件本地留存，可按请求提供。
本节不生成完整 21 格 Demo 证据，不覆盖旧失败尝试。

| 格 | RSS KiB 前→后 / 下降 | glibc 堆 PD KiB 前→后 / 下降 | memps heap P(DATA) KiB 前→后 | MemAvailable Δ KiB（无 none，非净效应） | 含 ptrace 注入 ms | 静置 min/maj faults |
|---|---|---|---|---|---|---|
| r1 | 11972→11880 / 92 | 3208→3120 / 88 | 3108→3020 | +12524 | 1861.981721 | 1 / 0 |
| r2 | 11884→11884 / 0 | 3124→3124 / 0 | 3024→3024 | -9280 | 1899.209517 | 0 / 0 |
| r3 | 11884→11880 / 4 | 3124→3120 / 4 | 3024→3020 | +8376 | 1963.377091 | 1 / 0 |

RSS 下降三重复中位 4 KiB（0.003906 MiB、0.033659%），极差 92 KiB；堆 PD 下降中位
4 KiB、极差 88 KiB。memps heap 的绝对水平与含其他 glibc arena 的我方分类相差
100 KiB，但两者下降量逐格一致为 88/0/4 KiB；不能把桶水平说成相同。
含 ptrace 耗时中位 1899.209517 ms，不是约 1 ms 的 release-hook 代价。
系统背景变化大且无 none 对照，不归因为守护进程 trim 的整机收益。

注入起点间隔 126.096085980 / 126.617640221 s；三段独立静置窗
120.113473725 / 120.098603391 / 120.113094707 s，全部满足 ≥120.000 s。
采样窗口 major fault 均 0；静置 faults 单列，next-cycle 为 NA。
M7 XML 三份均 parse 成功、非 NULL FILE 关闭成功、调试器 detach 成功；
[r1 XML](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/xml/G4_trim_r1.xml)、
[r2 XML](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/xml/G4_trim_r2.xml)、
[r3 XML](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/xml/G4_trim_r3.xml)，
对应 [r1](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/raw/G4_trim_r1/gdb_m7.txt)、
[r2](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/raw/G4_trim_r2/gdb_m7.txt)、
[r3](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/raw/G4_trim_r3/gdb_m7.txt)原文。

### 8.4 清理完成项与未闭合边界

| 项目 | 状态 | 证据/范围 |
|---|---|---|
| 三格及测量后健康 | PASS | 各格 OOM/LMK=0、可归因新告警=0、zram 三项 Δ=0；测量期 stability 0→0，见最终回执 `round_health`。不外推到卸包后 |
| 四核 governor | PASS | [恢复原文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/RESTORE_GOVERNORS.txt)均 schedutil |
| 我方进程/helper | PASS | [负载](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/OWN_PROCESS_ABSENT.txt)、[helper](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/OWN_HELPER_ABSENT.txt)不存在；未终止 enlightenment |
| 工作目录 | PASS | [删除并核验](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/WORKDIR_REMOVE.txt)，只删除带本轮 owner token 的目录及空父目录；原始件已拉回可恢复 |
| 六包卸载与包清单 | PASS | [卸载原文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/GDB_REMOVE.txt)：六包均 not installed；包清单 1263→1263，added/removed 均空；[卸包后清单](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/PACKAGE_INVENTORY_AFTER.txt) |
| 包文件残留审计 | **FAIL / 未执行** | [原文](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/PACKAGE_RESIDUE_0000.txt)只有 `error: service name too long`。按 200 条路径拼接的首请求为 11800 UTF-8 字节，SDB 请求层拒绝，无远端 RC/DONE；不是发现了残留，也不是 rpm 卸载失败 |
| 卸包后的 dmesg/zram/stability/boot | **NOT_EVALUATED** | 前项异常短路，未运行 `after_cleanup` 快照与 boot 复核；不可用测量前后快照填补 |
| root off | PASS_NONROOT | 一次成功，UID=5001；无降权重试，此后无板端命令 |

卸包警告原文为 `warning: Plugin msm: hook tsm_post failed` 和
`/sbin/ldconfig: Cannot lstat /lib/libpython3.14.so.1.0: Permission denied`。
按 PM 裁决，警告本身不阻断；本次停止项是独立的审计命令长度缺陷与后置健康缺口。
未放宽停止门、未改为短命令重试、未重跑已完成格、未再提权或重启。

因此 **G4 交付项按用户停止门记 NOT_EXECUTED（未完成整轮验收）**；事实层明确保留
“3/3 格观测已完成并逐格校验通过”，不是 0 次执行。最终回执为 STOP/cleanup FAIL。
历史 B/B2 的 [272 KiB / 36 KiB / 8–20 KiB](tizen_native_evidence_20260904.md)
只作常驻/官方负载背景，不填补本次后置健康门。第 3–5 段停止，demo-v11 继续有效，
没有 demo-v12、没有新头条或复审 brief。

### 8.5 复现与下一步限制

harness 为 [G4-only 入口](../tools/runners/system_level_before_after_20260908/execute_g4_resume.py)及
[本轮显式授权包装层](../tools/runners/system_level_before_after_20260908/run_authorized_g4_20260910.py)，
冻结参数仍引用 §1/原 contract。授权已在本次降权收尾，不可当作未来 root-on 默认许可；
当前入口存在本节已记录的残留审计长度缺陷，**不得直接再次运行**。

确定性/有效性检查：同 PID/start tick、XML/JSON parse、归档/逐文件 SHA、每格 RC/DONE、
无 OOM/LMK/可归因新告警、zram Δ=0、静置 major fault=0、间隔 ≥120 s、清理及非 root 复核。
容差/报告项：RSS/堆 PD 实测回收与含 ptrace 耗时不以历史值作为通过带；系统变化保留
符号且 G4 净效应为 NA。当前不是全门通过的复现样本。

host 保留件可用 [publish_g4_observations.py](../tools/runners/system_level_before_after_20260908/publish_g4_observations.py)
重新校验并输出两份原 analyzer 派生 TSV；它只能发布 STOP 下的三格观测，不能发布完整
矩阵头条。[日志发布器](../tools/runners/system_level_before_after_20260908/publish_execution_log.py)
同时要求最终降权回执，原文编辑/逐文件哈希见[manifest](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/manifest.json)。
下一步须 PM 裁决是否仅授权修复短命令分批并补齐收尾核验，**无需且不得重跑已有三格或旧 18 格**。

## 9. 2026-09-11 只补收尾：再次停止

### 9.1 裁决、执行范围与时间线

[PM 2026-09-10 续裁决](pm_decisions.md#2026-09-10-续21-格验收保留只补收尾2026-09-11-落地)
验收保留原 18 格及 G4 三格，禁止任何重跑；仅授权修复请求长度、补只读收尾，
确因读权限不足才提权，最后必须降权。合同 tag 仍为
`system-before-after-contract-20260908`（对象 `0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3`），
合同与 analyzer 字节未改，也未重新打 tag。

执行器先以 [b583821a12314abe21570963418922b409b6024b](https://github.com/lhmax2010/glibc_optimization/commit/b583821a12314abe21570963418922b409b6024b)
推 main，随后在该干净提交执行一次补审计。实际 host 时间 **2026-09-11
02:22:37.086295–02:22:43.678378 UTC**，不是裁决日期；全部命令顺序、字节正文、
host 状态及时间见 [commands.json](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/commands.json)，
最终状态见 [audit.json](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/audit.json)。
本次 0 格测量、0 次注入、0 文件推送、0 包改动、0 governor 写入、0 次进程清除，
未执行 reboot/poweroff。原 21 格数据及原 STOP 回执保持字节不变。

### 9.2 已补齐项与仍未闭合项

| 核验项 | 本次事实 / 判定 | 原文 |
|---|---|---|
| 身份三项 | `6.12.80-arm-rpi4-v7l` / `armv7l` / BUILD_ID 与合同完全相同；提权前后均通过 | [内核](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ROOT_UNAME_R.txt)、[架构](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ROOT_UNAME_M.txt)、[完整镜像身份](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ROOT_OS_RELEASE.txt) |
| 环境 | `glibc-2.40-1.6.armv7l`、MemTotal 8117408 KiB，不变 | [glibc](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ROOT_GLIBC.txt)、[meminfo](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ROOT_MEMINFO.txt) |
| 本次提权必要性 | UID=5001 时 livedump 目录 `Permission denied`，读权限确实不足；按本轮方案 A 提权，id=0 | [提权前 id 全文](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/ID_BEFORE.txt)、[权限拒绝](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/READ_ACCESS.txt)、[root on](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/AUTH_ROOT_ON.txt)、[提权后 id](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/AUTH_ID_AFTER_ON.txt) |
| 启动与目标连续性 | boot ID 与原 G4 相同；enlightenment PID=498、start tick=1489，未重启 | [boot](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/BOOT_ID.txt)、[目标 stat](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/TARGET_STAT.txt) |
| 占用/残留进程 | 未检出额外交互会话及匹配 alloc/gst/gdb/采样负载；未终止任何进程 | [完整会话](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/SESSIONS.txt)、[进程名称与命令行](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/PROCESS_NAMES.txt)、[TCP](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/TCP.txt) |
| governor / 工作目录 | 四核 schedutil；本轮工作目录及 `/opt/usr/glibc_memopt` 不存在 | [governor](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/GOVERNORS.txt)、[目录独立 RC/DONE](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/WORKDIR.txt) |
| 空间 | `/` 1789104 KiB、`/opt/usr` 115421416 KiB 可用 | [df](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/SPACE.txt) |
| 卸包后清单 | 原/current 均 1263 包，added/removed 均空；六个 GDB/依赖均未安装；本次无新增包 | [全清单](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/PACKAGE_INVENTORY_CURRENT.txt)、[六包逐项查询](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/PACKAGES_ABSENT.txt)、[汇总回执](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/audit.json) |
| 已采到的卸包后健康快照 | audit_start：zram 三项 4096/74/4096 B，与原 G4 相同；告警 0。停止后仅在 host 复核：dmesg 仍含原前缀，增量 29 行，OOM/LMK 零命中。**仅此时点，不是完整审计后健康通过** | [zram](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/raw/round_health/zram_audit_start.txt)、[告警快照](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/raw/round_health/stability_audit_start.tsv)、[dmesg](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/raw/round_health/dmesg_audit_start.txt) |
| 包文件残留清单 | **FAIL / 未执行**：首批请求仍过长，没有 RC/DONE；后面 52 批未发出，无残留/归属清单可供判定 | [失败原文](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/PACKAGE_RESIDUE_0000.txt) |
| audit_end 健康 / 最终 boot | **NOT_EVALUATED**：停止门短路，不能由 audit_start 填充 | [终态与命令顺序](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/audit.json) |
| root off / 非 root 复核 | 首次 root-off 成功，UID=5001；没有重试，此后没有板端命令 | [root off](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/AUTH_ROOT_OFF_1.txt)、[最终 id 全文](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/AUTH_ID_AFTER_OFF_1.txt) |

我方残留处置清单：**无已确认待清除项**；已查的目录/进程不存在，包文件清单尚未执行，
不能说“全部无残留”。非我方观察：当前包清单无新增/删除；没有删除任何归属未知文件。
旧卸包警告仍按 §8.4/PM 裁决只记录，不是本次阻断原因。此次无需且未安装/卸载 gdb。

### 9.3 长度修复为何仍未闭合

实现已把原按 200 路径分批改为 **UTF-8 服务请求字节分批**：3500 字节本地预算包含
`shell:` 与独立 RC/DONE 包装；旧 11800 字节正文可完整分为 53 批，最大 3498 字节。
这些是本地构造/测试事实，**不能证明板端可接受这一预算**。

实发首批 `PACKAGE_RESIDUE_0000` 正文 **3468 字节**、含 `shell:` **3474 字节**，
host RC=1，原文只有：

```text
error: service name too long
```

没有远端 RC/DONE，查询没有成功执行。此前本次最长成功请求为
`ROOT_READ_ACCESS`：含 `shell:` **1116 字节**。这两个点不定位精确协议上限；
本轮选择 3500 的保守预算假设被实际客户端结果否定，**不把 167 项 host 测试通过
写成长度问题已解决**。发送层本地超长拒绝与分批无遗漏测试有效，但缺少对真实客户端
长度边界的保证。停止后未改预算、未追加探测、未重连或重试，更没有重跑任何测量。

下一步需 PM 再授权仅补收尾，可选逐路径短请求或已批准范围内的只读脚本方案；
不得重跑 21 格，不以缺失的残留清单/审计后快照作通过推断。当前入口只作为失败记录，
**不得直接再次执行**。这是执行器传输缺口，不是新测量偏差、包卸载失败或健康事件。

### 9.4 归档、复核与交付状态

[原文发布清单](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/manifest.json)
包含 39 个文件的原始/公开 SHA；仅删除 CR、按既有映射处理测试板地址与 host home，
板端运行路径保留。完整原始件本地留存，可按请求提供。
[发布器](../tools/runners/system_level_before_after_20260908/publish_cleanup_audit.py)
校验终态及降权完成，原始文件未改写。host 检查见
[检查记录](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/host_checks.tsv)。

“复现”在此仅指 **host 重放/故障回归**：

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py' -v
bash tools/reproduce/reproduce.sh verify
```

前者 167 项 PASS；后者 OVERALL PASS（提交前显式 dirty override，未跳过测试）。
确定性/有效性门为命令字节预算、远端标志、原文哈希与 root-off；容差项无新增，
沿用 §1 且不执行新格。host 通过不能闭合本节板端 STOP。

发布停止结果 `7f2d4e1f89f110dad1c3cf463480f4a59915537f` 后，从 GitHub 远端干净克隆
main 再验：167 项 runner 测试、默认 verify OVERALL PASS、356 个关联链接均通过。
未启用 dirty/test-skip/expected-SHA override；main 身份为 REPORT_ONLY，并非新交付快照
的 required 矩阵。原 ps 输出行尾空格原样保留，不以格式清理改变日志哈希。

**整轮仍 STOP，21 格数据已验收保留但收尾未闭合；第 3–5 段停止。**
未集成新头条、未生成 v12 brief、未运行 v12 交付矩阵或创建 demo-v12。
当前有效快照 **demo-v11**：commit `0e8a2f731b13690009badf1ca2acbd57018e7bc8`，
annotated tag 对象 `f1266c0be6c225a2ceb962836380c656758f9427`。

## 10. 2026-09-11 单项收尾：进程清单完整性 STOP

### 10.1 授权、方法与时间线

PM 裁决日期为 2026-09-10；执行日以原始 UTC 为准。裁决要求一项检查一条请求、
完整请求体超过 200 UTF-8 字节本地拒绝，禁止继续拼批次或试探长度；先完成 UID=5001
只读全扫，权限拒绝项单列后才能按方案 A 做一次受限 root round。21 格永久保留，不重跑。
详见[裁决台账](pm_decisions.md#2026-09-10-再续单项请求200-字节硬限2026-09-11-落地)。

[执行器](../tools/runners/system_level_before_after_20260908/audit_single_cleanup_20260911.py)
及 [200 字节硬闸](../tools/runners/system_level_before_after_20260908/single_request.py)
先以 `9f839b25e5b07fdbd489043050dd59969bd0497e` 推 main。执行前 192 项 host 测试、
默认 verify 均通过；这不代表板端读权限或全清单完整性已证明。合同 tag
`system-before-after-contract-20260908` 与 analyzer 原字节未变。

| UTC | 事项 | 结果与原文 |
|---|---|---|
| 03:00:51.873671 | 入口开始；检查干净、已推快照、原 G4 来源与冻结合同 | [audit.json](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/audit.json) |
| 03:00:53.074443–53.082014 | sdb version / connect 各一次 | [版本](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/SDB_VERSION.txt)、[连接](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/CONNECT.txt) |
| 03:00:53.082290–53.911018 | id、三重身份门、glibc、MemTotal，各一请求 | UID=5001、rpi4/armv7l/BUILD_ID 及环境均符合 |
| 03:00:53.911541–54.641636 | boot、ps、dmesg、zram、livedump 列举，各一请求 | ps 清单不完整；livedump 权限拒绝；其余本时点原文已留存 |
| 03:00:54.642842–54.783703 | 停止后的最后一条 id；入口结束 | UID=5001；未提权、未重试，此后无板端命令 |

以上时间均来自[逐请求命令记录](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/commands.json)。
共 14 个客户端调用，其中 12 个 shell 请求；每条一件检查，RC/DONE/FAIL 为必要记账，
不是拼接第二项检查。正文最短 70、最长 106 字节；全部远端标志完整，11 条 RC=0、
1 条 RC=2/FAIL（目录权限拒绝）。这些只是实发命令长度，不是对协议上限的探测。

### 10.2 核验表、权限清单与观察

| 核验项 | 本次状态 | 原文 / 边界 |
|---|---|---|
| UID 起止 | 5001→5001；无 root on/off | [起始 id](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_ID_BEFORE.txt)、[最终 id](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_ID_FINAL.txt) |
| 三重身份门 | PASS | [uname -r](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_UNAME_R.txt)、[uname -m](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_UNAME_M.txt)、[完整 os-release](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_OS_RELEASE.txt) |
| 环境未漂移 | glibc-2.40-1.6.armv7l、MemTotal 8117408 KiB | [glibc](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_GLIBC.txt)、[meminfo](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_MEMINFO.txt) |
| boot | 与原 G4 一致 | [boot](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_BOOT_START.txt)；不能替代目标 PID/start tick 核验 |
| 进程 / 占用 | **STOP / 完整性不成立** | [ps 原文](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_PS_START.txt)：148 行、RC=0，但缺 PID 1 和原目标 PID 498；不能判无人占用，也不能判目标已消失或重启 |
| dmesg / zram 开始快照 | 原 dmesg 前缀保留；增量 39 行、OOM/LMK 零命中；zram 三项 Δ=0 | [dmesg](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_DMESG_START.txt)、[zram](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_ZRAM_START.txt)、[host 重放](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/host_replay.json)；只有开始时点，不是全审计后健康 PASS |
| stability-monitor / livedump | **不可读，未取得计数** | [目录原文](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/NONROOT_ALERTS_START.txt)：`Permission denied`，RC=2/FAIL；不是计数为零 |
| 工作/顶层残留、2570 包路径、完整包清单/六包、governor、df、结束健康 | **NOT_EVALUATED** | 非 root 全扫未完成即停止；不复制 §9 旧结果充作本次检查 |

截至停止点的权限拒绝清单只有 `ALERTS_START`：

```text
ls: cannot access /opt/usr/share/crash/livedump: Permission denied

RC=2
FAIL
```

原始 [audit.json](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/audit.json)
已保存此项；尚未形成全扫后的完整 `permission_denied.json`，所以没有发起 root round。
回执初始枚举 `root_elevation=NOT_NEEDED` 仅表示本次没有尝试提权，**不表示已证明
所有项目无需 root**；本次确有目录权限拒绝。非 root `ps` 的 RC=0 未被误当作全进程可见。

我方残留处置清单：无已确认对象、无删除、无进程清除；**不是全部无残留**。
非我方观察：可见列表中有 `login -- root` 与 `ttyS0 -bash`；没有归属依据，未清除。
列表中的 pts/0 shell 与 ps 是本次采集命令自身，不能充作外部交互占用证据。
没有新取 target stat 或挂载/访问策略，无法确诊静默缺行原因；可能与非 root 可见性
有关，但这是待验证假说，不认定为 SMACK/hidepid 或进程消失。

### 10.3 Host 复算、停止处置与待裁

16 个原文/回执文件按[发布清单](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/manifest.json)
保存编辑前后 SHA，原始件保持不变；仅按既有映射编辑路由地址、host home 和 CR。
完整原始件本地留存，可按请求提供。复算不连接板：

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_single_cleanup_stop.py \
  data/raw/system_level_before_after_20260908/cleanup_single_20260911
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
bash tools/reproduce/reproduce.sh verify
```

首条完整输出见 [host_replay.json](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/host_replay.json)：
校验原文哈希、全部请求 ≤200、远端标志、ps 完整性拒绝及仅已采时点的健康。
新增真实 RC=0/缺 PID 1 的 host 回归，**不修改停止判定、不增加板端重试**。
本轮确定性/有效性检查是原文与字节硬限、RC 和可见性证明；无新容差项，无新测量数字。

停止后 193 项 runner 测试通过，默认 verify `OVERALL PASS`（提交前显式 dirty override，
未跳过测试）；391 个关联链接通过，脱敏扫描零命中。检查详情见
[host_checks.tsv](../data/raw/system_level_before_after_20260908/cleanup_single_20260911/host_checks.tsv)。
这些是 host 检查，不是板端收尾或 demo-v12 交付矩阵通过。

停止结果以 `204bf4f8e93421e6f34809aafb124137f8aee7d1` 推 main 后，从 GitHub 远端
普通克隆 main 再验：193 项 runner 测试、默认 verify `OVERALL PASS`、391 个关联链接、
host_replay 逐字节 cmp 与脱敏扫描均通过，克隆前后工作树干净。未设置 dirty、test-skip
或 expected-SHA override；main 交付身份为正确的 REPORT_ONLY，仍不是 demo-v12 矩阵。

待 PM 裁决：是否允许把“RC=0 但已证明列表不完整”的进程检查单列为需要 root 的项目，
以及如何完成剩余非 root 单项扫描后再做清单内 root 核验。本次未把它自行转成权限豁免，
未改完整性门或在停止后继续试命令。200 字节/单项规则与 21 格不重跑均继续有效。

**整轮仍 STOP，第 3–5 段不执行**：无新 Demo 头条、无 v12 brief、无交付矩阵或 demo-v12。
当前有效 **demo-v11**：commit `0e8a2f731b13690009badf1ca2acbd57018e7bc8`，annotated tag
对象 `f1266c0be6c225a2ceb962836380c656758f9427`。旧 18 格与 G4 三格完全保留。

## 11. 2026-09-11 受限 root 续审（执行前登记）

PM 于 2026-09-10 续裁批准：将 §10 中 RC=0 但缺 PID 1 的进程检查纳入受限
root 清单；板已专供本项目，非我方进程只报告、不清除，也不因此停止。此裁决
闭合的是权限范围问题，不预先声明收尾通过。§10 STOP 原文与原始回执保持不变。

本次使用[独立续审入口](../tools/runners/system_level_before_after_20260908/audit_restricted_resume_20260911.py)，
先校验 §10 原文清单哈希，复用已通过的三重身份、glibc、MemTotal、开始 boot/dmesg/zram
共八项证据，**不再次发送这些检查**。先以 UID=5001 完成此前未执行的非 root 单项扫描。
已有证据不完整的 ps、同视图不可见的原目标 stat，以及已证实不可读的 livedump 目录
直接登记；新遇到的权限拒绝逐项加入清单。结束 boot/dmesg/zram 是续审结束的新时点，
用于桥接 G4 原始执行，不冒充测量当时快照。清单写入本地后才执行一次授权 root round。

root 内只执行登记项与其精确归属/归档/复核子项。进程门须 UID=0、`ps -e` 全系统选择、
PID 1/init 与原 enlightenment PID/start tick 相符；这证明本次操作层面的完整视图，
不外推底层访问控制原因。非我方会话或负载原样报告；仅当已验收 G4 helper 的 PID、
start tick、解释器及工作目录内精确脚本 argv 同时吻合，才归档元数据、再次核对身份、
TERM 并验证消失。PID 复用不归我方。可归因新告警仍是健康停止门，不作豁免。

每条只有一个操作，完整请求体（含 RC/DONE/FAIL）≤200 UTF-8 字节；超限本地拒绝，
不发送、不试探。finally 执行 root off 并复核 UID=5001，失败至多一次重试。
没有测量、文件推送、包变更、governor 写入、reboot/poweroff；原合同、analyzer 和
21 格数据不改。执行器与故障测试先提交并推 main，再连板；结果另行追加。

复现本次 host 安全检查（不连接板）：

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
```

本节为获批方法登记，不是新测量合同；没有新的确定性 payload 或容差指标。
验收仍为原文/远端状态/请求字节硬限、受限 root 范围、残留归属与健康核验。

### 11.1 执行结果与原文

执行器以 `418181e8b3766343e434fe04d86117a371faf6a9` 先推 main；执行前 209 项 runner
测试、默认 verify 通过。实际执行 **2026-09-11 04:58:37.178265–05:04:40.881497 UTC**，
共 363.703232 s（审计耗时，不进入 Demo 代价数字）。
[终态回执](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/audit.json)
保持 **STOP**，失败原文为：

```text
unowned/unknown residue; metadata archived, not removed: /usr/share/gdb
```

2614 个 SDB 客户端调用中有 2610 个 shell 请求，完整正文 70–189 UTF-8 字节，全部
有匹配 RC/DONE/FAIL。32 条 RC=0；2578 条 RC=1 分别为 2565 个路径不存在、5 次目录无
RPM 归属、6 包未安装、2 个工作目录不存在，不能把这些预期查询状态当作卸包失败。
来源为[commands.json](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/commands.json)
及[独立 host 重放](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/host_replay.json)。

| 核验项 | 结果 | 原文 / 范围 |
|---|---|---|
| 旧证据复用 | 八项成功记录校验哈希后复用；没有重发 | [回执 reused_nonroot_checks](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/audit.json)，出处仍为 §10 |
| root round | 5001 → 0 → 5001；root off 一次成功，无重试 | [提权前](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_ID_BEFORE_ROOT.txt)、[提权后](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_ID_ROOT.txt)、[降权后](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_ID_OFF_1.txt) |
| 受限清单 | 只有 PS_START、ALERTS_START、TARGET_STAT、PS_END、ALERTS_END；没有新增非 root 权限拒绝 | [提权前落盘清单](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/permission_denied.json)；其余 root shell 仅身份记账 |
| 全系统进程 | 两份均 204 行、包含 PID 1/init 与 enlightenment PID 498；没有匹配的我方残留负载/helper | [开始 ps](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_PS_START.txt)、[结束 ps](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_PS_END.txt) |
| 原目标与 boot | PID 498/start tick 1489 不变；boot 与原 G4 相同 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_TARGET_STAT.txt)、[boot](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_BOOT_END.txt) |
| stability-monitor | 两次目录计数 0→0，无归档/删除对象 | [开始](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_ALERTS_START.txt)、[结束](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/ROOT_ALERTS_END.txt) |
| 卸包后健康 | 结束 dmesg 仍含原 G4 前缀，增量 39 行，无 OOM/LMK；zram 三项 Δ=0 | [dmesg](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_DMESG_END.txt)、[zram](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_ZRAM_END.txt)；采于非 root 扫描结束、root-off 之前，不外推未采时点 |
| 包清单 / 六包 | 1263→1263、added/removed 均空；gdb/libgmp/gdbm/libpython3_141_0/python3-base/python3 均 not installed | [完整清单](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PACKAGES.txt)、[六包复算](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/host_replay.json) |
| 工作目录 | 本轮工作目录及父目录均不存在 | [WORK](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_WORK.txt)、[WORK_PARENT](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_WORK_PARENT.txt) |
| governor | 四核均 schedutil；本次无写入 | [核 0](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_GOV_0.txt)、[核 1](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_GOV_1.txt)、[核 2](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_GOV_2.txt)、[核 3](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_GOV_3.txt) |
| df 可用 | 根 1789104 KiB，/opt/usr 115421416 KiB | [根](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_DF_ROOT.txt)、[/opt/usr](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_DF_OPTUSR.txt) |

### 11.2 残留清单、归属边界与停止处置

2570 条原包路径均执行一次 stat；只有下列五项现存，逐项另做 rpm -qf。执行器在首个
无 RPM 归属项终止判定；**五项原文在停止前均已采到**，此处全表为离线整理，不是
停止后又连板。每项类型为 directory、stat 大小 4096、UID:GID=0:0；目录大小不是
所含文件字节数，不能据此认定空目录或总残留体积。

| 路径 | mtime UTC（原始 epoch 换算） | 当前 RPM 归属 / 处置 | 原文 |
|---|---|---|---|
| /usr/share/gdb | 2026-09-09 05:33:43 | 无；未删除 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2477.txt)、[owner](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2477_OWNER.txt) |
| /usr/share/gdb/python | 2026-08-14 07:46:09 | 无；未删除 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2478.txt)、[owner](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2478_OWNER.txt) |
| /usr/share/gdb/python/gdb | 2026-09-09 05:33:43 | 无；未删除 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2479.txt)、[owner](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2479_OWNER.txt) |
| /usr/share/gdb/python/gdb/command | 2026-09-09 05:33:43 | 无；未删除 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2483.txt)、[owner](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2483_OWNER.txt) |
| /usr/share/gdb/python/gdb/function | 2026-09-09 05:33:43 | 无；未删除 | [stat](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2519.txt)、[owner](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/NONROOT_PATH_2519_OWNER.txt) |

这些路径列在原 GDB 包文件表中，四项 mtime 接近卸包时段，但这只是关联，不足以证明
现存内容全由本轮创建。另有一项 mtime 为镜像日期；mtime 本身不能证明创建者或内容。
本次未列举这五个目录的子项，不能把它们定性成可直接删除的我方文件，也不能称其
一定是 Python 缓存。未用递归删除，未补发命令探查内容，未开始第二次 root round。

已确认我方残留处置：无进程/告警/工作目录删除对象；以上五个**未完成归属的包路径目录**
单列，不混同为“无残留”。非我方进程观察：PID 667/tty7 `/bin/bash`、PID 1096/ttyS0
`-bash`，按 PM 本次裁决只报告，未清除、未据此停止。

§8.4 的卸包警告仍依原裁决不构成阻断；六包已卸载且无新增包的条件此次再次证明。
**本次 STOP 是执行器的未知残留归属门，不是卸包警告升级为失败，也不是健康门失败。**
受限清单已执行完、root-off 也已闭合，但残留内容/归属/处置仍未闭合，不能将整轮
改为完成。需 PM 决定是否将这五目录按卸包残留观察接受，或另行授权其逐项内容/归属
核验与可证明我方条目的归档清理。未自行扩大 root 清单或放宽此门。

### 11.3 Host 重放与交付状态

2619 个原文/命令/终态文件转录入[发布清单](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/manifest.json)，
编辑前后 SHA 同存；使用 CR、路由地址、host home 编辑，另将原始 TCP 表及回执内可还原
IP 的小端十六进制端点同步映射为 `<TEST_BOARD_IP>` / `<HOST_IP>`，保留端口/状态；
该编辑逐文件记录在 manifest，板端路径原样保留，本地原始件不改。
完整原始件本地留存，可按请求提供。以下只在 host 读取公开证据：

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_restricted_cleanup.py \
  data/raw/system_level_before_after_20260908/cleanup_restricted_20260911
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
bash tools/reproduce/reproduce.sh verify
```

第一条输出与[host_replay.json](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/host_replay.json)
逐字节相同：重查哈希、全部正文硬限、受限 root 操作、UID、204 行全系统视图、原目标、
健康前缀、包清单及 2570 个路径，明确输出 `STOP_NOT_CLEANUP_PASS`，不篡改旧 STOP。
原合同/analyzer、已验收 18+3 格均未变；本次没有测量、文件推送、包变更、governor
写入、文件删除、进程终止或重启。root-off 后不再调用板端。

停止后 host 验证：216 项 runner 测试通过；默认 verify `OVERALL PASS`（提交前显式
`REPRODUCE_ALLOW_DIRTY=1`，未跳过测试）；442 个相关链接通过；原文哈希/复算输出逐字节
核验通过；含 TCP 十六进制端点的脱敏扫描零命中。详见
[host_checks.tsv](../data/raw/system_level_before_after_20260908/cleanup_restricted_20260911/host_checks.tsv)。
这些检查验证归档和工具，不将目录处置 STOP 改成 PASS，也不是 v12 交付矩阵。

推库后干净克隆发现并修复一项归档漏收：原 G4 manifest 中的三份 `controller.log`
此前受全局 `*.log` 忽略规则影响，只在本地存在，导致新重放在克隆里缺文件。三份各
851 字节，均与原 manifest 的 public SHA 完全相同；本次只补收既有字节，不修改原
manifest、回执、XML、测量值或合同，也不连接板。新增“manifest 所列文件必须被 Git
追踪”回归。该问题是 host 公开件完整性问题，独立于五目录的板端 STOP。
该克隆的默认 verify 仍 `OVERALL PASS`；缺文件由另行执行的本轮 runner 全量测试发现，
不能只拿既有 Demo verify 代替本轮新证据测试。

漏件修复已以 `03d32a5d7445bef3a799be04d8267ca7af3a82a6` 推 main。GitHub 远端普通 main
克隆保持干净，ff 同步该提交后复验：217 项 runner 测试通过、host_replay 逐字节 cmp
静默、443 个相关链接通过、脱敏零命中；默认 verify `OVERALL PASS`，没有 dirty/
test-skip/expected-SHA override。初次漏件失败仍保留记录，不掩写为一次成功。
这仅闭合公开归档自包含问题；五目录处置 STOP 和 demo-v11 状态不变。

**第 3–5 段 NOT_EXECUTED_STOP_GATE**：无新 Demo 头条、无 v12 brief、未运行 v12
交付矩阵、不切 demo-v12。当前有效交付继续为 **demo-v11**，commit
`0e8a2f731b13690009badf1ca2acbd57018e7bc8`，annotated tag 对象
`f1266c0be6c225a2ceb962836380c656758f9427`。

## 12. 2026-09-11 PM 五目录裁决与限定处置（执行前登记）

裁决人 PM，日期 2026-09-11，依据为 §11.2 的原始目录时间戳和镜像/安装时间线：
`/usr/share/gdb/python` 定为镜像自带，不动；其余四目录定为我方卸包后的目录残留。
此为 PM 归属裁决，不把时间戳相关性改称内容级来源证明；§11 的原 STOP 保留。
原合同及 annotated tag `system-before-after-contract-20260908` 不变，已验收 21 格
全部保留，绝不重跑。处置结果另记，不改写旧 G4 执行回执。

执行入口为 [dispose_gdb_dirs_20260911.py](../tools/runners/system_level_before_after_20260908/dispose_gdb_dirs_20260911.py)：
先重新核验身份/环境，逐项 `stat` 与 `ls -A`（包含隐藏项）存 host 原文。
一次显式方案 A root round：记录 UID=5001 → UID=0；只执行四目录处置及所列收尾检查；
finally 降权并核验 UID=5001，root-off 至多重试一次。无需任何板端临时文件。

仅在重新核验目录及祖先为原 inode 的真实目录、且列举为空后，用非递归 `rmdir`
按 function → command → python/gdb → /usr/share/gdb 顺序处理，每删一个立即核验不存在。
镜像 python 必须保留；其父 gdb 若仍包含 python，一并保留。非空目录（含隐藏项，或
检查后出现子项而内核拒绝 rmdir）登记 `REPORT_ONLY_PENDING_NONEMPTY`，不删、不重试
删除，继续后续检查。符号链接、身份变化、异常远端返回等仍停止，不扩展清理名单。
祖先/目标身份核验是分条、非原子的检查，不声称抵御恶意并发替换；非递归 rmdir
由内核拒绝删除非空目录，确保不会递归清除其内容。

每条检查单独一条请求，完整 RC/DONE/FAIL 正文不超过 200 UTF-8 字节；本地硬拒绝
超限，不试探长度。收尾检查为目录、包含 PID 1 的 root 全系统进程、governor、完整
包清单/原六包缺席、stability-monitor、dmesg 增量、zram 与 df。非我方进程仅报告。
本次不带入历史进程 TERM 或文件 rm 通道；如发现需额外处置的我方对象，归档后停止。
禁止 reboot/poweroff、测量、推送文件、安装卸载包或 governor 写入。

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
python3 tools/runners/system_level_before_after_20260908/dispose_gdb_dirs_20260911.py \
  --ip '<TEST_BOARD_IP>' \
  --output-dir board_results/system_level_before_after_20260908/directory_disposition_20260911 \
  --pm-authorization PM-GDB-DIRECTORIES-20260911
```

执行器要求自身为已推 main 的干净提交后才可连接板。确定性验收：一操作一请求、
完整请求 ≤200 字节、远端证明匹配、非 root 复原；健康/有效性门沿用原 G4；本次只做
目录处置，不新增性能容差或测量值。非空项按本次 PM 裁决单列，不视为性能/健康失败。

### 12.1 实际处置与收尾结果

执行器 `c89c9abd1add883fd35850e805e9d4a7248b2eee` 先推 main；232 项本轮 host 测试
及默认 verify 通过后执行。实际窗口为 2026-09-11 06:39:24.953366–06:39:42.378125 UTC。
原文/逐文件编辑前后 SHA 见[manifest](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/manifest.json)，
时序见[commands](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/commands.json)。

| 目录 | ls -A 原文（含隐藏项） | 处置 / 原文 |
|---|---|---|
| /usr/share/gdb/python/gdb/function | `__pycache__` | 非空保留待查；[原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_CHECK_LIST_0.txt) |
| /usr/share/gdb/python/gdb/command | `__pycache__` | 非空保留待查；[原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_CHECK_LIST_1.txt) |
| /usr/share/gdb/python/gdb | `__pycache__  command  function` | 非空保留待查；[原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_CHECK_LIST_2.txt) |
| /usr/share/gdb | `auto-load  python` | 非空保留待查；[原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_CHECK_LIST_3.txt) |
| /usr/share/gdb/python | `gdb` | 镜像目录保留；[结束原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_LIST_4.txt) |

清单为板端终端多列输出，未把一行误当一个文件名/目录项计数；未进入非空子目录查文件。
**没有发送 rmdir/rm/kill，零删除，无需恢复文件；四个非空项按最新裁决 REPORT_ONLY，
不构成停止门。** 目录设备号/inode/权限前后一致；不能称“残留全清”或“零残留”。

| 收尾项 | 核验 | 原文 |
|---|---|---|
| root round | 5001→0→5001，一次 root-off 成功；最后动作是降权后 id | [前](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/NONROOT_ID_BEFORE_ROOT.txt)、[root](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_ID_ROOT.txt)、[off](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_ID_OFF_1.txt) |
| 全系统视图 | 两份均 207 行、含 PID 1；enlightenment 498/start tick 1489 和 boot 未变，无匹配测试残留 | [ps](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_PS.txt)、[目标](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_TARGET.txt)、[boot](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_BOOT.txt) |
| 包/工作目录 | 清单 1263→1263、新增/缺失均空；gdb 和原五依赖缺席；工作目录及父目录不存在 | [包](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_PACKAGES.txt)、[回执](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/audit.json) |
| governor/健康 | 四核 schedutil；stability 0→0；dmesg 原前缀保留，增量 39 行无 OOM/LMK；zram 三项 Δ=0 | [回执](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/audit.json)、[告警](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_ALERTS.txt)、[dmesg](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/dmesg_increment_END.txt)、[zram](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_ZRAM.txt) |
| df | 分别取根和 /opt/usr 原文；无安装/卸载或推送 | [根](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_DF_ROOT.txt)、[/opt/usr](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/ROOT_END_DF_OPTUSR.txt) |

非我方 PID 667/tty7、1096/ttyS0 shell 仅报告。历史 dmesg 有 SMACK 拒绝行，不能写成
“日志没有任何告警”。共 111 条客户端命令、107 条 shell 正文，70–161 UTF-8 字节；
91 条 RC=0，16 条 RC=1 恰为工作目录/父目录四次缺席与六包各两次缺席，标志全部匹配。
116 是 manifest 文件数，不是命令数。以上计数可独立从原文重放：

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_directory_disposition.py \
  data/raw/system_level_before_after_20260908/directory_disposition_20260911
```

输出 `PASS_DELAYED_CLEANUP_WITH_REPORT_ONLY_NONEMPTY`，重验哈希、操作、UID、进程
与健康，不依赖回执自报 PASS。按 PM 裁决延期收尾闭合，**整轮完成**；旧 STOP 与 G4
cleanup=FAIL 原回执不修改。21 格不重跑；本次无测量、注入、文件推送、包/目录/文件
增删、governor 写入、进程终止或重启。完整原始件本地留存，可按请求提供。

## 13. 已验收矩阵合成与优化效果

[合成回执](../data/raw/system_level_before_after_20260908/accepted_matrix/composition.json)
连接已验收的重启前 18 格、重启后 G4 三格与延期收尾；不是一次连续运行。两次旧执行
回执 SHA、各 tar/文件/点转录均再次核验，原合同/analyzer 一字不改。
[组合入口](../tools/runners/system_level_before_after_20260908/compose_accepted_measurement.py)
不放宽旧 publish_measurement 的 STOP 拒绝门，也不覆盖历史回执。

以下为合同 **cycle=1、每臂三重复** 中位，前值、后值、配对降幅分别取中位，不能把
两个中位之差代替降幅中位。每格全量与极差见
[cycles.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)、
[summary.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)。

| trim 组 | RSS 前→后 MiB | RSS 降幅 MiB / % 中位 | 系统配对净效应 MiB | 耗时中位 ms |
|---|---|---|---|---|
| G1 mixed | 13.015625→7.718750 | 5.296875 / 40.696279% | **−0.167969** | 1.458574（释放点） |
| G2 medium-only | 13.152344→7.191406 | 5.960938 / 45.322245% | +5.304688 | 1.478167（释放点） |
| G3 gst | 8.671875→6.859375 | 1.820312 / 21.009919% | +1.855469 | 0.843612（释放点） |
| G4 enlightenment | 11.605469→11.601562 | 0.003906 / 0.033659% | NA，无 none 臂 | **1899.209517（含 gdb/ptrace 注入）** |

前三组 none 的 RSS 下降为零，不是系统 MemAvailable 不变。系统净效应按同重复/周期
顺序 none 格相减，非同一时刻并行隔离；mixed 为负，不能宣传系统净增。summary 中
memavailable_*_mb 是十进制 MB，除以 1.048576 转 MiB，原字段定义保留。RSS、heap PD、
other-anon、total PD、memps 不能互换；所有细项见逐周期 TSV。

G4 heap PD 下降 **88/0/4 KiB**，memps 堆口径同步；约 **0.03% 的分母是 RSS**。
静置 minflt **1/0/1**、majflt 零，next-cycle NA；两注入间隔均 ≥120 s，不能冒称业务
再激活代价。见[原 G4 观察](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_points.json)。
与[历史 B/B2](tizen_native_evidence_20260904.md)的 272 KiB / 36 KiB / 8–20 KiB 同向，
仅支持已测批量释放负载收益明显、已测常驻守护对照收益很小的边界。

本轮 gst 原 nearest-rank 规则、周期 2–51（每重复 50 主样本）：none p99 中位
20019.978470 ms，trim 20018.325636 ms，差 **−1.652834 ms**，none 极差
**11.794149 ms**；未检出可见劣化，仅 REPORT_ONLY，不等于零代价，不与旧 gst 轮混池。
来源：[判定](../data/raw/system_level_before_after_20260908/accepted_matrix/gst_comparison.json)、
[逐循环](../data/raw/system_level_before_after_20260908/accepted_matrix/gst_cycles.tsv)。

trim/none 使用相同已验哈希二进制，仅运行时调用，不修改 ELF 体积。前后采样窗 major
fault 均为零，末周期 next-cycle NA；不外推冷启任意窗口。以上是测试板量级，整机/
产品收益仍待产品板验证，产品侧四道启用门不变。

### 13.1 复现

[L1 完整命令/预期输出/五项 cmp](demo_reproduction_guide_20260901.md#l1-system-before-after)。
板端 harness 仍为本轮目录内 execute_contract.py / execute_g4_resume.py 与
[原合同](../tools/runners/system_level_before_after_20260908/contract.json)；不允许重跑本次
已验收格，未来复测需另行授权/登记，root 不作默认行为。
确定性项为合同 payload；validity gates 包括页对齐、majflt/zram/OOM-LMK、PID/身份、
健康/清理和 UID 复原；性能量按原统计/容差规则报告，不将本次 RSS/System 结果制定为
新验收带，G4 注入计时不套释放点调用带。
