# 周末交付前定向脱敏（2026-09-11 执行）

对应 PM 的 2026-09-12 至 09-14 周末批量授权；实际 UTC 见
[机器记录](../data/raw/demo_v12_delivery_20260911/weekend/redaction.json)，不把批次日期冒充执行日。
全程 host-only，没有板连接、提权、重启、测量重跑或数值调整。

## 1. 定向处置与历史清单

依预授权 A/D，仅改当前转录件地址 token 与 public SHA-256；原始哈希保留，
manifest 附日期说明。端口、状态、行数及空白结构不变。旧 STOP 留存于
[09-11 报告](demo_v12_delivery_20260911.md#4-新停止门既有-tcp-原文的编码地址未脱敏)。

| 文件（相对 data/raw/system_level_before_after_20260908） | 行号 | token 数 | 当前处置 | 历史引入提交 |
|---|---|---|---|---|
| `execution/TCP.txt` | 5、6 | 4 | `<TEST_BOARD_IP>` / `<HOST_IP>` | `60bea7c63ca2c603351e0ef25df15546e78db05c` |
| `g4_authorized_20260910/execution/TCP.txt` | 5、6、7 | 6 | 同上 | `ffd695ef345355da9f8fd9689442a70ffb59b392` |
| `cleanup_audit_20260911/TCP.txt` | 5、6 | 4 | 同上 | `7f2d4e1f89f110dad1c3cf463480f4a59915537f` |

初始全仓 4409 个跟踪文件仅上述 7 行、14 个端点命中，无额外当前树处置项。
三个 manifest 的逐文件引用已更新，旧、新文件与 manifest 哈希均入机器记录。
21 格 point_source、cycles、summary、XML、合同、analyzer、验收带不改。

历史风险：上表引入提交起至更正前版本仍含可逆端点；旧 clone/tag 和对象库不会
随新快照自动清除。历史不重写，不宣称历史零命中；正式 release 的历史可见性
策略建议 PM 优先裁决。本轮按明确授权记为已知项，不阻断当前快照。

## 2. 扫描与回归

[只读扫描器](../tools/privacy/scan_endpoints.py)识别 tcp/tcp6/udp IPv4/IPv6
小端、IPv4-mapped、十进制整数及网络字节序。运行时构造测试样本，不重新写入
真实端点。报告只列位置与编码。两个 publisher 共用该门，无可选 host 参数也生效。
负控覆盖主机 CIDR、无上下文整数/CRC、JSON parse 与地址前缀误匹配。
扫描不编辑；有歧义数字不自动改。默认 verify 的 host-tests 强制全树扫描及回归。

```sh
python3 tools/privacy/scan_endpoints.py --json
python3 -m unittest tools.privacy.test_endpoints
python3 -m unittest tools.runners.system_level_before_after_20260908.test_accepted_composition
```

相关 34 项测试通过，最小 PATH 的扫描器 12 项通过；完整/无 tag/浅克隆公开组合
12 项通过。当前树复扫零命中。合同严格字节门、板端 annotated tag 门均未削弱。

## 3. 文案核对（预授权 B）

提示中的 RSS 41.8% / 45.3% / 16.0% 与同口径公开三重复中位不一致。
按[summary](../data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)
与[原合同复算](demo_reproduction_guide_20260901.md#l1-system-before-after)，保持
40.696279% / 45.322245% / 21.009919%，不以提示近似值覆盖数据。
mixed 系统净效应为负；none 零仅指 RSS 下降；G4 的 1899.209517 ms 含 gdb/ptrace，
不与毫秒量级业务内钩子混列；量级只代表测试板，不是产品收益。

## 4. 验收顺序

单项闭合后先隔离候选完整矩阵，再正式切库验 GitHub 远端。保留三克隆 × 六环境
18 次完整 verify 与 129 次注入拒绝，不删损坏工具形态以缩回五环境。
最终状态随交付汇总发布；未完成前仍以 v11 为有效快照。
