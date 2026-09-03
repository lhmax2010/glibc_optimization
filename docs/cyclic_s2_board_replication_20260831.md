# RPI4 新 LLVM 镜像 S2 周期画像复现

- 执行日期：2026-08-31（host CST；板端 UTC+09:00）
- 目标板：`<TEST_BOARD_IP>`，仅经 SDB/26101；身份由三重门确认，不以地址判板
- 镜像：Tizen 11 Unified，`tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`
- glibc：`glibc-2.40-1.6.armv7l`
- 范围：仅 S2；`mixed` 与 `medium-only` 各一次、8 周期、无 trim；未执行 S3/S4
- 完整原始件：仅保留在本地 `board_results/cyclic_profile_replication_s2_20260831/`，不进入公开仓库
- 公开紧凑证据：[`data/raw/cyclic_profile_replication_s2_20260831/`](../data/raw/cyclic_profile_replication_s2_20260831/)
- 公开复用 harness：[`tools/runners/cyclic_s2_20260831/`](../tools/runners/cyclic_s2_20260831/)；保留冻结负载与分类口径，并在发布前补入 fail-closed 采样、初始 governor 门和输入顺序校验，执行副本/发布副本哈希均见其 README

> **2026-09-01 裁决追注（保留本报告执行时原文）：** 后续 F2/F3 审计确认产品
> `ServiceA` 的旧 `19.683240 s fall_edge` 是尾窗最小值落点伪影；正式完成代理为
> peak 后首次观测达到 `PD <= valley + 5% × (peak−valley)` 的
> `5.223693–8.910626 s` 上界。同时，产品
> 周期 PD 下降已自动归还，是 L6 反信号。故本报告中“等待 PM 在两个 S3 选项间
> 裁决”的状态已关闭：两个旧选项均不采纳，S3 原语义作废；本次 S2 数据保留为
> “约 6.4 MiB free 进入 rest/unsorted 且 PD 不降”的 bin 驻留表型板上基线，不再
> 要求复现产品 PD 峰谷。见
> [`cyclic_fall_mechanism_attribution_v2_20260901.md`](cyclic_fall_mechanism_attribution_v2_20260901.md)。

## 1. 结论摘要

1. **前置门、执行健康和回收语义均通过。** kernel、架构、BUILD_ID、glibc RPM、MemTotal 均与 2026-08-31 基线一致；两档各只运行一次，bench/sampler 均 `RC=0`；两份 JSON 可解析且冻结字段逐项匹配，64/64 份 XML 可解析。运行期间 dmesg 前后逐字节相同，zram 未使用，major fault 为 0。
2. **时序执行器复现了配置节奏。** `mixed` 的 rise/release 中位数为 `3.400143/19.702730 s`，`medium-only` 为 `3.400151/19.702684 s`，与 `3.4/19.7 s` 配置接近。代码没有独立记录 peak sleep 的实测 elapsed；其配置仍为 `4.7 s`，不能把配置值冒充独立实测值。
3. **M7 通过。** 每周期约 6.4 MiB payload 确实释放到 ptmalloc 的 rest/unsorted：`mixed` 的 rest/unsorted 增量中位数为 `6,447,939/6,443,936.5 B`，`medium-only` 为 `6,538,240/6,541,228 B`。XML 中 valley 明确出现 unsorted 块。
4. **S2 产品画像复现不成立。** 内部相位快照和外部 1 s 同口径序列都没有观察到 glibc-heap Private_Dirty 下降；两档峰减谷中位数均为 `-8 kB`，即 valley 反而高约 8 kB，属于边界采样量级。外部序列 16 个周期中可识别下降沿为 `0/16`。这与产品板 `ServiceA` 的 `6212 KiB` 峰谷中位数和 `19.683 s` 实测下降沿不符。
5. **S3 不应按冻结方案直接开跑。** 当前负载可以验证“渐进 free 进入 bins”和执行时序，但没有复现 S3 要代理的产品 PD 峰谷。如果直接跑 S3，只能解释为此合成 bin 驻留面的 trim 扫描，不能解释为已验证的 `ServiceA` 画像。是否接受这一缩窄语义，或先修订 S2 代理方案，需要 PM 裁决；本轮没有据首轮结果调参或补跑。

## 2. 前置门与执行纪律

