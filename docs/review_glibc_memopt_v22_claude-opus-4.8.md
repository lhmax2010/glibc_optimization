> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Adversarial Review — `tizen_glibc_memopt_design_v2.md` (v2.2)

## 1. Reviewer header

- **Reviewer**: Claude Opus 4.8 (`claude-opus-4-8[1m]`)
- **Date**: 2026-07-09
- **Tree / commit**: Tizen `tizen_base` @ `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- **Recompute method**:
  - Re-derived every §0b delta directly from the raw `## Run Summary Table` in `docs/board_ab_batch2_report.md` (99 rows) and the `## 3. 主数据表` + `## 2. 噪声带表` in `docs/board_ab_batch1_report.md`. Median-of-3-reps for throughput/RSS; percent deltas vs the C0 median.
  - Read the tool: `bench/alloc_bench/alloc_bench.c` (all 1134 lines) to find workload/measurement bias.
  - Opened the on-device `malloc_info()` XML attribution files (`board_results/batch2/{thread-churn,mixed}/{C0,T-L2}/rep*/malloc_info_*_measure.xml`) to check the L2 fragmentation causal story against arena-level `<total type="rest">` and heap counts.
  - **Note**: the two files the prompt cites — `docs/ab_batch{1,2}_adjudication_zh.md` — do not exist in the tree; the adjudication content lives in design §0b, which is what I audited. The Batch 2 report contains raw data only (no analysis section).
- **Cell legend** (Batch 2): C0=baseline; T-L1=`stack_cache_size=1MiB`; T-L2=`arena_max=2`; T-L3=`mmap_threshold=trim_threshold=131072`; T-L4a=`tcache_count=3`; T-L4b=`tcache_count=0`; T-L11=`mxfast=0`; T-L12=`tcache_unsorted_limit=3`; T-B1=bundle.

**Load-bearing context the doc under-weights**: every number in Batch 1/2 comes from **one Raspberry Pi 4** (`uname 6.12.80-arm-rpi4-v7l`, device `rpi4`, 4×A72, ~3.9 GB RAM, `overcommit_memory=0`, `THP=NA`, governor pinned `performance`). It is armv7l (correct arch) but **not TV silicon**, and it sits at a single value of the two covariates the doc itself calls decisive (THP, cores). See Challenge 1.

---

## 2. Part A — data→conclusion verdicts (recomputed)

Verdicts: **SUPPORTED** / **OVERREACHING** (conclusion exceeds data) / **NEEDS-MORE-DATA**.

