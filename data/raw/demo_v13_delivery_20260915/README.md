# demo-v13 交付核验回执（2026-09-15）

仅 host 核验，不是新测量或 GBS 构建证明。N12-05 WITHDRAWN-BY-PM；入口与
current-proof 保持 v12 原字节。[交付报告](../../../docs/demo_v13_delivery_20260915.md)。

| 文件 | 范围 |
|---|---|
| [isolated_matrix.txt](isolated_matrix.txt) | 隔离候选远端，18/18 完整 verify、129/129 启动拒绝 |
| [github_matrix.txt](github_matrix.txt) | GitHub 远端，18/18 完整 verify、129/129 启动拒绝 |
| [hq_demo_verify.txt](hq_demo_verify.txt) | 切库后普通 `git clone --branch demo`，完整 required verify |
| [hq_tag_verify.txt](hq_tag_verify.txt) | 切库后普通 `git clone --branch demo-v13`，detached annotated tag，完整 required verify |
| [verification.json](verification.json) | SHA、形态、核验项与上述文件字节哈希 |
| [gbs_blocker.json](gbs_blocker.json) | 续裁决前真实构建失败和固定源核查，历史原件保留 |
| [partial_verification.json](partial_verification.json) | 续裁决前 main 局部核验，不能替代完整交付验收 |

两份 HQ 输出字节相同是因为 SOURCE 与 required 身份相同；克隆形态分别核验为
`demo` 分支和 detached HEAD。矩阵默认 main 按原规则为 REPORT_ONLY，其余两形态
为 REQUIRED；每次均实际执行所有 host 测试，不用 REPRODUCE_SKIP_TESTS。

矩阵命令：`bash tools/reproduce/predelivery_check.sh --repo-url <remote> --branch demo --tag demo-v13`。
隔离日志只将本地候选远端路径替换为不可逆占位；GitHub 日志保留公开远端 URL。
当前树脱敏不覆盖 Git 历史，既有历史已知项见 PM 台账；未修改测量文件。

切库 main 为 `2bf46f2`，冻结 demo/tag commit 为 `1e8378a`。这些切库后回执随
后续 main 提交提供，不回写冻结标签。完整本地执行日志留存，可按请求提供。
