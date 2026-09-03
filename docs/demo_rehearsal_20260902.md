> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# Demo 彩排与演示板卫生审计

- 日期：2026-09-02
- 演示板：`<TEST_BOARD_IP>:26101`（SDB）
- 演示入口：[`demo_package_20260902.md`](demo_package_20260902.md)
- 基线：[`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md)
- 可执行审计件：[`tools/runners/demo_rehearsal_20260902/`](../tools/runners/demo_rehearsal_20260902/)
- 轮次边界：初始彩排的 L1 和卫生审计为只读；PM 裁决后追加精确残留清理与
  S4/gst 全量 L2 复跑。全部写入都限于指定工作目录和可归属归档，未装卸包、未重启。

## 1. 结论先行

1. **四组 L1 演示在当前文档修正后全部可现场执行。** A、C、D 的标准输出与复现指南
   冻结原文逐字符一致；B 的两个 `cmp`、D 的三个 `cmp` 均静默成功。发现并直接修正了
   两处不涉及规格或结论数字的文档问题：A 的“最后两行”改为“最后三行”；C 补上复现
   指南已经要求的 released-payload 与 4 kB 对齐两行输出。
2. **板身份与环境门通过。** 内核含 `rpi4`、架构严格为 `armv7l`、`BUILD_ID`、glibc
   和 `MemTotal` 均与 2026-08-31 基线一致。
3. **残留清理裁决已执行并闭合。** 两个 S4 livedump 先拉回本地、校验 SHA
   和内部元数据，再按精确路径删除；空 `/opt/usr/glibc_memopt` 用 `rmdir` 删除。
   删除后三个目标均不存在，stability-monitor 归档计数从 `2` 变为 `0`。
4. **L2 “假扮 HQ”全程已完成。** 在 `HEAD=1ebbf03` 的全新 clone 中，仅按复现
   指南及其链接执行 S4 10 格和 gst 6 格全矩阵；两者均完成 manifest 校验、
   JSON 解析、清理和 governor 恢复。
5. **数值验收与健康验收必须分开。** S4 的锚点、B 组三重复中位、payload、
   页对齐、faults、zram 和 OOM/LMK 均过带；追加的回收量字节审计只有 `10/12`
   周期与发布批相同，确认同 seed 不保证该量逐字节重现。另有两个明确归因本轮
   `alloc_bench` 的 stability-monitor 告警，因此 S4 的新健康门为硬失败；gst 的
   stability-monitor 前后均为 `0`，该门通过。
6. **stability-monitor v1 当轮规则已冻结。** 每轮记录运行前后告警计数并归因新增件；
   在当轮 v1 下，只有可归因我方 PID/二进制的新告警构成硬失败，其他告警原样报告、不动。
7. **trim 时延规格范围已经 PM 裁决闭合。** 释放点 trim（B 组与 gst）单次
   `<5 ms`；A 组锚点 trim 单列 `<20 ms`，且不作为钩子代价数字。
8. **stability-monitor v1/v2 判定并存。** 当轮按 v1 预先记录的结论仍是
   `HARD FAIL`，不回写；v2 将理由、窗口、owner 与数量上界匹配的 S4 A 组两个
   `cpu.relative` livedump 适用 known-alert waiver，完成归档和清理后判 `EXPECTED` 通过；
   这里只确认触发理由与窗口可复现，未做根因证明。

## 2. Host L1 完整彩排

### 2.1 干净 clone 条件

从 `origin` 新建非工作区 clone，确认 `HEAD=3e9cbd3` 且 `git status --short` 为空；所有
复算输出进入 clone 外的临时目录。表中耗时只用于演示编排，不进入任何性能或机制结论。

| 组 | 按文档执行的结果 | 标准输出核验 | `cmp` 核验 | 实测墙钟 | 裁决 |
|---|---|---|---|---:|---|
| A · ServiceA 归因链 | 两条命令均 `RC=0` | 与指南冻结的完整输出逐字符一致 | 不适用 | `0.087 s` | 通过；“最后两行”文字修为“最后三行” |
| B · retained-floor 普查 | 分析器 `RC=0` | 文档未冻结分析器 stdout，不作逐字节门 | 2/2 静默、`RC=0` | `0.080 s` | 通过 |
| C · S4 门控证据 | 原命令 `RC=0`，但仅输出 6 行；修正后的当前命令 `RC=0` 并输出 8 行 | 修正后与指南冻结原文逐字符一致 | 不适用 | 原 `0.024 s`；修正后 `0.024 s` | 原文阻断已闭合 |
| D · gst cycle replay | 分析器 `RC=0` | 与指南冻结的两行逐字符一致 | 3/3 静默、`RC=0` | `0.041 s` | 通过 |

正式计时前有一次外层捕获脚本未在新 shell 中重新声明 `OUT`，分析器未启动；这属于彩排
封装错误，不是仓库命令失败。演示日检查单把 clone、`cd` 和 `OUT` 初始化固定在同一 shell。

### 2.2 逐组预期原文核验

A 组完整 stdout：

```text
ServiceA
R1 P-V=9796kB zorig=0B zused=0kB minflt_rise=10652 majflt_fall=0
R2 P-V=6244kB zorig=0B zused=0kB minflt_rise=9436 majflt_fall=0
R3 P-V=8620kB zorig=0B zused=0kB minflt_rise=1238 majflt_fall=0
R4 P-V=6676kB zorig=0B zused=0kB minflt_rise=959 majflt_fall=0
R5 P-V=4032kB zorig=0B zused=0kB minflt_rise=1082 majflt_fall=0
R6 P-V=6180kB zorig=-262144B zused=-256kB minflt_rise=857 majflt_fall=0
R7 P-V=4332kB zorig=0B zused=0kB minflt_rise=9615 majflt_fall=0
R8 P-V=5792kB zorig=0B zused=0kB minflt_rise=5477 majflt_fall=0
median_P-V_kB 6212.0
zram_total -262144 -256
missing_rows 0 pid_changes {'ChannelLoader': 0, 'ServiceA': 0, 'ServiceB': 0, 'WebRuntime': 0}
ServiceA majflt=167->167 delta=0
```

B 组分析器额外打印一行摘要；该行不是冻结验收项，正式门仍是两个公开派生 TSV 的
`cmp` 静默成功：

```text
{"cyclic_min_over_tail": true, "plateau_min_over_tail": false, "plateau_targets": 10, "release_ratio_min_over_tail": false, "release_targets": 10}
```

C 组修正后的完整 stdout：

```text
A anchors: mixed=51.074077% medium-only=50.387886%
B reclaim/released range=80.175875-85.453954%
mixed trim_ms_median=1.233269 next_minflt_extra=+1351
medium-only trim_ms_median=1.218361 next_minflt_extra=+1465
released_payload_bytes: mixed=5742256,6566672 medium-only=6288384,6293504
reclaimed_4k_aligned=12/12
majflt_all_zero=true
zram_deltas=0,0,0 dmesg_increment=0 oom_lmk=0
```

D 组完整 stdout：

```text
replayed cells=6 cycles=306 primary=300
delta_p99_ms=6.228611 none_dispersion_ms=6.784167 visible=false
```

以上数字均来自既有公开输入；复算来源和命令仍以
[`HQ 复现指南 L1`](demo_reproduction_guide_20260901.md#l1-servicea)为准。

## 3. 板身份与环境门

所有命令均由远端回显 `RC=0` 和对应 `DONE_*` 标志。原文如下：

```text
$ sdb -s <TEST_BOARD_IP>:26101 shell 'uname -r; ...'
6.12.80-arm-rpi4-v7l
RC=0
DONE_UNAME_R

$ sdb -s <TEST_BOARD_IP>:26101 shell 'uname -m; ...'
armv7l
RC=0
DONE_UNAME_M

$ sdb -s <TEST_BOARD_IP>:26101 shell 'cat /etc/os-release; ...'
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

$ sdb -s <TEST_BOARD_IP>:26101 shell 'rpm -q glibc; ...'
glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC

$ sdb -s <TEST_BOARD_IP>:26101 shell 'grep "^MemTotal:" /proc/meminfo; ...'
MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
```

五项均通过，与[新 LLVM 镜像基线](board_baseline_llvm_image_20260831.md#4-新镜像基线)
一致，允许进入只读卫生审计。

## 4. 卫生审计

### 4.1 核验项

| 核验项 | 当前原文/证据摘要 | 与基线或无残留标准对照 | 判定 |
|---|---|---|---|
| 项目工作目录 | `/opt/usr/glibc_memopt` 存在，`drwxrwxrwx`，目录内无条目 | 历轮报告均要求删除具体轮次目录；固定父目录仍在 | 有我方空目录残留 |
| 顶层及候选哈希 | `/tmp`、`/home`、`/opt/usr` 顶层和项目目录中，按工具名、媒体/TSV/JSON/XML/hist/script 后缀扫描无我方文件；`RC=0/DONE_CANDIDATE_HASH_AUDIT` | 无历轮二进制、媒体、结果或脚本 | 通过 |
| 进程 | 完整 `ps -ef` 中无 `alloc_bench`、`gst_loop_decode`、采样器或历轮 runner | 无测试进程 | 通过 |
| governor | cpu0–cpu3 均为 `schedutil` | 与 S4/gst 退出纪律一致 | 通过 |
| zram / swap | `mm_stat = 4096 74 4096 0 4096 0 0 0 0`；`/dev/zram0` Used `0` | 与[08-31 基线](board_baseline_llvm_image_20260831.md#42-kernel内存cpu-与-zram-原文)逐值一致 | 通过 |
| 内存静置 | `MemAvailable: 6897324 kB`，zram 未使用 | 当前无交换压力，处于合理静置区间 | 通过 |
| 包变更 | `rpm -qa --last` 最新一批仍是 2026-08-15 镜像安装项 | 08-31 后无新包，符合历轮零安装声明 | 通过 |
| 磁盘 | `/` 可用 `1832374272 B`（`1.8G`）；`/opt/usr` 可用 `118190792704 B`（`111G`） | 根分区逐字节等于 [gst 能力门](gst_trim_cost_20260901.md#22-gstreamer插件与空间)，挂载占用量级与基线一致 | 通过 |
| crash/coredump | 常规 dump/temp/coredump 目录为空；livedump 有 2 个 S4 `alloc_bench` 快照 | 不满足“无历轮产物” | 有我方残留 |
| 当前内核事件 | 事件级 grep：`EVENT_MATCH_RC=1`；无测试名命中 | 无 OOM/LMK/segfault；仅有系统 deprecation 文字 | 通过 |

关键只读原文：

```text
WORK_ROOT=/opt/usr/glibc_memopt
drwxrwxrwx 2 0 0 3488 Sep  1 23:57 /opt/usr/glibc_memopt
RC=0
DONE_WORK_ROOT_AUDIT

/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
RC=0
DONE_GOVERNOR_AUDIT

4096 74 4096 0 4096 0 0 0 0
RC=0
DONE_ZRAM_MM_STAT_AUDIT

Filename      Type       Size     Used Priority
/dev/zram0    partition  3246960  0    0
RC=0
DONE_SWAPS_AUDIT

DMESG_RC=0
EVENT_MATCH_RC=1
RC=0
DONE_DMESG_EVENT_AUDIT
```

### 4.2 我方残留处置清单

| 精确目标 | 归属证据 | 建议处置 | 本轮状态 |
|---|---|---|---|
| `/opt/usr/glibc_memopt` | 固定项目工作根；内部为空；mtime 位于 gst 轮完成后 | 在两个 livedump 处置后用精确 `rmdir` 删除 | `RC=0/DONE_ADJUDICATED_RESIDUAL_CLEANUP`；二次复核不存在 |
| `/opt/usr/share/crash/livedump/alloc_bench.armv7l_31200_20260901172715.zip` | `info.json` 的 executable path 指向 S4 工作目录；大小 `359978 B`；SHA-256 `0a5a8780c0edb2427795330123fe6715b5157933c738a32b0ebe09168799cfa0` | 先归档校验，再按精确文件名删除 | host 归档 SHA 匹配；删除后不存在 |
| `/opt/usr/share/crash/livedump/alloc_bench.armv7l_31971_20260901172754.zip` | 同上；大小 `361579 B`；SHA-256 `fd7a56db8385f4066e7181f0970bf5d100c125d6145e42f08a959ca51bb0661e` | 先归档校验，再按精确文件名删除 | host 归档 SHA 匹配；删除后不存在 |

两个压缩包的 `dump_reason` 分别报告 `cpu.relative` 实际值 `3.8203134021870864` 和
`3.8165405446011791` 超过允许值 `3.7999999999999998`；调用栈停在
`usleep`/`nanosleep`。它们是 stability-monitor 生成的 live snapshot，不是仍存活进程；
但作为历轮落盘物仍应清除。PM 批准后实际执行了下列精确范围，未使用通配符：

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
sdb -s "$SDB_SERIAL" shell '
f1=/opt/usr/share/crash/livedump/alloc_bench.armv7l_31200_20260901172715.zip
f2=/opt/usr/share/crash/livedump/alloc_bench.armv7l_31971_20260901172754.zip
test "$(sha256sum "$f1" | awk "{print \$1}")" = 0a5a8780c0edb2427795330123fe6715b5157933c738a32b0ebe09168799cfa0 &&
test "$(sha256sum "$f2" | awk "{print \$1}")" = fd7a56db8385f4066e7181f0970bf5d100c125d6145e42f08a959ca51bb0661e &&
rm -f "$f1" "$f2"
rc=$?
echo RC=$rc
if [ $rc -eq 0 ]; then echo DONE_APPROVED_LIVEDUMP_CLEANUP; else echo FAIL_APPROVED_LIVEDUMP_CLEANUP; fi'
sdb -s "$SDB_SERIAL" shell '
rmdir /opt/usr/glibc_memopt
rc=$?
echo RC=$rc
if [ $rc -eq 0 ]; then echo DONE_APPROVED_WORKROOT_CLEANUP; else echo FAIL_APPROVED_WORKROOT_CLEANUP; fi'
sdb -s "$SDB_SERIAL" shell '
test ! -e /opt/usr/glibc_memopt &&
test ! -e /opt/usr/share/crash/livedump/alloc_bench.armv7l_31200_20260901172715.zip &&
test ! -e /opt/usr/share/crash/livedump/alloc_bench.armv7l_31971_20260901172754.zip
rc=$?
echo RC=$rc
if [ $rc -eq 0 ]; then echo DONE_APPROVED_CLEANUP_RECHECK; else echo FAIL_APPROVED_CLEANUP_RECHECK; fi'
```

二次复核原文为三个目标均 `ABSENT`、`STABILITY_MONITOR_FILE_COUNT=0`、
`RC=0/DONE_POST_CLEANUP_VERIFY`。完整 ZIP、`dump_reason`、`info.json` 和拉回哈希保留在
本地 `board_results/demo_rehearsal_20260902/residual_cleanup_20260902/`。

#### 与 S4 正式格时间线对照

- PID `31200` 的归档名时刻 `17:27:15`，mtime `17:27:20.179999635 +0900`，落在
  `A/mixed/rep1` 的 `17:27:07.575874569–17:27:48.610417285 +0900` 正式窗口。
- PID `31971` 的归档名时刻 `17:27:54`，mtime `17:27:59.839999612 +0900`，落在
  `A/medium-only/rep1` 的 `17:27:48.648846785–17:28:29.684120242 +0900` 正式窗口。
- 两个 `info.json` 的 executable path 均指向正式 S4 二进制，PID 也与对应格的
  XML 文件名一致；因此“落在正式格窗口”和“可归因我方负载”均确立。

两格 bench/sampler 均退出 `0`、各保留 `41` 个 1 s 样本，JSON/XML 解析和 controller
`DONE_A_*` 均成功，没有证据表明 livedump 改写了堆或导致数据缺失。但生成 live
snapshot 仍是正式窗口内的外部干扰，现有证据不能证明其对调度和系统负载“绝对
零影响”。因而已发布 A 组回收率仍作为可解析、内部自洽的锚点，同时附上
stability-monitor 干扰告警；不将它描述为“已证明完全不受影响”。

### 4.3 非我方观察清单

| 观察 | 归属依据 | 处理 |
|---|---|---|
| `/tmp/505_stack`、`/tmp/505_status`、`/tmp/505_wchan` | uid/gid、PID 与系统 compositor 对应；名称和 SHA 均不匹配任何已发布工具或资产 | 非我方，仅报告，不动 |
| `/var/crash/minicoredumper`、`/var/lib/systemd/coredump` | 镜像系统目录，当前为空，时间早于历轮实验 | 非我方，仅报告，不动 |
| dmesg 中 `oom_control is deprecated`、`oom_adj is deprecated` | 仅为接口弃用提示；严格事件模式零命中 | 非 OOM 事件，仅报告，不动 |

归属不明的文件没有因“看起来可疑”而删除；只有文件名、哈希或内部 executable path 能与
本项目闭环时才进入我方清单。

## 5. 阻断项与处置

| 项目 | 类型 | 处置 | 当前状态 |
|---|---|---|---|
| A 组说明写“最后两行”，实际需读三个摘要行 | 文档笔误 | 改为“最后三行” | 已闭合 |
| C 组命令少打印 payload 与 4 kB 对齐两项，不能匹配指南冻结的 8 行 | 文档漏项，不涉及数据/规格 | 复用指南中同输入的既有计算代码补齐，并在干净 clone 重跑 | 已闭合 |
| 两个 S4 livedump 与空工作根仍在板上 | 演示板卫生阻断 | 先归档校验，再按精确清单清除并二次审计 | **已闭合** |
| stability-monitor 是否纳入后续健康门 | 新规格决策 | 冻结为“前后计数 + 新增归因”；只有我方 PID/二进制新告警为硬失败 | **已闭合** |
| 全新 clone 中无法从公开仓取得 ARM ELF/媒体 | 外部前置 | 本次以本地历轮已验 SHA 归档作为“内部制品交付”的最小假设；指南已明确需 PM/交付方预先给出产物包或 sysroot | **外部依赖，已文档化** |
| `<5 ms` 未指明适用组，字面上会误伤 A 组大释放锚点 | 涉及验收规格 | PM 裁决为释放点 trim（B 组 + gst）单次 `<5 ms`；A 组锚点单列 `<20 ms` 且不是钩子代价 | **已闭合** |
| L2 按轮次删除子目录后会留下空工作根 | 指南清理漏项 | S4/gst 清理段均补 `rmdir /opt/usr/glibc_memopt` 和不存在复核 | **已闭合** |

## 6. 演示日顺序检查单

预计总耗时约 **10–15 分钟**，主要取决于受控重启后 SDB 恢复；四组 L1 本身为秒级。
§4.2 的历史残留已按 PM 裁决清理并二次复核。演示日仍应按下列顺序重做核心卫生门；
若当日复核不通过，只做 host L1，不把该板标成“卫生已通过”。

### 6.1 Host 与版本门

```sh
export REPO=/path/to/glibc_optimization
cd "$REPO"
git fetch origin main
git checkout main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
python3 --version
export OUT
OUT=$(mktemp -d /tmp/glibc-memopt-demo.XXXXXX)
```

预期：`git status --short` 静默；`HEAD` 是 PM 指定演示提交或其后经批准的 main。

### 6.2 受控重启与重新建连

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
sdb connect '<TEST_BOARD_IP>'
sdb -s "$SDB_SERIAL" shell 'date; uptime; rc=$?; echo RC=$rc; if [ $rc -eq 0 ]; then echo DONE_PRE_REBOOT; else echo FAIL_PRE_REBOOT; fi'
sdb -s "$SDB_SERIAL" shell 'reboot'
while ! sdb connect '<TEST_BOARD_IP>' 2>&1 | tee /tmp/demo-board-connect.txt | grep -Eq 'connected|already'; do
  sleep 2
done
sdb devices
```

重启会使 SDB 短暂断开，这是预期行为。若设备序列与预约演示板不一致，停止，不用 IP
代替身份门。

### 6.3 身份门与核心卫生复核

```sh
mkdir -p board_results/demo_rehearsal_20260902/demo_day
sh tools/runners/demo_rehearsal_20260902/read_only_board_audit.sh \
  board_results/demo_rehearsal_20260902/demo_day
grep -Fx IDENTITY_AND_ENV_GATE_PASS \
  board_results/demo_rehearsal_20260902/demo_day/gate_verdict.txt
grep -Fx READ_ONLY_HYGIENE_AUDIT_DONE \
  board_results/demo_rehearsal_20260902/demo_day/audit_verdict.txt
grep -F '=schedutil' \
  board_results/demo_rehearsal_20260902/demo_day/governor_audit.txt
grep -E 'alloc_bench|gst_loop_decode|sample_smaps|reclaim_probe|run_s4|run_gst_trim|cyclic_s2' \
  board_results/demo_rehearsal_20260902/demo_day/process_audit.txt || true
```

人工验收：四个 governor 都是 `schedutil`；项目工作根不存在；上一个 `grep` 无命中；
`df` 仍在基线量级；crash/coredump 无我方文件；严格 dmesg 事件模式的
`EVENT_MATCH_RC=1`。脚本完成只表示采集成功，不会替人工执行归属判断。

### 6.4 连通与资产哈希门

当前正式演示包是 host-only，因此板端资产合同为 `N/A`，不应临时推送任何文件。L1
证据资产由 Git 对象和五个静默 `cmp` 共同核验。若 PM 临时加入 L2，必须先按
[`HQ 复现指南 L2`](demo_reproduction_guide_20260901.md#l2-prerequisites)冻结资产清单与
SHA-256，再另行执行；不得在现场即兴选文件或参数。

```sh
git diff --exit-code
git diff --cached --exit-code
git fsck --no-dangling
sdb -s "$SDB_SERIAL" shell 'date; rc=$?; echo RC=$rc; if [ $rc -eq 0 ]; then echo DONE_BOARD_CONNECTIVITY; else echo FAIL_BOARD_CONNECTIVITY; fi'
```

### 6.5 四组现场 L1

依次照抄 [`Demo 包 §2`](demo_package_20260902.md#2-现场可跑的-l1-复算) 的 A、B、C、D
代码块；不得改输入、口径或期望原文。每组记录 `RC=0`，并核对：

1. A 与 C 的完整 stdout 和复现指南逐字符一致；
2. B 的两个 `cmp` 静默；
3. D 的两行 stdout 逐字符一致，三个 `cmp` 静默；
4. 演示结束执行 `git status --short`，必须仍静默；随后仅删除 host 临时目录。

```sh
git status --short
rm -rf -- "$OUT"
```

`OUT` 由本检查单在 `/tmp/glibc-memopt-demo.XXXXXX` 下创建并明确持有，删除范围仅限该
单一临时目录；板端没有演示资产或工作目录需要清理。

## 7. 复现与验收

### 7.1 Harness 与冻结条件

只读板审计 harness：
[`read_only_board_audit.sh`](../tools/runners/demo_rehearsal_20260902/read_only_board_audit.sh)，
使用方式见同目录 [`README.md`](../tools/runners/demo_rehearsal_20260902/README.md)。冻结身份与
环境条件为：内核名含 `rpi4`、`armv7l`、指定 `BUILD_ID`、
`glibc-2.40-1.6.armv7l`、`MemTotal: 8117408 kB`。L1 冻结命令与期望输出由
[`Demo 包 §2`](demo_package_20260902.md#2-现场可跑的-l1-复算)给出。

### 7.2 确定性项

- 身份与环境五门逐值通过，且每条远端命令含 `RC=0/DONE_*`；
- 四核 governor 均为 `schedutil`；
- 无项目工作目录、我方文件和测试进程；
- 无 08-31 镜像时间后的包安装；
- event-level dmesg 无 OOM/LMK/segfault；
- 每个板上轮次记录 stability-monitor 前后告警清单与计数；v2 实际观测且按预登记
  匹配、完成归档/精确清理/复核后才记 `EXPECTED`，未观测记
  `REGISTERED/NOT-EVALUATED`；未登记我方告警记 `FAIL`，非我方或归属
  不明告警记 `REPORT_ONLY`、只报告不动；模板见
  [`health_gate_template.md`](../tools/reproduce/health_gate_template.md)；
- A/C/D stdout 逐字符一致，B/D 共五个 `cmp` 静默。

### 7.3 容差与人工判定项

- `MemAvailable`、uptime/load 和文件系统 used 值会随重启与系统服务波动；以 zram/swap
  未产生持续压力、可用空间仍处于基线量级为验收，不要求逐值相等；
- crash、`/tmp` 和进程列表必须按归属纪律人工判定，不能把非我方对象批量删除；
- 彩排耗时只用于演示排程，换机、换批次不要求复现，也不进入 Demo 结论。

<a id="l2-hq-rehearsal"></a>
## 8. L2 全程“假扮 HQ”彩排

### 8.1 独立性、前置与计时

在新建临时目录中从 `origin/main` 做全新 clone，确认 `HEAD=1ebbf03`、跟踪文件
无修改。执行期间只阅读 [`HQ 复现指南 L2`](demo_reproduction_guide_20260901.md#l2-run)
及其直接链接的 runner/报告。公开 clone 不包含 ARM ELF 和媒体；本次以本地历轮
已验 SHA 归档充当“内部制品交付”的最小假设后继续。这是外部前置，不是公开
仓的自含能力；指南已补明交付方必须事先提供产物包或 sysroot。

| 前置门 | 冻结值 | 本次 HQ 彩排 | 判定 |
|---|---|---|---|
| 身份/环境 | kernel 含 `rpi4`；`armv7l`；冻结 `BUILD_ID`；`glibc-2.40-1.6.armv7l`；`MemTotal≈8117408 kB` | 清理前、S4 前和 gst 前均重复通过，均有远端 `RC=0/DONE_*` | PASS |
| S4 bench / hist SHA-256 | `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd` / `2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b` | host 与板端逐项相同；因已命中冻结产物，未重建 | PASS |
| gst bench / probe / media SHA-256 | `204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6` / `3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7` / `3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d` | host 与板端逐项相同；因已命中冻结产物，未重建 | PASS |
| governor | 初始/最终四核 `schedutil`，运行态 `performance` | S4、gst 均按该状态机执行并在退出后复核 | PASS |

| 阶段 | 实测墙钟 | 说明 |
|---|---:|---|
| 干净 clone | `1.70 s` | 仅作彩排排程，不进入 Demo 性能结论 |
| S4 前置门 | `0.72 s` | 身份/环境门本身 |
| S4 controller | `851.44 s` | 2 个 A 格 + 8 个 B 格 |
| S4 拉回 / 分析 | `10.61 / 0.05 s` | manifest 校验和 JSON/XML 解析已包含 |
| gst 身份门 / 能力门 | `0.72 / 2.85 s` | 未安装任何包 |
| gst controller | `6511.50 s` | 6 格 × 51 循环 |
| gst 拉回 / 分析 | `85.99 / 0.18 s` | `1922` 文件，零跳过 |

上述计时只用于证明 HQ 执行成本和安排窗口，不进入效果或业务代价结论。

<a id="s4-acceptance"></a>
### 8.2 S4 验收带对照

| 指标 | published 值 | 本次 HQ 彩排值 | 冻结带/规则 | 判定 |
|---|---:|---:|---|---|
| A mixed 瞬时释放回收率 | `51.074077%` | `51.997998%` | `49% ±4 pp` | PASS |
| A medium-only 瞬时释放回收率 | `50.387886%` | `49.278061%` | `49% ±4 pp` | PASS |
| B mixed 三重复中位回收/released | `81.661264%` | `81.661264%` | 锚定发布值 `81.661264% ±5 pp` | PASS |
| B medium-only 三重复中位回收/released | `84.446566%` | `84.446566%` | 锚定发布值 `84.446566% ±5 pp` | PASS；但 rep2 单格中位为 `68.169197%`，不用单格代替预登记的三重复中位规则 |
| B mixed trim 耗时 | 中位 `1.233269 ms` | 中位 `1.309306 ms`，最大 `1.575833 ms` | 释放点 trim 单次 `<5 ms` | PASS |
| B medium-only trim 耗时 | 中位 `1.218361 ms` | 中位 `1.239269 ms`，最大 `1.261981 ms` | 释放点 trim 单次 `<5 ms` | PASS |
| A 组 trim 耗时 | `13.331907/12.723240 ms` | `13.737370/12.438482 ms` | 锚点 trim 单次 `<20 ms`；非钩子代价 | PASS；规格范围已闭合 |
| mixed 下一周期 minflt 增量 | `+1351` | `+1351` | 与回收页数同数量级 | PASS |
| medium-only 下一周期 minflt 增量 | `+1465` | `+1465` | 与回收页数同数量级 | PASS |

确定性项单独验收：

| 项 | published 值 | 本次 HQ 彩排值 | 冻结规则 | 判定 |
|---|---|---|---|---|
| B 组 released payload | mixed `5742256/6566672 B`；medium-only `6288384/6293504 B`，各重复相同 | `16/16` 周期逐字节相同 | 相同 profile/cycle 逐值一致 | PASS |
| B 组 trim 回收量（追加审计） | 12 个 trim 周期的发布 TSV 值 | `10/12` 相同；medium-only/valley/rep2 两周期分别由 `5246976/5378048 B` 变为 `4222976/4354048 B`，各少 `1024000 B` | 明确排除出确定性项；每档三重复中位分别锚定 `81.661264% / 84.446566% ±5 pp` | **字节值不作硬门；同 seed 不钉 arena 指派** |
| 回收量 4 KiB 对齐 | `12/12` | `12/12` | 每个 trim 回收量是 `4096 B` 整数倍 | PASS |
| 下一周期 majflt | `16/16` 为 `0` | `16/16` 为 `0` | 必须为 `0` | PASS |
| zram `orig/compressed/mem_used_total` | `Δ=0/0/0` | `Δ=0/0/0` | 三项必须为 `0` | PASS |
| dmesg OOM/LMK | 增量 `0`，命中 `0` | 增量 `0`，命中 `0` | OOM/LMK 零命中 | PASS |
| bench/sampler/controller | 10 格均完成 | 10 格均 `RC=0/DONE_*` | 远端退出码和 DONE 双门 | PASS |
| stability-monitor v1（历史原判） | 发布时未列为健康门；事后发现两个可归属告警 | `0 → 2`；新增件均指向本轮 S4 bench | 新增且可归因本轮即硬失败 | **HARD FAIL（保留，不改写）** |
| stability-monitor v2（2026-09-02 追注） | 同上；两件均为 A 组 `alloc_bench` 的 `cpu.relative`，分别落在 mixed/medium-only 正式窗口 | `0 → 2`；等于登记上界，已归档、精确删除并复核为 `0` | known-alert waiver：理由 + 窗口 + owner + 数量上界匹配登记项；触发/窗口可复现，未做根因证明 | **EXPECTED；健康门通过** |

两个新告警分别落在本次 `A/mixed` 和 `A/medium-only` 窗口，触发理由仍是
`cpu.relative` 略高于阈值。ZIP 已拉回本地并校验，板上按精确哈希二次确认后删除。
v1 下 S4 数值分析可用但整体健康门不通过；该历史结论保留。按随后生效的 v2 规则，
两件告警匹配首条预登记且已完成归档/清理，因此为 `EXPECTED` 通过。两套结论对应不同
规则版本，不互相覆盖。

### 8.3 gst 验收带对照

| 指标 | published 值 | 本次 HQ 彩排值 | 冻结带/规则 | 判定 |
|---|---:|---:|---|---|
| trim 与 none 的 p99 中位差 | `+6.228611 ms` | `+2.343963 ms` | 硬校验规则执行；方向只报告 | `REPORT_ONLY`；仍为 `false` |
| none p99 重复离散 | `6.784167 ms` | `5.903519 ms` | 预登记比较带 | 用于上行判定 |
| 153 次 trim p50/p95/p99/max | `0.671556/0.818315/0.842185/0.856944 ms` | `0.666944/0.842963/0.910444/0.932537 ms` | 完整报告；单次 `<5 ms` | PASS |
| 三格首次 release | `51.014041–51.406250%` / `1.277344–1.285156 MiB` | `51.250000–51.486698%` / `1.281250–1.285156 MiB` | 与既有约半数、约 `1.3 MiB` 量级作相容性对照，无新设百分比硬带 | 相容 |

gst 确定性项：

| 项 | published 值 | 本次 HQ 彩排值 | 冻结规则 | 判定 |
|---|---|---|---|---|
| 资产 SHA | 三个冻结 SHA | 三项 host/板端逐字一致 | 必须逐字一致 | PASS |
| 格/周期/主样本 | `6×51=306` / `300` | `6×51=306` / `300` | 格顺序、循环数、每重复 50 个主样本齐全 | PASS |
| JSON/PID | `306` 对可解析、格内 PID 恒定 | `306` 对可解析、格内 PID 恒定 | 全量通过 | PASS |
| trim/none 合同 | `153` 次调用 / `153` 个未调用哨兵 | `153` / `153` | 数量逐项一致 | PASS |
| majflt | 目标内和外部 1 s 序列均为 `0`；旧 capture-meta 为已知 `S0` | 目标内、capture-meta、外部 1 s 序列均为数值 `0` | 发布版 harness 的 capture-meta 不得再为 `S0`；其余必须为 `0` | PASS |
| zram 三项 | `Δ=0/0/0` | `Δ=0/0/0` | 必须为 `0` | PASS |
| dmesg OOM/LMK | 增量 `0`，命中 `0` | 增量 `0`，命中 `0` | 零命中 | PASS |
| stability-monitor | 历史 gst 未发现可归属残留 | `0 → 0` | 可归因本轮新增件为硬失败 | PASS |
| 退出/清理 | 全格退出 0、governor 恢复、轮次目录删除 | 全格退出 0；项目工作根也删除；governor 四核 `schedutil` | RC/DONE、目录、进程和 governor 全部闭合 | PASS |

本次 capture-meta 已全批为数值 `0`，不再出现发布批的旧 `S0` 字段缺陷。

### 8.4 指南阻断项、直接修正与最终现场

| 发现 | 是否需要文档外知识 | 处置 |
|---|---|---|
| 公开 clone 不含 ARM ELF/媒体，指南又不可能公开内部制品库坐标 | 是 | 用已验本地归档做最小假设继续；指南明确它是 PM/交付方必须预供的外部前置 |
| S4 `<5 ms` 字面未限定 B 组，会与已发布 A 组约 `13 ms` 相冲突 | 否，可由指南链接证据自证 | PM 已裁决：B 组/gst `<5 ms`，A 组 `<20 ms` 且不作钩子代价；指南与机器配置已同步 |
| 清理段只删轮次子目录，会留空项目根 | 否 | S4/gst 都补精确 `rmdir` 和复核 |
| 指南未含 stability-monitor 前后计数与归因 | 否，PM 已冻结规则 | 写入 L2 健康门和后续板上报告模板 |

最终复核：`/opt/usr/glibc_memopt` 不存在，无 `alloc_bench`/`gst_loop_decode`/
采样器进程，四核 governor 均为 `schedutil`，stability-monitor 归档计数为 `0`，
`RC=0/DONE_FINAL_BOARD_HYGIENE`。

## 9. 原始件与公开边界

完整命令记录、全量 `ps`、包列表、目录清单和带真实连接标识的原始输出保留在本地
`board_results/demo_rehearsal_20260902/`，不推公开仓库。本报告只收录能支持裁决的紧凑、
脱敏摘录。L2 彩排数值只用于本报告的复现验收，不替换公开 Demo 头条数字；
彩排计时也不进入机制、效果或业务代价结论。
