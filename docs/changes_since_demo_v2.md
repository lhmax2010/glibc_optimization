> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# demo-v2 以来的交付变更对照

- 对照起点：annotated tag `demo-v2` peel 后提交
  `959b4fb1f18327eaeb07f6b34d9055e993b6a2cd`
- 收口源提交：`09075df049c700e9d577c265403e25beabd5023e`
- 交付账务截至：`e8be0e9652806eef1772dc8dd346770a38551b9d`
- `demo-v3 → demo-v4`：仅修复交付身份测试 fixture 的分支假设并新增三形态远端交付前自检；无测量、验收带或技术结论变化
- `demo-v4 → demo-v5`：闭合第三轮终审 A 段，并以事前 tag 固定、未参与建带的 GBS-only held-out 四格独立关闭 V4-1；随后只做交付措辞、日期路径与快照身份收口
- 范围：三方第三轮复审使用的分类索引；不产生新测量数字，不替代各正式报告
- 复核命令：`git log --reverse --oneline 959b4fb..e8be0e9`

`demo-v2` 是从当时 main 切出的交付快照提交，不是当前 main 的祖先；本表按共同基线后的
main 提交序列列出变化，并把每个提交映射到下述发现项。编号 `A-*` / `GBS-*` 沿用
[`第 2 轮评审闭环`](review_fix_20260903.md#第-2-轮复审与-gbs-闭环)；其余编号在本表中
定义，供第三轮复审逐项引用。

证据等级、验收聚合和路径优先级的现行裁决见
[`PM 裁决台账`](pm_decisions.md)；本文件只索引对应代码、文档与证据提交。

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
| A2-HV、GBS-CALIBRATION | `840b9572ac8ce75b9615141fbdf46b098cd035d4` | 12 格 frozen/GBS 固定合同重放命中 H-V 并形成 v4 校准带；终审指出 GBS 观测参与建带，故撤回独立通过与首选路径结论，等待 held-out 验证 | [`A2 报告`](a_anchor_replication_20260904.md)、[`裁决 JSON`](../data/raw/a_anchor_replication_20260904/decision.json) |

## 5. Tizen 原生实证 B / B2

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| B-T1、B-E1–B-E4、B-INT | `dff8ae677d38f51180fbb43c513319d464f74079` | 用 Tizen enlightenment、`memps`、`gst-launch-1.0` 与官方仓库 gdb 建立交叉见证；保留 T1 `1/5`、E4 `0/1` 和两个 `<120 s` 缺口；确认 M7 rest 不等于可回收量 | [`原生实证 §3–§4`](tizen_native_evidence_20260904.md#3-执行结果) |
| B2-T1、B2-E4、B2-INT | `a35413df78f22d68d9eaac2ea59e807005c7f2c2` | 固定合同重放补齐官方 GST `5/5`、原生应用活动 `5/5` + E4′ `1/1`、四个 `≥120 s` 间隔，并保留旧格不追认；原始纳秒时间戳确认执行日为 2026-09-04 | [`B2 结果`](tizen_native_evidence_20260904.md#7-b2-补跑结果实际板上执行日-2026-09-04)、[`B2 摘要`](../data/raw/tizen_native_evidence_b2_20260904/summary.json) |

## 6. 可回收估算器

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| EST-1–EST-4 | `a35413df78f22d68d9eaac2ea59e807005c7f2c2` | 新增 `<size>` 整页上下界估算器和验证器；严格配对 `15/15` 不覆盖实测，方向也不一致，裁决为仅诊断、不可作量化启用门 | [`估算器报告`](trimmable_estimator_20260905.md)、[`validation.tsv`](../data/raw/trimmable_estimator_20260905/validation.tsv) |

## 7. demo-v3 前收口

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| CLOSE-1 | `09075df049c700e9d577c265403e25beabd5023e` | 产品启用合同由旧三门定稿为四门，新增“同目标、同相位 trim 探针实测收益达到事前固定阈值”，旧文字保留带日期追注 | [`落点建议 §1`](product_landing_recommendation_20260901.md#1-启用门清单) |
| CLOSE-2 | `09075df049c700e9d577c265403e25beabd5023e` | Demo 合同纳入 GBS/v4 校准与 Tizen 原生 B/B2；HTML 新增四门章节；GBS 路径优先级随后由终审降为待 held-out | [`Demo 合同`](demo_package_20260902.md#delivery-contracts)、[`HTML 决策门`](demo_report.html#decision-gate) |
| CLOSE-3 | `09075df049c700e9d577c265403e25beabd5023e` | HTML 与双语模板边界新增守护进程碎片化驻留收益微小、估算器不可用两条；delivery ref 预置为 `demo-v3` | [`HTML 边界`](demo_report.html#boundaries)、[`中文模板`](../tools/report/demo_README.zh-CN.md)、[`English template`](../tools/report/demo_README.md) |
| CLOSE-META | `accd86b38516939fe9b50111dca898fd1fadc69c` | 新增本变更索引并把 demo-v3 收口写入时间线 | [`INDEX`](INDEX.md) |
| CLOSE-HTML | `20f5760aa73a97201ac815684bcc8eee830880bb` | 以包含全部 HTML 输入的 `09075df` 为父源提交，单独冻结 source marker 与逐字节派生 HTML | [`source marker`](../tools/report/source_commit.txt)、[`HTML`](demo_report.html) |

## 8. demo-v3 → demo-v4 交付阻断修复

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| DELIVERY-FIXTURE-1 | `demo-v4^{}` | 从当前 HEAD 的精确 SHA 构造身份测试 fixture，不再要求源 clone 存在本地 `main`；显式回归 main、demo、detached-tag 三种源形态 | [`host 测试`](../tools/reproduce/test_host.py) |
| DELIVERY-PREFLIGHT-1 | `demo-v4^{}` | 新增远端三形态强制自检脚本；每形态均须执行完整 host verify 并得到 `PASS host-tests`、`OVERALL PASS` | [`predelivery_check.sh`](../tools/reproduce/predelivery_check.sh)、[`执行合同`](../tools/reproduce/README.md#mandatory-pre-delivery-clone-matrix) |

`demo-v3` 保留用于审计；`demo-v4` 只承载上述 fixture 与交付前自检修复，以及随标签递增
所需的交付引用/入口指针更新，不改变任何既有实验数据或结论。

## 9. demo-v3 前提交覆盖核对

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
测量变更。第三轮证据边界仍可用 `demo-v3^{}` 与 `git log --reverse --no-merges
959b4fb..demo-v3^{}` 复核；交付阻断修复边界改用 `demo-v4^{}` 与
`git log --reverse --no-merges demo-v3^{}..demo-v4^{}`，避免循环自引用。

第四轮交付应以 `demo-v4^{}` 的 peel 后提交为最终快照身份，并通过远端 demo 分支、
detached `demo-v4` 标签、默认 main 三种克隆形态的完整 verify，再核验双语 README/INDEX
链接、HTML source-marker byte-cmp 和脱敏扫描。各实验数字仍以链接的正式报告与公开
TSV/JSON 为唯一事实源。

## 10. 第三轮终审 A 段

| 发现项编号 | 提交 | 变化 | 复核入口 |
|---|---|---|---|
| N4-01 / V4-1–V4-4 | `8e117142211f8a66bef0de56337fb51017dec126` | 默认 verify 去真实 GBS 构建；v4 降为校准带并恢复冻结件默认；B2 日期/证据等级订正；新增 PM 裁决台账与板上轮次事前 tag 规则；闭环终审 minor 项 | [`第 3 轮闭环`](review_fix_20260903.md#第-3-轮终审-a-段闭环2026-09-04)、[`PM 裁决`](pm_decisions.md) |

## 11. demo-v4 → demo-v5：第三轮终审 A/B 闭环

| 发现项编号 | 提交 / tag | 变化 | 复核入口 |
|---|---|---|---|
| N4-01 / V4-1–V4-4 | `8e117142211f8a66bef0de56337fb51017dec126` | A 段把默认 verify 与真实 GBS 环境解耦；v4 降级为校准带；撤回循环使用建带样本得出的 GBS 独立通过；统一 B2 日期/证据等级并建立 PM 台账 | [`第 3 轮 A 段`](review_fix_20260903.md#第-3-轮终审-a-段闭环2026-09-04)、[`PM 台账`](pm_decisions.md) |
| A-CLOSURE | `a7e2379e787a1a1b1bb83440a2515d0994fa5484` | 回填 A 段修复 SHA、重建派生 HTML，并确认默认 verify 在有/无 GBS 两类 PATH 下都不执行真实构建 | [`修复记录`](review_fix_20260903.md)、[`workflow`](../tools/reproduce/README.md) |
| V4-1 / HELDOUT-CONTRACT | `1b6304c583a7ed2e03790ffe5308dabf158eb30c`；轻量 tag `gbs-heldout-contract-20260904` | 在连板前固定 GBS ELF × mixed/medium-only × 2 重复四格合同、既有 v4 闭区间逐格判据、analyzer 与 runner；明确四格不回灌建带样本 | [`合同`](../tools/runners/gbs_heldout_validation_20260904/contract.json)、[`事前规格`](gbs_heldout_validation_20260904.md#1-固定规格) |
| V4-1 / HELDOUT-RESULT | `7f6d95ff10a3dc5ef7a38ac3724dd9ce8473318a` | B 段四格 4/4 落入冻结后的 v4 校准闭区间，身份、validity、stability-monitor 和清理门通过；由独立样本关闭 V4-1，恢复 GBS 默认 L2、冻结件备选 | [`held-out 报告`](gbs_heldout_validation_20260904.md)、[`判定 JSON`](../data/raw/gbs_heldout_validation_20260904/decision.json) |
| V4-1 / HELDOUT-HTML | `e8be0e9652806eef1772dc8dd346770a38551b9d` | 以结果提交为 source marker 重建离线 HTML，使交付层的 GBS 优先级与独立 held-out 依据一致 | [`HTML`](demo_report.html#s4)、[`source marker`](../tools/report/source_commit.txt) |

V4-1 的关闭逻辑是：v4 数值继续只是由 frozen/GBS 建带样本形成的**校准带**；另取在该带
冻结之后、由事前提交与轻量 tag 固定且不参与建带的 GBS-only 四格，按原闭区间得到
4/4 PASS。因而“GBS 重基线通过”只由 held-out 结果支持，不能倒推为 A2 建带样本的
独立结论。`demo-v5` 不改任何测量数字或验收带，只冻结这条证据等级与路径优先级。
