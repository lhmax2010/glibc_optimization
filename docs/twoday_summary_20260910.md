# 两日批量执行汇总（2026-09-08 至 09-10）

## 最新续报（2026-09-11）：21 格验收保留，补收尾再次 STOP

PM 2026-09-10 续裁决已落实为“仅补收尾、不得重跑”。本次实际执行为
2026-09-11 02:22:37.086295–02:22:43.678378 UTC，
[终态回执](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/audit.json)
记录 **0 格测量、0 推送、0 包变更、0 governor 写入、0 进程清除**。
原 G1/G2/G3 18 格与 G4 三格全部验收保留，未改字节。

| 段 | 本次状态 | 原因 / 边界 |
|---|---|---|
| host 修复 | 已推 main；真实长度缺陷仍未闭合 | 字节分批、防超长发送与安全测试 167 项 PASS；默认 verify OVERALL PASS。但 3500 本地预算被真实客户端否定 |
| 第 2 段收尾 | **STOP / 未闭合** | 首批 3474 字节服务请求仍返回 `service name too long`，没有 RC/DONE；不得把未执行查询写作无残留 |
| 第 3 段 Demo 集成 | NOT_EXECUTED_STOP_GATE | 不新增 HTML/README/指南头条 |
| 第 4 段 demo-v12 | NOT_EXECUTED_STOP_GATE | 不切 demo、不打 v12、不运行新交付矩阵 |
| 第 5 段复审 brief | NOT_EXECUTED_STOP_GATE | 无 v12，不生成其 brief |

