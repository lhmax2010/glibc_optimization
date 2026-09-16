# 产品板只读 floor 复确认：连接停止证据

终态：`STOP_CONNECTION_FAILED`。英文影响报告先行完成；本段没有任何板端
shell、身份判定、进程画像或新 floor 数据。

- [报告](../../../docs/product_floor_reconfirm_20260916.md)
- [事前推送回执](contract_push.json)：annotated tag 与完成时间。
- [间隔及固定字节门](contract_gate.json)：实际间隔大于 600 s。
- [逐条命令](commands.jsonl)：仅本机 sdb version 与首次 connect。
- [终态](state.json)、[连接原文](raw/connect.txt)、[客户端版本](raw/sdb_version.txt)。
- [发布清单](publication.json)：原始件/脱敏公开件的 SHA-256。

端点统一为 `<PRODUCT_BOARD_IP>`；原行结构保留。host 路径与已有内部别名按
映射脱敏，板端运行路径保留。完整原始件本地留存，可按请求提供。
没有 timeseries/summary；不得将连接失败解释为测试板或产品板身份已经确立。
