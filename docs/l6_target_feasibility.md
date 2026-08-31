> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# L6 补测目标可行性探查报告

日期：2026-08-07  
范围：仅 RPI4 `.25`；未连接或操作 TV `.26`。本轮未调用 `malloc_trim`、`pageout`，未安装包、未重启 service、未修改持久配置。  
通道：`<USER_HOME>/tizen-studio/tools/sdb`，`sdb root on`。

## 1. 板身份自检

每个采集阶段先检查内核含 `rpi4`、`/etc/os-release` 含 `unified-dev`；首次与收尾实测均通过：

```text
<TEST_BOARD_IP>:26101 device rpi4
Switched to 'root' account mode
IDENTITY_OK
uid=0(root) gid=0(root) ...
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Mon Jul 27 09:29:29 UTC 2026 armv7l GNU/Linux
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_A>
```

身份与通道原文：`board_results/l6_target_feasibility_20260807/identity_and_channel.txt`。

`/tmp` 为 `noexec`，底层 `/root` 为只读。为运行已有 armv7l `profile` 探针，临时在 `/root` 挂载 64 MiB tmpfs，仅放置 `reclaim_probe`；收尾已卸载。探针 smoke 对 PID 1 成功输出 `reclaim_probe.v1` JSON。

## 2. 应用清单与候选

完整 `app_launcher -l` 共 59 行，原文位于 `board_results/l6_target_feasibility_20260807/app_launcher_list.txt`。镜像中没有名称或 appid 含 video/media/player 的 UI 应用；存在浏览器、隐藏 WebView、图库 UG 和板载媒体测试工具。

| 类别 | appid/工具 | 可执行路径 | launchpad 子进程 | 本轮事实 |
|---|---|---|---|---|
| 浏览器 | `AppL` | `/usr/apps/AppL/bin/chrome_tizen` | 是，主 PID 9098 的 PPID=740，740 为 `ServiceJ` | 可前台启动并保持 60 s；多进程 |
| 隐藏 WebView | `AppK` | `/opt/usr/globalapps/AppK/bin/efl_webview_app` | 是，PID 11625 的 PPID=740 | 可启动，含 `efl_webprocess` 子进程；终止时出现 ANR，见异常项 |
| Web 服务 | `AppM` | `/usr/bin/wrt-service` | 未启动，无法判定 | `Nodisplay=1`，不是本轮前台浏览器候选 |
| Web 服务 launcher | `AppN` | `/usr/bin/wrt-service-launcher` | 未启动，无法判定 | `Nodisplay=1` |
| 图库 UG | `attach-panel-gallery` | `/usr/ug/bin/attach-panel-gallery` | 启动后 5 s 内退出，未取得 PPID | `app_launcher` 给出 PID 11544，但随后 `not running` |
| 相机 UG | `attach-panel-camera` | `/usr/ug/bin/attach-panel-camera` | 未启动 | 仅按图像类名称筛出；本轮不访问相机 |
| NUI 图形候选 | `AppJ` | `/usr/apps/AppJ/bin/NUIGadgetViewer.dll` | 未启动 | `dotnet-nui`，仅列入清单，不在浏览器/播放范围内启动 |
| 常驻 UI | `AppQ` | `/usr/apps/AppQ/bin/runner` | 是，PID 960 的 PPID=740 | 已有常驻进程，本轮不重启 |
| 常驻 UI | `AppX` | manifest 为 `AppUIA.dll`；运行 exe 为 `/usr/bin/dotnet-hydra-loader` | 否，PID 1013 的 PPID=869 | 已有常驻进程，本轮不重启 |
| 平台播放测试件 | `player_test` | `/usr/bin/player_test` | 否，不是 appid | 可经 Wayland 会话环境自动播放 |
| GStreamer 测试件 | `gst-launch-1.0` | `/usr/bin/gst-launch-1.0` | 否，不是 appid | 可命令行解码播放 |

`pkginfo --appcontrol` 对浏览器、WebView、图库均没有列出 app-control 条目。候选元数据原文见 `candidate_metadata.txt` 与 `additional_candidate_metadata.txt`。

## 3. 浏览器探查

### 3.1 启动与进程架构

启动原文：

```text
$ app_launcher -s AppL
... successfully launched pid = 9098 with debug 0
HOST_RC=0

[aul_app_lifecycle_get_state test] AppL
==> result: 0, state: RESUMED
```

进程树确认是多进程架构，而不是单进程浏览器：

