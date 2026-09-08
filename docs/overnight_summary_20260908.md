# 无人值守批量任务汇总（2026-09-08）

## 当日续跑最终汇总

**当前有效交付快照仍为 `demo-v11`；未切 demo-v12。** PM 批准的两条残留会话已清除，
占用门闭合；原合同不改字节、不重打 tag。执行器在干净提交上运行后，G1/G2/G3 的
18 格通过，G4 首格 M7 的 `$fp` 赋值报错，触发停止门。没有重跑失败格，也未执行
Demo 集成和交付切库。详见 [续跑报告 §6](system_level_before_after_20260908.md#6-当日续跑结果g4-首格停止不进入-demo-集成)。

| 段 | 续跑终态 | 依据 |
|---|---|---|
| 0：N10-01 / demo-v11 | 已完成，保持有效 | 原交付 SHA 与矩阵见下方历史记录 |
| 1：系统级前后对照 | **STOP_G4_M7_ASSIGNMENT** | [回执](../data/raw/system_level_before_after_20260908/execution/execution.json)：G1/G2/G3 18/18，G4 0/3；M7 首行报 lvalue 错误 |
| 2：Demo 集成 | **未执行，受停止门阻断** | 不将部分样本转成 Demo 头条 |
| 3：demo-v12 | **未执行，受停止门阻断** | demo 分支 / demo-v11 保持原提交，不产生 v12 |

| 关键量 / 检查 | 续跑记录 |
|---|---|
| 已完成采样 | 18 格、330 个释放点；[逐周期 TSV](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)，仅为不完整矩阵的已完成前缀 |
| 新的完整前后对照 / 三重复 Demo 头条 | 未生成；G4 缺失，不能宣称完成 21 格 |
| 健康 | 整轮 OOM/LMK 0，stability 0→0，zram 三项 Δ=[0,0,0]；不是效果结论 |
| 已检查清理 | 目录/包登记/辅助进程/四核 schedutil 通过；原文见报告 |
| 清理边界 | G4 空 XML 已产生，目标内部可能的 FILE*/FD 残留未排除；卸包 msm/ldconfig 警告保留 |

本轮启动/结束 UTC 为 `06:05:53.362393` / `08:16:11.304636`，距原合同推送
`4201.242326624 s`。运行使用提交 `06799668543c014b0552a23720ca7e79304f4346`，
对应事前执行器修复 `d0c4247`；两者均已推 main。结果与停止证据所属提交见 Git 历史及
本次最终回执，不填写自引用 SHA。合同提交/tag 对象与 demo-v11 SHA 均沿用下方记录。

需要 PM 裁决的是 G4 后续恢复：新执行器重复用了旧原生实证已避开的 `$fp` 名称，
必须补真实 ARM GDB 赋值/失败副作用覆盖；还须决定如何核验/恢复目标内可能的 FILE*/FD
状态与卸包警告，不能由目录清理通过推断内部已恢复。停止后没有再次注入或重启目标。
已完成 G1/G2/G3 原始件不丢弃、不覆盖，但不据此绕过完整矩阵门。

## 首次停止及执行前追注（历史保留）

当日续跑追注：PM 已确认专供板并批准清除两条残留会话；清除及只读复核已完成，
原占用门闭合，见 [报告 §5](system_level_before_after_20260908.md#5-pm-裁决后续跑占用处置与执行器闭合)。
执行器安全/故障测试已补齐（本轮全套 host 62 项通过，既有 verify OVERALL PASS），
准备先提交再启动原 21 格合同。以下首次停止记录保持原样；在全部测量和交付门完成前，
有效交付仍为 demo-v11，未生成新的 Demo 绝对值。

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
