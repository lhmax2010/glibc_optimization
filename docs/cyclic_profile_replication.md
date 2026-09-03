> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# 周期型分配画像的受控复现与 trim 时机扫描

原始执行状态（2026-08-14）：**板上扫描阻塞于 RPI4 SDB 通道；实现、host 验证与 armv7l 构建已完成。**

后续状态（2026-08-31）：**SDB 通道和新镜像基线已恢复；S2 已按冻结参数执行，但产品 PD 峰谷画像未复现，S3 暂停等待 PM 裁决。** 详见 [`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md) 和 [`cyclic_s2_board_replication_20260831.md`](cyclic_s2_board_replication_20260831.md)。
日期：2026-08-14（Asia/Shanghai）

## 1. 身份门、环境与工具扩展

### 1.1 板身份门

目标地址沿用最近一次 RPI4 任务的 `<TEST_BOARD_IP>:26101`。本轮没有取得
shell，因此三重身份门未执行成功，也没有向板上推送或执行任何文件。

原始通道记录：

```text
$ sdb connect <TEST_BOARD_IP>
connecting to <TEST_BOARD_IP>:26101 ...
failed to connect to <TEST_BOARD_IP>:26101

$ sdb devices
List of devices attached

$ sdb kill-server; sdb start-server; sdb connect <TEST_BOARD_IP>
error: protocol fault: no status
* Server is not running. Start it now on port 26099 *
* Server has started successfully *
connecting to <TEST_BOARD_IP>:26101 ...
failed to connect to <TEST_BOARD_IP>:26101
```

网络只读探测显示 `.26` 可 ping、TCP 26101 可建立，但 SSH 22 拒绝连接；
SDB 协议握手没有成功。因此本报告不记录板上 glibc、MemTotal、governor、
zram 等协变量，避免把历史环境当成本轮事实。

### 1.2 alloc_bench 扩展

修改文件：

- `bench/alloc_bench/alloc_bench.c`
- `bench/alloc_bench/selftest.sh`
- `bench/alloc_bench/README.md`

新增能力：

| 项目 | 实现事实 |
|---|---|
| `--release-duration SEC` | 周期模式下将释放均摊到指定时长；`0` 保持瞬时释放 |
| `--cycles N` | 1-64 个周期；worker 跨周期存活并保留各自 live pool/arena |
| 周期参数 | `--cycle-rise`、`--cycle-peak`、`--cycle-valley` |
| trim 时机 | `none`、`peak`、`fall-mid`、`valley`、`valley+N` |
| 尺寸档 | 新增内置 `medium-only`：1/2/4/8/16 KiB 等权 |
| JSON | schema 仍为 `alloc_bench_v1_1`，周期模式为 `mode=cyclic` |
| 每周期采集 | start/peak/fall-mid/valley/trim 前后堆 PD、释放 payload、trim 返回值/耗时、下一周期 faults |
| M7 | peak/fall-mid/valley/posttrim 四阶段 fast/rest/unsorted/arena 与 XML |
| 渐进性证据 | JSON 输出释放 25/50/75/100% 四个时间检查点 |

非周期调用仍走原 v1.1a 相位机，原 JSON 字段和一次性 `idle-release` 行为未改。

### 1.3 host 与交叉构建质量门

```text
PASS build host
PASS A1 determinism
PASS A2 ASan+UBSan seven built-in profiles
PASS A3 RSS lower-bound sanity
PASS A4 JSON parse
PASS A5 armv7l ELF 32-bit ARM dynamic
PASS A6 burst-free-small fastbin residual
PASS A7a mixed idle-release retained free bytes
PASS A7b mixed idle-release idle-trim OS reclaim
PASS A8 new-profile determinism
PASS A9 v1 profile old-field compatibility
PASS A10 release orders and applicability instrumentation
A11_RELEASE_PROGRESS_NS=[100163219, 200128659, 300941627, 400954183]
PASS A11 cyclic progressive-release timing
SUMMARY PASS=13 FAIL=0
```

额外的周期 ASan+UBSan 短跑为零报告。armv7l 产物：

```text
ELF 32-bit LSB executable, ARM, EABI5, dynamically linked
interpreter /lib/ld-linux.so.3
NEEDED libpthread.so.0, libc.so.6
SHA-256 314201e1d570fa03740ca0bf9823a73c9fa2403621279646f2174ffeb401c680
```

## 2. S2 画像复现验证

### 2.1 Host 校准（非板上结果）

使用 `mixed`、4 线程、512 objects/thread、release 50%、high 顺序、
rise 3.4 s、peak 4.7 s、fall 19.7 s 跑 1 个无 trim 周期：

| 指标 | 产品板 `ServiceA` 画像 | host 校准 | 状态 |
|---|---:|---:|---|
| 峰谷/释放规模 | glibc heap PD 中位 6212 KiB | payload 6,390,240 B（6.094 MiB） | 数量接近，口径不同 |
| 上升沿 | 3.406 s | 3.400188 s | 接近 |
| 峰值带 | 4.682 s | 4.7 s 配置值 | 接近 |
| 下降沿 | 19.683 s | 19.701299 s | 接近 |
| 谷底趋势 | 3464 -> 4252 kB（8 轮） | 未做有效板上多周期观测 | 未验证 |

host 的既有 1 MiB arena 启发式把 pthread arena 映射计入 `other-anon`，
该轮 `glibc-heap PD` 为 start/peak/valley = 120/24/32 kB，不能作为产品画像
复现证据。全量触碰校准中，peak `other-anon PD` 为 12,612 kB，与完整 live
payload 的量级一致。正式判断必须使用 armv7l 板上的同口径采样。

M7 在 host 校准中可见：peak -> valley 的 rest 增量 6,398,826 B，unsorted
增量 6,366,153 B；它只证明受控释放发生，不替代板上 PD 画像。

### 2.2 板上复现

2026-08-31 已在身份门通过后按以下冻结参数采集：

```text
--threads 4 --seed 20260814 --live-set 512 --idle-release 50
--release-order high --touch-full --cycles 8 --cycle-rise 3.4
--cycle-peak 4.7 --release-duration 19.7 --cycle-valley 20
--trim-at none --warmup 0
```

`mixed` 与 `medium-only` 各运行一次，没有依据首轮结果改变参数。rise/release
执行节奏和 M7 bin 释放成立，但内部与外部 glibc-heap PD 均没有下降；两档
peak-valley 中位数均为 `-8 kB`，不复现产品板的 `6212 KiB` 中位数。因此 S2
总体判定不成立，完整结果见 [`cyclic_s2_board_replication_20260831.md`](cyclic_s2_board_replication_20260831.md)。

## 3. S3 trim 时机扫描

板上 6 格 x 3 重复尚未执行。由于 S2 核心画像合同未通过，S3 暂停等待 PM
决定是接受“合成 bin 驻留面”的缩窄语义，还是先修订 S2 代理方案。原冻结公共参数与 S2 相同，但每次 `--cycles 2`，
以第二周期记录第一周期 trim 后的 refault；格为 `peak`、`fall-mid`、
`valley`、`valley+5`、`valley+20`、`none`。

| 时机 | rep | A_ceiling | A / 周期峰谷差 | trim 耗时 | next-cycle minflt/majflt | M7 rest/unsorted |
|---|---:|---:|---:|---:|---:|---:|
| peak | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |
| fall-mid | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |
| valley | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |
| valley+5 | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |
| valley+20 | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |
| none | 1-3 | 未采集 | 未采集 | 未采集 | 未采集 | 未采集 |

## 4. S4 派生

由于 S3 没有板上输入，本轮不能计算以下派生量：

- 回收比例 vs trim 时机曲线；
- 最佳时机回收比例乘以产品板 `6212 KiB`（`6.07 MiB`）峰谷差；
- 渐进释放与既有瞬时释放曲线的差异。

既有瞬时释放参考值为 `mixed / 50% / high = 53.55%`、
`medium-only / 50% / high = 50.60%`。2026-08-31 的新镜像在 BUILD_ID、
kernel build、glibc RPM release、MemTotal 与 zram 容量上均已变化，因此这些值
仅保留为历史 sanity range，不能作为新镜像的同板对照或通过阈值；S4 必须先在
新镜像补跑两项参考格。本报告没有把历史值代入尚未完成的渐进释放扫描。

## 5. 2026-08-14 初始失败、限制与恢复现场

1. 阻塞点发生在板身份门之前：SDB TCP 端口可达，但协议连接失败；SSH 关闭。
2. 未向 `.25` 或 `.26` 推送二进制、脚本或数据，未运行负载，未触碰系统应用、
   service 或持久配置。
3. host 的线程 arena 映射布局与 armv7l Tizen 不同，host 三分类仅用于暴露
   口径限制，不作为板上曲线。
4. `malloc_info()` 本身会短暂分配；所有调用位于相位边界，worker 在等待态。
5. 周期模式把 release 分成两半以在 fall-mid 采样；中点 XML/`/proc` 采集时间
   会令完整下降沿比配置值多出少量包络，JSON 同时记录实际检查点。

恢复现场：板上没有产生任何临时文件或进程，因此无板上残留。

## 6. 原始文件

2026-08-14 当时仅有 host 验证临时结果（位于 `/tmp/cyclic-host-cal.*` 与
`/tmp/cyclic-touch-cal.*`，不属于板上证据）。板上原始目录原计划在通道恢复后
建立为 `board_results/cyclic_profile_replication_20260814/`；截至 2026-08-31，
该初始目录没有创建。后续 S2 完整原始件仅保留于本地
`board_results/cyclic_profile_replication_s2_20260831/`，公开紧凑证据位于
[`data/raw/cyclic_profile_replication_s2_20260831/`](../data/raw/cyclic_profile_replication_s2_20260831/)。
