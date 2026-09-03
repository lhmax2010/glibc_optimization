> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Adversarial Review: Tizen glibc Memory Optimization Design v1

## 1. Reviewer header

- Model: Kimi Code CLI
- Date: 2026-07-07
- Audited commit: `8f08a7e30396822a8d969d357822a6ffd56b43fb` (`tizen_base`)
- Method:
  - `git log upstream/2.40..HEAD -- malloc/ nptl/ sysdeps/nptl/ sysdeps/pthread/ elf/dl-tunables* locale/ iconv/ iconvdata/ packaging/`
  - `git diff upstream/2.40..HEAD` for the paths above
  - Direct source reads of cited file:line anchors in `malloc/`, `nptl/`, `elf/`, `libio/`, `packaging/`
  - Independent search for tunables, `struct pthread` layout, TLS/DTV sizing, stdio buffering, packaging, and Tizen-specific `dlconf`

---

## 2. T1 re-derivation result

**Verdict: INCOMPLETE / partially confirmed.**

Evidence used:

```text
upstream/2.40 = d7477af362
HEAD          = 8f08a7e303
merge-base    = 3d1aed8749
```

### 2.1 What the doc got right

- The only **source** delta in `malloc/` vs. `upstream/2.40` is the memalign CVE-2026-0861 guard: `93fd24e807 memalign: reinstate alignment overflow check (CVE-2026-0861)` (`malloc/malloc.c:5036-5053`).
- `nptl/`, `sysdeps/nptl/`, `sysdeps/pthread/`, `locale/` source files have **net zero** diff vs. `upstream/2.40`.
- `elf/dl-tunables*` have **zero** diff.

### 2.2 What the doc missed or under-specified

| Delta | Evidence | Why it matters |
|---|---|---|
| Transient `__USE_TIME_BITS64` revert/reapply in nptl/pthread headers | `076080b7e6` (revert), `2e56c13e72` (reapply) — both touch `sysdeps/nptl/pthread.h`, `sysdeps/pthread/semaphore.h`, `sysdeps/pthread/threads.h` | Behavior-relevant history in exactly the paths T1 covers; net zero at HEAD but the pair is a real delta |
| `dlconf` loader-config feature enabled by default | `a1882d3189`, `a67f170a80`, `cc952c3325`, `2f5ebeb9fa`, `7fe6e78df8`, `a11afb8881` — all modify `packaging/glibc.spec` and add `packaging/dlconf.service` | Changes `ld.so` runtime search behavior and adds a boot-time service; not "just packaging" |
| Forced `en_US.UTF-8` locale in base package | `1af8de6b4e [packaging] Include en_US.UTF-8 locale by default in glibc package` (`packaging/glibc.spec`) | Increases base flash/locale footprint beyond upstream defaults |
| Post-upgrade helper `glibc_post_upgrade.c` | `75bee72a13 packaging: add packaging` | Runs `ldconfig`, regenerates iconv cache, can `telinit u`; runtime behavior at upgrade time |

**Correction:** T1 is accurate as a statement of **final net source diff** in the named runtime paths, but adversarially it is incomplete. The transient nptl/pthread time64 history and the runtime-behavior packaging changes (`dlconf`, forced locale, post-upgrade helper) should be called out explicitly rather than waved away as "packaging changes."

---

## 3. Part A verdict table

