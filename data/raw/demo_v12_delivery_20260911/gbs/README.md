# demo-v12 候选显式 GBS 构建自证（未交付）

GBS 本身通过，但后续 host 克隆测试触发[交付停止门](../../../../docs/demo_v12_delivery_blocker_20260911.md)。
没有创建 demo-v12，当前有效快照仍为 demo-v11；不得把本次构建通过当成交付矩阵通过。

2026-09-11，干净提交 `4539139956b89d82864a93c57ce68b7b07bdc850` 实际执行
`bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`，RC=0 / OVERALL PASS。
这是 host 构建，不是板上重跑；原 21 格、原合同、验收带和全部 ELF 身份均未改变。

- [执行 proof](execution_provenance.json)：执行前 clean HEAD、dirty=false、Python/UTC、六文件 Git 字节 SHA。
- [checker 原始摘要](build_summary.json)：执行后 proof 字节/JSON 复核、原始 gbs.log SHA、RPM 与三 ELF SHA。
- [入口输出](workflow_summary.tsv)：包含实际命令、所有门与 OVERALL PASS。

耗时 268.052634 s；RPM `glibc-memopt-tools-1.0.0-1.armv7l`，三个 ELF 均匹配
[manifest](../../../../tools/reproduce/deliverables_manifest.json)。本次 RPM wrapper SHA 与
历史归档不同是 REPORT_ONLY，不能替代三个 ELF 的硬哈希门。

publisher 在同一 clean HEAD 校验并原样复制 proof、summary，先输出到 git-ignored
本地目录，再导入本目录；三件文件导入后 `cmp` 均静默。当前 host 测试严格核对六文件
与执行提交、当前 main HEAD、当前文件的字节 SHA；[v11](../../demo_v11_delivery_20260908/gbs/README.md)
按历史提交校验，不伪称其证明新增 L1 入口。provenance 为自记完整性记录，不是签名级远程证明。

原始 gbs.log、RPM/ELF 及完整构建件本地留存于 `board_results/demo_v12_delivery_20260911/`，
可按请求提供；原日志以摘要中的 `gbs_log_sha256` 校验，不能使用过滤 TSV 代替。
清理遇到 root 属主文件，唯一 buildroot 残留按既有规则 REPORT_ONLY，未擅自提权清除。
有权限的操作者确认目录归属后可清理：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-3939591-10_sqp_z
```
