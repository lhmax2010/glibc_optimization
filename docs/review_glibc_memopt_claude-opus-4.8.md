> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Adversarial Review — `tizen_glibc_memopt_design_v1.md`

## 1. Reviewer header

- **Reviewer model**: Claude Opus 4.8 (1M context) — `claude-opus-4-8[1m]`
- **Date**: 2026-07-07
- **Tree**: Tizen `platform/upstream/glibc`, branch `tizen_base`
- **Commit audited**: `git rev-parse HEAD` = `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- **Baseline for T1**: tag `upstream/2.40` = `d7477af3627d24b4ba2609e33337881b838c33b7`
- **Method**:
  - T1: `git diff --stat/-p upstream/2.40 HEAD` over `malloc/ nptl/ sysdeps/nptl/ sysdeps/pthread/ elf/dl-tunables* locale/ iconv/ iconvdata/ csu/` and a full-tree name-only diff to catch out-of-scope deltas.
  - Part A: opened every cited `file:line` and confirmed the code supports the claim (ground rule 3). Malloc-path files are byte-identical to `upstream/2.40` except the one memalign guard, so line numbers are reliable.
  - Part B: independent reads of `elf/dlconf.c` + loader hooks, `malloc/arena.c` heap sizing, `elf/dl-tls.c` TLS surplus, `nss/nss_module.c`, `iconv/gconv_cache.c`, `locale/`, packaging `%files`.
- **Constraint applied**: armv7l 32-bit is primary; every word-size-dependent number below is the 32-bit value.

---

## 2. T1 re-derivation result

**Verdict: CONFIRMED-AS-SCOPED, but the scope is a load-bearing omission (INCOMPLETE).**

Within the exact paths T1 names (malloc / nptl / locale / tunables), the delta vs `upstream/2.40` is **even smaller than the doc claims** — one code hunk, not "a memalign CVE patch plus packaging":

```
git diff --stat upstream/2.40 HEAD -- malloc/ nptl/ sysdeps/nptl/ \
    sysdeps/pthread/ elf/dl-tunables* locale/ iconv/ iconvdata/ csu/
 malloc/malloc.c               | 7 +++++--
 malloc/tst-malloc-too-large.c | 10 ++--------
