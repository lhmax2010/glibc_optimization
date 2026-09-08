# 系统级前后对照补测（2026-09-08）

状态：合同冻结，尚未连接板、尚无测量结果。既有数据、验收带与技术结论不变。当前有效交付快照仍为 `demo-v11`。

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
