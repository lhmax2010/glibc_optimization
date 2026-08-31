> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# L6 释放相位规模验证与已有目标重测

采集日期：2026-08-12（板上 JST）  
板：当前 `<TEST_BOARD_IP>` 的 RPI4 测试板  
通道：`sdb`，先执行 `root on`  
数据根目录：`board_results/l6_release_phase_scale_20260812/`

本报告只记录实测事实和合同定义的派生量，不作上线裁决。

## 1. 身份、环境与素材

### 1.1 身份门

身份门通过。原文：

```text
IDENTITY_OK
6.12.80-arm-rpi4-v7l
VERSION="11.0.0 (Tizen11.0/Unified)"
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
```

`/etc/os-release` 不含 `<PRODUCT_IMAGE>`。因此本轮不是 TV 产品板。

### 1.2 glibc 与协变量

| 项 | 实测值 |
|---|---|
| glibc RPM | `glibc-2.40-2.8.armv7l` |
| libc 版本 | GNU libc 2.40 |
| libc 编译器 | GNU CC 14.2.0 |
| MemTotal / 初始 MemAvailable | 3,976,480 / 3,797,484 kB |
| swap/zram | `/dev/zram0` 1,590,588 kB；Used 0 |
| `vm.overcommit_memory` | 0 |
| CPU | 4 核，online `0-3` |
| governor | 4 核均为 `schedutil`，本轮未修改 |
| THP | `/sys/kernel/mm/transparent_hugepage` 不存在 |

该 MemTotal/governor 与上一轮同一 BUILD_ID 报告中的约 8 GiB/`performance` 不同；本报告保留本轮实测值，不用旧协变量替代。

### 1.3 工具与素材

- `gst_loop_decode.armv7l` SHA-256：`f691077b718e73d9f281ffb1f08bf056fb4c4e1971ba571a227b0e9db959160e`。
- 原素材 `/root/cabi.mp4`：88,765,233 B，SHA-256 `f58743eaba12f47320c4d8ea0ea7f9418b91728335c74df0c352d9730f63dd48`；只读使用。
- 重新生成素材：320x240、MPEG-4、60.1 s、1,802 帧、1,679,164 B。
- LLDB 使用临时运行库；`sleep 300` 的 `getpid()` 与 `malloc_trim(0)` 均成功，trim 返回 1，随后正常 detach。
- 8 路命令：`gst_loop_decode small_320x240.mp4 2 20 40`，各路错开 1 s。

## 2. 八路并发结果

### 2.1 相位同步

最终有效轮为 run4。8 路均取得 `PROCESS_READY`、首轮 `PLAYING_START` 和首轮 `NULL_DONE` 标记；用于 refault 的路 1/2 另取得第二轮 `PLAYING_START`。T1b 实际位于各路 PLAYING 后 +13.020～13.059 s；所选线程栈均停在 `gst_loop_decode.c:213` 的 PLAYING sleep。T2 `/proc` 画像位于各路 `NULL_DONE` 后 +5.010～5.027 s。全部 8 路进入 NULL 后再逐路注入。runner 退出码为 0，8 路 trim 后均存活。

表内三分类顺序均为 `glibc-heap / other-anon / file-backed`，单位 MiB。

