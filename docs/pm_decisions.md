> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# PM 裁决台账

本表只记录会改变交付判读或证据等级的 PM 裁决。实验原始记录不因裁决被抹除；后续文档
用带日期追注说明现行口径。批准人统一记为 `PM`。

| 发现编号 | 日期 | 裁决 | 理由 | 批准人 |
|---|---|---|---|---|
| P0-6 / IDENTITY-WAIVER | 2026-09-03 | Demo 阶段接受既有提交身份与 annotated tag 未签名；正式 release 前统一处理提交身份与仓库可见性策略 | 当前 Demo 验证的是可复现证据链；重写历史会破坏已经引用的提交与标签身份，签名/可见性属于正式发布治理 | PM |
| GST-P50-GATE | 2026-09-04 | 驳回把 gst 业务门从 p99 改为 p50 | p50 可见是需要报告的补充观察，但原合同比较量是 p99；看结果后换门会改变问题定义 | PM |
| GST-MORE-REPEATS | 2026-09-04 | 驳回为改变当前结论而追加重复数 | 已完成批次按固定三重复合同报告；新增重复必须成为独立事前合同的新批次，不能并入旧批次刷数 | PM |
| S4-N3-MEDIAN | 2026-09-03 | B 组按 profile 分别使用三重复中位与发布中心 `±5 pp`；`n=3` 最多吸收一个离群 | 同 seed 不固定 arena 指派，单重复可出现约 1 MiB 台阶；分档中位保留 profile 差异且不把回收字节误列为确定性项 | PM |
| GST-P99-DIRECTION | 2026-09-03 | gst p99 方向为 `REPORT_ONLY`；只把 nearest-rank、重复中位、none 离散带和严格比较的正确执行设为硬门 | 不同板上可能得到不同方向；方向本身是批次业务观察，不应被 workflow 误报为协议失败 | PM |
| V4-CALIBRATION | 2026-09-04 | v4 A 带降级为“校准带”；撤回“GBS 重基线通过”和“GBS 为 HQ 首选 L2”，等待 held-out 验证 | GBS 观测参与中心与半宽的构造，用同一观测落带不能提供独立通过证据 | PM |
| B2-EVIDENCE-LEVEL | 2026-09-04 | B2 实际执行日订正为 2026-09-04；没有独立事前 commit/tag 的“预登记”降级为“固定合同重放” | 原始纳秒时间戳确定实际日期；同一工作轮内先写规格不足以形成第三方可审计的事前凭证 | PM |

对应修复闭环见 [`review_fix_20260903.md`](review_fix_20260903.md)，从 demo-v2 开始的提交与
证据变化索引见 [`changes_since_demo_v2.md`](changes_since_demo_v2.md)。
