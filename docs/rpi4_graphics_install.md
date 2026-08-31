> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# RPI4 coregl/mesa 安装记录

- 日期：2026-08-12
- 目标：`<TEST_BOARD_IP>:26101`
- 通道：`<USER_HOME>/tizen-studio/tools/sdb -s <TEST_BOARD_IP>:26101`
- 变更范围：安装 `coregl-0.4.0-0.armv7l`、`mesa-24.3.4-0.armv7l`；未安装或升级其他 RPM，未重启整机或 service。
- 原始证据：[`board_results/rpi4_graphics_install_20260812/`](../board_results/rpi4_graphics_install_20260812/)

## 1. 身份门与安装前快照

### 1.1 身份门

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

证据：[`identity_gate.txt`](../board_results/rpi4_graphics_install_20260812/identity_gate.txt)。

### 1.2 RPM 回滚基线

板上执行：

```sh
rpm -qa | sort > /root/pre_install_rpm_list.txt
```

- 安装前 RPM 数：1268
- 安装前清单 SHA-256：`9683274d4e66827f3da9c73b4fa83fb7865419857d3baaed768b791ec18e1983`
- 已拉回：[`pre_install_rpm_list.txt`](../board_results/rpi4_graphics_install_20260812/pre/pre_install_rpm_list.txt)

安装后清单与安装前清单的完整 diff 只有：

```diff
+coregl-0.4.0-0.armv7l
+mesa-24.3.4-0.armv7l
```

证据：[`rpm_list_diff.txt`](../board_results/rpi4_graphics_install_20260812/post/rpm_list_diff.txt)、[`post_install_rpm_list.txt`](../board_results/rpi4_graphics_install_20260812/post/post_install_rpm_list.txt)。因此本轮回滚集合可精确限定为这两个新增 RPM；本轮未执行回滚。

### 1.3 系统基线

| 项目 | 安装前实测 |
|---|---|
| glibc | `glibc-2.40-2.8.armv7l` |
| libc SHA-256 | `d5e36dd6339e95adedcbb01b655bc3df46d233fbba5d98f24105192eb8935015` |
| MemTotal / MemAvailable | `3,976,480 / 3,736,808 kB` |
| rootfs 空间 | 2.9 GB 总量，1.6 GB 可用 |
| `coregl`, `mesa` | 均未安装 |
| EGL/GLES 文件 | `/usr/lib` 与 `/hal/lib/driver` 均无 `libEGL*`、`libGLESv2*` |
| `display-manager` | `activating/auto-restart`，主进程 `status=127`，`NRestarts=3042` |
| failed units | `0 loaded units listed`；该列表不把 auto-restart unit 算作 failed |

完整状态见 [`system_snapshot.txt`](../board_results/rpi4_graphics_install_20260812/pre/system_snapshot.txt)。

## 2. RPM 获取与依赖检查

### 2.1 下载件

来源为 workspace [`gbs.conf`](../gbs.conf) 配置的 Tizen Unified 官方 reference 仓库。

| RPM | URL | SHA-256 | 解包后安装尺寸 |
|---|---|---|---:|
| `coregl-0.4.0-0.armv7l.rpm` | `https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/reference/repos/standard/packages/armv7l/coregl-0.4.0-0.armv7l.rpm` | `8f6deea5b3f77918d1a2a6b5681fd803049911c5a533c297ac766517f6509af6` | 2,348,611 B |
| `mesa-24.3.4-0.armv7l.rpm` | `https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/reference/repos/standard/packages/armv7l/mesa-24.3.4-0.armv7l.rpm` | `cd6f5e48395ec28c89aa1b703d225078a6633eebad2514cc424d2837d48183c8` | 19,884,515 B |

host 与板端 SHA-256 一致。`rpm -Kv` 的 header SHA256/SHA1、payload SHA256 和 MD5 均为 `OK`；输出没有 GPG signature 项，因此本轮只验证了摘要完整性，没有可记录的 RPM GPG 签名验证。

RPM 与审核原文保留在 [`rpms/`](../board_results/rpi4_graphics_install_20260812/rpms/)。

### 2.2 依赖与事务预检

对两个实际 RPM 执行：

```sh
rpm -qpR <rpm>
rpm -qp --conflicts <rpm>
rpm -qp --obsoletes <rpm>
rpm -qp --scripts <rpm>
rpm -qpl <rpm>
```

事实：

