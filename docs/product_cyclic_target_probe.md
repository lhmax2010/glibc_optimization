> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# 周期型目标 ServiceA 定向峰谷测量

- Host 日期：2026-08-14（Asia/Shanghai）
- 板端窗口：2026-08-14 01:55:47.993 - 02:06:47.716（`-0700`）
- 通道：SSH root，无 PTY；采集体经 stdin 注入已签名 `sh`
- 边界：未安装包、未推送二进制、未注入调试器、未重启 service、未修改配置
- 名称：全文只使用公开仓库既有代号

## 1. 身份、环境与目标

身份门通过：

```text
IDENTITY_OK
kernel=6.12.60
arch=armv7l
VERSION="10.0.0 (<PRODUCT_IMAGE>)"
vk_send=/usr/bin/vk_send
glibc-2.40-1.12.armv7l
GNU C Library 2.40, compiled by GNU CC 14.2.0
MemTotal:      1599416 kB
MemAvailable:  808624 kB
zram size/used: 1039320/92940 kB
overcommit_memory=1
```

正式窗口内 `MemAvailable` 为 737800-801396 kB，zram 已用为
92684-92940 kB。

全进程画像取得 315 个可读进程。为降低 smaps 遍历开销，正式采集只保留
4 个目标；P0 基线取 60 s 静置期最后一个实际采样点：

| 目标 | 角色 | PID | glibc heap PD (kB) | other-anon PD (kB) | file-backed PD (kB) |
|---|---|---:|---:|---:|---:|
| `ServiceA` | 本轮主目标 | 3953 | 3464 | 4300 | 2656 |
| `ServiceB` | 另一周期型候选 | 692 | 3940 | 4440 | 2176 |
| `ServiceH[ServiceK]` | 平台型频道 loader 对照 | 3740 | 13252 | 25724 | 4324 |
| `ServiceE` | Web Runtime 无响应对照 | 545 | 8772 | 2120 | 7800 |

四个 PID 在 660 个样本点中均未变化，每目标均有 660 行且无 `NA`。

### vk_send 预演

预演前 `ServiceH[ServiceK]` 为 `PAUSED/STATUS_BG`；发送 `73` 后变为
`RESUMED/STATUS_FOCUS`；发送 `182` 后回到 `RESUMED/STATUS_BG`。本镜像中
按键生效时 `vk_send` 返回码仍为 1，与上一轮一致。预演通过后才启动正式窗口。

## 2. 按键时间线

每轮均发出固定序列 `73,116,116,116,182,96,96,95,95,138,182`。下表为
相对 collector 起点的板端实际秒数与键值；完整绝对时间戳见
`derived/key_timeline_alias.tsv`。

| 轮次 | 实际时间线（elapsed s / key） |
|---|---|
| R1 | 60.055/73; 63.185/116; 64.272/116; 65.097/116; 66.144/182; 69.176/96; 73.192/96; 77.095/95; 81.123/95; 85.155/138; 89.208/182 |
| R2 | 120.054/73; 123.544/116; 124.113/116; 125.607/116; 126.820/182; 129.164/96; 133.252/96; 137.105/95; 141.122/95; 145.122/138; 149.239/182 |
| R3 | 180.064/73; 183.447/116; 185.015/116; 185.437/116; 186.179/182; 189.580/96; 193.305/96; 197.093/95; 201.131/95; 205.046/138; 209.660/182 |
| R4 | 240.046/73; 243.271/116; 244.308/116; 245.435/116; 246.176/182; 249.479/96; 253.132/96; 257.105/95; 261.158/95; 265.047/138; 269.036/182 |
| R5 | 300.056/73; 303.465/116; 304.527/116; 305.529/116; 306.299/182; 309.220/96; 313.239/96; 317.072/95; 321.092/95; 325.171/138; 329.711/182 |
| R6 | 360.047/73; 363.341/116; 364.191/116; 365.405/116; 367.243/182; 369.111/96; 373.160/96; 377.159/95; 381.164/95; 385.177/138; 389.063/182 |
| R7 | 420.025/73; 423.397/116; 424.277/116; 425.347/116; 426.626/182; 429.538/96; 433.168/96; 437.126/95; 441.096/95; 445.085/138; 449.210/182 |
| R8 | 480.046/73; 483.062/116; 484.220/116; 485.680/116; 487.056/182; 489.291/96; 493.081/96; 497.147/95; 501.144/95; 505.061/138; 509.578/182 |

88/88 个按键均有记录；lateness min/median/max 为
24.522/176.135/1242.877 ms。每轮第 35 s 的生命周期检查均为
`PAUSED/STATUS_BG`。

## 3. 问题 1：ServiceA 周期形态

### 3.1 口径

由于操作高峰时 smaps 读取变慢，派生分析不用 collector 的名义 stage，全部按
实际 epoch 重分 60 s 轮次。每轮用观测到的 glibc excursion 定义：

- 上升沿起点：达到 excursion 10% 前的最后一个点；
- 峰值带入口：首次达到 excursion 90% 的点；
- 回落起点：峰后首次跌出 90% 峰值带的点；
- 谷底：回落起点后至该轮结束的第一个最小值。

