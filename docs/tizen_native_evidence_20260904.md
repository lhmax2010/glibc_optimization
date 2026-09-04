# Tizen 原生进程与工具门控 trim 实证（2026-09-04）

> 本报告的 §2 在 T1/T2/T3 正式格执行前写定。执行基线为 `main`
> `840b9572ac8ce75b9615141fbdf46b098cd035d4`；不得依据结果调整负载、间隔、
> 重复数、观测口径或主张边界。板地址在入库内容中统一记为
> `<TEST_BOARD_IP>`。

## 1. 能力侦察

侦察只决定硬前置是否满足，不产生 T1/T2 结果。三重身份门与环境门原文为：

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
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l
RC=0
DONE_OS_RELEASE
glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC_RPM
MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
0
RC=0
DONE_ROOT_UID
```

### 1.1 enlightenment 与 `memps`

`/usr/bin/enlightenment` 正在运行，侦察 PID 为 `505`，采集时已启动约 6.9 天。
静置 60 s 得到 60 个可解析样本，PID 恒定，项目分类的 glibc heap PD 每点均为
`3472 KiB`。同一时刻 Tizen 自带 `memps 505` 的原文关键行是：

```text
 S(CODE)  S(DATA)  P(CODE)  P(DATA)      PSS     SWAP ADDR(start-end)   OBJECT NAME
       0        0        0     3472     3472        0 018d6000-02296000 [heap]
RC=0
DONE_MEMPS_PID
```

`memps -a` 与 `memps <pid>` 均返回 `RC=0`；后者按 mapping 给出 `P(DATA)`，可独立
读取主堆 Private_Dirty。侦察摘要及后续健康事实见
[`execution_excerpt.txt`](../data/raw/tizen_native_evidence_20260904/execution_excerpt.txt) 和
[`health.json`](../data/raw/tizen_native_evidence_20260904/health.json)。完整原始件留在本地
`board_results`，可按请求提供。

### 1.2 gdb 来源、空间预算与注入自测

镜像初始未安装 `gdb`。固定 Base Toolchain 快照
`tizen-base-toolchain_20260813.050338` 的 repodata revision 为 `1786696327`；其中
`gdb-16.3-1.1.armv7l` RPM 为 `2,759,221 B`、安装体积 `6,686,215 B`，SHA-256 为
`95d713691a0628ed0cc7fdf61cbe896f439135e4bb0b8c5690c2ef5010530165`。完整依赖事务为：

| 包 | 安装体积 (B) |
|---|---:|
| `gdb-16.3-1.1.armv7l` | 6,686,215 |
| `python3-3.14.2-1.5.armv7l` | 3,480,703 |
| `python3-base-3.14.2-1.6.armv7l` | 39,102,845 |
| `libpython3_141_0-3.14.2-1.6.armv7l` | 3,512,680 |
| `libgmp-4.2.1-1.6.armv7l` | 188,360 |
| `gdbm-1.8.3-1.7.armv7l` | 39,876 |

合计 `53,010,679 B`。根分区安装前可用 `1,832,374,272 B`，事务预检通过，安装后
可用 `1,774,624,768 B`，仍高于 `1.2 GiB` 硬门。RPM 的 `%post/%postun` 运行
`ldconfig` 时打印了两个 “Cannot lstat ... Permission denied” 警告；实际 `gdb --version`
为 `GNU gdb 16.3`，动态依赖检查和两项注入自测均通过。

[`trim_via_gdb.sh`](../tools/reclaim_probe/trim_via_gdb.sh) 已由过时的 `unified-dev`
字符串门修正为冻结 BUILD_ID + `armv7l` + `rpi4` 三门。在自研 `alloc_bench` 进程上，
`malloc_trim(0)` 返回 `1`、detach 后进程仍存活；另用非 ARM 寄存器名 `$stream` 验证
`malloc_info` XML 可解析。硬前置通过。

### 1.3 原生 GST 与 UI 能力

`gst-launch-1.0 1.24.11` 可执行；`multifilesrc`、`filesrc`、`decodebin`、
`avdec_mpeg4`、`fakesink`、`identity` 均由板上 `/usr/lib/gstreamer-1.0/` 插件提供。
`app_launcher -l` 列出多个原生 UI 应用；预登记选择 `attach-panel-gallery`。能力存在只表示
命令/插件可解析，不预判其持续运行生命周期。

## 2. 预登记规格

### 2.1 不变量、身份门与健康门

- 身份门：`uname -r` 含 `rpi4`，`uname -m` 严格为 `armv7l`，BUILD_ID 严格为
  `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`。
- 环境门：`glibc-2.40-1.6.armv7l`，MemTotal 约 `8117408 kB`，root 身份；
  4 核 governor 可写，工作目录固定为
  `/opt/usr/glibc_memopt/tizen_native_evidence_20260904/`。
- 所有板端步骤输出远端 `RC=...` 与 `DONE_*/FAIL_*`；host 只认这些标志和
  可解析产物。正式格开始前把 4 核切为 `performance`，所有退出路径恢复
  `schedutil` 并复核。
- 正式窗口前后记录 dmesg、zram `mm_stat`、`/proc/swaps`、进程 PID/启动时长和
  stability-monitor livedump 快照。任何新增告警都逐件归档并归因；本轮不预登记豁免，
  可归因于注入或本轮 PID 的告警原样记为健康失败。要求零 OOM/LMK，Tizen 目标进程
  无崩溃、无重启。
- 本轮官方仓库安装的 `gdb` 及依赖在收尾时反向卸载；随后复核包缺失、根分区空间、
  工作目录消失、我方进程为零。

### 2.2 T1：Tizen 官方工具作为负载

媒体资产固定为 `small_320x240.mp4`，SHA-256
`3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d`。命令逐字冻结为：

```sh
gst-launch-1.0 -v \
  multifilesrc location=/opt/usr/glibc_memopt/tizen_native_evidence_20260904/small_320x240.mp4 start-index=0 stop-index=0 loop=true \
  ! decodebin ! identity name=counter silent=false \
  ! fakesink sync=true