### 2.1 SDB 与 host 判定

本机客户端为：

```text
Smart Development Bridge version 4.2.25
```

每条板端 shell 命令都由远端自身保存 `$?`，输出 `RC=` 和唯一 `DONE/FAIL` 标志；host 不使用 SDB 自身退出码判定。第一次 `uname -r` 查询已经返回 `RC=0 / DONE_UNAME_R`，但 host 包装器最初没有去除 SDB 的 CRLF，因而保守停止；修正为仅在 host 侧去除 `\r` 后，从身份门起点完整重跑。该事件发生在任何板端写入或负载之前。

### 2.2 三重身份门原文

```text
$ sdb shell uname -r
6.12.80-arm-rpi4-v7l
RC=0
DONE_UNAME_R
```

硬性项 a 包含 `rpi4`。

```text
$ sdb shell uname -m
armv7l
RC=0
DONE_UNAME_M
```

硬性项 b 严格为 `armv7l`。

```text
$ sdb shell cat /etc/os-release
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l
RC=0
DONE_OS_RELEASE
```

BUILD_ID 与基线报告完全一致。

### 2.3 环境未漂移原文

```text
$ sdb shell rpm -q glibc
glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC_RPM

$ sdb shell "awk '/^MemTotal:/ {print}' /proc/meminfo"
MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
```