这些沿时长受实际采样间隔限制，是离散采样近似值。

### 3.2 各轮形态

时间均为相对正式窗口起点的实际秒数，内存单位为 kB。

| 轮 | 点数 | 起点 t/value | 峰值 t/value | 峰值最近前序键 | 回落起点 t/value | 谷底 t/value | 轮末 | 上升沿/峰值带/下降沿 (s) |
|---|---:|---|---|---|---|---|---:|---|
| R1 | 57 | 59.023 / 3464 | 66.241 / 13272 | `182` 后 0.097 s | 71.671 / 3512 | 90.286 / 3476 | 3476 | 4.833 / 5.430 / 18.616 |
| R2 | 54 | 119.547 / 3476 | 124.498 / 10068 | `116` 后 0.385 s | 130.575 / 3844 | 150.238 / 3824 | 3824 | 3.567 / 6.077 / 19.663 |
| R3 | 54 | 179.738 / 3824 | 182.928 / 12612 | `73` 后 2.864 s | 185.774 / 4564 | 191.519 / 3992 | 4048 | 1.682 / 2.846 / 5.744 |
| R4 | 54 | 239.694 / 4048 | 242.827 / 10708 | `73` 后 2.781 s | 246.098 / 6772 | 270.559 / 4032 | 4032 | 3.133 / 3.271 / 24.461 |
| R5 | 58 | 299.648 / 4032 | 302.892 / 8176 | `73` 后 2.836 s | 307.224 / 6248 | 311.390 / 4144 | 4172 | 3.245 / 4.331 / 4.166 |
| R6 | 57 | 359.494 / 4172 | 362.525 / 10392 | `73` 后 2.478 s | 365.253 / 8372 | 384.957 / 4212 | 4212 | 1.695 / 2.729 / 19.703 |
| R7 | 58 | 419.387 / 4212 | 425.166 / 8396 | `116` 后 0.889 s | 430.390 / 4128 | 451.339 / 4064 | 4064 | 5.006 / 5.224 / 20.950 |
| R8 | 56 | 479.824 / 4064 | 483.415 / 10044 | `116` 后 0.353 s | 488.448 / 6820 | 511.087 / 4252 | 4252 | 3.590 / 5.034 / 22.639 |

八轮中位数：上升沿 **3.406 s**、峰值带 **4.682 s**、下降沿
**19.683 s**。峰值均出现在频道列表打开/前三次移动/第一次退出这段序列中：
R3-R6 在 `73` 后，R2/R7/R8 在 `116` 后，R1 在第一次 `182` 后。

逐点序列为
`board_results/product_cyclic_target_probe_20260814/derived/serviceA_timeseries.tsv`；
其中同时保存 nominal sample、actual elapsed、三分类 PD、fault 和系统协变量。

## 4. 问题 2：glibc 与 other-anon 归属

“同刻下降”固定使用 ServiceA glibc 峰值与其后谷底两个时刻；比例只在
glibc 与 other-anon 两类下降量之和内计算，不含 file-backed。`other own range`
则是该轮 other-anon 自身最大值减最小值。

| 轮 | glibc 峰→谷 (kB) | other 同刻下降 (kB) | 两类下降占比 glibc/other | other own range (kB) |
|---|---:|---:|---:|---:|
| R1 | 9796 | 2112 | 82.3% / 17.7% | 2420 |
| R2 | 6244 | 5004 | 55.5% / 44.5% | 5004 |
| R3 | 8620 | 5332 | 61.8% / 38.2% | 5440 |
| R4 | 6676 | 4956 | 57.4% / 42.6% | 4956 |
| R5 | 4032 | 3848 | 51.2% / 48.8% | 3900 |
| R6 | 6180 | 6868 | 47.4% / 52.6% | 6868 |
| R7 | 4332 | 7516 | 36.6% / 63.4% | 7916 |
| R8 | 5792 | 2576 | 69.2% / 30.8% | 2576 |

glibc 峰到谷中位数为 **6212 kB**，范围 4032-9796 kB；other-anon
轮内自身极差中位数为 **4980 kB**，范围 2420-7916 kB。高密度数据表明
两类都存在周期峰谷；上一轮由各 stage 粗粒度峰值形成的
`4032 -> 10888 kB` other-anon“单调上涨”没有在本轮谷底序列中复现。

ServiceA other-anon 在各 glibc 谷底处依次为
4440/4468/4384/4240/4296/4320/4704/4364 kB；相对 P0 的 4300 kB 不单调，
R8 为 `+64 kB`。

## 5. 问题 3：谷底趋势

| 轮 | 谷底 elapsed (s) | glibc 谷底 (kB) | 相对 P0 (kB) | 相对 P0 |
|---|---:|---:|---:|---:|
| R1 | 90.286 | 3476 | +12 | +0.346% |
| R2 | 150.238 | 3824 | +360 | +10.393% |
| R3 | 191.519 | 3992 | +528 | +15.242% |
| R4 | 270.559 | 4032 | +568 | +16.397% |
| R5 | 311.390 | 4144 | +680 | +19.630% |
| R6 | 384.957 | 4212 | +748 | +21.594% |
| R7 | 451.339 | 4064 | +600 | +17.321% |
| R8 | 511.087 | 4252 | +788 | +22.748% |

