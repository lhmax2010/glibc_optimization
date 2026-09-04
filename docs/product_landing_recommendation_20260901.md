> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# 产品侧 L6 落点建议

- 日期：2026-09-01
- 定位：基于第 1 周已入库证据给出产品侧验证顺序，不授权实现或投放
- 配套材料：[`demo_narrative_20260901.md`](demo_narrative_20260901.md)、
  [`demo_reproduction_guide_20260901.md`](demo_reproduction_guide_20260901.md)

## 1. 启用门清单

以下三项是硬门，缺一项就不应启用 `malloc_trim(0)`。

### 门 A：反信号排除证据

- 在候选释放相位观察 glibc-heap Private_Dirty；若出现物理页可见下降，必须同步检查
  zram、majflt、total PD 和 other-anon。
- 若 PD 实跌且 zram 没有正增长、majflt 不变、total PD 同步下降、other-anon 没有近等幅
  镜像迁移，则该下降分量已经自动归还，是 L6 反信号。`ServiceA` 的完整示范链见
  [`cyclic_rounds.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv)
  与 [`serviceA_large_steps.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_large_steps.tsv)。
- 反信号只排除已经下降的分量；同一目标上的 retained floor 应保留独立标签，不能用
  a 优先级整体覆盖。

### 门 B：M7 驻留确认

- 在业务 free 前后、trim 前取得 `malloc_info`，确认全局 `rest`/`unsorted` 中出现与释放
  相位一致的空闲驻留；S4 的字段合同见
  [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)。
- smaps 只能说明 Private_Dirty 的形态，不能区分 live/bin。没有 M7 时，平台、floor 或
  谷底残渣都只是候选，不得换算 trim 收益。
- `malloc_info` 不导出 tcache 驻留；M7 阴性不等于 allocator 内绝对没有空闲字节，但在
  当前保守合同下仍按“不启用”处理。

> **2026-09-05 量化追注：** `<size from/to>` 整页容量估算在 15 个可配对观测上
> `15/15` 未覆盖实测，且 enlightenment E1 为高估、S4 全部格为低估，不能建立稳定的
> 阈值或修正系数。详见 [`trimmable_estimator_20260905.md`](trimmable_estimator_20260905.md)
> 与 [`validation.tsv`](../data/raw/trimmable_estimator_20260905/validation.tsv)。因此门 B
> 改写为：M7 只确认“存在与相位一致的 allocator 空闲驻留”；量化启用必须另有同目标、
> 同相位的实际 trim A/B 校准并通过门 C。估算器只作离线诊断，不得把 rest、unsorted
> 或几何整页区间直接当可回收量，也不设置产品阈值。

### 门 C：代价预算

- 调用耗时：S4 合成代理两档中位约为 `1.2 ms`
  ([证据 TSV](../data/raw/s4_retention_20260901/b_cycles.tsv))，只能作为测试板基线；产品
  线程模型必须重新测量。
- 再激活 faults：S4 下一周期相对 none 增加 `+1351/+1465 minflt`，`majflt=0`
  ([证据 TSV](../data/raw/s4_retention_20260901/b_cells.tsv))；产品侧需把 faults 换算为
  业务墙钟、帧时延和能耗。
- 并发锁停顿：glibc trim 遍历并锁定 arena；当前合成负载没有给出真实并发分配线程的
  停顿分布，必须补 p50/p95/p99 和最坏值后再定预算。
- 以上三类代价中任一未测或超预算，默认降级为不调用。

> **2026-09-05 四门定稿追注（现行口径）：** 上述“三项”与门 A/B/C 的原始文字保留，
> 作为 2026-09-01 当时的决策记录；现行启用合同将“实测收益”从 M7 和代价中拆成独立
> 硬门，顺序定稿为四条：**反信号排除 → M7 驻留确认 → 同目标、同相位的 trim 探针
> 实测收益达到事前固定阈值 → 代价预算**。上文 2026-09-05 量化追注中的“通过门 C”按
> 旧编号理解；在现行编号中分别对应下面的门 3 和门 4。

| 现行门 | 通过条件 | 失败/不可判时动作 |
|---|---|---|
| 1. 反信号排除 | 按门 A 排除已经自动下降的分量 | 不 trim 该分量 |
| 2. M7 驻留确认 | 按门 B 定性确认相位一致的 allocator 空闲驻留 | 无驻留或不可判则不 trim |
| 3. 实测 trim 探针收益 | 在看结果前为目标/相位登记最低回收阈值；用同目标、同相位的受控 trim 探针或 trim/none A/B 实测，回收量达到该阈值 | 未实测、低于阈值或重复不稳定均不启用；不得用 `rest`、`unsorted` 或直方图估计替代 |
| 4. 代价预算 | 上文旧门 C 的调用耗时、再激活 faults、业务时延/能耗和并发锁停顿均已测且过预算 | 任一未测或超预算则不启用 |

门 3 是必要的，因为“驻留”与“可回收收益”在真实进程上并不等价：enlightenment
历史 E1 即使有约 `5.84 MiB rest` 也只回收 `272 KiB`，真实 UI 活动后的 E4′ 回收
`36 KiB`，Tizen 官方 GST 五格仅回收 `8–20 KiB`
（[`B 格证据`](../data/raw/tizen_native_evidence_20260904/cells_derived.tsv)、
[`B2 格证据`](../data/raw/tizen_native_evidence_b2_20260904/cells_derived.tsv)）。同一 E4′ 的
几何估计为 `2200–7976 KiB`，而严格配对验证 `15/15` 均未覆盖实测，故估算器不能承担
这道量化门（[`估算器报告`](trimmable_estimator_20260905.md)、
[`验证表`](../data/raw/trimmable_estimator_20260905/validation.tsv)）。阈值必须由产品 owner
按目标价值、调用频率与业务预算事前固定，并按新规则先提交合同/analyzer、打轻量 tag；
本报告不从现有代理数字新造统一产品阈值。

