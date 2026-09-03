> Public archive note: host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# S4 新镜像参考格与滞留表型 trim 效果/代价

- 日期：2026-09-01
- 传输：`sdb`，报告地址统一记为 `<TEST_BOARD_IP>`
- 执行纪律：身份/环境门通过后才写板；板端工作目录固定为 `/opt/usr/glibc_memopt/s4_retention_20260901/`；全程不信任 sdb 自身退出码，以远端 `RC=0` 和 `DONE_*` 双标志判定
- harness：[`tools/runners/s4_retention_20260901/`](../tools/runners/s4_retention_20260901/)

## 1. 执行前冻结规格

本节在建立任何板端连接前写定。所有参数、重复数、顺序和判据在看见本轮结果前冻结；本轮不依据结果调参或补重复。

### 1.1 共同环境合同

- 身份门：`uname -r` 含 `rpi4`；`uname -m` 严格为 `armv7l`；`BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`。
- 未漂移门：`glibc-2.40-1.6.armv7l`；`MemTotal` 以 `8117408 kB ±1%`（`8036234–8198582 kB`）验收。
- 二进制：沿用 S2 已验产物，SHA-256 固定为 `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`。
- governor：四核初值记录并要求均为 `schedutil`；运行统一切到 `performance`；退出 trap 无论成败恢复四核 `schedutil` 并复核。
- 健康证据：全矩阵前后 `zram0/mm_stat`、`/proc/swaps`、`dmesg`；dmesg 增量要求 OOM/LMK 零命中。
- 每格伴随同 S2/product 口径的 1 s `smaps` 采样，glibc heap PD 与 other-anon 分栏；JSON 必须解析成功、所有 `malloc_info` XML 必须解析成功。

### 1.2 A 组：新 LLVM 镜像瞬时释放参考格（2 格）

历史格由 `tools/runners/l6_applicability_curve_20260813/run_frozen_matrix.sh` 与冻结 `matrix.tsv` 反推。历史每格为三次重复的中位数；本轮按任务合同各只跑一次，历史数字只作不可比参考，不设复现阈值。

共同完整参数：

```text
--threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15
--idle-trim --post-trim-ops-per-thread 4096
--live-set 4096 --idle-release 50 --release-order high
```

| 本轮格 | `--profile` | 重复 | 历史不可比参考 | 画像输入 |
|---|---|---:|---:|---|
| A-mixed | `mixed` | 1 | 53.55% | 内建 mixed |
| A-medium-only | `external:/opt/usr/glibc_memopt/s4_retention_20260901/medium_1k_16k.hist` | 1 | 50.60% | `1024/2048/4096/8192/16384` 等权；hist SHA-256 `2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b` |

参考格主口径沿用历史报告：`(glibc_heap_pd_pretrim - glibc_heap_pd_posttrim) / glibc_heap_pd_pretrim`。机制基线预期为释放比例 `50% × 0.98 ≈ 49%`，只按页粒度和单次格作相容性解释；同时列出“回收字节 / 已释放 payload”避免口径混淆。

### 1.3 B 组：滞留表型 trim 效果/代价（8 格）

除 `--cycles` 从 S2 的 8 改为任务指定的 2、以及 `--trim-at` 按矩阵取值外，其余逐字保留 S2 冻结参数：

```text
--threads 4 --seed 20260814 --live-set 512 --idle-release 50
--release-order high --touch-full --cycles 2 --cycle-rise 3.4
--cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20
--warmup 0
```

矩阵顺序固定为：

| profile | `--trim-at valley` | `--trim-at none` |
|---|---:|---:|
| mixed | rep1、rep2、rep3 | rep1 |
| medium-only | rep1、rep2、rep3 | rep1 |

每格报告：两周期已释放 payload；trim 前/后 glibc heap PD 和据此得到的回收量；`trim 回收 / 已释放 payload`；trim 前/后 M7 `rest_bytes` 与 `unsorted_bytes`；`malloc_trim` 返回值与耗时；第一周期之后下一周期的 minflt/majflt；进程/采样器退出码；全程外部序列样本数与 faults 增量。`none` 格是驻留对照，不把 `trim_return=-1` 和 `trim_elapsed=0` 解释为调用结果。

