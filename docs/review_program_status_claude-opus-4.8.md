> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Independent Review — `glibc_memopt_program_status_report_zh.md`

## 1. Reviewer header

- **Reviewer**: Claude Opus 4.8 (`claude-opus-4-8[1m]`)
- **Date**: 2026-08-06
- **Method**: re-checked every quantitative claim against the raw batch tables (recomputed, not re-quoted); read `docs/pg0_decisive_probe.md` in full; diffed **`upstream/2.40..upstream/2.41` in this tree** for real memory-relevant malloc/tunable commits (verifiable anchors, not memory-from-training); cross-referenced the AT_SECURE / launchpad-env claims against PG0 raw evidence. Part D (competitive) is answered directly to you and is **not** folded into any suggested edit.

---

## 2. Part A — facts & conclusions

| Claim | Verdict | Recomputed / basis | Note |
|---|---|---|---|
| **L6 = 59.9 MB / 112 MB, controls reclaim 0** | **SUPPORTED (number) / OVERSTATED (framing)** | Batch 2.5 Part D: `D-C0-idle-trim` measure 114792 → idle **53500** = **61292 kB = 59.9 MB**; `D-C0` release-only 114404→114444 = **0**; `D-T-L3` 114664→114704 = **0**. Arithmetic exact. | The number is a **synthetic** microbench (mixed profile, single 50 % release, n=3, threads-idle, refault uncosted). §5.1 says "这是平台当前正在损失的内存" — that generalizes a synthetic figure to a **real platform loss**, which is unproven (and, per Part C/D, likely far smaller on the actual .NET targets). Put the qualifier next to the number, not only in §5.2/§7. |
| **L2 oversubscription curve** (1:1 +1.0 %/−1.6 MB; 4:3 −22 %; 4:2 −46 %; churn +11~21 MB any cap) | **SUPPORTED** | Batch 2.5 A: arena4 +1.0 %/−1.63 MB; arena3 **−22.0 %**; arena2 **−45.9 %**; 2-thread 2:2 control +0.8 %/−1.25 MB; thread-churn medians +11.0/+17.9/+21.3 MB, 15/15 reps > baseline. | Clean. The dual 1:1 control (2:2 & 4:4) is genuine. |
| **R11 `tcache_count=0`** −5.7~−10.1 %, ≈0 return | **SUPPORTED** | −10.1 %/−8.2 %/−5.7 %/−7.7 % across four profiles; memory −16 kB…+1.6 MB. Mechanistic (evicted → bins), not workload-specific. | Correct to reject. |
| **R12 `mxfast=0`** −5.6 % for −31 kB | **SUPPORTED, but rejection is not universal** | burst-free-small: −5.6 % (9944215 vs 10534439), −32 kB; A6 proved ~50 kB fastbin residency. | The −31 kB is **`burst_size=2048`-bounded**. Fastbins accumulate unboundedly until consolidation; a process bursting tens of thousands of ≤64 B objects without reuse could hold MB-scale fastbin backlog. R12 is sound *for realistic bursts* — but stating it as a flat "否决" overreaches the one burst size tested. See Part A.3. |
| **R13 `tcache_unsorted_limit`** inert on its own surface | **SUPPORTED** | unsorted-drain: +0.3 %, ΔRss noise. Mechanism only reorders unsorted→bins vs →tcache; retention unchanged. | Correct. |
| **L1+L3 combo** +0.1 % / −2.43 MB | **SUPPORTED** | thread-churn: throughput +0.07 %; RSS median **70224 vs 72708 = −2.48 MB**. No interaction penalty. | Matches. |
| **AT_SECURE: top-5 heap targets all =1; env dead for main surface** | **SUPPORTED (PG0-grounded)** | PG0 Q1: AppProcB / AppProcD / ServiceE / AppProcA / ServiceH all **AT_SECURE=1**; 10/10 consistent with recon3 TSV. Only `ServiceF` (996 kB) and `ServiceC` (1072 kB) are AT_SECURE=0 with a unit. | The pivot to `mallopt()`/L6 code injection is correctly forced. |

