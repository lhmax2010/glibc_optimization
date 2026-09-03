> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# RPI4 图形环境诊断

- 采集日期：2026-08-12（Asia/Shanghai）
- 目标：`<TEST_BOARD_IP>:26101`
- 通道：`<USER_HOME>/tizen-studio/tools/sdb -s <TEST_BOARD_IP>:26101`
- 操作范围：只读查询；未安装/下载 RPM，未修改配置，未重启服务，未向板上写入临时文件。
- 原始证据目录：`board_results/rpi4_graphics_diagnosis_20260812/`
- 公开归档说明：完整原始件仅在 host 本地留存，可按请求提供；下文文件名均为非链接引用。

## 1. 身份门

执行的门：

```sh
kernel=$(uname -r)
case "$kernel" in *rpi4*) ;; *) exit 97;; esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release; then exit 98; fi
```

结果：`IDENTITY_OK`。

```text
Linux localhost 6.12.80-arm-rpi4-v7l ... armv7l GNU/Linux
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
uid=0(root) ... groups=44(video),201(display),...
```

证据：`identity.txt`。身份门通过，确认不是 `<PRODUCT_IMAGE>` 产品板。

## 2. 缺失库与提供包

### 2.1 `ldd` 完整缺失清单

命令：

```sh
ldd /usr/bin/enlightenment
ldd /usr/apps/AppQ/bin/runner
```

| 目标 | 缺失 SONAME（去重后的完整清单） | 结果 |
|---|---|---|
| `/usr/bin/enlightenment` | `libEGL.so.1`, `libGLESv2.so.2` | 两者均 `not found` |
| `/usr/apps/AppQ/bin/runner` | `libEGL.so.1`, `libGLESv2.so.2` | 两者均 `not found`；出现在 runner 的依赖闭包内 |

除这两个 SONAME 外，两份 `ldd` 输出没有其他 `not found`。完整原文见 `ldd_full.txt`。

对两个缺失库均执行：

```sh
find / -name 'libEGL.so*' 2>/dev/null
find / -name 'libGLESv2.so*' 2>/dev/null
```

两个查询均无结果，是真缺失，不是已有文件未进入 `ld.so` 路径。板上只有相邻但不能替代该 ABI 的 `libtpl-egl.so.1`、`libwayland-egl.so.1` 等。证据：`library_search.txt`。

`rpm -V enlightenment` 还直接报告：

```text
Unsatisfied dependencies for enlightenment-0.20.0-tz11_2.26.0.armv7l:
    libEGL.so.1 is needed ...
    libGLESv2.so.2 is needed ...
```

证据：`target_rpm_requirements.txt`。该文件中的 license/preload 文件缺失与本次动态链接失败无关，但已保留原文。

### 2.2 板上图形包现状

筛选命令：

```sh
rpm -qa | grep -Ei 'mesa|egl|gles|drm|coregl|gl$|vulkan|wayland'
```

完整命中如下：

```text
ServiceV-mod-wayland-core-1.81.6-1.armv7l
building-blocks-sub1-domain_HALAPI-Drm-11.0.0-0.armv7l
building-blocks-sub2-domain_API-UI-Tizen_Core_Wayland-11.0.0-0.armv7l
hal-api-drm-1.0.5-1.armv7l
libdrm-2.4.131-1.3.armv7l
libtpl-egl-1.13.2-0.armv7l
libwayland-client-1.23.1-0.armv7l
libwayland-cursor-1.23.1-0.armv7l
libwayland-egl-1.23.1-0.armv7l
libwayland-egl-tizen-1.1.1-0.armv7l
libwayland-extension-client-1.3.82-0.armv7l
libwayland-extension-server-1.3.82-0.armv7l
libwayland-server-1.23.1-0.armv7l
libwayland-tbm-client-0.9.0-0.armv7l
libwayland-tbm-server-0.9.0-0.armv7l
```

`coregl` 和 `mesa` 均未安装。完整筛选及相关 EFL/TBM 包见 `rpm_graphics.txt`。

### 2.3 官方仓库 provider

查询的是 workspace [`config/gbs.conf`](../config/gbs.conf) 配置的两个 reference 仓库：

```text
Tizen-Base/reference/repos/standard/packages/
Tizen-Unified/reference/repos/standard/packages/
```

只获取了 `repomd.xml`、`primary.xml.gz` 和 `filelists.xml.gz` 元数据，没有获取 RPM。元数据中两个 SONAME 均有两个 capability provider，但文件落点和职责不同：

| 包 | 版本 | 实际文件路径 | 板上状态 | 直接依赖状态 |
|---|---:|---|---|---|
| `coregl` | `0.4.0-0.armv7l` | `/usr/lib/libEGL.so.1`, `/usr/lib/libGLESv2.so.2` | 未安装 | 所有直接 capability 已由当前板上的 bash/glibc/libdlog/libgcc/libtpl-egl 满足 |
| `mesa` | `24.3.4-0.armv7l` | `/hal/lib/driver/libEGL.so.1`, `/hal/lib/driver/libGLESv2.so.2`，另含 Gallium、Broadcom Vulkan、GBM driver | 未安装；`/hal/lib/driver` 与 `/hal/lib/gbm` 均为空 | 所有直接 capability 已由当前板上的 glibc/libdlog/libdrm/libexpat/libgcc/libstdc++/libtbm/libtpl-egl/ttrace/libsystemd/Wayland/zlib 满足 |