| Item | Verdict | Evidence (file:line) | Correction / consequence if not CONFIRMED |
|---|---|---|---|
| T1 | INCOMPLETE | `malloc/malloc.c:5036-5053`; `git log upstream/2.40..HEAD` (see §2) | Net source diff is only the memalign guard, but transient nptl time64 revert/reapply and packaging changes (`dlconf`, forced `en_US.UTF-8`, post-upgrade helper) have runtime/memory impact and are omitted |
| T2 | CONFIRMED | `elf/dl-tunables.c:289-355` (`__libc_enable_secure` returns early at lines 300-301 and 340-341) | — |
| G1 | CONFIRMED | Same as T2 | — |
| G2 | CONFIRMED | `malloc/malloc.c:1978-1994`; `malloc/malloc-debug.c:49-78`; `malloc/Makefile` builds `libc_malloc_debug.so` | — |
| L1 | CONFIRMED | `sysdeps/nptl/dl-tunables.list:26-29`; `nptl/nptl-stack.c:23`; cache add/trim at `nptl/nptl-stack.c:95-108` | — |
| L2 | INCOMPLETE | `malloc/malloc.c:1921-1922`; `malloc/arena.c:830-842` | `mp_.arena_max` defaults to **0**, not "2×cores on 32-bit"; the effective default cap is driven by `arena_test = NARENAS_FROM_NCORES(1)`. Setting `arena_max=2` is a hard cap regardless of core count |
| L3 | CONFIRMED | `malloc/malloc.c:5424-5451`; `malloc/malloc.c:3375-3388`; `malloc/malloc.c:945-958` | Also note `do_set_mmaps_max` (`malloc/malloc.c:5454-5461`) and `do_set_top_pad` (`malloc/malloc.c:5434-5441`) disable dynamic thresholds as side effects |
| L4 | CONFIRMED | `malloc/malloc.c:292-317`; `malloc/malloc.c:1923-1928`; `malloc/malloc.c:5508-5517`; `malloc/malloc.c:3118-3122` | `tcache_count=0` stops caching but **does not free the per-thread `tcache_perthread_struct`** (~384 B on armv7l). Avoiding the struct requires a `USE_TCACHE=0` rebuild |
| L5 | CONFIRMED | `elf/dl-tunables.list:68-70`; `malloc/malloc.c:5494-5505` | Lowering `tcache_max` does not flush existing cached chunks above the new limit; benefit is gradual until thread exit/turnover |
| L6 | CONFIRMED | `malloc/malloc.c:5151-5195` (MADV_DONTNEED interior pages); `malloc/malloc.c:5200-5202` (main-arena top trim); `malloc/malloc.c:5209-5228` (all-arena lock walk) | — |
| L7 | CONFIRMED | `iconvdata/Makefile:26-65,252-259`; `packaging/glibc.spec:813-823` | — |
| L8 | CONFIRMED | `packaging/glibc.spec:752-765`; `packaging/nsswitch.conf:29-46` | — |
| L9 | CONFIRMED | `packaging/glibc.spec:529-538` | — |
| L10 | CONFIRMED | `packaging/glibc.spec:752-771,858-909` | — |
| R1 | CONFIRMED | `malloc/malloc.c:936-938` (`DEFAULT_TOP_PAD 0`); `malloc/malloc.c:1917`; `elf/dl-tunables.list:34-38` (metadata claims 131072); `elf/dl-tunables.c:467`; `malloc/malloc.c:5434-5441` | — |
| R2 | CONFIRMED | `malloc/arena.c:830-852` | — |
| R3 | CONFIRMED | `nptl/descr.h:407-419`; `sysdeps/nptl/dl-tls_init_tp.c:102-105` | — |
| R4 | CONFIRMED | `malloc/malloc.c:5454-5461` | — |
| R5 | CONFIRMED | `malloc/set-freeres.c:123-244` | — |
| R6 | CONFIRMED | `packaging/glibc.spec:329-338` | — |
| R7 | CONFIRMED | `packaging/glibc.spec:59-76,547-556,796-800` | — |

---

## 4. Top-3 challenges to the document as a whole