- 两个 RPM 均无 `Conflicts` 和 `Obsoletes`。
- `coregl` 依赖 glibc 最高到 `GLIBC_2.34`，`mesa` 最高到 `GLIBC_2.38`；板上 glibc 2.40 已提供这些 capability。
- 其余直接依赖均由板上现有 bash、libdlog、libdrm、libexpat、libgcc、libstdc++、libtbm、libtpl-egl、ttrace、libsystemd、Wayland、zlib 等满足。
- 两个包没有声明替换或升级 glibc、GStreamer 或其组件。
- `coregl` scriptlet 只维护 GLESv1 符号链接；`mesa` post/postun 调用 `/sbin/ldconfig`。

板上预检：

```sh
rpm -Uvh --test /root/coregl-0.4.0-0.armv7l.rpm \
  /root/mesa-24.3.4-0.armv7l.rpm
```

结果：`TEST_EXIT=0`，随后 `rpm -q glibc` 仍为 `glibc-2.40-2.8.armv7l`。预检打印：

```text
warning: Plugin msm: hook tsm_post failed
```

该警告未变成依赖/文件冲突，预检退出码仍为 0。完整原文：[`board_test_transaction.txt`](../board_results/rpi4_graphics_install_20260812/rpms/board_test_transaction.txt)。

## 3. 安装与库验证

### 3.1 安装输出

执行：

```sh
rpm -Uvh /root/coregl-0.4.0-0.armv7l.rpm \
  /root/mesa-24.3.4-0.armv7l.rpm
```

关键原文：

```text
Updating / installing...
   1:mesa-24.3.4-0
   2:coregl-0.4.0-0
INSTALL_EXIT=0
```

安装期间 `mesa` 的 `ldconfig` scriptlet 还打印：

```text
/sbin/ldconfig: Cannot lstat /lib/libgdbm.so.3.0.0: Permission denied
/sbin/ldconfig: Cannot lstat /lib/libLLVM.so.22.1: Permission denied
```

这两个文件在安装前已经存在，owner 分别为 `gdbm-1.8.3-1.9.armv7l` 和 `libllvm-22.1.8-2.1.armv7l`，Smack label 为 `User::Shell`。事务未因此失败。带 RPM 进度控制字符的完整输出见 [`install_output.txt`](../board_results/rpi4_graphics_install_20260812/install_output.txt)。

### 3.2 文件与 loader

安装后 `rpm -V coregl mesa` 无输出。文件 owner 与落点：

| 文件 | owner |
|---|---|
| `/usr/lib/libEGL.so.1`, `/usr/lib/libGLESv2.so.2` | `coregl-0.4.0-0.armv7l` |
| `/hal/lib/driver/libEGL.so.1`, `/hal/lib/driver/libGLESv2.so.2` | `mesa-24.3.4-0.armv7l` |

合同命令 `ldconfig -p | grep -E 'libEGL|libGLESv2'` 没有输出；cache 本身可读并报告 1241 项。实际动态 loader 验证为：

```text
## ldd enlightenment missing
NONE
## ldd AppUIB missing
NONE
## enlightenment resolved paths
libEGL.so.1 => /lib/libEGL.so.1
libGLESv2.so.2 => /lib/libGLESv2.so.2
```

`/lib -> usr/lib`，因此以上路径对应 `coregl` 文件。完整证据：[`library_verification.txt`](../board_results/rpi4_graphics_install_20260812/post/library_verification.txt)、[`final_health.txt`](../board_results/rpi4_graphics_install_20260812/post/final_health.txt)。

## 4. Compositor 与应用启动

没有执行 service restart。安装完成后，原有 `Restart=always` 循环自行进行下一次尝试：

```text
Aug 12 23:20:49 ... status=127
Aug 12 23:21:00 ... Starting Display manager...
Aug 12 23:21:00 ... Started Display manager.
```

安装后状态：

| 项目 | 实测 |
|---|---|
| Enlightenment | PID 2600，`ActiveState=active`, `SubState=running`, `Result=success` |
| restart 计数 | 停在 `NRestarts=3050`，后续快照未继续增长 |
| Wayland | `/run/wayland-0` socket 与 `/run/wayland-0.lock` 已建立 |
| AppUIB | 显式 `app_launcher -s AppQ` 退出 0，返回已运行 PID 2743；进程状态 sleeping，21 threads |
| AppUIA | 显式 `app_launcher -s AppX` 退出 0，返回已运行 PID 2542；进程状态 sleeping，14 threads |
| failed units | 安装后仍为 0 |

dlog 记录 `COREGL` 初始化完成、`Driver GL version 3.2`，AppUIB 经 VC4 TBM backend 从 display server 获得 authenticated DRM fd，并创建 1920x1080 surface queue。此前两个 HDMI connector 均 disconnected，但本轮 compositor 没有因无物理输出拒绝启动，因此没有尝试 headless 配置或环境变量。

