> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Chromium 页面加载诊断

- 日期：2026-08-13
- 板：RPI4 测试板 `<TEST_BOARD_IP>:26101`
- 通道：`<USER_HOME>/tizen-studio/tools/sdb -s <TEST_BOARD_IP>:26101`
- 范围：只诊断；未安装包、未改持久配置、未重启 service、未做 L6/trim 测量
- Chromium 包：`chromium-efl-1.1.144-1.armv7l`，运行日志报告 Chromium `144.0.7559.132`
- 原始证据：`board_results/chromium_load_diagnosis_20260813/`
- 公开归档说明：完整原始件仅在 host 本地留存，可按请求提供；下文文件名均为非链接引用。

## 1. 身份门与环境

身份脚本执行了合同中的内核、架构和产品镜像三重断言，退出码为 0：

```text
IDENTITY_OK
Linux localhost 6.12.80-arm-rpi4-v7l ... armv7l GNU/Linux
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
glibc-2.40-2.8.armv7l
uid=0(root) ... context="User::Shell"
```

证据：`identity_environment.txt`。

| 环境项 | 实测 |
|---|---|
| `display-manager` | `active/running`，MainPID `2600`，全程 `NRestarts=3050` |
| Wayland | `/run/wayland-0` 存在；`/run/user/5001/wayland-0 -> /run/wayland-0` |
| HDMI | `HDMI-A-1=disconnected`，`HDMI-A-2=disconnected` |
| EGL/GLES | `libEGL.so.1.5`、`libGLESv2.so.2.0` 已安装，`ldd` 无 `not found` |
| Chromium 入口 | `AppUIC`、`efl_webview_app`、`mini_browser` 均在 `/usr/apps/AppK/bin/` |

环境与动态链接证据：`stage0/`、`binaries_ldd.txt`。

## 2. Q2 分层结果

每层均以独立 `AppUIC -v -n <URL>` 进程运行并抓取完整 `dlogutil -v time '*:V'`。原始直接启动未人为补环境变量，正好复现此前调用方式。

| 层 | 请求 | `ewk_view_url_set` | LoadProgress | 首个错误/结果 |
|---|---|---|---|---|
| L1 | `about:blank` | `view: 0`，URL 接受 | 无回调 | `XDG_RUNTIME_DIR is invalid or not set`，随后 `EGL_NOT_INITIALIZED` |
| L2 | `data:text/html,...` | wrapper 改写成 `http://data:text/html,...`，`view: 0` | 无回调 | 同 L1；本层未形成有效 `data:` 导航 |
| L3 | 极简 `/tmp` 文件 | `view: 0`，URL 接受 | 无回调 | 同 L1 |
| L4 | 少量 DOM 文件 | `view: 0`，URL 接受 | 无回调 | 同 L1 |
| L5 | heavy 文件 | `view: 0`，URL 接受 | 无回调 | 同 L1；未出现页面标记 |

**第一个失败层是 L1 `about:blank`。** 原始 shell 启动在内容、文件 I/O 和网络之前，便已因缺少 Wayland runtime 环境而无法建立有效 EWK view。因此 L3-L5 的失败不能归因于页面复杂度。

逐层原始日志：`L1/`、`L2/`、`L3/`、`L4/`、`L5/`。

### 2.1 XDG 对照揭示第二个卡点

仅对进程临时设置：

```sh
XDG_RUNTIME_DIR=/run/user/5001 WAYLAND_DISPLAY=wayland-0 AppUIC -v -n <URL>
```

之后 L1 与 L3 均建立非零 view，开始导航并到达 `LoadProgress=0.1`，但 renderer 随即因 `/dev/shm` 写入失败而 FATAL：

```text
ewk_view_url_set ... view: 0x..., url: about:blank
LoadProgressChanged ... progress : 0.1
Creating shared memory in /dev/shm/.org.chromium.Chromium.* failed: Permission denied (13)
Unable to access(W_OK|X_OK) /dev/shm: Permission denied (13)
FATAL ... Try 'sudo chmod 1777 /dev/shm' to fix.
```

证据：`L1_xdg/dlog_full.txt`、`L3_xdg/dlog_full.txt`。该对照精确复现了历史的“卡在 0.1”。

## 3. Q1 关键时间线

以最简 L1 为例，板端时间为 `+0900`：

