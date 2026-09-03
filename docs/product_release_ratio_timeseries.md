> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# 产品板目标释放比例只读时间序列

采集日期：2026-08-14（host，Asia/Shanghai）  
板端采集窗口：2026-08-13 23:19:07.737833050 - 23:29:06.862798574（板端 `-0700`）  
通道：SSH root、无 PTY；采集脚本经 `ssh ... 'sh -s'` stdin 注入。未推送二进制。

## 1. 身份门与环境

身份门通过，原文为：

```text
IDENTITY_OK
kernel=6.12.60
arch=armv7l
PRETTY_NAME="<PRODUCT_IMAGE>"
BUILD_ID=<PRODUCT_BUILD_ID>
glibc-2.40-1.12.armv7l
MemTotal:        1599416 kB
MemAvailable:    1045220 kB
Filename                                Type        Size       Used       Priority
/dev/zram0                              partition   1039320    95480      -2
zram_mm_stat=92983296 23737405 34074624 0 38830080 2 0 17 33 0 0 1310528
overcommit=1
```

内核串不含 `rpi4`，系统标识含 `<PRODUCT_IMAGE>`，架构为 `armv7l`。采集期间
`MemAvailable` 范围为 993844-1060328 kB，zram 已用范围为
79504-92816 kB。

## 2. 方法与完整性

分类口径沿用既有 `parse_smaps.pl`：`[heap]` 加上起始地址按 1 MiB 对齐、
长度不超过 1 MiB 的匿名 `rw-p` 段计入 `glibc-heap`；其余匿名可写段计入
`other-anon`；其他段计入 `file-backed`。每段累计 `Private_Dirty`。

正式采集每 2 秒一次，共 300 个时间点、10 个目标、3000 行。每行同时记录
三分类 Private Dirty、`minflt`/`majflt`、`MemAvailable` 和 zram。完整性结果：

| 项 | 原始值 |
|---|---:|
| 请求时间点 | 300 |
| 数据行 | 3000 |
| 字段数不为 17 的行 | 0 |
| 每目标行数 | 300 |
| `PID=NA` 行 | 3 |
| 实际总时长 | 599.125 s |
| deadline overrun | 2 |
| 相邻采样间隔 min / median / max | 1.429136 / 2.000110 / 2.817370 s |
| 大于 2.1 s 的相邻间隔 | 1 |

一次 2.817 s 延迟后下一间隔为约 1.43 s，绝对 deadline 追赶完成；未丢时间点。

形态分类采用本任务门槛：极差小于基线 10% 为“平缓型”；存在段内峰值到
后续谷值下降至少基线 10% 为“锯齿型”；达到 10% 极差但没有该类下降为
“阶梯型”。PID 变化处强制分段，不跨进程计算跌落。

## 3. 目标与基线

按 S1 全进程画像选择当前 glibc 堆最大的前 9 个进程，再加入指定目标
`ServiceD`；因此当前排名第 10 的 `ServiceF` 未进入 10 个名额。

| 当前排名 | 目标 | PID | exe | glibc heap PD (kB) | other anon PD (kB) | file-backed PD (kB) |
|---:|---|---:|---|---:|---:|---:|
| 1 | `AppProcD` | 424 | `/usr/bin/ServiceI` | 12592 | 18620 | 5140 |
| 2 | `ServiceE` | 404 | `/usr/bin/wrt` | 7804 | 2888 | 7800 |
| 3 | `AppProcB` | 896 | `/usr/bin/ServiceH` | 6056 | 11768 | 6416 |
| 4 | `ServiceH` | 2869 | `/usr/bin/ServiceH` | 4100 | 4004 | 3040 |
| 5 | `cynara` | 205 | `/usr/bin/cynara` | 1652 | 1032 | 212 |
| 6 | `AppProcA` | 2724 | `/usr/bin/ServiceH` | 1212 | 3644 | 3732 |
| 7 | `systemd` | 1 | `/usr/lib/systemd/systemd` | 1056 | 164 | 440 |
| 8 | `enlightenment` | 258 | `/usr/bin/enlightenment` | 792 | 888 | 3036 |
| 9 | `buxton2d_worker` | 229 | `/usr/sbin/buxton2d` | 760 | 28 | 440 |
| 34 | `ServiceD` | 1037 | `/opt/usr/apps/AppF/bin/ServiceD` | 180 | 1740 | 3224 |

指定的五个目标均已包含。这里的基线来自 23:10 的 S1 画像；正式序列从
23:19 开始，因此正式首点可能已经高于 S1 基线。

## 4. 操作日志

| 板端时间 | 动作 | 原始结果 |
|---|---|---|
| 23:19:07-23:20:17 | 首段静置 | 板端实测约 69.5 s；host 调度等待配置为 65 s，无应用动作 |
| 23:20:17.293 | 打开频道列表 | `successfully launched pid = 2869`，随后 `running` |
| 23:20:42.783 | 关闭频道列表 | `Terminate appId`，随后 `not running` |
| 23:21:02.883 | 启动内容浏览器 | `successfully launched pid = 3988`，紧接着 `not running` |
| 23:21:38.052 | 内容浏览器返回检查 | `App isn't running` |
| 23:21:58.246 | 启动 AppUIF | `successfully launched pid = 1025`，紧接着 `not running` |
| 23:22:33.644 | AppUIF 返回检查 | `App isn't running` |
| 23:22:33-23:29:05 | 末段静置 | 约 392 s，无应用动作 |

