# demo-v11 显式 GBS 构建自证

2026-09-11 追注：本归档作为 v11 执行历史原样保留（superseded for current entrypoint）。
v12 新增系统级 L1 复算入口，已由 [v12 新构建](../../demo_v12_delivery_20260911/gbs/README.md)
重新绑定当前入口；本目录 JSON/TSV 未改写，仅按原执行提交验证。

2026-09-08，host-only；干净提交 `3fe95c18a52e86ef45ad97ab0b6323737eecd311`
实际执行 `bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`，RC=0 / OVERALL PASS。
本次绑定 N10-01 修复后的入口：真实 Python 最终调用传回拒绝状态，枚举失败关闭。
不连板，不新增或改变实验测量、验收带、held-out 或技术结论。

- [`execution_provenance.json`](execution_provenance.json)：checker 在 GBS 前采集
  clean HEAD、dirty=false、六文件 Git 字节 SHA、Python 版本与 UTC。
- [`build_summary.json`](build_summary.json)：proof 与原始 gbs.log SHA、RPM NVR/SHA、
  三个 ELF SHA、实际 argv、耗时和残留路径。
- [`workflow_summary.tsv`](workflow_summary.tsv)：过滤后的入口输出，包含 OVERALL PASS。

GBS 后重新读取磁盘 proof，先字节后 JSON，输出副本再次校验；同一 clean HEAD 的
publisher 校验原始日志与产物后原样搬运 JSON。三件公开文件导入前后 cmp 静默。
三个 ELF 与 manifest 一致。当前 host 测试将六文件字节同时核对执行提交、交付 HEAD
和当前文件；以后变更这些文件须重新构建归档，不能事后补写指纹。

GBS 原始日志含 host 路径，不公开；收到原始件后以 `sha256sum gbs.log` 对照摘要中的
`gbs_log_sha256`，不能以过滤后的 TSV 替代。完整件、RPM/ELF 留在
`board_results/demo_v11_delivery_20260908/`，可按请求提供。

RPM wrapper 元数据 SHA 漂移与 root 属主 buildroot 清理失败均按现行规则 REPORT_ONLY；
没有放宽 ELF/身份门，没有自动 sudo 删除。具备权限者先确认本轮唯一目录归属，再清理：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-3100873-xc4uj568
```

这是自记完整性证据，不是签名级远程证明；入口哈希指仓库内文件字节，不代表调用者。
边界见 [workflow README](../../../../tools/reproduce/README.md#gbs-execution-provenance)。
[v10 归档](../../demo_v10_delivery_20260908/gbs/README.md) 原 JSON/TSV 不变，仍按其执行
提交复核，不再声称其证明 v11 入口执行。