### 1.4 预先写定的判断规则

1. A 组：以回收率是否和约 `49%` 的机制预期同方向、处于页粒度/单次噪声可解释范围内作相容性判断；历史 `53.55% / 50.60%` 不作通过阈值。
2. B 组：“表型门控 trim”叙事要求同一冻结负载同时给出：反信号已排除（S2 已证明 PD 不自动下降）、M7 在 trim 前确认 rest/unsorted 驻留、主动 trim 后 PD 实降、回收/释放比例、trim 延迟、下一周期 minflt/majflt。任一字段缺失则只列缺口，不外推。
3. 任一身份/环境门、JSON/XML 完整性、OOM/LMK 或 governor 恢复门失败，停止并只报告已完成部分。

## 2. 前置门与执行时间线

### 2.1 通道与硬门原文

本机客户端为 `Smart Development Bridge version 4.2.25`。`sdb connect` 报告已连接；`sdb devices` 的设备地址在公开文本中脱敏为 `<TEST_BOARD_IP>:26101`，其名称列为 `rpi4`。设备名和地址均不代替三重身份门。

```text
$ sdb shell uname -r
6.12.80-arm-rpi4-v7l
RC=0
DONE_UNAME_R

$ sdb shell uname -m
armv7l
RC=0
DONE_UNAME_M

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

$ sdb shell rpm -q glibc
glibc-2.40-1.6.armv7l
RC=0
DONE_GLIBC_RPM

$ sdb shell awk '/^MemTotal:/ {print}' /proc/meminfo
MemTotal:        8117408 kB
RC=0
DONE_MEMTOTAL
```

三项身份门、glibc 与 MemTotal 门全部通过。当前用户原文为 `uid=0(root) ... context="User::Shell"`；本轮未执行 `sdb root on`。`/opt/usr` 为 `/dev/mmcblk0p5`，执行前可用 `111G`。目标目录执行前不存在。

### 2.2 资产、governor 与时间线

| 时间/阶段 | 证据与判定 |
|---|---|
| 执行前 | cpu0–3 均为 `schedutil`；四个上传资产 host/board SHA-256 逐项一致 |
| 二进制门 | `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`，通过 |
| 运行态 | cpu0–3 均复核为 `performance` |
| board start | `2026-09-01T17:27:07,555825180+0900` |
| A-mixed / A-medium-only | 各 bench/sampler `0/0`，各 41 个 1 s 样本，均 DONE |
| B 8 格 | 各 bench/sampler `0/0`，各 96 个 1 s 样本，均 DONE |
| board end | `2026-09-01T17:41:18,317474858+0900` |
| 退出 trap | `DONE_GOVERNOR_RESTORE`；cpu0–3 均为 `schedutil` |

控制器在板端再次重复身份、glibc、MemTotal、二进制/hist 哈希门，全部 `RC=0/DONE_*` 后才切 governor。10 格顺序与 §1 一致，未补跑、未删格、未调参。

## 3. A 组结果：新镜像锚点

| profile | pre → post trim glibc PD (kB) | 回收 (kB) | 回收率 / pretrim | 回收 / 已释放 | 机制预期 | 与预期差 | 历史不可比参考 | trim (ms) | refault min/maj |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mixed | 104648 → 51200 | 53448 | **51.074077%** | 108.002588% | 49.0% | +2.074077 pp | 53.55% | 13.331907 | 1655 / 0 |
| medium-only | 107248 → 53208 | 54040 | **50.387886%** | 104.710419% | 49.0% | +1.387886 pp | 50.60% | 12.723240 | 3093 / 0 |

两格 `malloc_trim` 均返回 1，trim 自身 faults 均为 `6/0`；外部全程 majflt 也均为 0。回收量 `53448/54040 kB` 均为 4 kB 页粒度整数倍。