两项与 [`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md) 一致，前置门判定 `PASS`。

## 3. 二进制、目录与 governor

冻结候选存在但 SHA 不匹配，因此没有使用。按照 `tools/alloc_bench/README.md` 从同一份 `alloc_bench.c` 重新交叉构建：

| 项目 | 值 |
|---|---|
| 冻结期望 SHA-256 | `314201e1d570fa03740ca0bf9823a73c9fa2403621279646f2174ffeb401c680` |
| 现有候选 SHA-256 | `0c27428044d4b283b2186938e724ecab834dc5f26462c40893db5274d4beaa40` |
| source SHA-256 | `93617220c8e1f0b4e988815a7210004d8296272ae11a733590cf859ef6e4e85d` |
| 编译器 | `armv7l-tizen-linux-gnueabi-gcc (Tizen GCC 14.2.0 20240801 1.2) 14.2.0` |
| scratch root | `<GBS_SCRATCH_ROOT>` |
| flags | `-std=c99 -O2 -g -Wall -Wextra -Werror -D_GNU_SOURCE -O2 -g -pthread` |
| 新产物 | ELF 32-bit ARM EABI5，动态链接，interpreter `/lib/ld-linux.so.3`，带 debug info |
| 新 SHA-256 | `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd` |
| 板上 SHA-256 | `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd` |

新 SHA 与冻结值不同是已允许的“缺失或不一致后重建”分支；本报告不把它写成冻结产物的字节复现。板端工作目录记为 `<TEST_BOARD_WORKDIR>`，位于 `/opt/usr`；创建前确认不存在，上传后 host/board SHA 一致。运行前 `/opt/usr` 约有 `111G` 可用。

4 核 governor 原始状态和恢复状态均为：

```text
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
```

控制器在 trap 生效后写入并复核 4 核均为 `performance`，结束时 trap 写回并复核 4 核均为 `schedutil`。host 在拉取前和删除目录后又各做一次独立只读复核，均为 `schedutil`。

## 4. 冻结负载与外部口径

两档只改变 `--profile`，公共参数逐字为：

```text
--threads 4 --seed 20260814 --live-set 512 --idle-release 50
--release-order high --touch-full --cycles 8 --cycle-rise 3.4
--cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20
--trim-at none --warmup 0
```

没有调用 `malloc_trim`、`MADV_PAGEOUT` 或 S3 探针。每档 bench 启动后立即取得 PID，并行运行 1 s `/proc/PID/smaps` 采样，直到进程退出。分类逐字复用产品板 collector / `reclaim_probe` 口径：

- `[heap]`，或 `rw-p`、无名、起址 1 MiB 对齐且长度 `<= 1 MiB` 的映射，计入 glibc heap；
- 其余可写匿名映射计入 other-anon；
- 其余映射计入 file-backed。

两档各取得 383 个数据点，覆盖约 383 s，deadline overrun 均为 0。外部逐周期值按冻结相位窗口划分：peak 取 `rise` 后 4.7 s 窗口最大值，valley 取 release 后 20 s 窗口最小值；这避免在“没有下降沿”时用事后调参强行找峰谷。完整 1 s 序列留在本地，公开仓库仅保留逐周期派生表。

## 5. 八周期逐周期结果

内存单位为 kB；`P-V` 为 peak 减 valley。内部值来自 JSON 相位边界；外部值来自独立 1 s smaps 序列。

### 5.1 mixed

| 周期 | 内部 peak / valley / P-V | 外部 peak / valley / P-V | rise 实测 | release 执行实测 |
|---:|---:|---:|---:|---:|
| 1 | 11568 / 11596 / -28 | 11576 / 11596 / -20 | 3.400109 s | 19.702533 s |
| 2 | 12904 / 12916 / -12 | 12904 / 12916 / -12 | 3.400116 s | 19.702629 s |
| 3 | 13444 / 13456 / -12 | 13448 / 13456 / -8 | 3.400142 s | 19.702762 s |
| 4 | 13684 / 13692 / -8 | 13684 / 13692 / -8 | 3.400930 s | 19.702681 s |
| 5 | 13692 / 13692 / 0 | 13692 / 13692 / 0 | 3.400142 s | 19.702821 s |
| 6 | 14052 / 14060 / -8 | 14052 / 14060 / -8 | 3.400246 s | 19.704530 s |
| 7 | 14060 / 14060 / 0 | 14060 / 14060 / 0 | 3.400145 s | 19.702711 s |
| 8 | 14256 / 14264 / -8 | 14256 / 14264 / -8 | 3.400161 s | 19.702748 s |

峰减谷中位数：内部 `-8 kB`，外部 `-8 kB`。valley 为 `11596 -> 12916 -> 13456 -> 13692 -> 13692 -> 14060 -> 14060 -> 14264 kB`，R1→R8 为 `+2668 kB`，非下降且单调不减。

### 5.2 medium-only

| 周期 | 内部 peak / valley / P-V | 外部 peak / valley / P-V | rise 实测 | release 执行实测 |
|---:|---:|---:|---:|---:|
| 1 | 11692 / 11716 / -24 | 11700 / 11716 / -16 | 3.400106 s | 19.702640 s |
| 2 | 12084 / 12092 / -8 | 12084 / 12092 / -8 | 3.400138 s | 19.702719 s |
| 3 | 12688 / 12708 / -20 | 12692 / 12708 / -16 | 3.400234 s | 19.702653 s |
| 4 | 12788 / 12796 / -8 | 12788 / 12796 / -8 | 3.400153 s | 19.702756 s |
| 5 | 12796 / 12796 / 0 | 12796 / 12796 / 0 | 3.400131 s | 19.702715 s |
| 6 | 12828 / 12836 / -8 | 12828 / 12836 / -8 | 3.400169 s | 19.702651 s |
| 7 | 12836 / 12836 / 0 | 12836 / 12836 / 0 | 3.400163 s | 19.702646 s |
| 8 | 12836 / 12836 / 0 | 12836 / 12836 / 0 | 3.400149 s | 19.702726 s |

峰减谷中位数：内部 `-8 kB`，外部 `-8 kB`。valley 为 `11716 -> 12092 -> 12708 -> 12796 -> 12796 -> 12836 -> 12836 -> 12836 kB`，R1→R8 为 `+1120 kB`，同样单调不减。

### 5.3 相位时长解释

| 口径 | mixed | medium-only | 配置/产品参考 | 判定 |
|---|---:|---:|---:|---|
| JSON rise 中位数 | 3.400143 s | 3.400151 s | 3.4 s / 产品 3.406 s | 执行节奏复现 |
| peak sleep | 未独立计时 | 未独立计时 | 4.7 s / 产品 4.682 s | 只能确认配置，不能声称实测 |
| JSON release executor 中位数 | 19.702730 s | 19.702684 s | 19.7 s / 产品 19.683 s | free 节奏复现 |
| 外部 PD 跌出 90% 峰值带 | 0/8 | 0/8 | 产品 8/8 可识别 | 不复现 |
| 外部 PD 峰值带 | 有 excursion 的周期均至少 43–44 s，右删失 | 同左 | 产品中位 4.682 s | 不复现；没有后续下降 |
| 外部 PD 下降沿 | 未观察到 | 未观察到 | 产品中位 19.683 s | 不复现；不能用 19.703 s 的 free 时长替代 |

第一周期外部 10%→90% 上升近似均约 4.0 s；后续因上一周期脏页和已建 arena 被复用，增量 excursion 很小或为零，10%→90% 只需约 1–2 s或不可定义。正式判断采用内部 pacing 证明时序执行、外部序列证明 PD 形状，二者不混用。

## 6. 与产品板 ServiceA 对照

| 指标 | 产品板 ServiceA | mixed S2 | medium-only S2 | 偏差 |
|---|---:|---:|---:|---|
| glibc peak→valley 中位数 | 6212 KiB | -8 kB | -8 kB | 两档均少 6220 kB；实际为零下降 |
| rise | 3.406 s | 3.400143 s | 3.400151 s | `-0.006 s`，pacing 接近 |
| peak band | 4.682 s | 无下降、≥43–44 s 右删失 | 同左 | 形状不符 |
| fall | 19.683 s | 无 PD 下降沿；free 为 19.702730 s | 无 PD 下降沿；free 为 19.702684 s | free 节奏接近但内存响应缺失 |
| 八轮谷底变化 | P0→R8 `+788 kB`，非严格单调 | R1→R8 `+2668 kB` | R1→R8 `+1120 kB` | 分别 `+1880/+332 kB`，且两档单调不减 |
| M7 释放入 bins | 产品板边界不可取 | 约 6.44 MB rest/unsorted | 约 6.54 MB rest/unsorted | 合成负载语义成立 |

第一周期前 S2 进程尚未建立持久 live pool，因此如果从 cycle 1 start 算到 R8 valley，会得到更大的初始化增量；为避免把首次建池混入产品的八轮谷底比较，上表使用 R1 valley→R8 valley。即便采用这一更保守口径，mixed 偏差仍明显。

本轮不根据偏差修改 `live-set`、分布、release 比例、顺序、时长或任何其他参数，也没有补跑。

## 7. M7：unsorted/rest 直接证据

两档 8 个周期的 `m7_rest_delta_bytes` 和 `m7_unsorted_delta_bytes` 均为正。第一周期 XML 摘录：

```xml
<!-- mixed peak, top level -->
<total type="rest" count="10" size="132757"/>
<!-- mixed valley, arena examples -->
<unsorted from="1033" to="859497" total="1346737" count="17"/>
<unsorted from="1033" to="866593" total="1435741" count="13"/>
<!-- mixed valley, top level -->
<total type="rest" count="67" size="6020134"/>
```

对应 JSON：rest `+5,887,377 B`，unsorted `+5,742,148 B`。

```xml
<!-- medium-only peak, top level -->
<total type="rest" count="17" size="168692"/>
<!-- medium-only valley, arena examples -->
<unsorted from="557441" to="1026537" total="1583978" count="2"/>
<unsorted from="663057" to="1018345" total="1681402" count="2"/>
<!-- medium-only valley, top level -->
<total type="rest" count="17" size="6473348"/>
```

对应 JSON：rest `+6,304,656 B`，unsorted `+6,299,880 B`。这证明 `free` 确实发生并进入 allocator bins；它同时解释了为何“没有 PD 下降”不能误判为 release 命令未执行。

## 8. 运行健康、完整性与清理

| 项目 | mixed | medium-only | 判定 |
|---|---:|---:|---|
| bench / sampler RC | 0 / 0 | 0 / 0 | PASS |
| 外部样本 / overrun | 383 / 0 | 383 / 0 | PASS |
| JSON / 周期数 | parse PASS / 8 | parse PASS / 8 | PASS |
| XML | 32/32 parse PASS | 32/32 parse PASS | PASS |
| bench stderr | 0 B | 0 B | PASS |
| 外部 sampler stderr | 0 B | 0 B | PASS |
| rise minflt 合计（JSON） | 3750 | 3399 | 已记录 |
| 外部首末 minflt 增量 | 3726 | 3403 | 与内部量级一致 |
| majflt | 0 | 0 | PASS |

运行前后 dmesg 均为 43,475 B、567 行，SHA-256 均为 `a1ee606bb78db7edfef06bb45a26241a9fcb4252e173bb3b9e1e2c2d9f6bab73`，文件逐字节相同，因此增量为空，没有新增 OOM/LMK 证据。

zram `mm_stat` 前后原文相同。按 kernel 字段顺序拆列后为：orig data `4096 B`、
compressed data `74 B`、total memory `4096 B`、memory limit `0 B`、peak memory
`4096 B`，其余 same pages/pages compacted/huge pages/huge pages since 均为 `0`。

`/proc/swaps` 中 `/dev/zram0` 前后 Used 均为 `0 kB`。

板端生成的 manifest 覆盖 102 个文件；host 拉回后 `102/102` SHA-256 校验通过。两份 JSON 大小为 15,927/16,176 B，两份外部序列为 39,337/38,954 B。确认 JSON/XML/序列和健康证据完整后，才解析工作目录真实路径并删除；随后复核目录不存在且 4 核均为 `schedutil`。没有安装/删除包，没有执行 `sdb root on`。

## 9. Host 口径限制

沿用 08-14 报告的限制：host 的既有 1 MiB arena 启发式把 pthread arena 映射计入 `other-anon`，host 校准中的 `glibc-heap PD` 不能作为产品画像复现证据。host 的线程 arena 映射布局与 armv7l Tizen 不同，host 三分类只用于暴露口径限制，不作为板上曲线。正式判断只使用本轮 armv7l 板上的内部相位采样和独立 1 s smaps 序列。

本轮板上内外口径使用相同启发式，但仍有方法限制：1 s 外部序列是离散近似；`malloc_info()` 和内部 `/proc` 读取位于相位边界，会产生小量时间包络；Private_Dirty 只说明页面状态，不能单独等同于 live payload 或可 trim 字节。以上限制不会改变“16 个周期均无可识别 PD 下降”的方向。

## 10. 最终判断与 PM 裁决项

### 10.1 S2 是否成立

**不成立。** 冻结负载在板上准确执行了 rise/free 节奏，且 M7 证明约 6.4 MiB 每周期进入 rest/unsorted；但核心合同——复现 `ServiceA` 的 `6212 KiB`（约 `6.07 MiB`）glibc PD 峰谷和约 19.7 s PD 下降沿——在内部与外部两种口径均失败。因此不能把当前 S2 标记为产品板周期画像的有效代理。

### 10.2 S3 能否直接开跑

**不能按原冻结语义直接开跑。** PM 需要在以下偏差上裁决：

1. 是否接受 S3 降格为“约 6.4 MiB bin 驻留、渐进 free 的合成 trim 时机扫描”，明确不再声称已复现产品 PD 画像；
2. 或者先修订 S2 代理合同/参数，再经新一轮批准后重跑 S2；本轮结果不得被用来现场调参；
3. 无论选择哪条路径，新镜像的 S4 `mixed / medium-only` 瞬时释放参考格仍需补跑；历史 `53.55% / 50.60%` 不恢复为同板阈值。

## 11. 证据索引

- [`run_record.txt`](../data/raw/cyclic_profile_replication_s2_20260831/run_record.txt)：身份、构建、冻结参数、尝试次数、manifest 与清理门。
- [`internal_cycles.tsv`](../data/raw/cyclic_profile_replication_s2_20260831/internal_cycles.tsv)：16 个内部相位周期、时长、M7 和 faults。
- [`external_cycles.tsv`](../data/raw/cyclic_profile_replication_s2_20260831/external_cycles.tsv)：固定相位窗口派生的外部峰谷与信号沿判定。
- [`summary.json`](../data/raw/cyclic_profile_replication_s2_20260831/summary.json)：两档中位数与趋势汇总。
- [`m7_xml_excerpts.txt`](../data/raw/cyclic_profile_replication_s2_20260831/m7_xml_excerpts.txt)：第一周期 XML 直接摘录。
- [`health_summary.txt`](../data/raw/cyclic_profile_replication_s2_20260831/health_summary.txt)：dmesg、zram、fault 和 stderr 紧凑健康证据。

完整原始 JSON、64 份 XML、两条 1 s 全序列、命令记录、拉取 manifest、dmesg 快照与构建日志仅位于本地 `board_results/cyclic_profile_replication_s2_20260831/`，不推公开仓库。
