> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# 真实 UI 目标的释放相位 L6 测量

采集日期：2026-08-12（host CST）/ 2026-08-13（板上 JST）

板：当前 `<TEST_BOARD_IP>` 的 RPI4 测试板

通道：`sdb -s <TEST_BOARD_IP>:26101`，root 模式
原始数据根：`board_results/l6_ui_release_phase_20260812/`

本报告只记录事实与合同定义的派生量，不作上线裁决。

## 1. 环境确认

### 1.1 身份门

身份门通过。原文：

```text
IDENTITY_OK
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Tue Jul 28 02:41:25 UTC 2026 armv7l GNU/Linux
VERSION="11.0.0 (Tizen11.0/Unified)"
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
```

`/etc/os-release` 不含 `<PRODUCT_IMAGE>`，因此本轮不是 TV 产品板。

### 1.2 glibc、协变量与图形栈

| 项 | 实测值 |
|---|---|
| glibc RPM | `glibc-2.40-2.8.armv7l` |
| libc | GNU libc 2.40；GNU CC 14.2.0 |
| libc SHA-256 | `d5e36dd6339e95adedcbb01b655bc3df46d233fbba5d98f24105192eb8935015` |
| MemTotal / 初始 MemAvailable | 3,976,480 / 3,406,732 kB |
| swap/zram | `/dev/zram0` 1,590,588 kB；Used 0 |
| zram `mm_stat` 首三项 | `4096 74 4096` |
| CPU | 4 核，online `0-3` |
| governor | 四核均为 `schedutil`，本轮未修改 |
| compositor | `display-manager` active/running，MainPID 2600，`NRestarts=3050` |
| Wayland | `/run/wayland-0` 存在 |
| 初始目标 | AppUIA PID 2542；AppUIB PID 2743 |

glibc release 与本轮要求的 `2.40-2.8` 一致。历史 AppUIA/AppUIB
静置态数据来自另一镜像 `<TEST_IMAGE_A>`、glibc `2.40-3.12`，不能视为
同镜像复测。

### 1.3 LLDB 最小验证

临时 LLDB 为 22.1.8。`sleep 300` 验证原文：

```text
SLEEP_PID=10268
(lldb) expr -t 5000000 -- (int)getpid()
(int) $0 = 10268
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $1 = 1
(lldb) detach
Process 10268 detached
LLDB_RC=0
SLEEP_ALIVE_AFTER=1
```

正式 `malloc_info` attach 前均先独立执行 `thread list` + `bt all`。选用的
thread #1 在 AppUIB 中停于 Ecore `poll()` 主循环，在 AppUIA 中停于
`.NET`/Ecore `poll()` 主循环；记录的所选栈中没有 malloc/free/realloc 帧。

## 2. M7 口径与动作

`rest` 取 `malloc_info` XML 的全局末行 `<total type="rest">`；`unsorted`
为各 heap `<unsorted total>` 求和。只有观察到与释放动作一致的显著空闲字节
增长，才确认 M7 并允许 trim。受控 GStreamer 参考中，每路 `rest` 增长约
2.15 MiB、`unsorted` 增长约 1.7-2.0 MiB。

| 目标 | 分配/活动相 | 释放相 | 每轮新鲜态 |
|---|---|---|---|
| AppUIB | 依次启动 keyboard setting、ISE setting、NUI gadget viewer、share panel、account setting，间隔 3 s；三轮均 5/5 进入 running | 逐个 `app_launcher -t`，再等 10 s | 三轮 PID 19825 / 20607 / 21210 |
| AppUIA | 连续 5 次启动 `tizen.syspopup`，每次传入不同 message，间隔 1 s；每轮 5/5 返回当轮 AppUIA PID | T1 与其 `malloc_info` 采集完成后再等约 22 s 采 T2；gadget 在此期间自动关闭 | 三轮 PID 22504 / 22907 / 23862 |
| Chromium | `AppUIC -v -n file:///tmp/l6_ui_heavy_release.html`；页面设计为 5 s 后进入 heavy、30 s 后导航 `about:blank#L6_UI_RELEASED` | 页面导航未实际发生 | 无有效释放相位，不进入 n=3/注入 |

## 3. AppUIB

三分类均为 Private_Dirty，单位 MiB。

| rep | 点 | glibc-heap | other-anon | file-backed | total |
|---:|---|---:|---:|---:|---:|
| 1 | T0 | 9.594 | 17.445 | 3.227 | 30.266 |
| 1 | T1 | 9.055 | 15.824 | 3.227 | 28.105 |
| 1 | T2 | 9.055 | 16.418 | 3.250 | 28.723 |
| 2 | T0 | 10.145 | 16.816 | 3.227 | 30.188 |
| 2 | T1 | 9.770 | 15.457 | 3.227 | 28.453 |
| 2 | T2 | 9.605 | 15.742 | 3.250 | 28.598 |
| 3 | T0 | 9.594 | 17.422 | 3.227 | 30.242 |
| 3 | T1 | 9.051 | 15.805 | 3.227 | 28.082 |
| 3 | T2 | 9.059 | 16.406 | 3.250 | 28.715 |