```

管线启动后先稳态运行 30 s；随后以每次注入开始时刻相隔至少 60 s 的固定节奏，
由 `gdb -p` 调用 `malloc_trim(0)` 共 5 次。每次记录：注入前后项目既有
glibc heap PD 分类值、`memps <pid>` 原文、远端单调/墙钟时刻、trim 返回值、
整次 gdb 注入耗时。该耗时包含 attach、ptrace 停顿、符号解析、调用与 detach，
只作为注入方案观测，不作为进程内钩子代价数字。

每次注入前后均要求 PID 存活，并记录日志中 `identity` 的累计 buffer 消息数；5 次后
再次确认计数增长、进程存活，且日志无 `ERROR`。最后只向该本轮启动 PID 发送 TERM，
等待退出并记录状态。

### 2.3 T2：Tizen 平台守护进程实证

目标为侦察时已在运行的 `/usr/bin/enlightenment`，正式执行前重新解析 PID，不沿用 IP
或旧 PID 判板。E1/E2/E3 三格的注入开始时刻彼此至少相隔 120 s；每格顺序固定为：

1. 记录 PID、`/proc/<pid>/stat` 启动时刻、项目分类 PD 与 `memps <pid>`；
2. gdb 注入 `malloc_info(0, fp)`，XML 写入本轮工作目录；XML 必须解析成功，登记
   arena 数及 `fast/rest/unsorted` 字节（M7）；
3. 紧接着注入 `malloc_trim(0)`，记录返回值与含 ptrace 的总注入耗时；
4. 立即再次取项目分类 PD 与 `memps`；要求同 PID 存活且启动时刻未变。

侦察已发现原生 UI 应用 `attach-panel-gallery`，因此执行 E4“释放相位后 trim”格：
严格重复 5 次 `app_launcher -s attach-panel-gallery`、等待 5 s、
`app_launcher -t attach-panel-gallery`、等待 5 s；每条启动/终止命令都要成功并有
RC/DONE 标志。随后按 E1–E3 同样顺序取 M7、trim 与前后观测。E4 不并入 120 s
重复统计，只单列。

### 2.4 T3：`memps` 交叉见证与主张边界

T2 每格注入前后同时保存 Tizen 自带 `memps <pid>` 原文和项目分类结果。主比较使用
`memps` 的 `[heap]` Private/Data 读数与项目分类的主堆值；若存在额外 1 MiB 对齐匿名
arena，两者定义差异必须单列，不强行判一致。只允许陈述：实测回收 KiB、M7 驻留证据、
过程中是否崩溃/重启，以及 `memps` 是否独立看到同方向变化；不声称产品收益，不换算
业务指标，不由聚合 XML 推断具体 systrim/heap_trim/munmap 路径。

完整机器可读冻结项见
[`preregistered_contract.json`](../tools/runners/tizen_native_evidence_20260904/preregistered_contract.json)。
正式格开始前于 `2026-09-04T13:30:49,620002416+08:00` 记录该文件，SHA-256 为
`9de3cdda433be68239add7f20da2ee4ace3fbeba8092288f2d34e8599afd1dfb`；原始登记摘要收录在
[`execution_excerpt.txt`](../data/raw/tizen_native_evidence_20260904/execution_excerpt.txt)。

## 3. 执行结果

### 3.1 workflow 缺陷与数据采用规则

正式负载前后出现两个 harness 缺陷，均在产生对应格的 trim 数据前触发：第一次 T1
控制器因 POSIX shell 函数共享 `label` 变量而在 T1_1 pre-observation 后停止；第一次
T2 尝试因 ARM 的 `$fp` 是帧指针寄存器而在 `malloc_info` convenience-variable 赋值处
停止，XML 为 0 字节。两次均由 trap 结束本轮进程、恢复 governor，且告警增量为 0。
修复分别是函数变量加作用域前缀，以及把 convenience variable 改为 `$stream`；没有
改变 §2 的负载、时间、次数或口径。两次零格尝试不进入结果表。

T1 正式重试完成 T1_1 后，冻结管线在媒体时间 `60.100233983 s` 正常 EOS，早于 T1_2；
因此只采用 T1_1，明确记为 `1/5`，不得据此形成五重复结论。随后只跳过已失败的 T1，
用原规格独立执行 T2。T2 E1–E3 完成；E4 的第一个 Gallery 启动命令返回成功，但 5 s
后应用已自行退出，冻结的 terminate 命令返回 “App isn't running”，故 E4 为 `0/1`，
没有 trim 数据，也没有改用 `-k` 或换应用补跑。

另有一项协议偏差：控制器用整数秒边界实现“至少 120 s”，前置采样时刻的两个间隔实为
`119.806876910 s / 119.856460299 s`，分别短 `0.193123090 s / 0.143539701 s`。
因此 E1–E3 是三个完整、可解析观测，但不能标为严格满足 ≥120 s 的合规重复。完成度和
偏差均固化在 [`summary.json`](../data/raw/tizen_native_evidence_20260904/summary.json)。

### 3.2 T1：板上 `gst-launch-1.0`

| 格 | heap PD 项目口径 (KiB) | `memps [heap]` (KiB) | 回收 (KiB) | gdb 注入 (ms) | buffer 计数 | min/majflt Δ | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| T1_1 | 1372 → 1360 | 1372 → 1360 | 12 | 1154.652672 | 903 → 941 | +4 / 0 | 完成 |
| T1_2–T1_5 | — | — | — | — | — | — | 管线于 T1_2 前 EOS |

T1_1 的 `malloc_trim(0)` 返回 `1`；注入窗口内 PID/启动时刻不变，解码 buffer 仍从
`903` 增至 `941`，日志没有 ERROR。该 `1154.652672 ms` 包含 gdb/ptrace 全路径，不能
与进程内钩子时延比较。项目主堆和 `memps` 都看到 `12 KiB` 下降；但只有一个完整格，
不对五次稳定性作主张。逐字段见
[`cells_derived.tsv`](../data/raw/tizen_native_evidence_20260904/cells_derived.tsv)。

### 3.3 T2/T3：enlightenment 的 M7、trim 与 `memps` 交叉见证

三个格的 PID 均为 `505`、`starttime_ticks=1468`；进程在每次 detach 后存活，最终
`/proc/505/exe` 仍为 `/usr/bin/enlightenment`。

| 格 | M7 arena / fast / rest / unsorted (B) | 项目 heap PD (KiB) | `memps [heap]` (KiB) | 回收 (KiB) | gdb 注入 (ms) | min/majflt Δ |
|---|---:|---:|---:|---:|---:|---:|
| E1 | 8 / 1448 / 6118675 / 0 | 3472 → 3200 | 3472 → 3200 | **272** | 1697.762304 | 0 / 0 |
| E2 | 8 / 1312 / 6118694 / 0 | 3204 → 3200 | 3204 → 3200 | **4** | 1771.618048 | 0 / 0 |
| E3 | 8 / 1048 / 6118706 / 0 | 3204 → 3200 | 3204 → 3200 | **4** | 1732.586752 | 0 / 0 |

每格的 pre-trim `malloc_info` 都可解析，8 个 arena 的顶层 `rest` 约 5.84 MiB，证明该时刻
allocator 统计里存在 free-chunk 驻留；它不等于全部可返还字节，也不能区分最终走
systrim、heap_trim 或 munmap。三次 `malloc_trim(0)` 均返回 `1`。首次观测主堆下降
`272 KiB`，后两次各 `4 KiB`；Tizen `memps` 与项目主堆口径逐格、逐值完全一致，因而
回收方向和数值不是只由自研 smaps 解析器观察到。原始/派生格表分别见
[`cells_raw.tsv`](../data/raw/tizen_native_evidence_20260904/cells_raw.tsv) 和
[`cells_derived.tsv`](../data/raw/tizen_native_evidence_20260904/cells_derived.tsv)。

### 3.4 健康、告警与清理

| 项 | 观测 | 判定 |
|---|---:|---|
| stability-monitor 新增 livedump | 0 | PASS |
| dmesg 规范化前后 | 588 行逐字一致 | PASS，零新增 OOM/LMK/segfault |
| zram original/compressed/used Δ | 0 / 0 / 0 | PASS |
| enlightenment PID/启动时刻 | 505 / 1468 恒定 | PASS |
| 最终 governor | 4/4 `schedutil` | PASS |
| 本轮目录/进程/示例应用 | ABSENT / 0 / not running | PASS |
| 本轮安装包残留 | 0/6 | PASS |

完整板端文件在删除前生成 manifest；拉回 61 件，大小/SHA-256 逐件核验为
`missing=0, bad=0`。6 包用下列命令通过卸载预检并实际卸载：

```sh
rpm -e --test gdb python3 python3-base libpython3_141_0 libgmp gdbm
rpm -e        gdb python3 python3-base libpython3_141_0 libgmp gdbm
```

根分区清理后可用 `1,832,058,880 B`，轮次目录按精确路径删除；健康事实见
[`health.json`](../data/raw/tizen_native_evidence_20260904/health.json)。

## 4. 结论与边界

1. **原生交叉见证成立，但矩阵未完整。** Tizen 守护进程 enlightenment、Tizen 自带
   `memps`、官方仓库 `gdb` 与 glibc 自身 `malloc_info` 共同形成了一条不只依赖自研
   负载/观察器的证据链。三个完成格中，`memps` 和项目主堆口径对
   `272/4/4 KiB` 回收逐值一致，进程无重启/崩溃；这只陈述本次测量。
2. **M7 有驻留不等于等量可回收。** 三格均有约 5.84 MiB `rest`，首次 trim 可见
   `272 KiB` 主堆下降，后续只有页粒度 `4 KiB`；聚合 XML 不能判定具体回收路径，也
   不能把 rest 总量直接当回收上限。
3. **T1 与释放相位格未闭合。** 原生命令管线只完成 `1/5`，Gallery 格为 `0/1`；
   enlightenment 两个间隔还各低于 120 s 约 0.2 s。故本轮不能声称“原生 GST 五次持续
   注入”或“真实 UI 释放相位后回收”成立。这三项是下一次重新预登记前必须修正的缺口，
   不能用本轮数据补推。
4. **主张边界不变。** 本报告不证明产品内存收益、不换算业务指标、不把含 ptrace 的
   1.15–1.77 s 注入时延当钩子代价，也不改变现有产品启用门。

## 5. 复现

本轮 harness 位于
[`tools/runners/tizen_native_evidence_20260904/`](../tools/runners/tizen_native_evidence_20260904/)；
机器合同是 [`preregistered_contract.json`](../tools/runners/tizen_native_evidence_20260904/preregistered_contract.json)，
冻结命令见 §2。完整命令、官方 gdb 获取/卸载和本轮已知停止点见
[`README.md`](../tools/runners/tizen_native_evidence_20260904/README.md)；Demo L2 手工入口见
[`复现指南`](demo_reproduction_guide_20260901.md#l2-tizen-native-evidence)。

```sh
python3 tools/runners/tizen_native_evidence_20260904/analyze_native_evidence.py \
  --t1-pull <T1-board-pull> --pull <T2-board-pull> --output <derived-dir>
