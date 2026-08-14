> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Pre-Freeze Review — `tizen_glibc_memopt_design_v2.md` (v2.3)

## 1. Reviewer header

- **Reviewer**: Claude Opus 4.8 (`claude-opus-4-8[1m]`)
- **Date**: 2026-07-09
- **Tree / commit**: Tizen `tizen_base` @ `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- **Standard applied**: "what will cause TV-phase rework", not completeness.
- **Recompute method**: re-derived every §0c number from the raw `## Run Summary Table` in `docs/board_ab_batch25_report.md` (80 rows, Parts A/B/C/D). Median-of-reps for throughput/RSS; % vs C0 median. Read the bench delta specs (`alloc_bench_spec_v1_1_delta_zh.md`, `_v1_1a_zh.md`) and confirmed the schema in `bench/alloc_bench/alloc_bench.c:1574`. Checked mallopt coverage (`malloc/malloc.c:5584-5620`), the L6 all-arena lock (`:5217-5226`), tunable closure vs `elf/dl-tunables.list` + `sysdeps/nptl/dl-tunables.list`, and every cross-referenced file's existence.
- **Board reminder**: still one Raspberry Pi 4 (`6.12.80-arm-rpi4-v7l`, 4 cores, THP=NA, `overcommit=0`, ~3.9 GB, governor pinned `performance`, thermal 32–38 °C). Not TV silicon.

**Prior-review obligations discharged (good)**: bench v1.1/v1.1a adopted all four blind-spot fixes from the v2.2 round — `burst-free-small` + `unsorted-drain` fair surfaces, `--touch-full` (unconditional ≥128 KiB full-touch), periodic measure-phase RSS sampling, and `--idle-release`/`--idle-trim` reclamation surface. The A6/A7 self-proof gates confirm the surfaces are real, not new blind spots.

---

## 2. Part A — Batch 2.5 data→conclusion verdicts (recomputed)

| §0c claim | Verdict | Recomputed (median of reps) | Weakness / correction |
|---|---|---|---|
| **A-1. L2 cost = thread:arena oversubscription ratio; safe floor `arena_max ≥ cores`** | **SUPPORTED (interpolation, not extrapolation)** | mixed 4-thread: 4:4 **+1.0 %/−1.63 MB** (2029159 vs 2008889; 113448 vs 115076); 4:3 **−22.0 %** (1567803); 4:2 **−45.9 %** (1087237). 2-thread control 2:2 **+0.8 %/−1.25 MB** (1204550 vs 1194537; 56616 vs 57868). large-transient 4:2 **−1.7 %/−10.75 MB** (95290 vs 96986; 96432 vs 107436). | Monotonic in ratio + **genuine dual 1:1 control** (2:2 and 4:4 both ≈free) → ratio-invariance is evidenced, so "1:1-free" generalizes to 8-core TV by interpolation. **But two TV-risky gaps** (see A-1 note). |
| **A-2. L6 = 59.9 MB reclaimed; controls reclaim 0; L3 ⊥ reclamation** | **SUPPORTED** | D-C0-idle-trim: measure 114792 → idle **53500** = **−59.9 MB** (61292 kB, `idle_trim_ret=1`). D-C0 release-only: 114404 → 114444 = **0** (`ret=−1`; `idle_free_delta` ~48–50 MB sits in free lists). D-T-L3 (pinned threshold, no trim): 114664 → 114704 = **0**. | Clean 3-cell isolation. **But**: single profile (mixed), single release ratio (50 %), n=3; and the **trim-time all-arena lock walk** (`malloc/malloc.c:5217-5226`, one `__libc_lock_lock` per arena around `mtrim`→`malloc_consolidate`+`MADV_DONTNEED`) was measured with **threads idle** — concurrent-allocator stall is unmeasured, on top of the flagged refault. |
| **A-3a. R12 `mxfast=0` rejected on fair surface** | **SUPPORTED (caveat)** | burst-free-small: **−5.6 %** tput (9944215 vs 10534439) for **−32 kB** (1432 vs 1464). A6 proved ~50 kB fastbin residency → surface is real. | Magnitude is **`burst_size=2048`-bounded**; fastbins hold only ≤~64 B chunks, so realistic backlog is tens–low-hundreds kB. Rejection sound for realistic patterns; a pathological huge-burst-no-reuse process is the only untested corner and is rare. |
| **A-3b. R13 `tcache_unsorted_limit` rejected on its own surface** | **SUPPORTED** | unsorted-drain: **+0.3 %** tput (2432474 vs 2425487), ΔRss +284 kB (noise). Surface forces the unsorted-traversal path. | Genuinely inert (mechanism only reorders unsorted→bins vs →tcache; retention unchanged). Strong rejection. |
| **A-4. Churn ban at any cap; "+11~+21 MB", n=5, 15/15 above baseline** | **Ban SUPPORTED / magnitude soft-but-irrelevant** | Churn RSS Δ vs C0 (73784-max region): arena4 (1:1) median **+11.0 MB** (83968); arena3 **+17.9 MB** (90992); arena2 **+21.3 MB** (94528). All 15 reps > C0 max. **Even the safe 1:1 floor inverts (+11 MB).** | "+11~+21" is the inter-cap **median** range; per-cell dispersion is far wider (arena2 reps span **+5.7~+44.9 MB**; single reps 78–118 MB). Because the lever is **forbidden**, the soft magnitude is not decision-relevant — the ban rests on the 15/15 direction, which is robust. |