就当前普通动态链接器搜索所见，`coregl` 的 `/usr/lib` 文件会直接补齐 `ldd` 缺口；`mesa` 文件位于 HAL driver 目录，是 VC4/V3D 后端候选，不能把单独安装 `mesa` 等同于补齐当前 `/usr/lib` ABI。

元数据证据：`provider_dependency_summary.txt`、`rpi4_display_chain.txt`、`unified_filelists.xml.gz`。板上 capability 对照见 `coregl_board_requirements.txt` 和 `mesa_board_requirements.txt`。

### 2.4 镜像包关系不完整

板上已安装：

```text
building-blocks-sub2-Preset_boards-COMMON-Display-11.0.0-0.armv7l
```

但该元包声明依赖 `coregl`，`rpm -V` 明确报 `coregl` 未满足。另一方面，官方仓库的 RPI4 显示后端元包未安装：

```text
building-blocks-sub2-Preset_boards-RPI4_HAL_Backend-Display-11.0.0-0.armv7l
  -> hal-backend-tbm-vc4-3.2.1-1.armv7l
  -> hal-backend-tdm-vc4-2.2.2-0.armv7l
  -> mesa-24.3.4-0.armv7l
```

板上已有 `/hal/lib/libhal-backend-{tbm,tdm}-vc4.so*` 文件，但 `rpm -qf` 显示这些文件没有 RPM owner；对应两个 backend RPM 也未安装。证据：`image_composition_state.txt`、`display_building_blocks.txt`。

## 3. GPU、DRM 与显示连接

| 项目 | 实测事实 |
|---|---|
| 板型 | `Raspberry Pi 4 Model B Rev 1.5`，DT compatible 为 `raspberrypi,4-model-b`, `brcm,bcm2711` |
| DRM 节点 | `/dev/dri/card0`, `/dev/dri/card1`, `/dev/dri/renderD128` 均存在 |
| KMS/显示驱动 | `card0` 的 sysfs driver 为 `vc4-drm`，DRM name 为 `vc4` |
| 3D 驱动 | `card1` 与 `renderD128` 的 sysfs driver 为 `v3d`，DRM name 为 `v3d` |
| 当前 DRM client | 两个 client 表只有表头，无已打开设备的用户态 client |
| HDMI | `HDMI-A-1=disconnected`, `HDMI-A-2=disconnected`；当前没有显示器连接 |
| kernel log | `dmesg | grep -iE 'vc4|v3d|drm|gpu'` 无输出；`/proc/modules` 也无匹配。内核配置不可读，因此无法由本次证据区分 built-in 与 module；sysfs driver binding 和设备节点证明驱动当前已绑定并创建设备。 |

证据：`hardware_drm.txt`、`hardware_detail.txt`。

结论限于硬件侧事实：GPU/DRM 节点与 VC4/V3D 绑定具备；“无 GPU”不成立。当前同时存在 HDMI 未连接和用户态 EGL/Mesa 包缺失两个独立事实。

## 4. Compositor 现状与期望环境

### 4.1 运行状态

| 项目 | 状态 |
|---|---|
| `display-manager.service` | `activating (auto-restart)`；`ExecStart=/usr/bin/enlightenment` 每约 10 s 退出，`status=127`；采样时 `NRestarts=1689` |
| `display-manager-monitor.service` | active，运行 `/usr/bin/enlightenment_mon.sh` |
| `enlightenment.service` | 不存在；实际 unit 是 `display-manager.service` |
| `weston.service` / `weston` | unit 不存在，命令也不存在 |
| Wayland socket | `/run/wayland-0` 不存在；只有 `/run/user/5001/wayland-0 -> /run/wayland-0` 的悬空软链接 |

状态原文：`compositor_status.txt`、`display_manager_journal.txt`。`journalctl` 只记录 127，没有打印 loader 的 SONAME；缺失 SONAME 由同一 ELF 的 `ldd` 和 RPM 未满足依赖独立确认。

### 4.2 启动方式与环境

活动 unit 为 `/usr/lib/systemd/system/display-manager.service`，无 drop-in：

```ini
[Service]
Type=notify
EnvironmentFile=/etc/sysconfig/enlightenment
ExecStartPre=-/usr/bin/keymap_update.sh
ExecStart=/usr/bin/enlightenment
ExecStartPost=/usr/bin/bash -c "/usr/bin/touch $XDG_RUNTIME_DIR/.wm_ready; echo $MAINPID > $XDG_RUNTIME_DIR/enlightenment.pid"
Restart=always
RestartSec=10
```

关键环境：