```

验收分两类：

- **确定性/有效性项：** 身份与精确 BUILD_ID/glibc/媒体 SHA 过门；已完成格的 JSON/TSV/XML
  可解析；PID + starttime 在格前后相同；`memps [heap]` 与项目 `[heap]` 逐值相同；
  majflt 增量、zram 三项增量、dmesg OOM/LMK、新增 stability 告警均为 0；最终包、目录、
  进程和 governor 清理门通过。
- **容差/观察项：** 本轮没有为原生常驻进程预登记回收量或 gdb 注入耗时容差带；这些值
  依赖运行时状态，只按原值报告，不作为 PASS 条件。重跑不得用 S4 的合成负载验收带
  套用 enlightenment。冻结 T1/T2 完成数和 ≥120 s 间隔未满足，应复现为公开的
  `INCOMPLETE/PROTOCOL-DEVIATION`，不能判整轮 PASS。

## 6. B2 补跑：规格冻结（2026-09-05，执行前登记）

本节只追加、不改写 §1–§5 的原始观测和结论。机器合同为
[`preregistered_contract.json`](../tools/runners/tizen_native_evidence_20260905/preregistered_contract.json)。
以下规格在冻结前能力侦察通过后、任何正式格执行前写定；结果异常只报告，不改参数。

### 6.1 冻结前侦察与选择

- 身份/环境门重走并通过：内核 `6.12.80-arm-rpi4-v7l`、`armv7l`、精确
  BUILD_ID、`glibc-2.40-1.6.armv7l`、`MemTotal 8117408 kB`、`uid=0`。
- enlightenment 为 PID `505`、`starttime_ticks=1468`，已运行超过 6 天；60 秒、61 个
  1 秒序列中 PID/starttime 恒定，项目 glibc heap PD 逐样本为 `3220 KiB`。
- gdb 初始未安装；根分区可用 `1832058880 B`，扣除官方冻结六包安装体积
  `53010679 B` 后仍高于 `1.2 GiB`。安装后版本为 `gdb-16.3-1.1.armv7l`，先对
  SHA 为 `88667139…4efcffa` 的自研 `alloc_bench` 做一次 attach/trim 自测，返回成功且
  detach 后进程仍存活。该自测不进入 T1′/E4′数据。
- GST 冻结为 5 个顺序 `gst-launch-1.0` 进程各实时软解同一资产一次。侦察 controller
  总耗时 `301.209678592 s`（首进程启动至末进程结束 `301.165996080 s`）；5/5 进程均在
  30 秒存活、各有 `1802` 条 buffer 消息、退出码 0、
  ERROR 行 0。
- E4′ 冻结应用为 `setting-myaccount-efl`：侦察启动 PID `30598`，
  `30.249268736 s` 后同 starttime 仍存活，`app_launcher -t` 返回 0，2 秒后 PID 消失。

上述侦察数字只证明构造可执行，不并入正式回收结论。

### 6.2 T1′：官方 GST 工具五格

每格启动一个全新进程，命令逐字冻结为：

```sh
gst-launch-1.0 -m -v filesrc location=<small_320x240.mp4> \
  ! decodebin ! identity name=counter silent=false ! fakesink sync=true
