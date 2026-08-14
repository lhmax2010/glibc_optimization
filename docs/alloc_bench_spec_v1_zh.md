> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# alloc_bench 微基准规格 v1（Batch 2 设计冻结件）

- 目的：在 armv7l 真机上产出各 glibc 杠杆的 **Rss × 吞吐/延迟敏感度曲线**，补齐 M3 性能预算门（5–10%）的真机数字；本板守护进程给不出的作用面（小对象紧 churn、大块瞬态、线程 churn、争用）由本工具受控生成。
- 定位：曲线用于杠杆排序与划界；终审仍按 v2.1 §6 在 TV 真实服务上执行。
- 上游依据：`docs/ab_batch1_adjudication_zh.md` §5、设计文档 v2.1。

## 1. 程序形态

- 单文件 C99（`alloc_bench.c`），仅依赖 libc + libpthread，**动态链接**（与生产一致，保证 GLIBC_TUNABLES 生效路径相同）。
- 构建：提供 Makefile，两个目标——host（x86_64，自测用）与 armv7l 交叉（用 Tizen 工具链，`-O2 -g`）。
- 无任何板端依赖（不用 pactl/systemd），纯自压测进程。

## 2. 负载模型

每个 worker 线程执行分配循环，参数全部可由 CLI 配置：

- **尺寸分布**：从直方图抽样（`<size_bytes> <weight>` 行格式）。内置四档 profile + 外部文件加载：
  - `small-churn`：16–256 B 均匀，live-set 小（256 对象/线程），紧分配/释放 —— tcache/fastbin 敏感面
  - `mixed`：16 B–64 KiB 近似对数正态（用 8 个桶离散近似），live-set 中等（4096 对象/线程）
  - `large-transient`：主体 mixed，叠加周期性大块（256 KiB–2 MiB 均匀，持有 100 ops 后释放）—— mmap/trim 阈值敏感面
  - `thread-churn`：mixed 负载 + worker 线程按配置周期退出重建（默认每 2 s 全量换代）—— stack cache 敏感面
  - `external:<file>`：加载 memusage 采集的直方图（校准锚，P2 可选步骤）
- **生命周期**：每线程维护环形 live 池，新分配随机替换池内一个旧对象并 free 之（可复现的复用节奏）；写触碰每个分配的首尾各 64 B（保证页真实变脏，Rss 有意义）。
- **PRNG**：xorshift64，种子 CLI 指定；同种子同参数两次运行的每线程 op 序列必须逐一相同（决定性验收项）。
- **相位**：warmup（默认 5 s，不计数）→ measure（默认 30 s，计数）→ idle（默认 10 s，静置观察保留 Rss）。

## 3. 度量与输出

- 吞吐：measure 相位内 alloc+free 对/秒（全线程合计）。
- 延迟：每第 64 个 op 用 `clock_gettime(CLOCK_MONOTONIC)` 采样 malloc 调用耗时，进程内聚合 p50/p99（固定桶直方图，避免存全量样本）。
- 内存：进程自读 `/proc/self/smaps_rollup`（measure 相位末 3 采样取中位、idle 相位末 1 采样）+ `/proc/self/status` 的 VmHWM；`malloc_info()` 在 measure 末与 idle 末各 dump 一份到文件（进程内调用，这是对守护进程做不到的归因优势）。
- 输出：stdout 一行 JSON（机器可解析：全部参数回显 + 全部指标），原始 malloc_info XML 落盘到 `--outdir`。
- 退出码：0 正常；参数错误 2；运行期错误 1。

## 4. 实验格（Batch 2 矩阵）

profile（4 档合成）× 格：

| 格 | GLIBC_TUNABLES |
|---|---|
| C0 | （无） |
| T-L3 | `glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072` |
| T-L4a | `glibc.malloc.tcache_count=3` |
| T-L4b | `glibc.malloc.tcache_count=0` |
| T-L11 | `glibc.malloc.mxfast=0` |
| T-L12 | `glibc.malloc.tcache_unsorted_limit=3` |
| T-L2 | `glibc.malloc.arena_max=2`（微基准有真实争用，补 L2 的性能代价数字——Batch 1 只有空闲态） |
| T-B1 | 保守组合：`arena_max=2:mmap_threshold=131072:trim_threshold=131072:tcache_unsorted_limit=3` |

- L1（`stack_cache_size=1048576`）只在 `thread-churn` 档加测（其余档无作用面）。
- 每格 3 次重复取中位；重复间差即噪声。默认线程数 = 板上核数（rpi4 为 4）。
- 规模：4 档 × 8 格 × 3 重复 + churn 档 L1 3 次 ≈ 99 次运行 × ~45 s ≈ 75 分钟。

## 5. 验收门（实现质量，host 侧）

- A1 决定性：同种子两次运行，每线程 op 计数与尺寸序列 hash 完全一致。
- A2 ASan+UBSan 构建下全 profile 各跑一次干净（host）。
- A3 度量自洽：C0 下 measure Rss ≥ live-set 理论下界（对象数 × 平均尺寸的量级校验）。
- A4 JSON 输出可被 `python3 -m json.tool` 解析。
- A5 armv7l 交叉编译产物 `file` 验证为 ELF 32-bit ARM 动态链接。

## 6. 明确不做

- 不实现 NUMA/大页/多进程模式；不做图表（曲线绘制在裁决侧）；不在本任务里跑板（板上执行是下一个独立任务）。
