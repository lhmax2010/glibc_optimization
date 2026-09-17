# 可移植探针：权限预检停止证据

[报告 §7](../../../../docs/product_floor_reconfirm_20260916.md#71-执行结论可移植性闭合读取范围-stop)。
本轮没有采样脚本推送或 10 分钟序列；主候选在受限视图中未见，不等于不存在。

- [合同推送](contract_push.json)、[614 s 事前门与冻结字节](contract_gate.json)。
- [终态与执行器哈希](state.json)、[660 条远端请求及 3 条客户端调用](commands.jsonl)。
- [基线含 ps 视图](baseline.json)、[工具探测](tools.json)、[逐 PID 预检](permissions.json)。
- [权限摘要](preflight_summary.json)：213 PID、0 可采、4 个 smaps Permission denied、3 个读取时消失、206 个空 smaps。
- [cleanup](cleanup.json)：空；没有产生自身脚本，无需删除。
- [公开/原始双哈希](publication.json)：43 文件；失败读取原文在 raw/，完整原始件本地留存，可按请求提供。

Host 复算入口 `tools/runners/product_floor_reconfirm_20260916/summarize_permissions.py`，命令见报告。
不输出 floor、换出排除或目标不存在结论。空映射绝不计为零堆；原始拒绝与正常进程退出分别记录。
