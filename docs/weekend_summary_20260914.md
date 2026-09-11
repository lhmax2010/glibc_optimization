# 周末无人值守批量汇总（2026-09-12 至 09-14）

文件名与标题是 PM 指定批次；实际 host 操作于 2026-09-11 执行，UTC 见机器回执。
日期仅作批次标识。全程未连测试板、未提权、未 reboot，21 格没有重跑或改值。

## 1. 逐段状态

| 段 | 状态 | 证据 / 说明 |
|---|---|---|
| 1 定向脱敏与扫描器 | 完成 | [更正报告](weekend_redaction_20260911.md)、[14 token 哈希链](../data/raw/demo_v12_delivery_20260911/weekend/redaction.json)；仅三份 TCP 7 行，历史未改写 |
| 2 自检与切库 | 完成 | 隔离与 GitHub 远端各 18/18 完整 verify、129/129 注入拒绝；annotated v12 已推并核验 |
| 3 材料收口 | 完成 | [复审简报](v12_review_brief.md)；未联系第三方；所有数值来自已验收公开件 |
| 4 周一材料 | 完成 | 本文与[机器回执](../data/raw/demo_v12_delivery_20260911/weekend/verification.json)；后置材料不改代码或测量 |

**当前有效交付快照是 demo-v12。** demo-v11 标签保留，所有历史停止记录保留。

矩阵[隔离摘要](../data/raw/demo_v12_delivery_20260911/weekend/isolated_matrix.tsv)与
[GitHub 摘要](../data/raw/demo_v12_delivery_20260911/weekend/github_matrix.tsv)逐格记录身份和完整
host-tests；每套均三克隆 × 六环境，不因提示“3×5”而删除既有损坏工具形态。
[额外 GitHub 三形态重放](../data/raw/demo_v12_delivery_20260911/weekend/public_replay_clones.log)
的完整/无 tag/浅克隆各五份派生物 byte cmp 通过；浅克隆缺固定对象时预期 RC=2，
有明确 fetch 诊断，补对象后仍无 tag/仍浅克隆而 PASS，不算跳过。
47 项针对性测试、246 项 runner 回归通过。冻结快照链接：交付面 723 / 全仓 1483，
均 PASS；双语模板按根 README 解释，含 zh README 和 INDEX。HTML 重建 58184 字节 cmp
静默；当前树脱敏结果见[复扫](../data/raw/demo_v12_delivery_20260911/weekend/after_scan.json)。

## 2. 关键数字（沿用已验收数据）

以下为 cycle=1 每臂三重复的独立列中位，不能拿展示前后中位重新算百分比。
每个数字的共同来源为 [summary.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)
与 [cycles.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)，
单位解释及逐数字入口见 [L1 指南](demo_reproduction_guide_20260901.md#l1-system-before-after)。

| 组 | RSS 前 → 后 MiB | RSS 降幅中位 | 系统配对净效应 MiB | 释放点调用中位 ms |
|---|---|---|---|---|
| G1 mixed | 13.015625 → 7.718750 | 40.696279% | −0.167969 | 1.458574 |
| G2 medium-only | 13.152344 → 7.191406 | 45.322245% | +5.304688 | 1.478167 |
| G3 gst | 8.671875 → 6.859375 | 21.009919% | +1.855469 | 0.843612 |

- 三组 none 的 RSS 下降均为 0，不代表 MemAvailable 不变；mixed 的系统净效应确为负。
  配对为同编号重复/周期的顺序 none，不能称并行同期。[逐周期证据](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)。
- gst p99 中位差 −1.652834 ms 对基线重复离散 11.794149 ms，固定规则方向 REPORT_ONLY、
  未检出不等于零代价；没有与旧 gst 数据混池。[判定](../data/raw/system_level_before_after_20260908/accepted_matrix/gst_comparison.json)。
- G4 堆 PD 下降 88/0/4 KiB；RSS 降幅中位 0.033659%，1899.209517 ms 是**含 gdb/ptrace
  的注入开销**，不是上表约 1 ms 的钩子代价。G4 无 none，系统净效应 NA；静置 minflt
  1/0/1，与下周期分开。[G4 原表](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)。
- 已观测 capture/next-cycle major faults 为 0，末周期 next-cycle NA 不改写为零。
  trim/none 使用相同已核验 ELF，运行时调用不改变二进制体积。[整轮报告](system_level_before_after_20260908.md)。
- 常驻守护收益很小，与既有 272 / 36 / 8–20 KiB 反例同向；不证明产品收益或一般整机收益。
  [B/B2](tizen_native_evidence_20260904.md)。

## 3. 推库身份清单

| 对象 | SHA | 说明 |
|---|---|---|
| main 脱敏修复 | `0518993f3e905eb6e3f32996bd88288187492134` | 第 1 段完成后已推 |
| main 切库源 | `60c102d39fcc6293d3a77ee2081fac83e4f60482` | demo 的直接父提交，完整快照源 |
| demo / demo-v12 peel commit | `9ff3fe9c0e91b6be6b599fd6abab6276e8556ade` | 相对切库源仅双语 README |
| demo-v12 annotated tag 对象 | `26e46c46fdc32c04da08fa31b317800dda25d560` | 与 commit 分列，不混淆对象类型 |
| 保留 demo-v11 commit | `0e8a2f731b13690009badf1ca2acbd57018e7bc8` | 旧标签未重写 |

此汇总、简报和远端验证日志属于切库后的 main 文档提交，不假称在冻结 demo 内。
该后置 main 提交可用 `git log -1 --format=%H -- docs/weekend_summary_20260914.md` 定位；
最终推送 SHA 在交付回复中报告，避免把自引用提交 SHA 写成不可实现的固定字面值。

## 4. 预授权实际处置与硬停审计

| 授权 | 实际处置 |
|---|---|
| A / D | 三 TCP 共 14 端点不可逆替换；原始哈希不变，三个 public manifest 与引用记录更新；初始扫描无其他当前树命中；历史可见性只列不改 |
| B | 提示 41.8% / 45.3% / 16.0% 与库内同口径不符，保留表中已发布值并说明；新文档链接实查；地址前缀、CIDR 与数字误改负控在提交前修复 |
| C | 缺 ARM 工具链/GBS 等沿用显式 SKIPPED；坏 rpmspec 按既有环境规则处理，静态 spec/合同/注入/脱敏门照常执行 |
| E / F / G / H | 当前无新硬停命中；没有改合同/验收带/测量/派生指标，没有削弱或跳过门，没有需要连板确认的问题 |

此前 tag/SHA 与 TCP STOP 仍是历史事实，不改写为当时 PASS；本次只记录获新授权后的闭合。
四个非空目录按 [PM 台账](pm_decisions.md)为已知项，内容已归档，非我方文件没有清除。

## 5. 建议 PM 周一优先处理

1. 正式 release 的历史隐私/仓库可见性策略：旧三份 TCP 的历史对象仍可恢复；本次“零命中”
   只指当前工作树，不含历史。此轮已有明确只列不改授权，不是未授权的历史清理。
2. 四个非空 GDB 目录的长期归属与保留策略：本次作为已知项接受，不要求再次连板才能交付。
3. 产品侧实测收益与代价预算、媒体/完整原始件交付安排：沿用既有后续计划；测试板绝对值不
   外推产品/整机收益，默认 L2 的包外资产前置不因本次 host 自检消失。

全部交付门通过，暂无需要 PM 立即裁决才能继续的事项。上述排序是正式 release / 产品落点
的后续建议，不是本轮未闭合的硬停项。