| 路 | T0 | T1b | T2 | T4 | `A_ceiling` | A/T2 glibc | trim_return |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.078 / 0.059 / 0.496 | 2.199 / 1.590 / 0.496 | 2.777 / 1.000 / 0.512 | 1.430 / 0.527 / 0.520 | 1.347656 MiB | 48.5232% | 1 |
| 2 | 1.078 / 0.059 / 0.496 | 2.195 / 1.590 / 0.496 | 2.781 / 1.000 / 0.512 | 1.414 / 0.516 / 0.520 | 1.367188 MiB | 49.1573% | 1 |
| 3 | 1.078 / 0.059 / 0.496 | 2.195 / 1.590 / 0.496 | 2.777 / 1.000 / 0.512 | 1.410 / 0.520 / 0.520 | 1.367188 MiB | 49.2264% | 1 |
| 4 | 1.078 / 0.059 / 0.496 | 2.195 / 1.594 / 0.496 | 2.785 / 1.000 / 0.512 | 1.422 / 0.523 / 0.520 | 1.363281 MiB | 48.9481% | 1 |
| 5 | 1.078 / 0.059 / 0.496 | 2.191 / 1.582 / 0.496 | 2.777 / 0.992 / 0.512 | 1.406 / 0.527 / 0.520 | 1.371094 MiB | 49.3671% | 1 |
| 6 | 1.078 / 0.059 / 0.496 | 2.195 / 1.582 / 0.496 | 2.777 / 0.992 / 0.512 | 1.414 / 0.512 / 0.520 | 1.363281 MiB | 49.0858% | 1 |
| 7 | 1.078 / 0.059 / 0.496 | 2.195 / 1.598 / 0.496 | 2.781 / 1.000 / 0.512 | 1.426 / 0.527 / 0.520 | 1.355469 MiB | 48.7360% | 1 |
| 8 | 1.078 / 0.059 / 0.496 | 2.199 / 1.582 / 0.496 | 2.777 / 0.992 / 0.512 | 1.410 / 0.523 / 0.520 | 1.367188 MiB | 49.2264% | 1 |

8 路 `A_ceiling` 合计为 **11,431,936 B（10.902344 MiB）**。单路范围为 1.347656–1.371094 MiB；回收比例范围为 48.5232%–49.3671%。

### 2.2 M7 相位确认证据

`rest` 取 `malloc_info` 全局末行 `<total type="rest">`；`unsorted` 为各 heap `<unsorted total>` 之和。正增量表示 T2 比 T1b 增加。

| 路 | T1b rest | T2 rest | rest 增量 | T1b unsorted | T2 unsorted | unsorted 增量 | M7 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 379,006 | 2,531,183 | +2,152,177 | 4,505 | 1,818,811 | +1,814,306 | 已观察到增长 |
| 2 | 383,255 | 2,535,444 | +2,152,189 | 5,174 | 1,851,263 | +1,846,089 | 已观察到增长 |
| 3 | 379,265 | 2,532,585 | +2,153,320 | 10,932 | 1,855,528 | +1,844,596 | 已观察到增长 |
| 4 | 385,737 | 2,540,931 | +2,155,194 | 5,445 | 1,915,435 | +1,909,990 | 已观察到增长 |
| 5 | 369,800 | 2,522,588 | +2,152,788 | 2,948 | 1,805,834 | +1,802,886 | 已观察到增长 |
| 6 | 373,757 | 2,521,389 | +2,147,632 | 9,517 | 2,019,537 | +2,010,020 | 已观察到增长 |
| 7 | 390,860 | 2,534,920 | +2,144,060 | 8,062 | 1,970,889 | +1,962,827 | 已观察到增长 |
| 8 | 377,715 | 2,526,837 | +2,149,122 | 2,580 | 1,717,325 | +1,714,745 | 已观察到增长 |

8 路 arena 数均为 8。T1b/T2 的全局 fastbin 分别处于 2,016–5,544 B 和 2,400–2,600 B；`malloc_info` XML 不导出 tcache 驻留量。T1b XML 的所选栈确认在 PLAYING；T2 XML 紧邻各路 trim，因串行注入位于各自 `NULL_DONE` 后 +14.251～14.958 s，仍在 40 s NULL 窗口内。表中 T2 `/proc` 画像则是严格的 +5 s 点，两者不是同一瞬间。

### 2.3 系统级采样

| 点 | MemAvailable | swap used | zram `mm_stat` 首三项 |
|---|---:|---:|---|
| PRE_START | 3,743,580 kB | 0 | `4096 74 4096` |
| PRE_TRIM | 3,726,268 kB | 0 | `4096 74 4096` |
| POST_TRIM | 3,693,760 kB | 0 | `4096 74 4096` |
| POST_REFAULT | 3,712,188 kB | 0 | `4096 74 4096` |