**A-1 note (the two TV-risky gaps):**
1. **The gate's decisive input has no measurement method.** The rule keys on "peak concurrent allocating threads" and "is this a thread-churn service", but the specified instrument — `malloc_info()` time series — reports **arena count and retained-free bytes**, not concurrent-allocator count or thread create/exit rate. On TV you cannot classify a service by the gate as written.
2. **The intermediate-cap cost curve is core-count-dependent.** 4:3 = −22 % and 4:2 = −46 % are 4-core numbers; lock contention at a fixed ratio generally steepens with core count. The safe floor (`≥cores`, no oversubscription) is portable, but "deeper caps for low-allocation-rate services" (e.g. large-transient arena_max=2) needs per-SoC re-measurement — it is not a portable license.

---

## 3. Part B — finalization completeness

### B-1. R/L coverage closure (vs full tunable set)
Enumerated `elf/dl-tunables.list` (malloc/elision/rtld/mem/gmon) + `sysdeps/nptl/dl-tunables.list` (pthread). Every **memory-relevant** tunable is placed:

| tunable | placed as | tunable | placed as |
|---|---|---|---|
| malloc.check | G2 | malloc.mxfast | R12 |
| malloc.top_pad | R1 | malloc.hugetlb | **Q3 only — not a formal R** |
| malloc.perturb | G2 | pthread.stack_cache_size | L1 |
| malloc.mmap_threshold/trim_threshold | L3 | pthread.rseq | R3 |
| malloc.mmap_max | R4 | pthread.stack_hugetlb | L13 |
| malloc.arena_max | L2 | pthread.mutex_spin_count | **neither (memory-neutral)** |
| malloc.arena_test | R2 | rtld.optional_static_tls / nns | R8 |
| malloc.tcache_max / tcache_count | L5 / L4+R11 | elision.* / mem.tagging / mem.decorate_maps / rtld.{enable_secure,dynamic_sort} / gmon.* | non-memory or arch-N/A |
| malloc.tcache_unsorted_limit | L12→R13 | | |

**Closure is essentially complete.** Two housekeeping gaps for freeze: (a) `glibc.malloc.hugetlb` is only a Q3 parenthetical anti-lever — promote to a formal **R14** so the rejected set is self-contained; (b) `glibc.pthread.mutex_spin_count` (default 100) is in neither list — it is perf-only/memory-neutral, but a one-line negative_fact prevents a future reviewer re-raising it.

### B-2. Internal reference consistency — **3 dangling evidence pointers (freeze-blocker)**

| Cited path | Cited at | Status |
|---|---|---|
| `docs/ab_batch2_adjudication_zh.md` | R11 (L109), §0b (L18) | **MISSING** |
| `docs/ab_batch25_adjudication_zh.md` | implied §10 "(+ adjudication)", R12/R13 basis | **MISSING** |
| `docs/review_glibc_memopt_Gemini-Code-Assist.md` | §10 (L151); Gemini named as 1 of the **4 consolidation inputs** (L3) | **MISSING** |
| `docs/v22_review_arbitration_zh.md` | (spec delta) | exists ✓ |

