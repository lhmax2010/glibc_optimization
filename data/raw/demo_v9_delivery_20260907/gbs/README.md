# demo-v9 显式 GBS 构建自证

2026-09-07，host-only。在干净已提交快照
`de89a10bb187d0a1576aaf24a45b9586c55ba3c1` 上实际执行
`bash tools/reproduce/reproduce.sh gbs --output-dir <new-dir>`，非桩构建，未连接板端。
本记录只验证交付工具，不增加或改变实验测量、验收带、held-out 或技术结论。

- [`execution_provenance.json`](execution_provenance.json)：schema v2，启动时
  `dirty=false`，绑定入口、checker、两 config、manifest、spec 共六文件的 Git 字节。
- [`build_summary.json`](build_summary.json)：checker 记录的执行前 proof SHA、原始
  `gbs.log` SHA、RPM NVR/身份、三 ELF SHA、实际 argv、UTC/耗时与残留位置。
- [`workflow_summary.tsv`](workflow_summary.tsv)：过滤后的入口原文，非原始 GBS 日志。

GBS 返回后 proof 字节与执行前 SHA 相同，再对重读 JSON 完整校验；输出副本再次校验。
同一 clean HEAD 下 publisher 重新校验原始日志、proof、RPM/ELF，仅搬运记录、不补哈希；
两个 JSON 搬运前后及三件公开文件导入后 cmp 均静默。三 ELF 匹配 manifest，
`OVERALL PASS`。后续交付提交不得改变这六个绑定文件，否则需重新构建归档。

原始 GBS 合并 stdout/stderr 的 SHA 为机器摘要中的 `gbs_log_sha256`；原始日志含
host 路径，不公开，完整原始件与 RPM/ELF 本地留存，可按请求提供。收到原始 `gbs.log`
后执行 `sha256sum gbs.log` 对照该字段；publisher 已实际完成这一校验，不能用
`workflow_summary.tsv` 代替原始日志。完整件本地位置为
`board_results/demo_v9_delivery_20260907/`。

RPM 外层 SHA 因归档元数据变化为 `REPORT_ONLY`，不改变 NVR/%files/ELF 硬门。
root 属主文件使清理返回 Permission denied，残留已记录为 `REPORT_ONLY`，没有自动 sudo
删除。拥有权限者应先确认下面唯一临时目录归属，再清理：

```sh
sudo rm -rf -- /tmp/glibc-memopt-gbs-2533297-7mkw722o
```

此自记记录可检查意外/静默篡改，不是签名级远程证明；入口哈希是仓库文件字节，非实际
调用者身份。方法与边界见 [`workflow README`](../../../../tools/reproduce/README.md#gbs-execution-provenance)。
[`v8 真实构建记录`](../../demo_v7_delivery_20260907/gbs/README.md) 原样保留为历史，
其 schema v1 没有本轮新增的日志与扩大文件集合，不作为 v9 执行证明。