```text
E_CONF_PROFILE=tizen-common
XDG_RUNTIME_DIR=/run
XDG_CACHE_HOME=/run
XDG_DATA_DIRS=/usr/local/share:/hal/share
ECORE_DRM_TTY=/dev/tty1
ECORE_DRM_DEVICE_USER_HANDLER=1
ECORE_EVAS_FORCE_SYNC_RENDER=1
ECTOR_BACKEND=default
TBM_DISPLAY_SERVER=1
HOME=/var/lib/enlightenment
```

未设置 `LD_LIBRARY_PATH`。`ExecStartPost` 从未执行，因此不会生成 `/run/.wm_ready` 和 `/run/enlightenment.pid`，monitor 只能持续看到 display server 未就绪。另有 `/etc/isu/enlightenment/system-services/display-manager.service` 模板，但当前 `FragmentPath` 证明它不是活动 unit。完整 unit、sysconfig、monitor 脚本与 ISU 模板见 `compositor_config.txt` 和 `compositor_detail.txt`。

## 5. 仓库可得性与依赖链

| 候选层次 | 官方仓库包 | 版本 | 本板缺失 | 依赖链事实 |
|---|---|---:|---|---|
| 公共 EGL/GLES ABI | `coregl` | `0.4.0-0.armv7l` | 是 | 当前所有直接 runtime capability 已满足；安装尺寸元数据约 2.35 MB |
| RPI4 GPU driver | `mesa` | `24.3.4-0.armv7l` | 是 | 当前所有直接 runtime capability 已满足；安装尺寸元数据约 19.88 MB |
| RPI4 backend 元包 | `building-blocks-sub2-Preset_boards-RPI4_HAL_Backend-Display` | `11.0.0-0.armv7l` | 是 | 依赖 `mesa`, `hal-backend-tbm-vc4`, `hal-backend-tdm-vc4` |
| VC4 TBM backend | `hal-backend-tbm-vc4` | `3.2.1-1.armv7l` | RPM 缺失，裸文件存在且无 owner | 直接 runtime capability 均已存在 |
| VC4 TDM backend | `hal-backend-tdm-vc4` | `2.2.2-0.armv7l` | RPM 缺失，裸文件存在且无 owner | 直接 runtime capability 均已存在 |

没有发现其他缺失的直接依赖包；这里的“已满足”以板上 `rpm --whatprovides` capability 为准。注意 `gbs.conf` 使用可移动的 `reference` 仓库，元数据中的 Base 包 release 与板上 release 并不完全相同；本次只证明候选包及依赖 capability 可得，没有执行事务求解，也没有证明 reference 仓库与 2026-07-28 镜像逐包同源。

## 6. 修复候选（未执行）

| 候选 | 包集合 | 已知依赖问题 | 边界 |
|---|---|---|---|
| 恢复公共 ABI | `coregl-0.4.0-0.armv7l` | 未发现额外缺失 capability | 能直接补 `/usr/lib/libEGL.so.1` 与 `libGLESv2.so.2`，但单独补 ABI 不证明 VC4 硬件渲染链完整 |
| 恢复 RPI4 图形包组成 | `coregl` + `building-blocks-sub2-Preset_boards-RPI4_HAL_Backend-Display`，后者带入 `mesa`、`hal-backend-tbm-vc4`、`hal-backend-tdm-vc4` | 当前直接 runtime capability 均存在；需在与该镜像匹配的固定 snapshot 上做正式包事务校验 | 与仓库声明的 COMMON Display + RPI4 HAL 分层一致；应处理现有无 owner backend 文件，不能假定覆盖行为 |
| 软件渲染（仅无 GPU 场景） | 未找到独立 `llvmpipe`/`swrast`/`softpipe` 包；仓库只检出 `mesa` | 是否在该 Mesa build 内编入软件 rasterizer，metadata 无法判定 | 本板 VC4/V3D 已绑定，“无 GPU”前提不成立；HDMI disconnected 也不能靠软件渲染修复 |

候选不是安装指令。本轮没有执行任何候选，也没有验证补包后的 compositor 启动结果。

## 7. 负面事实

- 缺失库不止 `libEGL` 的猜测已排除：完整 `ldd` 的缺失集合恰好是 `libEGL.so.1` 和 `libGLESv2.so.2`。
- 两个 SONAME 不是单纯路径遗漏：全盘 `find` 无文件。
- `libwayland-egl`、`libtpl-egl` 已安装，但不提供缺失的两个 SONAME。
- 不是“没有 GPU/DRM”：VC4/V3D 已绑定并有 render node。
- 不是 Weston 正在占用 display：Weston 命令和 unit 都不存在。
- 没有活动 Wayland socket；用户目录中的条目只是指向不存在目标的软链接。
- 没有证据表明单独安装 `mesa` 会把 `/hal/lib/driver` 加入普通 `ld.so` 搜索路径。
- 没有找到独立软件 rasterizer 包，也没有从 metadata 证明当前 Mesa 包是否内建 llvmpipe。