| Claim (v2.2) | Verdict | Recomputed from raw | Confounder / correction |
|---|---|---|---|
| **L2 demoted T1→T2** (perf cliff) | **SUPPORTED** | throughput Δ vs C0 median: mixed **−52.8%** (2156430→1018058), large-transient **−44.7%** (1402009→775583), thread-churn **−45.5%** (1895265→1032507); p99 mixed 1172→26700 = **×22.8**. All ≫10% ceiling. | Cliff is **oversubscription-specific**: `malloc_info` shows 4 threads forced onto **2 arenas**. small-churn (tiny objects, tcache-served) is only **−2.1%** (3227333→3159956) — so the cliff is not universal; it is a function of contention the bench maxes out (threads=nproc). |
| **L2 churn Rss inverts to +8~+26 MB** | **SUPPORTED (direction) / NEEDS-MORE-DATA (magnitude)** | T-L2 thread-churn RSS = **100228 / 92700 / 81044** kB vs C0 **73784** (C0 noise = 116 kB). Δ = **+26.4 / +18.5 / +7.3 MB**; median **+18.5 MB**. All 3 reps ≥ +7 MB over a 0.1-MB-noise baseline → direction robust. | **19 MB inter-rep spread on n=3.** `malloc_info` explains it: retained-free (`<total rest>`) in the 2 arenas swings **9.3 MB (rep3)→29.8 MB (rep1)** — stochastic consolidation state at sample time. The "+8~+26" band is honest but the point estimate is soft; **n≥10 needed** (Part B). |
| **L2 idle-daemon win −28~−36 kB (Batch 1)** | **SUPPORTED-WITH-CAVEAT** | ServiceR −36/−32, ServiceS −36/−36, pulseaudio −32/−28 kB (each ≥4× its noise band). BUT **pass = +12/+24 kB** (wrong sign; noise band 92 kB — uninformative) and ServiceV = +0. | The batch1 "arena approx count **2→0**" driving the win is **mechanistically unexplained**: `arena_max=2` *caps*, it cannot *evict* to zero secondary arenas. Batch 2 shows `arena_max=2` holds **2** arenas, never 0. The −32 kB is real but its arena-count attribution method is undocumented → treat as weak corroborant of the far stronger Batch-2 steady-state result. |
| **L2 memory effect (overall framing "small but free in idle daemons; negative outside envelope")** | **OVERREACHING (understates the win)** | In **steady-state** mixed/large-transient, T-L2 RSS = **−9.3 MB** (115176→105920) / **−9.2 MB** (114620→105404). `malloc_info`: 5 arenas/12.2 MB-free → 2 arenas/10.5 MB-free. | The steady-state win is **~9 MB, not "kB-small"**. L2 is memory-**positive** in sustained multi-threaded allocation and only inverts under thread churn. The doc credits only the Batch-1 kB figure and the churn inversion, dropping the 9 MB steady win from its risk/benefit. |
| **R11: `tcache_count=0` rejected — full price, ≈0 return** | **SUPPORTED** | throughput Δ: small-churn **−10.1%** (3227333→2901149, touches ceiling), mixed **−8.2%**, large-transient **−5.7%**, thread-churn **−7.7%**. Memory Δ: **−16 kB … +1.6 MB** (net **neutral-to-negative** across all 4). | Robust and **mechanistic, not workload-specific**: evicted chunks migrate to bins (retained, not returned) → the ≈0 memory return holds regardless of profile. The live-pool workload is not "unfairly" minimizing tcache benefit — tcache_count=0 has no memory upside anywhere by construction. Rejection is sound. |
| **L1 upgraded (churn −1.0 MB @ 0.0%)** | **SUPPORTED** | T-L1 thread-churn throughput median 1895780 = **+0.0%**; RSS median 72748 vs 73784 = **−1.0 MB** (reps 70696/72748/72864 all < C0). | Modest (rep1 −3.1 MB, rep2/3 −0.9 MB) but consistent sign and truly zero cost. Tier-1 status justified. |
| **L3 quantified (≈0% except −4.9% large; −0.9~−1.6 MB)** | **SUPPORTED** | large-transient throughput **−4.9%** (1402009→1332664); mixed/small/churn **≈0%**. RSS: large-transient −944 kB; mixed **−1.7 MB** (115176→113496). | Matches. Strongest Tier-2 survivor confirmed. Caveat: bench large blocks touch only 128 B (Part B) → L3's real-world mmap-return benefit is likely **larger** than measured, not smaller. |
| **L11/L12 UNTESTED-EFFECT (0 cost, 0 effect)** | **SUPPORTED** (as "untested", not "ineffective") | All profiles ≈0% cost, ≈0 memory (mxfast mixed RSS 114804 vs 115176; unsorted_limit likewise). | The 0-effect is a **tool artifact**, correctly not read as rejection. The blind spot is **cheaply closable** — one burst-free profile (Part B). Deprioritizing without running that profile is defensible only as a scheduling call, not an evidentiary one. |
| **First-wave bundle L1+L3; withdraw any arena_max bundle** | **SUPPORTED** | L1+L3 both ≈0 cost, device-validated. T-B1 (bundle w/ arena_max) inherits cliff: mixed **−47.6%**, thread-churn RSS median **+32.9 MB** (106672 vs 73784). | Correct. But "withdraw the class" conflates `arena_max=2` with `arena_max` at any value — the un-oversubscribed settings were never tried (Challenge 3 / Part C). |
| **M3 dual gate (microbench pre-screen + real-service ship gate)** | **SUPPORTED, incomplete** | — | Sound structure, but the pre-screen tool has the four blind spots in Part B; and neither gate measures the **PSI north-star** at all (Part C). |
| **T2 device-verified (ServiceV AT_SECURE=1, env present, 0 effect)** | **SUPPORTED** | Batch1 §4: ServiceV C3 env `stack_cache_size=…:arena_max=2` present in `/proc/pid/environ`, RSS/Pss Δ = **+0/+0**, arena 1→1. Clean negative control. | Strongest single datum in the set — a true positive control for the AT_SECURE gate. |

