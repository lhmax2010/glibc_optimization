# demo-v12：host 合同身份闭合与交付验收（2026-09-11）

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
