> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# PG0 决定性事实探测（TV `.26`）

- 日期：2026-08-06（Q3：11:36:07–11:42:23 UTC）
- 通道：`ssh -T root@<PRODUCT_BOARD_IP>`，root，keyboard-interactive，无 PTY；`.26` 无 sdb
- 方法：Q1 从侦察 3 冻结 TSV 提取并用当前 `/proc/PID/auxv` 复核；Q2 比较 pool/child 的初始环境并反查 systemd；Q3 在 `/dev/shm` 写 30% 气球并每 10 s 采样
- 原始证据根目录：`board_results/pg0_decisive_probe_20260806/`

执行入口（口令未写入命令或报告）：

```sh
ssh -T root@<PRODUCT_BOARD_IP> 'sh -s' < collect_q1_q2.sh
scp -O -r root@<PRODUCT_BOARD_IP>:/tmp/pg0_decisive_probe ...
ssh -T root@<PRODUCT_BOARD_IP> 'sh -s' < collect_q3.sh
scp -O -r root@<PRODUCT_BOARD_IP>:/tmp/pg0_decisive_probe ...
```

Q1/Q2、Q3 的 SSH 退出码均为 0；递归 pull 退出码均为 0。第一次用非递归通配符 pull 时因 `q2_env` 是目录返回 1，随后改为 `scp -O -r` 完整拉回 25 个 Q1/Q2 文件；该传输异常未影响板侧采集。

## 1. 板身份自检

两个采集脚本和清理脚本均在任何采集/写 tmpfs 前执行以下门：

```text
IDENTITY_OK=PRODUCT_BOARD
kernel=6.12.60
NAME=Tizen
VERSION="10.0.0 (<PRODUCT_IMAGE>)"
PRETTY_NAME="<PRODUCT_IMAGE>"
BUILD_ID=<PRODUCT_BUILD_ID>
```

脚本同时拒绝 `rpi4`、`unified-dev`、非 `6.12.60` 和非 `<PRODUCT_IMAGE>`。证据：`raw/q1_q2_complete/identity.out`。

**解锁 v3 的决策：** 本报告数据属于 TV 产品板 `.26`，不是 RPI4 `.25`。

## 2. Q1：Top 目标的 AT_SECURE

“glibc 堆量”沿用侦察 3 的同口径值：`[heap]` 加 1 MiB 对齐 arena-like 匿名段的 `Private_Dirty`。这是冻结快照堆量，本轮只复核 AT_SECURE。

| 目标 | 侦察 3 PID / AT_SECURE | 当前 PID / AT_SECURE | glibc 堆量（kB；占总 Private_Dirty） | GLIBC_TUNABLES env 可达性事实 |
|---|---:|---:|---:|---|
| `AppProcB` | 2556 / 1 | 2556 / 1 | 14,872；44.5% | AT_SECURE=1；glibc tunables 不生效；无 per-app unit |
| `AppProcD` | 562 / 1 | 562 / 1 | 10,080；28.4% | AT_SECURE=1；glibc tunables 不生效；无 per-app unit |
| `ServiceE` | 572 / 1 | 572 / 1 | 7,912；40.6% | AT_SECURE=1；glibc tunables 不生效；无 per-app unit |
| `AppProcA` | 3772 / 1 | 3772 / 1 | 4,960；37.3% | AT_SECURE=1；glibc tunables 不生效；无 per-app unit |
| `ServiceH` | 4042 / 1 | 3999 / 1 | 3,412；31.2% | AT_SECURE=1；glibc tunables 不生效；无 per-app unit |
| `ServiceD` | 1048 / 0 | 1048 / 0 | 1,948；25.5% | AT_SECURE=0；pool 直接子进程；无 per-app unit，pool 也无 unit |
| `ServiceL` | 613 / 0 | 613 / 0 | 964；23.7% | AT_SECURE=0；pool 直接子进程；无 per-app unit，pool 也无 unit |
| `enlightenment` | 265 / 0 | 265 / 0 | 2,936；20.4% | AT_SECURE=0；`init.scope`，无独立 service unit |
| `ServiceF` | 1595 / 0 | 1595 / 0 | 996；14.9% | AT_SECURE=0；`issue_report_agent.service` |
| `ServiceC` | 669 / 0 | 669 / 0 | 1,072；15.7% | AT_SECURE=0；`ServiceG.service` |

10/10 个 AT_SECURE 值与侦察 3 TSV 一致；只有 `ServiceH` PID 从 4042 变为 3999。冻结源：`board_results/tv_recon3_20260806/product_board/final_pull/tv_recon3_product_board/c0_inventory.tsv`；当前原始值：`raw/q1_q2_complete/q1_current.tsv`；合并核对：`derived/q1_comparison.tsv`。

