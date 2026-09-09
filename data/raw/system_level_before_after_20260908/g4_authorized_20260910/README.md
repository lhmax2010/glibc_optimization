# G4 单轮授权续跑：STOP 下保留件

PM 授权消息日期为 2026-09-10；实际 host 命令 UTC 为 2026-09-09，目录名不是执行时间。
最终 **STOP / cleanup FAIL / root_off PASS_NONROOT**。三格均已采集并通过逐格校验，
不是成功完整轮次，也不是未发生注入；不得用于宣告 Demo v12 就绪。

- [execution/execution.json](execution/execution.json)：最终回执，含旧 18 格保全摘要与本轮授权生命周期。
- [execution/commands.json](execution/commands.json)：逐条命令、host UTC 和退出码；板端成功还需远端 RC/DONE。
- [execution/manifest.json](execution/manifest.json)：165 件原文选集，编辑前后逐文件 SHA；只移除 CR、替换约定地址和 host home，板端路径与源输出尾随空格保留。
- [observations/g4_points.json](observations/g4_points.json)：三格解析采样、独立静置 faults、健康数据、三份归档与 243 个原始文件的哈希。
- [observations/g4_cycles.tsv](observations/g4_cycles.tsv)、[observations/g4_summary.tsv](observations/g4_summary.tsv)：原冻结 analyzer 的逐格与三重复派生，两件均与本地派生逐字节 cmp。
- `observations/xml/`：三份 M7 原始 XML；其 SHA 已包含在逐文件归档证明中。

阻塞原文：[PACKAGE_RESIDUE_0000.txt](execution/PACKAGE_RESIDUE_0000.txt) 为
`error: service name too long`。200 条路径拼成的首请求 11800 字节被 SDB 请求层拒绝，
没有远端执行/RC/DONE。不是卸包失败或已发现残留。包清单前后相同且六包已卸载，
目录/进程/governor 恢复、一次 root-off 返回 UID=5001 均已核验；但残留路径清单及
随后的卸包后 dmesg/zram/stability/boot 核验未完成。测量期健康通过不覆盖这一缺口。

发布工具：[日志](../../../../tools/runners/system_level_before_after_20260908/publish_execution_log.py)、
[观测](../../../../tools/runners/system_level_before_after_20260908/publish_g4_observations.py)。
完整原始件本地留存，可按请求提供。未合并旧 18 格生成完整矩阵，未改旧结果。