```text
chrome_tizen,9098
  `-chrome_tizen,9120 --type=zygote
      |-chrome_tizen,9166 --type=renderer
      |-chrome_tizen,9167 --type=renderer
      `-chrome_tizen,9194 --type=renderer
```

完整 `ps -ef`、PID/PPID/exe/cmdline 与 `pstree` 位于 `browser_initial/`。本次只有一个标签页可见的启动过程，但启动即产生 3 个 renderer；因此不能把 renderer 数机械解释为“每标签一个进程”。

### 3.2 URL 命令行加载

对 `https://example.com/` 逐项执行：

```text
$ app_launcher -s AppL __APP_SVC_URI__ https://example.com/
... successfully launched pid = 9098 with debug 0
RC=0

$ aul_test launch AppL __APP_SVC_URI__ https://example.com/
[aul_launch_app test] AppL
... test successful ret = 9098
RC=0

$ aul_test launch AppL \
    __APP_SVC_OPERATION__ http://tizen.org/appcontrol/operation/view \
    __APP_SVC_URI__ https://example.com/
... test successful ret = 9098
RC=0

$ aul_test open_content https://example.com/
... test successful ret = 0
RC=0
```

四条命令均只证明 AUL 请求返回成功。请求前后仍为同一主 PID、同一 zygote 和同 3 个 renderer；dlog 中没有 `example.com` 的 `StartJob`、`DidFinishLoad` 或标题记录。日志里出现的网络请求仅为 Chromium 自身的 Google update/checkin/safebrowsing 请求，并以 `ERR_NAME_NOT_RESOLVED` 失败。

**URL 自动加载判定：FAIL（未证实页面加载）**。返回码 0 不作为页面加载成功证据。完整原文见 `browser_url_attempts.txt` 和 `browser_after_60s/dlog_filtered.txt`。

### 3.3 内存分布

单位为 MiB，均为 `Private_Dirty`。分类口径与既有 `reclaim_probe` 一致。

| 时点/PID | 角色 | glibc-heap | other-anon | file-backed | 总 PD |
|---|---|---:|---:|---:|---:|
| 启动后 9098 | browser main | 18.426 | 8.992 | 10.039 | 37.457 |
| 启动后 9120 | zygote | 0.219 | 0.215 | 0.191 | 0.625 |
| 启动后 9166 | renderer | 1.898 | 2.133 | 0.520 | 4.551 |
| 启动后 9167 | renderer | 4.477 | 19.273 | 0.688 | 24.438 |
| 启动后 9194 | renderer | 1.848 | 1.316 | 0.461 | 3.625 |
| **启动后合计** | 5 个进程 | **26.867** | **31.930** | **11.898** | **70.695** |
| **额外 60 s 后合计** | 同 5 个进程 | **27.023** | **27.375** | **11.629** | **66.027** |

启动后 glibc-heap 占聚合总 PD 的 38.00%；额外 60 s 后占 40.93%。glibc-heap 有可见体量，但不是进程组的绝对多数。由于 URL 页面加载未证实，本轮没有把这组空白/初始页数据表述为“网页加载后”画像。

### 3.4 前台存活性

浏览器启动于 12:12:29 KST；12:13:43 与 12:14:43 均为同一 PID 9098、`RESUMED`，所有 5 个进程仍存在。额外 60 s 观察结果：**PASS，未被系统终止**。本轮没有浏览器终止原因需要归档；dlog 未见对应 LMK/OOM/fatal。

探查后执行 `app_launcher -t AppL`，返回 0，随后为 `not running`。

## 4. 视频播放探查

### 4.1 介质与 UI app-control

`lsblk` 确认 U 盘 `/dev/sda1` 挂载于 `/opt/media/USBDriveA1`，只读列目录发现：

```text
-r--r--r--  4102390  Argentina.mp4
-rw-rw-rw- 59938456  64687_VID_BM_MM_h265_fhd_seamless.mp4
```

本轮未写 U 盘。`aul_test get_mime_file` 将 `Argentina.mp4` 识别为 `video/mp4`，但 `get_default_app` 返回 `(null)`。应用清单中没有视频播放器 appid，故没有可执行的 `app_launcher -s <video-appid>` 目标。

```text
$ aul_test open_file /opt/media/USBDriveA1/Argentina.mp4
... test successful ret = 0
$ aul_test open_content /opt/media/USBDriveA1/Argentina.mp4
... test successful ret = 0
$ aul_test open_content file:///opt/media/USBDriveA1/Argentina.mp4
... test successful ret = 0
```

