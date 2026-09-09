# 两日批量执行汇总（2026-09-08 至 09-10）

记录创建于 2026-09-09；文件名为批量交付窗口，不表示尚未发生的 09-10 测量。
**终态：第 2 段在当前 UID=5001（要求 0）处 STOP，后续全部停止。**
当前有效交付快照仍为 **demo-v11**，未创建 demo-v12。G1/G2/G3 已验收的 18 格保留，未重跑。

| 段 | 状态 | 证据/后续门 |
|---|---|---|
| 1 · host 执行器闭合 | 完成，推库后才允许连板 | 114 项本轮 host 测试通过；既有 verify OVERALL PASS（提交前显式 dirty override）；[回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv) |
| 2 · 重启后卫生门 / G4 三格 | STOP / G4 NOT_EXECUTED | 三项身份、glibc、MemTotal 通过；UID=5001 触发 root 硬门，未尝试 root-on；其后卫生与占用项未执行，不能声称现场已恢复 |
| 3 · Demo 集成 | NOT_EXECUTED_STOP_GATE | G4 缺口未闭合；HTML/README/指南头条不改 |
| 4 · demo-v12 | NOT_EXECUTED_STOP_GATE | 不切库、不执行新交付矩阵，demo-v11 保持有效 |
| 5 · 定向复审准备 | NOT_EXECUTED_STOP_GATE | 无 v12，不生成其 brief、不联系第三方 |

本次从 2026-09-09 03:09:54.998761 UTC 的客户端检查开始，至 03:09:58.111178 UTC
停止。只读原文、命令、编辑前后 SHA 见[回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/execution.json)
和[清单](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/manifest.json)。
本次 0 格测量、0 次注入、0 文件推送、0 包安装/卸载、0 governor 修改，无重启或会话清除。

## 已保留证据与数字边界

既有 18 格及 330 对采样见[公开紧凑件](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json)
和[逐周期派生](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)。
不在 G4 完成前把部分矩阵提升为新的 Demo 头条。none 的“零”仅能指确实观测到的进程
RSS/堆 PD 下降；系统 MemAvailable 背景波动与配对净效应必须保留符号，不能强写成零或净增。
系统配对是同相位顺序格，不是同一时刻并行对照。G4 后续数据属于重启后的独立健康时期。

### 保留的 18 格：停止报告用数字表（非完整矩阵 / 非 Demo 集成）

以下仅整理已经验收的 09-08 数据，每档取三重复的 **cycle=1** 中位，与冻结
[summary 定义](../tools/runners/system_level_before_after_20260908/contract.json)一致。
数字逐项来自[completed_cycles.tsv](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)
同名字段（RSS=`rss_drop_mib/rss_drop_pct`，系统=`memavailable_net_mib`，耗时=`trim_elapsed_ms`）。
这些是测试板负载量级，不等于产品或整机收益；未新增或补齐任何 G4 数据。

| 组 / trim 臂 | RSS 下降 MiB / % 中位 | 配对 MemAvailable 净效应 MiB 中位 | trim ms 中位 | none RSS 下降 MiB | G4 状态 |
|---|---|---|---|---|---|
| G1 mixed | 5.296875 / 40.696279% | **-0.167969** | 1.458574 | 0 | 不适用 |
| G2 medium-only | 5.960938 / 45.322245% | +5.304688 | 1.478167 | 0 | 不适用 |
| G3 解码循环 | 1.820312 / 21.009919% | +1.855469 | 0.843612 | 0 | 不适用 |
| G4 enlightenment | NA | NA（原合同无 none 臂） | NA（含 ptrace，不是 hook 代价） | NA | NOT_EXECUTED |

G1 的系统配对净效应为负，不能写“系统可用内存净增”；none 的系统可用内存也有背景
变化，只有表中进程 RSS 的下降为零。所有前后采样窗口 major fault 为 0；最后一周期
next-cycle 为 NA，G3 冷启动首周期按合同独立记录，不能把这个 0 外推到任意启动。
G4 背景参考仍为[历史 B/B2](tizen_native_evidence_20260904.md)的 272 KiB / 36 KiB，
不能用它们填本次三格。此次没有“业务无代价”的新结论。

## 推库与待裁事项

原 18 格/失败 G4 结果提交：`60bea7c63ca2c603351e0ef25df15546e78db05c`；
执行器来源：`06799668543c014b0552a23720ca7e79304f4346`。
本次第 1 段已推提交：`ff2442ef0b2b8779646a08408fab9bf5bc3e7488`。
停止结果已推提交：`776de96e6c53932f2ed45e28558a9e8035ae2a78`。
所有已完成部分进入 main，未改 demo 分支。

从 GitHub 远端普通 main 克隆结果提交 `776de96e6c53932f2ed45e28558a9e8035ae2a78`，
工作树干净、未使用 dirty/test-skip override：本轮 114 项测试通过，默认 verify
`OVERALL PASS`；main 的交付身份正确标为 REPORT_ONLY，指向 demo-v11。
停止报告链接 235 项通过，11 件公开日志哈希与清单一致，脱敏扫描零命中；
见[检查回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv)。
这是 host 修复验证，不是未执行的 G4/整轮健康/交付 v12 矩阵通过。

待周五 PM 裁决：当前 sdb 会话 UID=5001，不满足固定 root 门；请决定如何恢复满足合同的
会话并重新授权 G4，或是否接受缺 G4 的 v12。执行器不得自行 root-on、降门或重启。
PM 手动重启与卸包警告裁决见[台账](pm_decisions.md)；当前卫生/包状态仍需后续重新核验。

有效交付身份：demo/demo-v11 peel commit `0e8a2f731b13690009badf1ca2acbd57018e7bc8`；
annotated tag 对象 `f1266c0be6c225a2ceb962836380c656758f9427`。本轮没有 demo-v12。