**A 组判断：相容。** 两个单次新镜像锚点分别为 `51.074077%` 和 `50.387886%`，距 `50% × 0.98 = 49%` 只有 `+2.074077 / +1.387886 pp`，方向、量级和页粒度均符合机制基线。历史 `53.55% / 50.60%` 来自旧板/旧镜像三次中位数，只列参考；本轮相对历史为 `-2.475923 / -0.212114 pp`，不据此判复现成败。

## 4. B 组结果：trim 效果与代价

### 4.1 逐格结果

每行的回收、M7 和 trim 时间是该格两个周期的中位数；“下一周期 faults”严格取 cycle 1 之后的 cycle 2 rise。每个 profile 的两个周期释放 payload 固定列在表头说明中：mixed 为 `5,742,256 / 6,566,672 B`，medium-only 为 `6,288,384 / 6,293,504 B`。

| profile | trim | rep | 回收中位 (kB) | 回收/释放 | M7 rest pre→post (B) | M7 unsorted pre→post (B) | trim ret / ms | 下一周期 min/maj | 外部样本 / 全程 min/maj | exit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mixed | valley | 1 | 4914 | 81.661264% | 6380078 → 6406806 | 6166817 → 6166922 | 1 / 1.369064 | 1678 / 0 | 96 / 4748 / 0 | 0 |
| mixed | valley | 2 | 4914 | 81.661264% | 6379966 → 6406695 | 6166817 → 6166922 | 1 / 1.446352 | 1678 / 0 | 96 / 4747 / 0 | 0 |
| mixed | valley | 3 | 4914 | 81.661264% | 6379974 → 6406703 | 6166817 → 6166922 | 1 / 1.142324 | 1678 / 0 | 96 / 4748 / 0 | 0 |
| mixed | none | 1 | 0 | 0% | 6361542 → 6361542 | 6166817 → 6166817 | 未调用 / 0 | 327 / 0 | 96 / 3391 / 0 | 0 |
| medium-only | valley | 1 | 5188 | 84.446566% | 6587192 → 6613816 | 6433224 → 6433224 | 1 / 1.267972 | 1557 / 0 | 96 / 4690 / 0 | 0 |
| medium-only | valley | 2 | 5188 | 84.446566% | 6587192 → 6613816 | 6433224 → 6433224 | 1 / 1.218361 | 1557 / 0 | 96 / 4689 / 0 | 0 |
| medium-only | valley | 3 | 5188 | 84.446566% | 6587056 → 6613680 | 6433224 → 6433224 | 1 / 0.995379 | 1557 / 0 | 96 / 4687 / 0 | 0 |
| medium-only | none | 1 | 0 | 0% | 6568760 → 6568760 | 6433224 → 6433224 | 未调用 / 0 | 92 / 0 | 96 / 3218 / 0 | 0 |

`none` 格中的 JSON 合同值为 `trim_return=-1`，表示未调用，不是 trim 失败。逐周期精确值见紧凑 [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)：

- mixed：cycle 1 `11500 → 7004 kB`，回收 `4496 kB / 80.175875%`；cycle 2 `12804 → 7472 kB`，回收 `5332 kB / 83.146653%`。
- medium-only：cycle 1 `11632 → 6508 kB`，回收 `5124 kB / 83.439179%`；cycle 2 `11876 → 6624 kB`，回收 `5252 kB / 85.453954%`。

三次 valley 重复的回收量、比率、下一周期 faults 逐字一致；trim 调用时间、M7 rest bytes 与外部全程 minflt 只有微小离散。trim 前 M7 已明确显示约 5.7–6.8 MB rest、5.7–6.6 MB unsorted。trim 后 `malloc_info` 的 rest/unsorted 不下降并不与 PD 回收冲突：M7 统计 allocator 中逻辑空闲 chunk，trim 可丢弃其物理页而保留 chunk/arena 元数据。

### 4.2 聚合效果/代价