---

## 3. Part B — audit of the microbenchmark (`bench/alloc_bench/alloc_bench.c`)

### Structural (workload-model) bias — all four push conclusions toward "no effect / harmful"

1. **Uniform 1:1 live-pool replacement holds occupancy constant → cannot generate burst-free backlog** (`worker_main` L353-358: every alloc frees one *random* existing slot; `pool` stays exactly `live_set` full). Fastbins/unsorted bins therefore never accumulate beyond steady turnover. This is the *direct structural reason* L11 (mxfast) and L12 (tcache_unsorted_limit) show zero effect — their target surface (many frees without reuse) is never produced. **The doc's UNTESTED-EFFECT verdict is a property of this loop, not of the levers.**
2. **`threads = nproc = 4`, all in tight malloc loops → maximum arena contention** (`parse_args` L532-533). `arena_max=2` on 4 hot threads = 2:1 oversubscription — the worst case. Real services rarely run every core in a malloc loop; the **−45~−53% cliff is an upper bound**, and L2's demotion rests on it.
3. **Large allocations touch only 128 B** (`touch_alloc` L167-173: first+last 64 B for size≥128). A 2 MiB large-transient block contributes ~1–2 resident pages, not 2 MiB. So large-transient RSS is metadata-dominated and **L3's mmap-return benefit is understated** for real, fully-written large buffers.
4. **The "idle" phase holds the live pool and never trims** (`worker_main` L293-297: PHASE_IDLE just spins; no free, no `malloc_trim`). Confirmed in data: `idle_rss ≈ measure_rss` in **all 99 rows** (e.g. mixed C0 115176→115212). So the bench **never measures reclamation / return-to-OS** — precisely the regime where L6 (proactive trim) and the release benefit of every lever live. The tool measures *steady-state retention* well and *burst-release* not at all.

### Measurement (metric-timing) bias

5. **The 3 RSS samples are 100 ms apart** (`run_benchmark` L903-910) — far inside the **2000 ms** thread-churn period. All 3 land in the same churn phase → correlated, so median-of-3 does **not** reduce cross-generation variance. This is why n=3 cannot pin the +8~+26 MB band (the real variance is inter-*rep*, driven by which point of the churn cycle rep-start aligns to).
6. **`VmHWM` (peak RSS) is captured but dropped from the report table** (`read_vmhwm_kb` L658-671, emitted in JSON L1088). For churn/burst workloads peak RSS is more decision-relevant than an instantaneous median; surfacing it would stabilize the L2 churn magnitude.
7. **Latency is sampled on `malloc()` only, not `free()`** (L332-342), every 64th op. Under arena-lock contention both sides wait; p99 therefore captures only half the contention path (still directionally valid, magnitude possibly understated).
8. **RSS sampled with workers alive-but-idle, before join** (L901 sets IDLE, then L903 samples). Fine for steady state, but it means "idle_rss" includes live threads' TLS/stack — not a quiescent-process figure.

### Suggested补测 profiles/parameters (cheap, close the blind spots)

