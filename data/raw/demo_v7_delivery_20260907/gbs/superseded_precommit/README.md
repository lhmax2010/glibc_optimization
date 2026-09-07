# 被替代的提交前工作树构建记录

2026-09-07 追注（N7-01）：这里原样保留 demo-v7 的
[`build_summary.json`](build_summary.json) 与 [`workflow_summary.tsv`](workflow_summary.tsv)。
当时入口为提交前工作树版本；entrypoint SHA 由 publisher 事后补写，不能绑定到执行
时刻或对应 git 对象。旧记录不是新的执行 provenance，不能用于证明交付脚本端到端
通过。后续同目录上级的新记录由取锁后、GBS 调用前生成的指纹替代；旧文件不改写。

旧记录的三 ELF 身份与已发布测量不因该工具链自证问题而改变。完整旧日志、RPM/ELF
仍在本地 `board_results/` 留存，可按请求提供；旧 root 属主 buildroot 残留以旧输出
为准，不在本轮自动删除。
