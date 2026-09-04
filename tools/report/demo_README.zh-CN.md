中文 | [English](README.md)

# Tizen glibc 门控 trim Demo

> 英文入口由中文技术文档派生；如有歧义，以中文技术文档为准。

## 这是什么

这是 Tizen glibc（ptmalloc）门控 trim 的冻结 Demo：把可见自动归还当作反信号，先用
M7 确认 allocator 空闲驻留，再要求同目标、同相位的 trim 探针实测收益达到事前固定阈值，
最后只在明确释放相位调用 `malloc_trim(0)`，并把再激活、时延和健康证据作为同一合同
验收。在冻结的 RPI4/Tizen
`glibc-2.40-1.6.armv7l` 矩阵上，现行校准带中心为 51%–53%，门控 trim 回收已释放 payload 的约
80%–85%，调用耗时分档中位为 mixed `1.233269 ms` / medium-only `1.218361 ms`；gst p99
方向按固定比较规则未检出。
这些是机制与量级结果，不是产品内存收益承诺。

## 头条结果

| 对照 | 验收结果 | 报告 | 紧凑证据 |
|---|---|---|---|
| 瞬时释放锚点 | 校准带 mixed `52.794499% ±4.304705 pp`、medium-only `50.669791% ±4.918088 pp`（各 `n=8`，pre-trim heap）；独立 GBS held-out 4/4 通过 | [HTML 摘要](docs/demo_report.html#summary) | [`校准`](data/raw/a_anchor_replication_20260904/decision.json)、[`held-out`](data/raw/gbs_heldout_validation_20260904/decision.json) |
| 门控 valley trim vs none | 已释放 payload 的 `80.18%–85.45%`；调用中位 mixed `1.233269 ms` / medium-only `1.218361 ms`；下一周期 `+1351/+1465 minflt`，`majflt=0` | [S4 效果](docs/demo_report.html#s4) | [`b_cycles.tsv`](data/raw/s4_retention_20260901/b_cycles.tsv)、[`b_cells.tsv`](data/raw/s4_retention_20260901/b_cells.tsv) |
| gst trim vs none | p99 `+6.228611 ms` 对 none 离散 `6.784167 ms`：margin `0.555556 ms`、达门槛 91.8%，`REPORT_ONLY` 未检出；同规则 p50 判可见（`+1.870462` 对 `0.173927 ms`）；`+359 minflt/循环` | [真实并发](docs/demo_report.html#gst) | [`comparison.json`](data/raw/gst_trim_cost_20260901/comparison.json)、[`cycles.tsv`](data/raw/gst_trim_cost_20260901/cycles.tsv) |
| Tizen 原生交叉见证 | 历史 enlightenment 格约 `5.84 MiB` rest、回收 `272/4/4 KiB`；B2 官方 gst `5/5` 回收 `8/16/16/20/16 KiB`，原生 UI 五次验证后 E4′ rest `6019572 B`、回收 `36 KiB`；项目 heap PD 与 Tizen `memps` 逐值一致 | [真实平台进程](docs/demo_report.html#native) | [`B2 格`](data/raw/tizen_native_evidence_b2_20260904/cells_derived.tsv)、[`B2 摘要`](data/raw/tizen_native_evidence_b2_20260904/summary.json)、[`历史摘要`](data/raw/tizen_native_evidence_20260904/summary.json) |

批量释放相位的 `48.9% / 1.36 MiB × 8 进程` 来自 `<TEST_IMAGE_B>` /
`glibc-2.40-2.8`，仅为相容性对照，不属于冻结矩阵
（[证据](data/raw/demo_reproduction_20260901/batch_release_phase.tsv)）。

## 快速上手三条路

1. **离线阅读——分钟级。** 打开 [`docs/demo_report.html`](docs/demo_report.html)。
2. **Host 核验——分钟级。** 必须使用真实 `git clone`（不支持 ZIP/source export），
   运行 `bash tools/reproduce/reproduce.sh`；开发专用覆盖变量见
   [`tools/reproduce/README.md`](tools/reproduce/README.md)。
3. **板上完整复现——小时级。** 满足下列前置与
   [L2 指南](docs/demo_reproduction_guide_20260901.md#l2-prerequisites)后，运行
   `bash tools/reproduce/reproduce.sh board --ip <addr>`。

### L2 硬前置

- RPI4，镜像 BUILD_ID 有意公开为
  `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`；
- 精确 `glibc-2.40-1.6.armv7l`、SDB 4.2.25 参考版本及三重身份门；
- 远端 `id -u=0`、四核 governor 可写、`/opt/usr` 可写；
- 按 [`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json) 取得 SHA 固定的
  ARM/媒体 bundle；媒体获取位置由交付方随交付邮件提供，收到后按清单 SHA-256 核对。

没有内部 bundle 时 board 模式不可启动。媒体资产尚无可再分发 provenance，随包外内部
渠道交付，不进入公开仓库。

### HQ 首选 GBS 构建（held-out 4/4 通过）

三项 ELF 的 GBS 首选路径是真实 `git clone` 后执行
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`。该显式模式需要仓库网络访问、可执行 root
构建的 GBS 环境、buildroot 磁盘空间，耗时也显著长于分钟级 host verify。固定快照
[`gbs_llvm.conf`](config/gbs_llvm.conf) 与
[`glibc-memopt-tools.spec`](packaging/glibc-memopt-tools.spec) 会生成一个同时包含
`alloc_bench`、`gst_loop_decode`、`reclaim_probe` 的 RPM；NVR 与全部哈希按
[`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json) 核对。完整提取命令见
[L2 GBS 小节](docs/demo_reproduction_guide_20260901.md#l2-gbs-build)。四个配置官方仓的包名、
Provides、filelists 零命中结果及 spec 全部 BuildRequires 的独立版本复核见
[`三工具来源声明`](docs/tool_provenance_20260903.md)。

GBS 产物参与了固定合同 H-V 校准样本，因此该样本本身不能作为独立通过证据。随后由
独立事前 tag 固定、且不参与建带的 GBS-only 四格 held-out 验证 4/4 通过；GBS 现为
L2 默认路径，冻结件和固定目录交叉构建为备选。GBS 不提供媒体文件，媒体仍是仓库外的
交付前置。见 [`held-out 报告`](docs/gbs_heldout_validation_20260904.md) 与
[`decision.json`](data/raw/gbs_heldout_validation_20260904/decision.json)。

## 仓库地图

- [`docs/`](docs/)：报告与指南；正文为中文，
  [HQ 复现指南](docs/demo_reproduction_guide_20260901.md)是流程权威参考。
- [`tools/`](tools/)：harness、分析器、workflow 与报告生成器。
- [`data/raw/`](data/raw/)：公开紧凑证据。
- `board_results/`：不公开；完整原始件在 host 本地留存，可按请求提供。

## 环境前提与验收带

唯一机器合同是 [`acceptance_bands.json`](tools/reproduce/acceptance_bands.json)。唯一
确定性数字为 released payload 字节。validity gates 是：回收量 4 KiB 对齐、
`majflt=0`、zram 三项增量为 0、dmesg 零 OOM/LMK。S4 B 容差按每档三重复中位，
mixed 锚定 `81.661264% ±5 pp`、medium-only 锚定 `84.446566% ±5 pp`；`n=3` 只容忍
一个离群。S4 B 与 gst 的释放点 trim 单次 `<5 ms`；S4 A 锚点单列 `<20 ms`，不是
钩子代价数字。

现行 A 锚点校准带由 frozen/GBS 共用：mixed `52.794499% ±4.304705 pp`、medium-only
`50.669791% ±4.918088 pp`，每档合并八次观测。由于 GBS 观测参与建带，它仍只称校准带；
独立通过证据来自之后排除于建带样本的四格 held-out 4/4 PASS，且没有改带。固定合同
H-V 重放取代旧的现行 `n=1` 局限；原始单次观测仍作为历史证据保留。

“同样的数据”正式指：确定性 payload 逐字节一致、容差项落带、validity gates 通过。
固定 seed 不钉 arena 指派；单重复可出现约 1 MiB 台阶，因此回收字节只作带宽参考。

stability-monitor v2 known-alert waiver 覆盖 S4 A 至多两个
`alloc_bench cpu.relative` livedump。实际匹配且完成记录/归档/精确清理/复核才记
`EXPECTED`；未观测记 `REGISTERED/NOT-EVALUATED`。触发理由与窗口可复现，但未做
根因证明。

## 产品启用四门

产品侧必须依次通过四道硬门：**反信号排除 → M7 驻留确认 → 同目标、同相位的 trim
探针实测收益达到事前固定阈值 → 代价预算**。阈值必须在看结果前按目标/相位登记；未实测、
低于阈值或重复不稳定均不启用。M7、`rest`/`unsorted` 和直方图估计不能代替第三门。
带日期定稿和保留的旧三门文字见
[`产品落点建议`](docs/product_landing_recommendation_20260901.md#1-启用门清单)。

## 边界与术语

- 合成代理缺产品候选 M7 live/bin 分解、产品业务时延及其他线程仍分配时的全 arena
  锁停顿直测。
- gst trim 在 NULL 后触发，不是分配热区注入。
- B2 按固定合同重放完成官方 gst `5/5` 和原生 UI 五周期后的 E4′，四个注入间隔为
  `120.122271759–120.142672892 s`；历史 T1 `1/5`、UI `0/1` 与 E1–E3 的
  `119.806876910/119.856460299 s` 偏差继续保留，不被追认成合规。
- M7 驻留量不等于可回收量：`<size>` 估算器在 `15/15` 个严格配对格上未覆盖实测，
  E4′ 对 `36 KiB` 实测给出 `2200–7976 KiB`。它只作诊断，不是量化启用阈值；见
  [`估算器报告`](docs/trimmable_estimator_20260905.md)。
- enlightenment 守护进程虽有约 `5.84 MiB rest`，历史三格只回收 `272/4/4 KiB`，
  真实 UI 活动后的 E4′也只回收 `36 KiB`；这些格上的碎片化驻留收益很小，不外推到
  其他守护进程或相位。
- “p99 未检出”不等于零代价；若另一块板判可见，保留三重复并报告越带 margin，方向
  仍是 `REPORT_ONLY`。
- 产品启用仍须通过反信号排除、M7 驻留确认、同目标实测收益达到事前固定阈值、代价预算
  四道硬门，见
  [落点建议](docs/product_landing_recommendation_20260901.md#1-启用门清单)。
- **retained floor**：释放观察后仍抬高的 Private_Dirty；仅靠 smaps 不能判断 live/bin。
- **nearest-rank**：排序 `n` 个样本后取 `ceil(p×n)`；gst 主样本 50 个时 p99 即最大值。

host 侧路径已脱敏，板端运行路径保留。`demo` 分支是冻结快照：修正先进入 `main`，再切
新快照/标签。
