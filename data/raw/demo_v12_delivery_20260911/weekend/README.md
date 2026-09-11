# 周末 host 交付核验

周末批次标识为 2026-09-12 至 09-14；执行从 2026-09-11 开始，具体 UTC 随回执记录。
没有板端连接、提权、重启或测量重跑。本目录是切库后 main 上的交付回执，
不声称这些后置文件已包含在冻结 demo commit 中。

终态：[verification.json](verification.json) 为 PASS，当前有效标签 **demo-v12**。
隔离 [18 格](isolated_matrix.tsv)与 GitHub 远端 [18 格](github_matrix.tsv)分别全过，
各含 129 次注入拒绝检查。[额外克隆重放](public_replay_clones.log)、
[克隆回归](public_replay_tests.log)、[246 项 runner](runner_tests.log)、
[47 项针对性测试](targeted_tests.log)、[首个 clean main verify](main_verify_0518993.log)、
[冻结快照链接](snapshot_links.txt)、[最终当前树扫描](after_scan.json)分别归档。

- [redaction.json](redaction.json)：初始当前树 4409 文件扫描、三份 TCP 的 14 token/7 行、
  新旧 public 与 manifest 哈希；原始 SHA 不改，原测量不改，Git 历史不重写。
- 交付源 main 为 `60c102d39fcc6293d3a77ee2081fac83e4f60482`；demo 为
  `9ff3fe9c0e91b6be6b599fd6abab6276e8556ade`，仅两个入口 README 不同。
- 全部矩阵使用已有 [predelivery_check.sh](../../../../tools/reproduce/predelivery_check.sh)，
  每格完整 host-tests，不设置 dirty/skip-tests/expected-SHA 绕行；main 身份
  REPORT_ONLY 与 demo/tag required 的既定分工不变。
- [复审简报](../../../../docs/v12_review_brief.md)、
  [定向更正](../../../../docs/weekend_redaction_20260911.md)。

日志中隔离仓位置使用 `<ISOLATED_BARE_REPO>`，本地工作目录使用 `<HOST_REPO>`；
不携带板端点。SKIPPED 只适用于既有可选环境规则，不代表跳过合同、注入或脱敏门。
真实 GBS 构建沿用上一阶段干净源码的 [proof](../gbs/README.md)；六文件字节未变，
不把默认 host verify 的 GBS SKIPPED 伪称为新实际构建。
