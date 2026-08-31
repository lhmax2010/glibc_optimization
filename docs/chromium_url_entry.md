> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Chromium 指定 URL 驱动路径

状态：**已取得可用的非持久驱动路径；B1 app-control bundle 路径不成立，B2 transient service 路径成立**

记录日期：2026-08-13；原始证据根：`board_results/chromium_url_entry_20260813/`。

本报告只记录事实、派生量与任务要求的可行性结论，不作上线裁决。

## 1. 身份门与环境

与 A 线共用的三重身份门通过：

```text
kernel=6.12.80-arm-rpi4-v7l
arch=armv7l
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
glibc-2.40-2.8.armv7l
```

display-manager 全程为 PID 2600、active/running、`NRestarts=3050`；Wayland socket
`/run/wayland-0` 存在。初始 AppUIB/AppUIA PID 为 21210/23862。板上没有
`lldb`；B4 时复核也没有 `gdb`。

Chromium 包为 `chromium-efl-1.1.144-1.armv7l`，Source RPM 字段为
`chromium-efl-1.1.144-1.src.rpm`；运行日志报告 Chromium `144.0.7559.132`。

## 2. B1：认哪个 app-control key

### 2.1 静态事实

实际 manifest 是 `/usr/share/packages/AppO`。它注册
`AppK`，exec 为 `efl_webview_app`，但没有声明任何
app-control operation、uri 或 mime 节点。

`strings` 结果中：

- `efl_webview_app` 没有 app-control/bundle getter；匹配项均是 EWK 自身的 URI、mime、policy API。
- `AppUIC` 和 `mini_browser` 链接 app-control 相关库，但没有发现消费 launch bundle URI 的字符串证据。
- `libchromium-impl.so` 含通用 `app_control_get_extra_data`、`appsvc_get_uri` 等 API；这不能证明 demo entry 使用它们。

| 检查面 | operation | URI | mime/extra data | 事实 |
|---|---|---|---|---|
| package manifest | 未声明 | 未声明 | 未声明 | 只有 ui-application exec/label/privileges |
| `efl_webview_app` strings | 未见 getter | 未见 bundle URI getter | 未见 bundle getter | 仅有 EWK 页面回调相关字符串 |
| `AppUIC` / `mini_browser` strings | 未见消费证据 | 未见消费证据 | 未见消费证据 | 只确认链接 app-control 相关库 |
| `libchromium-impl.so` | 有通用 API | 有通用 API | 有通用 API | 库级能力，不是 demo entry 调用证据 |

可访问的 Tizen `tizen_src` 源码快照给出决定性实现事实：

```text
app.c:435    ewk_set_arguments(argc, argv)
app.c:454    ecore_getopt_parse(...)
app.c:455-462 第一个不以 '-' 开头的剩余 argv 被 strdup 为 start_url
app.c:583    set_url_from_user_input(view, start_url)
```

该 entry 没有读取 app-control bundle，因此 launchpad 注入的第一个位置参数会先于
`__APP_SVC_URI__` 值成为 URL。

### 2.2 动态尝试

指定 URL 均为 `file:///tmp/chromium_url_entry_simple.html`。表中的 progress=1 与
DidFinish 若实际 URL 是 token，表示 DNS 错误页完成，并不表示指定文件完成。

| 尝试 | shell exit | 实际 `ewk_view_url_set` URL | progress / DidFinish | 指定 URL 加载 |
|---|---:|---|---|---|
| `app_launcher -s ... __APP_SVC_URI__ URL` | 0 | `http://<LAUNCH_TOKEN>` | 1 / 有 | 否 |
| operation/view + URI + text/html | 0 | 同一 token | 1 / 有 | 否 |
| `aul_test launch` 同一标准 bundle | 89；工具内部打印成功 PID 32601 | 同一 token | 1 / 有 | 否 |
| `aul_test open_content FILE` | 0 | 没有 Chromium URL 记录，也没有测试进程 | 无 | 否 |
| `app_launcher -e ... __APP_SVC_URI__ URL` | 0 | 同一 token | 1 / 有 | 否 |
| `launch_app ... __APP_SVC_URI__ URL` | 0 | 同一 token | 1 / 有 | 否 |

