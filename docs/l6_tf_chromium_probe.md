> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# TensorFlow 与 Chromium 的 L6 作用点测量

日期：2026-08-07  
目标板：RPI4 `.25` (`<TEST_BOARD_IP>`)  
产品板 `.26`：未连接、未操作  
采集根目录：`board_results/l6_tf_chromium_20260807/`

## 1. 阶段零：环境复核

### 1.1 身份门

强制身份检查通过：

```text
IDENTITY_OK_RPI4
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Tue Jul 28 02:41:25 UTC 2026 armv7l GNU/Linux
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_B>
TZ_BUILD_PROJECT=Tizen-Unified-Toolchain
```

内核含 `rpi4`，`os-release` 不含 `<PRODUCT_IMAGE>`。本轮未用镜像变体名作为排除条件。

### 1.2 glibc 身份与历史对照

```text
glibc-2.40-2.8.armv7l
Source RPM  : glibc-2.40-2.8.src.rpm
GNU C Library (GNU libc) stable release version 2.40.
Compiled by GNU CC version 14.2.0.
```

本轮 release `2.40-2.8` 与历史 AppUIA/AppUIB 测量使用的 `2.40-3.12` 不同；历史报告的镜像为 `<TEST_IMAGE_A>`，本轮为 `<TEST_IMAGE_B>`。两组数据分属不同镜像，不能直接并列为同镜像 A/B。

### 1.3 资产

TensorFlow Lite 入口为 `/usr/bin/tflite_benchmark_model`，包版本 `tensorflow2-lite-util-2.18.0-1.armv7l`。模型目录存在且只读使用：

| 文件 | 字节 |
|---|---:|
| `Llama-3.2-1B-Instruct-Q4_0.gguf` | 773025824 |
| `Llama-3.2-1B-Instruct-Q4_K_M.gguf` | 807694368 |
| `inception_resnet_v2.tflite` | 120996332 |
| `inception_v4.tflite` | 170674020 |
| `mobilenet_v1_1.0_224.tflite` | 16901128 |
| `mobilenet_v1_1.0_224_quant.tflite` | 4276352 |
| `nasnet_mobile.tflite` | 21361452 |
| `squeezenet.tflite` | 5006664 |

平台 Chromium appid 为 `AppK`，包为 `chromium-efl-1.1.144-1.armv7l`，运行日志回显 Chromium `144.0.7559.132`。旧 appid `AppL` 不存在。平台包同时提供 `efl_webview_app`、`mini_browser` 和 `AppUIC`。

### 1.4 协变量

| 项 | 实测 |
|---|---|
| MemTotal | 8,117,408 kB |
| 初始 MemAvailable | 6,980,516 kB |
| `vm.overcommit_memory` | 0 |
| swap | `/dev/zram0`, 3,246,960 kB，初始 Used=0 |
| zram `mm_stat` | `4096 74 4096 0 4096 0 0 0 0` |
| CPU | 4 核，online `0-3` |
| governor | 4 核均为 `schedutil` |
| THP | `/sys/kernel/mm/transparent_hugepage` 不存在 |

### 1.5 LLDB

镜像未自带可执行 `lldb`。使用官方 `lldb-22.1.8-19.1.armv7l.rpm` 的文件及精确版本 `libLLVM.so.22.1`、`libclang-cpp.so.22.1`，全部放在 256 MiB 临时 `/root` tmpfs，未安装 RPM、未改 RPM 数据库。

```text
lldb version 22.1.8
```

一次性 `sleep 300` 最小门通过：

