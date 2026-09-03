> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# L6 GStreamer 真释放相位测量报告

日期：2026-08-11  
范围：仅 RPI4 测试板 `<TEST_BOARD_IP>`；未连接或操作 TV 产品板。未安装板上软件包，未修改持久配置。  
通道：`<USER_HOME>/tizen-studio/tools/sdb`，序列号 `<TEST_BOARD_IP>:26101`，`sdb root on` 后执行。

## 1. 身份、环境与素材

### 1.1 身份门

```text
kernel=6.12.80-arm-rpi4-v7l
IDENTITY_KERNEL_PASS
IDENTITY_TV_GUARD_PASS
VERSION="11.0.0 (Tizen11.0/Unified)"
VERSION_ID=11.0.0
BUILD_ID=<TEST_IMAGE_B>
IDENTITY_GATE_PASS
IDENTITY_EXIT=0
```

有效身份为 RPI4 测试板，`<PRODUCT_IMAGE>` 保护条件未命中。有效身份为 `uid=0(root)`。

### 1.2 glibc 与协变量

| 项 | 实测 |
|---|---|
| glibc | `glibc-2.40-2.8.armv7l` |
| libc 版本串 | GNU libc 2.40，`Compiled by GNU CC version 14.2.0` |
| MemTotal / 初始 MemAvailable | 8,117,404 / 7,509,112 kB |
| overcommit | `vm.overcommit_memory=0` |
| swap | `/dev/zram0`，3,246,960 kB，初始 Used=0 |
| zram `mm_stat` | `4096 74 4096 0 4096 0 0 0 0` |
| CPU | 4 核，online `0-3` |
| governor | 4 核均为 `performance`，本轮未改动 |
| THP | `/sys/kernel/mm/transparent_hugepage` 不存在 |

本轮镜像和 glibc release 与 `docs/l6_ffmpeg_swdecode_probe.md`、`docs/l6_tf_chromium_probe.md` 相同；与历史 AppUIA/AppUIB 的 `<TEST_IMAGE_A>`、glibc `2.40-3.12` 不同。

### 1.3 素材

原始 `/root/cabi.mp4` 为 960x640、H.264 Baseline、30 fps、约 270.6 s，大小 88,765,233 B。采集前后 SHA-256 均为：

```text
f58743eaba12f47320c4d8ea0ea7f9418b91728335c74df0c352d9730f63dd48
```

测试片使用板上 libav 软件编码路径生成：

```text
gst-launch-1.0 -e filesrc location=/root/cabi.mp4 ! qtdemux name=d \
  d.video_0 ! queue ! h264parse ! avdec_h264 ! videoscale ! videoconvert ! \
  video/x-raw,format=I420,width=320,height=240,framerate=30/1 ! \
  identity eos-after=1800 ! avenc_mpeg4 ! mp4mux ! \
  filesink location=/root/l6gstprobe/small_320x240.mp4
```

管线退出 0，耗时 30.419 s。host `ffprobe` 复核结果为 MPEG-4 Part 2 Simple、320x240、yuv420p、约 30 fps、60.1 s、1,802 帧、1,679,164 B。320x240 YUV420 单帧约 115,200 B，小于 128 KiB。

### 1.4 LLDB

镜像未自带可运行的 `lldb/lldb-server`。本轮临时使用已验证的官方 armv7l LLDB 22.1.8、`libLLVM.so.22.1` 和 `libclang-cpp.so.22.1`，通过一次性 `LD_LIBRARY_PATH` 运行，未安装 RPM。

一次性 sleep 最小门通过：

```text
(lldb) expr -t 5000000 -- (int)getpid()
(int) $0 = 30487
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $1 = 1
Process 30487 detached
LLDB_RC=0
SLEEP_ALIVE_AFTER=1
SLEEP_CLEANED
```

## 2. `gst_loop_decode` 交付与构建

### 2.1 交付

- 源码：`bench/gst_loop_decode/gst_loop_decode.c`
- 板上产物：`bench/gst_loop_decode/gst_loop_decode.armv7l`
- 源码 SHA-256：`af7e2ca3eaa1da189fed247158a6c3d690a456d8f7c5caa9d29c4dc5cafefb27`
- 二进制 SHA-256：`f691077b718e73d9f281ffb1f08bf056fb4c4e1971ba571a227b0e9db959160e`
- ELF：32-bit ARM EABI5，动态链接，interpreter `/lib/ld-linux.so.3`，Build ID `55094dc680596cda84ee65038deff16c47066993`

CLI：

```text
gst_loop_decode <file> <cycles> <play_seconds> <null_seconds>
```

