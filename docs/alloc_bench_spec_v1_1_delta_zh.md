> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# alloc_bench 规格 v1.1 增量（相对 v1，Batch 2.5 前置件）

- 依据：`docs/v22_review_arbitration_zh.md` §1.5/§2（三家评审共识的工具偏差修正）
- 原则：v1 行为全部保留（JSON 旧字段不动，schema 升 `alloc_bench_v1_1` 并新增字段）；决定性验收 A1 对新档同样成立（burst 边界按 op 计数触发，不用时间）

## Δ1. 新档 `burst-free-small`（L11/fastbin 作用面）

- 尺寸：16/24/32/40/48/56/64 B 均匀（覆盖 armv7l fastbin 区间并跨 bin 边界）
- 节奏（全部按 op 计数，保证决定性）：
  - 积累相：连续分配 `burst_size`（默认 2048）个对象入突发池（独立于 live 池）
  - 释放相：按 PRNG 决定性顺序释放其中 50%，**不立即复用**（期间继续少量 live 池正常负载，比例 1:8，维持吞吐参照）
  - 滞留相：突发池剩余对象持有 `hold_ops`（默认 4096）后全量释放，进入下一轮
- 设计意图：制造 fastbin 中大量已释放、未复用、未触发 64 KiB consolidation 的积压——这是 mxfast 的作用面

## Δ2. 新档 `unsorted-drain`（L12/unsorted 作用面）

- 尺寸：两组交替——填充组 256 B–4 KiB（对数均匀 5 桶），请求组 96–192 B
- 节奏：填充相分配 `batch`（默认 4096）个填充组对象 → 排空相按决定性顺序全量释放（非 fastbin 尺寸，free 后进 unsorted）→ 请求相立即分配 `batch/2` 个请求组对象，迫使 malloc 遍历 unsorted 链（`tcache_unsorted_limit` 恰在此路径生效）→ 循环
- live 池照常保留小比例背景负载（1:8）

## Δ3. 触碰策略修正（修"大块只脏 2 页"偏差）

- 新增 `--touch-full`：所有分配全量写触碰
- 默认行为变更：**≥128 KiB 的分配无条件全量触碰**（不需要 --touch-full）；<128 KiB 维持 v1 首尾 64 B 策略
- JSON 回显 `touch_policy` 字段

## Δ4. measure 相位周期 Rss 采样（修"仅相位末采样"偏差）

- measure 相位内每 2 s 采一次 smaps_rollup（主线程，计数窗口外语义不变——采样本身不计入 op）
- JSON 新增：`measure_rss_kb_p50 / p95 / max / n_samples`；v1 的 `measure_rss_kb_samples`（末 3 采样）与 `_median` 字段保留不变

## Δ5. 回收面观测（修"idle 恒等于 measure"偏差）

- 新增 `--idle-release PCT`（0–100，默认 0=v1 行为）：进入 idle 相位时按决定性顺序释放 live 池的 PCT%，随后照常静置
- JSON 新增 `idle_release_pct`、`idle_rss_kb_after_release`
- 意图：给 trim/收缩路径一个可观测作用面（L3 的 trim_threshold、后续 L6 类实验都依赖它）

## Δ6. 低优先可选项（不阻塞验收）

- `--stagger-churn`：thread-churn 档的换代 deadline 按线程序号错开 period/threads，削弱同步换代波

## Δ7. 验收门（v1 的 A1–A5 全部保留，新增）

- **A6 作用面自证（关键）**：`burst-free-small` 在 C0 下运行后，measure 末 malloc_info XML 中 fastbin 驻留（`<sizes>` 下 fast 类条目的 total）必须显著非零（≥ 突发池预期滞留量的 50%）——证明新档真的制造了 L11 的作用面，而不是又一个盲区
- **A7 回收面自证**：`mixed --idle-release 50` 在 C0 下 `idle_rss_kb` 必须显著低于 `measure_rss_kb_median`（≥ 理论释放量的 30% 被回收）——证明回收路径可观测
- **A8 决定性扩展**：A1 的同种子比对对 `burst-free-small` 与 `unsorted-drain` 同样通过（op 计数模式）
- **A9 兼容性**：v1 的四档在 v1.1 二进制下、不加新参数时，JSON 旧字段值与 v1 语义一致（触碰策略变更只影响 ≥128 KiB 分配，v1 四档中仅 large-transient 的大块受影响——该差异在报告中显式声明，不算破坏兼容）
