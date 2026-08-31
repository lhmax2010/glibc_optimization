> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# ffmpeg 软解 L6 作用面测量报告

日期：2026-08-11  
范围：仅 RPI4 测试板 `<TEST_BOARD_IP>`。未连接或操作 TV 产品板。未安装包、未修改持久配置。  
通道：`<USER_HOME>/tizen-studio/tools/sdb`，设备序列号 `<TEST_BOARD_IP>:26101`，`sdb root on` 后执行。

## 1. 身份门、环境与素材

### 1.1 身份门原文

```text
kernel=6.12.80-arm-rpi4-v7l
IDENTITY_KERNEL_PASS
IDENTITY_TV_GUARD_PASS
VERSION="11.0.0 (Tizen11.0/Unified)"
VERSION_ID=11.0.0
BUILD_ID=<TEST_IMAGE_B>
IDENTITY_GATE_PASS
EXIT=0
```

有效身份为 RPI4 测试板；`<PRODUCT_IMAGE>` 保护条件未命中。root 身份为 `uid=0(root)`。

### 1.2 glibc 与协变量

| 项 | 实测 |
|---|---|
| glibc RPM | `glibc-2.40-2.8.armv7l`，Source RPM `glibc-2.40-2.8.src.rpm` |
| libc | `/usr/lib/libc.so.6` 与 `/lib/libc.so.6`，均为 1,429,532 B |
| libc 版本串 | GNU libc 2.40，`Compiled by GNU CC version 14.2.0` |
| MemTotal / 初始 MemAvailable | 8,117,404 / 7,514,456 kB |
| overcommit | `vm.overcommit_memory=0` |
| swap | `/dev/zram0`，3,246,960 kB，初始 Used=0 |
| zram `mm_stat` | `4096 74 4096 0 4096 0 0 0 0` |
| CPU | 4 核，online `0-3` |
| governor | 4 核均为 `performance`，本轮未改动 |
| THP | `/sys/kernel/mm/transparent_hugepage` 不存在 |

本轮镜像和 glibc release 与 `docs/l6_tf_chromium_probe.md` 相同；与历史 AppUIA/AppUIB 测量的 `<TEST_IMAGE_A>`、glibc `2.40-3.12` 不同。

### 1.3 解码工具与替代路径

板上没有 `ffmpeg`、`ffprobe`，在 `/usr`、`/opt` 的文件搜索也未找到。因此不能执行原定的 `ffmpeg -hwaccel none ... -f null -` 命令。按任务允许的替代路径，实测以下 GStreamer/libav 组件存在：

```text
/usr/bin/gst-launch-1.0
GStreamer 1.24.11 avdec_h264
GStreamer 1.24.11 avdec_mpeg4
mpeg4videoparse
videoscale / videoconvert
avenc_mpeg4
mp4mux
```

解码管线显式指定 `avdec_h264` 或 `avdec_mpeg4`，没有自动选择硬件 decoder。各进程 maps 均记录 `ALLOCATOR_SO_NONE`，未发现 tcmalloc、jemalloc、mimalloc 或 scudo 映射。

### 1.4 视频素材

原始素材只读使用。因板上无 `ffprobe`，将原文件拉到 host 后用 host `ffprobe` 读取元数据；板上原文件未改动。

| 文件 | codec/profile | 分辨率 | 帧率 | 时长 | 帧数 | 大小 |
|---|---|---:|---:|---:|---:|---:|
| `/root/cabi.mp4` | H.264 Baseline, yuv420p | 960x640 | 30 fps | 270.600 s（container 270.744671 s） | 8,118 | 88,765,233 B |
| 临时 `small_320x240.mp4` | MPEG-4 Part 2 Simple, yuv420p | 320x240 | 约 30 fps | 60.100 s | 1,802 | 1,679,164 B |

板上没有 x264 encoder，临时小视频用软件 libav MPEG-4 encoder 生成：

```text
gst-launch-1.0 -e filesrc location=/root/cabi.mp4 ! qtdemux name=d \
  d.video_0 ! queue ! h264parse ! avdec_h264 ! videoscale ! videoconvert ! \
  video/x-raw,format=I420,width=320,height=240,framerate=30/1 ! \
  identity eos-after=1800 ! avenc_mpeg4 ! mp4mux ! \
  filesink location=/root/l6ffmpeg_probe/small_320x240.mp4
```