程序显式创建 `filesrc/qtdemux/queue/mpeg4videoparse/avdec_mpeg4/fakesink`，用 `pad-added` 回调在每次从 NULL 回到 PLAYING 时重新连接 qtdemux video pad。每次 `gst_element_set_state` 后均用 `gst_element_get_state(..., 30 * GST_SECOND)` 阻塞确认。首次 PLAYING 前固定留 5 s T0 窗口；每周期输出 `PLAYING_REQUEST/PLAYING_START/NULL_REQUEST/NULL_DONE/NULL_WAIT_START/CYCLE_DONE` 时间戳；最后再等待一个 `null_seconds` 窗口。SIGINT/SIGTERM 会转入 NULL 并清理 pipeline。

### 2.2 开发环境处置

板上事实：

```text
MISSING:gcc
pkg-config --exists gstreamer-1.0 -> rc 1
/usr/include/gstreamer-1.0/gst/gst.h: missing
installed runtime: gstreamer-1.24.11-38.armv7l
```

板上无 dnf/tdnf/zypper/yum，因此没有尝试用裸 RPM 改动板上软件状态。host 从 workspace `gbs.conf` 已配置的官方 Tizen Unified 仓库下载并只解包以下 devel RPM 到临时 sysroot：

| host-only RPM | SHA-256 |
|---|---|
| `glib2-devel-2.80.5-0.armv7l.rpm` | `ed1d961371080299b643840806dbc26c5666ba9e56cd3b1d4d542b7d5a814f5f` |
| `gstreamer-devel-1.24.11-41.armv7l.rpm` | `8882e2d4ac8a9c0205c518cd0477dec345adcd281cac3f9c165bff5ceb9e6e8e` |

头文件为 GStreamer 1.24.11；devel RPM release 41 与板上 runtime release 38 不同。链接输入使用从板上拉回的实际 `libgstreamer-1.0.so.0`、`libgobject-2.0.so.0` 和 `libglib-2.0.so.0`，最终 ELF 的 NEEDED 即这三个 SONAME 加 pthread/libc。

实际交叉编译核心命令为：

```text
armv7l-tizen-linux-gnueabi-gcc -std=c99 -O2 -g -Wall -Wextra -Werror \
  -I<temp>/usr/include/gstreamer-1.0 \
  -I<temp>/usr/include/glib-2.0 \
  -I<temp>/usr/lib/glib-2.0/include \
  -o bench/gst_loop_decode/gst_loop_decode.armv7l \
  bench/gst_loop_decode/gst_loop_decode.c \
  -L<temp>/usr/lib -Wl,-rpath-link,<temp>/usr/lib \
  -Wl,--allow-shlib-undefined \
  -l:libgstreamer-1.0.so.0 -l:libgobject-2.0.so.0 \
  -l:libglib-2.0.so.0 -pthread
```

最终两周期 smoke 连续得到两组 PLAYING/NULL 标记，退出 0、stderr 为空。

## 3. 相位有效性证据

有效单路命令均为：

```text
/root/l6gstprobe/gst_loop_decode small_320x240.mp4 2 20 30
```

每轮 T1b 约在首轮 PLAYING 后 13 s；T2 严格取首轮 `NULL_DONE` 后 5 s。三轮 `NULL_DONE` 都在 `NULL_REQUEST` 后约 2 ms 出现，程序继续存活。

冻结判据及同步发生的分类变化如下；正数表示 T2 比 T1b 增加：

| rep | glibc-heap T1b→T2 | other-anon T1b→T2 | file-backed | 总 PD T1b→T2 | glibc/other 段数 T1b→T2 | 冻结门 |
|---:|---:|---:|---:|---:|---|---|
| 1 | +614,400 B（+0.585938 MiB） | -630,784 B | 0 | -16,384 B | 4/18 → 6/16 | 未通过：glibc PD 未下降 |
| 2 | +610,304 B（+0.582031 MiB） | -622,592 B | 0 | -12,288 B | 4/18 → 6/16 | 未通过：glibc PD 未下降 |
| 3 | +610,304 B（+0.582031 MiB） | -622,592 B | 0 | -12,288 B | 4/18 → 6/16 | 未通过：glibc PD 未下降 |

按任务冻结定义，三轮 T1→T2 的 glibc-heap PD 均无下降，单路相位验证条件未成立。因此 S4 的 8 路并发前置门未满足，多路测量未启动。

同一批次的后续事实是：三轮 T2→T4 的 glibc-heap PD 均下降 1,425,408 B，且 trim 返回 1；该数据列入下一节，但不用于改写上述冻结门结果。

## 4. 单路核心数据

### 4.1 各点画像

PD 单位为 MiB。fault 为进程累计 `minflt/majflt`；MemAvailable 单位 kB。

