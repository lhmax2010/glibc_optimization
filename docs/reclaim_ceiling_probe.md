> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Reclaim Ceiling Probe 实测报告

日期：2026-08-06（采集时间均为 UTC）  
测量性质：真实进程回收天花板测量；未修改产品配置，未重启系统服务。

## 1. 身份自检与负载

| 板 | 通道 | 强制身份断言 | 实测身份 | 结果 |
|---|---|---|---|---|
| RPI4 `.25` | sdb root | 内核含 `rpi4`，`os-release` 含 `unified-dev` | `6.12.80-arm-rpi4-v7l`; Tizen 11 unified-dev; build `<TEST_IMAGE_A>` | PASS |
| TV `.26` | SSH root，无 PTY | 内核严格等于 `6.12.60`，<PRODUCT_IMAGE>，拒绝 `rpi4`/`unified-dev` | `6.12.60`; Tizen 10/TV; build `<PRODUCT_BUILD_ID>` | PASS |

每个板侧采集脚本在首次采集前执行上述断言。RPI4 每个有效轮次的 `meta.txt` 均以 `IDENTITY_OK=RPI4_UNIFIED_DEV` 开头；TV 原文见 `product_board/pull/identity.out`。

RPI4 的固定负载脚本为 `board_results/reclaim_ceiling_probe_20260806/scripts/test_board_prepare_load.sh`。每轮顺序如下，共重复三轮，然后静置 60 s：

1. 前台启动 Chromium/EFL browser，等待 3 s。
2. 前台启动 EFL account settings，等待 3 s。
3. 返回 AppUIB，等待 3 s。
4. 请求恢复 browser，等待 2 s，再返回 AppUIB，等待 2 s。

参与负载的真实应用包括 `.NET` AppUIA、AppUIB、Chromium/EFL browser 和 EFL settings。板上没有 `input-keyevent`、`keyevent`、`xdotool` 或 `perf`，因此无法自动执行滚动，也无法取得从输入到首帧的 UI 延迟；T4 的“响应耗时”仅为 `app_launcher` 命令返回耗时。

RPI4 的 `/tmp` 为 `noexec`，原 `/root` 为只读。执行期在既有 `/root` 挂载点临时挂载 64 MiB tmpfs；收尾时已卸载，验证 `ROOT_READONLY_RESTORED` 且探针残留为 0。

## 2. 工具与口径

交付物：

- `bench/reclaim_probe/reclaim_probe.c`：`profile <pid>` 和 `pageout <pid> <class>`。
- `bench/reclaim_probe/Makefile`：host 与 armv7l 构建。
- `bench/reclaim_probe/trim_via_gdb.sh`：带 RPI4 身份门的 gdb trim 触发器。

host 与 armv7l 均以 `-std=c99 -O2 -Wall -Wextra -Werror` 编译通过。armv7l 产物为动态链接 ARM EABI5 ELF，解释器 `/lib/ld-linux.so.3`。RPI4 root 预检对一次性 `sleep` 进程执行 `process_madvise(MADV_PAGEOUT)` 成功，返回 errno 0；六个有效轮次的 T2/T3 也全部 errno 0、所有选中区间调用成功。

分类沿用历史 `parse_smaps.pl`：`glibc-heap` 为 `[heap]`，加上起始地址 1 MiB 对齐、长度不超过 1 MiB、`rw-p`、无 pathname 的匿名段；`other-anon` 为其余匿名可写段；其余归 `file-backed`。数值均来自 `/proc/<pid>/smaps` 的 `Private_Dirty` 和 `Rss`。

派生量严格按任务定义计算：`B_glibc=T1-T2` 总 Private_Dirty，`B_other=T2-T3` 总 Private_Dirty。`process_madvise` 的 `successful_bytes` 是内核已接受 advice 的虚拟地址长度，不作为实际迁出量；实际迁出以采样到的 Private_Dirty 下降表示。

## 3. RPI4 核心对比