管线退出 0，执行时间 30.355 s。原始素材采集前后 SHA-256 均为 `f58743eaba12f47320c4d8ea0ea7f9418b91728335c74df0c352d9730f63dd48`。

### 1.5 LLDB 环境

镜像未自带 `lldb/lldb-server`。本轮临时使用此前已验证的官方 armv7l LLDB 22.1.8 文件以及精确匹配的 `libLLVM.so.22.1`、`libclang-cpp.so.22.1`，通过一次性 `LD_LIBRARY_PATH` 运行，未安装 RPM。

一次性 sleep 最小门通过：

```text
frame #0: libc.so.6`__GI___clock_nanosleep_time64
(lldb) expr -t 5000000 -- (int)getpid()
(int) $0 = 19952
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $1 = 1
Process 19952 detached
LLDB_RC=0
SLEEP_ALIVE_AFTER=1
SLEEP_CLEANED
```

## 2. 阶段一预筛

原片使用 `avdec_h264`，小片使用 `avdec_mpeg4`，sink 均为 `fakesink sync=false`。T0 为启动后立即 SIGSTOP 的暂停态；随后恢复解码并连续采样，最后一条为进程退出前最后一个成功 profile。单位均为 MiB `Private_Dirty`。

| 分辨率 | 点 | glibc-heap | other-anon | file-backed | 总 PD |
|---|---|---:|---:|---:|---:|
| 960x640 | T0 | 0.667969 | 0.050781 | 0.121094 | 0.839844 |
| 960x640 | T1a | 1.195312 | 17.589844 | 0.500000 | 19.285156 |
| 960x640 | T1b | 1.230469 | 17.488281 | 0.500000 | 19.218750 |
| 960x640 | glibc 最大点 `tail_13` | 1.406250 | 17.988281 | 0.500000 | 19.894531 |
| 960x640 | 结束前 `tail_18` | 1.406250 | 18.054688 | 0.500000 | 19.960938 |
| 320x240 | T0 | 0.656250 | 0.050781 | 0.121094 | 0.828125 |
| 320x240 | T1a | 2.753906 | 0.925781 | 0.500000 | 4.179688 |
| 320x240 | T1b | 2.785156 | 1.019531 | 0.500000 | 4.304688 |
| 320x240 | 结束前/最大点 `tail_2` | 2.851562 | 1.019531 | 0.500000 | 4.371094 |

| 配置 | T0 glibc PD | 最大 glibc PD | 增长 | 冻结门 `>=1 MiB` |
|---|---:|---:|---:|---|
| 960x640 H.264 | 700,416 B | 1,474,560 B | 774,144 B（0.738281 MiB） | 未通过 |
| 320x240 MPEG-4 | 688,128 B | 2,990,080 B | 2,301,952 B（2.195312 MiB） | 通过 |

因此阶段二仅执行 320x240 配置。原片正确运行 29.47 s、取得 22 点；小片正确运行 0.87 s、取得 6 点，两个有效管线均退出 0。

## 3. 阶段二 L6 测量

### 3.1 相位构造

每轮新起一个 `gst-launch-1.0` 进程，使用 `fakesink sync=true` 按媒体时钟实时软解。T1a/T1b 分别约在 5 s/15 s；约 20 s 时 SIGSTOP，T2 为暂停态。该构造保持进程存活，但没有 EOS，也没有独立证明 decoder 在 T2 集中释放 DPB；这是本轮相位口径。

每轮 T2 后先单独执行 `thread list + bt all`。三轮所有线程栈均无 `malloc/calloc/realloc/free/arena` 命中；所选 thread 1 均为：

```text
libc.so.6`__GI___poll
libglib-2.0.so.0`g_main_loop_run
gst-launch-1.0
```

随后在同一选中线程依次调用 `malloc_info`、`fflush/fclose` 和 `malloc_trim(0)`。

### 3.2 相位数据

PD 单位为 MiB。fault 列为进程累计 `minflt/majflt`；zram 列为 `orig_data_size/compr_data_size` MiB。

| rep | 点 | glibc-heap | other-anon | file-backed | 总 PD | faults | zram orig/compr |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | T0 | 0.664062 | 0.050781 | 0.121094 | 0.835938 | 1205/0 | 0.003906/0.003906 |
| 1 | T1a | 2.843750 | 1.003906 | 0.500000 | 4.347656 | 2959/0 | 0.003906/0.003906 |
| 1 | T1b | 2.757812 | 1.003906 | 0.500000 | 4.261719 | 2963/0 | 0.003906/0.003906 |
| 1 | T2 | 2.761719 | 1.003906 | 0.500000 | 4.265625 | 2964/0 | 0.003906/0.003906 |
| 1 | T4 | 2.753906 | 1.007812 | 0.515625 | 4.277344 | 2969/0 | 0.003906/0.003906 |
| 2 | T0 | 0.652344 | 0.050781 | 0.121094 | 0.824219 | 1201/0 | 0.003906/0.003906 |
| 2 | T1a | 2.843750 | 1.003906 | 0.500000 | 4.347656 | 2959/0 | 0.003906/0.003906 |
| 2 | T1b | 2.753906 | 1.003906 | 0.500000 | 4.257812 | 2963/0 | 0.003906/0.003906 |
| 2 | T2 | 2.757812 | 1.003906 | 0.500000 | 4.261719 | 2964/0 | 0.003906/0.003906 |
| 2 | T4 | 2.750000 | 1.007812 | 0.515625 | 4.273438 | 2969/0 | 0.003906/0.003906 |
| 3 | T0 | 0.640625 | 0.050781 | 0.121094 | 0.812500 | 1197/0 | 0.003906/0.003906 |
| 3 | T1a | 2.843750 | 1.003906 | 0.500000 | 4.347656 | 2959/0 | 0.003906/0.003906 |
| 3 | T1b | 2.746094 | 1.003906 | 0.500000 | 4.250000 | 2962/0 | 0.003906/0.003906 |
| 3 | T2 | 2.750000 | 1.003906 | 0.500000 | 4.253906 | 2963/0 | 0.003906/0.003906 |
| 3 | T4 | 2.742188 | 1.007812 | 0.515625 | 4.265625 | 2967/0 | 0.003906/0.003906 |

### 3.3 `A_ceiling`

`A_ceiling` 按合同取 T2 到 T4 的 glibc-heap Private_Dirty 下降。T3 包络包含 attach、栈回溯、`malloc_info`、flush/fclose、trim 和 detach，不是 `malloc_trim` 函数自身的独立耗时。

| rep | `A_ceiling` | A / T2 glibc | 总 PD 下降 | trim_return | T3 注入包络 |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.007812 MiB（8,192 B） | 0.2829% | -0.011719 MiB | 1 | 1.03 s |
| 2 | 0.007812 MiB（8,192 B） | 0.2833% | -0.011719 MiB | 1 | 1.09 s |
| 3 | 0.007812 MiB（8,192 B） | 0.2841% | -0.011719 MiB | 1 | 1.03 s |
| 中位数 | **0.007812 MiB（8,192 B）** | **0.2833%** | **-0.011719 MiB** | 1 | **1.03 s** |

三轮 glibc-heap 净下降均为 8 KiB。T4 的 `other-anon` 增加 4 KiB、`file-backed` 增加 16 KiB，因此总 PD 比 T2 高 12 KiB；表中保留原始符号，没有把总 PD 变化替代成 glibc-heap 回收量。三轮 zram `mm_stat` 均未增长，swap Used 保持 0。

### 3.4 `malloc_info` 分布

XML 在 T2、trim 前采集。fast/rest 使用 XML 最末全局 `<total>`；unsorted 为各 heap `<unsorted total=...>` 求和。

| rep | arena | fast count/bytes | rest count/bytes | unsorted count/bytes | fast/(fast+rest) | unsorted/rest | system current bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 96 / 2,328 | 273 / 520,769 | 8 / 6,328 | 0.4450% | 1.2151% | 3,915,776 |
| 2 | 8 | 229 / 5,536 | 328 / 512,720 | 5 / 1,621 | 1.0682% | 0.3162% | 3,911,680 |
| 3 | 8 | 81 / 1,968 | 266 / 508,434 | 9 / 22,569 | 0.3856% | 4.4389% | 3,903,488 |

`malloc_info` XML 不导出 tcache residency，本轮没有从 XML 推测 tcache 字节数。`rest` 包含的不只是 unsorted，表中未将二者等同。

## 4. 与既有目标的比例对照

| 目标 | glibc 回收比例或预筛分布 | 镜像 / glibc | 可比性事实 |
|---|---:|---|---|
| 本轮 320x240 libav 软解 | 0.2833% 中位数 | `<TEST_IMAGE_B>`, `2.40-2.8` | T2 是实时解码暂停态，非已验证 EOS 集中释放 |
| Chromium | 0.196% 中位数 | `<TEST_IMAGE_B>`, `2.40-2.8` | 同镜像；其释放相位也未独立验证 |
| TensorFlow Lite float | 未 trim；推理中 22.293/23.035 MiB PD 位于 other-anon（96.78%） | `<TEST_IMAGE_B>`, `2.40-2.8` | 同镜像；预筛未过 1 MiB glibc 增长门 |
| AppUIA | 4.48% | `<TEST_IMAGE_A>`, `2.40-3.12` | 不同镜像；历史完整静置态测量 |
| AppUIB | 5.03% | `<TEST_IMAGE_A>`, `2.40-3.12` | 不同镜像；历史完整静置态测量 |
| 历史 GStreamer 视频 | 未 trim；播放中 90.14% 总 PD 位于 other-anon | `<TEST_IMAGE_A>` | 不同镜像；EOS 后进程退出 |

以上只并列原值和采集口径，没有把不同镜像或不同相位的数据作为直接 A/B。

## 5. 失败、限制与恢复现场

- 板上没有 ffmpeg/ffprobe，本轮是规格允许的 GStreamer libav fallback，不是 ffmpeg CLI 进程；进程框架自身的 GLib/GStreamer 分配也计入该进程画像。
- 小视频首次转码包装因 `/usr/bin/time` 缺失退出 127，编码管线未启动。移除不存在的计时包装后，管线原样重试并退出 0；失败原文保留。
- 原片预筛第一次 runner 因 POSIX sh 函数覆盖全局计数器，在 `008` 处触发八进制解析错误。该 gst PID 被单独终止，失败目录完整保留；只修正采集器变量名后重新新起进程，有效重跑退出 0。
- T2 是 SIGSTOP 暂停点，不是已证明的 DPB 集中释放点；因此本轮没有取得“解码段结束但进程仍存活”的独立画像。
- `glibc-heap` 是 `[heap]` 加 1 MiB 对齐匿名段的历史代理口径，不是 allocator ownership 的逐页证明。
- T3 只取得完整注入包络，未取得 `malloc_trim` 函数体的独立耗时。
- 三轮 dmesg 的 alert grep 仅命中开机 21 s 的 `oom_control is deprecated` 和 uptime 83955 s 的旧 sdbd `oom_adj` 记录；本轮前后没有新增 LMK、OOM 或 fatal 行。

收尾证据：

```text
DELETE_EXIT=0
TEMP_DIR_ABSENT
NO_GST_LAUNCH
NO_LLDB
===lldb_runtime_residual===
```

临时小视频、runner、`reclaim_probe`、LLDB 和运行库均已删除。原始 `/root/cabi.mp4` 仍存在，大小与 SHA-256 未变。

## 6. 原始文件清单

完整清单共 202 个文件，见：

- `board_results/l6_ffmpeg_swdecode_20260811/raw_file_manifest.tsv`

主要目录和派生表：

- `board_results/l6_ffmpeg_swdecode_20260811/stage0/`：身份、环境、glibc、工具、素材元数据、转码与 LLDB smoke 原文；含只读拉回的原始素材副本。
- `board_results/l6_ffmpeg_swdecode_20260811/stage1/original_960x640/`：有效原片预筛 22 点。
- `board_results/l6_ffmpeg_swdecode_20260811/stage1/small_320x240/`：有效小片预筛 6 点。
- `board_results/l6_ffmpeg_swdecode_20260811/stage1/original_960x640_failed1/`：runner 计数器失败原文。
- `board_results/l6_ffmpeg_swdecode_20260811/stage1/prescreen_values.tsv`、`prescreen_gate_summary.txt`：预筛原值与门计算。
- `board_results/l6_ffmpeg_swdecode_20260811/stage2/small_320x240_rep{1,2,3}/`：T0/T1a/T1b/T2/T4、完整 LLDB 栈与注入输出、malloc_info XML、dmesg 和清理证据。
- `board_results/l6_ffmpeg_swdecode_20260811/stage2/phase_values.tsv`、`derived_values.tsv`、`malloc_info_values.tsv`：阶段二原值与派生量。
- `board_results/l6_ffmpeg_swdecode_20260811/scripts/`：实际推送执行的两个采集 runner。
- `board_results/l6_ffmpeg_swdecode_20260811/precleanup_evidence.txt`、`cleanup_evidence.txt`、`original_asset_integrity.txt`：收尾与原素材完整性证据。