token 路径均伴随：

```text
[NETWORK ERROR] Failing url : http://<LAUNCH_TOKEN>/
Error code : -105 Error message : net::ERR_NAME_NOT_RESOLVED
```

因此 B1 未发现 `efl_webview_app` 会消费的 key 组合。它不是 key 拼写问题，而是
该 demo entry 的 argv 处理方式。

## 3. B2：正式域内启动 AppUIC

### 3.1 现有机制探测

板上存在 `systemd-run`、`runuser` 和 `launch_app`，不存在 `setpriv`、`run-as`
或 `smackexec`。没有调用 `chsmack`，也没有修改任何 Smack 规则或文件 label。

只执行身份与 `/dev/shm` 临时写入探针：

```text
runuser: failed to establish user credentials: Failure setting user credentials
RUNUSER_EXIT=1

systemd-run --wait --pipe --collect --uid='<USER>' --gid=users ...
uid=5001(<USER>) gid=100(users) ... context="System::Privileged"
attr_current=System::Privileged
shm_write=PASS
Finished with result: success
SYSTEMD_RUN_EXIT=0
```

测试文件当场删除，transient unit 执行后不存在。

### 3.2 AppUIC 指定 URL 实测

使用平台现有 transient service，不写 unit 文件：

```text
systemd-run --no-block --collect --unit=chromium-url-entry-AppUIC \
  --uid='<USER>' --gid=users -p SupplementaryGroups=display \
  -E XDG_RUNTIME_DIR=/run/user/5001 -E WAYLAND_DISPLAY=wayland-0 \
  -E HOME=/opt/usr<USER_HOME> \
  /usr/apps/AppK/bin/AppUIC -v -n \
  file:///tmp/chromium_url_entry_simple.html
```

关键原文：

```text
ewk_view_url_set ... url: file:///tmp/chromium_url_entry_simple.html
LoadProgressChanged ... progress : 0.1
DidFinishLoad
LoadProgressChanged ... progress : 1
```

进程事实：主进程 PID 1345、renderer PID 1376，均 UID 5001、GID 100、
`CapEff=0`、`attr_current=System::Privileged`；renderer `NoNewPrivs=1`。unit 在采集时
active，停止后 `could not be found`，即没有留下 persistent/transient unit。

**B2 判定：已取得可用的指定 URL 驱动路径。** 该判定只覆盖当前 RPI4 测试镜像
中现有 `systemd-run` + `System::Privileged` 执行域，不推断产品镜像或上线权限模型。

## 4. B3：demo app 改动成本（静态评估）

B2 已成功，因此没有实施 B3。等待 A 线期间只做了 host 静态评估：

- 官方 `tizen_src` 仓库可访问；取到的源码快照为 75 MiB，SHA-256
  `ebd1b85791addad8ad9d40e9790b4fd614ac43aea4e597c08990b7a3127364d4`。
- 与板上 release 精确对应的 SRPM URL 可访问，但 Content-Length 为
  7,226,509,561 byte；未下载、未构建、未签名、未安装。
- `efl_webview_app/app.c` 的代码改动面局限于启动参数/bundle 消费：当前只取首个
  positional argv。源码快照中未发现可直接沿用的 app-control lifecycle handler。
- `AppUIC/main.cc:290-310` 的 Tizen app lifecycle 块由 `TIZEN_APP` 条件关闭；
  `AppUIC/BUILD.gn:34-38` 同时注释掉该 define，并注明需 proper manifest。

所以代码改动本身是局部 entry 处理，完整交付仍需 Chromium-EFL 大型 SRPM 的构建、
manifest/打包和平台签名链。由于 B2 已提供现成路径，本轮未对工时作未经实测的小时数估算。

