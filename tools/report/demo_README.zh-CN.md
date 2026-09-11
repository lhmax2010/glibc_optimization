中文 | [English](README.md)

# Tizen glibc 门控 trim Demo

> 英文入口由中文技术文档派生；如有歧义，以中文技术文档为准。

## 这是什么

这是 Tizen glibc（ptmalloc）门控 trim 的冻结 Demo：把可见自动归还当作反信号，先用
M7 确认 allocator 空闲驻留，再要求同目标、同相位的 trim 探针实测收益达到事前固定阈值，
最后只在明确释放相位调用 `malloc_trim(0)`，并把再激活、时延和健康证据作为同一合同
验收。在冻结的 RPI4/Tizen
`glibc-2.40-1.6.armv7l` 矩阵上，现行校准带中心为 50.67% / 52.79%（medium-only / mixed），门控 trim 回收已释放 payload 的约
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
| 分配负载 RSS 绝对值 | mixed `13.015625 → 7.718750 MiB`，下降 `40.696279%`；medium-only `13.152344 → 7.191406 MiB`，下降 `45.322245%`；系统配对净效应分别 `−0.167969 / +5.304688 MiB` | [优化效果一览](docs/demo_report.html#system-effect)、[L1 复算](docs/demo_reproduction_guide_20260901.md#l1-system-before-after) | [三重复摘要](data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)、[逐周期](data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv) |
| 解码 RSS vs none | gst `8.671875 → 6.859375 MiB`，降幅中位 `21.009919%`；系统配对净效应 `+1.855469 MiB`；调用中位 `0.843612 ms`；none RSS 下降 `0`；p99 差 `−1.652834 ms` 对离散 `11.794149 ms`，固定规则未检出 | [优化效果一览](docs/demo_report.html#system-effect)、[L1 复算](docs/demo_reproduction_guide_20260901.md#l1-system-before-after) | [摘要](data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)、[p99](data/raw/system_level_before_after_20260908/accepted_matrix/gst_comparison.json) |

绝对值行沿用 cycle=1、每臂三重复；前值、后值、配对降幅分别取中位，前后中位相减
不一定等于降幅中位。none 的零指进程 RSS，不指系统 MemAvailable。这里只是测试板
量级，非产品收益。[口径](docs/system_level_before_after_20260908.md#13-已验收矩阵合成与优化效果)。

批量释放相位的 `48.9% / 1.36 MiB × 8 进程` 来自 `<TEST_IMAGE_B>` /
`glibc-2.40-2.8`，仅为相容性对照，不属于冻结矩阵
（[证据](data/raw/demo_reproduction_20260901/batch_release_phase.tsv)）。

## 快速上手三条路

1. **离线阅读——分钟级。** 打开 [`docs/demo_report.html`](docs/demo_report.html)。
2. **Host 核验——分钟级。** 必须使用真实 `git clone`（不支持 ZIP/source export），
   运行 `bash tools/reproduce/reproduce.sh`；依赖 Git、Python ≥3.10、Bash/POSIX sh 与
   显式列出的系统命令白名单，
   GBS/RPM/ARM 工具链均为可选项且不构成默认硬门。开发专用覆盖变量与依赖审计见
   [`tools/reproduce/README.md`](tools/reproduce/README.md)。
   须从干净 shell 运行：启动钩子及未导出的函数/别名会在 verify 前以 RC=2 和明确诊断拒绝，
   包括 exec/exit/builtin 遮蔽；
   Environment Modules 用户可按[净化进程命令](tools/reproduce/README.md#default-verify-system-dependencies)运行。
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

### HQ 默认 L2 路径：GBS 构建（alloc_bench 经 held-out 4/4 验证）

三项 ELF 的 GBS 默认路径是真实 `git clone` 后执行
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`。该显式模式需要仓库网络访问、可执行 root
构建的 GBS 环境、buildroot 磁盘空间，耗时也显著长于分钟级 host verify。固定快照
[`gbs_llvm.conf`](config/gbs_llvm.conf) 与
[`glibc-memopt-tools.spec`](packaging/glibc-memopt-tools.spec) 会生成一个同时包含
`alloc_bench`、`gst_loop_decode`、`reclaim_probe` 的 RPM；NVR 与全部哈希按
[`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json) 核对。完整提取命令见
[L2 GBS 小节](docs/demo_reproduction_guide_20260901.md#l2-gbs-build)。四个配置官方仓的包名、
Provides、filelists 零命中结果及 spec 全部 BuildRequires 的独立版本复核见
[`三工具来源声明`](docs/tool_provenance_20260903.md)。

构建自证绑定干净 Git 快照、两个 workflow 脚本、两份 GBS 配置、manifest 与已跟踪 spec。
构建返回后及复制后重新核验 proof 字节，发布时核验原始 GBS 日志哈希。这是本机自记的
完整性检查，**不是签名级远程证明**；`entrypoint_sha256` 表示仓库入口文件字节，不代表
实际调用者。覆盖范围与能力边界见 [workflow 说明](tools/reproduce/README.md#gbs-execution-provenance)。

GBS 产物参与了固定合同 H-V 校准样本，因此该样本本身不能作为独立通过证据。随后由
独立事前 tag 固定、且不参与建带的 GBS-only 四格 held-out 验证 4/4 通过；GBS 为默认
L2 路径（经 held-out 验证），冻结件和固定目录交叉构建为备选。GBS 不提供媒体文件，媒体仍是仓库外的
交付前置。见 [`held-out 报告`](docs/gbs_heldout_validation_20260904.md) 与
[`decision.json`](data/raw/gbs_heldout_validation_20260904/decision.json)。

**held-out 四格只覆盖 alloc_bench。** GBS `gst_loop_decode`、`reclaim_probe` 的 ELF
身份链与 manifest 一致；其板上行为依据是此前 9 月 3 日 rebaseline retry2，现补公开
[`原有 gst 紧凑证据`](data/raw/gbs_rebaseline_20260903/gst_retry2/README.md)，不称额外
held-out 验证。范围详见 [held-out 报告 §7](docs/gbs_heldout_validation_20260904.md#7-workflow-发现与结论)。

显式 `gbs` 在环境不可用、锁超时或 RPM/ELF 缺失时非零退出；必须输出完整核验 bundle
才能 `PASS`。root 属主临时 buildroot 清理失败单列 `gbs-buildroot-residue`，不影响已过门
产物；核验该次具体路径后用 `sudo rm -rf -- <path>` 清理，见
[`构建退出语义`](tools/reproduce/README.md)。

## 仓库地图

- [`docs/`](docs/)：报告与指南；正文为中文，
  [HQ 复现指南](docs/demo_reproduction_guide_20260901.md)是流程权威参考。
- [`tools/`](tools/)：harness、分析器、workflow 与报告生成器。
- [`data/raw/`](data/raw/)：公开紧凑证据。
- `board_results/`：不公开；完整原始件在 host 本地留存，可按请求提供。

## 环境前提与验收带

系统前后对照保留原 21 格，打包不重跑。G4 常驻守护对照堆 PD 下降 `88/0/4 KiB`；
RSS 降幅中位 `0.033659%`（约 `0.03%`，分母是 RSS 而不是堆 PD）。`1899.209517 ms`
包含 gdb/ptrace 注入开销，不是约 1 ms 的释放点钩子代价。trim/none 两臂使用同一已验
哈希二进制，差别为运行时调用，不修改 ELF，二进制体积不变。
[证据与 L1](docs/demo_reproduction_guide_20260901.md#l1-system-before-after)。

延期收尾按授权规则通过，不等于零残留：四个非空 GDB 目录列举后作为已知非阻断残留保留，镜像 Python
目录保留，会话已回到 UID 5001。[处置原文](docs/system_level_before_after_20260908.md#121-实际处置与收尾结果)。

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