### 3.1 M7 证据

| rep | T1 rest | T2 rest | rest 增量 | T1 unsorted | T2 unsorted | unsorted 增量 | M7 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 1,788,739 | 1,761,181 | -27,558 | 20,138 | 78,578 | +58,440 | 未确认 |
| 2 | 1,792,925 | 1,759,329 | -33,596 | 452,052 | 63,233 | -388,819 | 未确认 |
| 3 | 1,776,931 | 1,746,015 | -30,916 | 17,471 | 68,155 | +50,684 | 未确认 |

三轮全局 rest 均下降，没有观察到空闲字节增长。按 M7 合同，三轮均未调用
`malloc_trim(0)`，因此 `A_ceiling`、回收比例、`trim_return` 与 T4-T5 代价
均为 n/a。

## 4. AppUIA

三分类均为 Private_Dirty，单位 MiB。下表是 host 审核 M7 的干净重测，
三轮均未注入。

| rep | 点 | glibc-heap | other-anon | file-backed | total |
|---:|---|---:|---:|---:|---:|
| 1 | T0 | 5.395 | 12.238 | 2.047 | 19.680 |
| 1 | T1 | 5.395 | 12.246 | 2.047 | 19.688 |
| 1 | T2 | 5.395 | 12.250 | 2.070 | 19.715 |
| 2 | T0 | 5.449 | 12.238 | 2.047 | 19.734 |
| 2 | T1 | 5.449 | 12.246 | 2.047 | 19.742 |
| 2 | T2 | 5.449 | 12.250 | 2.070 | 19.770 |
| 3 | T0 | 5.395 | 12.242 | 2.047 | 19.684 |
| 3 | T1 | 5.395 | 12.250 | 2.047 | 19.691 |
| 3 | T2 | 5.395 | 12.254 | 2.070 | 19.719 |

### 4.1 M7 证据

| rep | T1 rest | T2 rest | rest 增量 | T1 unsorted | T2 unsorted | unsorted 增量 | M7 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 2,082,798 | 2,089,929 | +7,131 | 429,978 | 430,371 | +393 | 未确认 |
| 2 | 2,153,726 | 2,160,632 | +6,906 | 429,919 | 430,247 | +328 | 未确认 |
| 3 | 2,083,458 | 2,090,535 | +7,077 | 429,290 | 429,778 | +488 | 未确认 |

三轮 action 原文均为 5 次 `test successful ret = <当轮 AppUIA PID>`。
T1-T2 增长只有数百字节 unsorted 和约 7 KiB rest，不构成参考释放相位中
MiB 级空闲字节增长。host 审核未确认 M7，三轮均未调用 trim，故正式
`A_ceiling` 与代价项为 n/a。

## 5. Chromium

### 5.1 页面真实性门

正式只读复现拉起主进程 PID 25408 与 renderer PID 25440。加载原文：

```text
ewk_view_url_set(...): url: file:///tmp/l6_ui_heavy_release.html
LoadProgressChanged(...): progress : 0.1
LOAD_PROGRESS_1=0
RELEASE_NAVIGATION_VERIFIED=0
```

37 s 内没有 `LoadProgress=1`、`DidFinishLoad`、`L6_UI_HEAVY` 或
`about:blank#L6_UI_RELEASED` 证据。另一路 app-control rehearsal 虽返回 PID，
但实际加载 URL 为占位主机名 `http://<LAUNCH_TOKEN>/`，不是指定文件。

### 5.2 只读画像

三分类均为 Private_Dirty，单位 MiB。

| 进程 | 点 | glibc-heap | other-anon | file-backed | total |
|---|---|---:|---:|---:|---:|
| main 25408 | P12 | 11.070 | 5.047 | 9.320 | 25.438 |
| main 25408 | P37 | 11.070 | 5.047 | 9.320 | 25.438 |
| renderer 25440 | P12 | 0.996 | 1.273 | 0.457 | 2.727 |
| renderer 25440 | P37 | 0.996 | 1.273 | 0.457 | 2.727 |

两时点的三类 Private_Dirty 完全相同。由于重页面和 blank 导航均未发生，
Chromium 没有可审核的 T1/T2，更没有 M7；按合同不注入、不填名义值。

## 6. 核心结果与对照

