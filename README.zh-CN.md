中文 | [English](README.md)

# Tizen glibc 门控 trim Demo

> 英文入口由中文技术文档派生；如有歧义，以中文技术文档为准。

## 这是什么

这是 Tizen glibc（ptmalloc）内存优化 Demo 的冻结交付包：把可见自动归还当作反信号，
先用 M7 确认 allocator 空闲驻留，再只在明确释放相位调用 `malloc_trim(0)`，并把回收、
再激活、时延和健康证据作为同一合同验收。在冻结的 RPI4/Tizen glibc 2.40 矩阵上，
机制锚点约为 50%，门控 trim 回收已释放 payload 的约 80%–85%、调用中位约 1.2 ms，
GStreamer 业务 p99 按预登记门未检出可见代价。这些是机制与量级结果，不是产品内存
收益承诺。

## 头条结果

| 对照 | 冻结结果 | 报告 | 紧凑证据 |
|---|---|---|---|
| 新镜像瞬时释放锚点 | mixed `51.07%`；medium-only `50.39%` | [HTML 摘要](docs/demo_report.html#summary) | [`a_cells.tsv`](data/raw/s4_retention_20260901/a_cells.tsv) |
| 门控 valley trim vs none | 回收已释放 payload 的 `80.18%–85.45%`；调用中位约 `1.2 ms`；下一周期 `+1351/+1465 minflt`，`majflt=0` | [S4 效果](docs/demo_report.html#s4) | [`b_cycles.tsv`](data/raw/s4_retention_20260901/b_cycles.tsv)、[`b_cells.tsv`](data/raw/s4_retention_20260901/b_cells.tsv) |
| GStreamer trim vs none | 重复中位 p99 `+6.229 ms`，低于 none 重复离散 `6.784 ms`；按预登记门未检出 | [真实并发](docs/demo_report.html#gst) | [`comparison.json`](data/raw/gst_trim_cost_20260901/comparison.json)、[`cycles.tsv`](data/raw/gst_trim_cost_20260901/cycles.tsv) |

## 快速上手三条路

1. **离线阅读——分钟级。** 打开
   [`docs/demo_report.html`](docs/demo_report.html)。它是单文件报告，图表全部由证据生成
   并以内联 SVG 嵌入，无 CDN、无外部图片。
2. **Host 核验——分钟级。** 在仓库根目录运行：

   ```sh
   bash tools/reproduce/reproduce.sh
   ```

   默认 `verify` 模式会运行全部公开 L1 复算与逐字节比较、重建 HTML、检查链接；任一
   失败都返回非零。
3. **板上完整复现——小时级。** 准备 RPI4、
   `BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`、glibc 2.40、
   SDB 和带 SHA 的内部 ARM/媒体产物包，然后运行：

   ```sh
   bash tools/reproduce/reproduce.sh board --ip <addr>
   ```

   执行前阅读 [L2 指南与前置](docs/demo_reproduction_guide_20260901.md#l2-prerequisites)。
   判板只认三重身份门，不认地址。

## 仓库地图

- [`docs/`](docs/)：报告与指南；技术正文为中文，
  [HQ 复现指南](docs/demo_reproduction_guide_20260901.md)是流程权威参考。
- [`tools/`](tools/)：benchmark harness、分析器、报告生成器和一键 workflow。
- [`data/raw/`](data/raw/)：复算全部公开 Demo 数字所需的脱敏紧凑证据。
- `board_results/`：不公开入库；完整板上原始件保留在本地，可由项目 owner 按请求提供。

## 环境前提与验收带

唯一机器可读合同是
[`acceptance_bands.json`](tools/reproduce/acceptance_bands.json)。确定性项固定为：payload
字节、回收量 4 KiB 对齐、`majflt=0`、zram 三项增量为 0、dmesg 零 OOM/LMK。跨批次量
按预登记容差带：S4 B 以每档三重复中位按 `80% ±5 pp` 验收；S4 B 与 GStreamer 的
释放点 trim 单次 `<5 ms`；S4 A 锚点另按 `<20 ms`，且不作为钩子代价数字。

stability-monitor v2 的首条预期告警登记是：S4 A 的 `alloc_bench` 最多产生两个
`cpu.relative` livedump。匹配时记 `EXPECTED`，但不是忽略；仍必须记录、归档、按精确
路径清理并复核。未登记且可归因我方的告警仍为失败。

## 边界声明

- 合成代理没有给出产品候选的 M7 live/bin 分解、产品业务时延，也没有直接测量其他
  线程仍在分配时的全 arena 锁停顿分布。
- GStreamer trim 在 pipeline 进入 NULL 后触发；它测的是释放点与下一循环后效，不是
  把 trim 注入分配热区。
- “p99 未检出”**不等于零代价**；它只表示冻结的三重复结果没有越过预登记的 none
  重复离散门。
- 固定 seed 不钉 arena 指派；单重复可出现约 1 MiB 页台阶，因此回收字节不是确定性项，
  协议使用三重复中位。
- 产品侧启用仍关闭，直到反信号排除、M7 驻留确认、代价预算三道硬门全部通过。见
  [产品侧落点建议](docs/product_landing_recommendation_20260901.md#1-启用门清单)。

`demo` 分支是冻结快照。任何修正先进入 `main`，再切新快照并递增 `demo-vN` 标签；禁止
直接在本分支开发。