板上 `gdb` 不存在，故所有轮次 T1 均明确记录 `SKIPPED: gdb unavailable; malloc_trim was not called`。因此 `A_ceiling` 是 **N/A（未测）**，不能把 T0 到 T1 的自然变化记作 trim 收益。

下表为每个目标三轮的中位数。单位为 MiB；占比以同轮 T0 总 Private_Dirty 为分母后取中位数。

| 目标 | 进程/实现 | T0 总 Private_Dirty | A_ceiling | B_glibc | B_glibc 占比 | B_other | B_other 占比 | T1→T3 zram 增量（orig/mem/swap-used） | T4 refault（min/maj） | T3→T4 zram 换入代理 | T4 命令耗时 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AppUIA | PID 1004, `dotnet-hydra-loader` | 2.930 | N/A | 0.375 | 12.80% | 0.074 | 2.56% | 1.129 / 0.211 / 1.000 | 99 / 230 | 1.000 MiB | 34.186 ms |
| AppUIB | PID 915, native EFL runner | 6.379 | N/A | 0.168 | 2.63% | 0.855 | 13.41% | 1.641 / 0.523 / 1.500 | 123 / 129 | 0.500 MiB | 32.436 ms |

`zram orig` 是 `/sys/block/zram0/mm_stat` 的 `orig_data_size`，`zram mem` 是 `mem_used_total`，`swap-used` 来自 `/proc/swaps`。T3→T4 的换入代理取 `orig_data_size` 的下降；这些是系统级并发计数器，不是目标进程专属计数器。

### 逐轮原始派生值

| 目标 | rep | T0 PD MiB | B_glibc MiB | B_other MiB | zram orig 增量 MiB | refault min/maj | zram 换入代理 MiB | T4 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AppUIA | 1 | 10.125 | 2.781 | 4.844 | 6.789 | 248 / 260 | 1.000 | 33.200 |
| AppUIA | 2 | 2.930 | 0.375 | 0.059 | 1.129 | 99 / 230 | 1.000 | 37.160 |
| AppUIA | 3 | 2.902 | 0.332 | 0.074 | 1.043 | 86 / 222 | 0.750 | 34.186 |
| AppUIB | 1 | 29.688 | 7.863 | 16.441 | 21.219 | 123 / 129 | 0.750 | 31.551 |
| AppUIB | 2 | 6.148 | -0.063 | 0.645 | 1.145 | 106 / 103 | 0.250 | 32.436 |
| AppUIB | 3 | 6.379 | 0.168 | 0.855 | 1.641 | 130 / 133 | 0.500 | 33.505 |

AppUIB rep 2 的 `B_glibc=-0.063 MiB` 是 T1→T2 十秒窗口内总 Private_Dirty 的实测净变化，原值保留，未截成 0。

### 每目标一句话事实

- AppUIA：glibc trim 路线因 gdb 缺失未测；逐轮 `B_glibc+B_other` 的中位数为 0.434 MiB Private_Dirty，其中 `B_other` 中位数为 0.074 MiB；T0 总 Private_Dirty 中位数为 2.930 MiB。
- AppUIB：glibc trim 路线因 gdb 缺失未测；页级路线中位数额外迁出 1.023 MiB Private_Dirty，其中 `other-anon` 0.855 MiB；T0 总 Private_Dirty 中位数为 6.379 MiB。

PAGEOUT 把页迁往 zram，并不等于释放这些页占用的系统总内存。上表同时列出 zram 原始数据量、压缩后物理占用和 swap-used 的变化，以区分 RSS/Private_Dirty 下降与系统净内存变化。

## 4. TV `.26` 只读画像

Top-5 来自采集时 `smaps_rollup` 的 Rss 排序。`glibc-heap` Private_Dirty 是 malloc_trim 理论可触及区间的宽松上界，不等同于其中已释放且可 trim 的字节数。

