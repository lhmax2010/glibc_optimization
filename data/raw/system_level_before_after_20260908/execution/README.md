# 续跑终态原文选集

终态为 STOP，详见 [报告 §6](../../../../docs/system_level_before_after_20260908.md#6-当日续跑结果g4-首格停止不进入-demo-集成)。
`manifest.json` 记录每份原文与公开版 SHA，唯一编辑为 CR 规范化、路由 IP 和 host home
脱敏；板端路径保留。`commands.json` 保留全过程命令/时间/host RC，板端 RC/DONE 原文
在对应文件，不用 sdb 自身 RC 代替远端门。

重点文件：`CELL_G4_trim_r1.txt`、`raw/G4_trim_r1/m7.gdb`、`gdb_m7.txt(.stderr)`、
`controller.log`、`GDB_REMOVE.txt`、`FINAL_REVIEW.txt`。G4 未 trim，空 XML 已出现，
目标内部可能的 FILE*/FD 未排除；cleanup PASS 仅指明确检查的目录/包/辅助进程/governor，
不掩盖卸包警告或等同于完整内部状态恢复。

完整原始件本地留存，可按请求提供；本目录不含媒体、完整相位 XML 或 tar 归档。
选集由 `tools/runners/system_level_before_after_20260908/publish_execution_log.py` 生成。
