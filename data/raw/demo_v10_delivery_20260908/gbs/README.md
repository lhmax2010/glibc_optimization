# demo-v10 显式 GBS 构建自证

2026-09-08，host-only；干净提交 `6a10812848f31170bacb70022b1b35fe9d161892`
实际执行 `bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`。本轮只验证
净化后的入口与交付工具，不连板，不新增或改变实验测量、验收带、held-out 或结论。

- [`execution_provenance.json`](execution_provenance.json)：checker 在调用 GBS 前
  记录 clean HEAD、dirty=false 与六文件的 Git 字节 SHA；包括本轮净化入口全文。
- [`build_summary.json`](build_summary.json)：proof 自身 SHA、原始 gbs.log SHA、
  RPM NVR/身份、三个 ELF SHA、实际 argv、UTC、耗时和残留路径。
- [`workflow_summary.tsv`](workflow_summary.tsv)：过滤后的入口输出，包含 OVERALL PASS。

GBS 后重新读取 proof 比较字节，再校验 JSON；输出副本再次校验。同一 clean HEAD 的
publisher 原样搬运并校验原始日志与所有产物；两个 JSON 搬运前后、三件公开文件导入
前后 cmp 均静默。三个 ELF SHA 与 manifest 一致。交付 host 测试同时核验执行提交、
交付 HEAD 与当前文件六项字节，后续改动这些绑定文件须重新构建归档。

GBS 原始日志含 host 路径，不公开；摘要记录 `gbs_log_sha256`，收到日志后可执行
`sha256sum gbs.log` 核对。不能用过滤 TSV 代替原始日志。完整件、RPM/ELF 本地留存于
`board_results/demo_v10_delivery_20260908/`，可按请求提供。

RPM 外层元数据 SHA 漂移与 root 属主 buildroot 清理失败均按现行规则 REPORT_ONLY，
未掩盖 ELF/身份门，也未自动 sudo 删除。拥有权限者先确认本轮唯一目录归属，再清理：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-2890993-g7_r3wup
```

这是自记完整性证据，不是签名级远程证明，入口哈希是仓库内文件字节而非调用者身份。
边界见 [workflow README](../../../../tools/reproduce/README.md#gbs-execution-provenance)。
[v9 归档](../../demo_v9_delivery_20260907/gbs/README.md) 原 JSON/TSV 不变，按原执行
提交复核，不再声称其证明 v10 入口执行。