谷底总体抬升但不是严格单调：R1 接近 P0，R2-R6 连续抬升，R7 回落，R8
再次升至 4252 kB。P1 120 s 静置期为 4252 -> 4248 kB；最终值相对 P0
为 `+784 kB`（+22.63%）。按“P0 ±5%”标签，只有 R1 谷底落在近基线范围。

峰值确实出现在 glibc-heap 分类中，因此不能解释为“峰值从未分配到分类堆”。
但只读 smaps 不能测 ptmalloc bin 空闲字节：`Private_Dirty` 回落只说明这些页在
谷底时已不再作为该分类的私有脏页存在，不能单独区分 bin 驻留、madvise、munmap
或映射生命周期变化。因此本报告不把 4-10 MiB 峰谷差直接写成 trim 可回收字节；
bin 驻留量需要 `malloc_info` 或进程内观测，本产品板边界不允许取得。

## 6. 对照目标

| 目标 | P0 glibc/other (kB) | R1-R8 glibc 峰值 (kB) | P1 glibc 末值 | 同期事实 |
|---|---:|---|---:|---|
| `ServiceH[ServiceK]` | 13252 / 25724 | 13772/14052/13972/14100/14196/14300/14628/14588 | 14120 | 峰值总体抬升，R7-R8 差 40 kB；本轮最大高度 1376 kB |
| `ServiceB` | 3940 / 4440 | 3984/3896/3924/3928/3912/3912/3872/3864 | 3904 | 本组按键下 glibc 最大仅高于 P0 44 kB（1.12%） |
| `ServiceE` | 8772 / 2120 | 8772/8772/8772/8772/8772/8772/8772/8772 | 8772 | glibc 与 other-anon 全程逐点不变 |

## 7. 采集质量、失败与限制

- 660/660 样本、2640/2640 目标行、88/88 按键；字段错误 0、PID `NA` 0、
  PID 变化 0；collector/runner 退出码均为 0。
- collector 报告 555 次 deadline overrun。唯一采样时间轴的相邻间隔
  min/median/max 为 0.614598/0.756541/6.077082 s；106 个间隔 >1.1 s，
  44 个 >2 s，15 个 >3 s。另有 428 个 <0.9 s 的追赶点。
- 实际 wall-clock 重分段后，R1-R8 每轮分别有 57/54/54/54/58/57/58/56 点；
  短峰可能位于最长 6.08 s 的空档内，沿时长不具备严格 1 s 精度。
- 名义 sample stage 在追赶时会偏离 wall clock，本报告及全部派生表均改用
  `epoch_ns - start_ns` 重分段；原始名义字段保留以供复核。
- 本轮只建立 smaps 分类时间序列，没有 `malloc_info`，因此不能量化谷底
  ptmalloc fast/rest/unsorted 驻留，也不对 trim 回收量作推断。

## 8. 恢复现场与文件

收尾时 `ServiceH[ServiceK]` 为 `PAUSED/STATUS_BG`，四个目标 PID 均存活。
板上 `/tmp/product_cyclic_target_probe_20260814` 及三个辅助输出均已删除，
最终检查为 `ALL_PRODUCT_CYCLIC_TMP_ABSENT`。SSH ControlMaster 已关闭。

原始文件：

- `board_results/product_cyclic_target_probe_20260814/raw/timeseries.tsv`
- `board_results/product_cyclic_target_probe_20260814/raw/key_timeline.tsv`
- `board_results/product_cyclic_target_probe_20260814/raw/collection_meta.txt`
- `board_results/product_cyclic_target_probe_20260814/raw/identity_environment.txt`
- `board_results/product_cyclic_target_probe_20260814/raw/all_process_baseline.tsv`
- `board_results/product_cyclic_target_probe_20260814/raw/vk_preflight.txt`
- `board_results/product_cyclic_target_probe_20260814/raw/round_state.log`
- `board_results/product_cyclic_target_probe_20260814/raw/cleanup_evidence.txt`
- `board_results/product_cyclic_target_probe_20260814/raw/cleanup_post_pull.txt`
- 同目录下 collector/runner stdout、start time 与本地目标解析记录

派生文件：

- `derived/serviceA_timeseries.tsv`（逐点时间序列）
- `derived/serviceA_cycle_shape.tsv`
- `derived/serviceA_peak_valley.tsv`
- `derived/serviceA_valley_trend.tsv`
- `derived/serviceA_edge_medians.tsv`
- `derived/target_stage_summary.tsv`
- `derived/pid_segments.tsv`
- `derived/quality.tsv`
- `derived/key_timeline_alias.tsv`

完整文件校验表：
`board_results/product_cyclic_target_probe_20260814/SHA256SUMS`。核心文件哈希：

```text
470ea0c4be1a484ac45205b17a28e64a5fbbcb77efad5417f561d2cf14b800e1  raw/timeseries.tsv
0026c90317747903fdf14bb94754d624b3e1017e4f043f8efef08a9b509b2cbd  derived/serviceA_timeseries.tsv
```