| profile | trim 回收范围 / 中位 (kB) | 回收/释放范围 / 中位 | trim 时间范围 / 中位 (ms) | 下一周期 minflt：trim / none / 增量 | majflt |
|---|---:|---:|---:|---:|---:|
| mixed | 4496–5332 / 4914 | 80.175875–83.146653% / 81.661264% | 1.042000–1.850704 / 1.233269 | 1678 / 327 / **+1351** | 全部 0 |
| medium-only | 5124–5252 / 5188 | 83.439179–85.453954% / 84.446566% | 0.990537–1.280260 / 1.218361 | 1557 / 92 / **+1465** | 全部 0 |

16 个 B 周期内部 `peak − valley` 为 `-28…-8 kB`：free 后 valley 没有 PD 可见下降，反而只高 8–28 kB；这与 S2 的“bin 驻留、无自动归还”表型一致。valley trim 随后立即回收 4.4–5.2 MiB，且下一周期只出现额外 minflt、没有 majflt。

## 5. 运行健康、完整性与清理

| 门 | 结果 |
|---|---|
| zram `orig/compressed/mem_used_total` | `4096/74/4096 → 4096/74/4096 B`，三项 Δ=0 |
| dmesg 增量 | before 是 after 的完整前缀；增量 0 行；OOM/LMK 0 命中 |
| 外部采样 | A 各 41、B 各 96，共 850 行；10 格 PID 均恒定；deadline overrun 全部 0；majflt 全部 0 |
| JSON/XML | 10/10 JSON parse；72/72 `malloc_info` XML parse |
| 拉回完整性 | 198 个 manifest SHA 全通过；199 行板端大小记录零不匹配；完整目录共 200 文件、1.3 MB |
| 清理 | 精确路径校验后删除 `/opt/usr/glibc_memopt/s4_retention_20260901`；复核不存在；cpu0–3 均为 `schedutil`；`RC=0/DONE_FINAL_CLEANUP` |

完整原始件保留在本地 `board_results/s4_retention_20260901/`，不进入公开仓库。公开仓库只收录派生表、健康摘要和不含真实地址的门证据。

## 6. 判断

### 6.1 新镜像锚点

**成立。** A 组新锚点与“回收率 ≈ 释放比例 × 0.98，按页归还”的机制基线相容；正式锚点更新为 mixed `51.074077%`、medium-only `50.387886%`。旧 `53.55% / 50.60%` 继续仅作换板换镜像的不可比参考。

### 6.2 表型门控 trim

**对 S2 合成滞留表型，叙事所需的冻结数字齐全并得到支持：**

1. 反信号排除：16/16 周期均没有 free 后 PD 自动下降；
2. M7 驻留确认：trim 前 rest/unsorted 均为 MB 级；
3. 主动回收：mixed/medium-only 分别回收释放 payload 的中位 `81.661264% / 84.446566%`；
4. 已知代价：释放点 trim 的分档中位为 mixed `1.233269 ms` / medium-only `1.218361 ms`，下一周期相对 none 增加 `1351 / 1465` 次 minflt，majflt 为 0；
5. 健康门：zram 不变、dmesg 无增量、零 OOM/LMK、所有退出和清理门通过。

**尚缺、因此不能直接升级为产品投放结论的数字：**

- 产品候选 retained floor（包括 `enlightenment +1736 kB`、`ServiceH[ServiceK]` 平台和 `ServiceA +788 kB` 残渣）的 M7 live/bin 分解；本轮只验证合成代理。
- trim 在真实并发线程下的全 arena 锁停顿、业务 p99/帧时延；本轮只有单次调用 wall time。
- 下一周期额外 minflt 对业务墙钟/能耗的换算；当前只得到 faults 计数。
- `none` 每档仅一次，按冻结合同没有对照方差；valley 三次足以证明本负载的重复性，但不能替代更广工作负载覆盖。

因此本轮支持“**反信号排除 → M7 确认驻留 → trim 以明确 page-fault/调用耗时代价回收**”作为实验门控叙事；是否对具体产品候选启用，仍必须补齐上列产品侧 M7 与业务代价门。