```text
frame #0: libc.so.6`__GI___clock_nanosleep_time64
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $0 = 1
Process 6375 detached
LLDB_RC=0
SLEEP_CLEANED
```

`malloc_info` 的 persistent variable、`fflush`、`fclose` 另行在一次性 sleep 上验证，生成 582 字节完整 XML 后删除，`LLDB_RC=0`。

## 2. 阶段一预筛

### 2.1 TensorFlow Lite

`ldd /usr/bin/tflite_benchmark_model` 仅列出 `libm`、`libstdc++`、`libgcc_s`、`libc` 和 loader；运行中 maps 也未出现 tcmalloc、jemalloc、mimalloc 或 scudo，记录为 `ALLOCATOR_SO_NONE`。

第一轮用 quant MobileNet、1 线程、10 次 warmup、持续多轮推理：

```text
--graph=/opt/usr/home/model/mobilenet_v1_1.0_224_quant.tflite
--num_threads=1 --num_runs=100000 --min_secs=60 --max_secs=120
--run_delay=0.001 --warmup_runs=10
```

第二轮按规格改用 float MobileNet、4 线程和更多 warmup，制造中小分配累积：

```text
--graph=/opt/usr/home/model/mobilenet_v1_1.0_224.tflite
--num_threads=4 --num_runs=100000 --min_secs=45 --max_secs=90
--run_delay=0.001 --warmup_runs=20
```

| 负载 | 点 | glibc-heap PD | other-anon PD | total PD | glibc 增长 |
|---|---|---:|---:|---:|---:|
| quant, 1 thread | 启动暂停态 | 0 MiB | 0.027 MiB | 0.098 MiB | - |
| quant, 1 thread | 推理 2/10/25 s | 0.180 MiB | 1.879 MiB | 2.168 MiB | 0.180 MiB |
| float, 4 threads | 启动暂停态 | 0 MiB | 0.027 MiB | 0.098 MiB | - |
| float, 4 threads | 推理 3/15 s | 0.633 MiB | 22.293 MiB | 23.035 MiB | 0.633 MiB |

**预筛：不通过。** 两轮 glibc-heap 增长均小于冻结门 1 MiB；第二轮主要增长位于 `other-anon`。因此 TensorFlow 未进入阶段二，没有对该进程注入 LLDB、`malloc_info` 或 `malloc_trim`。

### 2.2 Chromium

app control 路径实测：

```text
app_launcher -s AppK __APP_SVC_URI__ https://example.com/
... launch failed
aul_test launch ...
... test failed
aul_test open_content https://example.com/
... test successful ret = 0
```

`open_content` 返回 0，但进程内存与 dlog 未显示目标 URL 被加载。平台 `mini_browser` 即使给位置 URL仍固定请求 `http://www.google.com/`。同包 `AppUIC` 支持 `[URL]` 参数，以下直接入口成功：

```text
/usr/apps/AppK/bin/AppUIC file:///tmp/l6_chromium_heavy.html
[INFO:...ewk_view.cc: ewk_view_url_set(151)] ... url: file:///tmp/l6_chromium_heavy.html
```

进程架构为主进程 `AppUIC`、zygote `efl_webprocess`、renderer `efl_webprocess`。主进程与 renderer 前台存活 65 s。`/dev/uinput` 存在且为 `crw------- root root`，本轮按边界只探查、未实现或使用输入注入。

有效预筛的主进程画像：

| 点 | 主进程 glibc-heap PD | 主进程 other-anon PD | renderer glibc-heap PD | renderer other-anon PD |
|---|---:|---:|---:|---:|
| 启动后 1 s | 3.133 MiB | 3.602 MiB | renderer 尚未出现 | renderer 尚未出现 |
| URL 后 8 s | 9.926 MiB | 5.539 MiB | 1.043 MiB | 1.242 MiB |
| URL 后 15 s | 9.969 MiB | 5.551 MiB | 1.043 MiB | 1.242 MiB |
| 名义释放后 35 s | 9.969 MiB | 5.551 MiB | 1.043 MiB | 1.242 MiB |
| 65 s | 9.969 MiB | 5.551 MiB | 1.043 MiB | 1.242 MiB |

**数值预筛：通过。** 主进程 glibc-heap 从 1 s 到 15 s 增长 6.836 MiB，超过 1 MiB 门，因此进入阶段二。

**相位验证修正：不完整。** EWK 明确接受本地 URL并创建 renderer，但日志只出现 `LoadProgressChanged ... 0.1`，未出现 load-finished 或页面内 `L6_HEAVY` / `L6_RELEASED` hash 标记；T1 到名义 T2 的内存也保持不变。另有 4K TBM buffer `TBM_ERROR_OUT_OF_MEMORY`，不是内核 OOM/LMK。故下节数据是按固定时钟执行的名义 T0-T5，不能证明页面“重负载后集中释放”相位已实际发生。

