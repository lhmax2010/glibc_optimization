# 两日批量执行汇总（2026-09-08 至 09-10）

记录创建于 2026-09-09；文件名为批量交付窗口，不表示尚未发生的 09-10 测量。
当前有效交付快照仍为 **demo-v11**。G1/G2/G3 已验收的 18 格保留，禁止重跑。

| 段 | 状态 | 证据/后续门 |
|---|---|---|
| 1 · host 执行器闭合 | 完成，推库后才允许连板 | 114 项本轮 host 测试通过；既有 verify OVERALL PASS（提交前显式 dirty override）；[回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv) |
| 2 · 重启后卫生门 / G4 三格 | NOT_EXECUTED | 需新鲜身份/环境/占用原文；不沿用旧 PID 清除授权 |
| 3 · Demo 集成 | NOT_EXECUTED | G4 和健康门全部通过才执行 |
| 4 · demo-v12 | NOT_EXECUTED | 前三段闭合、完整交付矩阵通过才切库 |
| 5 · 定向复审准备 | NOT_EXECUTED | 仅 v12 切出后生成 brief，不联系第三方 |

## 已保留证据与数字边界

既有 18 格及 330 对采样见[公开紧凑件](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json)
和[逐周期派生](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)。
不在 G4 完成前把部分矩阵提升为新的 Demo 头条。none 的“零”仅能指确实观测到的进程
RSS/堆 PD 下降；系统 MemAvailable 背景波动与配对净效应必须保留符号，不能强写成零或净增。
系统配对是同相位顺序格，不是同一时刻并行对照。G4 后续数据属于重启后的独立健康时期。

## 推库与待裁事项

原 18 格/失败 G4 结果提交：`60bea7c63ca2c603351e0ef25df15546e78db05c`；
执行器来源：`06799668543c014b0552a23720ca7e79304f4346`。
本次提交及终态将在对应步骤完成后追加。当前没有新增 PM 问题；若任何停止门触发，
后续全部停止并保留 demo-v11，等待周五裁决。PM 手动重启与卸包警告裁决见[台账](pm_decisions.md)。
