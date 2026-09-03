> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# A_ceiling LLDB 实测报告

日期：2026-08-06（板上时间均为 UTC）  
范围：仅 RPI4 `.25`；未连接或操作 TV `.26`。本任务未安装包、未修改持久配置。

## 1. 身份与 S1 能力验证

每个板侧脚本在首次采集前均执行身份断言。实测为：

```text
kernel=6.12.80-arm-rpi4-v7l
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
BUILD_ID=<TEST_IMAGE_A>
IDENTITY_OK_RPI4_UNIFIED_DEV
uid=0(root)
```

板上初始 LLDB 状态原文：

```text
/usr/bin/lldb
MISSING:lldb-server
lldb: error while loading shared libraries: libclang-cpp.so.22.1: cannot open shared object file: No such file or directory
```

`/usr/bin/lldb` 是指向 `/opt/usr/<USER_HOME>/share/tmp/sdk_tools/lldb/bin/lldb` 的符号链接；同目录实际存在 `lldb-server`，但它也缺少相同运行库。板上 RPM 为 `lldb-22.1.8-19.1.armv7l`，只安装了该一个 LLVM/Clang 相关包。

为完成只临时运行的能力验证，从 Tizen 官方 Base Toolchain 仓库下载了精确匹配的 `clang-22.1.8-19.1.armv7l.rpm` 与 `libllvm-22.1.8-19.1.armv7l.rpm`，在 host 解包，仅将以下两个 ARM EABI5 `.so` 推到临时 `/root/lldb-runtime`，通过一次性 `LD_LIBRARY_PATH` 使用，未执行 RPM 安装：

```text
libLLVM.so.22.1       sha256 bdf79f73567deaa4cb5788a4b2ea8dce59460103782a9103c9a5111977d90de1
libclang-cpp.so.22.1 sha256 0dbb64ecc4fb5d3e8d040ab25beae622e7c8e55f559a00e8666498dc56df2938
lldb version 22.1.8
```

LLDB 帮助确认 `expression -t/--timeout` 的单位为微秒；正式调用统一使用 `-t 5000000`。一次性 `sleep 300` 验证原文摘录：

```text
SLEEP_PID=11128
thread #1 ... __GI___clock_nanosleep_time64 ...
(lldb) expr -t 5000000 -- (int)getpid()
(int) $0 = 11128
(lldb) expr -t 5000000 -- (int)malloc_trim(0)
(int) $1 = 1
(lldb) detach
Process 11128 detached
LLDB_RC=0
SLEEP_CLEANED
```

S1 判定：attach、表达式执行、符号解析和 detach 全部成功。

## 2. 新鲜态与注入记录

每轮均先 `app_launcher -t` 再 `app_launcher -s`，终止和启动退出码均为 0，并确认 PID 改变；随后运行原 `test_board_prepare_load.sh` 三轮应用切换并静置 60 s。六轮 PID 证据如下：

| 目标 | rep | 旧 PID | 新 PID | load rc | 轮次状态 |
|---|---:|---:|---:|---:|---|
| AppUIA | 1 | 1004 | 1003 | 0 | COMPLETE |
| AppUIA | 2 | 1003 | 1028 | 0 | COMPLETE |
| AppUIA | 3 | 1028 | 12219 | 0 | COMPLETE |
| AppUIB | 1 | 915 | 15854 | 0 | COMPLETE |
| AppUIB | 2 | 15854 | 17051 | 0 | COMPLETE |
| AppUIB | 3 | 17051 | 18248 | 0 | COMPLETE |

每次 attach 后均先执行 `thread list` 和 `bt all`。六轮都选择线程 #1；AppUIA 的选中栈为 `poll → ecore_main_loop → AppCore → Dali/C# binder`，AppUIB 为 `poll → ecore_main_loop → AppCore → ui_app_main → runner`。六份选中栈除随后输入的 `malloc_trim` 命令外，没有 `malloc/free/calloc/realloc/arena` 命中。

| 目标 | rep | 所选线程与栈顶 | trim_return | expr 时间证据 | detach | LLDB 全部原文 |
|---|---:|---|---:|---|---|---|
| AppUIA | 1 | #1, `poll`, Ecore 主循环 | 1 | 单独计时 N/A；完整人工审栈会话 39606.063 ms | 成功 | `test_board/runs/systemui/rep1/lldb_injection.txt` |
| AppUIA | 2 | #1, `poll`, Ecore 主循环 | 1 | 单独计时 N/A；无脚本解释器；expr 所在 host 批次上界 250.707 ms | 成功 | `test_board/runs/systemui/rep2/lldb_injection.txt` |
| AppUIA | 3 | #1, `poll`, Ecore 主循环 | 1 | 时间戳包络 319.429 ms | 成功 | `test_board/runs/systemui/rep3/lldb_injection.txt` |
| AppUIB | 1 | #1, `poll`, Ecore 主循环 | 1 | 时间戳包络 323.866 ms | 成功 | `test_board/runs/AppUIB/rep1/lldb_injection.txt` |
| AppUIB | 2 | #1, `poll`, Ecore 主循环 | 1 | 时间戳包络 317.407 ms | 成功 | `test_board/runs/AppUIB/rep2/lldb_injection.txt` |
| AppUIB | 3 | #1, `poll`, Ecore 主循环 | 1 | 时间戳包络 331.190 ms | 成功 | `test_board/runs/AppUIB/rep3/lldb_injection.txt` |

