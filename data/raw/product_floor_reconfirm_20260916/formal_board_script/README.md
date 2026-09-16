# 产品 floor 正式执行：产品身份通过、执行器依赖停止

[报告 §6](../../../../docs/product_floor_reconfirm_20260916.md#61-本轮结果与停止原因)。
本目录独立保存本轮证据，不覆盖此前连接停止记录。

- [新合同推送回执](contract_push.json)、[事前间隔/固定文件字节门](contract_gate.json)。
- [终态与采集入口哈希](state.json)：STOP，`timeout_path RC=1`。
- [逐条请求](commands.jsonl)：26 条调用、其中 23 条只读 shell；均保留 host RC，远端以 RC/DONE/FAIL 判定。
- [全部基线](baseline.json)、[原始输出目录](raw/)、[最后失败原文](raw/timeout_path.txt)。
- [收尾列表](cleanup.json)：空；本轮没有推送脚本或生成板端结果，无需删除。
- [发布双哈希清单](publication.json)：31 个原文/状态文件；脱敏只作用于端点、host 路径与既有别名，板端路径和行结构保留。

没有 inventory、timeseries 或 summary。产品身份已确立，不能把缺失的候选画像视为
零值或历史分类复现；也不能把 timeout 查询失败归为身份失败、安装授权或 root 需求。
命令标签 `shell_status` 读取的是 `/proc/self/status`，实际为 cat 进程，不是父 shell。
meminfo 的 zram 行仅一次快照，不是逐秒字节序列。完整未脱敏原文本地留存，可按请求提供。