| rep | 点 | glibc-heap | other-anon | file-backed | 总 PD | faults | MemAvailable |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | T0 | 1.078125 | 0.058594 | 0.496094 | 1.632812 | 1662/0 | 7,480,028 |
| 1 | T1a | 2.191406 | 1.695312 | 0.496094 | 4.382812 | 2625/0 | 7,468,424 |
| 1 | T1b | 2.199219 | 1.597656 | 0.496094 | 4.292969 | 2629/0 | 7,459,428 |
| 1 | T2 | 2.785156 | 0.996094 | 0.496094 | 4.277344 | 2634/0 | 7,472,064 |
| 1 | T4 | 1.425781 | 0.523438 | 0.511719 | 2.460938 | 2634/0 | 7,431,828 |
| 1 | T5 | 1.921875 | 2.015625 | 0.511719 | 4.449219 | 3152/0 | 7,467,600 |
| 2 | T0 | 1.078125 | 0.058594 | 0.496094 | 1.632812 | 1662/0 | 7,464,176 |
| 2 | T1a | 2.191406 | 1.683594 | 0.496094 | 4.371094 | 2622/0 | 7,470,344 |
| 2 | T1b | 2.195312 | 1.582031 | 0.496094 | 4.273438 | 2625/0 | 7,503,328 |
| 2 | T2 | 2.777344 | 0.988281 | 0.496094 | 4.261719 | 2631/0 | 7,464,620 |
| 2 | T4 | 1.417969 | 0.519531 | 0.511719 | 2.449219 | 2631/0 | 7,435,484 |
| 2 | T5 | 1.921875 | 2.015625 | 0.511719 | 4.449219 | 3153/0 | 7,468,580 |
| 3 | T0 | 1.078125 | 0.058594 | 0.496094 | 1.632812 | 1662/0 | 7,472,876 |
| 3 | T1a | 2.191406 | 1.691406 | 0.496094 | 4.378906 | 2624/0 | 7,479,040 |
| 3 | T1b | 2.191406 | 1.589844 | 0.496094 | 4.277344 | 2626/0 | 7,464,352 |
| 3 | T2 | 2.773438 | 0.996094 | 0.496094 | 4.265625 | 2632/0 | 7,481,588 |
| 3 | T4 | 1.414062 | 0.531250 | 0.511719 | 2.457031 | 2632/0 | 7,439,164 |
| 3 | T5 | 1.925781 | 2.011719 | 0.511719 | 4.449219 | 3149/0 | 7,477,180 |

三轮所有采样的 zram `orig_data_size/compr_data_size` 均为 4,096/4,096 B，swap Used 保持 0。

### 4.2 T2→T4 与再次 PLAYING

`A_ceiling` 为合同算术口径 T2 glibc-heap PD 减 T4 glibc-heap PD。由于第 3 节冻结门未通过，表中只记录该派生量，不替代相位门。

| rep | T1b→T2 glibc 自然下降 | `A_ceiling` | A/T2 glibc | trim_return | T4→T5 refault min/maj | T3 注入包络 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | -0.585938 MiB | 1.359375 MiB | 48.8079% | 1 | 518/0 | 1.01 s |
| 2 | -0.582031 MiB | 1.359375 MiB | 48.9451% | 1 | 522/0 | 1.03 s |
| 3 | -0.582031 MiB | 1.359375 MiB | 49.0141% | 1 | 517/0 | 1.03 s |
| 中位数 | **-0.582031 MiB** | **1.359375 MiB** | **48.9451%** | 1 | **518/0** | **1.03 s** |

“自然下降”为负表示 T2 高于 T1b。T3 包络包含 attach、栈回溯、`malloc_info`、flush/fclose、trim 和 detach，不是 `malloc_trim` 函数体的独立耗时。

三轮 attach 前均执行 `thread list + bt all`，所有线程栈对 `malloc/calloc/realloc/free/arena` 的命中数均为 0。所选 thread 1 均停在 `clock_nanosleep → sleep_seconds`，三轮注入后进程仍存活；第二轮 PLAYING marker 和 T5 均取得，随后 SIGTERM 使程序转入 NULL、输出 STOPPED 并清理。

## 5. 多路并发

| 计划 | 执行状态 | 原因 | 数据 |
|---|---|---|---|
| 8 路，错开 1 s，全部 NULL 后逐个 trim | 未执行 | 三轮单路 T1b→T2 glibc-heap PD 均未下降，未满足 S4 前置门 | n/a |

因此没有 8 路 A_ceiling 汇总，也没有并发 zram/MemAvailable 数据。

## 6. `malloc_info` 分布

XML 在 T2、trim 前采集。fast/rest 使用 XML 最末全局 `<total>`；unsorted 为各 heap `<unsorted total=...>` 求和。