**解锁 v3 的决策：** 五个高堆量 launchpad 目标为 AT_SECURE=1；AT_SECURE=0 且有独立 systemd unit 的表内目标只有 `ServiceF` 和 `ServiceC`。表中其余 AT_SECURE=0 目标没有已证实的 systemd drop-in 注入点。

## 3. Q2：launchpad env 继承与 unit 反查

### 3.1 拓扑

```text
pool_pid=255
pool_ppid=241
pool_exe=/usr/bin/ServiceJ
pool_cmdline=/usr/bin/ServiceJ
pool cgroup: .../init.scope

parent_exe=/usr/bin/bash
parent_cmdline=/bin/sh /usr/bin/ServiceJ.sh init
parent cgroup: .../init.scope
```

`AppProcB`、`AppProcD`、`ServiceE`、`AppProcA`、`ServiceH`、`ServiceD`、`ServiceL` 当前 PPID 均为 255，都是 pool 的直接子进程。证据：`raw/q1_q2_complete/q2_pool.out`、`q2_children.tsv`。

### 3.2 环境差集

pool 有 84 个唯一变量名。每个 child 都保留其中 83 个；pool 有而 child 无的差集对七个 child 完全相同：

```text
AppProcB:  LD_USE_LOAD_BIAS=1
AppProcD: LD_USE_LOAD_BIAS=1
ServiceE:      LD_USE_LOAD_BIAS=1
AppProcA: LD_USE_LOAD_BIAS=1
ServiceH:   LD_USE_LOAD_BIAS=1
ServiceD:    LD_USE_LOAD_BIAS=1
ServiceL:       LD_USE_LOAD_BIAS=1
```

child 的唯一变量总数分别为 85、112、85、85、85、113、110；因此这是“继承 83/84 个 pool 变量并增加 app 变量”，不是清空整个环境。唯一实测到的 pool→child 过滤项属于 `LD_*`。pool 没有任何 `GLIBC_*` 变量，所以本次零注入观察无法判定 `GLIBC_TUNABLES` 是否另有专门过滤规则。逐 child 原始差集：`derived/q2_diffs/*_pool_only.txt`；完整 NUL 转行并排序后的环境：`raw/q1_q2_complete/q2_env/`。

### 3.3 systemd/login 反查原文

```text
--- list-units launchpad ---
● wrt_launchpad_daemon.service  not-found inactive dead
--- list-unit-files launchpad ---
NONE
--- status pool PID ---
Failed to get unit for PID 255: PID 255 does not belong to any loaded unit.
--- status pool parent PID ---
Failed to get unit for PID 241: PID 241 does not belong to any loaded unit.
--- service MainPID/ControlPID matches ---
[无输出]
--- loginctl list-sessions ---
sh: line 160: loginctl: command not found
```

`systemctl status/cat 'ServiceJ*'` 无匹配 unit；遍历所有 service 的 MainPID/ControlPID 也没有匹配 PID 255/241。`loginctl` 不存在，故 login session 侧没有额外结果。完整原文：`raw/q1_q2_complete/q2_unit_loginctl.out`。

**解锁 v3 的决策：** pool 环境继承成立（83/84），同时存在 `LD_USE_LOAD_BIAS` 的选择性消失；没有 broad `clearenv` 证据。pool 和父进程均无 systemd unit/drop-in 路径；`GLIBC_TUNABLES` 专项过滤仍未被零注入数据覆盖。

## 4. Q3：PSI 保持态与压力源

### 4.1 安全门结果：本次 Q3 作废

Q3 开始前的 dmesg 基线已经含持续的 `.NET TP Worker` SIG11。基线最后一组在 uptime `11284.022711/11284.022743`；基线快照结束于 `11284.492975`。此后第一组新增信号在 `11289.023404/11289.023432`，即约 4.53 s 后。

整个 Q3 期间合并各 10 s dmesg 快照并去重，得到 **150 行新增 SIG11（75 组双行报告）**，最后一组在 uptime `11659.020419/11659.020450`；涉及 `.NET TP Worker` PID 1575 和 3602。未发现新增 LMK/OOM 行。原文全集：`derived/q3_new_fatal_lmk_events.txt`。

板上安全检查错误地比较“当前匹配行总数是否大于基线 60”。高频 kernel log 使 ring buffer 轮转，计数先降到 58，后来回到 60，因此没有触发停止，Q3 脚本最终错误地返回 0。按照任务的硬规则“任何同类 fatal signal 即作废该档”，**随机页档、5 分钟保持曲线以及基于它们的 PSI 指标选择全部作废**。发现该问题后没有再次施压。

