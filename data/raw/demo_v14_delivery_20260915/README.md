# demo-v14 交付核验回执（2026-09-15）

本轮仅回执登记与文案口径订正；未连接测试板、未测量、未构建 GBS。
[交付完成记录](../../../docs/demo_v13_delivery_20260915.md#7-demo-v14-交付完成)。

| 文件 | 实际执行范围 |
|---|---|
| [isolated_matrix.txt](isolated_matrix.txt) | 隔离候选远端：18/18 完整 verify，129/129 启动注入拒绝，RC=0 |
| [github_matrix.txt](github_matrix.txt) | 切库后的 GitHub 远端：18/18 完整 verify，129/129 启动注入拒绝，RC=0 |
| [isolated_snapshot_verify.txt](isolated_snapshot_verify.txt) | 隔离候选默认 host 环境完整 required verify，RC=0 |
| [hq_demo_verify.txt](hq_demo_verify.txt) | GitHub 普通 `git clone --branch demo` 后完整 required verify，RC=0 |
| [hq_tag_verify.txt](hq_tag_verify.txt) | GitHub 普通 `git clone --branch demo-v14` 后完整 required verify，RC=0 |
| [verification.json](verification.json) | 逐格结果、引用、scope、不变性与各输出文件 SHA-256 |

矩阵使用未修改的 `predelivery_check.sh --branch demo --tag demo-v14`。
三克隆 × 五 PATH 加启动注入，即六环境、18 次完整 verify；启动注入的每个克隆
先检查 43 个拒绝变体，再实际执行 clean verify。可选工具存在形态使用受控桩，
不是新 GBS 构建。默认 main 为既定 REPORT_ONLY，demo/tag 为 REQUIRED；未跳过测试。

切库 main `0d91ac6`，demo / annotated demo-v14 peel `7289a47`，tag 对象 `5d60d80`。
demo-v13 原对象 `0353ad4` 保留。本目录为切库后追加到 main 的记录，不回写冻结 tag。
本轮重新执行的 [v13 回执](../demo_v13_delivery_20260915/verification.json) 则已在切库前
入 main，随 v14 快照提供；两轮执行与两个测试对象不混用。

仅隔离矩阵首行的 host 侧远端路径替换为 `<LOCAL_CANDIDATE_REMOTE>`；公开 GitHub
矩阵与 HQ 输出保留原字节。哈希对应这里的公开件。两份 HQ 输出相同是因为验证
同一 commit，克隆形态分别经分支与 detached annotated tag 检查；不是复用一次执行。
三份单次 verify 日志中的 CLI 表格行尾对齐空格也按原字节保留，不作为文档格式修正；
完整文件仍纳入哈希校验与脱敏扫描。
当前树脱敏不宣称覆盖 Git 历史，历史已知项及 1 ulp 双舍入问题仍按 PM 台账保留。
