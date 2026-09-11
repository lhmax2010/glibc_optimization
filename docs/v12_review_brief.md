# demo-v12 定向复审简报

本简报供第三方自行复核，不联系任何第三方。周末批次为 2026-09-12 至 09-14，
本次实际 host 操作从 2026-09-11 开始；没有连板、提权、重启或重跑测量。

## 1. 固定版本与范围

- 切库 main：`60c102d39fcc6293d3a77ee2081fac83e4f60482`。
- demo / demo-v12 commit：`9ff3fe9c0e91b6be6b599fd6abab6276e8556ade`。
- annotated tag 对象：`26e46c46fdc32c04da08fa31b317800dda25d560`。
- demo 相对切库 main 仅替换/新增 `README.md`、`README.zh-CN.md`。旧 demo-v11
  及历史 STOP 保留。此简报、远端验证回执及周末汇总是切库后 main 上的交付材料，
  不把它们误称为已包含在上述冻结 commit 内。

隔离候选和 GitHub 远端完整矩阵均为 18/18 PASS，各自 129 次启动拒绝通过；
远端完整 / 无 tag / 浅克隆公开复算另行通过。**demo-v12 为当前有效快照**。
详见[机器回执](../data/raw/demo_v12_delivery_20260911/weekend/verification.json)
与[周末汇总](weekend_summary_20260914.md)，不是用“已推标签”替代验收。

## 2. v11 → v12 全部变化分组