时间戳包络是在 LLDB 内于 expr 前后执行 `platform shell date +%s%N` 的差值，包含 LLDB 命令分派和第二次 shell 启动时间，不是纯 `malloc_trim` CPU 时间。板上 LLDB 编译时没有脚本语言支持，故无法使用内嵌 Python 单调时钟。

## 3. T0 / T1' / T2 全量采样

下表中的 PD、Rss、Pss、zram 均为 kB。`zram orig/mem` 分别是 `mm_stat` 的 `orig_data_size` 和 `mem_used_total`。完整的分段数、各类 Rss/PD、`free` 六字段、`smaps_rollup`、zram 九字段及原始 `/proc/<pid>/stat` 见 `all_points.tsv` 和各轮目录。

| target | rep | point | glibc PD kB | other PD kB | file PD kB | total PD kB | Rss/Pss kB | minflt/majflt | zram orig/mem kB | MemAvailable kB |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AppUIA | 1 | T0 | 5900 | 12252 | 2396 | 20548 | 49592/31986 | 19507/228 | 20776/12860 | 6725908 |
| AppUIA | 1 | T1' | 5556 | 12256 | 2420 | 20232 | 49244/31669 | 19510/228 | 20776/12860 | 6717204 |
| AppUIA | 1 | T2 | 5556 | 12260 | 2420 | 20236 | 48104/30949 | 19645/228 | 20776/12860 | 6716672 |
| AppUIA | 2 | T0 | 4976 | 5988 | 2396 | 13360 | 42776/24910 | 14647/34 | 20776/12860 | 6719780 |
| AppUIA | 2 | T1' | 4784 | 5992 | 2420 | 13196 | 42584/24747 | 14650/34 | 20776/12860 | 6723088 |
| AppUIA | 2 | T2 | 4784 | 5996 | 2420 | 13200 | 41444/24027 | 14785/34 | 20776/12860 | 6723132 |
| AppUIA | 3 | T0 | 4996 | 5980 | 2396 | 13372 | 42776/24897 | 14521/0 | 20776/12860 | 6721384 |
| AppUIA | 3 | T1' | 4772 | 5984 | 2420 | 13176 | 42548/24701 | 14523/0 | 20776/12860 | 6715392 |
| AppUIA | 3 | T2 | 4772 | 5988 | 2420 | 13180 | 41408/23981 | 14658/0 | 20776/12860 | 6714764 |
| AppUIB | 1 | T0 | 9804 | 18144 | 3252 | 31200 | 63852/49396 | 67078/54 | 288/404 | 6781072 |
| AppUIB | 1 | T1' | 9380 | 18240 | 3276 | 30896 | 63532/49087 | 67416/54 | 288/404 | 6722452 |
| AppUIB | 1 | T2 | 9380 | 18240 | 3276 | 30896 | 63532/49087 | 67416/54 | 288/404 | 6722520 |
| AppUIB | 2 | T0 | 9312 | 18820 | 3252 | 31384 | 64036/49579 | 67227/0 | 288/404 | 6770732 |
| AppUIB | 2 | T1' | 8844 | 18672 | 3276 | 30792 | 63428/48983 | 67420/0 | 288/404 | 6761556 |
| AppUIB | 2 | T2 | 8844 | 18764 | 3276 | 30884 | 63520/49075 | 67485/0 | 288/404 | 6721536 |
| AppUIB | 3 | T0 | 8836 | 19352 | 3252 | 31440 | 64092/49635 | 67223/0 | 288/404 | 6698696 |
| AppUIB | 3 | T1' | 8388 | 19336 | 3276 | 31000 | 63636/49191 | 67488/0 | 288/404 | 6740560 |
| AppUIB | 3 | T2 | 8388 | 19340 | 3276 | 31004 | 63640/49195 | 67489/0 | 288/404 | 6741296 |

六轮 T0→T1' 的 zram 九字段均逐字不变，`orig_data_size` 与 `mem_used_total` 差量均为 0。未观察到 trim 对 zram 的增长归因。

## 4. 核心结果与 PAGEOUT 对照

以下为每目标三轮中位数。`A_ceiling` 按合同取 glibc-heap 类 Private_Dirty 的 T0→T1' 下降；总 PD 下降独立列出。`B_glibc` 使用前一报告中同目标 PAGEOUT rep1 新鲜态原值，而非受前轮 PAGEOUT 影响的后续中位数。

