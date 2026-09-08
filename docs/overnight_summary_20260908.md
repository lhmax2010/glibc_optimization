# 无人值守批量任务汇总（2026-09-08）

当前有效交付快照：**`demo-v11`**。本次批量任务在第 1 段只读占用门停止，未进入正式测量；不切 demo-v12。

| 段 | 状态 | 依据 / 后续门 |
|---|---|---|
| 0：N10-01 修复与交付 | 完成、已推送 | main `061d5039d69e32b1c8414b31ea8b7c0e05619338`；demo-v11 peel `0e8a2f731b13690009badf1ca2acbd57018e7bc8`，tag 对象 `f1266c0be6c225a2ceb962836380c656758f9427`；扩展矩阵 18 次 verify 与 129 个预期拒绝探针全通过，见 [修复记录](review_fix_20260903.md#第-8-轮定向闭环demo-v102026-09-08) |
| 1：系统级前后对照 | **停止：共享交互会话归属未明** | [报告 §3](system_level_before_after_20260908.md#3-实际执行只读前置门后停止)；身份/环境门通过，但已有两个 `sh -l` 会话，不能排除共享占用；0/21 格执行 |
| 2：Demo 集成 | **未执行：受第 1 段停止门阻断** | 不使用比例反推绝对值，不更新 HTML/README 头条 |
| 3：demo-v12 | **未执行：受第 1 段停止门阻断** | demo-v11 保持当前交付，不生成 v12 tag，不移动 demo 分支 |

## 合同与推库记录

- 事前合同 + analyzer：`54ee2ba8d2819014f3e5656de023ffaf283b4a4a`。
- Annotated tag：`system-before-after-contract-20260908`，对象 `0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3`。
- origin 确认完成时间：`2026-09-08T04:55:52.140217+00:00`；最早允许连接时间 `2026-09-08T05:05:52.140217+00:00`。以 host UTC 和 monotonic 两种时钟检查至少 600 s 间隔。
- 合同提交前既有 verify `OVERALL PASS`；新分析器 10 项测试通过。等待期间的观测握手 host smoke test 通过，非板上性能证据。
- 首次检查实际 host UTC `05:06:11.703742`；距推送确认 `619.572023306 s`，满足事前间隔，见 [停止证据](../data/raw/system_level_before_after_20260908/stop_evidence.json)。
- 只读原文、单次追加核查、停止判定与准备件状态收尾提交：`027bbc0b0e44dfd60edaee24598601eee3ec344b`；该干净提交上普通 `bash tools/reproduce/reproduce.sh verify`（无 dirty override）亦为 `OVERALL PASS`。本条 SHA 回执更新不改代码/证据；回执自身所属最终提交以 Git 与最终响应为准，避免自引用 SHA。
- [收尾检查](../data/raw/system_level_before_after_20260908/host_checks.tsv)：既有 verify PASS，新轮次 13 项 host 测试通过，相关链接 155 项通过，脱敏零命中。没有执行第 3 段新交付矩阵，不把第 0 段的通过记录冒充 v12 验收。

## 关键数字

| 指标 | 本轮结果 |
|---|---|
| RSS / 堆 PD 前后值及降幅 | 无测量，`NOT-EVALUATED` |
| MemAvailable none 校正净效应 | 无测量，`NOT-EVALUATED` |
| trim 耗时 / 下周期 faults / gst 业务墙钟 | 无测量，`NOT-EVALUATED` |
| G4 常驻守护收益 | 无测量，`NOT-EVALUATED` |

历史百分比不用于填补本轮绝对值。身份门观察的 glibc/MemTotal/df 仅作为可用性证据，不是新 Demo 数字。

## 待裁事项

需要后续确认 PID `26799`（`pts/0`）与 `27105`（`pts/1`）的归属及可用实验时段。
[原文](../data/raw/system_level_before_after_20260908/occupancy_excerpt.txt) 显示两者 sleeping、PPID=1，
但这不足以确认其为无人使用的残留；未声称已证明他人在主动测试。两条会话均未处置。

正式格未运行，健康/回收/业务结论未生成。执行器草稿另有未完成的安全与故障路径测试，已
以无条件 RC=2 阻断，详见 [准备件状态](../tools/runners/system_level_before_after_20260908/README.md#未执行准备件不可作为可用复现入口)。
本轮不绕过停止门继续，也不切 demo-v12；若重启这项工作，须先明确占用状态并闭合执行器。

完整原始日志本地留存于 `board_results/system_level_before_after_20260908/`，可按请求提供；公开报告保持既有脱敏映射，板端运行路径保留。
