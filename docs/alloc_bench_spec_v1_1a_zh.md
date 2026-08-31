> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# alloc_bench 规格 v1.1a 修订（A7 门重定义 + L6 仪器）

- 性质：对 v1.1 增量规格的勘误与小扩充。起因：A7 原门（C0 下 OS 级回收 ≥ 释放量 30%）与 glibc 文档化机制矛盾——内部释放不经 malloc_trim 不归还 OS（设计文档 L6 的存在理由），该门要求被测对象表现出它不具备的行为。**规格方错误，实现方（拒绝用 malloc_trim 造数）处置正确。**
- 独立复验依据：C0 下释放 25124 kB，OS 回收 88 kB；malloc_info free 字节（fast+rest）差量 25927 kB ≈ 释放量 103%。

## Δ8. A7 重定义为仪器自证门（替换原 A7）

**A7a（滞留可观测性）**：`mixed --idle-release 50` C0 下：
- `idle malloc_info` 的 free 字节合计（`<total type="fast">` + `<total type="rest">`）
  相对 `measure malloc_info` 的增量 ≥ 理论释放量的 **70%**；
- 且 `idle_rss_kb` 与 `measure_rss_kb_median` 差值 < 理论释放量的 10%
  （确认 C0 的"释放但滞留"现象在 RSS 侧同样成立）。
两个条件共同证明：释放真实发生、且以可归因的形式被仪器捕获。

## Δ9. 新增 `--idle-trim`（L6 仪器，opt-in）

- 行为：仅当与 `--idle-release` 同时给出时生效——释放完成后、静置开始前，
  主线程调用一次 `malloc_trim(0)`，并在 JSON 记录 `idle_trim: true` 与
  `malloc_trim` 返回值（`idle_trim_ret`）。
- 定位：这是给 L6（主动 trim）的第一个定量仪器；与不带该 flag 的格
  分列，不污染 L3/trim_threshold 语义（Codex 在 v1.1 报告中的顾虑由
  opt-in 边界解决）。
- **A7b（trim 回收门）**：`mixed --idle-release 50 --idle-trim` C0 下，
  OS 级回收（measure_rss_median − idle_rss）≥ 理论释放量的 **30%**。
  若实测不达标，如实报数并 FAIL——这个数字本身就是 L6 的板前预览。

## Δ10. JSON

- schema 维持 `alloc_bench_v1_1`（新增字段向后兼容）：`idle_trim`、
  `idle_trim_ret`、`idle_free_bytes_measure`、`idle_free_bytes_idle`
  （A7a 所用的 fast+rest 合计，进程内直接算好，selftest 不再解析 XML
  做加法——XML 仍照常落盘供人工核对）。

## 验收清单变化

- A7 → A7a + A7b；其余 A1–A6、A8、A9 不变。