频道切换未执行：板上没有已签名的按键/遥控注入命令；虽有 `/dev/uinput`，
但新增注入器违反本任务“不推送二进制”的边界。内容浏览器和 AppUIF 均
在启动请求后立即退出，因此没有把它们记为成功的内容浏览操作。

## 5. 峰谷分析

`ServiceH` 在频道列表启动时发生生命周期变化，故分成两个 PID 段。
PID 719 不在 S1 基线中，其门槛使用该段第一个有效样本 3384 kB。

| 目标 | PID | 有效点 | 基线 (kB) | min | max | 极差 (kB) | 极差/基线 | >=10% 跌落 | 形态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `AppProcD` | 424 | 300 | 12592 | 12592 | 12684 | 92 | 0.73% | 0 | 平缓型 |
| `ServiceE` | 404 | 300 | 7804 | 7804 | 7804 | 0 | 0.00% | 0 | 平缓型 |
| `AppProcB` | 896 | 300 | 6056 | 6572 | 6860 | 288 | 4.76% | 0 | 平缓型 |
| `ServiceH` | 2869 | 35 | 4100 | 4100 | 4100 | 0 | 0.00% | 0 | 平缓型 |
| `ServiceH` | 719 | 262 | 3384 | 3384 | 3968 | 584 | 17.26% | 0 | 阶梯型 |
| `cynara` | 205 | 300 | 1652 | 1648 | 1652 | 4 | 0.24% | 0 | 平缓型 |
| `AppProcA` | 2724 | 300 | 1212 | 1212 | 1216 | 4 | 0.33% | 0 | 平缓型 |
| `systemd` | 1 | 300 | 1056 | 1124 | 1148 | 24 | 2.27% | 0 | 平缓型 |
| `enlightenment` | 258 | 300 | 792 | 888 | 2744 | 1856 | 234.34% | 1 | 锯齿型 |
| `buxton2d_worker` | 229 | 300 | 760 | 836 | 1212 | 376 | 49.47% | 0 | 阶梯型 |
| `ServiceD` | 1037 | 300 | 180 | 180 | 588 | 408 | 226.67% | 0 | 阶梯型 |

唯一达到门槛的跌落事件为：

| 目标 | PID | 峰值时间 | 谷值时间 | 峰值→谷值 | 占基线 | 与操作关系 |
|---|---:|---|---|---:|---:|---|
| `enlightenment` | 258 | 23:20:23.767 | 23:28:17.755 | 2744→2624 kB（120 kB） | 15.15% | 峰值出现在频道列表打开后 6.47 s；谷值位于末段静置，距最近操作超过 15 s |

频道列表打开时，`enlightenment` 从 888 kB 上升到 2744 kB、
`ServiceD` 从 180 kB 上升到 588 kB；后者在剩余窗口维持 588 kB，
没有达到 10% 基线的后续下降。30 秒聚合的三分类完整序列见原始文件清单。

## 6. PID 变化与限制

- `ServiceH` PID 2869 在 sample 35（23:20:17.773）变为不可读，
  sample 35-37 共 3 行 `NA`；sample 38 起同名目标解析为 PID 719。
  该切换与频道列表启动返回 PID 2869 同时发生。PID 719 与 2869 的数据未拼接。
- 同名 `ServiceH` 由 `pgrep -x` 跟踪；进程退出后选择当前第一个同名 PID，
  因此它表示同名 loader 槽位的连续观察，不表示同一进程身份。
- 频道切换、页面内浏览和人工遥控动作没有可用的只读自动化入口，未执行。
- 内容浏览器和 AppUIF 不能维持运行，故本次代表性负载主要由频道列表
  打开/关闭及其后静置构成。
- `Private_Dirty` 的 1 MiB 匿名段规则是 glibc arena 代理，不等同于
  allocator 内部“已释放字节”；本任务只报告代理时间序列。
- 板端时钟与 host 时钟约有 10 s 偏差；事件对应统一使用板端时间。

## 7. 原始文件

- `board_results/product_release_ratio_timeseries_20260814/raw/timeseries.tsv`
  （3000 行正式原始序列；SHA-256
  `0939ac419365971117b2ddbf6720339d92de175ade771bad344dd20729d63af5`）
- `board_results/product_release_ratio_timeseries_20260814/derived/summary_30s.tsv`
  （每目标 30 s 聚合：中位数、min、max）
- `board_results/product_release_ratio_timeseries_20260814/derived/peak_valley.tsv`
- `board_results/product_release_ratio_timeseries_20260814/derived/drop_events.tsv`
- `board_results/product_release_ratio_timeseries_20260814/derived/pid_changes.tsv`
- `board_results/product_release_ratio_timeseries_20260814/raw/all_process_baseline.tsv`
- `board_results/product_release_ratio_timeseries_20260814/raw/targets.tsv`
- `board_results/product_release_ratio_timeseries_20260814/raw/operations.log`
- `board_results/product_release_ratio_timeseries_20260814/raw/identity_environment.txt`
- `board_results/product_release_ratio_timeseries_20260814/raw/collection_meta.txt`
- `board_results/product_release_ratio_timeseries_20260814/raw/cleanup_evidence.txt`

## 8. 恢复现场

收尾复核原文：

```text
AppC: not running
AppA: not running
AppE: not running
TMP_AFTER
TMP_ABSENT
IDENTITY_POST
6.12.60
armv7l
PRETTY_NAME="<PRODUCT_IMAGE>"
BUILD_ID=<PRODUCT_BUILD_ID>
CLEANUP_DONE
```

板上 `/tmp/product_release_ratio_20260814` 已删除，SSH ControlMaster 已关闭。
未安装包、未推送二进制、未注入调试器、未重启 service、未修改配置。
