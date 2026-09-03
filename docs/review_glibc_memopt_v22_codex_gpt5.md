> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc memopt v2.2 adversarial review - Codex GPT-5

## 1. Reviewer header

- Reviewer/model: Codex GPT-5
- Date: 2026-07-09
- Audited checkout: `tizen_base`, `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Target document: `docs/tizen_glibc_memopt_design_v2.md` v2.2
- Method: parsed `board_results/batch2/run_summary.tsv` with Python `csv/statistics`; recomputed per-profile median deltas versus C0, paired-by-rep deltas, replicate ranges and stdev; parsed `malloc_info_*_measure.xml` for heap count and allocator `system/current`; rechecked Batch 1 table and C0 noise bands from `docs/board_ab_batch1_report.md`; read `bench/alloc_bench/alloc_bench.c`, `bench/alloc_bench/README.md`, Batch 2 harness, and relevant glibc source anchors.
- Missing input: `docs/ab_batch1_adjudication_zh.md` and `docs/ab_batch2_adjudication_zh.md` are referenced by v2.2 but absent from this checkout. All verdicts below use the batch reports/raw TSV/XML, not those adjudication texts.

## 2. Part A verdict table

| v2.2 change | Verdict | Recomputed numbers | Review |
|---|---|---|---|
| L2 `arena_max=2` demoted Tier 1 -> Tier 2/envelope gated | SUPPORTED for demotion; OVERREACHING for causal story | T-L2 throughput median vs C0: small -2.1%, mixed -52.8%, large-transient -44.7%, thread-churn -45.5%. p99: small 453->640 ns, mixed 1172->26700 ns, large 29439->35224 ns, thread 1481->19397 ns. Thread-churn Rss paired deltas: +26.4/+18.9/+7.4 MB; idle paired +26.4/+18.9/+7.3 MB. T-L2 thread Rss reps are 100228/92700/81044 kB versus C0 73784/73800/73684 kB. Batch 1 C2/C3 idle-service wins outside noise: ServiceR -36/-32 kB, ServiceS -36/-36 kB, pulseaudio -32/-28 kB; pass is inside 92 kB noise; ServiceV secure negative control +0 kB. | The performance cliff is real for mixed, large-transient, and thread-churn, and the thread-churn RSS inversion is directionally robust despite n=3. But "4-thread sustained allocation -45~-53%" silently excludes small-churn (-2.1%). The "retained fragmentation / cross-generation lifetimes" mechanism is not directly proven: `malloc_info` heap count verifies 5->2 heaps, but T-L2 thread-churn `system/current` median is 109952 KiB versus C0 112344 KiB, so RSS inversion is not the same as larger allocator system footprint. Mechanism needs heap/dirty-page timeline evidence. |
| R11: `tcache_count=0` rejected | OVERREACHING | T-L4b throughput median: small -10.1%, mixed -8.2%, large-transient -5.7%, thread-churn -7.7%. Rss median: small -16 kB, mixed +168 kB, large +420 kB, thread +1604 kB. | Data supports rejecting `tcache_count=0` for these four live-pool profiles and for any first-wave default. It does not support a global "do not re-propose" rule: the benchmark creates continuous reuse and almost no sustained per-thread tcache residency backlog. Source also confirms fixed tcache metadata is still allocated (`malloc/malloc.c:3241-3271`), so zero memory return here is unsurprising. |
| L1 stack cache evidence upgraded | SUPPORTED, magnitude shaky | T-L1 only on thread-churn: throughput +0.03%, p99 1481->1479 ns, Rss median -1036 kB. Paired Rss deltas: -3088/-1052/-820 kB; T-L1 replicate range 2168 kB, C0 range 116 kB. | Low cost is supported. The -1.0 MB headline is the median, but one repeat is much better than the other two; use "about 0.8-1.0 MB on this workload, with one -3 MB outlier" rather than a stable scalar. |
| L3 `mmap_threshold/trim_threshold=131072` quantified | SUPPORTED with correction | T-L3 throughput median: small -0.1%, mixed -0.1%, large-transient -4.9%, thread-churn -0.2%. Rss median: small +0 kB, mixed -1680 kB, large -944 kB, thread -208 kB. p99 roughly flat except large +6%. | Correct that L3 is the strongest non-arena survivor and its large-transient cost is just under the 5% target. The memory line "-0.9~-1.6 MB" only holds for mixed/large; small and thread-churn are ~0/-0.2 MB. |
| L11/L12 marked UNTESTED-EFFECT | SUPPORTED as status; NEEDS-MORE-DATA for effect | T-L11 throughput: small -0.2%, mixed -0.4%, large -0.5%, thread +0.2%; Rss: +0/-484/+0/+1160 kB. T-L12 throughput: small -0.2%, mixed -0.2%, large -0.6%, thread +0.0%; Rss: +0/-724/+620/+312 kB. | "Target surface not generated" is correct. "Zero effect" is imprecise: small deltas exist, including thread Rss worsening for L11, but they do not exercise burst-free/unsorted backlog behavior. Low-cost补测 is available; do not leave this as an indefinite parking lot. |
| First-wave bundle L1+L3; bundles with arena_max withdrawn | NEEDS-MORE-DATA for L1+L3 bundle; SUPPORTED for withdrawing arena bundles | There is no L1+L3 grid. Individually: L1 +0.03%/-1036 kB on thread-churn; L3 -0.2%/-208 kB on thread-churn and -4.9%/-944 kB on large-transient. T-B1 with arena_max: throughput small -2.1%, mixed -47.6%, large -38.3%, thread -43.8%; thread Rss median +32888 kB, paired +42.4/+30.9/+33.0 MB. | Withdrawing arena bundles is supported. Calling L1+L3 a "device-validated bundle" is too strong; they are device-validated as separate levers, not together. Mechanisms are mostly independent, so this is probably low risk, but the report should label it as an inferred bundle pending one combined run. |
| M3 amended to microbenchmark pre-screen + real-service shipping gate | SUPPORTED with amendments | Batch 2 has 99 ok rows, zero nonzero exits, performance governor set to `performance`, thermal before-run 34.6-38.9 C, no thermal wait. Harness uses fixed grid order and n=3. | Two gates are the right shape. Missing gates: workload coverage gate (burst-free/cross-thread/pressure), randomized or interleaved run order for small effects, and minimum sample design for TV. The microbench should veto obvious cliffs, not certify global conclusions. |

### Confounders checked

- Governor: Batch 2 captured schedutil -> performance -> schedutil restore (`docs/board_ab_batch2_report.md:54-90`), so CPU frequency is reasonably controlled.
- Thermal: no wait event; before-run max was 34563-38946 mC. This cannot explain -45% arena cliffs, but it can confound sub-1% decisions.
- Run order: harness runs C0 first, then T-L3/T-L4a/T-L4b/T-L11/T-L12/T-L2/T-B1 for each profile (`board_results/batch2/run_batch2_alloc_bench.sh:306-318`). That is not randomized. Large effects survive; small effects should be treated as directional only.
- Sample size: n=3 is enough to flag L2's cliff, not enough to estimate its thread-churn RSS magnitude. T-L2 thread Rss range is 19.2 MB.
- Workload model: all built-ins are live-pool replacement workloads; this is the dominant blind spot for R11/L11/L12.

## 3. Part B - alloc_bench findings

| Finding | Class | Evidence | Consequence |
|---|---|---|---|
| New allocation happens before freeing the replaced object | Structural bias | `bench/alloc_bench/alloc_bench.c:323-357` | This keeps a stable live set and avoids free-first bursts. It favors allocators/tunables that perform well under immediate reuse and suppresses fastbin/unsorted backlog surfaces. |
| Live pool is uniform random replacement | Structural bias | small/mixed profile definitions at `bench/alloc_bench/alloc_bench.c:448-475`; README table `bench/alloc_bench/README.md:51-56` | No long-tailed lifetimes, ownership transfer, or phase-separated free storms. Real services often have request/session/cache phases. |
| Thread churn is synchronized full-generation replacement | Structural bias | per-worker deadline starts at creation (`bench/alloc_bench/alloc_bench.c:286-312`); main recreates joined slots (`:798-817`) | Good stress test for `arena_max=2`, but it may exaggerate cliff shape versus staggered service churn. Add staggered churn before forbidding all thread-churn services. |
| Fixed four threads in Batch 2 | Structural bias | `board_results/batch2/run_batch2_alloc_bench.sh:208-213` | It finds the rpi4 4-core case, not the knee. It cannot answer whether `arena_max=4` is the right compromise. |
| Write-touch is partial for >=128 B | Structural/metric bias | `bench/alloc_bench/alloc_bench.c:163-172`; README `bench/alloc_bench/README.md:58-59` | RSS is intentionally "touched pages", not allocated bytes. That is fine for resident-memory relevance, but theoretical live-set size cannot be used as an RSS lower bound for large objects. |
| Latency samples only `malloc()` every 64th measured op | Metric bias | `bench/alloc_bench/alloc_bench.c:332-365`; spec says malloc-call latency only (`docs/alloc_bench_spec_v1_zh.md:29-31`) | Free, touch, thread create/join, and `malloc_info()` costs are invisible. This can understate tunables whose cost appears on free/consolidation. |
| Measure/idle memory samples occur while worker live pools are still retained | Metric bias | PHASE_IDLE set at `bench/alloc_bench/alloc_bench.c:901`; samples/dumps/idle before PHASE_DONE and join/free at `:903-931` | `idle_rss_kb` means "quiescent with live objects held", not "after workload freed its live set". This is the main reason L11/L12 target surfaces are absent. |
| `malloc_info()` itself allocates after measure samples and before idle sample | Metric bias | `open_memstream`, `asprintf`, `free` in `bench/alloc_bench/alloc_bench.c:701-744`; called at `:911-923` | Measure RSS is clean, but idle allocator state can be slightly perturbed by the attribution dump. Low-kB conclusions should not lean on idle alone. |
| `malloc_info` confirms arena count, but not the L2 causal story | Metric limitation | XML parse: C0 heaps median 5, T-L2 heaps median 2 across profiles; thread T-L2 `system/current` median 109952 KiB vs C0 112344 KiB | Good for verifying tunable effect. Insufficient for "retained fragmentation" attribution; need private-dirty/page-age timeline or per-arena dirty bytes. |

### Fair补测 for L11/L12

1. `burst-free-small` for L11/fastbins:
   - `--threads 4` and `--threads 8`
   - sizes `16,32,64,128,256` B, weights `1:1:1:1:1`
   - live set `8192` and `32768` per thread
   - phases: fill -> sample -> barrier free-all -> sample at 100 ms/1 s/10 s -> refill
   - compare C0, `mxfast=0`, `tcache_count=3`, `tcache_count=0`; record Rss/Pss/Private_Dirty, VmHWM, malloc/free latency separately

2. `unsorted-drain` for L12:
   - sizes `128,256,512` B on armv7l to stay near tcache-eligible/non-fastbin ranges; first fill tcache bins, then free > `tcache_count` objects to spill into unsorted bins
   - next phase allocates same-size objects to force unsorted scan and tcache fill
   - compare `tcache_unsorted_limit=0` vs `3`; collect malloc latency and `malloc_info` before refill, after refill, after 10 s idle

3. `cross-thread-free` for L2/R11 realism:
   - allocate in producer threads, free in consumer threads; vary `arena_max=0,2,4`
   - add staggered thread churn periods `500/1000/2000/5000 ms`, not only synchronized 2000 ms
   - target output: lock-contention cliff, RSS inversion threshold, per-service pre-screen rule

4. `stack-cache-only` for L1:
   - create/destroy threads with minimal heap allocation and controlled stack touch depth
   - cache sizes `0,1,4,40 MiB`, stack sizes default/512 KiB/1 MiB
   - separates stack-cache savings from heap live-set effects.

## 4. Part C - new directions

| Direction | Feasibility verdict | Evidence / literature anchor | Expected magnitude | Cost vs 5-10% budget | Validation cost |
|---|---|---|---|---|---|
| Scan the arena knee instead of binary `arena_max=2`: test `arena_max=4` and maybe `arena_max=cores` per service | FEASIBLE | glibc effective cap formula is core-based (`malloc/malloc.c:1921`, `malloc/arena.c:830-841`); Batch 2 shows 2 arenas is too low under mixed/thread pressure | Could keep most Batch 1 idle win where default creates needless arenas while avoiding much of the -45% cliff; exact RSS unknown | Low if per-service; risk is allocation lock contention | One extra Batch 2 matrix: C0/2/4/default x mixed/thread/cross-thread, n>=5 |
| Per-service allocation contention atlas before any L2 decision | FEASIBLE | Kernel uprobes can trace userspace function entry/return through `/sys/kernel/tracing/uprobe_events` (https://docs.kernel.org/trace/uprobetracer.html); PSI exposes memory stall and triggers under `/proc/pressure/*` (https://docs.kernel.org/accounting/psi.html) | Direct saving is zero; prevents bad rollout and identifies the 10-20 services where allocator tuning matters | Profiling overhead can exceed budget while enabled; use short windows only | 0.5-2 days: uprobe malloc/free counts + stack sampling + `malloc_info` snapshots + PSI around launch/use cases |
| Allocator replacement A/B for selected services, not image-global | FEASIBLE-WITH-CAVEATS | jemalloc documents multiple arenas and thread caches with memory/fragmentation tradeoffs (https://jemalloc.net/jemalloc.3.html); mimalloc documents eager page purging and bounded overhead (https://github.com/microsoft/mimalloc/blob/main/readme.md) | Potential 5-30% RSS/peak-RSS on allocator-fragmented services; zero or negative elsewhere | Can exceed budget or break ABI/interposition assumptions; AT_SECURE blocks env preload | Medium: package allocator, LD_PRELOAD/non-secure A/B, service allowlist, rollback plan |
| MGLRU/working-set gate for TV pressure tests | FEASIBLE-WITH-CAVEATS | Kernel MGLRU is designed to improve reclaim/RAM efficiency and has `/sys/kernel/mm/lru_gen` controls (https://docs.kernel.org/admin-guide/mm/multigen_lru.html) | Primarily PSI/reclaim latency, not per-process RSS. Could be material under TV memory pressure. | Usually below app hot-path budget if kernel supports it; risk is reclaim policy regressions | Low if kernel has `CONFIG_LRU_GEN`: enable/disable A/B under pressure injection; otherwise kernel-build item |
| zram/zswap tuning as north-star PSI lever | FEASIBLE-WITH-CAVEATS | Batch 2 board had 1.59 GB swap (`docs/board_ab_batch2_report.md:109-112`). zram exposes compression and allocator overhead in `/sys/block/zram*/mm_stat` (https://docs.kernel.org/admin-guide/blockdev/zram.html); zswap trades CPU for reduced swap I/O (https://docs.kernel.org/admin-guide/mm/zswap.html) | Does not reduce process RSS; can reduce stalls/OOM and effective memory pressure under overcommit | CPU compression can breach budget on low-end cores; must be pressure-only, not hot-path | 1-2 days: identify swap backend, run pressure harness, compare PSI `some/full`, UI jank, CPU |
| Targeted KSM for duplicate anonymous payloads, not general glibc heaps | FEASIBLE-WITH-CAVEATS | KSM only scans `MADV_MERGEABLE` anonymous memory and warns about scan/COW cost; profit stats are exposed per process (https://docs.kernel.org/admin-guide/mm/ksm.html) | Could save MiB-class only for duplicated immutable anon data across services; likely near-zero for normal allocator churn | ksmd CPU and COW can exceed budget if applied broadly | Medium: one candidate service class, mark explicit ranges, use `/proc/<pid>/ksm_stat` profit threshold |
| Build/link section GC for cold DSOs/tools, not libc core first | FEASIBLE-WITH-CAVEATS | Current spec forces `-O2 -g` (`packaging/glibc.spec:329-356`). GCC `-ffunction-sections/-fdata-sections` plus linker `--gc-sections` can reduce unused sections (GCC docs: https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html#index-fdata-sections; LD docs: https://sourceware.org/binutils/docs/ld/Options.html#index-gc_002dsections) | Mostly FLASH; possible PSS/text-page reduction for cold gconv/NSS/tools if fewer pages touched | Low runtime risk for cold modules, higher ABI/symbol risk for libc/ld.so | Medium: build variant, map file diff, ABI check, launch/page-fault smoke |
| Image-wide dirty-page audit for non-glibc DSOs; glibc itself is already `--enable-bind-now` | FEASIBLE-WITH-CAVEATS | glibc spec already enables bind-now (`packaging/glibc.spec:371-375`), so glibc is not the first target | A few private dirty pages per loaded DSO if lazy binding/GOT writes are still common outside glibc | Startup cost can grow; security usually improves with full RELRO/BIND_NOW | Medium: smaps Private_Dirty before/after launch, `readelf -d/-l`, app startup timing |
| TV-stage sample design: choose by RSS/PSS plus allocation churn, not by threads alone | FEASIBLE | Inventory currently selected by threads/RSS (`docs/board_inventory_run_report.md:206-234`); PSI supports per-system and cgroup pressure views (https://docs.kernel.org/accounting/psi.html) | Prevents false positives; no direct saving | Measurement-only | Low: top 10 RSS/PSS, top 10 malloc/free rate, 3 secure services for mallopt Plan B; n>=7 interleaved runs per cell |
| Pressure-injection acceptance gate | FEASIBLE | Current north-star includes PSI, but Batch 1/2 do not record pressure. PSI triggers can wake userspace on memory stall thresholds (https://docs.kernel.org/accounting/psi.html) | Catches regressions invisible to RSS, especially zram/MGLRU/arena policies | Test-only; no production cost | Low: run service scenario under controlled memory hog, assert PSI `some/full`, p95/p99 UI latency, OOM absence |

## 5. Top-3 challenges

1. v2.2 treats n=3 synthetic microbench data as stronger than it is. It is strong enough to demote `arena_max=2`; it is not strong enough to prove the fragmentation mechanism, the RSS magnitude, or a final service gate.

2. The benchmark's live-pool replacement model systematically under-tests free-burst levers. L11/L12 and parts of R11 are being judged on a workload that almost deletes their intended surface.

3. The north-star says RSS/PSS/PSI, but the evidence is mostly single-process RSS under no memory pressure. TV rollout needs PSI pressure injection and per-service allocation contention data before any system-level conclusion.

## 6. negative_facts

- The referenced adjudication docs are absent from this checkout; no claim here relies on them.
- Batch 2 had 99 result rows, zero nonzero benchmark exits, and zero bad JSON rows (`docs/board_ab_batch2_report.md:9-10`, `:245-250`).
- Batch 2 did set CPU governors to `performance` and restored them (`docs/board_ab_batch2_report.md:54-90`).
- No thermal wait was logged; observed before-run temperatures were far below the 70 C gate in the harness.
- Batch 1 secure ServiceV negative control had env present and +0 kB Rss/Pss delta (`docs/board_ab_batch1_report.md:92-107`).
- `arena_max=2` is active in Batch 2: XML heap count median is 5 for C0 and 2 for T-L2/T-B1 across profiles.
- `tcache_count=0` cannot remove the per-thread tcache struct; `tcache_init()` allocates it unconditionally once tcache is initialized (`malloc/malloc.c:3241-3271`).
- glibc packaging already uses `--enable-bind-now` for glibc itself (`packaging/glibc.spec:371-375`); RELRO/BIND_NOW exploration should target the wider image first.
- Dev-board inventory reports THP as `NA`, so L13/hugetlb effects are not measured here (`docs/board_inventory_run_report.md:180-189`).

## 7. cannot-verify

- Contents of `docs/ab_batch1_adjudication_zh.md` and `docs/ab_batch2_adjudication_zh.md`.
- aarch64 behavior; all Batch 2 numbers are armv7l/rpi4.
- TV kernel covariates: MGLRU, zram/zswap backend and parameters, KSM availability, THP mode.
- Real TV services' allocation-rate, cross-thread-free, phase-change, and burst-free profiles.
- L1+L3 as a combined first-wave bundle.
- L11/L12 under their actual burst-free/unsorted backlog surfaces.
- PSI memory `some/full` impact; current Batch 1/2 reports do not include PSI.
- Per-service allocator replacement feasibility under Tizen service policy and AT_SECURE constraints.