| 目标 | A_ceiling glibc PD | 总 PD 下降 | trim_return | refault min/maj | T2 命令耗时 | B_glibc 新鲜态上界 | A/B | 对照事实 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| AppUIA | 0.219 MiB | 0.191 MiB | 1 / 1 / 1 | 135 / 0 | 33.447 ms | 2.781 MiB | 7.87% | A < B |
| AppUIB | 0.438 MiB | 0.430 MiB | 1 / 1 / 1 | 1 / 0 | 30.131 ms | 7.863 MiB | 5.56% | A < B |

逐轮派生量：

| 目标 | rep | glibc PD 下降 | 总 PD 下降 | glibc 回收占 T0 glibc PD | 总回收占 T0 总 PD | refault min/maj | T2 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| AppUIA | 1 | 0.336 MiB | 0.309 MiB | 5.83% | 1.54% | 135 / 0 | 34.228 |
| AppUIA | 2 | 0.188 MiB | 0.160 MiB | 3.86% | 1.23% | 135 / 0 | 31.459 |
| AppUIA | 3 | 0.219 MiB | 0.191 MiB | 4.48% | 1.47% | 135 / 0 | 33.447 |
| AppUIB | 1 | 0.414 MiB | 0.297 MiB | 4.32% | 0.97% | 0 / 0 | 30.005 |
| AppUIB | 2 | 0.457 MiB | 0.578 MiB | 5.03% | 1.89% | 65 / 0 | 30.366 |
| AppUIB | 3 | 0.438 MiB | 0.430 MiB | 5.07% | 1.40% | 1 / 0 | 30.131 |

两目标均满足 `A_ceiling ≤ B_glibc`；本轮没有出现需要解释的反向归因。

### 每目标一句话事实

- AppUIA：真实进程上 `malloc_trim(0)` 回收 glibc-heap Private_Dirty 中位数 0.219 MiB，占其 T0 glibc 堆私有脏页 4.48%，占其总私有脏页 1.47%。
- AppUIB：真实进程上 `malloc_trim(0)` 回收 glibc-heap Private_Dirty 中位数 0.438 MiB，占其 T0 glibc 堆私有脏页 5.03%，占其总私有脏页 1.40%。

## 5. 失败与限制

- 没有目标挂死、表达式超时、detach 失败或重试；六轮目标在操作后均存活，应用管理器状态为 running。
- 初始 LLDB RPM 缺少运行依赖；使用精确版本官方 RPM 的两个临时共享库后才能运行。板上 RPM 数据库未改变。
- S1 首次 sleep 命令尝试使用板上不存在的外层 `timeout`，因此在 LLDB attach 前以 rc 127 退出，sleep 已清理；确认 LLDB 自身 `expression -t` 后重跑并通过。
- AppUIA rep1 没有单独 expr 计时；rep2 尝试内嵌 Python 时得到 `Embedded script interpreter unavailable`。rep3 及 AppUIB 使用前后 shell 时间戳，其差值包含命令分派开销。
- T0→T1' 还包含 LLDB 表达式执行本身的进程扰动。各轮可见少量段数和非 glibc PD 变化；报告按合同使用 glibc-heap 类的净下降，不把总 PD 下降替代为 glibc 回收量。
- `refault_cost` 的 fault 差量取 T2−T1'。T0→T1' 的 fault 增长主要包含 attach/表达式成本，不计入该 refault 数。
- T2 耗时是 `app_launcher -s` 的返回耗时，不是输入到可见首帧的 UI 延迟。
- `glibc-heap` 仍是 `[heap]` 加 1 MiB 对齐匿名段的历史代理口径，不是 allocator ownership 的逐页证明。
- 六轮 fatal 基线与结束检查均为 0；未出现 LMK、OOM、SIGSEGV 或 signal 11。
- 临时 `/root` tmpfs 已卸载，探针、脚本和运行库残留为 0。卸载后的底层 `/root` 目录模式为 `dr-xr-x---`，但 root 写探针成功；测试文件已立即删除，未执行 remount。

## 6. 原始文件清单

- S1 依赖与 sleep 验证：`board_results/a_ceiling_lldb_20260806/s1/`
- 每轮完整采样：`board_results/a_ceiling_lldb_20260806/test_board/runs/{systemui,AppUIB}/rep{1,2,3}/`
- 每轮 LLDB 原文：上述每轮目录内的 `lldb_injection.txt`
- 逐轮派生量：`board_results/a_ceiling_lldb_20260806/derived_metrics.tsv`
- 三点全字段汇总：`board_results/a_ceiling_lldb_20260806/all_points.tsv`
- 恢复现场证据：`board_results/a_ceiling_lldb_20260806/test_board/pre_cleanup.txt`、`cleanup.txt`
- 临时执行脚本原文：`board_results/a_ceiling_lldb_20260806/scripts/`
- 全部文件逐项清单：`board_results/a_ceiling_lldb_20260806/raw_files_manifest.txt`
