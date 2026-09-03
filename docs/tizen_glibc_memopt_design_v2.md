> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc Memory Optimization — Design Proposal v2.4 (freeze candidate)

- Status: CONSOLIDATED — incorporates four heterogeneous AI reviews (Codex GPT-5, Claude Opus 4.8, Kimi, Gemini 2.5 Pro), source-level arbitration of all review conflicts against upstream `glibc-2.40`, the Q6 dlconf spot-check (`docs/review_dlconf_rss_spotcheck_codex.md`), and two rounds of on-device evidence (Batch 1 service A/B: `docs/board_ab_batch1_report.md`; Batch 2 microbenchmark curves: `docs/board_ab_batch2_report.md`; Batch 2.5 knee/fair-surface/reclamation runs: `docs/board_ab_batch25_report.md`)
- Target: Tizen TV, armv7l (primary, 32-bit) and aarch64
- Audited baseline: glibc 2.40, branch `tizen_base`, commit `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Supersedes: `tizen_glibc_memopt_design_v1.md`

## 0d. Changelog v2.3 → v2.4 (pre-freeze review fixes; four-reviewer unanimous SUPPORTED on all §0c data claims)

- **§8 Plan B reconciled with the v2.3 survivor set** (was stale, all four reviewers): mallopt covers **L2, L3** only; L11/L12 references removed (rejected as R12/R13); L6 is a code change and therefore AT_SECURE-independent by nature.
- **L2 gate made executable**: (a) safe floor is now *safe by construction* — concurrent *running* allocating threads ≤ online cores, so `arena_max = cores` guarantees a ≤1:1 running-thread:arena ratio on any SoC (portable by argument, evidenced by the 2:2/4:4 dual control); (b) churn classifier defined: periodic `/proc/<pid>/task` sampling, task-ID turnover rate > 0 sustained ⇒ churn class ⇒ forbidden; (c) **deeper caps (below cores) are per-SoC licenses** — the 4:3=−22 %/4:2=−46 % intermediate curve is 4-core data and lock contention at fixed ratio steepens with core count.
- **Churn-inversion magnitude phrasing corrected** (median vs rep-range): median +11~+21 MB per cap level; individual reps span +5~+44 MB. Decision (ban) rests on 15/15 direction, unaffected. All Δ figures in this document are median-of-reps.
- **L6 unmeasured-cost list extended**: besides post-trim refault, the all-arena serial lock walk (`malloc/malloc.c:5217-5226`) was measured threads-idle — concurrent-allocator stall during trim is a mandatory TV-pilot measurement.
- **R14 added** (housekeeping): `glibc.malloc.hugetlb` formalized as rejected on armv7l (was a Q3 parenthetical).
- negative_fact recorded: `glibc.pthread.mutex_spin_count` is memory-neutral — out of scope, do not re-raise.

## 0c. Changelog v2.2 → v2.3 (Batch 2.5 outcomes — four open questions closed)

- **L2 gate quantified — the cost variable is the thread:arena oversubscription ratio, not arena count.** Batch 2.5 sweep (armv7l): 1:1 is free (mixed arena_max=4: +1.0 % / −1.6 MB; cross-confirmed by the 2-thread:2-arena control at +0.8 % / −1.2 MB); 4:3 costs −22 %, 4:2 costs −46 %. Low-allocation-rate services take aggressive caps cheaply (large-transient arena_max=2: −10.8 MB at −1.7 %). **Churn inversion holds across every cap level at n=5** (+11~+21 MB, 15/15 reps above baseline) → thread-churn services forbidden at ANY cap. New rule: `arena_max ≥ peak concurrent allocating threads` (≈cores) is the safe floor.
- **R12/R13 added — L11/L12 rejected on purpose-built fair surfaces.** `mxfast=0`: −5.6 % throughput for −31 kB on `burst-free-small` (the backlog exists but is tens-of-kB scale). `tcache_unsorted_limit=3`: no effect even on `unsorted-drain`, its own designed surface. Batch 2's UNTESTED-EFFECT is resolved; the补测 obligation is discharged.
- **L6 promoted to priority pilot lever — the largest single memory number in the project.** One `malloc_trim(0)` after a 50 % release reclaimed **59.9 MB from a 112 MB process** on armv7l; the no-trim and pinned-threshold controls reclaimed exactly 0 — establishing both on-device retention and the **mechanism orthogonality of L3 vs reclamation** (threshold pinning does not reclaim interior heap). Unmeasured cost flagged: post-trim refault latency on re-activation — a mandatory TV-pilot measurement.
- **First-wave bundle combo-verified**: L1+L3 on thread-churn = +0.1 % / −2.43 MB, no interaction penalty.
- **M6 added**: reclamation levers use the Batch 2.5 Part D three-cell shape.

## 0b. Changelog v2.1 → v2.2 (on-device Batch 1/2 outcomes)

- **L2 demoted Tier 1 → Tier 2 and envelope-gated.** Batch 2 (armv7l, 4-thread sustained allocation) measured −45~−53% throughput and p99 ×20+ (1.2 μs → 27 μs); **new finding**: under thread churn, Rss *inverts* to +8~+26 MB of retained fragmentation (cross-generation lifetimes interleaved across the 2 remaining arenas), unanimous across repeats and persisting into idle. Batch 1's idle-daemon win (−28~−36 kB at zero cost) stands, but only inside its low-contention envelope. [evidence: `docs/board_ab_batch2_report.md`; adjudication: `docs/ab_batch2_adjudication_zh.md`]
- **R11 added**: `tcache_count=0` rejected on device evidence — −5.7~−10.1% throughput (touching the 10 % hard ceiling on its own target profile) for ≈0 memory return in all four profiles.
- **L1 evidence upgraded**: churn profile −1.0 MB at 0.0 % cost, device-confirmed; Tier 1 status reinforced.
- **L3 quantified**: ≈0 % cost on phase-change/small/mixed/churn shapes, −4.9 % on continuous large-block churn (its own target surface); −0.9~−1.6 MB. Strongest Tier 2 survivor.
- **L11/L12 marked UNTESTED-EFFECT**: zero cost and zero effect under the live-pool reuse workload — their target surface (burst frees without reuse) was not generated; deprioritized pending workload evidence, not rejected.
- **T2 upgraded to source+device verified** (Batch 1 negative control: ServiceV, AT_SECURE=1, env present, exactly zero effect).
- **First-wave bundle defined: L1 + L3**; any bundle containing `arena_max` is withdrawn (inherits the L2 contention cliff: −38~−48 %, +32 MB under churn).
- **M3 amended**: microbenchmark sensitivity curves (`bench/alloc_bench`) become the pre-screen gate; the real-service benchmark remains the shipping gate.

## 0a. Changelog v2 → v2.1 (Q6 spot-check outcome)

- **Q6 closed — single-reviewer dlconf claim REFUTED with refinement**: the config/cache mappings are transient and unmapped as claimed (mapping story CONFIRMED), but Tizen's dlconf restructuring introduced (a) an **orphaned heap allocation**: `dlconf_unload_cache()` frees each `struct caches` node without freeing its `glibc_hwcaps_priorities` array — upstream deliberately retains this array in statics for bounded reuse (`_dl_unload_cache` only zeroes `length`, upstream `dl-cache.c:508-519`), so the Tizen per-cache variant loses the pointer entirely, repeatable per dlopen; and (b) **uninitialized hwcaps fields** in `dlconf_find_cache`'s malloc'd `struct caches` — garbage `allocated` skips the allocation branch (`if (length > allocated)`, upstream `:93`) and the merge loop then **writes through a garbage pointer** (upstream `:115-135`): memory-corruption class, not leak class. [finding: codex-gpt5 spot-check; upstream-lifecycle refinement: arbitration]
- **Materiality on target**: both defects gate on a consulted cache carrying a nonempty `glibc-hwcaps` extension section; glibc 2.40 defines hwcaps subdirectories only for x86-64/POWER/s390 — none for arm/aarch64 — so ARM TV images are dormant. **R9's practical conclusion therefore survives** (see revised R9); the defects are filed as a correctness work item (§9), not an optimization lever.

## 0. Changelog v1 → v2 (arbitration outcomes)

- **G2 corrected (REFUTED in part)**: `MALLOC_PERTURB_` is live in normal libc (`malloc/arena.c:301` `TUNABLE_GET(perturb,...)`, `malloc/malloc.c:5468` `do_set_perturb_byte`, env alias in `elf/dl-tunables.list:39-43`); only `MALLOC_CHECK_`/`glibc.malloc.check` is a stub. Hygiene list extended. [finding: codex-gpt5 + claude-opus; kimi's contrary negative_fact refuted by source]
- **L4/L5 accounting corrected**: `tcache_init()` allocates the per-thread `tcache_perthread_struct` unconditionally — no `mp_.tcache_count` check (`malloc/malloc.c:3241-3268`). `tcache_count=0` saves cached chunks only; the 384 B (armv7l) metadata is removable only via a `USE_TCACHE=0` rebuild. [finding: codex-gpt5 + kimi, cross-confirmed]
- **L2 rephrased**: `arena_max` defaults to 0; the "2×cores (32-bit) / 8×cores (64-bit)" figure is the *effective* cap computed after `narenas > arena_test` (`malloc/arena.c:828-842`). Added armv7l heap mechanics: 1 MiB VA per secondary arena (`HEAP_MAX_SIZE = 2×512 KiB`, `malloc/arena.c:28-31`); reclaim is `MADV_DONTNEED` (RSS only, VA retained) unless `vm.overcommit_memory==2` (`malloc/arena.c:516-525`, `sysdeps/unix/sysv/linux/malloc-sysdep.h:34-54`). [finding: kimi (default mechanism) + claude-opus (heap mechanics), both source-confirmed]
- **T1 trust boundary widened**: dlconf explicitly included (see §2). [finding: all four reviewers]
- **Memory-type labels introduced**: every lever is tagged RSS / PSS / VA / FLASH so the measurement protocol cannot misjudge VA levers with an Rss/Pss metric. [finding: claude-opus challenge C2]
- **New levers L11–L18 added; rejected list extended R8–R10** (static TLS surplus, dlconf-for-RSS, guard pages — all arbitrated against source).
- **Covariates added to M-protocol**: `vm.overcommit_memory`, THP mode. [finding: claude-opus]
- **AT_SECURE Plan B added** (§8). [finding: claude-opus challenge C3]
- **Dropped from v1**: none of L1–L10 removed; all verdicts CONFIRMED by ≥3 reviewers except as amended above.

## 1. Objective and Hard Constraints

Unchanged from v1: north-star = per-process RSS/PSS (`smaps_rollup`) + system PSI memory stall; secondary = flash. Hard perf budget: ≤5% target / ≤10% ceiling regression on allocation-heavy paths, per service, per architecture. Per-process opt-in over global defaults; on-device measurement over source-derived estimates.

## 2. Trust Boundary (revised)

- **T1 (revised, quadruple-confirmed)**: within `malloc/ nptl/ sysdeps/nptl/ sysdeps/pthread/ elf/dl-tunables* locale/ iconv* csu/`, the delta vs `upstream/2.40` is a single code hunk — the memalign CVE-2026-0861 guard (`malloc/malloc.c:5052`) plus a test file. All allocator/threading/tunables mechanics in this document are therefore upstream-2.40-faithful. **However**, the largest Tizen source delta lies outside those paths: the default-enabled `dlconf` loader subsystem (`elf/dlconf.c` +2641 lines, hooks in `dl-load.c`/`dl-cache.c`/`dl-open.c`/`rtld.c`; enabled at `packaging/glibc.spec:27-28,397-401`). One reviewer verified dlconf is steady-state RSS-benign: config/cache mappings are munmapped at startup completion (`elf/rtld.c:2003-2008`) and after every `dlopen` (`elf/dl-open.c:919-921` → `elf/dlconf.c:2555-2584`); retained cost is sub-100 B of ld.so BSS. **Pending action**: these Tizen-specific anchors were verified by one reviewer only — spot-check assigned (see Q6). The armv7l `kernel-features.h` delta is behavior-neutral at `--enable-kernel=2.6.16`.
- **T2 (confirmed)**: `GLIBC_TUNABLES` functional but silently ignored for `AT_SECURE` processes (`elf/dl-tunables.c:299-301`). Side note (arbitration byproduct): `AT_SECURE` processes automatically take the commit-releasing `PROT_NONE` heap-shrink path (`malloc-sysdep.h:41`). **Device-verified 2026-07-08**: Batch 1 negative control (ServiceV, AT_SECURE=1) had the env string present and exactly zero Rss/Pss/arena effect (`docs/board_ab_batch1_report.md` §E3).

## 3. Precondition Gates (P0)

- G1. Per-service `AT_SECURE` inventory. Unchanged; now paired with §8 Plan B.
- G2 (**rewritten**). Environment hygiene audit of all service launchers, two classes:
  - **Live in normal libc (silent perf/memory catastrophe if set)**: `MALLOC_PERTURB_` / `glibc.malloc.perturb` (memset on every alloc/free, `malloc/malloc.c:1982-1994`), `LD_PRELOAD` (incl. `libc_malloc_debug.so.0`), `LD_AUDIT`, `LD_PROFILE` (profiling buffers, `elf/dl-profile.c:180-235`), `LD_DEBUG*`, `GCONV_PATH` (disables gconv cache, forces private parsed config, `iconv/gconv_cache.c:54-58`, `iconv/gconv_conf.c:475-498`), stray `GLIBC_TUNABLES`.
  - **Inert without debug preload (audit anyway for hygiene)**: `MALLOC_CHECK_` / `glibc.malloc.check` (`do_set_mallopt_check` is a no-op stub, `malloc/malloc.c:5464-5468`).

## 4. Levers (tiered; every lever carries a memory-type label)

### Tier 1 — low risk, env-only, first A/B batch

| ID | Lever | Type | Mechanism (evidence) | Expected saving | Perf risk |
|---|---|---|---|---|---|
| L1 | `glibc.pthread.stack_cache_size` 40 MiB → 1–4 MiB (or 0) | **RSS** | Default 41943040 (`sysdeps/nptl/dl-tunables.list:26-29`, `nptl/nptl-stack.c:23`); cache is process-global, queued stacks are NOT madvised — dirty pages persist until munmap on overflow (`nptl/nptl-stack.c:56-130`) | Up to tens of MiB, **only** in thread-churning services; ≈0 for stable pools that never hit the cap. **Batch 2 churn profile: −1.0 MB at 0.0 % cost (device-confirmed)** | <5% typical; risk only if threads created/destroyed on request path |
| L13 | `glibc.pthread.stack_hugetlb=0` | **RSS** | Default 1 (`sysdeps/nptl/dl-tunables.list:36-41`); `=0` issues `MADV_NOHUGEPAGE` on new stacks (`nptl/allocatestack.c:372-375`) | Up to ~(2 MiB − touched)/thread **iff** kernel THP mode is `always`; exactly 0 otherwise — gate on Q3 (rpi4 dev board: THP absent → no-op there; TV kernel TBD) | Negligible; glibc never requests THP for stacks, so this only reduces or no-ops |

### Tier 2 — medium risk, env-only, benchmark-mandatory

| ID | Lever | Type | Mechanism (evidence) | Expected saving | Perf risk |
|---|---|---|---|---|---|
| L2 | `glibc.malloc.arena_max=N` — **oversubscription-gated** (gate quantified in v2.3) | **RSS** (envelope-dependent) | Mechanism unchanged (`malloc/arena.c:828-842`; 1 MiB VA/secondary arena, `arena.c:28-31`; shrink `MADV_DONTNEED` unless `overcommit==2`, `arena.c:516-525`). **Quantified knee (Batch 2.5 sweep, armv7l)**: cost tracks thread:arena oversubscription — 1:1 free (+1.0 %/−1.6 MB; 2-thread control cross-confirms), 4:3 −22 %, 4:2 −46 %. Low-allocation-rate services: aggressive caps cheap (large-transient arena_max=2 → −10.8 MB at −1.7 %). Churn: Rss +11~+21 MB at every cap, n=5 | −1.6~−10.8 MB depending on allocation rate and cap depth | **Executable gate (v2.4)**: `arena_max = cores` is safe by construction (running allocators ≤ cores ⇒ ratio ≤1:1; evidenced by 2:2/4:4 dual control); churn classifier = `/proc/<pid>/task` turnover sampling, sustained turnover ⇒ forbidden; deeper caps are per-SoC licenses requiring re-measurement (4-core intermediate curve does not port); latency-sensitive excluded |
| L3 | Pin `mmap_threshold=131072` + `trim_threshold=131072` | **RSS** | Setters force `no_dyn_threshold=1` (`malloc/malloc.c:5422-5449`); drift gated at `:3375-3388`; 32-bit drift ceiling 512 KiB, 64-bit 32 MiB (`:945-958`) | Hundreds of KiB–MiB; smaller absolute headroom on armv7l (512 KiB ceiling), larger on aarch64. **Batch 2: −0.9~−1.6 MB** | **Batch 2 measured**: ≈0 % on phase-change/small/mixed/churn shapes; **−4.9 %** on continuous large-block churn (its target surface). Strongest Tier 2 survivor; per-service shape check |
| L4 | `glibc.malloc.tcache_count=3` (**`=0` rejected → R11**) | **RSS** | Setter `malloc/malloc.c:5508-5517`. **Corrected accounting**: saving = cached chunks only; per-thread struct allocated unconditionally (`:3241-3268`), removal needs `USE_TCACHE=0` rebuild — out of scope | **Batch 2: ≤0.6 MB at −1.7~−2.3 %** — niche | Within budget but weak return; apply only where `malloc_info()` evidences large tcache residency |
| L5 | Lower `glibc.malloc.tcache_max` after size histogram | **RSS** | Setter `:5494-5505`. Note: does NOT flush already-cached chunks above the new limit; benefit ramps in with thread/chunk turnover | KiB–hundreds of KiB/busy thread | Exceeds budget if hot sizes sit just above new cap |

### Tier 3 — application/service code change

| ID | Lever | Type | Mechanism (evidence) | Expected saving | Perf risk |
|---|---|---|---|---|---|
| L6 | Proactive `malloc_trim(0)` at phase changes — **priority pilot lever (v2.3)** | **RSS** | Interior `MADV_DONTNEED` after consolidate (`malloc/malloc.c:5151-5195`) + `systrim` (`:5200-5202`); all-arena lock walk (`:5209-5228`). **On-device quantitative (Batch 2.5 Part D, armv7l)**: one call after a 50 % release reclaimed **59.9 MB of a 112 MB process**; no-trim and pinned-threshold controls reclaimed exactly 0 — interior frees are never returned without it, and L3 is mechanism-orthogonal to reclamation | Largest measured lever in the project; TV analogue is exact (scene change / app backgrounding = release-then-quiesce phase) | Low at quiescent points; forbidden on hot paths/timers. **Unmeasured (mandatory TV-pilot): post-trim refault latency; trim-time all-arena lock stall under concurrent allocation (Part D ran threads-idle)** |
| L14 | Reduce default thread stack size (`pthread_setattr_default_np` / systemd `LimitSTACK=`) | **VA** (primary, armv7l) + minor RSS | Default stacksize derives from `RLIMIT_STACK` (`sysdeps/nptl/pthread_early_init.h:30-54`); stacks are demand-paged — RSS = touched pages only, so the MiB-class figure is VA reservation, not resident | MiB VA per thread if rlimit-inherited default is large (e.g. 8 MiB) and 512 KiB suffices | None if depth verified; requires stack-usage profiling. Interacts with L1 (cached stacks keep their size) |
| L15 | Right-size stdio buffers via `setvbuf` for idle/control streams | **RSS** | `BUFSIZ`=8192 (`libio/stdio.h:100`), malloc'd per active buffered `FILE*` (`libio/filedoalloc.c:74-105`); wide-oriented streams allocate ~4× extra (`libio/wfiledoalloc.c`) | ~8 KiB/stream (narrow), more for wide | I/O-throughput dependent; idle/control streams only |

### Tier 4 — flash / packaging / image composition

| ID | Lever | Type | Evidence | Notes |
|---|---|---|---|---|
| L7 | gconv module allowlist | **FLASH** | `iconvdata/Makefile:26-65,252-259`, `packaging/glibc.spec:813-823` | MiB-class; needs product encoding inventory (Q5) |
| L16 | Regenerate `gconv-modules.cache` after any gconv pruning; never ship `GCONV_PATH` | **RSS+correctness** | Cache-hit path returns early (`iconv/gconv_conf.c:467-472`); cache is `MAP_SHARED, PROT_READ` = low PSS (`iconv/gconv_cache.c:80`); stale/absent cache forces private parsed config | Operational pairing for L7 [finding: codex-gpt5] |
| L8 | NSS packaging split — **corrected scope** | **FLASH** (split) + **RSS** (config) | `libnss_files`/`libnss_dns` are compat stubs — `files`/`dns` are builtin, no dlopen (`nss/nss_module.c:172-175`); removing stubs saves ~0. Real runtime cost: `compat`/`optfiles`/`securitymanager` on the passwd/group chain are dlopen'd and retained for process life (`nss/nss_module.c:183,277`) — tens of KB private RSS per service using `getpw*`/`getgr*` | Flash: move `db`/`hesiod` out of base. RSS: see L17 |
| L17 | Where product policy allows, move `passwd`/`shadow` to builtin `files` in `nsswitch.conf` | **RSS** | Avoids retained dlopen of shared NSS modules per process (`nss/nss_module.c:277`); `group` must keep `securitymanager` | High policy risk; Tizen `optfiles`/`compat` semantics must be inventoried first [finding: claude-opus] |
| L9 | `.symtab`/`.strtab` strip policy for production `*.so*` | **FLASH** | `packaging/glibc.spec:529-538` | Needs tooling-owner sign-off; RSS ≈0 |
| L10 | Image package-set audit — **extended**: add `glibc-devel-utils` (`libmemusage.so`, `libpcprofile.so`, libthread_db files, `packaging/glibc.spec:911-918`) to the v1 list | **FLASH** | `packaging/glibc.spec:752-771,858-918` | [extension: codex-gpt5] |
| L18 | Cold-DSO `-Os` (gconv/NSS modules only, libc/ld.so/pthread stay `-O2`) | **FLASH** | Current spec forces `-O2` globally (`packaging/glibc.spec:329-356`) | Middle ground vs rejected R6; observation item, needs per-component CFLAGS in spec [finding: kimi] |
| L19 | Base CLI tools subpackage (`localedef`, `iconv`, `gencat`, `getent`…) | **FLASH** | base `%files` ships them (`packaging/glibc.spec` §%files) | ~1 MB; verify no boot script uses `getent`/`iconv` [finding: claude-opus] |

### Recommended first-wave bundle (v2.2)

Conservative default for TV-phase pilots: **L1 + L3** — **combo-verified** (Batch 2.5 Part C: +0.1 % / −2.43 MB on thread-churn, no interaction penalty). `arena_max=cores` may join per-service after passing the L2 oversubscription gate. L12 removed from candidacy (R13).

## 5. Rejected Levers (extended; do not re-propose without new evidence)

R1–R7 unchanged from v1 (all quadruple-CONFIRMED). New:

- **R8. Static TLS surplus tunables (`glibc.rtld.optional_static_tls`, `glibc.rtld.nns`) as RSS levers — REJECTED.** Arbitrated against source over three reviewers' proposals: `_dl_allocate_tls_init` memsets only each loaded module's TLS block (`elf/dl-tls.c:638-641`); the surplus region is demand-zero and untouched at thread creation → **0 RSS**. Residual value is ~1.6 KB VA/thread — negligible vs 1 MiB/arena — against a real `dlopen` "cannot allocate memory in static TLS block" failure risk.
- **R9 (revised post-Q6). Disabling dlconf for RSS — REJECTED as an RSS lever on the target platform.** The mapping story holds: config/cache mappings are transient and unmapped at startup and after every dlopen; static retained state is 40 B (armv7l) / 72 B (aarch64) of BSS. The Q6 spot-check found a conditional steady-state heap leak plus uninitialized-field corruption risk in the hwcaps path (see §0a/§9), but both gate on `glibc-hwcaps` cache extension entries that ARM images do not generate — dormant on target, and in any case the remedy is the §9 patch, not disabling dlconf. Remaining dlconf-disable value is tens-of-KiB flash + per-dlopen CPU (each dlopen remaps/reads `/run/dlconf.dat` and consulted cache files by design), at high platform-policy risk — platform owner's call, outside this plan.
- **R11 (new in v2.2). `glibc.malloc.tcache_count=0` — REJECTED on device evidence.** Throughput −5.7 % to −10.1 % across all four Batch 2 profiles (touching the 10 % hard ceiling on its own target profile, small-churn), while memory benefit was ≈0 to +1.6 MB everywhere — evicted chunks merely migrate into bins. Full performance price, zero memory return. (`docs/board_ab_batch2_report.md`; adjudication `docs/ab_batch2_adjudication_zh.md`)
- **R12 (new in v2.3). `glibc.malloc.mxfast=0` — REJECTED on fair-surface evidence.** On `burst-free-small`, purpose-built to generate the fastbin backlog it targets: −5.6 % throughput (at the 5 % target line) for −31 kB. The backlog is real (A6: ~50 kB residual) but tens-of-kB scale per process. (`docs/board_ab_batch25_report.md` Part B)
- **R13 (new in v2.3). `glibc.malloc.tcache_unsorted_limit` — REJECTED.** No measurable effect (Δtput +0.3 %, ΔRss noise-level) even on `unsorted-drain`, a workload designed around its exact code path. (`docs/board_ab_batch25_report.md` Part B)
- **R14 (formalized in v2.4). `glibc.malloc.hugetlb` — REJECTED on armv7l.** `hugetlb>=2` inflates `heap_max_size()` to `hp_pagesize*4` = 8 MiB per arena on 32-bit (`malloc/arena.c:53-56`, `malloc/malloc.c:5541-5558`) — an anti-lever; `=1` is THP-gated and covered by Q3/L13 logic. negative_fact: `glibc.pthread.mutex_spin_count` is memory-neutral (perf-only) — out of scope.
- **R10. Thread guard-page removal — REJECTED.** Guard pages are `PROT_NONE` = 0 RSS (`nptl/allocatestack.c:366`); saving is 4 KiB VA/thread at the cost of overflow detection. Only reconsider under demonstrated VA exhaustion.

## 6. Measurement Protocol (revised)

- M1. Memory: `smaps_rollup` Rss+Pss per lever per service, ≥3 runs; PSI memory `some`/`full` system-level. **Metric must match the lever's type label**: VA levers (L14) are measured via `VmSize`/`maps` deltas, not Rss — an Rss-only protocol would falsely retire them.
- M2. Attribution: `malloc_info()` pre/post.
- M3 (amended v2.2). Performance, two gates: microbenchmark sensitivity curves (`bench/alloc_bench`, per-lever × workload-shape, Batch 2 data on file) act as the **pre-screen gate**; the per-service allocation benchmark on the real service, armv7l + aarch64, remains the **shipping gate** (≤5 % target / ≤10 % ceiling).
- M4. Rollout unit: per-service systemd drop-in; never image-global.
- **M5 (new). Covariates recorded per measurement host**: `vm.overcommit_memory` (determines whether arena shrink releases commit via `PROT_NONE` remap or only RSS via `MADV_DONTNEED`, `malloc/arena.c:516-525`) and THP mode (`/sys/kernel/mm/transparent_hugepage/enabled`, gates L13). Results from hosts with different covariate values are not comparable.
- M6 (new v2.3). Reclamation levers use the Batch 2.5 Part D three-cell shape — {release-only, release+trim, threshold-control} — separating retention, active reclaim, and threshold mechanics in one experiment.
- Note: setting `vm.overcommit_memory=2` system-wide would amplify L2/L6 but changes allocation-failure semantics for the whole image — recorded as a system-level decision **outside this plan's scope**.

## 7. Open Questions

- Q1. Per-service `AT_SECURE` inventory (gates all env levers; triggers §8 if mostly secure).
- Q2 (partially answered). Board-scale magnitudes on file (Batch 1/2 adjudications); TV-scale magnitudes on real services remain open.
- Q3. Kernel THP mode (gates L13; also `glibc.malloc.hugetlb` — note `hugetlb>=2` is an anti-lever on armv7l: `heap_max_size()` becomes `hp_pagesize*4` = 8 MiB/arena, `malloc/arena.c:53-56`, `malloc/malloc.c:5541-5558`).
- Q4. Final image package set + device `nsswitch.conf` (gates L8/L10/L17).
- Q5. Product encoding allowlist (gates L7/L16).
- ~~Q6~~ **CLOSED** — spot-check delivered (`docs/review_dlconf_rss_spotcheck_codex.md`): mapping claims CONFIRMED, "nothing retained" REFUTED (hwcaps orphaned allocation + uninitialized fields, dormant on ARM). R9 revised; patch work item opened in §9.
- Q7 (answered for the dev board: 0). TV-image value remains open (M5 covariate).

## 8. AT_SECURE Plan B (new)

If the G1 inventory shows target services are predominantly `AT_SECURE`, Tiers 1–2 as env levers are void. Fallback order:
1. **`mallopt()` in service code** — API covers `M_ARENA_MAX`, `M_MMAP_THRESHOLD`, `M_TRIM_THRESHOLD`, `M_MXFAST`, `M_ARENA_TEST` (`malloc/malloc.c:5584-5620`); of the **surviving** levers this rescues **L2 and L3** as one-line code changes. No mallopt path for tcache (L4/L5) or pthread levers (L1/L13). **L6 is already a code change and thus AT_SECURE-independent by nature.** (M_MXFAST exists as API but the mxfast lever is rejected — R12.)
2. **Tizen-spec default patch** — change defaults in `elf/dl-tunables.list` (or `mp_` initializers) at build time for the remaining levers. This violates the per-process-opt-in policy and becomes a global change requiring full-image validation; treat as last resort with its own review cycle.

## 9. Spin-off Work Item: dlconf hwcaps lifecycle patch (correctness, not optimization)

Two defects in Tizen `dlconf`, both gated on `glibc-hwcaps` cache extension entries (dormant on ARM today; latent for any future arch/vendor cache that carries them):

- **D1 — orphaned allocation**: `dlconf_unload_cache()` frees each `struct caches` node without freeing its `glibc_hwcaps_priorities` array (`elf/dlconf.c:2567-2573`); repeatable per dlopen. Fix: call the per-cache `glibc_hwcaps_priorities_free()` for each node before `free(node)`, preserving the `_malloced` guard (free is a no-op under minimal rtld malloc — upstream `dl-cache.c:48-56` semantics).
- **D2 — uninitialized fields (severity > D1: wild write, memory-corruption class)**: `dlconf_find_cache` mallocs `struct caches` without initializing the four hwcaps fields (`elf/dlconf.c:2410-2440`, `elf/dlconf.h:51-62`). Fix: allocate with `calloc` (physical enforcement — eliminates the entire uninitialized-field class for this struct, present and future), not field-by-field memset.

Acceptance: a repro/regression test needs a synthetic cache file with a nonempty `glibc-hwcaps` extension section (ldconfig on x86-64 with a `glibc-hwcaps/x86-64-v2` library, or a hand-built cache); verify (a) no allocation growth across repeated dlopen with valgrind/massif or `malloc_info()` diff, (b) no wild access under ASan with an uninit-hostile allocator. Patch review goes through the standard multi-AI gate; this item ships independently of the memory-optimization rollout.

## 10. Review Provenance

Full reviews: `docs/review_glibc_memopt_{codex_gpt5,claude-opus-4.8,kimi,Gemini-Code-Assist}.md`. Conflict arbitration (perturb, tcache metadata, arena default mechanism, static TLS surplus, HEAP_MAX_SIZE) resolved against upstream `glibc-2.40` source; on-device evidence: `docs/board_inventory_run_report.md`, `docs/board_ab_batch1_report.md` (+ adjudication), `docs/board_ab_batch2_report.md` (+ adjudication), tool `bench/alloc_bench/` (v1.1a), `docs/board_ab_batch25_report.md` (+ adjudication); Tizen-tree equivalence in those paths established by two independent `git diff` derivations (T1).