| 组 / 发现编号 | 提交或证据入口 | 复审重点 |
|---|---|---|
| SYSTEM-CONTRACT | `54ee2ba`；[固定合同身份](../tools/runners/system_level_before_after_20260908/contract_refs.json) | 原合同/analyzer 未改；board 事前 annotated tag / 推送 / 间隔门仍存在 |
| SYSTEM-G4 / ROOT-A | `ff2442e`、`cdab1db`；[整轮报告](system_level_before_after_20260908.md) | `$fp`、NULL、PID/路径、安全与故障路径；PM 当次 root 授权/恢复，不是默认提权 |
| SYSTEM-CLEANUP | `b583821`、`9f839b2`、`418181e`、`c89c9ab`；[收尾清单](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/README.md) | 一检查一请求、本地 200 字节硬闸、受限核验；四非空目录已知项，不宣称零残留 |
| SYSTEM-ABSOLUTE | `7093d8a`、`4539139`；[组合来源](../data/raw/system_level_before_after_20260908/accepted_matrix/composition.json) | 既有 18 格 + 重启后 G4 三格 + 延期收尾，不是连续新运行；333 个点对，不改历史 STOP |
| DEMO-OVERVIEW | [HTML](demo_report.html#system-effect)、[指南](demo_reproduction_guide_20260901.md#l1-system-before-after)、双语模板 | 绝对值与比例并列；独立中位、负净效应、G4 ptrace 与测试板边界 |
| HOST-TAG-SHA | `b5dd948`；[原停止与闭合](demo_v12_delivery_20260911.md) | host 只认固定 commit/双文件哈希；无 tag 可重放，浅克隆缺对象必须明确失败 |
| TCP-REDACTION / WEEKEND-A/D | `0518993`；[7 行处置与哈希链](weekend_redaction_20260911.md) | 14 地址 token 不可逆占位；测量不变；历史不重写；扫描器负控与默认 verify 硬门 |
| V12-DELIVERY | `60c102d`、`9ff3fe9`；[交付脚本](../tools/reproduce/predelivery_check.sh) | 三克隆 × 六环境、129 注入拒绝、GitHub 远端实克隆；无门被跳过 |

完整历史列表：`git log --reverse --oneline demo-v11..60c102d`；分类补充及 PM
依据分别见 [changes](changes_since_demo_v2.md)、[台账](pm_decisions.md)。没有修改原验收带、
held-out 独立性或既有结论。GBS 原构建 proof 绑定 `4539139`，其六个受保护文件与
v12 逐字节相同；本轮未重跑需提权的真实构建，详见[原构建归档](../data/raw/demo_v12_delivery_20260911/gbs/README.md)。

## 3. 新展示数字（原已验收数据，不是本轮新增测量）

下面均为 cycle=1、各臂三重复的各列独立中位。前/后中位之差不必等于差值中位，
百分比也不是用两个展示中位重新相除；系统是同编号重复/周期的顺序 none 配对，非并行对照。

| 组 | RSS 前 → 后 MiB | RSS 下降中位 | MemAvailable 配对净效应 MiB | 释放点调用中位 ms |
|---|---|---|---|---|
| G1 mixed | 13.015625 → 7.718750 | 40.696279% | −0.167969 | 1.458574 |
| G2 medium-only | 13.152344 → 7.191406 | 45.322245% | +5.304688 | 1.478167 |
| G3 gst | 8.671875 → 6.859375 | 21.009919% | +1.855469 | 0.843612 |

逐值来源：[summary.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/summary.tsv)、
[cycles.tsv](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)。三组 none 的
RSS 下降为 0，不表示系统内存不变。所观测 capture/next-cycle major faults 为 0；末周期
next-cycle 为 NA，不能改写成零。再激活 minor faults 保留在逐周期表。

G4：[逐格](../data/raw/system_level_before_after_20260908/accepted_matrix/cycles.tsv)堆 PD
88/0/4 KiB，RSS 降幅中位 0.033659%；注入中位 1899.209517 ms **含 gdb/ptrace**，
不是上表钩子代价。无 none，系统净效应 NA；静置 minflt 1/0/1 独立标注，不当作下周期代价。
与原生 [B/B2](tizen_native_evidence_20260904.md)的 272 / 36 / 8–20 KiB 同向，
说明常驻守护进程收益很小，不支持外推产品收益。

gst [固定规则复算](../data/raw/system_level_before_after_20260908/accepted_matrix/gst_comparison.json)：
p99 臂间中位差 −1.652834 ms、none 重复离散 11.794149 ms，方向 REPORT_ONLY、按规则未检出，
不等于零代价；与旧 gst 轮不混池。trim/none 使用同一已核验 ELF，运行时调用不改变
二进制体积。整机/产品收益仍待产品板验证；尤其不能把 mixed 的负净效应改写为净增。

## 4. L1 复核命令（host-only）

完整复算：`bash tools/reproduce/reproduce.sh verify`。只看本轮公开派生物：

```sh
system_out=$(mktemp -d)
system_source=data/raw/system_level_before_after_20260908/accepted_matrix
python3 tools/runners/system_level_before_after_20260908/replay_compact.py \
  --points "$system_source/point_source.json" \
  --gst-cycles "$system_source/gst_cycles.tsv" --output-dir "$system_out"
cmp "$system_source/cycles.tsv" "$system_out/cycles.tsv"
cmp "$system_source/summary.tsv" "$system_out/summary.tsv"
cmp "$system_source/gst_repetitions.tsv" "$system_out/gst_repetitions.tsv"
cmp "$system_source/gst_arms.tsv" "$system_out/gst_arms.tsv"
cmp "$system_source/gst_comparison.json" "$system_out/gst_comparison.json"
python3 -m unittest tools.runners.system_level_before_after_20260908.test_accepted_composition
python3 tools/privacy/scan_endpoints.py --json
```

派生输出原文：`PASS system-before-after compact replay cells=21 cycles=333 group_arms=7`；
五个 cmp 均应静默。克隆回归包含完整、无 tag、浅克隆缺对象明确 RC=2，以及获取固定
commit 后仍无 tag/仍浅克隆的 PASS 路径。命令不安装包、不连接板、不运行测量。

## 5. 已知边界

三份旧 TCP 的历史版本仍可见；本次只脱敏当前树，没有清除历史对象。四个非空 GDB
目录按 PM 接受为已知项，本轮没有新板状态结论。媒体与完整原始件仍按既有包外交付策略
提供；公开 L1 不替代完整原始件的独立来源审计。上述已知项与本轮交付检查结果分开陈述。