## 2. 逐候选行动表

| 候选 | 现有证据 | 当前缺口 | 建议动作 | 前置条件与依赖 |
|---|---|---|---|---|
| `enlightenment` retained floor | 同 PID 段 `+1736 kB` floor，同时存在 `120 kB` 自动回撤；a+b 双标签和告警见 [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | floor 的 live/bin 比例、自然释放钩子、并发线程代价未知 | 先在产品板重放只读时序确认 floor；再在可注入同表型代理上做 M7，只有 M7 阳性才进入 trim A/B | 需 PM 提供当时产品板地址；需目标 owner 确认相位；需可注入代理或受控构建 |
| `ServiceH[ServiceK]` 平台/floor | `2360 kB` 平台高度为上界，周期时序 floor `+868 kB`；release-ratio 新 PID 段另有 `+580 kB`，见 [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv) 与 [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | 两探针代号不能自动视为同一生命周期；PID 重启、平台内短峰和 M7 均需核验 | 以稳定 PID 段为单位重采，固定列表打开/关闭相位；分别报告上界、floor 和 M7，不跨 PID 拼接 | 需 PM 提供当时产品板地址；需遥控注入；需目标 PID/生命周期解析 |
| `ServiceA` 谷底残渣 | P0 到最终谷底净增 `+788 kB`，而周期峰谷分量已自动归还，见 [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv) | 残渣可能是 live 数据，也可能是 bins；现有产品采集无 `malloc_info` | 不再拟合周期峰谷；只围绕谷底残渣做 M7 可行性评估，若无法证明空闲驻留则关闭该候选 | 需 PM 提供当时产品板地址；需产品侧 M7 采集路径；需保持原按键合同 |
| 批量处理释放相位类 | GStreamer 释放相位单进程中位 `48.9451% / 1.359375 MiB`，并扩展到八进程；见 [`batch_release_phase.tsv`](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv) | 旧测量的注入/调试包络不等于产品业务延迟；并发分配时锁停顿仍缺 | 作为第 2 周测试板真实并发目标首选，保留 M7、trim、再激活和锁停顿同批采集 | 需冻结 `gst_loop_decode` 或等价多线程负载；需新镜像兼容二进制；无需产品板即可先做 |

候选表中的内存高度不能相加：它们来自不同探针、不同 PID 合同或不同平台，且尚未通过
同一产品侧 M7/代价门。

## 3. 钩子形态建议

建议形态是“相位触发 + 运行时 M7 自检”，不是定时器扫描，也不是在信号处理函数内
直接调用 trim：

```text
业务相位明确结束
  → 查询该相位是否已有自动下降反信号
  → 确认目标由 glibc/ptmalloc 管理
  → 在非关键线程取得释放前后 M7 快照并解析 rest/unsorted
  → M7 阳性后执行同目标、同相位的受控 trim 探针/A-B
  → 实测回收达到事前固定阈值，且冷却/代价预算均通过
  → 在专用 worker 调用 malloc_trim(0)
  → 记录调用时间、再激活 faults、业务延迟与回滚标志
```

`malloc_info` XML 的生成和解析本身有成本，也可能扰动 allocator。建议：

- 只在自然低频相位取样，不在热路径或每次 free 后解析；
- 在非关键线程生成与解析，记录其独立墙钟和输出大小；
- 缓存近期 M7 判定，并设置冷却窗口，避免重复快照；
- XML 缺失、解析失败、字段异常、超时、tcache-only 不可判、目标使用自带分配器或
  并发预算未知时，一律降级为不 trim；
- 若产品化后无法承受持续 M7，可先在离线校准阶段建立目标/相位 allowlist，运行时仅做
  低频抽检与熔断；但 allowlist 仍必须保留反信号、已校准的实测收益阈值和代价回滚门。

本节只定义接口和失败策略，不写实现，也不把 S4 的合成阈值直接固化为产品阈值。

## 4. 第 2/3 周计划修订

### 第 2 周：测试板真实并发目标的代价闭环

目标是在新 LLVM 测试板上选择 `gst_loop_decode` 或等价多线程负载，在 allocator 线程
真实活动时测量：释放相位 M7、trim 回收、下一次激活 faults、全 arena 锁停顿和业务
响应代理。A/B 必须保留 none 对照，运行顺序和重复数在看结果前冻结。

硬前置：

- RPI4 三重身份门、glibc `2.40` 系和 governor/健康恢复合同通过；版本来源见
  [`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md)。
- 可执行 harness、负载二进制、输入素材与哈希随轮提交；报告自带复现节，遵循
  [`HQ 指南的长期合同`](demo_reproduction_guide_20260901.md#后续板上报告的复现合同)。
- 在执行前冻结并发度、相位、重复数、锁停顿采样方法与验收预算。

### 第 3 周：产品侧 M7 可行性与 Demo 打包

先评估产品进程能否在不改配置、不安装包的约束下取得可信 M7，明确需要 app owner、
签名构建、注入代理或生命周期接口中的哪一种；只有路径可行才安排候选定向测量。
同时把 L1 一键复算、L2 测试板复跑、数字表、失败边界和回滚故事打包为 HQ Demo。

硬前置：

- 需 PM 提供当时产品板地址，并确认产品板访问与遥控注入窗口；
- 需产品 owner 确认候选真实释放相位和 allocator ownership；
- 需先通过产品侧 M7 可行性与数据脱敏审查；若无法取得 M7，则产品启用决策维持关闭，
  Demo 仅展示测试板机制与已知边界。