```

- `nptl/`, `sysdeps/nptl/`, `sysdeps/pthread/`, `elf/dl-tunables.list`, `elf/dl-tunables.c`, `locale/`, `iconv/`, `iconvdata/`, `csu/` = **zero** delta.
- The only behavior-relevant change is the memalign guard: `malloc/malloc.c:5052` (`if (nb == 0 || alignment > PTRDIFF_MAX)`) + a comment at `:5068-5071`. `tst-malloc-too-large.c` is a test-only change. So **every mechanical malloc/tunable/nptl claim in the doc can be trusted against upstream** — T1's operative conclusion holds.

**What T1's scoping hides.** A full-tree diff (`git diff --name-only upstream/2.40 HEAD`, 73 files) shows the single largest Tizen source delta is a **dynamic-loader subsystem that T1 excludes by construction**:

- `elf/dlconf.c` (**+2641**), `elf/dlconf.h` (+175), `elf/dlconf-print.c` (+232), plus hooks in `elf/dl-load.c` (+87), `elf/dl-cache.c` (+154), `elf/dl-open.c`, `elf/dl-init.c`, `elf/rtld.c` (+37), `elf/dl-support.c`, `sysdeps/generic/ldsodefs.h`. Enabled by default on the image: `packaging/glibc.spec:27-28` (`%define dlconf 1`, `dlconf_all_dirs 1`), `:397-401` (`--enable-dlconf --enable-dlconf-all-dirs`), `:722-723` (`dlconf.service` wired into `local-fs.target.wants`).
- A Tizen NSS module (`nss/nss_optfiles/*`, `libnss_optfiles.so.2`) referenced by the default `nsswitch.conf`.
- `sysdeps/unix/sysv/linux/arm/kernel-features.h` — the *primary arch* — changed.

The good news (I verified it so the consolidator need not): **dlconf is memory-benign at steady state** (see negative_facts). But the doc could not assert that, because it declared the loader out of scope. The armv7l `kernel-features.h` change is **behavior-neutral** at the configured `--enable-kernel=2.6.16`: it only moves the `__ASSUME_SET_ROBUST_LIST` undef threshold from `0x030E03` (3.14.3) to `0x020620` (2.6.32), and `0x020610 < both`, so the macro is undef'd either way. Not a missed behavior delta — but confirmed, not assumed.

**Bottom line:** T1 is true as written and its trust conclusion is safe, but "the Tizen delta is just a memalign patch + packaging" is a statement about four subdirectories, not about the runtime image. The biggest Tizen runtime component (dlconf) was never in the trust boundary.

---

## 3. Part A — verdict table

Legend: **C** = CONFIRMED, **INC** = INCOMPLETE (holds but omits a consequence), **C\*** = confirmed with a precision correction.

| Item | Verdict | Evidence (file:line) | Correction / consequence if not plain CONFIRMED |
|---|---|---|---|
| **T1** | C / INC | see §2 | Scope excludes dlconf (largest delta, `elf/dlconf.c:1`, spec:27-28) and armv7l `kernel-features.h` (neutral). |
| **T2** | C | AT_SECURE gate `elf/dl-tunables.c:299-301` (`if (__libc_enable_secure) return;` before `GLIBC_TUNABLES` parse `:311-315`); build present: `Makeconfig:1262-1269` (gen `dl-tunable-list.h`), `elf/Makefile` `dl-tunables` in `dl-routines`, `csu/libc-start.c:267` (`__tunables_init`) | — |
| **G1** | C (premise) | env-tunable-dead-for-AT_SECURE premise = T2 anchor `dl-tunables.c:299-301` | Procedural gate; the code premise is sound. |
| **G2** | C\* | debug hooks live in separate `libc_malloc_debug.so.0` (`malloc/malloc-debug.c:49-78`; shipped in base `spec:771`); `do_set_mallopt_check` is a **no-op stub** `malloc/malloc.c:5464-5468` | "Normal libc compiles these out" is right for `MALLOC_CHECK_`/`glibc.malloc.check` (inert without the preload) but **wrong for `MALLOC_PERTURB_`**, which *is* live in normal libc (`perturb_byte`, `do_set_perturb_byte` `:5470-5476`, memset on every alloc/free `:1982-1994`). The real silent catastrophe is `MALLOC_PERTURB_` or the `LD_PRELOAD`, not `glibc.malloc.check` alone. |
| **L1** | C / INC | default 40 MiB `nptl/nptl-stack.c:23`, `sysdeps/nptl/dl-tunables.list:26-28`; cache/overflow-unmap `nptl/nptl-stack.c:56-130` | Cache is **process-global** (`GL(dl_stack_cache)`); queued stacks are **not** `madvise`'d, so dirty pages persist until `__munmap` (`:83`) — reducing the cap *does* return RSS. But for a **stable thread pool the 40 MiB cap is never reached → ~0 saving**; the win is real only for services that churn threads. |
| **L2** | C / INC | `arena_max` checked *before* the CPU formula `malloc/arena.c:830`; formula `NARENAS_FROM_NCORES=n*2` on 32-bit `malloc/malloc.c:1921`; `arena_test=NARENAS_FROM_NCORES(1)=2` `:1922` | armv7l mechanism the doc asserts but doesn't show: each secondary arena reserves **1 MiB** VA (`HEAP_MAX_SIZE = 2*512KiB`, `arena.c:30` × `malloc.c:955`) via a **transient 2 MiB `PROT_NONE` probe** (`arena.c:414-424`); reclaim is **`MADV_DONTNEED` (RSS only, VA retained)**, not `munmap`, unless `vm.overcommit_memory==2` (`arena.c:518` vs `:525`, gate `sysdeps/unix/sysv/linux/malloc-sysdep.h:34-57`). The real armv7l cost is **duplicated retained RSS per arena**, not VA exhaustion — the doc's "VA pressure" framing is the weaker half. |
| **L3** | C | drift on free of mmap chunk gated `!no_dyn_threshold` `malloc/malloc.c:3379-3387`; setters force `no_dyn_threshold=1` `:5430,:5450`; 32-bit cap 512 KiB `:954-955` | "Larger effect on aarch64" is correct: 32-bit drift ceiling is only 512 KiB, so pinning on armv7l has small absolute headroom. |
| **L4** | C (exact) | 64 bins / fill 7 `malloc/malloc.c:294,:313`; init `:1925-1927`; setter `do_set_tcache_count` `:5508-5518` | tcache metadata is **exactly 384 B** on armv7l (`uint16_t counts[64]` + `tcache_entry* entries[64]`, `:3118-3122`; 128+256), 640 B on aarch64 — the doc's "≈" is exact. The struct is charged to the **thread's own arena** as its first alloc (`:3251-3252`), not a separate mmap. |
| **L5** | C | `do_set_tcache_max` updates `tcache_max_bytes` + recomputes `tcache_bins` `malloc/malloc.c:5496-5506` | — |
| **L6** | C | `mtrim` is *not* top-only: after `malloc_consolidate` it `MADV_DONTNEED`s page-aligned interior free chunks `malloc/malloc.c:5155,:5192`; then `systrim` main-arena top `:5201`; all-arena walk under lock `:5218-5226` | Correct and non-obvious. Reinforced: free-path auto-trim requires `size >= FASTBIN_CONSOLIDATION_THRESHOLD (65536)` `:4776` **and** `top >= trim_threshold` — so quiescent `malloc_trim(0)` is genuinely the primary main-arena RSS lever. |
| **R1** | C | metadata `default:131072` `elf/dl-tunables.list:34-38` is **dead**: malloc applies tunables callback-only (`arena.c:300` `TUNABLE_GET(top_pad,…,set_top_pad)` with no captured value) and the callback fires only `if (cur->initialized && callback != NULL)` `elf/dl-tunables.c:467-468`; effective default = static `DEFAULT_TOP_PAD (0)` `malloc/malloc.c:936-937,:1917`. Side-effect: `do_set_top_pad` also forces `no_dyn_threshold=1` `:5440` | Doc's resolution of the discrepancy is fully correct. |
| **R2** | C | `arena_max` short-circuits before `arena_test` `malloc/arena.c:830`; comment "If arena_max is set the value of arena_test is irrelevant" `:846-852` | — |
| **R3** | C | 32-byte `rseq_area` union embedded in `struct pthread`, `aligned(32)` `nptl/descr.h:407-419` | rseq=0 cannot reclaim the embedded 32 B. Correct. |
| **R4** | C | `do_set_mmaps_max` forces `no_dyn_threshold=1` `malloc/malloc.c:5460`; tunable `minval:0` `elf/dl-tunables.list:56` | — |
| **R5** | C | one-shot `already_called` CAS guard `malloc/set-freeres.c:128-130` | Not repeatable. Correct. |
| **R6** | C | `BuildFlags="$BuildFlags -O2 -g -U_FORTIFY_SOURCE"` `packaging/glibc.spec:330`; also strips `-fstack-protector*` `:332-333` | — |
| **R7** | C | `build_locales 0` all branches `packaging/glibc.spec:64,69,74`; minimal locale via `localedef … --no-archive … en_US.UTF-8` `:552-555`; installs `/usr/lib/locale/en_US.utf8` `:800` | — |
| **L7** | C | full gconv module set built `iconvdata/Makefile:27-65`; entire `%{_libdir}/gconv` packaged in `glibc-locale` `packaging/glibc.spec:823` | — |
| **L8** | C / INC | six base NSS modules `packaging/glibc.spec:760-765`; default `nsswitch.conf` uses `compat optfiles securitymanager files dns nis`, not `db`/`hesiod` `packaging/nsswitch.conf:29-46` | (a) `libnss_files`/`libnss_dns` are **empty stubs** (`nss/Makefile`), so removing them saves ~0. (b) L8 is framed flash-only but **misses a runtime-RSS cost**: `passwd/shadow/group` resolve through **shared** modules that are `dlopen`'d and **retained for process life** (`nss/nss_module.c:183,:277`) — see Part B **N3**. |
| **L9** | C | `STRIP_KEEP_SYMTAB=*.so*` for libthread_db/valgrind/PurifyPlus `packaging/glibc.spec:529-538` | Runtime RSS impact ≈0 (correct); flash only. |
| **L10** | C | base libs incl. `libc_malloc_debug.so.0` `packaging/glibc.spec:771`; subpackages `i18ndata/locale/profile/devel-static`; `build_profile 1` default `:73` → `glibc-profile` built by default | — |

---

## 4. Top-3 challenges (design-level)

**C1 — The trust boundary excludes the biggest delta, so "verified" means less than it reads.**
T1 scopes trust to malloc/nptl/locale/tunables and finds them near-pristine (I confirm). But the doc then behaves as if that licenses the whole design, while the largest Tizen runtime component — the default-enabled `dlconf` loader (`elf/dlconf.c:1`, 2641 lines; `spec:27-28`) — is never examined. It happens to be RSS-benign, but the design didn't know that; a trust boundary drawn to exclude the biggest change isn't establishing trust, it's assuming it. Fix: state T1 as "no behavior-relevant delta in the *allocator/threading/tunables* code" and explicitly clear dlconf with the unmap anchors, rather than implying the whole tree is upstream-equivalent.

**C2 — VA is conflated with RSS in exactly the levers the acceptance protocol (M1, `smaps_rollup` Rss/Pss) will measure — which can retire good levers and keep weak ones.** Several "savings" are virtual-address, not physical, on armv7l: the static-TLS surplus (VA-only, demand-zero, never written at thread creation — `elf/dl-tls.c:637-639`), thread guard pages (`PROT_NONE`, 0 RSS — `nptl/allocatestack.c:366`), and secondary-arena heaps (1 MiB VA reserved, only touched pages resident; freed via `MADV_DONTNEED` so RSS drops but VA persists — `arena.c:525`). The doc's own L2 rationale ("armv7l VA pressure") is the weak half of the story, and it omits that **arena/`malloc_trim` frees only return commit charge under `vm.overcommit_memory==2`** (`arena.c:518` vs `:525`; `malloc-sysdep.h:34-57`). Every lever needs an explicit RSS-vs-VA label, and the measurement protocol needs `vm.overcommit_memory` recorded as a covariate.

**C3 — The lever set is an allocator-tunable monoculture, and it has no plan for the failure mode it correctly identifies.** Two anchored wins sit just outside the doc's frame: (a) **fastbin retention** — `glibc.malloc.mxfast` (default 64 on 32-bit, `malloc.c:838`) caches small frees with **no per-bin count cap**, only consolidated at a 64 KiB threshold (`:4776`); the doc tunes tcache but not fastbins. (b) **retained NSS-module dlopens** — every service that calls `getpw*`/`getgr*` at startup permanently `dlopen`s `compat`/`optfiles`/`securitymanager` (`nss_module.c:277`), tens of KB private RSS/process, which L8 treats as flash only. Meanwhile the design's Tiers 1-2 are *entirely* env-based, and the doc itself flags (G1/Q1) that env tunables are "dead on arrival" for AT_SECURE processes — with **no fallback** (spec-baked `/etc` defaults, or code) for what may be most TV daemons. If the AT_SECURE inventory comes back mostly-secure, Tiers 1-2 evaporate and there is no Plan B.

---

## 5. Part B — new-lever table

Same schema as the doc's §4 (ID · Lever · Mechanism/evidence · Expected saving · Perf risk vs budget), with verdict/rollout/risk folded in.

| ID | Lever | Verdict | Mechanism (evidence file:line) | Expected saving | Perf risk vs budget | Rollout / Risk |
|---|---|---|---|---|---|---|
| **N1** | `glibc.malloc.mxfast=0` (or small) — disable/shrink fastbins | FEASIBLE-WITH-CAVEATS | default `DEFAULT_MXFAST=64` on 32-bit `malloc/malloc.c:838`; `set_max_fast(0)`→`global_max_fast < MINSIZE` ⇒ nothing qualifies `:1779-1781`; fastbins uncapped, only drained at `FASTBIN_CONSOLIDATION_THRESHOLD=65536` `:1749,:4776`; setter `do_set_mxfast` `:5529-5539`; tunable `elf/dl-tunables.list:77-80` | Workload-bounded: removes the per-arena backlog of tiny (≤~72 B) freed chunks that otherwise sit in fastbins until a 64 KiB consolidation. Order KiB–low-MiB in tiny-object-churn services. 0 for low-churn. | **Can exceed budget** on tiny-alloc hot loops (forces `malloc_consolidate` on the fast path) — benchmark-gate. | `GLIBC_TUNABLES=glibc.malloc.mxfast=0` per service (no env alias; AT_SECURE-gated). Risk: latency on small-alloc paths; other arenas leak existing fastbin entries on reduction (`:1775-1777`). |
| **N2** | `glibc.pthread.stack_hugetlb=0` — force `MADV_NOHUGEPAGE` on thread stacks (promotes doc **Q3** to a concrete lever) | FEASIBLE-WITH-CAVEATS | default 1 `sysdeps/nptl/dl-tunables.list:36-41`, `nptl/nptl-stack.c:24`; `MADV_NOHUGEPAGE` issued only when tunable==0 `nptl/allocatestack.c:372-375` | Up to ~(2 MiB − touched) **per thread** *iff* kernel THP mode is `always` and stacks were being collapsed to 2 MiB huge pages. **0** if THP is `madvise`/`never`. | Negligible (stacks rarely benefit from THP TLB coverage). Well within budget. | `GLIBC_TUNABLES=…stack_hugetlb=0` (env or image). Risk: very low — glibc never *requests* THP for stacks, so this only reduces or no-ops. Gated on Q3 (measure `/sys/kernel/mm/transparent_hugepage/enabled`). |
| **N3** | Move `passwd`/`shadow` (and `group` where policy allows) off shared NSS modules to builtin `files` | FEASIBLE-WITH-CAVEATS | only `files`/`dns` are builtin (no dlopen) `nss/nss_module.c:172-175`; others `dlopen`'d `:183` and handle **retained for life** `:277`; current config `packaging/nsswitch.conf:29-31` uses `compat optfiles securitymanager` | Avoids per-process **retained** `dlopen` of 2-3 `libnss_*.so` (each ≈ GOT/.data/.bss + relocs, order **tens of KB private RSS/process**) on every service doing `getpw*`/`getgr*` at startup; plus flash if modules dropped. | ~0 CPU (removes a startup dlopen — net faster). | Image `/etc/nsswitch.conf`. Risk: loses `compat` (+/- NIS syntax) and Tizen `optfiles` semantics; **`group` must keep `securitymanager`**. Only where those semantics are unused. |
| **N4** | System `vm.overcommit_memory=2` (image sysctl, not glibc) to make arena/trim frees actually release commit on armv7l | FEASIBLE-WITH-CAVEATS | `check_may_shrink_heap()` true only under secure-exec or `overcommit==2` `sysdeps/unix/sysv/linux/malloc-sysdep.h:34-57`; then `shrink_heap` uses commit-releasing `MMAP PROT_NONE MAP_FIXED` `malloc/arena.c:518` instead of `MADV_DONTNEED` `:525` | Converts secondary-arena RSS drops into true commit release; amplifies L2 + L6 on 32-bit. | None from the flag itself; strict overcommit changes allocation-failure semantics system-wide. | Image sysctl. Risk: strict overcommit can fail allocations in over-committing services — validate the whole image, not one service. |
| **N5** | `LC_ALL=C` for ASCII-only/byte-oriented daemons | FEASIBLE-WITH-CAVEATS (weak) | `C`/`POSIX` locale is builtin, no mmap `locale/findlocale.c:124-137`; C uses static ASCII conv steps, never triggers the gconv-cache mmap `wcsmbs/wcsmbsload.c`, cache trigger `iconv/gconv_db.c:712` | Eliminates locale-data + gconv-cache mmaps — but both are `MAP_SHARED`/`MAP_PRIVATE` **read-only** (page-cache-shared), so this is mostly **PSS** (tens of KB), little private. | 0 (faster startup). | systemd `Environment=LC_ALL=C` per service. Risk: breaks all non-ASCII (filenames, UTF-8 text, `strcoll`/`strftime`) — only for daemons that never touch non-ASCII. |
| **N6** | Move base CLI tools/aux libs to a subpackage or `%exclude` from the TV image (flash only) | FEASIBLE | base `%files` ships `localedef`, `iconv`, `gencat`, `getent`, `libnsl.so.1`, `libBrokenLocale.so.1`, `iconvconfig` `packaging/glibc.spec` (§`%files` base ~759,783-794) | ~1 MB flash (`localedef` dominant ~0.3-0.5 MB); **0 RSS**. | 0. | spec/image. Risk: some init scripts may call `getent`/`iconv` — verify; `localedef` is unneeded on-device (`build_locales 0`). |

---

## 6. negative_facts (checked, confirmed absent/false — do not re-check)

1. **dlconf retains ~0 steady-state RSS/PSS.** Config blob `/run/dlconf.dat` and per-exe cache mappings are mmapped read-only (shared pages) and explicitly `munmap`'d both at startup completion (`elf/rtld.c:2003-2008` `dlconf_unload_cache`) **and after every `dlopen`** (`elf/dl-open.c:919-921` `_dl_unload_cache` → `elf/dlconf.c:2555-2584` munmaps `conf_data` + `cache_list`). Retained cost = sub-100-byte BSS globals in ld.so's data page. dlconf's real tax is **per-dlopen CPU/syscall** (`access`, transient mmap/munmap, sometimes `readlink /proc/self/exe`), not memory. Do not chase it for RSS.
2. **Static-TLS surplus (`glibc.rtld.optional_static_tls`, default 512; total 1664 B/thread) is VA-only, not resident.** `_dl_allocate_tls_init` memsets only each loaded module's block, never the surplus (`elf/dl-tls.c:637-639`); it lives at the top of a demand-zero stack VMA and is touched only when an initial-exec-TLS library is `dlopen`'d into it (`elf/dl-reloc.c:140`). Lowering it saves ~0 RSS on worker threads and risks `dlopen` "cannot allocate memory in static TLS block". **Not an RSS lever.**
3. **`struct pthread` / embedded `__res_state` are fixed ABI, not config levers.** `struct __res_state res` is 512 B and embedded inline per thread (`nptl/descr.h:385`, `resolv/bits/types/res_state.h:41`) — resident whether or not DNS is used. The 88 B dead `__padding` (`descr.h:158-165`) is removable only by a source/ABI edit.
4. **Thread guard pages cost 0 RSS.** Default guard = 1 page mapped `PROT_NONE` (`nptl/allocatestack.c:366`, `sysdeps/nptl/pthread_early_init.h:54`); shrinking it saves no RAM and weakens overflow detection. (`ARCH_MIN_GUARD_SIZE=0` on arm already; the 64 KiB floor is aarch64-only, still `PROT_NONE`.)
5. **`getaddrinfo` scratch buffers are not retained.** 1024 B stack union, malloc-grown only on overflow, freed at end of every call (`nss/getaddrinfo.c` `scratch_buffer_free`).
6. **`hosts: files dns` triggers no `libnss_*.so` dlopen** — `files`/`dns` are builtin (`nss/nss_module.c:172-175`). Pure DNS lookups add no resident module.
7. **UTF-8↔INTERNAL conversion is builtin** (`iconv/gconv_builtin.h`); a pure-UTF-8 service `dlopen`s **no** gconv `.so`. The `gconv-modules.cache` is `MAP_SHARED, PROT_READ` (`iconv/gconv_cache.c:80`) → low PSS. **`GCONV_PATH` is a negative lever**: it forces the cache off (`:56-58`) and reparses the text config into private malloc'd trees (`iconv/gconv_conf.c:475-498`) → *more* private RSS.
8. **`glibc.malloc.hugetlb>=2` is dangerous on armv7l** — it sets `mp_.hp_pagesize` (`malloc/malloc.c:5541-5558`), making `heap_max_size()` return `hp_pagesize*4` (`arena.c:55`) ⇒ **8 MiB per secondary arena** with 2 MiB hugepages. Anti-lever. (`hugetlb=1` only touches `thp_pagesize`, harmless.)
9. **Effective default `top_pad` is already 0**, not the 131072 in the tunables metadata (re-confirms R1). Setting `MALLOC_TOP_PAD_`/`glibc.malloc.top_pad` *increases* per-request sbrk over-reservation.
10. **`BUFSIZ` is a fixed 8192**, arch-independent (`libio/stdio.h:100`); no env/tunable lever, only `setvbuf` in application code. Wide-stream buffers are 4× (`libio/wfiledoalloc.c`), but relevant only to `fwprintf`-style services.
11. **Single-threaded services pay zero secondary-arena cost.** The main arena is brk-based; `thread_arena` is pinned to `&main_arena` at init (`malloc/arena.c:296`); a non-main arena is minted only for a second thread (`arena.c:817-865`). arena_max/mxfast levers touch only multi-threaded services.
12. **armv7l `sysdeps/unix/sysv/linux/arm/kernel-features.h` delta is behavior-neutral** at `--enable-kernel=2.6.16` (§2).

---

## 7. cannot-verify list (require on-device measurement — do not estimate)

- **Q1 / G1**: per-service `AT_SECURE` status for target TV processes — gates all env levers (L1-L5, N1-N2, N5) and the entire Tier-1/2 strategy.
- **Q3 / N2**: kernel THP mode (`/sys/kernel/mm/transparent_hugepage/enabled`) — determines whether `stack_hugetlb=0` and `malloc.hugetlb` matter at all.
- **N4 / L2 / L6**: current `vm.overcommit_memory` value — determines whether secondary-arena frees release commit (`MMAP PROT_NONE`) or only RSS (`MADV_DONTNEED`).
- **All of L1-L6, N1-N5**: actual RSS/PSS deltas per service (source proves feasibility, not magnitude); per-service benchmark regressions vs the 5-10% ceiling.
- **L1 / N1**: whether target services create/destroy threads (L1) or churn tiny allocations (N1) on the request path — governs both saving and perf risk.
- **L5**: per-service allocation-size histograms — required before lowering `tcache_max`.
- **N6**: whether any init/boot script depends on base CLI tools (`getent`, `iconv`).
- **L7 / Q5**: product encoding allowlist for gconv pruning.
- **L8 / L10 / N3 / Q4**: final device `nsswitch.conf` and the actual installed image package set.