## 3. 阶段二正式测量

仅 Chromium 主进程进入本阶段。每轮均新起 `AppUIC`；T2 后独立执行 `thread list`、`bt all` 和所选线程栈检查。三轮所选 thread 1 均停在 `poll -> libecore -> ecore_main_loop_begin`，allocator frame 命中数为 0，随后才调用 `malloc_info` 与 `malloc_trim`。

### 3.1 核心数据

PD 单位为 MiB。`A_ceiling` 按合同取名义 T2 到 T4 的 glibc-heap PD 下降；由于释放相位未独立验证，表中同时标记为“名义值”。

| rep | T0 glibc/other | T1a glibc/other | T1b glibc/other | T2 glibc/other | T4 glibc/other | T5 glibc/other | 名义 A_ceiling | A/T2 glibc | trim_return | T4->T5 min/maj | LLDB 注入包络 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.434 / 0.676 | 9.941 / 5.961 | 9.941 / 5.961 | 9.941 / 5.961 | 9.922 / 5.449 | 9.922 / 5.449 | 0.019531 | 0.196% | 1 | 0 / 0 | 2590 ms |
| 2 | 1.469 / 1.148 | 9.902 / 5.875 | 9.926 / 5.879 | 9.926 / 5.879 | 9.914 / 5.348 | 9.914 / 5.348 | 0.011719 | 0.118% | 1 | 0 / 0 | 2600 ms |
| 3 | 1.906 / 1.523 | 10.113 / 5.270 | 10.152 / 5.273 | 10.152 / 5.273 | 10.109 / 5.246 | 10.109 / 5.246 | 0.042969 | 0.423% | 1 | 0 / 0 | 2550 ms |
| 中位数 | 1.469 / 1.148 | 9.941 / 5.875 | 9.941 / 5.879 | 9.941 / 5.879 | 9.922 / 5.348 | 9.922 / 5.348 | **0.019531** | **0.196%** | 1 | 0 / 0 | 2590 ms |

总 Private_Dirty 的 T2->T4 下降分别为 0.507812、0.519531、0.046875 MiB，中位数 0.507812 MiB。该总量包含 `other-anon` 和 LLDB/`malloc_info` 引起的分类变化，不替代 glibc-heap 口径的 `A_ceiling`。

三轮 zram `mm_stat` 未增长，swap Used 保持 0。T4 到 T5 的 minflt/majflt 均为 0/0；由于页面轻活动标记也未被验证，此 fault 差值只能记录为名义 T5 观测，不能作为已验证交互 refault。

### 3.2 注入原文摘录

三轮返回一致：

