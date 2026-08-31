> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# glibc 内存优化 — 板上试点 A/B 矩阵（Batch 1）

- 依据：设计文档 v2.1 + 板上盘点（`docs/board_inventory_run_report.md`，2026-07-08，rpi4/armv7l，Tizen 11.0 Unified）
- 定位：**管线验证轮**——验证 systemd drop-in 注入、度量流程、杠杆生效性；收益数字不代表 TV 平台
- 协变量（本板）：`overcommit_memory=0`（Rss 为有效指标）、THP 不存在（L13/hugetlb 类停放）

## 1. 目标进程选择（来自盘点 TSV）

### 实验组（非 secure × 多线程 —— L1/L2 的机制敏感人群）

| service | pid | 线程 | Rss(kB) | 选择理由 |
|---|---:|---:|---:|---|
| ServiceR | 413 | 12 | 4228 | 非 secure 中线程数最高，Rss 第二 |
| AppV | 751 | 9 | 2892 | 用户会话侧多线程代表 |
| ServiceS | 408 | 8 | 2208 | 中等线程 + 中等 Rss |
| pass | 802 | 8 | 1616 | 多线程小 Rss，观察下限 |
| pulseaudio | 505 | 5 | 2784 | 有实时路径的服务，兼做性能敏感哨兵 |

### 阴性对照组（secure —— 实证 T2 门控）

| service | pid | AT_SECURE | 用途 |
|---|---:|---:|---|
| ServiceV | 439 | 1 | 注入与实验组完全相同的 env，预期**零变化** — 把 T2 的源码结论变成实测证据 |

### 停放（本轮不动）

- esd / sdbd / media-server / net-config 等 secure 服务：Plan B（mallopt）范畴，TV 阶段处理；sdbd 另有实操风险（它是 sdb 通道本身）。
- 单线程进程（systemd、dbus-daemon 等）：L1/L2 无意义；L3/L11 留给 Batch 2。

## 2. 配置格（每 service 4 格）

| 格 | GLIBC_TUNABLES | 说明 |
|---|---|---|
| C0 | （无） | 基线 |
| C1 | `glibc.pthread.stack_cache_size=1048576` | L1 单独 |
| C2 | `glibc.malloc.arena_max=2` | L2 单独 |
| C3 | `glibc.pthread.stack_cache_size=1048576:glibc.malloc.arena_max=2` | L1+L2 组合 |

阴性对照 ServiceV 只跑 C0 与 C3 两格。

总计：5×4 + 1×2 = 22 格。

## 3. 度量协议（按 v2.1 §6 裁剪到板上）

- 注入方式：`/etc/systemd/system/<svc>.service.d/memopt.conf` 写 `[Service] Environment=GLIBC_TUNABLES=...`，`daemon-reload` + `restart`。
- 稳态定义：restart 后等 60 s，再以 15 s 间隔采 3 次 `smaps_rollup`（Rss、Pss），取中位数。
- 生效性验证（每格必做）：
  - E1：`/proc/<pid>/environ` 中确认 GLIBC_TUNABLES 字符串存在；
  - E2（L2 归因辅助）：统计 `/proc/<pid>/maps` 中匿名段里按 1 MiB 对齐、大小 ≤1 MiB 的 heap 型区域数量作为二级 arena 近似计数，C2/C3 相对 C0 应下降或持平（尽力而为指标，不作为验收门）。
  - E3（阴性对照）：ServiceV 的 C3 格必须满足 E1 通过（env 在）且 Rss/Pss 与 C0 中位数差 < 噪声带（±3%）——这才算 T2 实证成立。
- 噪声带标定：C0 基线本身重启 3 次、每次采 3 样，先得出每个 service 的自然波动，后续格的差值小于该波动带则记 NO-EFFECT。
- 性能哨兵（轻量）：本轮不跑完整 benchmark；仅对 pulseaudio 在每格做一次 `pactl list sinks short` 响应时延粗测 + 重启后 journal 无 xrun 告警，异常即标红。
- 全程记录 `date`、`uptime`、`free`，避免与系统级波动混淆。

## 4. 完成判据与出口

- 22 格全部有数据（含 NO-EFFECT），E1 全通过，E3 成立 → Batch 1 完成。
- 产出交我方做裁决：哪些杠杆在板上有可测效果、E2 是否可用、噪声带多大——这些决定 Batch 2（L3/L4/L11/L12）的格设计与 TV 阶段的样本量。
- 实验结束必须删除所有 drop-in 并 restart 恢复原状，末尾用盘点脚本复扫一遍确认零 LIVE 命中。