| 时间 | 事件 |
|---|---|
| 22:02:40.065 | 原始启动调用 `ewk_init` |
| 22:02:40.068 | Wayland 报 `XDG_RUNTIME_DIR is invalid or not set` |
| 22:02:40.493 | `eglInitialize Default failed: EGL_NOT_INITIALIZED` |
| 22:02:40.528 | `ewk_view_url_set(view: 0, about:blank)`；此后无进度回调 |
| 22:07:00.977 | XDG 对照：`ewk_view_url_set(view: 0x80004995, about:blank)` |
| 22:07:01.037 | `LoadProgressChanged: 0.1` |
| 22:07:01.038 | `DidStartNavigation` |
| 22:07:01.145 | renderer PID 9216 创建 `/dev/shm` 对象被拒绝 |
| 22:07:01.183 | renderer FATAL；捕获窗口内无 `DidFinishLoad` 或进度增长 |

同一个 renderer PID 9216 在 T02/T07/T12/T17/T22/T27 始终处于 `R` 状态，没有反复重建；它并非健康渲染，只是 FATAL 后未及时退出，最终随父进程关闭。证据：`process_timeline.txt`。

## 4. Q3 权限与沙箱

### 4.1 页面文件不是第一个权限卡点

| 文件 | Unix 权限 | Smack label | XDG 对照结果 |
|---|---|---|---|
| `/tmp/chromium_diag_l3.html` | `0777 root:root` | `System` | 0.1 后 `/dev/shm` FATAL |
| `/opt/usr/home/owner/chromium_diag_l3.html` | `0777 root:root` | `User::Shell` | 0.1 后同一 `/dev/shm` FATAL |

更换文件目录和 label 没有改变错误。证据：`file_permissions.txt`、`L3home_xdg/`。板上无 `getfattr`，Smack label 由 `ls -Z` 取得。

### 4.2 `/dev/shm` 的 Unix 权限正确，Smack 写权限不足

```text
/dev/shm: drwxrwxrwt root root System::Run
mount: tmpfs (rw,nosuid,nodev,noexec)
capacity: 1.9G, used 252K
User::Shell System::Run rxl
User::Pkg::AppK System::Run rwxat
```

因此 Chromium 日志中的 `chmod 1777` 通用提示不适用于本板：目录已经是 1777。直接启动的主进程为 UID 0、`User::Shell` 且保留全部 capabilities；它可创建测试文件。renderer 仍为 UID 0/`User::Shell`，但 `CapEff=0`、`NoNewPrivs=1`，不能借 capability 越过 Smack，且 `User::Shell -> System::Run` 规则没有 `w`。

renderer 命令行含 `--no-sandbox`，`Seccomp=0`；日志中没有 Chromium sandbox 拒绝。这里的实测拒绝是 Smack/MAC 访问 `/dev/shm`，不是 Chromium seccomp sandbox。

证据：`shm_smack.txt`、`smack_rules_probe.txt`、`smack_and_l5.txt`、`process_security.txt`。

## 5. Q4 渲染与合成侧

| 检查 | 结果 |
|---|---|
| renderer 存活/重启 | XDG 对照中创建 1 个 renderer；捕获期未换 PID，但在 `/dev/shm` FATAL 后不再推进 |
| EGL/GPU 映射 | 主进程映射 `libEGL.so.1.5`、`libGLESv2.so.2.0`、`libdrm`、`libtbm`、Wayland EGL；renderer 映射 Wayland EGL、DRM、TBM |
| HDMI disconnected | 不是决定性卡点；补齐 XDG 后 EGL 不再报初始化失败，并建立 1920x1079 Wayland surface |
| `AppUIC --help` | 只暴露 inspector/gui-level/help 等 wrapper 选项 |
| `--disable-gpu` | `AppUIC: unrecognized option '--disable-gpu'`；随后仍到 0.1 并死于 `/dev/shm` |
| `--headless` | wrapper 拒绝；结果同上 |
| `--use-gl=swiftshader` | wrapper 拒绝；结果同上 |

`libchromium-impl.so` 内确有 `disable-gpu`、`headless`、`use-gl`、SwiftShader 字符串，但 AppUIC wrapper 不转发本轮试验的参数，不能据内部字符串认定入口支持这些开关。

证据：`L1_xdg/maps_gpu_9166_T07.txt`、`switches/`、`impl_switches.txt`。

## 6. Q5 替代入口

| 入口 | 请求/实际 URL | 进度 | 结果 |
|---|---|---|---|
| `efl_webview_app file:///tmp/L3` 直接运行 | 实际为请求的 L3 URL | 0.1 | 与 AppUIC 相同的 `/dev/shm` FATAL |
| `mini_browser` 直接运行 | 固定 `http://www.google.com/` | 0.1 | `ERR_NAME_NOT_RESOLVED`，随后 `/dev/shm` FATAL；未到 1.0 |
| `app_launcher -s AppK __APP_SVC_URI__ <L3>` | **实际为** `http://` + launchpad 首个令牌 | 0.1 -> 0.7 -> 1.0 | `DidFinishLoad`，但不是请求的 L3 页面 |
| 同上请求 L5 | **实际仍为** launchpad 令牌 URL | 0.1 -> 0.8 -> 1.0 | `DidFinishLoad`，未出现 L5 页面标记 |