### A.2 — Under-stated value (the report leaves evidence on the table)
- **PG0 Q2 refuted a live worry the prior reviews raised**: launchpad env inheritance *works* — children keep 83 of 84 pool vars; only one `LD_*` var is filtered; there is **no broad `clearenv`**. The report reduces this to "无干净注入点" and never records that the mechanism itself is intact (it matters for the `enlightenment`/AT_SECURE=0 launchpad children, and for a future non-secure pool-env path).
- **PG0 Q3, though voided, produced a hard, decision-relevant result the report ignores**: a 30 % balloon **held 5 minutes** kept `some/full` PSI at **exactly 0** with swap/zram unchanged (probe §4.3). That is empirical proof that the safe-pressure window yields **no PSI signal at steady state** — which should downgrade PSI's status from "north-star we will measure" to "north-star we currently cannot excite safely on a 1.6 GB board." Surfacing this is more valuable than hiding it.

### A.3 — Is any of the 14 rejections wrong for an untested regime?
- **R12 (mxfast)** — the one with real exposure: rejected on `burst_size=2048`; the fastbin surface scales with burst size and was not swept. Not *wrong*, but "否决" should read "否决 for realistic burst sizes; unmeasured for large-burst tiny-object churn."
- **R14 (hugetlb)** — correctly rejected; verified `heap_max_size()` → `hp_pagesize*4` = 8 MiB/arena on armv7l (`malloc/arena.c:53-56`).
- The other 12 hold under the regimes that matter here (I re-verified R1/R8/R11/R13 mechanically in prior rounds). No second wrong rejection found.

---

## 3. Part B — route completeness

### B.1 Knob-coverage closure
Against the full glibc 2.40 tunable set, coverage is closed (every memory-relevant malloc/pthread knob is in survivor-or-rejected; `mutex_spin_count`/`elision.*`/`mem.tagging` are memory-neutral or arch-N/A, correctly out of scope). **Extend the closure statement to 2.41**: the only tunable 2.41 adds is `glibc.rtld.execstack` (default 1) — commit **`58272284b6`**, a security knob (executable-stack control), **not** a memory lever. So the closure survives the version bump; note it explicitly so it isn't re-raised.

