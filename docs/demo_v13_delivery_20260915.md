# demo-v13 对客口径修正与交付核验（2026-09-15）

基线 main `e8f37f7`、demo-v12 `9ff3fe9`。本轮 host-only，不连接板、不重跑或修改
任何测量。冻结合同、验收带、accepted_matrix 的 TSV/JSON 均保持原字节。
PM 裁决见[台账](pm_decisions.md#2026-09-15demo-v12-demo-v13-对客口径订正)。

## 1. 编号闭环

| 编号 | 修正 | 验证方式 |
|---|---|---|
| N12-01 | HTML、系统报告、双语入口与叙事/指南/包邻近说明 G3 首周期与全池 153 点的区别，收益/代价窗口不对称明确披露 | builder 从逐行整数独立算全池中位/范围与首周期排名；跨载体测试、输入变异负控 |
| N12-02 | 系统三组及 G4 RSS 邻列极差与 NOT-DETECTED，不宣称系统净增已证实 | 从 cycles 独立复算中位/极差；断言与负控；原 gst 有向规则未改 |
| N12-03 | 守护同目标只引用 272/36；8–20 明示官方 GST 工具；HTML boundaries 原文不动 | 归属检索、章节字节比较 |
| N12-04/V12-3 | 缺 commit 提示 fetch；README 区分公开复算与完整 verify，override 不绕过对象校验 | 缺对象诊断负控；完整克隆矩阵 |
| N12-05 | **WITHDRAWN-BY-PM**（2026-09-15 续裁决），不再实施显示项 | 入口与 current-proof 校验保持 v12 原字节，不为 nit 更换已钉源或重建产物 |
| V12-5 | 冻结 gst_arms 旧 max 字段加解释，不改 TSV | 从各重复最大值重算中位 1.097408 ms，独立核对全池最大 1.376555 ms |
| V12-6、N12-07 | 扫描器最终 13 项；周末 41.8/45.3/16.0 明示全周期口径 | 测试计数、文档核对 |
| 台账已知项 | 仅记录正式 release 建议，不改变门或数据 | PM 台账逐项保留理由与批准人 |

## 2. 数字与判读

输入均为[已验收逐周期](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)
及[摘要](../data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)。

| 量 | 中位 | 极差或范围 | 判读 |
|---|---|---|---|
| G3 全周期 RSS 下降（51×3 点） | 16.038164% | 13.282648–21.043165% | 头条 cycle=1 的 21.009919% 不是持续典型值 |
| G1 系统净效应 MiB | −0.167969 | 9.394531 | NOT-DETECTED |
| G2 系统净效应 MiB | +5.304688 | 8.136719 | NOT-DETECTED |
| G3 系统净效应 MiB | +1.855469 | 2.816406 | NOT-DETECTED |
| G4 RSS 下降 MiB | 0.003906 | 0.089844 | NOT-DETECTED |

按 PM 固定的幅度/重复离散规则：双向量可见 iff |中位| > 重复极差，不是统计显著性
检验。gst 原有正向劣化规则不变。收益头条 cycle=1 与成本 primary_cycles="2-51"
分别沿用既有合同/分析器；G4 1899.209517 ms 含 gdb/ptrace，仍与约 1 ms 钩子分列。
本轮只修展示，不能据此宣称产品或整机收益。

## 3. 交付验证记录

以下为同日续裁决前的历史记录，已由 §4 解除，不再是当前交付条件。

当时状态：**STOP_GBS_PINNED_BASE_UNAVAILABLE**。N12-01/02/03 及文档项已修；N12-05
未闭合，不切 demo-v13，不执行候选交付矩阵。demo/demo-v12 仍指向 `9ff3fe9`，
annotated tag 对象 `26e46c4` 未动；这不是宣称 v12 已解决本轮对客发现。

执行顺序：先提交候选 `9b8cdfc421615cacc4f55880f7b14bb604bbd36c`，对该 clean HEAD
实际执行一次 `bash tools/reproduce/reproduce.sh gbs --output-dir <NEW_HOST_BUNDLE>`。
取锁与启动指纹通过，依赖解析失败，未生成 RPM/ELF，未重试。输出为
NOT-EVALUATED gbs-build-unknown、OVERALL FAIL、RC=2；不将未建成误报为包缺陷。
随后的只读固定源核查确认 Base repomd HTTP 404，Unified HTTP 200。
[公开阻塞证据](../data/raw/demo_v13_delivery_20260915/gbs_blocker.json)。

失败入口改动没有取得新自证归档；为避免把当前文件不匹配的旧证明当作新证明，
main 的入口及 current-proof 校验保持原 v12 字节/要求，N12-05 改动连同回归留在
上述历史候选及本地 `n12-05-pending-gbs-proof`。没有跳过测试、降低门、修改源配置、
使用不同 snapshot、重新发布旧 proof 或重跑板上测量。

当时提出的待裁建议（已撤销，不再执行）：恢复已钉 Base snapshot，或批准具有可核验同源身份的镜像替代路径。
当前源与构建配置不擅改。源恢复后先启用候选 N12-05、在干净提交真实构建并归档，
再跑完整三克隆×六环境（含启动拒绝）矩阵，全部通过后才能切 demo-v13。

可合入部分验证（`e4ee10e6057058bddaad2e7050e7cdb2af42b7fb`）：完整
`bash tools/reproduce/reproduce.sh verify` 为 OVERALL PASS，13 个 host 模块正常执行，
只对缺少显式 ARM 环境与默认排除真实 GBS 的子项显示 SKIPPED；main 身份为既定
REPORT_ONLY，不是交付快照 required 验收。HTML 重建 cmp 静默，全仓链接 1504 项、
模板根入口链接 102 项通过，4429 文件当前树扫描零命中。报告 13 项、扫描器与合同
克隆 25 项专项测试通过。14 个固定输入/证据/入口文件与基线逐字节相同，HTML
boundaries 节原文不动。[机器记录](../data/raw/demo_v13_delivery_20260915/partial_verification.json)。

候选修复 `9b8cdfc`、N12-05 暂缓/阻塞记录 `a77293d`、生成 HTML `e4ee10e`；
最终记录提交以本文件的 `git log -1 --format=%H` 定位，不写自引用伪 SHA。
完整三克隆×六环境交付矩阵 **NOT_EXECUTED**，不可把上述通过写成 demo-v13
交付门通过。未创建 demo-v13，未移动 demo 或既有标签。

## 4. 2026-09-15 续裁决：撤回显示项，解除构建源阻塞

批准人 PM。N12-05 **WITHDRAWN-BY-PM**：为显示 nit 更换已钉源会触发 GBS
产物重新验证，风险收益不成比例。STOP_GBS_PINNED_BASE_UNAVAILABLE 不再是本轮
交付条件；不启用该候选改动，不改入口或 current-proof 门，不更换源、不重建 GBS。

历史事实：`9b8cdfc` 已在此前推送的 main 祖先链中，其中 N12-05 入口改动已由
`a77293d` 撤回。不能把“当前未生效”写成“提交从未进入历史”；本轮不重新合入该
改动，也不重写已发布历史。旧 v12 成功证明继续严格绑定当前受保护文件原字节。

固定 Base `20260813.050338` 的 repomd 已 HTTP 404，Unified 仍可用，原始核查见
[阻塞证据](../data/raw/demo_v13_delivery_20260915/gbs_blocker.json)。影响仅限需要
新建 GBS 构建证明的场景；既有证明与全部已发布数字不受影响。建议正式 release
使用长期可得源，或将所需 repodata/产物归档到内部制品库；本轮不改任何构建配置。

后续重新执行完整交付矩阵、HTML cmp、链接与脱敏门；结果在下节追加。板端合同、
测量 TSV/JSON、验收带、入口与 current-proof 校验不因解除显示项而弱化或改写。

## 5. 最终交付核验：PASS

2026-09-15 续跑完成，当前交付快照为 **demo-v13**；demo-v12 原对象保留。N12-05
已撤回，不是待修复项；固定 Base 失效是新建构建证明的已知限制，不再阻断本次交付。

| 核验 | 隔离候选远端 | GitHub 远端 |
|---|---|---|
| 三克隆 × 六环境完整 verify | 18/18 PASS | 18/18 PASS |
| 启动注入拒绝（RC=2、非空诊断、零冒充调用、无 MODE/PASS） | 129/129 PASS | 129/129 PASS |
| demo / annotated tag 身份 | REQUIRED，全部通过 | REQUIRED，全部通过 |
| 默认 main 身份 | 既定 REPORT_ONLY，完整 verify PASS | 既定 REPORT_ONLY，完整 verify PASS |
| HTML 重建 | cmp 静默 | cmp 静默 |
| 交付面 / 全仓链接 | 605 / 1579，零失败 | 605 / 1579，零失败 |
| 当前树脱敏 | 4431 文件、零命中 | 4431 文件、零命中 |

六环境为 GBS/RPM 均可发现、仅 RPM、仅 GBS、最小白名单、损坏工具、启动注入。
可选工具存在性用受控桩，GBS 真实构建从默认 verify 排除；未伪装成实际 GBS 重建。
每次完整 verify 均实际运行全部 13 个 host 测试模块。模板按根入口语义检查，
全仓扫描豁免模板源路径的相对链接，实际双语 README 与模板 cmp 均静默。

切库后另按普通 HQ 方式从 GitHub 分别 `git clone --branch demo` 与
`git clone --branch demo-v13`，两份默认 host 环境完整 verify 均 RC=0、
`PASS host-tests`、`OVERALL PASS`，无交付身份 REPORT_ONLY 降级。
原文及文件哈希见[公开回执](../data/raw/demo_v13_delivery_20260915/README.md)。

| 引用 | SHA |
|---|---|
| 切库 main | `2bf46f2680fa52f9a61d47a620880311c28a4dcf` |
| demo / demo-v13 peel 后 commit | `1e8378adbab9acf937b4a51d3348b8f0bde2ff5f` |
| demo-v13 annotated tag 对象 | `0353ad46ef83e9f46c305c2cb8a023256514bf52` |
| 保留的 demo-v12 annotated tag 对象 | `26e46c46fdc32c04da08fa31b317800dda25d560` |

快照相对切库 main 仅替换/新增两份 README。main 使用普通快进推送；demo 使用精确
旧 SHA lease 更新，不重写 main 历史。本节与远端回执是切库后追加到 main 的记录，
不回写冻结标签；最终回执提交可由 `git log -1 --format=%H -- <本报告路径>` 定位。

不变性：基线已有的 250 份 TSV/JSON/XML 逐字节未变；六个 provenance 保护文件、
current-proof 校验方法、冻结合同/分析器/验收带和 HTML boundaries 原文保持不变。
报告专项 13 项与脱敏/合同克隆专项 25 项通过。一次手工专项命令误写模块名导致
ModuleNotFoundError，更正为实际 `tools.privacy.test_endpoints` 后 25 项通过；
这是命令笔误，未改代码、未跳过测试。全程无板端连接、无测量或新 GBS 构建。

追加回执后的 main 当前树再次核验：4436 个跟踪文件脱敏零命中，全仓链接 1521 条
零失败，HTML 重建 cmp 静默。上表的 4431 / 1579 是冻结 demo 快照口径，两者不混用。