三次调用后 `app_launcher -S` 没有新增 appid，进程扫描也没有新增播放器。因此 **UI 播放 app-control 判定：FAIL**；成功返回仅代表请求被接受。

### 4.2 可用的替代播放入口

命令探测：

| 工具 | 状态 |
|---|---|
| `gst-launch-1.0` | 存在 |
| `player_test` | 存在 |
| `player_audio_test` / `player_es_push_test` | 存在 |
| `gst-play-1.0` | 缺失 |
| `mediaplayer` | 缺失 |

`player_test` 直接从普通 sdb shell 启动时报告 `failed to connect display, err -12`。复用前台 `<USER>` 会话的 `WAYLAND_DISPLAY=wayland-0`、`XDG_RUNTIME_DIR=/run/user/5001`、`ELM_ENGINE=wayland_egl` 后，可创建窗口并完成平台 player 流程：

```text
*** input mediapath.
1. After player_create() - Current State : 1
change surface type to OVERLAY
[Player_Test] video_changed_cb!!!! 720 x 480, 30, 0
After player_prepare() - Current State : 2
player_start returned [0]
player_stop returned [0]
After player_unprepare() - Current State : 1
```

完整、可复现的输入流和输出见 `video_player_test/transcript.txt`。因此 **板载测试工具的命令驱动播放：PASS**，但它不是产品播放器 appid。

同时验证 GStreamer 路径：

```text
gst-launch-1.0 -e playbin \
  uri=file:///opt/media/USBDriveA1/64687_VID_BM_MM_h265_fhd_seamless.mp4 \
  video-sink='fakesink sync=true' audio-sink='fakesink sync=true'

Pipeline is PREROLLED ...
Setting pipeline to PLAYING ...
Got EOS from element "playbin0".
Execution ended after 0:00:15.109185417
Setting pipeline to NULL ...
Freeing pipeline ...
```

该路径完成了解复用/解码并按媒体时钟运行，但使用 fakesink，不代表产品 UI 显示路径。

### 4.3 播放前/中/停止后画像

单位为 MiB `Private_Dirty`。

| 路径/时点 | PID | glibc-heap | other-anon | file-backed | 总 PD | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `player_test` 创建后、播放前 | 10877 | 0.313 | 0.207 | 1.582 | 2.102 | player state 1 |
| `player_test` 播放中 | 10877 | 0.313 | 0.227 | 1.582 | 2.121 | `player_start returned [0]` |
| `player_test` stop 后 | 10877 | 0.313 | 0.227 | 1.582 | 2.121 | `player_stop returned [0]` |
| `media-server` 播放前 | 443 | 0.656 | 0.480 | 1.047 | 2.184 | 常驻 |
| `media-server` 播放中 | 443 | 0.656 | 0.480 | 1.047 | 2.184 | 常驻 |
| `media-server` stop 后 | 443 | 0.656 | 0.480 | 1.047 | 2.184 | 常驻 |
| GStreamer 解码播放中 | 10553 | 8.465 | 84.273 | 0.750 | 93.488 | playbin PLAYING |
| GStreamer EOS 后 | 不存在 | n/a | n/a | n/a | 0 retained | 正常退出 |

平台 `player_test` 的 glibc-heap 在三点均为 0.313 MiB，other-anon 仅增长 0.020 MiB；`media-server` 三点逐字段不变。由这些 `/proc/<pid>/smaps` 数据只能确认播放缓冲没有体现在这两个进程的 glibc-heap 私有脏页中，不能进一步仅凭本轮数据把未计入部分断言为 DMA-buf。

GStreamer 解码进程播放中 84.273 MiB（90.14% 总 PD）落在 other-anon，glibc-heap 为 8.465 MiB（9.05%）。该进程 EOS 后退出，不留下可对其调用 trim 的停止后驻留状态。

**解码缓冲区间判定：** 已观测的大体量用户态增长位于 `other-anon`，不是 glibc-heap；平台 player 路径则未在被画像进程的三类 PD 中出现大体量增长。

## 5. 输入自动化能力

设备节点存在：`/dev/input/event0..3`、`/dev/input/mice`，以及 root-only `/dev/uinput`。但镜像中没有现成输入注入命令：

