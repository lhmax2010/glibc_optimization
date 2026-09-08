# 2026-09-08 续跑：占用处置证据

PM 确认专供板并批准两个残留登录会话清除，见 [报告 §5](../../../../docs/system_level_before_after_20260908.md#5-pm-裁决后续跑占用处置与执行器闭合)。
`occupancy/` 保留清除前完整 PID 快照、逐信号命令、清除后原文；`occupancy_recheck/`
保留唯一一次只读复核及离线 parser 订正。两份旧 `closure.json` 的 STOP 为采集器自身
PTY 的误报，原文不覆盖；最终 `closure_corrected.json` 根据 PID/PPID 子孙链排除明确的
自身进程，而非依据 IP 或忽略所有 PTY。

`publication.json` 记录原始/公开副本 SHA-256。编辑仅为 CR 归一化、板路由地址与 host
home 脱敏，板端运行路径保留。完整原始件本地留存，可按请求提供。测试日志属于 host
验证，不是板上性能证据；此准备提交尚无正式格结果。