```text
(lldb) thread select 1
frame #0: libc.so.6`__GI___poll
...
frame #9: libecore.so.1`ecore_main_loop_begin
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $3 = 1
(lldb) detach
```

“LLDB 注入包络”由 `/proc/uptime` 前后差计算，包含 attach、栈回溯、`malloc_info`、flush/fclose、`malloc_trim` 和 detach，不是 `malloc_trim` 函数自身耗时。

## 4. `malloc_info` 分布

XML 在名义 T2、trim 前采集。

| rep | arena 数 | tcache | fastbin bytes | unsorted bytes | rest bytes | system current bytes | fast/system | unsorted/system | rest/system |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 不可见 | 944 | 86666 | 1041107 | 14307328 | 0.00660% | 0.60575% | 7.27674% |
| 2 | 8 | 不可见 | 560 | 8954 | 1169391 | 14446592 | 0.00388% | 0.06198% | 8.09458% |
| 3 | 8 | 不可见 | 408 | 11292 | 759091 | 14032896 | 0.00291% | 0.08047% | 5.40937% |

`malloc_info` XML 不导出 tcache residency，因此本轮不能从 XML给出 tcache 字节数。`fastbin` 取全局末行 `<total type="fast">`；`unsorted` 为各 heap `<unsorted total=...>` 求和；`rest` 取全局 `<total type="rest">`，它包含的不只是 unsorted，二者未混写。

## 5. 与既有目标对照

| 目标 | glibc 回收比例 | 镜像 | 可比性 |
|---|---:|---|---|
| AppUIA | 4.48% | `<TEST_IMAGE_A>`, glibc `2.40-3.12` | 历史完整静置态测量 |
| AppUIB | 5.03% | `<TEST_IMAGE_A>`, glibc `2.40-3.12` | 历史完整静置态测量 |
| Chromium | 0.196% 中位数 | `<TEST_IMAGE_B>`, glibc `2.40-2.8` | 不同镜像，且释放相位未验证；仅列事实，不作直接 A/B |
| TensorFlow | n/a | `<TEST_IMAGE_B>`, glibc `2.40-2.8` | 预筛未过，未 trim |

## 6. 失败与限制

- TensorFlow 两轮均未达到 1 MiB glibc-heap 增长门，阶段二按合同跳过。
- `AppK` 的 app control URL 注入失败或未实际导航；最终使用同一平台包的 `AppUIC` 直接 URL入口。
- `mini_browser` 的位置 URL 参数实测被忽略并固定加载 Google，因此其试跑未用于数据。
- 首次 direct-browser 采样跟踪了 `setsid` wrapper PID；发现实际进程多 fork 一层后重采，错误轮保留但未纳入表格。
- Chromium EWK 接受 URL并创建 renderer，但只到 load progress 0.1；页面内重载、释放和轻活动标记均未获得。因此阶段二名义 T2 不等同于已证明的集中释放点。
- 平台日志出现 4K TBM surface allocation failure；三轮 dmesg 没有新增 LMK、内核 OOM、SIGSEGV 或 fatal signal。`dmesg_alerts.txt` 的三行只是启动早期 `oom_control/oom_adj is deprecated` 文本。
- `glibc-heap` 是 `[heap]` 加历史 1 MiB 对齐匿名段代理口径，不是 allocator ownership 的逐页证明。
- `malloc_info` 本身会分配；它在计数窗口外、trim 前执行，但仍可能扰动 T2->T4。
- LLDB attach 和表达式会制造 faults/映射变化；报告只以 glibc-heap PD 净下降计算名义 `A_ceiling`。
- T5 没有可验证的页面轻活动，因此 0/0 fault 仅为观测值。

## 7. 恢复现场

三轮目标均记录 `CLEANUP_ALIVE=0`。`/tmp` 的 XML和 HTML 残留计数为 0，模型文件的名称与大小复核不变。

首次卸载 `/root` tmpfs 因一个本轮 stdin 测试遗留的 `sh -s` PID 13222 仍以 `/root` 为 cwd 而返回 `target is busy`。该 shell 启动时间为本轮 20:18、PPID=1；未触碰先于本轮存在的 ttyS0 login bash PID 1060。终止本轮遗留 shell 后：

```text
ORPHAN_GONE
UMOUNT_RC=0
ROOT_TMPFS_ABSENT
L6TFPROBE_ABSENT
TARGETS
TMP
```

最终无 `AppUIC`、`mini_browser`、`efl_webprocess` 或 `lldb` 进程，无 `/root/l6tfprobe`，临时 LLDB 运行库随 tmpfs 卸载。

## 8. 原始文件

完整逐文件清单为 `board_results/l6_tf_chromium_20260807/raw_file_manifest.txt`，共 160 项。主要证据目录：

- `stage0_environment.txt`、`stage0_lldb_setup.txt`、`stage0_lldb_minimal_retry.txt`：身份、glibc、协变量和 LLDB 门。
- `tf_tool_identity.txt`、`tf_pre2/`、`tf_pre3/`：TF 入口、分配器和两轮预筛。
- `chromium_identity.txt`、`chromium_pre/`：appid、进程树和 app control 尝试。
- `chromium_ub_pre2/`：有效 Chromium 数值预筛。
- `chromium_stage2/rep1/`、`rep2/`、`rep3/`：T0-T5、完整 LLDB 输出、XML、dmesg 和清理证据。
- `chromium_stage2/derived.tsv`：逐点机械提取值。
- `stage2_final_logs_and_precleanup.txt`：URL、renderer、load progress 与异常日志。
- `cleanup_action*.txt`、`cleanup_verification*.txt`、`cleanup_holder_identity.txt`：卸载失败定位和最终恢复证据。

本报告只记录实测事实与派生量，不包含上线或重开裁决。