本次已核验：身份/镜像/glibc/MemTotal 不变、原 boot/PID/start tick 连续、无额外交互
会话/匹配负载、工作目录不存在、四核 schedutil；包清单 1263→1263、六个 GDB/依赖均
未安装。audit_start 快照 zram 三项 4096/74/4096 B、告警 0；host 停止后复核原 dmesg
前缀仍在、增量 29 行无 OOM/LMK。**未闭合：包文件残留全清单与 audit_end 健康/boot。**
这些部分核验不是整轮完成，详见[报告 §9](system_level_before_after_20260908.md#9-2026-09-11-只补收尾再次停止)。

UID=5001 无权读取 livedump 目录，因此本次才按方案 A 提权；结束首次 root-off 成功，
最终 UID=5001，无重试、无重启、此后没有板端命令。
[提权必要性](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/READ_ACCESS.txt)、
[最终 id](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/AUTH_ID_AFTER_OFF_1.txt)。
没有已确认待清除我方残留，也没有删除归属未知项；未执行的清单不能填“空”。

### 已验收数字保留（无新测量，尚未集成 Demo）

| 组 / cycle=1 三重复中位 | RSS 下降 MiB / % | MemAvailable 配对净效应 MiB | 耗时 ms | none RSS 下降 MiB |
|---|---|---|---|---|
| G1 mixed | 5.296875 / 40.696279% | **-0.167969** | 1.458574（hook） | 0 |
| G2 medium-only | 5.960938 / 45.322245% | +5.304688 | 1.478167（hook） | 0 |
| G3 解码循环 | 1.820312 / 21.009919% | +1.855469 | 0.843612（hook） | 0 |
| G4 enlightenment | 0.003906 / 0.033659% | NA（无 none） | **1899.209517（含 gdb/ptrace 注入，不是 hook）** | NA |

G1–G3 来自[已验收 TSV](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)；
G4 来自[逐格 TSV](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_cycles.tsv)
与[汇总](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_summary.tsv)。
G4 堆 PD 下降 **88/0/4 KiB**；约 0.03% 是 **RSS 下降百分比中位**，不能误作堆 PD 的
百分比分母。与 [B/B2 272 KiB / 36 KiB / 8–20 KiB](tizen_native_evidence_20260904.md)
共同限定当前证据范围，不外推任意常驻服务永远无收益。G1 系统净效应为负，不得写净增；
none 的“0”只指本表 RSS 下降，不指 MemAvailable 背景波动。全部仍为测试板量级，非产品收益。

### 推库与待裁

执行器先推：`b583821a12314abe21570963418922b409b6024b`；原 18 格结果
`60bea7c63ca2c603351e0ef25df15546e78db05c`，原 G4 结果
`ffd695ef345355da9f8fd9689442a70ffb59b392` 均未重写。
本次原文与编辑前后 SHA 见[39 文件 manifest](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/manifest.json)，
host 检查见[回执](../data/raw/system_level_before_after_20260908/cleanup_audit_20260911/host_checks.tsv)。

需 PM 裁决：是否再次授权只补收尾（逐路径短请求或只读脚本），以完成包文件清单和
审计后健康核验。**不需且不得重跑任何已验收格**；本次没有追加尝试，也未改预算规避停止门。
**当前有效交付仍是 demo-v11**：peel commit `0e8a2f731b13690009badf1ca2acbd57018e7bc8`；
annotated tag 对象 `f1266c0be6c225a2ceb962836380c656758f9427`。没有 demo-v12。

## 历史：方案 A 续跑终态（G4 已观测三格，收尾审计 STOP）

PM 方案 A 的消息日期为 **2026-09-10**，实际 host 命令时间为 **2026-09-09
05:26:22.230806–05:33:19.602955 UTC**；文件名为交付窗口，不倒填日期。
重启后会话 UID=5001，经 PM 本轮授权提权至 root；结束时首次 root-off 成功并复核
UID=5001，授权不外推。原合同/annotated tag 未改，旧 G1/G2/G3 18 格没有重跑。

| 段 | 本次状态 | 证据/原因 |
|---|---|---|
| 1 · host 执行器闭合 | 既有完成；另补本轮显式授权包装层 | 原 114 项 + 授权 9 项测试通过；默认 verify OVERALL PASS；授权包装层已推 `cdab1dbf0d24afefe05c4db1039f58ffde6911b9` 后连板 |
| 2 · 提权/前置门/G4/收尾 | **STOP**；实际三格完成、交付项 NOT_EXECUTED（未完成整轮验收） | 三格观测/健康/完整性通过；六包卸载、目录/进程/governor/非 root 恢复均有原文。残留审计请求过长被 SDB 拒绝，其后卸包后健康核验未执行 |
| 3 · Demo 集成 | NOT_EXECUTED_STOP_GATE | 未把部分通过结果写入 HTML/README/指南头条，未生成完整矩阵证据 |
| 4 · demo-v12 | NOT_EXECUTED_STOP_GATE | 不切库、不执行新交付矩阵，demo-v11 保持有效 |
| 5 · 复审简报 | NOT_EXECUTED_STOP_GATE | 未切 v12，因此无 v12 brief，不联系第三方 |

失败原文只有 `error: service name too long`，没有远端 RC/DONE；请求体 **11800 字节**，
来自按 200 条路径分批的首个残留审计命令。这不是 rpm 卸包失败，不是发现了残留；
已有卸包警告依裁决不阻断，但不能跳过独立的后置审计门。
测量期 OOM/LMK=0、zram 三项 Δ=0、stability 0→0；包清单 1263→1263、无差异。
**缺口：包文件残留清单，以及卸包后的 dmesg/zram/stability/boot 核验。**

| 组（cycle=1 三重复中位） | RSS 下降 MiB / % | 系统 MemAvailable 配对净效应 MiB | trim ms | none RSS 下降 MiB | 状态 |
|---|---|---|---|---|---|
| G1 mixed | 5.296875 / 40.696279% | **-0.167969** | 1.458574 | 0 | 原 18 格保留 |
| G2 medium-only | 5.960938 / 45.322245% | +5.304688 | 1.478167 | 0 | 原 18 格保留 |
| G3 解码循环 | 1.820312 / 21.009919% | +1.855469 | 0.843612 | 0 | 原 18 格保留 |
| G4 enlightenment | 0.003906 / 0.033659% | NA（无 none 臂） | 1899.209517（含 ptrace，非 hook） | NA | 三格已观测，整轮 STOP |

G1–G3 数字来源：[旧逐周期 TSV](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)；
G4 来源：[本次逐格 TSV](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_cycles.tsv)、
[三重复汇总](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/observations/g4_summary.tsv)。
G4 堆 PD 下降为 **88/0/4 KiB**，memps 同样观测到该下降量；静置 faults 为
**1/0、0/0、1/0**（min/maj），独立于 next-cycle 的 NA。G1 系统净效应为负，不改写为
“净增”；none 的系统 MemAvailable 不是零。以上为测试板观测量级，非产品/整机收益。
完整原始件本地留存，可按请求提供；本次三份归档 243 文件均已校验。

命令、提权前后及降权原文、清理边界与复现入口见[报告 §8](system_level_before_after_20260908.md#8-pm-方案-a-授权续跑三格已观测收尾-stop)，
[执行回执](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/execution.json)及
[公开文件哈希清单](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/manifest.json)。
原 18 格结果提交仍为 `60bea7c63ca2c603351e0ef25df15546e78db05c`，host 闭合基线
`6095765575addbd57f421efbf106b0e72da522a5`；本次先推授权入口 `cdab1dbf0d24afefe05c4db1039f58ffde6911b9`。
三格观测、原文及停止报告已推结果提交 `ffd695ef345355da9f8fd9689442a70ffb59b392`。
三份选定 M7 XML 原文及结果回执已推补充提交 `eef3888fbee2996b6e011314d65d7912ae3381cd`。

停止后 host 检查：本轮 **129 项测试通过**，默认 verify **OVERALL PASS**（本地提交前
显式 dirty override，未跳过 host tests），两件 G4 派生 cmp、165 件公开日志哈希和
脱敏零命中均通过。见[检查回执](../data/raw/system_level_before_after_20260908/g4_authorized_20260910/host_checks.tsv)。
随后从 GitHub 远端新克隆 main 的 `eef3888fbee2996b6e011314d65d7912ae3381cd`，
工作树干净、未设置 dirty/test-skip/expected-SHA override：本轮 **129 项测试通过**，
默认 verify **OVERALL PASS**，报告关联链接 **309 项通过**。main 交付身份按设计为
REPORT_ONLY，提示 checkout demo-v11；未把 main 复核冒充交付快照的 required 验收。
这些是 host 归档验证，不是未执行的板端后置健康或 demo-v12 矩阵通过。

待 PM 裁决：是否授权**只修复短命令分批并补齐收尾只读核验**；不需且不得重跑已完成
G4 或旧 18 格。未闭合前保持停止，不以历史 B/B2 的 272 KiB / 36 KiB / 8–20 KiB
背景代替本轮健康门。**当前有效交付快照仍为 demo-v11**：peel commit
`0e8a2f731b13690009badf1ca2acbd57018e7bc8`，annotated tag 对象
`f1266c0be6c225a2ceb962836380c656758f9427`。没有 demo-v12。

## 历史：授权前 UID 停止记录（原文保留）

记录创建于 2026-09-09；文件名为批量交付窗口，不表示尚未发生的 09-10 测量。
**终态：第 2 段在当前 UID=5001（要求 0）处 STOP，后续全部停止。**
当前有效交付快照仍为 **demo-v11**，未创建 demo-v12。G1/G2/G3 已验收的 18 格保留，未重跑。

| 段 | 状态 | 证据/后续门 |
|---|---|---|
| 1 · host 执行器闭合 | 完成，推库后才允许连板 | 114 项本轮 host 测试通过；既有 verify OVERALL PASS（提交前显式 dirty override）；[回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv) |
| 2 · 重启后卫生门 / G4 三格 | STOP / G4 NOT_EXECUTED | 三项身份、glibc、MemTotal 通过；UID=5001 触发 root 硬门，未尝试 root-on；其后卫生与占用项未执行，不能声称现场已恢复 |
| 3 · Demo 集成 | NOT_EXECUTED_STOP_GATE | G4 缺口未闭合；HTML/README/指南头条不改 |
| 4 · demo-v12 | NOT_EXECUTED_STOP_GATE | 不切库、不执行新交付矩阵，demo-v11 保持有效 |
| 5 · 定向复审准备 | NOT_EXECUTED_STOP_GATE | 无 v12，不生成其 brief、不联系第三方 |

本次从 2026-09-09 03:09:54.998761 UTC 的客户端检查开始，至 03:09:58.111178 UTC
停止。只读原文、命令、编辑前后 SHA 见[回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/execution.json)
和[清单](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/read_only_gate/manifest.json)。
本次 0 格测量、0 次注入、0 文件推送、0 包安装/卸载、0 governor 修改，无重启或会话清除。

## 已保留证据与数字边界

既有 18 格及 330 对采样见[公开紧凑件](../data/raw/system_level_before_after_20260908/completed_prefix/completed_points.json)
和[逐周期派生](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)。
不在 G4 完成前把部分矩阵提升为新的 Demo 头条。none 的“零”仅能指确实观测到的进程
RSS/堆 PD 下降；系统 MemAvailable 背景波动与配对净效应必须保留符号，不能强写成零或净增。
系统配对是同相位顺序格，不是同一时刻并行对照。G4 后续数据属于重启后的独立健康时期。

### 保留的 18 格：停止报告用数字表（非完整矩阵 / 非 Demo 集成）

以下仅整理已经验收的 09-08 数据，每档取三重复的 **cycle=1** 中位，与冻结
[summary 定义](../tools/runners/system_level_before_after_20260908/contract.json)一致。
数字逐项来自[completed_cycles.tsv](../data/raw/system_level_before_after_20260908/completed_prefix/completed_cycles.tsv)
同名字段（RSS=`rss_drop_mib/rss_drop_pct`，系统=`memavailable_net_mib`，耗时=`trim_elapsed_ms`）。
这些是测试板负载量级，不等于产品或整机收益；未新增或补齐任何 G4 数据。

| 组 / trim 臂 | RSS 下降 MiB / % 中位 | 配对 MemAvailable 净效应 MiB 中位 | trim ms 中位 | none RSS 下降 MiB | G4 状态 |
|---|---|---|---|---|---|
| G1 mixed | 5.296875 / 40.696279% | **-0.167969** | 1.458574 | 0 | 不适用 |
| G2 medium-only | 5.960938 / 45.322245% | +5.304688 | 1.478167 | 0 | 不适用 |
| G3 解码循环 | 1.820312 / 21.009919% | +1.855469 | 0.843612 | 0 | 不适用 |
| G4 enlightenment | NA | NA（原合同无 none 臂） | NA（含 ptrace，不是 hook 代价） | NA | NOT_EXECUTED |

G1 的系统配对净效应为负，不能写“系统可用内存净增”；none 的系统可用内存也有背景
变化，只有表中进程 RSS 的下降为零。所有前后采样窗口 major fault 为 0；最后一周期
next-cycle 为 NA，G3 冷启动首周期按合同独立记录，不能把这个 0 外推到任意启动。
G4 背景参考仍为[历史 B/B2](tizen_native_evidence_20260904.md)的 272 KiB / 36 KiB，
不能用它们填本次三格。此次没有“业务无代价”的新结论。

## 推库与待裁事项

原 18 格/失败 G4 结果提交：`60bea7c63ca2c603351e0ef25df15546e78db05c`；
执行器来源：`06799668543c014b0552a23720ca7e79304f4346`。
本次第 1 段已推提交：`ff2442ef0b2b8779646a08408fab9bf5bc3e7488`。
停止结果已推提交：`776de96e6c53932f2ed45e28558a9e8035ae2a78`。
所有已完成部分进入 main，未改 demo 分支。

从 GitHub 远端普通 main 克隆结果提交 `776de96e6c53932f2ed45e28558a9e8035ae2a78`，
工作树干净、未使用 dirty/test-skip override：本轮 114 项测试通过，默认 verify
`OVERALL PASS`；main 的交付身份正确标为 REPORT_ONLY，指向 demo-v11。
停止报告链接 235 项通过，11 件公开日志哈希与清单一致，脱敏扫描零命中；
见[检查回执](../data/raw/system_level_before_after_20260908/g4_postreboot_20260909/host_checks.tsv)。
这是 host 修复验证，不是未执行的 G4/整轮健康/交付 v12 矩阵通过。

待周五 PM 裁决：当前 sdb 会话 UID=5001，不满足固定 root 门；请决定如何恢复满足合同的
会话并重新授权 G4，或是否接受缺 G4 的 v12。执行器不得自行 root-on、降门或重启。
PM 手动重启与卸包警告裁决见[台账](pm_decisions.md)；当前卫生/包状态仍需后续重新核验。

有效交付身份：demo/demo-v11 peel commit `0e8a2f731b13690009badf1ca2acbd57018e7bc8`；
annotated tag 对象 `f1266c0be6c225a2ceb962836380c656758f9427`。本轮没有 demo-v12。