app framework 对照的进程为 UID 5001，Smack label 为 `User::Pkg::AppK`，renderer capabilities 仍为 0；该域拥有对 `System::Run` 的 `rwxat`，所以不再出现 `/dev/shm` 错误。这证明在 HDMI disconnected 状态下，Chromium renderer 和合成路径可以推进到 `DidFinishLoad`，也验证了 Smack 归因。

但 `efl_webview_app` 将 launchpad 注入的第一个位置参数 `<LAUNCH_TOKEN>` 当成 URL，没有消费 `__APP_SVC_URI__` bundle。因此现有 appid 入口不能直接作为指定页面驱动器。`app_launcher -t` 对这个 demo app 返回 `Failed to terminate ... (-6)`，本轮随后只对该测试 PID 发送 `SIGTERM`，进程及子进程均退出。

证据：`direct_efl/`、`direct_mini/`、`app_efl/`、`app_efl_heavy/`。

## 7. 结论与解决方向

**卡点位于内容加载之前的启动上下文，不是 heavy 页面本身。** 直接从 root/sdb shell 运行 AppUIC 时有两个串联问题：

1. shell 没有 `XDG_RUNTIME_DIR`，导致 Wayland/EGL 初始化失败，EWK view 为 0。
2. 临时补齐 XDG 后，renderer 以 `User::Shell` 且零 capability 运行，Smack 不允许其写 `System::Run` 标记的 `/dev/shm`，所以所有内容无关的导航都在 0.1 FATAL。

建议的解决方向仅限以下诊断结论，不在本轮实施：

- 不应修改 `/dev/shm` Unix mode；它已是 1777。应让测试入口通过已注册应用上下文运行，获得正确的 Wayland 环境和 `User::Pkg::AppK` Smack 域。
- 需要一个能在该应用域中**正确解析 app-control URI**的入口。可修正/替换当前 demo entry 的参数处理，或提供已注册、已签名的诊断 wrapper；现有 `efl_webview_app` appid 路径会误读 launchpad token。
- 无需先解决物理 HDMI：正确应用域对照在两路 HDMI disconnected 时已建立 renderer 并完成一次导航。
- GPU/headless 开关不是当前第一修复点；AppUIC wrapper 目前拒绝这些开关，且 XDG 修正后最早的确定性失败是 `/dev/shm` Smack。

## 8. 失败、限制与恢复现场

- L2 被 AppUIC wrapper 改写为 `http://data:...`，所以不能作为有效 data-scheme 测试；L1 已独立证明失败发生在文件/网络之前。
- `mini_browser` 同时遇到 DNS `ERR_NAME_NOT_RESOLVED` 与 `/dev/shm` FATAL，无法用本轮结果判断正常网络页面加载能力。
- app framework 的 `DidFinishLoad` 对应 launchpad token URL 的错误页，不是 L3/L5 内容；报告未把它冒充页面加载成功。
- 未修改 Smack 规则、`/dev/shm` 权限或任何持久环境。未测试“临时切换 Smack label”之类具有修复性质的操作。
- 原始 `dlog` 中含少量采集命令自身的 `SDBD_TRACE`，结论所列时间线均排除了这些自噪声。

清理后：

```text
NO_PROCESS:AppUIC
NO_PROCESS:efl_webview_app
NO_PROCESS:mini_browser
NO_PROCESS:efl_webprocess
REMOTE_WORKDIR_REMOVED
display-manager: active, MainPID=2600, NRestarts=3050
AppUIB/AppUIA: running
```

证据：`cleanup_and_health.txt`、`final_verify.txt`。

## 9. 原始文件清单

原始目录共 526 个文件、约 120 MiB：

- 身份/环境：`stage0/`
- 包、入口、权限预检：`prescreen/`
- L1-L5 与 XDG/目录对照：`layers/`
- 每层完整 `dlog`、进程时间线、renderer security/maps：上述各 layer 子目录
- Smack 与 `/dev/shm`：`security/`、`permissions/`
- GPU/headless/software 开关：`switches/`
- host 侧 ELF 字符串与映射证据：`rendering/`
- 替代入口：`entries/`
- 采集脚本与测试 HTML：`scripts/`
- 清理和最终健康检查：`cleanup/`