1. **T1 is materially incomplete.** The document treats "plus packaging changes" as a footnote, but the Tizen tree adds `dlconf` (loader-config boot service), forced `en_US.UTF-8` in the base package, and a post-upgrade helper with runtime side effects. These are not metadata-only and should be in the trust-boundary assessment.
2. **L2 misstates the default arena mechanism.** Saying "default is 2×cores on 32-bit, 8×cores on 64-bit" describes the **effective** cap driven by `arena_test`, while `arena_max` itself defaults to 0. This distinction matters because `arena_max=2` is a hard global cap, not a tweak around a default.
3. **The document understates the AT_SECURE gate and the cost of tcache_count=0.** Every env-based lever is silently ignored for secure processes, yet this is listed only as a "gate" rather than a likely showstopper for many TV services. And while L4 correctly notes `count=0` removes the fast path, it omits that the per-thread tcache struct (~384 B on armv7l) is still allocated; only a `USE_TCACHE=0` rebuild removes it.

---

## 5. Part B — new levers not in the design document

All env-based levers below share the same AT_SECURE gate as T2.

| ID | Lever | Verdict | Evidence (file:line) | Expected saving | Perf cost vs 5–10% budget | Rollout | Risk notes |
|---|---|---|---|---|---|---|---|
| B1 | `glibc.rtld.optional_static_tls=0` | FEASIBLE-WITH-CAVEATS | `elf/dl-tunables.list:127-130`; `elf/dl-tls.c:75-76,105-109,125-126` | ~0.5 KiB/thread less static-TLS surplus | Negligible | Per-process `GLIBC_TUNABLES` | Only affects dynamic-TLS/dlmopen surplus; monitor TLS allocation failures in services that `dlopen` TLS-bearing DSOs |
| B2 | `glibc.rtld.nns=2` (default 4) | FEASIBLE-WITH-CAVEATS | `elf/dl-tunables.list:121-126`; `elf/dl-tls.c:72-73,105-109` | ~0.5–1 KiB/thread static-TLS surplus | Negligible | Per-process `GLIBC_TUNABLES` | Hard-caps `dlmopen` namespaces; audit modules still consume headroom |
| B3 | `glibc.malloc.tcache_unsorted_limit` from 0 (unlimited) to a small value | FEASIBLE-WITH-CAVEATS | `elf/dl-tunables.list:74-76`; `malloc/malloc.c:1928,4230-4236,5521-5524` | Tens–hundreds KiB in threaded alloc-heavy services | Low–medium; can exceed budget if service relies on unsorted→tcache fast path | Per-process env after size histogram (e.g. `=3`) | Less aggressive than `tcache_count=0`; good intermediate experiment |
| B4 | Reduce default thread stack via `RLIMIT_STACK`/`systemd LimitSTACK=` or `pthread_setattr_default_np` | FEASIBLE-WITH-CAVEATS | `sysdeps/nptl/pthread_early_init.h:30-54`; `nptl/allocatestack.c:228-234`; `sysdeps/arm/nptl/pthreaddef.h:19` | MiB/thread if service inherits a large rlimit and can live with, e.g., 512 KiB | None if stack still fits | Image/systemd drop-in or service code | **Highest per-thread RSS lever on armv7l**; requires stack-usage profiling |
| B5 | Drop guard page for bounded pool threads on armv7l (`guardsize=0`) | FEASIBLE-WITH-CAVEATS | `nptl/allocatestack.c:343-346`; `sysdeps/arm/nptl/pthreaddef.h:22` (`ARCH_MIN_GUARD_SIZE=0`) | 4 KiB/thread | None | Application code (`pthread_attr_setguardsize`) | Loses stack-overflow detection; only for threads with verified small depth |
| B6 | Avoid wide-oriented `FILE` streams / right-size buffers with `setvbuf` | FEASIBLE-WITH-CAVEATS | `libio/wfiledoalloc.c:69-79`; `libio/filedoalloc.c:83-101`; `libio/stdio.h:100` (`BUFSIZ=8192`) | ~24 KiB/stream on armv7l when wide buffer allocated; up to ~8 KiB/stream with smaller narrow buffer | None (avoided conversion) or IO-throughput dependent | Application code | Functional: wchar APIs unavailable on narrow-only stream |
| B7 | Build cold DSOs (gconv/NSS modules) with `-Os` | FEASIBLE-WITH-CAVEATS | `packaging/glibc.spec:329-356` (currently `-O2` for everything) | Hundreds KiB–low MiB flash across many small DSOs | Near-zero if restricted to cold paths | Spec (per-component `CFLAGS`) | Keep libc/pthread/ld.so/string code at `-O2` |
| B8 | Disable Tizen `dlconf` if product isolation policy permits | FEASIBLE-WITH-CAVEATS | `packaging/glibc.spec:27-28,396-402`; `configure.ac:239-276`; `elf/rtld.c:2003-2008` | Text/data of dlconf code in `ld.so` (~tens KiB); slight startup win | None | Spec/profile (`--disable-dlconf`) | High policy risk; Tizen security/isolation may require it |
| B9 | Move `libc_malloc_debug.so.0` out of runtime base image | FEASIBLE-WITH-CAVEATS | `packaging/glibc.spec:771`; `malloc/Makefile:194-216` | Flash: hundreds KiB; runtime: 0 unless preloaded | None | Spec/package split | Keep in debug/devel-utils package for field diagnostics |
| B10 | Stop keeping `.symtab`/`.strtab` in production `*.so*` or split debug | FEASIBLE-WITH-CAVEATS | `packaging/glibc.spec:529-538` (`STRIP_KEEP_SYMTAB=*.so*`) | Flash: MiB-class across libc/ld.so/NSS/gconv; runtime RSS ≈0 | None | Spec/image (strip or debug package split) | Needs tooling owner sign-off (valgrind/PurifyPlus/libthread_db) |

