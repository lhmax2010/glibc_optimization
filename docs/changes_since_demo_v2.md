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
- `demo-v5 → demo-v6`：仅修复默认 host tests 对 RPM 工具链的隐藏依赖，并把交付前自检扩展为三种克隆形态乘四种可选工具 PATH；不改变任何测量、验收带或结论
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

## 12. demo-v5 → demo-v6：测试环境依赖修复

| 发现项编号 | 提交 / tag | 变化 | 复核入口 |
|---|---|---|---|
| V5-RPM-DEPENDENCY | `demo-v6^{}` | 显式 GBS 环境失败与锁占用测试不再从 host 借用 `rpm` / `rpm2cpio` / `cpio`；改用 fail-if-invoked 自包含桩，使无 RPM 工具链环境仍实际执行断言逻辑 | [`host 测试`](../tools/reproduce/test_host.py)、[`依赖审计`](../tools/reproduce/README.md#default-host-test-dependency-audit) |
| V5-PREDELIVERY-12 | `demo-v6^{}` | 交付前门从三种克隆形态扩展为三形态 × GBS 有/无 × RPM 工具链有/无共 12 次完整 verify；`minimal-git-python` 成为强制环境 | [`predelivery_check.sh`](../tools/reproduce/predelivery_check.sh)、[`交付合同`](demo_package_20260902.md#02-交付快照强制自检) |

`demo-v5` 保留用于审计。`demo-v6` 相对 `demo-v5` 只改变测试 fixture、依赖声明、交付前
自检维度与随标签递增所需的入口引用；没有新增或重算板上数据，也没有修改技术判断。

## 13. demo-v6 → demo-v7

本次仅交付工具行为与文档修正，不改任何测量或技术结论。验收带、held-out 独立性不变。
`demo-v6` 原标签保留；修复先进 main，`demo-v7` 是其完整快照加双语入口，`demo-v7^`
可解析为本轮最终 main。PM 决策见 [`台账`](pm_decisions.md)。

| 发现编号 | 修复提交/引用 | 闭环内容与验证 |
|---|---|---|
| N6-01 / V6-02 | `demo-v7^` | 显式 GBS 的缺环境、锁超时、缺 RPM/任一 ELF 非零退出；成功完整落盘、SHA 校验；清理 EPERM 只报告。覆盖成功/缺工具/锁/缺产物/哈希漂移/清理失败测试，并归档 [`真实构建`](../data/raw/demo_v7_delivery_20260907/gbs/build_summary.json) |
| V6-01 | `demo-v7^` | PATH 从排除法改为闭合白名单；Python ≥3.10 门与完整系统命令清单；三克隆 × 五 PATH（含真最小与损坏工具）验收 |
| N6-02 / V6-1 | `demo-v7^` | 坏 rpmspec 带原因 SKIPPED，静态合同硬门保留；损坏工具完整 verify 回归 |
| N6-03 | `demo-v7^` | held-out 限定 alloc_bench；校验后补公开 [`9/3 retry2 gst 原有紧凑件`](../data/raw/gbs_rebaseline_20260903/gst_retry2/README.md)，纳入公开重放 cmp |
| V6-2 / GBS-STATUS | `demo-v7^` | 历史构建命令和 checker 复跑命令分清；manifest 命令含固定 source commit；pending 事实订正保留日期 |
| V6-5 / V6-6 / V6-7 | `demo-v7^` | B/B2 M7 取值差异披露；估算器/产品落点日期订正；INDEX 补齐报告与 PM 台账 |
| N6-04 / V6-4 | `demo-v7^` | 后续合同 annotated tag + tagger/推送时间 + ≥10 分钟实际审计间隔；历史 tag 不改写 |

## 14. demo-v7 → demo-v8

仅交付工具自证机制与文档修正，不改任何测量、验收带、held-out 独立性或技术结论。
`demo-v7` 保留，`demo-v8^` 指向本轮最终 main；具体实现与验证见
[`第 5 轮闭环`](review_fix_20260903.md#第-5-轮终审闭环demo-v72026-09-07) 与
[`PM 裁决`](pm_decisions.md#2026-09-07-第五轮裁决demo-v7-demo-v8)。

| 发现编号 | 修复提交/引用 | 变化与验证 |
|---|---|---|
| N7-01 | `demo-v8^` | 执行时 clean HEAD/dirty/两脚本哈希/Python/UTC 指纹；publisher 拒绝缺失/漂移且只搬运；git 对象与交付字节一致性测试；干净提交真实重构建并保留旧工作树记录 |
| N7-02 | `demo-v8^` | 锁/RPM 工具/未知 GBS 环境故障 NOT-EVALUATED；可识别源码错误 FAIL；缺产物维持硬 FAIL；桩回归覆盖 |
| N7-03 | `demo-v8^` | 白名单拒绝函数、别名与非可执行文件；真最小/损坏工具等 15 格复核 |
| N7-02b / N7-06 | `demo-v8^` | README 标题限定 alloc_bench；packaging 唯一 workflow 操作入口/固定 payload source/唯一 buildroot/默认路径/范围纳入一致性测试 |
| V6-8 / V6-9 / F12 | `demo-v8^` | 固定 repo 字节比较与移动指针现状分组；导语改为既有带中心两位；同板性依据与缺少唯一硬件序列号证据的局限明确披露 |

## 15. demo-v8 → demo-v9

仅交付工具校验加固与文档，不改任何测量、验收带、held-out 独立性或技术结论。
`demo-v8` 保留，`demo-v9^` 指向本轮最终 main。批准依据见
[`第六轮 PM 裁决`](pm_decisions.md#2026-09-07-第六轮裁决demo-v8-demo-v9)，逐项验证见
[`第六轮修复记录`](review_fix_20260903.md#第-6-轮终审闭环demo-v82026-09-07)。

| 发现编号 | 修复提交/引用 | 变化与验证 |
|---|---|---|
| N8-01 | `demo-v9^` | 执行前 proof 自身字节 SHA；构建后重新打开磁盘文件、先字节后 JSON；输出/发布副本复核；改写、截断、删除、符号链接替换均硬失败 |
| N8-02 | `demo-v9^` | Python 文件系统引导与 shutil.which，不信任 shell command 覆盖；导出 command+目标函数回归；环境标记阻断自调用递归 |
| CC N8-01 | `demo-v9^` | 两份 GBS config、manifest、全部 tracked spec 加入 Git 对象哈希集合；skip-worktree 四输入篡改测试 |
| N8-03 / V8-1 | `demo-v9^` | 缺头文件单列 unknown/需人工二判；明确环境 → 缺头文件歧义 → 源码错误 → 未知的诊断优先级 |
| CC N8-02/N8-03 / N8-04 | `demo-v9^` | 自记而非签名级远程证明、入口字节非调用者的边界声明；原始 GBS 日志哈希归档/校验；脏快照独立失败标签 |

实现提交为 `de89a10bb187d0a1576aaf24a45b9586c55ba3c1`；在该 clean HEAD 上实际 GBS
构建及 publisher 通过，新增 [`v9 构建自证`](../data/raw/demo_v9_delivery_20260907/gbs/README.md)，
保留 v8 历史记录。这不是板上复测，不改变任何原有实验数据或结论。

## 16. demo-v9 → demo-v10

仅入口执行环境净化与文档，不改测量、验收带、held-out 独立性或技术结论。
`demo-v9` 保留；`demo-v10^` 指向本轮最终 main。依据见
[`第七轮 PM 裁决`](pm_decisions.md#2026-09-08-第七轮裁决demo-v9-demo-v10)，
实现与验证见 [`修复记录`](review_fix_20260903.md#第-7-轮终审闭环demo-v92026-09-08)。

| 发现编号 | 修复提交/引用 | 变化与验证 |
|---|---|---|
| Codex N9-01 | `demo-v10^` | 在 shell 普通命令前检查未导出函数/别名；真实 Python execve 无启动文件的新 shell；净化标记预置拒绝；五变体 RC=2 且未进入 MODE |
| Kimi V9-1 / CC N9-02 | `demo-v10^` | 缺依赖与环境注入分开诊断；全量函数拒绝的 Modules 提示与干净进程命令；双语入口同步 |
| V10-DELIVERY-MATRIX | `demo-v10^` | 15 格扩为 18 格：注入环境先预期拒绝，再真跑全量 verify；main REPORT_ONLY、demo/tag required 身份口径不变 |
| CC N9-01 / F01 / F05 | `demo-v10^` | 仅 PM 台账记录：整体 proof 伪造、媒体与完整件包外交付在当前门槛之外；正式 release 处理，不改变现行证据强度 |

实现提交 `6a10812848f31170bacb70022b1b35fe9d161892`；其 clean HEAD 的真实 GBS
构建与 publisher 校验已通过，[v10 执行归档](../data/raw/demo_v10_delivery_20260908/gbs/README.md)
绑定新入口。v9 原始 JSON/TSV 保留为历史；这不是新的板上测量。

## 17. demo-v10 → demo-v11

仅入口信任边界与注入拒绝路径加固，不改测量、验收带、held-out 独立性或技术结论。
`demo-v10` 保留；原 N9-01 的 v10 闭合判断被本次 N10-01 定向复现撤销，历史记录不抹除。
`demo-v11^` 指向本轮最终 main。批准依据见
[`定向 PM 裁决`](pm_decisions.md#2026-09-08-定向裁决demo-v10-demo-v11)，实现与验证见
[`第八轮修复记录`](review_fix_20260903.md#第-8-轮定向闭环demo-v102026-09-08)。

| 发现编号 | 修复提交/引用 | 变化与验证 |
|---|---|---|
| N10-01（1） | `demo-v11^` | 最终真实 Python 调用自然传回 RC，不使用 shell exec/exit 传递拒绝；正文在该调用前保持惰性；非空拒绝诊断由 Python 输出 |
| N10-01（2） | `demo-v11^` | POSIX 特殊内建优先级保护枚举入口；builtin 被遮蔽或枚举器不可用均失败关闭，不降级成空表 |
| N10-01（3–4） | `demo-v11^` | 43 个拒绝变体逐例硬断言 RC=2/非空诊断/无 MODE 与 PASS/零冒充调用；远端三克隆 × 六环境 18 次完整 verify，加 129 次明确拒绝探针 |

实现提交 `3fe95c18a52e86ef45ad97ab0b6323737eecd311` 已在 clean HEAD 实际完成 GBS
构建与 publisher 校验；[v11 归档](../data/raw/demo_v11_delivery_20260908/gbs/README.md)
绑定新入口字节，旧 proof 留作对应执行提交的历史。没有板端连接或新的实验数据。
## v11 → v12：已验收系统前后对照与延期收尾集成

最终交付（2026-09-11）：切库 main `60c102d39fcc6293d3a77ee2081fac83e4f60482`，
demo/v12 `9ff3fe9`，annotated tag 对象 `26e46c4`（完整 refs 在下列汇总，交付
分支/tag 对象不要求位于 main 的无 tag 历史内）。隔离与 GitHub 远端各 18/18 完整 verify、
129/129 启动拒绝全通过；[周末汇总](weekend_summary_20260914.md)、
[完整复审范围](v12_review_brief.md)。以下旧停止/候选表述保留为历史。

周末续跑（2026-09-11 实施；09-12 至 09-14 批次）：

| 发现/授权编号 | 修复提交/入口 | 闭合内容 |
|---|---|---|
| TCP-REDACTION / WEEKEND-A/D | `0518993f3e905eb6e3f32996bd88288187492134` | 三份 TCP 7 行/14 端点不可逆占位，public 哈希链更新，原始哈希与历史保留 |
| ENDPOINT-SCANNER | 同上；[扫描器](../tools/privacy/README.md) | proc IPv4/IPv6/mapped、整数检测；CIDR/JSON/数字歧义负控；默认 verify 全树硬门 |
| WEEKEND-B / SYSTEM-OVERVIEW | [核对说明](weekend_redaction_20260911.md#3-文案核对预授权-b) | 保留原 21 格数字、mixed 负系统净效应、G4 ptrace 边界；不以提示近似值覆盖证据 |
| HOST-CONTRACT-SHA / KNOWN-RESIDUE | `b5dd9483548dcbe5827461e5da24d9bee9bf2977`；[台账](pm_decisions.md) | host 固定 commit+双文件哈希；板端 annotated 门不变；四非空目录已知项 |
| V12-DELIVERY | 新 main 的完整快照 + 双语 README | v11 保留，v12 必须 annotated；三克隆×六环境及 GitHub 远端验证结果另行归档 |

仅公开日志脱敏、host 门与交付材料收口，不改已验收测量、合同、验收带或派生指标。

- SYSTEM-CLEANUP-BOUNDS / PM-GDB-DIRECTORIES-20260911：受限目录执行器与故障回归，
  [c89c9abd1add883fd35850e805e9d4a7248b2eee](https://github.com/lhmax2010/glibc_optimization/commit/c89c9abd1add883fd35850e805e9d4a7248b2eee)；
  四个非空目录实际全部保留，UID 恢复，健康核验闭合。[证据](system_level_before_after_20260908.md#121-实际处置与收尾结果)。
- SYSTEM-ABSOLUTE：按原 annotated `system-before-after-contract-20260908` 合同组合
  已验收 18+3 格，不改历史 STOP，不重跑；[组合证明](../data/raw/system_level_before_after_20260908/accepted_matrix/composition.json)。
- DEMO-SYSTEM-OVERVIEW：HTML 摘要后新增绝对值章节、双语入口两行、L1 五项 cmp 与
  跨载体数字断言；[新章节](demo_report.html#system-effect)、[复算](demo_reproduction_guide_20260901.md#l1-system-before-after)。
  保留 mixed 系统净效应为负、G4 含 ptrace、非空目录待查及非产品收益的边界。
- 入口只新增 host 公开件复算/测试，不修改既有启动注入防护、GBS/held-out 结论或
  验收带；裁决依据见[PM 台账](pm_decisions.md)。

2026-09-11 前次停止状态（历史保留）：以上是候选集成，**当时没有切出 demo-v12**。源码集成提交
`7093d8a60814b706f1f6809cf6b6d282a359c402`，HTML 构建提交/真实 GBS clean HEAD
`4539139956b89d82864a93c57ce68b7b07bdc850`；[构建证明](../data/raw/demo_v12_delivery_20260911/gbs/README.md)
通过，但新增收尾重放依赖命名合同 tag，交付身份无 tag fixture 的八个子用例失败。
[停止报告](demo_v12_delivery_blocker_20260911.md)保留根因；未放宽测试、未执行远端矩阵。
demo-v11 仍为当前有效交付，21 格与全部旧证据不受影响。

2026-09-11 后续 PM 方向二闭合：`STOP_HOST_REPLAY_TAG_DEPENDENCY` 修复提交
`b5dd9483548dcbe5827461e5da24d9bee9bf2977`，host 只读固定 commit、双文件 SHA-256
并严格比较原字节；三种实际克隆形态和缺对象诊断回归通过，板端 annotated tag、
事前提交/推送与时间间隔门未改。四个非空目录按 `SYSTEM-GDB-KNOWN-RESIDUE` 作为
已知项保留，不删非我方文件。本次不连板、不改数据或结论；[交付验收记录](demo_v12_delivery_20260911.md)
与 [PM 裁决](pm_decisions.md)衔接此后快照状态，旧停止报告保留。

随后执行留痕：修复及文档 `b5dd9483548dcbe5827461e5da24d9bee9bf2977` /
`2f0cb95745b9a8df6a6041a021b505e522f9809a` 已推 main；新全仓脱敏门发现既有 TCP
编码地址 7 行未替换，按 PM 原停止规则中止隔离矩阵（仅前两格通过），不发布 v12。
数据、合同与旧证据不改写，交付配置恢复指向 v11；[新停止记录](demo_v12_delivery_20260911.md#4-新停止门既有-tcp-原文的编码地址未脱敏)。