| 目标 | PID | 总 PD MiB | glibc-heap PD MiB | 占总 PD | other-anon PD MiB | 占总 PD |
|---|---:|---:|---:|---:|---:|---:|
| `AppProcB` | 2556 | 33.090 | 15.066 | 45.53% | 11.668 | 35.26% |
| `AppProcD` | 562 | 37.102 | 10.816 | 29.15% | 21.570 | 58.14% |
| `ServiceE` | 572 | 19.023 | 7.730 | 40.64% | 3.840 | 20.18% |
| `AppProcA` | 3772 | 13.102 | 4.898 | 37.39% | 4.785 | 36.52% |
| `ServiceD` | 1048 | 7.746 | 2.121 | 27.38% | 2.594 | 33.48% |

shell 等价画像成功且无 stderr。按受限尝试要求，将外部 armv7l 探针传到 `/root` 后只执行 `profile 2556`：退出码 0，二进制输出与 shell 输出逐字段一致。TV 未执行 pageout、未做 gdb 注入、未重启或终止进程；`gdb=MISSING`。清理返回 `TV_TEMP_CLEAN`。

## 5. 失败项与方法限制

- **A 路线未测**：RPI4 和 TV 均没有 gdb。任务规定无 gdb 则跳过，未采用其他注入手段。
- **有效目标少于计划**：尝试了四个目标，只有 AppUIA 与 AppUIB 完成 3/3。Chromium 两次在 60 s 静置期内被应用生命周期终止，均在 T0 前以 driver rc 21、`TARGET_PID_NOT_FOUND` 退出，未对其执行 pageout。
- **settings 轮次作废**：两次都完成到 T3，但 T4 分别以 `app_launcher` rc 255 和 `aul_test resume` rc 250 失败，driver rc 均为 32，故不进入核心表。
- **连续轮次存在历史状态**：没有重启 AppUIA 或 AppUIB。每轮虽重新执行相同的三轮应用负载，但第 1 轮 PAGEOUT 后的低驻留状态延续到后续轮次；这在 AppUIA 与 AppUIB 的 T0 原始值中直接可见。按合同仍取三轮中位数，未用第 1 轮替换中位数。
- **交互覆盖受限**：完成了应用切换、恢复和返回；板上缺少输入注入工具，未执行滚动。T4 仅测应用管理命令确认耗时，不是可见 UI 首帧耗时。
- **分类是近似签名**：1 MiB 对齐匿名段是历史兼容口径，不证明每个命中段都由 glibc arena 所有，也不能区分 `other-anon` 内的 GC、JIT、线程栈等子类。
- **zram 与 fault 并非进程独占**：zram 计数器为系统全局；`minflt/majflt` 来自目标 `/proc/<pid>/stat`，但响应窗口内也可能有目标后台活动。
- **安全检查**：六个有效轮次 T0–T4 的 PID 均不变、进程均存活；LMK/OOM/fatal/segfault 基线与每步复核均为 0。首次从默认 cwd 卸载 `/root` 返回 busy，改在 `/` 重试后成功；该失败与恢复原文均保留。

## 6. 原始文件

- 工具源码与产物：`bench/reclaim_probe/`
- 固定负载与采集脚本：`board_results/reclaim_ceiling_probe_20260806/scripts/`
- RPI4 有效轮次：`board_results/reclaim_ceiling_probe_20260806/test_board/runs/systemui/rep{1,2,3}/`、`test_board/runs/AppUIB/rep{1,2,3}/`
- RPI4 失败轮次：`test_board/runs/browser/`、`test_board/runs/settings/`
- RPI4 派生表：`test_board/derived_metrics.tsv`
- RPI4 恢复证据：`test_board/final/pre_cleanup.txt`、`cleanup.txt`、`cleanup_retry.txt`
- TV shell 原始画像：`product_board/pull/top5.tsv`、`product_board/pull/top5_profiles.jsonl`
- TV 二进制可执行性：`product_board/binary_profile.out`、`product_board/binary_profile.rc`
- TV 清理证据：`product_board/cleanup.stdout`、`product_board/cleanup.rc`
- 全文件逐项清单：`board_results/reclaim_ceiling_probe_20260806/raw_files_manifest.txt`