### B.2 Upstream dynamics (verifiable in this tree, `upstream/2.40..2.41`)
- **`e2436d6f5a` malloc: send freed small chunks to smallbin** — freed *small* chunks now go **directly to smallbin** instead of unsorted (large chunks still go unsorted). This is a **free-path fragmentation/locality change** in the exact "tune ptmalloc" lane: it changes reuse ordering and unsorted-bin traffic. Worth evaluating on a 2.41 rebase for RSS/fragmentation effect on the churn profiles (it plausibly interacts with the arena-fragmentation story behind L2's churn inversion).
- **`226e3b0a41` Add tcache path for calloc** + **`1c4cebb84b` Optimize small memory clearing for calloc** + **`c69e8cccaf` Avoid func call for tcache quick path in free()** + **`c621d4f74f` Split `_int_free()` into 3 sub functions** — perf/refactor; low RSS relevance but they change `_int_free` structure (re-verify the L6/mtrim anchors if rebasing).
- **No new memory tunable and no new trim/decay/arena-management semantics in 2.41.** (2.42 is not tagged in this tree — see cannot-verify; do not assume a decay knob appeared.)

### B.3 Peer approaches within "don't replace the allocator" (anchors; some from knowledge, flagged)
1. **Kernel-driven external reclaim via `process_madvise(MADV_PAGEOUT/MADV_COLD)`** *(from knowledge: syscall since Linux 5.10; Android 12+ "app compaction")*. A manager process (ServiceR) pages out a **backgrounded** app's cold anon pages to zram **with no app code change, no `GLIBC_TUNABLES`, no `malloc_trim` all-arena lock**. This sidesteps all three of the project's blockers at once (AT_SECURE, code-owner, lock-stall) and reaches the **.NET GC heap** too (it is page-based, allocator-agnostic) — which `malloc_trim` cannot. Strongly complementary; arguably a better primary lever than in-process trim for the .NET/WRT targets. TV kernel is 6.12.60, so it is available.
2. **Lifecycle-graded reclaim** *(from knowledge: Android `onTrimMemory` levels UI_HIDDEN → BACKGROUND → COMPLETE)* — third-party validation of the exact L6-on-pause pattern, and a design upgrade: light trim on hide, full trim + `MADV_PAGEOUT` on complete-background. The report's L6 is binary; a graded policy is proven at scale.
3. **DAMON / DAMOS reclaim** *(from knowledge: mature in 6.12; `Documentation/mm/damon`)* — kernel access-pattern-driven cold-page reclaim, per-cgroup, zero app change. Directly serves the PSI/RSS north-star and co-exists with the glibc route. The v2 protocol already parks MGLRU as an "adjacent track"; DAMON belongs there too and is more targeted.
4. **Profile-driven parameter adaptation** — the funnel already collects arena count + TID-turnover; feeding that into a per-service `arena_max = min(default, peak_running_threads)` is a small automation of the L2 gate rather than a fixed cap.

---

## 4. Part C — 3-week LD_PRELOAD-shim plan: traps & advice

1. **`malloc_trim()` from a signal handler is not async-signal-safe — this is a correctness bug, not a nit.** Week-1 proposes "信号驱动…在相位点发信号" calling `malloc_trim(0)` in the handler. If the signal interrupts a thread holding an arena lock, the handler's trim tries to retake it → **deadlock/corruption** (the all-arena walk locks every arena, `malloc/malloc.c:5217-5226`). Fix: handler sets a `volatile sig_atomic_t`; a dedicated shim thread (or a self-pipe/`signalfd` loop) calls `malloc_trim` **outside** signal context. Also pick an unused RT signal (`SIGRTMIN+n`) and verify the target doesn't already use it.
2. **`mallopt` in a constructor is mostly fine, with two caveats.** It sets **global** `mp_`, so it affects every already-`dlopen`'d library's future allocations (no per-lib problem). But (a) allocations made *before* the constructor runs (ld.so, earlier-init preloads, IFUNC resolvers) keep old behavior — harmless for `M_ARENA_MAX`/thresholds; (b) `M_MMAP_THRESHOLD`/`M_TRIM_THRESHOLD` force `no_dyn_threshold=1` (intended L3), just document it.
3. **.NET/CoreCLR & WRT are the trap that decides the demo's credibility.** The top-5 are all managed-runtime processes whose bulk RSS is the **GC heap / bmalloc — mmap'd directly, invisible to `malloc_trim` and to `mallopt`** (they touch only the 28–45 % glibc-native fraction, and only its *free* part). So on the real targets the shim will reclaim **far less than 59.9 MB** — quite possibly single-digit MB — because the GC heap is untouchable and the glibc-native heap may be mostly live. Worse, the trim's all-arena lock can stall .NET native interop/GC-helper allocations. **Do not lead the demo with a .NET target and a 59.9-MB expectation.**
4. **Faster, safer path to credible numbers than the shim** *(and it doubles as Part D.3)*: skip the in-process shim for the *reclaim ceiling* question and measure it externally first. A ~50-line tool that reads a target's `[heap]`+arena VMAs from `/proc/pid/smaps` (`Private_Dirty`), calls **`process_madvise(pid, MADV_PAGEOUT)`** on those ranges (and/or a `gdb -p` batch `call malloc_trim(0)` where gdb exists), and re-reads `Private_Dirty`, tells you in **a day** how much is actually returnable on `AppProcB` / `ServiceE` under load — no shim, no signal-safety hazard, no per-target preload, no code owner. That single number is the demo's headline (see Part D.3).
5. **Reproducibility / noise** (Week-2 real-load script): interleave A-B-A-B, not blocks; a mandatory **C0-vs-C0 null arm** to set the noise floor (board lesson: `pass` 92 kB band swallowed everything); pin the scene sequence deterministically; and **exclude runs contaminated by the board's background `.NET TP Worker` SIG11 storm** (PG0 §4.1 — 150 SIG11 lines in ~6 min) — this is an active, run-invalidating confounder the report only mentions in passing (§7 last row).

Most-likely-to-slip step: **Week 2 producing adjudicable reclaim numbers on real targets.** The .NET GC-heap opacity + the SIG11 noise floor + the small live-vs-free glibc fraction together make a null or ambiguous result the base-rate outcome unless the ceiling is measured first (advice #4).

---

## 5. Part D — competitive judgment (for you; not for the report)

**1. Inherent advantages / disadvantages vs "replace with jemalloc/tcmalloc".**
- **Our advantages**: *zero ABI/link risk* (no allocator interposed into libc; their "compiles+links but boot/runtime unverified" is the classic init-order/TLS chicken-and-egg of statically linking a thread-caching allocator into libc — malloc is called during libc's own bringup before the new allocator's arenas/TLS exist). *Rollback granularity*: ours is per-process/per-call and reversible; theirs is **image-global** — one libc, no per-service A/B, no field rollback short of OTA. *Tight-memory fit*: ptmalloc + trim/`process_madvise` is lean; thread-cache allocators trade RSS for CPU and carry **per-thread cache + decayed-dirty-page overhead** — and the targets run **40–55 threads**, precisely where per-thread caching overhead compounds on a 1.6 GB box. *Their single product-candidate knob is `dirty_decay_ms:0,muzzy_decay_ms:0`* — i.e. aggressive dirty-page return, the **same goal as our L6**, but *continuous* decay vs our *phase-triggered* trim; continuous decay=0 risks more refaults under active load, so on the very knob they've chosen, our phase-targeted trigger is arguably better-targeted.
- **Our disadvantages**: *lower ceiling* — bounded by ptmalloc + trim, and the main surface is AT_SECURE (env dead) + managed-runtime (GC heap untouchable). *Requires a code owner* for the `mallopt`/`malloc_trim` insertion on the AT_SECURE surface. *(Symmetry worth using in the debate: neither route reaches the .NET GC heap — jemalloc replaces glibc malloc, not CoreCLR's GC — so their ceiling on the top-5 targets is bounded by the same native fraction as ours.)*

**2. Third-party evidence that thread-cache allocators can raise RSS/fragmentation on tight-memory embedded** *(from knowledge; verify before quoting externally)*:
- **Android** shipped a `svelte`/low-RAM malloc configuration specifically to cap jemalloc arena/cache overhead on ≤1 GB devices, and later moved the default to **Scudo** — memory determinism on low-RAM being a stated motivation. Evidence that stock jemalloc was too heavy untuned on tight devices.
- **jemalloc's own tuning surface** (`dirty_decay_ms`/`muzzy_decay_ms`) exists *because* default nonzero decay **retains** dirty pages → higher RSS than trim-on-demand ptmalloc; the competitor's decay=0 candidate is a tacit acknowledgment.
- **tcmalloc** is throughput-tuned; per-CPU/per-thread caches inflate baseline RSS, hence its `tcmalloc.max_total_thread_cache_bytes` / release-rate knobs.
- General allocator-RSS comparisons repeatedly place ptmalloc among the **lowest-RSS** (at throughput/fragmentation cost) — the exact tradeoff that favors a memory-constrained TV. *(Exact figures: cannot-verify — cite the mechanism, not a number.)*

**3. The one datum to add before September, for maximum persuasiveness.**
**The real returnable memory on the actual top AT_SECURE target under load** — e.g. "of AppProcB's 14.9 MB glibc heap, `process_madvise(MADV_PAGEOUT)` / `malloc_trim` returns X MB at background." It converts the story from "59.9 MB on a synthetic pool" to "X MB on the real #1 target," directly answers the project's biggest open risk (live-vs-free fraction on managed-runtime processes), and — per Part C.4 — is obtainable in **days without a shim, without a code owner, without waiting for the 3-week plan**. Against a competitor whose September deliverable is a "rpi4 single-target validation package" (product-applicability self-rated *stretch*), a **real-TV-target returnable-MB number** is the stronger card.

---

## 6. Top-3 — do these now

1. **Measure the reclaim ceiling on the real AT_SECURE targets this week, via `process_madvise`/gdb, not the shim.** It de-risks the entire route (the 59.9 MB may not survive contact with the .NET GC heap) and is the single most persuasive pre-September datum (Part C.4 + D.3).
2. **Fix the signal-driven-trim async-safety bug in the Week-1 plan before any implementation** — defer `malloc_trim` out of signal context (Part C.1). And add `process_madvise`-based external reclaim as a first-class alternative lever (reaches the GC heap, dodges AT_SECURE and the all-arena lock; Part B.3).
3. **Correct two framing items in the report**: the L6 headline (59.9 MB) needs its "synthetic / idle / refault-uncosted" qualifier inline, and §5.1's "平台当前正在损失的内存" must not present a microbench figure as a real platform loss (Part A.1); add the empirical PSI-at-steady-state≈0 finding from PG0 as a known limitation (Part A.2).

---

## 7. negative_facts (verified — do not re-litigate)

- **Every headline number recomputes correctly**: L6 59.9 MB (61292 kB), L1+L3 −2.48 MB, L2 curve (+1.0/−22/−45.9 %), R11 −5.7~−10.1 %, R12 −5.6 %/−32 kB, R13 inert. Arithmetic is faithful to the raw tables.
- **AT_SECURE top-5 = 1 is PG0-confirmed**, 10/10 consistent with recon3; the pivot to code-level `mallopt`/L6 is correctly forced.
- **Launchpad env inheritance is intact** (PG0 Q2: 83/84 vars retained, no broad `clearenv`; only one `LD_*` var filtered) — the injection problem is AT_SECURE + no-unit, *not* env scrubbing.
- **Coverage closure survives 2.41**: the sole added tunable is `glibc.rtld.execstack` (`58272284b6`), a security knob, not memory; no new trim/decay/arena semantics in 2.41.
- **R14 hugetlb** rejection is mechanically correct (`heap_max_size = hp_pagesize*4` = 8 MiB/arena on armv7l, `arena.c:53-56`).
- **The board is genuinely unstable independent of the experiments** — PG0 §4.1: continuous `.NET TP Worker` SIG11 (150 lines / ~6 min). Any real-load measurement must gate on this. The report acknowledges it (§7) but under-weights it.
- **A 30 % balloon held 5 min → PSI exactly 0** at steady state (PG0 §4.3) — the safe-pressure window has no PSI signal; the north-star is not currently excitable safely on this board.

## 8. cannot-verify

- **The live-vs-free fraction of each target's glibc heap under load** — the datum that decides the route's real value (Top-3 #1). Not in any report.
- **glibc 2.42 memory changes** — 2.42 is not tagged in this tree (only 2.40/2.41); any 2.42 trim/decay/arena claim must be checked against upstream before use.
- **`process_madvise`/DAMON/MGLRU availability & efficacy on the TV kernel** — 6.12.60 supports them by version, but config (`CONFIG_DAMON`, `CONFIG_LRU_GEN`) and Smack/cap permission for a manager to `process_madvise` another process are unverified.
- **jemalloc/tcmalloc RSS-vs-ptmalloc exact figures on this class of device** — mechanism is well-established (Part D.2), specific numbers are not in hand.
- **Whether `GLIBC_TUNABLES` specifically survives the launchpad handoff** — PG0 saw a pool with no `GLIBC_*` vars, so the zero-injection test could not decide it (moot for the AT_SECURE=1 targets, which ignore it regardless).
- **Real-target `malloc_trim` refault cost and trim-time lock stall under live threads** — still unmeasured (Batch 2.5 Part D was threads-idle).