| 路径 | 结果 |
|---|---|
| `evtest` | MISSING |
| `sdb-shell-input` | MISSING |
| `uinput-tool` | MISSING |
| `input` | MISSING；`sdb shell input --help` 原文为 `/bin/sh: input: command not found` |
| `xdotool` / `wtype` / `ydotool` | 文件名扫描无命中 |
| `efl_util` | MISSING |
| Ecore/Evas 输入测试工具 | 文件名扫描无命中；仅有图像转换工具 `ecore_evas_convert` |
| sdb 自身 input 子命令 | `sdb help` 只列出通用 `shell`，没有 input/key/event 子命令 |
| `efl_debug` | 存在，但连接 debug daemon 失败；不是已验证输入入口 |

**输入自动化判定：没有可直接使用的现成输入注入工具。** `/dev/uinput` 的存在只证明内核节点存在，本轮没有编写或注入新的输入程序。

## 6. 可行性判定

| 候选 | 可自动化驱动 | glibc 堆是否内存主体 | 适合作为 L6 补测目标 | 阻塞事实 |
|---|---|---|---|---|
| Chromium 浏览器 `AppL` | **否**：可自动启动/停止，但 URL 加载未证实，且无输入注入工具 | **否**：进程组 glibc-heap 为总 PD 的 38.00%（60 s 后 40.93%）；有可见体量但未过半 | **否（当前环境）** | 无法制造并验证“页面大量分配→集中释放”相位；本轮只得到初始页画像 |
| 隐藏 WebView `AppK` | **否** | 未画像 | **否** | 启动参数被当作异常 URL；终止请求出现 ANR 并由 AMD status 9 清理 |
| Gallery UG `attach-panel-gallery` | **否** | 未画像 | **否** | 无 app-control 条目；独立启动后 5 s 内退出 |
| 产品 UI 视频播放器 | **否** | n/a | **否** | 镜像没有视频播放器 appid/default app；`aul_test open_*` 未启动进程 |
| 平台 `player_test` | **是**：可脚本化 create/prepare/play/stop | **否**：glibc-heap 仅 0.313 MiB，播放前后无增长 | **否** | 没有形成可供 L6 回收的大体量 glibc 驻留堆 |
| GStreamer `gst-launch-1.0` | **是** | **否**：播放中 90.14% 总 PD 在 other-anon，9.05% 在 glibc-heap | **否** | EOS 后进程退出，不存在停止后的驻留 trim 时点；且大体量增长不在 glibc-heap |

本表只回答本轮候选是否具备可复现驱动和 glibc 作用面，不包含 `malloc_trim` 补测或上线判断。

## 7. 异常与恢复

- 隐藏 WebView `AppK` 的 `app_launcher -t` 返回 `-6`；随后 `aul_test terminate_app_async` 返回 0，但 AMD 在超时后记录 `Application is Not Responding`，最终进程 status 9。该候选已标为不可用，未继续探查。
- 第一次卸载临时 `/root` tmpfs 返回 `target is busy`。定位到本轮遗留的 PID 11832 `aul_test terminate_app_async AppK` 仍以 `/root` 为 cwd；终止该探查命令后卸载成功。
- dmesg 本轮尾部没有新增 LMK、OOM、killed process、segfault 或 fatal signal；只有启动期的 `oom_control is deprecated` 和既有 `oom_adj is deprecated` 提示。
- 收尾验证：三个启动过的 appid 均 `not running`；`chrome_tizen`、`efl_webview_app`、`efl_webprocess`、`player_test`、`gst-launch-1.0` 全部 absent；`ROOT_TMPFS_ABSENT`、`PROBE_ABSENT`。

## 8. 原始证据

原始目录：`board_results/l6_target_feasibility_20260807/`

完整文件与字节数清单：`manifest.txt`。

- 身份/通道：`identity_and_channel.txt`
- 完整应用清单：`app_launcher_list.txt`
- 命令、介质、工具基线：`baseline_capabilities.txt`
- app/pkg 元数据：`candidate_metadata.txt`、`additional_candidate_metadata.txt`
- 浏览器：`browser_start.txt`、`browser_initial/`、`browser_url_attempts.txt`、`browser_60s_survival.txt`、`browser_after_60s/`、`browser_cleanup.txt`
- 视频 app-control：`video_entry_probe.txt`、`video_appcontrol_attempts.txt`
- GStreamer：`video_gst_play.log`、`video_profiles/`
- 平台 player：`video_player_test/transcript.txt`、`video_player_test/before_play.txt`、`video_player_test/during_play.txt`、`video_player_test/after_stop.txt`
- 输入能力：`input_automation_deep_probe.txt`
- 异常/恢复：`other_candidate_launches.txt`、`other_candidate_dlog.txt`、`webview_cleanup.txt`、`root_busy_diagnosis.txt`、`final_cleanup.txt`、`final_verification.txt`