## 5. B4：重页面到 about:blank 快速验证

### 5.1 相位证据

自包含页面生成 12,000 个 DOM 节点和 32 个 512x512 canvas，title 为
`Chromium URL Entry Heavy Probe`，20 s 后执行 `location.href="about:blank"`。

```text
ewk_view_url_set ... file:///tmp/chromium_url_entry_heavy.html
Set title: Chromium URL Entry Heavy Probe
DidFinishLoad
LoadProgressChanged ... progress : 1

Set location to url[about:blank]
Set title: about:blank
DidFinishLoad
LoadProgressChanged ... progress : 1
```

这同时验证了指定重页面实际解析和 `about:blank` 释放动作实际发生。

### 5.2 两点画像

分类值为 Private_Dirty，单位 KiB：

| 进程 | 相位 | glibc-heap | other-anon | file-backed | total PD |
|---|---|---:|---:|---:|---:|
| 主进程 PID 2376 | heavy | 11,144 | 5,676 | 9,608 | 26,428 |
| 主进程 PID 2376 | blank + 10 s | 11,144 | 5,712 | 9,600 | 26,456 |
| renderer PID 2419 | heavy | 2,348 | 78,632 | 472 | 81,452 |
| renderer PID 2419 | blank + 10 s | 2,444 | 53,576 | 472 | 56,492 |

导航后差量：主进程 glibc-heap `0 KiB`，renderer glibc-heap `+96 KiB`；renderer
other-anon `-25,056 KiB`。本次页面负载释放的可见 PD 下降发生在 renderer
other-anon，不是 glibc-heap。

### 5.3 malloc_info 限制

板上 `lldb`、`gdb` 均不存在，AppUIC 没有外部 `malloc_info` 导出接口。本任务
不安装工具、不改 demo、不做注入，因此未采到 T1/T2 malloc_info，M7 状态为
`NOT_COLLECTED_NO_INJECTION_INTERFACE`；不能仅凭 PD 变化替代 M7。

## 6. 结论、限制与恢复现场

1. B1 没有可用 key：所有 bundle 组合均加载 token，而非指定 URI。
2. B2 的 transient `systemd-run` 路径可以用位置参数驱动 AppUIC，指定本地页和
   后续 `about:blank` 均有实际 URL 与 DidFinish/progress=1 证据。
3. B4 已证明内容加载/释放相位可构造；本次重页面的 renderer PD 下降主要是
   other-anon。M7 因缺少非持久采集接口未验证。
4. 所有 Chromium 测试进程均已关闭；三个测试 transient unit 均不存在。
5. `/root/chromium_url_entry`、两个 `/tmp/chromium_url_entry_*.html` 均已删除。
6. 最终 display-manager PID 2600、`NRestarts=3050`，AppUIB/AppUIA PID
   21210/23862 仍在；dmesg 没有 OOM/LMK/fatal 匹配。

## 7. 原始文件清单

- 共用身份环境：`board_results/l6_applicability_curve_20260813/stage1/shared_environment.txt`
- B1 manifest/帮助/strings/RPM：`board_results/chromium_url_entry_20260813/b1_static/`
- B1 六次动态尝试：`board_results/chromium_url_entry_20260813/dynamic/<attempt>/`
- B2 域探针：`dynamic/b2_domain_probe/`
- B2 AppUIC：`board_results/chromium_url_entry_20260813/b2_AppUIC/`
- B3 源码与仓库证据：`board_results/chromium_url_entry_20260813/b3_source/`
- B4 重页面、日志与画像：`board_results/chromium_url_entry_20260813/b4_phase/`
- 运行脚本与测试 HTML：`board_results/chromium_url_entry_20260813/run_*.sh`、
  `chromium_url_entry_*.html`
- 最终清理：`board_results/chromium_url_entry_20260813/final/l6_combined_cleanup_evidence.txt`、
  `final/l6_final_verify_exact.txt`