| 目标 | M7 | 释放相位 `A_ceiling` | 回收比例 | trim_return | refault/代价 |
|---|---|---:|---:|---:|---|
| AppUIB | 3/3 未确认 | n/a | n/a | n/a | n/a，未 trim |
| AppUIA | 3/3 未确认 | n/a | n/a | n/a | n/a，未 trim |
| Chromium main/renderer | 页面加载与释放导航未验证 | n/a | n/a | n/a | n/a，未 trim |

| 目标 | 本轮释放相位 | 历史静置态 | 受控 GStreamer 基准 | 可比性 |
|---|---:|---:|---:|---|
| AppUIB | n/a，M7 未确认 | 0.438 MiB / 5.03% | 约 49% | 历史值来自 `<TEST_IMAGE_A>` / glibc 2.40-3.12；本轮为 toolchain_20260728 / 2.40-2.8 |
| AppUIA | n/a，M7 未确认 | 0.219 MiB / 4.48% | 约 49% | 同上 |
| Chromium | n/a，页面门未过 | 0.019531 MiB / 0.196% | 约 49% | 历史 Chromium 数据来自不同镜像；本轮页面未加载 |

受控 GStreamer 49% 来自与本轮相同 BUILD_ID、glibc `2.40-2.8` 的
`docs/l6_release_phase_scale.md`；这里只并列口径，不把该比例代入 UI 目标。

## 7. 失败、偏差与限制

1. AppUIB 的首次执行器尝试把 `malloc_info` XML 写到 `/root`。表达式在
   `<USER>` 目标权限下运行，`fopen` 返回空指针，随后 LLDB 表达式触发 SIGSEGV；
   LLDB 原文称进程已恢复到表达式执行前状态。该轮在 T1 中止，未到 T2、未
   trim；随后改为 `/tmp` 落盘、复制回证据目录并立即删除。原始证据保存在
   `runs/AppUIB/rep1_attempt1/`。
2. AppUIA 初版自动门把 `8-40 B` unsorted 与约 `4 KiB` rest 的微小正波动
   当成显著增长，导致两个尝试轮调用了 trim。两轮 `trim_return=1`，glibc
   分类 PD 均下降 368,640 B，但 M7 不成立，故这些调用和数值全部作废，不计入
   正式表。原始证据保存在 `runs/systemui/rep{1,3}_attempt_auto_gate/`。正式三轮
   改为 host 审核，均未注入。
3. Chromium 只读脚本在核心数据采完后因 POSIX `sh` 函数变量覆盖，未能在其
   自身目录写入最终 dmesg/DONE 标记；进程清理与 `health_after.txt` 已先完成。
   随后独立收尾确认无 Chromium、compositor active，故页面门和 P12/P37 数据
   保留；脚本尾部完整性问题记录为异常。
4. AppUIB 的五个外部 app 都在 T1 前确认 running；清理时其中一个已自行
   退出，因此每轮只有四条成功 terminate 原文。最终均不在 app status。
5. 三个目标都没有通过 M7，因此本轮没有合规的 T4/T5；无法给出真实 UI 释放
   相位的 trim 停顿、minflt/majflt、zram 换入或 utime/stime 代价。
6. 六个正式 UI 轮次的 dmesg alert 文件均为空；没有观察到 LMK/OOM/fatal。

## 8. 恢复现场

收尾原文：

```text
ROOT_TEMP_ABSENT
TMP_L6_UI_COUNT=0
glibc-2.40-2.8.armv7l
active
MainPID=2600
Result=success
NRestarts=3050
AppQ (21210)
AppX (23862)
Swap: 1590588 0 1590588
```

`/root/l6uirelease` 与 `/tmp/l6_ui*` 已全部删除。临时 LLDB 运行库、脚本、HTML
和 XML 均不再留在板上；没有安装包、没有持久配置改动。收尾时 zram 仍 Used 0，
compositor 的 `NRestarts` 与开场同为 3050。

## 9. 原始文件清单

- 环境与 LLDB：`board_results/l6_ui_release_phase_20260812/stage0/`
- 入口探查与 rehearsal：`board_results/l6_ui_release_phase_20260812/prescreen/`
- AppUIB 正式三轮：`board_results/l6_ui_release_phase_20260812/runs/AppUIB/rep{1,2,3}/`
- AppUIA 正式三轮：`board_results/l6_ui_release_phase_20260812/runs/systemui/rep{1,2,3}/`
- Chromium 正式只读复现：`board_results/l6_ui_release_phase_20260812/runs/chromium/blocked_attempt/`
- 作废尝试：`runs/AppUIB/rep1_attempt1/`、`runs/systemui/rep{1,3}_attempt_auto_gate/`
- 执行件：`board_results/l6_ui_release_phase_20260812/scripts/`
- 收尾证据：`board_results/l6_ui_release_phase_20260812/post/cleanup.txt`
- 291 个原始文件的完整 SHA-256 清单：
  `board_results/l6_ui_release_phase_20260812/raw_file_manifest.sha256`