### 4.2 作废运行的原始零页/随机页观测

以下只保留为取证，不作为有效对比结果：

| 状态 | 气球 | MemAvailable before→after (kB) | 下降 (kB) | swap used (kB) | zram `orig/compr/mem_used` |
|---|---:|---:|---:|---:|---|
| 零页 | 282 MiB | 965,592→667,180 | 298,412 | 54,892→54,892 | `46116864/9236322/16166912`，不变 |
| 随机页 | 280 MiB | 956,016→664,376 | 291,640 | 54,892→54,892 | `46116864/9236322/16166912`，不变 |

零页写入和采样在 0.74 s 内完成，并在第一条基线后新增 SIG11 之前删除；该单点显示零页文件确实按约 282 MiB 量级降低 MemAvailable，且当时没有进入 swap/zram。随机页写入耗时 5.07 s，发生在持续 SIG11 时段，故两者比较不满足安全门。

随机气球删除后 30 s：MemAvailable 943,816 kB；板侧报告 `BALLOON_CLEANUP_OK`。原始状态块：`raw/q3_complete/q3.out`。

### 4.3 作废的 5 分钟原始时间序列

原始 collector 把前三列标题写成了 avg10/60/300，但板上实际字段和值自带标签为 avg2/6/10；下表仅校正标题，数值未改。文件：`derived/q3_timeseries_corrected.tsv`。

```text
elapsed_s  utc                   MemAvail_kB  swap_used  zram_orig  zram_compr  zram_mem  some_avg2/6/10  some_total  full_avg2/6/10  full_total
0          2026-08-06T11:36:44Z  663768       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
10         2026-08-06T11:36:55Z  668308       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
20         2026-08-06T11:37:05Z  671816       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
30         2026-08-06T11:37:15Z  672188       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
40         2026-08-06T11:37:25Z  672608       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
50         2026-08-06T11:37:36Z  672148       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
60         2026-08-06T11:37:46Z  671092       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
70         2026-08-06T11:37:56Z  669756       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
80         2026-08-06T11:38:06Z  669136       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
90         2026-08-06T11:38:17Z  669208       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
100        2026-08-06T11:38:27Z  668468       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
110        2026-08-06T11:38:37Z  668108       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
120        2026-08-06T11:38:47Z  667696       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
130        2026-08-06T11:38:58Z  666952       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
140        2026-08-06T11:39:08Z  666376       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
150        2026-08-06T11:39:18Z  666104       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
160        2026-08-06T11:39:29Z  665148       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
170        2026-08-06T11:39:39Z  664840       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
180        2026-08-06T11:39:49Z  663596       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
190        2026-08-06T11:39:59Z  663172       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
200        2026-08-06T11:40:10Z  662804       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
210        2026-08-06T11:40:20Z  662292       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
220        2026-08-06T11:40:30Z  660980       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
230        2026-08-06T11:40:40Z  660808       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
240        2026-08-06T11:40:51Z  660844       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
250        2026-08-06T11:41:01Z  660456       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
260        2026-08-06T11:41:11Z  659892       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
270        2026-08-06T11:41:21Z  659428       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
280        2026-08-06T11:41:32Z  658524       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
290        2026-08-06T11:41:42Z  658004       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
300        2026-08-06T11:41:52Z  657128       54892      46116864   9236322     16166912  0/0/0            2286590     0/0/0            1504018
```

作废曲线的原始描述值：MemAvailable 最小 657,128 kB、最大 672,608 kB、极差 15,480 kB；swap/zram 全程不变；some/full 的 avg2/6/10 全为 0，`some.total` 增量 0，`full.total` 增量 0。

**Q3 事实结论及解锁状态：** 零页单点未被 zram 吃掉；零页与随机页的有效对比、5 分钟保持态、PSI 主指标选择均因持续 SIG11 不满足安全门，无法从本轮定案。该事实阻止 v3 把本轮作废曲线作为 PSI 协议依据。

## 5. 收尾证据

```text
IDENTITY_OK=PRODUCT_BOARD
kernel=6.12.60
PG0_TMP_CLEAN
PG0_BALLOONS_CLEAN
REMOTE_CLEANUP_RC=0
FINAL_CLEANUP_VERIFY_RC=0
```

未重启 service，未写持久位置。`/tmp/pg0_decisive_probe`、清理证据临时文件及 `/dev/shm/.pg0_zero_*`、`/dev/shm/.pg0_random_*` 均已删除。
