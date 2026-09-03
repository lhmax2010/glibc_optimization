> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc Memory Optimization — Design Proposal v1

- Status: DRAFT — pending heterogeneous multi-AI review
- Target: Tizen TV, armv7l (primary, 32-bit) and aarch64
- Audited baseline: glibc 2.40, branch `tizen_base`, commit `8f08a7e30396822a8d969d357822a6ffd56b43fb` (`platform/upstream/glibc`)
- Provenance: proposals drafted by Claude, source-audited by Codex against the Tizen tree, mechanical claims independently re-verified by Claude against upstream `glibc-2.40`. Evidence anchors are file:line in this tree.

## 1. Objective and Hard Constraints

- North-star metrics: per-process RSS/PSS (`/proc/<pid>/smaps_rollup`) and system PSI memory stall. Secondary: flash footprint of glibc-owned packages.
- Hard constraint: no lever may degrade performance of allocation-heavy paths by more than **5–10%** (per-service benchmark, armv7l and aarch64).
- Policy constraints (project-wide): per-process opt-in over global defaults; physical enforcement over soft convention; every rollout decision backed by on-device measurement, not source-inspection estimates.

## 2. Trust Boundary (reviewers: attack this first)

- Claim T1 (from Codex audit, NOT independently verified): the delta between this tree and upstream `glibc-2.40` in malloc/nptl/locale/tunables paths is limited to the memalign CVE-2026-0861 guard (`malloc/malloc.c:5036-5053`, commit `93fd24e807`), plus packaging changes. **If T1 is false, every mechanical claim below must be re-derived from this tree.**
- Claim T2 (verified in source, not on device): `GLIBC_TUNABLES` parsing is built and functional (`Makeconfig:1257-1269`, `elf/Makefile:78-85`, `csu/libc-start.c:264-268`) but silently ignored for `AT_SECURE` processes (`elf/dl-tunables.c:289-355`). Whether target TV services run `AT_SECURE` (Smack/caps) is UNVERIFIED and gates every env-based lever below.

## 3. Precondition Gates (P0, before any lever ships)

- G1. Per-service `AT_SECURE` inventory for all target processes. Env-based tunables are dead-on-arrival for secure processes.
- G2. Environment hygiene audit of service launchers: confirm no accidental `MALLOC_CHECK_`, `MALLOC_PERTURB_`, `glibc.malloc.check`, or `LD_PRELOAD=libc_malloc_debug.so.0`. Normal libc compiles these out (`malloc/malloc.c:1978-1994`, `malloc/malloc.c:5464-5468`, debug hooks live in `malloc/malloc-debug.c:49-78`); accidental enablement is a silent catastrophic perf/memory regression.

## 4. Proposed Levers (tiered by risk)

### Tier 1 — low risk, env-only, first A/B batch

| ID | Lever | Mechanism (evidence) | Expected saving | Perf risk vs budget |
|---|---|---|---|---|
| L1 | `glibc.pthread.stack_cache_size` reduced from 40 MiB default to 1–4 MiB (or 0) per service | Default 41943040 (`sysdeps/nptl/dl-tunables.list:26-29`, `nptl/nptl-stack.c:23-24`); freed stacks cached until cap, overflow unmaps (`nptl/nptl-stack.c:56-130`) | Up to tens of MiB in thread-churning processes; zero effect on live stacks | Usually <5% for pool-based services; risk concentrated in services creating/destroying threads on request path |
| L2 | `glibc.malloc.arena_max=2` per multi-threaded service | Tunable (`elf/dl-tunables.list:58-62`); default is 2×cores on 32-bit, 8×cores on 64-bit (`malloc/malloc.c:1921`); `mp_.arena_max` caps before CPU formula (`malloc/arena.c:817-865`) | MiB-class in fragmented long-lived services; on armv7l also relieves VA pressure | Lock contention; `arena_max=2` is the low-risk entry, reserve `=1` for low-concurrency services after benchmark |

### Tier 2 — medium risk, env-only, second batch (per-service benchmark mandatory)

| ID | Lever | Mechanism (evidence) | Expected saving | Perf risk vs budget |
|---|---|---|---|---|
| L3 | Pin `glibc.malloc.mmap_threshold=131072` + `glibc.malloc.trim_threshold=131072` | 131072 is already the initial threshold; the effect is **pinning** it and disabling dynamic upward drift: setters force `mp_.no_dyn_threshold=1` (`malloc/malloc.c:5422-5449`); drift happens on free of mmapped chunks gated by `!no_dyn_threshold` (`malloc/malloc.c:3375-3388`); 32-bit dynamic cap is 512 KiB, 64-bit 32 MiB (`malloc/malloc.c:945-958`) | Hundreds of KiB to multi-MiB in services with transient ≥128 KiB allocations; larger relative effect on aarch64 (higher drift ceiling) | mmap/munmap syscalls + page faults on repeated large alloc/free cycles; can exceed 10% on such paths, fine for phase-change allocation patterns |
| L4 | Reduce tcache before disabling: `glibc.malloc.tcache_count=3`, escalate to `0` only for memory-critical services | Defaults: 64 bins, fill count 7 (`malloc/malloc.c:292-317`, `mp_` init `malloc/malloc.c:1923-1928`); setter (`malloc/malloc.c:5508-5517`); metadata ≈384 B/thread on armv7l, ≈640 B on aarch64, plus cached chunks | Tens to hundreds of KiB per allocation-heavy thread | `count=0` removes the lockless fast path — high risk, benchmark-gated; `count=3` is the sanctioned first step |
| L5 | `glibc.malloc.tcache_max` lowering (after allocation-size histogram) | Setter updates `mp_.tcache_max_bytes`/bins (`malloc/malloc.c:5494-5505`) | KiB–hundreds of KiB per busy thread | Exceeds budget if hot sizes sit just above the new cap; requires size profiling first |

