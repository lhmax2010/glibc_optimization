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
| N12-05 | check 父项 PASS 保留，SKIPPED/REPORT_ONLY 子项与原因同步输出 | 成功含 SKIPPED / 非零失败回归；完整 verify |
| V12-5 | 冻结 gst_arms 旧 max 字段加解释，不改 TSV | 从各重复最大值重算中位 1.097408 ms，独立核对全池最大 1.376555 ms |
| V12-6、N12-07 | 扫描器最终 13 项；周末 41.8/45.3/16.0 明示全周期口径 | 测试计数、文档核对 |
| 台账六类已知项 | 仅记录正式 release 建议，不改变门或数据 | PM 台账逐项保留理由与批准人 |

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

修复提交与最终 SHA、完整矩阵、HTML cmp、全树脱敏结果在执行完成后追记于本节。
未完成前仍以 demo-v12 为既有快照；不提前声明 demo-v13 可交付。
