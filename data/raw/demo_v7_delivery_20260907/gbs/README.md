# demo-v7 显式 GBS 端到端构建记录

2026-09-07 在 host 实际执行 `bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`。
这不是模拟 GBS，也未连接板端。完整二进制和日志在本地 `board_results/` 留存，可按请求
提供；这里只发布 [`机器摘要`](build_summary.json) 与 [`workflow 原文摘要`](workflow_summary.tsv)。

RPM 为 `glibc-memopt-tools-1.0.0-1.armv7l`，三个生成 ELF 均逐字节匹配 manifest 的
`gbs_build_sha256`，输出目录四件都复核了哈希。耗时、实际 argv、RPM 的本次 SHA、
记录 SHA 与作用范围详见机器摘要。RPM 外层归档元数据身份与 ELF 可复现身份分开记录。

清理尝试遇到 root 属主文件的 Permission denied，输出
`REPORT_ONLY gbs-buildroot-residue /tmp/glibc-memopt-gbs-1950580-rub_b2fj`。该路径保留；
这是产物核验后的清理残留，不是产物缺失。拥有 sudo 权限者核验具体路径后可执行：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-1950580-rub_b2fj
```

只有上述已解析出的本次临时目录是清理目标。复跑机制与退出语义见
[`workflow README`](../../../../tools/reproduce/README.md)，公开摘要生成器见
[`publish_gbs_build.py`](../../../../tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py)。