```

共 5 格，每进程启动 30 秒进入稳态后注入一次 `malloc_trim(0)`，随后等待该次解码自然
结束。每格必须记录：注入前后项目 glibc heap PD、`memps [heap]`、PID/starttime、
进程前后存活、buffer 计数严格增长、自然退出码与 ERROR 行数，以及包含 gdb/ptrace 的
注入墙钟。第 2–5 次注入的“开始时刻减上次开始时刻”必须由纳秒时钟记录且
`≥120.000000000 s`；高精度等待按绝对纳秒截止时刻循环复核，不能再用整数秒边界。

### 6.3 E4′：真实 UI 活动后单格

对冻结应用 `setting-myaccount-efl` 顺序做 5 次：`app_launcher -s` 成功 → 记录 PID/
starttime → 30 秒后确认仍存活且 starttime 不变 → `app_launcher -t` 返回 0 → 2 秒后确认
该 PID 已消失。五次全部成功后，对原 enlightenment PID 先注入 `malloc_info` 取得 M7，
再注入 `malloc_trim(0)`；前后同时记录项目 glibc heap PD 与 `memps [heap]`。E1–E3 不重跑，
§3.1 的两个约 0.2 秒间隔偏差原样保留。

### 6.4 健康、清理与主张边界

正式 runner 再次校验身份/环境/资产 SHA；记录并把 4 核 governor 设为 `performance`，
所有退出路径恢复并复核 `schedutil`。记录 zram `mm_stat`、dmesg、stability-monitor
前后快照；新增注入类告警逐项归因且没有预期告警豁免。结束后逐件 SHA 拉回，卸载本轮
六个 gdb 相关包，删除精确工作目录并复核无进程/目录/包残留。

允许的主张仍限于：实测回收 KiB、M7、观测窗口内无崩溃/无重启、`memps` 与项目口径
是否一致。gdb 时延包含 ptrace，不作钩子代价；不声称产品收益、不换算业务指标。

## 7. B2 补跑结果（2026-09-05）

派生事实总表见 [`summary.json`](../data/raw/tizen_native_evidence_20260905/summary.json)，
逐格与计时分别见
[`cells_derived.tsv`](../data/raw/tizen_native_evidence_20260905/cells_derived.tsv) 和
[`intervals.tsv`](../data/raw/tizen_native_evidence_20260905/intervals.tsv)。以下只按 §6
冻结口径报告；不修改 §3 的旧值。

### 7.1 T1′：5/5 官方 GST 格完成

| 格 | 项目 heap PD (KiB) | `memps [heap]` (KiB) | 回收 (KiB) | gdb/ptrace 注入 (ms) | buffer | min/majflt Δ | 进程结果 |
|---|---:|---:|---:|---:|---:|---:|---|
| T1′-1 | 1360 → 1352 | 1360 → 1352 | 8 | 1047.252480 | 902 → 997 | +2 / 0 | exit 0，ERROR 0 |
| T1′-2 | 1368 → 1352 | 1368 → 1352 | 16 | 1062.385152 | 902 → 997 | +3 / 0 | exit 0，ERROR 0 |
| T1′-3 | 1368 → 1352 | 1368 → 1352 | 16 | 1041.132032 | 902 → 997 | +2 / 0 | exit 0，ERROR 0 |
| T1′-4 | 1368 → 1348 | 1368 → 1348 | 20 | 1025.379072 | 903 → 997 | +3 / 0 | exit 0，ERROR 0 |
| T1′-5 | 1364 → 1348 | 1364 → 1348 | 16 | 1016.830208 | 902 → 997 | +1 / 0 | exit 0，ERROR 0 |

五格均为新 PID，注入前后 starttime 不变、进程存活，随后各自完成一次自然 EOS；项目
口径与 `memps` 前后值 `5/5` 逐值相同。回收范围为 `8–20 KiB`、中位 `16 KiB`；含
ptrace 的注入范围为 `1016.830208–1062.385152 ms`、中位 `1041.132032 ms`。这些是
原生工具进程本次状态的观测值，不是进程内 hook 延迟。

高精度计时器的四个间隔依次为 `120.137978836 / 120.136903576 /
120.142672892 / 120.122271759 s`，全部严格大于 `120.000000000 s`。这证明新 controller
实现满足登记纪律；E1–E3 的旧 `119.806876910 / 119.856460299 s` 仍保留为历史协议偏差，
没有被新数据改写。

### 7.2 E4′：真实 UI 活动后格完成

冻结应用的五次活动均满足：启动返回 0、30 秒后同 PID/starttime 存活、终止返回 0、
2 秒后原 PID 消失；逐次记录见
[`app_cycles.tsv`](../data/raw/tizen_native_evidence_20260905/app_cycles.tsv)。之后
enlightenment 仍为 PID `505`、`starttime_ticks=1468`，M7 与回收结果为：

| 格 | M7 arena / fast / rest / unsorted (B) | 项目 heap PD (KiB) | `memps [heap]` (KiB) | 回收 (KiB) | gdb/ptrace 注入 (ms) | min/majflt Δ |
|---|---:|---:|---:|---:|---:|---:|
| E4′ | 8 / 1864 / 6019572 / 11002 | 3324 → 3288 | 3324 → 3288 | **36** | 1707.005696 | 0 / 0 |

M7 原文与派生值见
[`malloc_info_E4_PRIME.xml`](../data/raw/tizen_native_evidence_20260905/malloc_info_E4_PRIME.xml)
和 [`m7.tsv`](../data/raw/tizen_native_evidence_20260905/m7.tsv)。`malloc_trim(0)` 返回 1；
`memps` 与项目口径的 `36 KiB` 下降一致。观测窗口内 enlightenment 的 PID/starttime
没有变化，未见崩溃或重启。这里只证明“真实 UI 活动之后，本次注入看到这些量”。

### 7.3 估算器对 E4′的交叉检查

同一个 E4′ XML 的 `<size>` 整页几何区间为 `2252800–8167424 B`，即
`2200–7976 KiB`，而实测仅 `36 KiB`；区间两端误差为 `+2164 / +7940 KiB`。复算见
[`estimator_E4_PRIME.json`](../data/raw/tizen_native_evidence_20260905/estimator_E4_PRIME.json)。
它与 host 验证集 `15/15` 个严格配对观测均落在区间外的裁决一致：直方图区间可作诊断，
不能当量化启用门，M7 rest 也不能直接换算为回收量。

### 7.4 健康、完整性与清理

| 项 | 结果 | 判定 |
|---|---:|---|
| 正式 controller | RC=0；T1′ 5/5，应用 5/5，E4′ 1/1 | PASS |
| 拉回完整性 | manifest 68 件；missing/bad/extra = 0/0/0 | PASS |
| stability-monitor livedump | 0 → 0 | PASS，无新增告警需归因 |
| dmesg | 前后逐字节一致 | PASS，零新增 OOM/LMK/segfault |
| zram original/compressed/used Δ | 0 / 0 / 0 | PASS |
| 正式格 majflt Δ | T1′ 5 格及 E4′ 均为 0 | PASS |
| 最终 governor | 4/4 `schedutil` | PASS |
| gdb 六包/目录/进程 | 6/6 absent；轮次目录与父目录 absent；进程 0 | PASS |

详细收尾记录见
[`run_record.txt`](../data/raw/tizen_native_evidence_20260905/run_record.txt)。gdb 卸载事务本身
返回 0，随后逐包复核为 6/6 absent；原卸载辅助脚本因“全部不存在”循环最后一个预期非零退出码
误报 `FAIL_GDB_REMOVE_VERIFY`，独立复核后确认是 host 判定缺陷，并已在本轮 harness
中补显式成功返回。安装前预算读取另有一处 `$4` 转义缺陷，失败发生在任何推送/安装前，
同样已修复并纳入 host 测试；两条原始失败记录保留在本地完整原始件。

## 8. B2 结论、边界与复现（2026-09-05）

1. **T1 数量缺口闭合。** 重新冻结的官方工具构造完成 `5/5` 注入，持续解码、自然退出、
   buffer 增长与双口径回收均有证据；不再用上一轮 `1/5` 外推稳定性。
2. **E4 覆盖缺口闭合。** 可验证存活的原生应用完成 `5/5` 启停，随后 E4′ 得到可解析 M7
   与 `36 KiB` 双口径回收；这不把 UI 活动与回收量建立因果或产品收益关系。
3. **新计时器合规，旧偏差保留。** T1′ 四个跨格间隔均为 `≥120.000 s`，证明高精度等待
   生效；未重跑的 E1–E3 仍按旧报告的 protocol deviation 解释。
4. **“驻留量不等于可回收量”进一步成立。** E4′ rest 为 `6019572 B`，实测回收仅
   `36 KiB`；直方图估算也没有量化预测能力。产品门仍需实际 A/B 与代价预算。
5. **主张边界不变。** 不声称产品收益、不换算业务指标；原生进程的 gdb/ptrace 时间不是
   hook 代价；“本次未崩溃/未重启”不外推长期可靠性。

本次 harness 位于
[`tools/runners/tizen_native_evidence_20260905/`](../tools/runners/tizen_native_evidence_20260905/)，
冻结参数以 [`preregistered_contract.json`](../tools/runners/tizen_native_evidence_20260905/preregistered_contract.json)
为唯一事实源。host 复算：

```sh
python3 tools/runners/tizen_native_evidence_20260905/test_host.py
python3 tools/analysis/test_trimmable_estimator.py
python3 tools/runners/tizen_native_evidence_20260905/analyze_b2.py \
  --pull <local-complete-board-pull> \
  --idle-log <local-idle-60s-raw-log> \
  --output /tmp/tizen-native-b2
```

- **确定性/有效性项：** 精确身份/环境/资产与 contract SHA；T1′/应用/E4′ 完成数；
  JSON/TSV/XML 可解析；PID/starttime 稳定；`memps` 与项目 heap 前后逐值一致；buffer
  严格增长；注入间隔 `≥120000000000 ns`；majflt、zram 三项、dmesg 新增 OOM/LMK、
  stability livedump 均为 0；退出、governor、包、目录、进程清理通过。
- **容差/观察项：** 原生进程回收 KiB、M7 值与含 ptrace 注入时延不设跨运行容差，原样
  报告；不套用 S4 合成负载验收带。估算器在同一 XML/页大小下应逐字节复算，但不得用
  它判定板端回收 PASS/FAIL。
