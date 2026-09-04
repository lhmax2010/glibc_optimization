> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# demo-v2 以来的交付变更对照

- 对照起点：annotated tag `demo-v2` peel 后提交
  `959b4fb1f18327eaeb07f6b34d9055e993b6a2cd`
- 收口源提交：`09075df049c700e9d577c265403e25beabd5023e`
- 交付账务截至：`20f576005b42cbe71ad13a8c8804d31b0cd9da60`
- 范围：三方第三轮复审使用的分类索引；不产生新测量数字，不替代各正式报告
- 复核命令：`git log --reverse --oneline 959b4fb..09075df`

`demo-v2` 是从当时 main 切出的交付快照提交，不是当前 main 的祖先；本表按共同基线后的
main 提交序列列出变化，并把每个提交映射到下述发现项。编号 `A-*` / `GBS-*` 沿用
[`第 2 轮评审闭环`](review_fix_20260903.md#第-2-轮复审与-gbs-闭环)；其余编号在本表中
定义，供第三轮复审逐项引用。

## 1. 评审修复第 2 轮

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| A-1–A-10、GBS-11、GBS-13、GBS-14 | `20ab8c80d7b357254542dd841212ed8d7e7085c8` | 更正分档 trim 中位；统一 manifest 选 SHA；补可复现构建、手工/workflow 一致性、delivery identity、GBS spec 与 host 检查 | [`闭环逐项表`](review_fix_20260903.md#第-2-轮复审与-gbs-闭环) |
| A-1、A-5、A-10、GBS-12 | `a6cf8fccc8478b5f06573d4189c5f7841fb55c5b` | 登记实际 GBS RPM/ELF 身份，更新派生 HTML 与 source marker | [`GBS 构建记录`](../data/raw/gbs_package_20260903/README.md) |
| R2-META | `c44a8a2d4287a26fd6e93276f65b6ea5388dcab2` | 把 A-1–A-10、GBS-11–GBS-14 的最终提交映射回填到闭环记录 | [`评审修复记录`](review_fix_20260903.md) |

## 2. GBS 化

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| GBS-11–GBS-14 | `20ab8c80d7b357254542dd841212ed8d7e7085c8`、`a6cf8fccc8478b5f06573d4189c5f7841fb55c5b` | 新增单 RPM 三工具 spec，钉住 Unified/Base snapshot，记录 buildroot、NVR、RPM/ELF SHA；当时状态为“待板上重基线” | [`packaging README`](../packaging/README.md)、[`build_summary.json`](../data/raw/gbs_package_20260903/build_summary.json) |

## 3. 工具来源声明与 clone 身份回归

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| SRC-0 | `e8fe1cd4fe35558b2aa1c913ee0b799755cbc819` | 修复 main 普通 clone 无法解析交付标签时的 verify 硬失败；`report_only` 改为提示且不计失败 | [`reproduce.sh`](../tools/reproduce/reproduce.sh) |
| SRC-1–SRC-3 | `f0549432073f5b8a5dd6ea39bc532d1203a0f4d9` | 解析四个配置仓，按包名/Provides/filelists 搜索三工具并得到零命中；复核 spec BuildRequires 与官方源；发布自研来源声明 | [`来源报告`](tool_provenance_20260903.md)、[`公开摘要`](../data/raw/tool_provenance_20260903/summary.json) |
| SRC-0-TEST | `0aa1a3d09959b4b1bc37cf31524a7c1e8edd8f8f` | 用真实干净 clone 覆盖 main 的 `REPORT_ONLY` 与交付快照的 `required` 身份语义 | [`host 测试`](../tools/reproduce/test_host.py) |

## 4. GBS 重基线与 A2 锚点裁决

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| RB-D1–RB-D5、RB-A-OUT | `01f9bb651e04ba3b0ad9a0d93cf5d044d51da4c8` | GBS workflow 首轮完整矩阵发现 A/mixed 旧带外；闭环远端 SHA、livedump、stdin、验收退出码和即时停止五类执行器缺陷，保持停止门 | [`GBS 重基线 §3`](gbs_rebaseline_20260903.md#3-workflow-执行记录与一等发现) |
| A2-HV、GBS-PROMOTE | `840b9572ac8ce75b9615141fbdf46b098cd035d4` | 预登记 12 格 frozen/GBS 交替复测命中 H-V；acceptance 升 v4 共同带，归档矩阵复判通过，GBS 转正为 HQ 首选 L2 | [`A2 报告`](a_anchor_replication_20260904.md)、[`裁决 JSON`](../data/raw/a_anchor_replication_20260904/decision.json) |

## 5. Tizen 原生实证 B / B2

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| B-T1、B-E1–B-E4、B-INT | `dff8ae677d38f51180fbb43c513319d464f74079` | 用 Tizen enlightenment、`memps`、`gst-launch-1.0` 与官方仓库 gdb 建立交叉见证；保留 T1 `1/5`、E4 `0/1` 和两个 `<120 s` 缺口；确认 M7 rest 不等于可回收量 | [`原生实证 §3–§4`](tizen_native_evidence_20260904.md#3-执行结果) |
| B2-T1、B2-E4、B2-INT | `a35413df78f22d68d9eaac2ea59e807005c7f2c2` | 新预登记补齐官方 GST `5/5`、原生应用活动 `5/5` + E4′ `1/1`、四个 `≥120 s` 间隔，并保留旧格不追认 | [`B2 结果`](tizen_native_evidence_20260904.md#7-b2-补跑结果2026-09-05)、[`B2 摘要`](../data/raw/tizen_native_evidence_20260905/summary.json) |

## 6. 可回收估算器

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| EST-1–EST-4 | `a35413df78f22d68d9eaac2ea59e807005c7f2c2` | 新增 `<size>` 整页上下界估算器和验证器；严格配对 `15/15` 不覆盖实测，方向也不一致，裁决为仅诊断、不可作量化启用门 | [`估算器报告`](trimmable_estimator_20260905.md)、[`validation.tsv`](../data/raw/trimmable_estimator_20260905/validation.tsv) |

## 7. demo-v3 前收口

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| CLOSE-1 | `09075df049c700e9d577c265403e25beabd5023e` | 产品启用合同由旧三门定稿为四门，新增“同目标、同相位 trim 探针实测收益达到预登记阈值”，旧文字保留带日期追注 | [`落点建议 §1`](product_landing_recommendation_20260901.md#1-启用门清单) |
| CLOSE-2 | `09075df049c700e9d577c265403e25beabd5023e` | Demo 合同纳入 GBS 首选 L2、A 锚点 v4 与 Tizen 原生 B/B2；HTML 新增四门章节 | [`Demo 合同`](demo_package_20260902.md#delivery-contracts)、[`HTML 决策门`](demo_report.html#decision-gate) |
| CLOSE-3 | `09075df049c700e9d577c265403e25beabd5023e` | HTML 与双语模板边界新增守护进程碎片化驻留收益微小、估算器不可用两条；delivery ref 预置为 `demo-v3` | [`HTML 边界`](demo_report.html#boundaries)、[`中文模板`](../tools/report/demo_README.zh-CN.md)、[`English template`](../tools/report/demo_README.md) |
| CLOSE-META | `accd86b38516939fe9b50111dca898fd1fadc69c` | 新增本变更索引并把 demo-v3 收口写入时间线 | [`INDEX`](INDEX.md) |
| CLOSE-HTML | `20f576005b42cbe71ad13a8c8804d31b0cd9da60` | 以包含全部 HTML 输入的 `09075df` 为父源提交，单独冻结 source marker 与逐字节派生 HTML | [`source marker`](../tools/report/source_commit.txt)、[`HTML`](demo_report.html) |

## 8. 提交覆盖核对

下列 13 个 main 提交构成 `demo-v2..20f5760` 的完整非合并提交清单，均已在上表出现：

```text
20ab8c8 fix(review): close round-2 A1-A10 and add GBS package
a6cf8fc build(gbs): record A10/GBS-12 artifacts and report
c44a8a2 docs(review): record round-2 A1-A10 GBS-11-14 commits
e8fe1cd fix(reproduce): tolerate unavailable delivery tag on main
f054943 docs(provenance): audit Tizen repos for demo tools
0aa1a3d test(reproduce): exercise full clone identity semantics
01f9bb6 fix(reproduce): stop on failed GBS board acceptance
840b957 board: rebaseline A anchors and promote GBS path
dff8ae6 Add Tizen native trim cross-witness evidence
a35413d evidence: close native B2 gaps and validate trim estimator
09075df docs(demo): finalize four-gate delivery contract
accd86b docs(demo): index changes since demo-v2
20f5760 build(report): freeze demo-v3 source provenance
```

本文件的最终发布提交不自写自身 SHA；它只完善上述已知提交的索引，不承载新的技术或
测量变更。最终边界以 `demo-v3^{}` 和 `git log --reverse --no-merges
959b4fb..demo-v3^{}` 复核，避免循环自引用。

第三轮复审应以 `demo-v3^{}` 的 peel 后提交为最终快照身份，并分别核验：host verify
required 模式、双语 README/INDEX 链接、HTML source-marker byte-cmp 和脱敏扫描。各实验
数字仍以链接的正式报告与公开 TSV/JSON 为唯一事实源。