- **`burst-free` profile** (fixes #1, gives L11/L12 a fair surface): allocate `N` objects into a growing pool, then free a large fraction *without* re-allocating, then idle+`malloc_trim`. Concretely: `--live-set 8192`, phase pattern "fill → free 75% in a burst → hold", small sizes 16–256 B to load fastbins/tcache. Measure idle_rss after the burst-free with vs without `mxfast=0` / `tcache_unsorted_limit=3` / `tcache_count`.
- **Contention sweep** (fixes #2, feeds Part C1): run `mixed` at `--threads 1,2,4,8` × `arena_max 2,3,4,5` to map the perf/RSS knee instead of a single 4-thread/arena_max=2 point.
- **Full-touch large mode** (fixes #3): a `touch=full` flag so large blocks are fully written → real L3 benefit.
- **Reclaim phase** (fixes #4): after measure, drop the live pool and call `malloc_trim(0)` before idle sampling → lets the bench score L6 and return-to-OS.
- **Adaptive reps** (fixes #5): n≥10 (or until CV<5%) for any cell whose inter-rep RSS CV>5% — currently only thread-churn needs it (small-churn CV<0.3%).

---

## 4. Part C — better directions (open exploration)

| # | Direction | Feasibility | Evidence / anchor | Expected magnitude | Perf cost vs 5–10% | Verification cost |
|---|---|---|---|---|---|---|
| **C1** | **Sweep `arena_max ∈ {3,4,5}`, don't jump to 2.** The cliff is 2:1 oversubscription (4 threads/2 arenas). `arena_max`≈cores gives each hot thread its own arena → no lock cliff, while still capping the effective ~5–8 default. | **FEASIBLE — highest value/cost** | `malloc/arena.c:828-842` (cap = `NARENAS_FROM_NCORES` only after `narenas>arena_test`); Batch2 malloc_info: C0=5 heaps, T-L2=2 heaps; cliff absent at low contention (small-churn −2.1%) | Banks much of the −9 MB steady win with perf cost **«10%** (no oversubscription); intermediate churn behaviour | Likely well under budget | **1 matrix column** — reuse Batch-2 harness |
| **C2** | **Kernel-side memory stack (dominant, orthogonal, hits PSI north-star directly).** Board already has 1.5 GB swap (`free`: Swap 1591412) — configure **zram+zstd/lz4**; enable/tune **MGLRU** (kernel is 6.12 → `/sys/kernel/mm/lru_gen/enabled`); evaluate **KSM** for launchpad-forked look-alike processes. | **FEASIBLE** (image/kernel config) | `board_ab_batch2` covariates (kernel 6.12.80, swap present, THP=NA); north-star = PSI (design §1) | **10s–100s MB** effective / large PSI improvement — dwarfs the KB–MB glibc tunables | CPU for compression/scan — **not** on the alloc-path budget | Medium (kernel config + PSI runs) |
| **C3** | **Make L2's precondition gate executable via `malloc_info` time-series (reuse M2).** Sample arena count + per-arena `<total rest>` over a representative scenario → oversubscription ratio = busy-threads/arenas → pick `arena_max` per service. | **FEASIBLE — cheap** | M2 already dumps `malloc_info` (`dump_malloc_info_file` L701); the attribution I used (`<total type="rest">`, heap count) is exactly this signal | Turns "profile contention first" from prose into a one-shot snapshot decision | none (offline) | **Near-zero** — tooling exists |
| **C4** | **Actually measure the PSI north-star.** Inject controlled memory pressure (`stress-ng --vm` or an allocator) alongside a candidate service and compare PSI `some/full avg10` with vs without the L1+L3(+arena_max) bundle. | **FEASIBLE** | design §1/§6 name PSI as north-star but **no lever was ever measured against it** — only smaps_rollup | Directly scores the metric the plan optimizes for | test-only | Low–medium |
| **C5** | **`vm.overcommit_memory=2` as a *tested* lever, not a parked note.** malloc_info shows 10–30 MB arena retained-free that, under overcommit=2, is released by commit-freeing `PROT_NONE` remap instead of `MADV_DONTNEED`. | **FEASIBLE-WITH-CAVEATS** | `malloc/arena.c:516-525`; `malloc-sysdep.h:34-54`; board `overcommit=0` (so all Batch data is on the non-releasing path) | Could cut the +18 MB churn inversion and deepen steady wins | none on alloc path; **system-wide alloc-failure semantics change** | Medium (needs whole-image validation) |
| **C6** | **Loader-side PSS: full RELRO + `bind-now` so GOT pages go read-only → shareable.** Partial-RELRO GOTs are private-dirty per process; `-z now -z relro` (or `LD_BIND_NOW`) makes them clean/shared across the many TV processes sharing libc. | **FEASIBLE-WITH-CAVEATS** | different axis from allocator; gconv already conditionally BIND_NOW (`iconvdata/Makefile:67-68`) — audit the rest | KB-per-DSO × many processes of **PSS** | startup latency (eager binding), **not** alloc-path | Medium (spec flags + PSS A/B) |
| **C7** | **Scoped `mimalloc`/`jemalloc` A/B for the 1–2 worst churn services.** glibc's arena model produces the +18 MB churn fragmentation; modern allocators bound per-thread cache without arena explosion. | **FEASIBLE-WITH-CAVEATS** | Batch2 thread-churn T-L2 retained-free 29.8 MB; `nss` etc. dlopen retained — LD_PRELOAD blocked under AT_SECURE (design §8) | Could reverse the churn inversion; unknown steady tradeoff | integration/latency risk; +200–800 KB flash | Medium-high |
| **C8** | **THP=`madvise`/`never` system-wide as an RSS lever** (not just L13's covariate/gate). If TV kernel defaults THP=`always`, 2 MiB internal fragmentation inflates RSS across *all* processes. | **FEASIBLE** | design Q3 treats THP only as gate; `malloc/arena.c:53-56` shows hp inflation | Process-wide RSS; larger than per-lever tunables | possible minor TLB perf change | Low (one sysfs write + A/B) |
| **C9** | **Re-run the whole sensitivity matrix on real TV silicon before shipping.** THP mode, core count and RAM (the covariates that set L13, the arena cliff, and PSI) all differ from rpi4. | **REQUIRED validity step** | board = rpi4 (Challenge 1); design M5 records covariates but all data is one point | Prevents shipping a board-tuned bundle that regresses on TV | — | Medium (needs TV board) |

---

## 5. Top-3 challenges (design-level)

**Challenge 1 — The entire evidence base is one Raspberry Pi 4, and it sits at the single covariate point where the two biggest levers are guaranteed dormant.** `rpi4`, kernel 6.12.80, **THP=NA**, **overcommit=0**, 4×A72, ~3.9 GB RAM. The doc's own M5 says results across differing covariates "are not comparable" — yet 100% of Batch 1/2 comes from one covariate vector, and it is the vector where L13 (stack_hugetlb) is a **guaranteed no-op** (THP absent, admitted) and where arena shrink can **never** release commit (overcommit=0, so every RSS number is on the `MADV_DONTNEED`-only path). The arena contention cliff depth is set by core count (4 here; TV SoCs vary), and PSI/pressure behaviour is set by RAM (TV has less). The safe first-wave (L1+L3) is safe precisely because it is covariate-insensitive — but the doc presents the board curves as the general response surface. **Board data proves feasibility and direction; it cannot set the shipping magnitudes, and the doc should say so per-lever.**

**Challenge 2 — The pre-screen tool has four structural blind spots that all bias toward "no effect / harmful," and two of the doc's verdicts are really verdicts about the tool.** Uniform 1:1 live-pool replacement (never bursts-and-frees) → L11/L12 *cannot* show effect; nproc-thread tight loops → L2's −50% is a max-contention corner; 128-B touch of large blocks → L3 understated; idle phase holds the pool and never trims → `idle_rss≈measure_rss` in all 99 rows, so **reclamation is never measured**. The doc labels L11/L12 "UNTESTED-EFFECT" but then deprioritizes them — the honest move is to run the one cheap burst-free profile that would actually test them (Part B) before ranking. A bench that only measures steady-state retention should not be the sole pre-screen for levers whose entire value is burst-release.

**Challenge 3 — L2 is demoted on a perf cliff whose confirmed −9 MB steady-state RSS win is uncredited, and the setting the data points to (arena_max = cores) was never tested.** `malloc_info` proves the cliff and the +18 MB churn inversion are the same phenomenon: `arena_max=2` on 4 threads is 2:1 arena oversubscription, and the churn RSS is dominated by retained-free that swings 9.3→29.8 MB across three reps (n=3 cannot pin it). In steady multi-arena workloads the identical lever gives **−9.2/−9.3 MB**. The design's response space is two points — default (~5 arenas) and `=2` — and it generalizes to "withdraw the arena_max class from bundles." But `arena_max ∈ {3,4,5}`, where threads are not oversubscribed, is the obvious knee that could bank most of the memory win at «10% perf, and it is one matrix column. Demoting the *aggressive* value is correct; retiring the *lever class* without sweeping its one parameter is premature.

---

## 6. negative_facts (checked, confirmed — do not re-litigate)

- **R11 is not an artifact of the live-pool workload.** tcache_count=0's ≈0 memory return is mechanistic (evicted chunks → bins, still retained); recomputed neutral-to-negative (−16 kB…+1.6 MB) across all four profiles while costing −5.7…−10.1%. Global rejection as an RSS lever is correct.
- **L2's steady-state memory win is real and ~9 MB** (mixed 115176→105920; large-transient 114620→105404), attributed by `malloc_info` to 5→2 arenas with retained-free 12.2→10.5 MB — not a throughput artifact (live-set is fixed-size, so occupancy is throughput-independent).
- **The L2 churn inversion is a genuine fragmentation effect**, not measurement noise: T-L2 rep1 retained-free 29.8 MB vs C0 11.9 MB in the `<total type="rest">` aggregate. Direction holds in all 3 reps.
- **Experimental hygiene is sound**: governor pinned `performance` and restored (batch2 L65-90); thermal 34–38 °C throughout (no throttling); AT_SECURE negative control clean; 99/99 rows exit 0.
- **Board `overcommit=0`** → all Batch data already reflects the non-commit-releasing arena-shrink path; overcommit=2 is untested, so its amplification is unmeasured, not disproven.
- **`idle_rss ≈ measure_rss` in every row** because workers hold the live pool through PHASE_IDLE — the reports' "idle" number is steady-state retention, not post-reclamation.
- **dlconf remains steady-state RSS-benign** (unchanged from v2.1/Q6; `elf/rtld.c:2003-2008`, `elf/dl-open.c:919-921`); the §9 hwcaps defects are dormant on ARM. Not re-audited here.

## 7. cannot-verify (needs more data / real target — do not estimate)

- Any shipping magnitude on **real TV silicon** — THP mode, core count, RAM all differ from rpi4 (gates L2 cliff depth, L13 entirely, PSI regime).
- **L13 (`stack_hugetlb=0`)** effect — THP=NA on board makes it a guaranteed no-op there; TV TBD.
- **True L2 churn magnitude** — n=3, inter-rep RSS CV ≈10%; needs n≥10 or VmHWM.
- **`arena_max ∈ {3,4,5}`** response — never run (Part C1).
- **L11/L12 real effect** — needs the burst-free profile (Part B).
- **PSI deltas per lever** — the north-star metric was never measured (Part C4).
- **Per-service production contention** — determines whether the −50% cliff is ever reached off-benchmark; gates whether L2 is safe at all.
- **overcommit=2 / zram / MGLRU / KSM / THP-policy** effects — untested (Part C2/C5/C8).
- **Batch-1 "arena approx count 2→0" methodology** — undocumented; the −32 kB idle-win causal attribution cannot be verified from the report.
- **esd** (highest-RSS service, 9 threads) — not in the A/B sample despite being a prime candidate.
