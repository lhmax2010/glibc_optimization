# 已完成前缀：STOP，不是 Demo 完整矩阵

对应 [报告 §6](../../../../docs/system_level_before_after_20260908.md#6-当日续跑结果g4-首格停止不进入-demo-集成)
与原 annotated tag `system-before-after-contract-20260908`。G1/G2/G3 的 18 格、330 个释放点
已完成；G4 首格 M7 赋值失败，G4 数据不补值。后续 Demo 集成和 demo-v12 不执行。

- `completed_points.json`：未舍入逐点转录、原始 metric、逐格健康、18 个完成格及失败 G4
  的归档/逐件 SHA；失败文件目录同时记录字节数，包含 0 B 的 M7 XML。
- `completed_cycles.tsv`：冻结 analyzer 对完整配对的 G1/G2/G3 前缀执行的原口径派生；
  不生成完整矩阵 summary 或 Demo 头条，不把 330 点冒充合同全部 333 点。
- 原始 JSON/XML、全部 memps/1 s 序列和 tar 归档仍在 host 本地留存，可按请求提供；
  公开转录与 SHA 引用不等同于公开完整原件。

发布入口：`tools/runners/system_level_before_after_20260908/publish_stopped_measurement.py`。
它要求明确终态 STOP 和完整 G1/G2/G3 前缀，逐件重验原件及归档；拒绝覆盖已有公开目录。
在完整原始件上复算沿用冻结 `analyze_system_level.py` 的函数，不修改合同与统计逻辑。