PRE_TRIM→POST_TRIM 的 MemAvailable 实测变化为 -32,508 kB；POST_TRIM→POST_REFAULT 为 +18,428 kB。系统点覆盖逐个 attach/采样的墙钟窗口，不把该波动归因成 8 路 trim 的系统净收益。进程分类口径下的 glibc PD 合计下降单独列于 2.1。

## 3. 已有目标释放相位重测

| 目标 | 本轮构造动作 | 存活/页面证据 | M7 | 释放相位 `A_ceiling` | 历史静置态数字 |
|---|---|---|---|---:|---:|
| AppUIA | `app_launcher -s AppX`，拟切换后返回 | 启动返回 PID 23200；8 s 后不在 app status；同一窗口出现 `dotnet-hydra-loader` crash-manager 报告 | 未能采集 | n/a，未注入 | 0.219 MiB，4.48% |
| AppUIB | `app_launcher -s AppQ`，拟打开应用后返回 | PID 24276 在装载时因 `libEGL.so.1` 缺失，从 LAUNCHING 转 DYING | 未能采集 | n/a，未注入 | 0.438 MiB，5.03% |
| Chromium (`AppUIC`) | 本地 heavy 页面，拟导航到 `about:blank` | 主进程存活，但阻塞于 `Wait for the server to be ready`；无 `/run/wayland*`、无 renderer、无 `ewk_view_url_set`/LoadProgress | 未能采集 | n/a，未注入 | 名义 0.019531 MiB，0.196% |

关键失败原文：

```text
/usr/apps/AppQ/bin/runner: error while loading shared libraries:
libEGL.so.1: cannot open shared object file: No such file or directory

/usr/bin/enlightenment: error while loading shared libraries:
libEGL.so.1: cannot open shared object file: No such file or directory

ERR<28657>: ... _ecore_wl2_display_wait() Wait for the server to be ready.
ls: cannot access /run/wayland*: No such file or directory
```

AppUIA/AppUIB 历史值来自 `<TEST_IMAGE_A>`、glibc `2.40-3.12`；Chromium 历史名义值来自本轮同 BUILD_ID/glibc，但当时释放相位未验证。历史值仅并列记录，没有与本轮 8 路数据混成同镜像 A/B。

## 4. 代价面

### 4.1 注入窗口与锁停顿代理

8 路均选择 thread 1，其栈顶为 `clock_nanosleep`；审栈未见 `malloc/free/realloc` 路径。所有进程在 T2/T4 的状态均为 `S`。

| 路 | 完整 LLDB 包络 | LLDB 内 MI+trim 时间窗 | utime 增量 | stime 增量 |
|---:|---:|---:|---:|---:|
| 1 | 1.28 s | 0.284 s | 0 | 0 |
| 2 | 1.17 s | 0.255 s | 0 | 0 |
| 3 | 1.20 s | 0.269 s | 0 | 0 |
| 4 | 1.26 s | 0.345 s | 0 | 0 |
| 5 | 1.17 s | 0.252 s | 0 | 0 |
| 6 | 1.20 s | 0.268 s | 0 | 0 |
| 7 | 1.22 s | 0.273 s | 0 | 0 |
| 8 | 1.31 s | 0.270 s | 0 | 1 tick |

完整包络由 `/proc/uptime` 包围 LLDB 进程；内部时间窗由两次 `platform shell date` 得到，但其中同时包含 `malloc_info`、flush/fclose 和 `malloc_trim`，不是生产内调用 `malloc_trim` 的独立延迟。目标被 debugger stop 的时间也包含 attach、审栈、命令分派和 detach。

### 4.2 再次 PLAYING 的 fault

