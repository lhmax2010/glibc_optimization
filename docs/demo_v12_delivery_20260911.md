# demo-v12：host 合同身份闭合与交付验收（2026-09-11）

**终态：host tag/SHA 分离已闭合；全仓脱敏检查触发
`STOP_DELIVERY_REDACTION_TCP_IPV4_MAPPED`，未发布 demo-v12，demo-v11 保持有效。**
隔离候选前两格 verify 通过，但不等于完整矩阵通过；发现停止项即中止矩阵，不继续
GitHub 远端交付验收，不创建正式分支/标签或 v12 review brief。详见 §4。

## 1. 修复边界

按 [PM 方向二裁决](pm_decisions.md)，`STOP_HOST_REPLAY_TAG_DEPENDENCY` 的
host 根因已修复，提交 `b5dd9483548dcbe5827461e5da24d9bee9bf2977`。
[原停止报告](demo_v12_delivery_blocker_20260911.md)及失败原文保留为历史，
不是抹去失败或跳过测试。本轮仅 host；没有板端连接、root 操作或测量重跑。

机器身份见 [contract_refs.json](../tools/runners/system_level_before_after_20260908/contract_refs.json)：

| 对象 | 固定身份 |
|---|---|
| 合同 commit（机器校验） | `54ee2ba8d2819014f3e5656de023ffaf283b4a4a` |
| annotated tag 对象（人工凭证） | `0ef26e51ac9efd18a9dd460b7fefd212ef2d78f3` |
| tag 名（人工凭证） | `system-before-after-contract-20260908` |
| contract.json SHA-256 | `11456d72dcf489194e11478e016aa6202c8a26c2d77e5eaeead64c305975446b` |
| analyze_system_level.py SHA-256 | `c9acb5569382dd029860c801b55ce0f361949c0ad0a8f3b4575eb42b431db2b8` |

`0ef26e51…` 是 tag 对象而非 commit；机器明确要求对象类型为 commit。
从固定 commit 读取两个文件，先核对固定哈希，再与当前文件逐字节比较。
不解析 tag 名、不自动联网补历史、不降级为跳过。浅克隆缺对象时 RC=2，
明确提示 `git fetch --no-tags --unshallow origin` 或获取固定 commit 后重放。
板上开跑仍要求 annotated tag、推送凭证和可审计间隔；原 preflight 未改。

## 2. 验证与交付顺序

- 新增 full / `--no-tags` / depth-1 shallow 实际克隆回归；浅克隆缺对象明确失败，
  获取对象后仍无 tag、仍为浅克隆，公开复算通过。两个合同文件、错误哈希、对象类型
  和常量结构的负控保留硬失败。该模块 12 项、整轮 runner 244 项测试通过。
- clean `b5dd948` 默认 verify 已 `OVERALL PASS`，含全部 host tests、系统复算五份
  派生件 cmp、HTML 重建与链接检查，没有 dirty/skip-tests/expected-SHA 覆盖。
- 保留现有更严格矩阵：三克隆 × 六环境共 18 次完整 verify，加 129 次启动注入
  拒绝检查；不删除损坏工具形态以缩回五环境。先对隔离候选快照运行，再正式切库，
  最后从 GitHub 远端按同一脚本验收。demo/tag 必须 required，main 身份 REPORT_ONLY
  但完整 verify 仍是硬门。矩阵执行结果另行归档；未完成前不宣告 v12 有效。

