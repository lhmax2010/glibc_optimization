# Host tag/SHA 闭合与脱敏停止证据（2026-09-11）

本目录是 host 检查输出/机读转录，不是新的板上测量。原 21 格、两个合同文件及历史
失败回执未修改。总体 **STOP_DELIVERY_REDACTION_TCP_IPV4_MAPPED**，不是交付 PASS。

- [result.json](result.json)：固定 commit 校验已闭合；测试范围、三份旧 TCP 文件的
  7 行位置及停止处置。地址不重复公开，完整解释见[交付报告](../../../../docs/demo_v12_delivery_20260911.md)。
- [fixed_main_verify.tsv](fixed_main_verify.tsv)：clean `b5dd948` 默认 verify 输出转录。
- [candidate_main_verify.tsv](candidate_main_verify.tsv)：clean `2f0cb95` 默认 verify 输出转录。
- [partial_local_matrix.tsv](partial_local_matrix.tsv)：隔离本地候选仅前两格 required
  通过；全仓脱敏停止后 SIGTERM/RC=143。不是 GitHub 远端矩阵、不是 18 格通过。

前两份日志仅去掉表格行末的终端对齐空格，内容/行序不改；第三份仅把 host 临时
bare 仓路径替换为 `<LOCAL_CANDIDATE_REMOTE>`，其余输出原样。
没有静默省略 FAIL 后判 PASS。
本地原件留存 `board_results/demo_v12_delivery_20260911/tag_sha_closure/`，可按请求提供。
正式 demo/demo-v11 未动，未发布 demo-v12；旧停止摘要
[host_gate_result.json](../host_gate_result.json)仍为原记录，不用本目录覆盖历史。
