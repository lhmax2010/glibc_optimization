> Public archive note: application/process names are aliases. Board identifiers,
> image delivery paths, and local filesystem paths are sanitized.

# Demo 彩排与演示板卫生审计

- 日期：2026-09-02
- 演示板：`<TEST_BOARD_IP>:26101`（SDB）
- 演示入口：[`demo_package_20260902.md`](demo_package_20260902.md)
- 基线：[`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md)
- 可执行审计件：[`tools/runners/demo_rehearsal_20260902/`](../tools/runners/demo_rehearsal_20260902/)
- 约束：L1 在独立干净 clone 中执行；板端仅做只读探查，不推送、不建目录、不运行负载、
  不改 governor、不装卸包、不重启、不清理

## 1. 结论先行

1. **四组 L1 演示在当前文档修正后全部可现场执行。** A、C、D 的标准输出与复现指南
   冻结原文逐字符一致；B 的两个 `cmp`、D 的三个 `cmp` 均静默成功。发现并直接修正了
   两处不涉及规格或结论数字的文档问题：A 的“最后两行”改为“最后三行”；C 补上复现
   指南已经要求的 released-payload 与 4 kB 对齐两行输出。
2. **板身份与环境门通过。** 内核含 `rpi4`、架构严格为 `armv7l`、`BUILD_ID`、glibc
   和 `MemTotal` 均与 2026-08-31 基线一致。
3. **演示板卫生门暂未闭合。** 工作目录只剩空的 `/opt/usr/glibc_memopt`，但 crash
   目录中有两个可由内部元数据精确归属到 S4 `alloc_bench` 的 stability-monitor
   livedump。二者已列入“我方残留，建议清除”，等待 PM 批准；本轮没有删除。
4. **没有运行板上演示负载。** 当前演示包明确规定四组现场命令均为 host-only，因而
   不存在需要彩排的板上现场段；同时卫生清理尚未获批，也不满足进入可选板上段的前提。
5. livedump 表明 stability-monitor 在 S4 期间因 `cpu.relative` 阈值生成了现场快照，
   并非本轮发现仍有测试进程，也没有 OOM/LMK/segfault 事件。这不改变已发布 Demo 数字；
   是否把 stability-monitor 零告警加入后续板上健康门，属于新的规格选择，留给 PM 裁决。

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

五项均通过，与[新 LLVM 镜像基线](board_baseline_llvm_image_20260831.md#4-新镜像环境基线)
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
| `/opt/usr/glibc_memopt` | 固定项目工作根；内部为空；mtime 位于 gst 轮完成后 | 在两个 livedump 处置后用精确 `rmdir` 删除 | 等 PM 批准，未执行 |
| `/opt/usr/share/crash/livedump/alloc_bench.armv7l_31200_20260901172715.zip` | `info.json` 的 executable path 指向 S4 工作目录；大小 `359978 B`；SHA-256 `0a5a8780c0edb2427795330123fe6715b5157933c738a32b0ebe09168799cfa0` | 精确文件名删除 | 等 PM 批准，未执行 |
| `/opt/usr/share/crash/livedump/alloc_bench.armv7l_31971_20260901172754.zip` | 同上；大小 `361579 B`；SHA-256 `fd7a56db8385f4066e7181f0970bf5d100c125d6145e42f08a959ca51bb0661e` | 精确文件名删除 | 等 PM 批准，未执行 |

两个压缩包的 `dump_reason` 分别报告 `cpu.relative` 实际值 `3.8203134021870864` 和
`3.8165405446011791` 超过允许值 `3.7999999999999998`；调用栈停在
`usleep`/`nanosleep`。它们是 stability-monitor 生成的 live snapshot，不是仍存活进程；
但作为历轮落盘物仍应清除。建议批准后只执行下列精确命令，不使用通配符：

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
sdb -s "$SDB_SERIAL" shell '
rm -f /opt/usr/share/crash/livedump/alloc_bench.armv7l_31200_20260901172715.zip \
      /opt/usr/share/crash/livedump/alloc_bench.armv7l_31971_20260901172754.zip
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
| 两个 S4 livedump 与空工作根仍在板上 | 演示板卫生阻断 | 等 PM 批准后按精确清单清除并二次审计 | **开放** |
| stability-monitor 是否纳入后续“零平台告警”健康门 | 新规格决策 | 不回改 S4 数字或结论，等 PM 裁决 | **开放，不阻断 host Demo** |

## 6. 演示日顺序检查单

预计总耗时约 **10–15 分钟**，主要取决于受控重启后 SDB 恢复；四组 L1 本身为秒级。
下列命令按顺序执行。先由 PM 批准并完成 §4.2 的精确清理；若未批准或二次审计不通过，
只做 host L1，不把该板标成“卫生已通过”。

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
- A/C/D stdout 逐字符一致，B/D 共五个 `cmp` 静默。

### 7.3 容差与人工判定项

- `MemAvailable`、uptime/load 和文件系统 used 值会随重启与系统服务波动；以 zram/swap
  未产生持续压力、可用空间仍处于基线量级为验收，不要求逐值相等；
- crash、`/tmp` 和进程列表必须按归属纪律人工判定，不能把非我方对象批量删除；
- 彩排耗时只用于演示排程，换机、换批次不要求复现，也不进入 Demo 结论。

## 8. 原始件与公开边界

完整命令记录、全量 `ps`、包列表、目录清单和带真实连接标识的原始输出保留在本地
`board_results/demo_rehearsal_20260902/`，不推公开仓库。本报告只收录能支持裁决的紧凑、
脱敏摘录；本轮没有产生新的 Demo 测量数字。