命令入口：[predelivery_check.sh](../tools/reproduce/predelivery_check.sh)，
L1 入口：[指南](demo_reproduction_guide_20260901.md#l1-system-before-after)。
[真实 GBS 构建归档](../data/raw/demo_v12_delivery_20260911/gbs/README.md)已在干净提交
执行，六个受保护文件的字节与本轮相同；此证据不代替克隆矩阵。

## 3. 已知非阻断残留与数据边界

PM 2026-09-11 接受以下非空目录为已知残留项；内容清单已归档，非我方文件不清除。
本轮不重新查询、不删除，也不声称零残留：

| 目录 | 上轮归档条目（含隐藏项扫描） | 本轮处理 |
|---|---|---|
| `/usr/share/gdb/python/gdb/function` | `__pycache__` | 保留，已知项 |
| `/usr/share/gdb/python/gdb/command` | `__pycache__` | 保留，已知项 |
| `/usr/share/gdb/python/gdb` | `__pycache__ command function` | 保留，已知项 |
| `/usr/share/gdb` | `auto-load python` | 保留，已知项 |

[目录与健康原文](../data/raw/system_level_before_after_20260908/directory_disposition_20260911/README.md)、
[收尾报告](system_level_before_after_20260908.md#121-实际处置与收尾结果)。镜像自带的
`/usr/share/gdb/python` 不动。已验收 18+3 格、分期执行和历史 STOP 回执全部保持原字节。
新增 Demo 章节只呈现既有绝对值：负系统净效应不隐藏、G4 注入含 ptrace 不混为钩子
耗时、none 的零仅指 RSS 下降，均不外推产品或整机收益。

## 4. 新停止门：既有 TCP 原文的编码地址未脱敏

2026-09-11 全仓检查发现以下三份**既有**公开文件共 7 行、14 个 IPv4-mapped
端点仍可解码为板端及 host 的私网地址。IPv4 十进制形式未出现，不代表已完成脱敏。
本报告只列路径/行号，不复制编码地址或可逆替代值。

| 既有文件（相对 data/raw/system_level_before_after_20260908/） | 行号 | 行数 | 原引入提交 |
|---|---|---|---|
| `execution/TCP.txt` | 5、6 | 2 | `60bea7c63ca2c603351e0ef25df15546e78db05c` |
| `g4_authorized_20260910/execution/TCP.txt` | 5、6、7 | 3 | `ffd695ef345355da9f8fd9689442a70ffb59b392` |
| `cleanup_audit_20260911/TCP.txt` | 5、6 | 2 | `7f2d4e1f89f110dad1c3cf463480f4a59915537f` |

只列位置、不再次输出地址的定位命令：

```sh
git grep -n -o -E 'FFFF0000' -- \
  data/raw/system_level_before_after_20260908/execution/TCP.txt \
  data/raw/system_level_before_after_20260908/g4_authorized_20260910/execution/TCP.txt \
  data/raw/system_level_before_after_20260908/cleanup_audit_20260911/TCP.txt
```

该命令只显示固定前缀；每行有两个端点，14 个前缀落在上述 7 行。进一步只读解码
确认与本项目板端/host 映射匹配；不是无关的任意十六进制串。文件在本轮基线
`d6a48f18292b363a85375a74ecb28b781d747022` 已存在，本轮对全部原测量数据的 diff 为空。
此前“新增文件脱敏零命中”成立，但**全仓交付脱敏并非零命中**，不可据此切快照。

按 PM“再次命中停止门即停”规则：没有修改这些原文及其 hash/manifest/来源引用，
没有改写 Git 历史。需 PM 裁决下一轮对这三份公开件做定向脱敏、如何同步严格来源
校验链并保留原始件；历史可见性/是否处理历史亦不擅自决定。四个已知非空目录不是
本次阻塞原因，无需因此新增板端动作。

## 5. 本轮实际验收范围与保留状态

| 检查 | 实际结果 |
|---|---|
| 固定合同 / 两文件字节 / full、no-tags、shallow 回归 | PASS；runner 244 项；其中新增公开组合模块 12 项 |
| clean main 默认 verify | `b5dd948`、`2f0cb95` 均 OVERALL PASS；没有覆盖/跳过测试 |
| 交付/HTML 单元测试 | 64 项 PASS |
| 隔离候选矩阵 | 仅 present-gbs+present-rpm 的 branch 与 tag 两格 required PASS；其余未完成，不计 PASS |
| 启动注入扩展 / GitHub 远端矩阵 | 本次未执行；不得沿用旧轮数字冒充 |
| HTML 重建 | 58184 字节，与提交版 cmp 静默；source `7093d8a60814b706f1f6809cf6b6d282a359c402` |
| 链接 | 交付面 559 / 全仓 1454 项 PASS；双语模板按根入口解释，含 zh README 与 INDEX |
| 脱敏 | 本轮增量零命中；全仓 7 行失败 → STOP |
| 正式交付 | 保留 demo/demo-v11，不切 demo-v12，不生成 v12 review brief |

本地隔离 fixture 的候选 commit 为 `c05c8af503c96c82c04156be8cc22bb6c3b3b087`，
只替换/新增双语 README；它及临时仓内同名 tag 仅用于预切库测试，**没有发布到 origin**，
不是正式交付快照。停止后测试进程组已终止（RC=143），没有继续后续验证或切库。
已推修复 `b5dd9483548dcbe5827461e5da24d9bee9bf2977`、文档与候选配置
`2f0cb95745b9a8df6a6041a021b505e522f9809a`；收线时把交付配置恢复指向仍有效的 v11。
原始 host 检查日志留本地 `board_results/demo_v12_delivery_20260911/tag_sha_closure/`，
公开[停止摘要](../data/raw/demo_v12_delivery_20260911/tag_sha_closure/result.json)不携带私网地址。

有效 demo-v11 commit：`0e8a2f731b13690009badf1ca2acbd57018e7bc8`；annotated tag 对象：
`f1266c0be6c225a2ceb962836380c656758f9427`。未触动这些 refs，也没有本轮板端连接或测量。
