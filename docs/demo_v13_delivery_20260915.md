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
| N12-05 | **BLOCKED，未启用**：实现与成功/失败回归已验证，但新入口真实 GBS 证明缺失，main 入口恢复原字节 | 本地候选 `9b8cdfc` 保留；不将旧证明用于新入口；待固定源恢复 |
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

状态：**STOP_GBS_PINNED_BASE_UNAVAILABLE**。N12-01/02/03 及文档项已修；N12-05
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

需 PM 裁决：恢复已钉 Base snapshot，或批准具有可核验同源身份的镜像替代路径。
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