### Tier 3 — code change in resident services (not glibc source)

| ID | Lever | Mechanism (evidence) | Expected saving | Perf risk vs budget |
|---|---|---|---|---|
| L6 | Proactive `malloc_trim(0)` at allocation phase changes (post-init, scene change, pre-idle) | In 2.40 `mtrim` is NOT top-only: after `malloc_consolidate` it `MADV_DONTNEED`s page-aligned interior free chunks in bins (`malloc/malloc.c:5151-5195`), then `systrim` for main arena top (`malloc/malloc.c:5200-5202`); walks all arenas under lock (`malloc/malloc.c:5209-5228`) | MiB-class after startup bursts / cache drops | Low at quiescent points; forbidden on hot paths and tight timers (all-arena lock + refault cost) |

### Tier 4 — flash/packaging (image composition, not glibc source)

| ID | Lever | Evidence | Notes |
|---|---|---|---|
| L7 | gconv module allowlist for TV image | Full set built and packaged in `glibc-locale` (`iconvdata/Makefile:26-65,252-259`, `packaging/glibc.spec:813-823`) | MiB-class flash; requires product encoding inventory (subtitles/media/web/regional) |
| L8 | NSS module split: move `libnss_db`, `libnss_hesiod` out of base | Base installs six NSS modules (`packaging/glibc.spec:752-765`); default `nsswitch.conf` uses `compat,optfiles,securitymanager,files,dns,nis` — not `db`/`hesiod` (`packaging/nsswitch.conf:29-46`) | Must verify final device nsswitch.conf |
| L9 | Revisit `.symtab`/`.strtab` retention in production `*.so*` | `STRIP_KEEP_SYMTAB=*.so*` kept for libthread_db/valgrind/PurifyPlus (`packaging/glibc.spec:529-538`) | MiB-class flash; needs debugging-tooling owner sign-off; runtime RSS impact ≈0 |
| L10 | Image package-set audit: `glibc-locale`, `glibc-i18ndata`, `glibc-devel-static`, `glibc-profile`, `libc_malloc_debug.so.0` presence on TV images | `packaging/glibc.spec:752-771,858-909` | Composition change only; zero runtime risk |

## 5. Rejected Levers (negative facts — do not re-propose without new evidence)

- R1. `glibc.malloc.top_pad=0`: actual allocator default is already 0 — `DEFAULT_TOP_PAD (0)` (`malloc/malloc.c:936-937`, `mp_` init `:1917`) despite tunable metadata claiming 131072 (`elf/dl-tunables.list:34-38`); callbacks fire only when env-initialized (`elf/dl-tunables.c:437-469`). Worse, explicitly setting it forces `no_dyn_threshold=1` as a side effect (`malloc/malloc.c:5432-5439`).
- R2. `glibc.malloc.arena_test`: not an arena cap; irrelevant once `arena_max` is set (`malloc/arena.c:830-852`).
- R3. `glibc.pthread.rseq=0`: cannot remove the embedded 32-byte rseq area from `struct pthread` (`nptl/descr.h:407-419`); no memory upside, possible CPU downside.
- R4. `glibc.malloc.mmap_max` lowering: typically RSS-negative (fewer independently unmappable large allocations); setter also kills dynamic thresholds (`do_set_mmaps_max`, `malloc/malloc.c:5452-5459`).
- R5. `__libc_freeres` as a resident-service cleanup API: one-shot shutdown path, not repeatable (`malloc/set-freeres.c:123-244`).
- R6. Blanket libc `-Os` rebuild: current spec forces `-O2 -g -U_FORTIFY_SOURCE` (`packaging/glibc.spec:329-356`); flash upside is low-single-digit %, perf risk on string/allocator/loader hot paths cannot be bounded from source. Parked until a dedicated experimental build with full benchmark suite exists.
- R7. Locale-archive minimization: already default — `build_locales 0`, minimal `en_US.UTF-8` via `localedef --no-archive` (`packaging/glibc.spec:59-76,547-556,796-800`).

## 6. Measurement Protocol (acceptance gates)

- M1. Memory: `smaps_rollup` Rss+Pss before/after per lever per service, ≥3 runs, steady-state definition per service; system-level PSI memory `some`/`full` deltas over representative TV scenarios.
- M2. Attribution: `malloc_info()` dump pre/post to attribute deltas to arena/bin level — RSS totals alone do not localize cause.
- M3. Performance: per-service allocation-heavy benchmark on armv7l and aarch64; a lever ships only if regression ≤5% (target) / ≤10% (hard ceiling) on its service's benchmark.
- M4. Rollout unit: systemd drop-in `Environment=GLIBC_TUNABLES=...` per service — never image-global env.

## 7. Open Questions (cannot be resolved by source inspection)

- Q1. Per-service `AT_SECURE` status on device (gates all env levers).
- Q2. Actual on-device savings magnitudes for L1–L6 (source proves feasibility only).
- Q3. Kernel THP/hugetlb state on TV kernels — determines whether `glibc.malloc.hugetlb` / `glibc.pthread.stack_hugetlb=0` are relevant at all (`malloc/malloc.c:5541-5558`, `nptl/allocatestack.c:372-376`).
- Q4. Final TV image package set and device `nsswitch.conf` (gates L7–L10).
- Q5. Product encoding allowlist for gconv pruning (gates L7).

## 8. Review Request

This document is itself under adversarial review. Reviewers: do not trust any claim above; verify against this tree; see the accompanying review prompt for the output contract.
