# 产品板只读 floor 复确认：连接停止证据

本目录根层保留首次尝试；PM 确认恢复后再次授权的续跑证据见
[resume_20260916](resume_20260916/README.md)，仍在连接门停止，不覆盖原记录。
其后 PM 解决连接并授权板端只读脚本的正式执行见
[formal_board_script](formal_board_script/README.md)：连接与产品身份通过，但执行器的
`timeout` 依赖门 STOP；已有环境基线，没有候选/画像。以下根层说明只指首次尝试。
09-17 可移植性续跑见 [portable_20260917](portable_20260917/README.md)：身份与工具门通过，
受限视图没有可用用户态 smaps，权限 STOP；未推脚本、未采样。

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