---

## 6. `negative_facts` — checked and confirmed absent/false

- `glibc.malloc.top_pad` actual allocator default is already 0 (`malloc/malloc.c:936-938`, `:1917`); the tunable metadata default of 131072 is misleading.
- `glibc.pthread.rseq=0` cannot remove the 32-byte `rseq_area` from `struct pthread` (`nptl/descr.h:407-419`).
- `glibc.malloc.mmap_max` lowering is RSS-negative and also disables dynamic thresholds (`malloc/malloc.c:5454-5461`).
- `MALLOC_CHECK_` / `MALLOC_PERTURB_` / `glibc.malloc.check` are compiled out of normal libc; debug behavior lives in `libc_malloc_debug.so` (`malloc/malloc.c:1978-1994`, `malloc/malloc-debug.c:49-78`).
- Locale archive minimization is already default: `build_locales 0`, minimal `en_US.UTF-8` via `localedef --no-archive` (`packaging/glibc.spec:59-76,547-556,796-800`).
- `LD_DEBUG` residual mask is zero unless explicitly set at startup; no steady-state cost.
- `__libc_freeres` is one-shot, not a repeatable resident-service API (`malloc/set-freeres.c:123-244`).
- No Tizen-specific tcache behavior change at HEAD; `USE_TCACHE=1` is the normal-libc default (`malloc/Makefile:339-340`).
- armv7l `ARCH_MIN_GUARD_SIZE` is 0, so guard-page removal is technically possible without glibc overriding the attr (`sysdeps/arm/nptl/pthreaddef.h:22`).

---

## 7. `cannot-verify` list (requires on-device measurement)

- Per-service `AT_SECURE` status on the TV (gates every `GLIBC_TUNABLES` env lever).
- Actual RSS/PSS savings magnitudes for L1–L6 and B1–B6 per service.
- Per-service allocation-heavy benchmark regressions on armv7l and aarch64.
- Kernel THP/hugetlb state on TV kernels (gates `glibc.malloc.hugetlb`, `glibc.pthread.stack_hugetlb`).
- Final TV runtime image package set and device `/etc/nsswitch.conf` (gates L7–L10, B9–B10).
- Product encoding allowlist for gconv pruning (gates L7, B7).
- Real stack-depth requirements per thread pool (gates B4, B5).
