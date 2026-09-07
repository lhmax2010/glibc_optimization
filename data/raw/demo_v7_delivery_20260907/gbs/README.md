# 显式 GBS 端到端构建记录（demo-v8 自证替换）

2026-09-07 在 host 实际执行 `bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`。
这不是模拟 GBS，也未连接板端。完整二进制和日志在本地 `board_results/` 留存，可按请求
提供；这里只发布 [`执行时指纹`](execution_provenance.json)、[`机器摘要`](build_summary.json)
与 [`workflow 原文摘要`](workflow_summary.tsv)。完整本轮原始件位置为本地
`board_results/demo_v8_delivery_20260907/`。

2026-09-07 追注（N7-01）：旧入口为提交前工作树版本，旧 publisher 事后补写的哈希
不能绑定执行时刻；原记录逐字节保留在 [`superseded_precommit/`](superseded_precommit/)。
上级当前记录已由本次替换，目录名仅保留历史引用兼容性。

本次 workflow 的已提交快照为 `707920125d6c0af6993f297214242dd4723e6b94`，
取锁后、调用 GBS 前的状态为 `dirty=false`、porcelain 为空。Python 为 `3.12.3`，
UTC 指纹时间为 `2026-09-07T08:55:01.644319+00:00`；耗时 `392.973037 s`。
publisher 在相同 clean HEAD 下校验并逐字节复制两个 JSON（cmp 静默），没有补写哈希。
执行 commit 与最终归档/交付 commit 不同：后者新增证据与入口文档，但两个执行脚本
字节必须不变；host 测试同时对照执行 commit 的 git 对象和当前交付文件哈希。
`source_commit` 指 frozen payload 源，`workflow_commit` 才是执行工具快照。

RPM 为 `glibc-memopt-tools-1.0.0-1.armv7l`，三个生成 ELF 均逐字节匹配 manifest 的
`gbs_build_sha256`，输出目录四件都复核了哈希。耗时、实际 argv、RPM 的本次 SHA、
记录 SHA 与作用范围详见机器摘要。RPM 外层归档元数据身份与 ELF 可复现身份分开记录。

清理尝试遇到 root 属主文件的 Permission denied，输出
`REPORT_ONLY gbs-buildroot-residue /tmp/glibc-memopt-gbs-2204117-1o6ruhnh`。该路径保留；
这是产物核验后的清理残留，不是产物缺失。拥有 sudo 权限者核验具体路径后可执行：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-2204117-1o6ruhnh
```

只有上述已解析出的本次临时目录是清理目标。复跑机制与退出语义见
[`workflow README`](../../../../tools/reproduce/README.md)，公开摘要生成器见
[`publish_gbs_build.py`](../../../../tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py)。