A frozen doc whose evidence pointers dangle cannot be audited downstream. The Gemini one is worst: the doc's authority claim ("four heterogeneous AI reviews") has no artifact for the fourth. Either add the files or correct the citations before freeze.

### B-3. Plan B (§8) vs the v2.3 surviving-lever set — **STALE**
§8 line 137: *"…M_MXFAST… i.e. L2, L3, **L11** survive as one-line code changes. No mallopt equivalent exists for tcache (L4/L5/**L12**)…"*. But **L11 was rejected this version (R12)** and **L12 was rejected (R13)**. The mallopt *API* coverage is source-correct (`M_ARENA_MAX`, `M_MMAP_THRESHOLD`, `M_TRIM_THRESHOLD`, `M_MXFAST`, `M_ARENA_TEST` all at `malloc/malloc.c:5584-5620`), but the **lever mapping is stale**: under an all-AT_SECURE inventory a team reading §8 would code up two rejected levers. Correct §8 to: *mallopt covers **L2, L3** (M_ARENA_MAX / M_MMAP_THRESHOLD / M_TRIM_THRESHOLD); no mallopt path for tcache (L4/L5) or pthread (L1/L13); L6 is already code (AT_SECURE-independent).*

---

## 4. Part C — TV-phase protocol inputs

| # | Recommendation | Method / anchor | Cost |
|---|---|---|---|
| **C1** | **One-sweep target funnel (hundreds → 5–10).** Extend the existing `docs/tizen_memopt_inventory.sh` (already emits AT_SECURE / elf_class / rss / pss / threads / env-blacklist) with: `smaps_rollup` **Private_Dirty**; **arena count** ≈ number of `rw-p` anon/`[heap]` segments in `/proc/pid/maps`; task-dir count. **Rank** = `Private_Dirty(Pss) × instance_count` (TV launchpad-forks share pages → weight by copies). **Stratify** top-N by {threads → L1/L2, arena count → L2/L6, heap RSS → L6, AT_SECURE → env vs §8}. | inventory.sh + M1 `smaps_rollup` + `/proc/pid/maps`; `/proc/pid/task` | one script, one sweep, seconds |
| **C2** | **L6 first pilot = a UI app's `pause`/`app_pause` lifecycle callback** (backgrounding = release-then-quiesce, the exact Part-D shape) on a memory-heavy app (web-runtime / media). **Second: ServiceR-driven trim** on a memory-pressure/LMK event — ties L6 to the PSI north-star, and `ServiceR` (pid 413) is both already A/B-tested and the platform memory manager. **Measure**: foreground-resume latency (refault) **and** trim duration under any live background thread (the A-2 lock gap). | Tizen app lifecycle (`app_pause`); `ServiceR` memory events; L6 anchor `malloc/malloc.c:5209-5228` | few lines in pause handler + measurement |
| **C3** | **PSI protocol (north-star, currently un-measured).** Sample `/proc/pressure/memory` + cgroup-v2 `memory.pressure` (avg10/avg60) at 1 Hz. **Inject** with a rate-controlled allocator holding the system at a target `MemAvailable` (or `stress-ng --vm`). **A/B**: same injection, with vs without the lever bundle on the target service(s), while driving a representative TV scenario (app-switch / channel-change). **Metric**: PSI some/full avg10 area-under-curve + `workingset_refault`/`pgmajfault` (`/proc/vmstat`). **Precheck**: `CONFIG_PSI=y` on the TV kernel. | kernel-6.12 PSI, cgroup-v2, `/proc/vmstat` | one injector + sampler; reproducible |

---

## 5. Top-3 challenges (finalization-level)

**C1 — The L2 gate's decisive input is not measurable with the specified instrument, so L2 is unshippable as written.** The rule is `arena_max ≥ peak concurrent allocating threads`, and the churn ban keys on "thread-churn service" — but `malloc_info()` (the named tool) yields arena count and retained-free, **not** concurrent-allocator count or thread lifecycle. Across hundreds of TV services you can neither confirm the safe floor nor identify the forbidden class, so you either mis-cap into the −46 % / +21 MB regime or never apply L2 at all. **Freeze the gate with a concrete classifier** (thread create/exit rate from `/proc/pid/task` sampling + arena-lock-wait sampling) or L2 stays a paper lever.