原始证据：[`compositor_after_install.txt`](../board_results/rpi4_graphics_install_20260812/post/compositor_after_install.txt)、[`app_launch_verification.txt`](../board_results/rpi4_graphics_install_20260812/post/app_launch_verification.txt)。

## 5. S4 回归确认

### 5.1 版本与协变量

| 项目 | 历史单路测量 | 本轮 |
|---|---|---|
| BUILD_ID | `<TEST_IMAGE_B>` | 相同 |
| glibc | `2.40-2.8.armv7l` | 相同 |
| GStreamer | `1.24.11-38.armv7l` | 相同 |
| MemTotal | 8,117,404 kB | 3,976,480 kB |
| governor | `performance` | `schedutil`（保持安装前原值，未修改） |

安装前后 libc SHA-256 均为：

```text
d5e36dd6339e95adedcbb01b655bc3df46d233fbba5d98f24105192eb8935015
```

glibc RPM 与二进制均未变化。

临时 LLDB 22.1.8 的 sleep 门通过：`getpid()` 返回正确 PID，`malloc_trim(0)=1`，detach 后 sleep 仍存活。证据：[`lldb_smoke.txt`](../board_results/rpi4_graphics_install_20260812/regression/lldb_smoke.txt)。

### 5.2 单路 320x240 释放相位

复用上一轮同 SHA-256 的 `gst_loop_decode`、`reclaim_probe`、320x240 MPEG-4 素材和 `single_rep.sh`，运行退出 `0`，无 program stderr、LMK/OOM/fatal dmesg 命中。

| 点 | glibc-heap PD | other-anon PD | total PD |
|---|---:|---:|---:|
| T0 | 1,130,496 B | 61,440 B | 1,712,128 B |
| T1a | 2,297,856 B | 1,773,568 B | 4,591,616 B |
| T1b | 2,306,048 B | 1,671,168 B | 4,497,408 B |
| T2 NULL 后 | 2,916,352 B | 1,044,480 B | 4,481,024 B |
| T4 trim 后 | 1,495,040 B | 557,056 B | 2,588,672 B |
| T5 再 PLAYING | 2,019,328 B | 2,113,536 B | 4,669,440 B |

派生值：

```text
A_ceiling = 2,916,352 - 1,495,040
          = 1,421,312 B
          = 1.355469 MiB
A / T2 glibc-heap = 48.7360%
trim_return = 1
T4 -> T5 faults = 523 minor / 0 major
LLDB injection envelope = 1.08 s
```

`1.355469 MiB / 48.7360%` 落在合同给出的历史复现窗口 `1.35-1.37 MiB / 约 49%` 内。完整数据：[`regression/`](../board_results/rpi4_graphics_install_20260812/regression/)，派生原文见 [`derived.txt`](../board_results/rpi4_graphics_install_20260812/regression/derived.txt)。

## 6. 异常与限制

- `rpm --test` 出现一次 `Plugin msm: hook tsm_post failed`，但退出 0；实际安装事务没有再次打印该警告。
- 实际安装的 `ldconfig` 对两个安装前已存在且标记为 `User::Shell` 的库报 `Permission denied`。EGL/GLES 不在 `ldconfig -p` 输出中，但两份 `ldd`、Enlightenment、COREGL 和应用实跑均已解析并使用这些库。
- 下载地址是移动的 `reference` URL；本报告保存了实际 RPM 和 SHA-256，后续不能只凭同一 URL 假定内容不变。
- 当前板 RAM/governor 与历史回归环境不同，已在第 5 节并列记录；本轮没有为追求历史数字修改 governor。
- 首次前台 sdb 运行在 T5 前脱离，但板端 runner 保持运行并最终生成 `DONE: EXIT=0`；所有相位文件时间线连续，未补跑或拼接数据。

## 7. 现场与回滚证据

- 板上保留安装状态：`coregl-0.4.0-0.armv7l`、`mesa-24.3.4-0.armv7l`。
- 本轮推入 `/root` 的 RPM、LLDB、探针、视频副本、结果目录和临时软链接均已删除并逐项验证 absent。
- 未删除安装前已存在的 `/root/cabi.mp4`、`/lib/libLLVM.so.22.1` 或其他既有文件。
- 安装前/后 RPM 清单、两个原始 RPM、SHA-256 和全部测量数据均保留在 host；文件清单见 [`raw_manifest.tsv`](../board_results/rpi4_graphics_install_20260812/raw_manifest.tsv)。
- 清理后 Enlightenment 仍 active，AppUIB/AppUIA PID 仍存活，glibc 仍为 `2.40-2.8.armv7l`。证据：[`cleanup.txt`](../board_results/rpi4_graphics_install_20260812/post/cleanup.txt)。
