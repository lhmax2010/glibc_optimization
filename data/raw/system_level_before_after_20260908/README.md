# 系统级前后对照：只读停止证据

[报告](../../../docs/system_level_before_after_20260908.md) / [晨间汇总](../../../docs/overnight_summary_20260908.md)。

本轮 0/21 格执行，无新 Demo 测量。合同已事前推送并 tagged，等待超过 600 s 后的
身份/环境检查通过；但两条已有交互会话归属未明，最终 `STOP_OCCUPANCY_UNRESOLVED`。
第 2、3 段不执行，保持 demo-v11。

- `preflight_raw.txt`：选定前置命令的完整输出；只编辑地址、换行。
- `occupancy_excerpt.txt`：两条会话完整 /proc 输出与对应 ps 原行；其余 ps 行未公开。
- `preflight_commands.json` / `occupancy_followup_commands.json`：实际命令、host 起止时间及退出码；板端命令另有原文 RC/DONE。
- `stop_evidence.json`：合同推送时间/实际间隔、自动检查原判定、人工占用停止判定并存、原文件哈希。
- `build_identity.json`：仅 host 构建的观测 ELF 身份，不代表上板验证。
- `host_checks.tsv`：收尾检查与未执行项分列；不存在 v12 验收结果。

`PASS_READONLY_AVAILABILITY` 是自动子检查的历史原输出，不是最终 GO；单个 TCP 连接不能
证明不存在共享逻辑 shell。没有认定他人在主动运行测试，只是不能确认占用解除，故按保守门停止。

公开件由 [publisher](../../../tools/runners/system_level_before_after_20260908/publish_preflight.py)
生成。完整原始件本地留存于 `board_results/system_level_before_after_20260908/`，可按请求提供。
host 侧路径已脱敏，板端运行路径保留；BUILD_ID 有意公开。不公开其他应用完整 ps 参数列表。