**C2 — The two levers v2.3 headlines (L6, aggressive-cap L2) are the most covariate-sensitive, and their production-critical costs are unmeasured on a board that differs from TV in exactly those covariates.** L6's 59.9 MB is on `overcommit=0` (MADV_DONTNEED path), THP=NA, 4 GB, and **threads idle during trim**; the all-arena serial lock walk (`malloc.c:5217-5226`) means a service that trims at a scene-change while a worker still allocates eats a stop-the-world-per-arena pause **plus** a ~60 MB refault on resume — neither measured, only the refault flagged. The intermediate-cap cost curve (4:3=−22 %) does not port to 8-core. On TV, these are precisely the things that make a pilot regress.

**C3 — The freeze carries stale internal state that will misroute the TV phase.** (a) Plan B (§8) still sells L11 (M_MXFAST) and L12 as survivors that this version rejected (R12/R13) — a self-contradiction one section away from R12/R13. (b) Three cited evidence files do not exist, including the Gemini review that underwrites the "four heterogeneous reviews" claim. A definition-of-done for freeze must include a link-check and a survivor-set reconciliation of §8.

---

## 6. negative_facts (checked, confirmed — do not re-litigate)

- **The R12/R13 fair surfaces are genuinely fair, not new blind spots.** `burst-free-small` A6 gate proved ~50 kB fastbin residency; `unsorted-drain` forces the unsorted-traversal path where `tcache_unsorted_limit` acts. The v2.2 UNTESTED-EFFECT obligation is discharged.
- **The bench fixes are real and adopted** (v1.1/v1.1a deltas + `alloc_bench.c:1574` schema `alloc_bench_v1_1`): full-touch ≥128 KiB, periodic RSS, idle-release/idle-trim, stagger-churn. The v1.1a A7 redefinition correctly rejected an incoherent "OS reclaims without trim" gate (glibc does not do that — it is L6's raison d'être).
- **L6's controls are clean**: release-only and L3-pinned-threshold both reclaim exactly 0 (idle≈measure); only explicit `malloc_trim(0)` returns interior heap → L3 ⊥ reclamation is proven, not asserted.
- **Oversubscription ratio-invariance has a real dual control** (2:2 @ +0.8 % and 4:4 @ +1.0 %, both ≈free) — a two-core-count anchor, not a single point.
- **mallopt API coverage is source-correct** (`M_ARENA_MAX`/`M_MMAP_THRESHOLD`/`M_TRIM_THRESHOLD`/`M_MXFAST`/`M_ARENA_TEST` at `malloc/malloc.c:5584-5620`); the §8 defect is the stale *lever mapping*, not the API claim.
- **large-transient throughput 1.4 M→97 k (Batch 2→2.5) is the expected effect of the v1.1a full-touch fix** (real large-block writes), not a regression — and it is why arena_max=2 there is now −10.75 MB at only −1.7 % (threads become bandwidth-bound, not lock-bound).
- **Experimental hygiene maintained**: governor performance + restored; thermal 32–38 °C (no throttle); overcommit recorded; 80/80 exit 0; a Part-D operator status check explicitly did not kill/modify a running process.

## 7. cannot-verify (needs real target / more data — do not estimate)

- All magnitudes on real TV silicon — cores, THP, RAM, overcommit all differ from rpi4 (gates L2 curve depth, L6 arithmetic, L13 entirely, PSI regime).
- **"Peak concurrent allocating threads" per real service** — no measurement method exists yet (Challenge C1).
- **L6 trim-time all-arena lock pause + resume refault** under concurrent allocation — Part D ran threads-idle.
- **L6 reclaim sensitivity to release ratio and size mix** — only 50 %/mixed/n=3.
- **R12 magnitude at large burst sizes** — `burst_size` fixed at 2048; fastbin backlog scales with it.
- **8-core intermediate-cap cost curve** (4:3/4:2 equivalents) — untested.
- **PSI deltas per lever** — the north-star has still never been measured on device.
- **TV kernel `CONFIG_PSI` / cgroup-v2 `memory.pressure` availability** — precheck required before C3.