| 路 | T4→T5 minflt | majflt | utime/stime 增量 | zram 增量 |
|---:|---:|---:|---|---:|
| 1 | +519 | 0 | +14 / +2 ticks | 0 |
| 2 | +525 | 0 | +15 / +2 ticks | 0 |

T5 在第二轮 `PLAYING_START` 后约 5 s 采样。两路 swap Used 保持 0，zram `mm_stat` 不变。该口径没有应用帧时间或端到端响应时延，只是进程 fault/CPU tick 代理。

## 5. 失败、限制与异常

- AppUIA、AppUIB、Chromium 均未确认 M7，因此按合同没有注入 trim，也没有填写名义释放相位回收量。
- 图形环境缺少 `libEGL.so.1`，enlightenment monitor 持续尝试拉起 compositor；本轮没有修改镜像或补库。
- run1 的 T1b/T2 `/proc` 点实际约为 +17 s/+13～14 s；run2 修正 T1b，但前 5 路 T2 仍为 +6.1～10.8 s；run3 的 `/proc` 时序合规，但串行 T1b LLDB 已落入 NULL。三轮均保留为执行偏差证据，主表只使用 run4。
- run4 为保证每路 T1b XML 处于 PLAYING，在 1 s 错开的时刻并行运行了最多相邻重叠的 LLDB 会话；这会增加采集期 CPU/调试器扰动。T1b `/proc` 画像在 attach 前采集。
- `malloc_info` 本身会分配；T1b/T2 都用相同调用序列，但仍可能扰动 allocator 状态。
- `glibc-heap` 分类沿用 `[heap]` 加 1 MiB 对齐匿名段代理，不是 allocator ownership 的逐页证明。
- dmesg 未出现本轮新增 LMK、OOM、killed process、fatal 或 SIG11。grep 命中的三行仅为启动期 `oom_control/oom_adj is deprecated` 文本。
- 正常 `app_launcher -t AppK` 返回 `-6`；随后对本轮启动且仍存活的 PID 25398 发送 TERM，进程退出。

## 6. 恢复现场

```text
TEMP_ROOT_ABSENT
TEMP_ROOT2_ABSENT
gst_loop_decode:NONE
reclaim_probe:NONE
lldb:NONE
lldb-server:NONE
AppUIC:NONE
efl_webprocess:NONE
PID25398_GONE
```

`/root/l6scaleprobe` 与 `/root/l6scaleprobe2`、转码产物、临时 Chromium HTML、LLDB 运行库和 XML 均已删除。`/root/cabi.mp4` 未修改。清理后 app status 只剩任务前已存在的 `AppV`。

## 7. 原始文件

- 环境与 LLDB：`board_results/l6_release_phase_scale_20260812/stage0/`
- 最终有效 8 路采样：`board_results/l6_release_phase_scale_20260812/multi/run4/lane{1..8}/`
- 并发系统点：`board_results/l6_release_phase_scale_20260812/multi/run4/system_*.txt`
- M7 XML：`board_results/l6_release_phase_scale_20260812/multi/run4/lane{1..8}/malloc_info_{T1b,T2}.xml`
- 派生明细：`board_results/l6_release_phase_scale_20260812/multi/{phase_values,malloc_info_values,derived_values}.tsv`
- 时序偏差轮：`board_results/l6_release_phase_scale_20260812/multi/run{1,2,3}/`
- runner 与异常：`board_results/l6_release_phase_scale_20260812/multi/run4/{run_record,dmesg_before,dmesg_after,dmesg_alerts}.txt`
- 目标探测：`board_results/l6_release_phase_scale_20260812/{systemui_start,systemui_failure_evidence,AppUIB_start,chromium_start,chromium_current_profile,chromium_direct_probe}.txt`
- 清理证据：`board_results/l6_release_phase_scale_20260812/{cleanup,cleanup_app_verify,cleanup_app_fallback}.txt`、`multi/run4_cleanup.txt`
- 完整清单：`board_results/l6_release_phase_scale_20260812/raw_file_manifest.txt`
