# 产品板连接诊断公开记录

- [报告](../../../docs/product_board_connectivity_diagnosis_20260916.md)
- [完整逐条原文](transcript.md)：stdout/stderr 分列，空流不省略含义。
- [主命令回执](commands.jsonl)、[host 补充回执](host_followup/commands.jsonl)
- [诊断终态](summary.json)、[原始/公开字节双哈希](publication.json)

2026-09-16：ping 可达；目标 TCP/26101 拒绝，TCP/22 可达但 SSH root 认证被拒绝。
没有登录板端、没有任何板端命令执行、没有身份/floor 数据。只在 host 重启 sdb server。
目标 ARP 查询为空，未取得目标 MAC；路由显示经网关，不按 IP 或网关 MAC 认板。

原始件本地留存，可按请求提供。公开件端点及 host 路径已脱敏；行结构保留。
机器记录的流哈希指向未脱敏原字节，publication.json 同时列可公开复核的副本哈希。