| rep | arena | fast count/bytes | rest count/bytes | unsorted count/bytes | fast/(fast+rest) | unsorted/rest | system current bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 77 / 2,192 | 268 / 2,551,308 | 148 / 2,101,140 | 0.0858% | 82.3554% | 3,764,224 |
| 2 | 8 | 77 / 2,192 | 264 / 2,535,464 | 134 / 1,808,478 | 0.0864% | 71.3273% | 3,747,840 |
| 3 | 8 | 77 / 2,192 | 274 / 2,538,818 | 129 / 1,774,809 | 0.0863% | 69.9069% | 3,751,936 |

`malloc_info` 不导出 tcache residency，未从 XML 推测 tcache 字节数。`rest` 包含的不只是 unsorted，二者没有混写。

## 7. 与既有目标对照

| 目标/相位 | glibc T2→T4 回收比例 | A_ceiling | 镜像 / glibc | 口径事实 |
|---|---:|---:|---|---|
| 本轮 GStreamer NULL 后 | 48.9451% 中位数 | 1.359375 MiB | `<TEST_IMAGE_B>`, `2.40-2.8` | T1b→T2 glibc PD 未下降，未过冻结相位门 |
| 上轮 GStreamer 暂停态 | 0.2833% 中位数 | 0.007812 MiB | 同镜像、同 glibc | SIGSTOP 时 decoder 缓冲仍活跃 |
| Chromium | 0.196% 中位数 | 0.019531 MiB | 同镜像、同 glibc | 释放相位未独立验证 |
| TensorFlow Lite | n/a | n/a | 同镜像、同 glibc | 预筛未过 1 MiB glibc 增长门 |
| AppUIA | 4.48% | 0.219 MiB | `<TEST_IMAGE_A>`, `2.40-3.12` | 不同镜像，历史静置态测量 |
| AppUIB | 5.03% | 0.438 MiB | `<TEST_IMAGE_A>`, `2.40-3.12` | 不同镜像，历史静置态测量 |

以上只并列原值与采集口径，没有把不同镜像或未通过相位门的数据作为直接 A/B。

## 8. 失败、限制与恢复现场

- host 首次解包 devel RPM 时相对路径多一层，`rpm2cpio` 找不到文件，未产生有效 sysroot；修正 host 路径后重新解包成功，板上未受影响。
- 初版程序将 `g_shell_quote()` 的单引号交给 GStreamer parser，filesrc 尝试打开带单引号的路径，smoke 真实退出码为 4。改为命名 filesrc 并通过 `g_object_set(location=...)` 设置路径后通过。
- parse-launch 延迟 pad 链接版在第二周期报 qtdemux `not-linked`，该次单路 rep1 退出 91 并完整归档。改为显式 `pad-added` 重链后，两周期 smoke 和正式 3/3 均退出 0。
- T1b→T2 同时发生 glibc/other 分类段数变化；报告保留各类 PD、段数和总 PD，不把一个类别的变化替代为总量变化。
- `glibc-heap` 是 `[heap]` 加 1 MiB 对齐匿名段的历史代理口径，不是 allocator ownership 的逐页证明。
- 三轮 dmesg alert 文件完全相同，只包含开机 21 s 的 `oom_control is deprecated` 和 uptime 83955 s 的旧 sdbd `oom_adj` 行；本轮未出现新增 LMK/OOM/fatal 行。

板上恢复证据：

```text
DELETE_EXIT=0
TEMP_DIR_ABSENT
NO_GST_LOOP
NO_LLDB
===residual===
===packages===
gstreamer-1.24.11-38.armv7l
gstreamer-utils-1.24.11-38.armv7l
```

临时转码片、程序、探针和 LLDB 运行库均已删除。原片大小和 SHA-256 未变。host-only devel sysroot、下载 RPM 和仓库 metadata 也已删除并验证目录不存在。

## 9. 原始文件清单

完整清单含 122 条原始/派生文件路径：

- `board_results/l6_gst_release_phase_20260811/raw_file_manifest.tsv`

主要路径：

- `board_results/l6_gst_release_phase_20260811/stage0/`：身份、环境、glibc、素材、devel 处置、构建、LLDB 与所有 smoke 原文。
- `board_results/l6_gst_release_phase_20260811/single/rep{1,2,3}/`：正式三轮 T0/T1a/T1b/T2/T4/T5、marker、完整 LLDB 输出、malloc_info XML、dmesg 与清理证据。
- `board_results/l6_gst_release_phase_20260811/single/failed_dynamic_relink_rep1/`：第二周期 qtdemux 重链失败的完整原文。
- `board_results/l6_gst_release_phase_20260811/single/phase_values.tsv`、`derived_values.tsv`、`malloc_info_values.tsv`、`median_summary.txt`：原值与派生量。
- `board_results/l6_gst_release_phase_20260811/scripts/single_rep.sh`：实际执行 runner。
- `board_results/l6_gst_release_phase_20260811/precleanup_evidence.txt`、`cleanup_evidence.txt`、`host_temp_cleanup_evidence.txt`：恢复现场证据。
