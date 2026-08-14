> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# Review: glibc memopt design v1

## Reviewer header

- Reviewer: Codex GPT-5
- Date: 2026-07-07
- Commit audited: `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Tree/branch: `platform/upstream/glibc`, `tizen_base`
- Method summary: read `docs/tizen_glibc_memopt_design_v1.md`; re-derived the requested diff against `upstream/2.40`; checked malloc, nptl, tunables, locale, iconv, dynamic-loader, dlconf, NSS, libio, and packaging anchors with `git diff`, `git log`, `rg`, and line-numbered source reads.

## T1 re-derivation result

Scoped result: **CONFIRMED for the paths named in the prompt, INCOMPLETE as a whole-design trust boundary.**

Commands used:

```sh
git diff --stat upstream/2.40..HEAD -- malloc nptl sysdeps/nptl sysdeps/pthread elf/dl-tunables.c elf/dl-tunables.list locale iconvdata iconv packaging
git diff --name-status upstream/2.40..HEAD -- malloc nptl sysdeps/nptl sysdeps/pthread elf/dl-tunables.c elf/dl-tunables.list locale iconvdata iconv packaging
git log --oneline upstream/2.40..HEAD -- malloc nptl sysdeps/nptl sysdeps/pthread elf/dl-tunables.c elf/dl-tunables.list locale iconvdata iconv packaging
```

Evidence:

- In the scoped non-packaging paths, the only behavior-relevant malloc change is commit `93fd24e807`, which adds `alignment > PTRDIFF_MAX` to `_int_memalign` at `malloc/malloc.c:5036-5053`; that commit also changes the test `malloc/tst-malloc-too-large.c`.
- No diff appeared for `nptl`, `sysdeps/nptl`, `sysdeps/pthread`, `locale`, `iconvdata`, `iconv`, or `elf/dl-tunables*` against `upstream/2.40`.
- Packaging is not only packaging in effect: the current tree has a Tizen dynamic-loader delta outside T1's scoped paths. `git diff --stat upstream/2.40..HEAD -- elf` shows 14 changed files, including `elf/dlconf.c`, `elf/dlconf.h`, `elf/dl-cache.c`, `elf/dl-load.c`, `elf/dl-open.c`, and `elf/rtld.c`. `elf/Makefile:89-94` compiles `dlconf`/`dlconf-print` into `dl-routines` when enabled, and `packaging/glibc.spec:27-28,396-402` enables both `dlconf` and `dlconf_all_dirs`.

## Part A verdict table

| Item | Verdict | Evidence | Correction/consequence if not CONFIRMED |
|---|---|---|---|
| T1 | INCOMPLETE | `malloc/malloc.c:5036-5053`; `git diff --name-status upstream/2.40..HEAD -- elf` shows dlconf loader delta | Scoped malloc/nptl/locale/tunables claim holds, but the design trust boundary must include Tizen `dlconf` runtime loader code. |
| T2 | CONFIRMED | `Makeconfig:1257-1269`, `elf/Makefile:78-85`, `csu/libc-start.c:264-268`, `sysdeps/unix/sysv/linux/dl-parse_auxv.h:41-47`, `elf/dl-tunables.c:289-355` | None. Env tunables remain dead for `AT_SECURE` processes. |
| G1 | UNVERIFIABLE-FROM-SOURCE | `elf/dl-tunables.c:299-301`; `sysdeps/unix/sysv/linux/dl-parse_auxv.h:45-46` | Needs on-device per-service `AT_SECURE` inventory. |
| G2 | REFUTED | `malloc/malloc.c:1978-1994`, `malloc/malloc.c:5464-5475`, `malloc/malloc-debug.c:49-78`, `elf/rtld.c:2674-2760`, `iconv/gconv_cache.c:54-58` | `MALLOC_CHECK_` is no-op in normal libc, but `MALLOC_PERTURB_` is active in normal libc via `do_set_perturb_byte`. Gate also misses `LD_DEBUG*`, `LD_AUDIT`, `LD_PROFILE`, `LD_PRELOAD`, and `GCONV_PATH`. |
| L1 | CONFIRMED | `sysdeps/nptl/dl-tunables.list:26-29`, `nptl/nptl-stack.c:23-24,56-130` | Magnitude is device/workload-only. |
| L2 | CONFIRMED | `elf/dl-tunables.list:58-62`, `malloc/malloc.c:1921`, `malloc/arena.c:817-865` | armv7l cap formula is 2x cores; contention needs benchmark. |
| L3 | CONFIRMED | `malloc/malloc.c:945-958,3375-3388,5422-5451` | Also note `top_pad` and `mmap_max` setters disable dynamic thresholds at `malloc/malloc.c:5434-5441,5454-5461`. |
| L4 | INCOMPLETE | `malloc/Makefile:339-340`, `malloc/malloc.c:292-317,3102-3125,3241-3278,3301-3318,4508-4555,5508-5517` | Runtime `tcache_count=0` stops caching chunks, but the fixed 64-bin per-thread tcache struct is still allocated on first malloc. Do not count metadata as saved by this tunable. |
| L5 | INCOMPLETE | `malloc/malloc.c:5494-5505`, `malloc/malloc.c:3118-3125` | Lowering `tcache_max` changes eligible bins and cached chunks, not the fixed per-thread tcache struct size. |
| L6 | CONFIRMED | `malloc/malloc.c:5151-5195,5200-5228` | Correctly not top-only; all-arena lock/refault risk must be benchmarked. |
| L7 | CONFIRMED | `iconvdata/Makefile:26-65,254-259`, `packaging/glibc.spec:813-823` | Encoding allowlist is external/product-owned. |
| L8 | CONFIRMED | `packaging/glibc.spec:752-765`, `packaging/nsswitch.conf:29-46` | Final device `nsswitch.conf` still must be checked. |
| L9 | CONFIRMED | `packaging/glibc.spec:529-538` | Runtime RSS impact remains approximately zero; flash impact needs build/package measurement. |
| L10 | INCOMPLETE | `packaging/glibc.spec:752-771,858-909,911-918` | Add `glibc-devel-utils` to the audit list: it packages `libmemusage.so`, `libpcprofile.so`, and `libthread_db` files. |
| R1 | CONFIRMED | `malloc/malloc.c:936-937,1915-1919,5434-5441`, `elf/dl-tunables.list:34-38`, `elf/dl-tunables.c:437-469` | None. `top_pad=0` should stay rejected. |
| R2 | CONFIRMED | `malloc/arena.c:830-852` | None. `arena_test` is irrelevant once `arena_max` is set. |
| R3 | CONFIRMED | `nptl/descr.h:407-419` | None. `rseq=0` does not shrink `struct pthread`. |
| R4 | CONFIRMED | `malloc/malloc.c:973-994,3375-3388,5454-5461` | Lowering `mmap_max` reduces independently unmappable allocations and also disables dynamic thresholds. |
| R5 | CONFIRMED | `malloc/set-freeres.c:123-244` | None. One-shot `already_called` guard makes it unsuitable for resident cleanup. |
| R6 | CONFIRMED | `packaging/glibc.spec:329-356` | Source cannot bound flash/perf; needs experimental build. |
| R7 | CONFIRMED | `packaging/glibc.spec:59-76,547-556,796-800` | None. Locale archive minimization is already default in this spec. |

## Top-3 challenges

1. **T1 is too narrow for the actual Tizen tree.** The scoped allocator/thread/tunables paths are close to upstream 2.40, but Tizen `dlconf` is compiled into the dynamic loader and enabled by spec (`packaging/glibc.spec:27-28,396-402`; `elf/Makefile:89-94`). That is a runtime memory/perf surface and should be audited beside allocator tunables.
2. **G2 is both wrong and too small.** `MALLOC_PERTURB_` is not compiled out of normal libc (`malloc/malloc.c:5470-5475`). The hygiene gate should also cover loader and conversion env vars: `LD_DEBUG*`, `LD_AUDIT`, `LD_PROFILE`, `LD_PRELOAD`, and `GCONV_PATH` (`elf/rtld.c:2674-2760`; `iconv/gconv_cache.c:54-58`).
3. **The tcache section needs sharper accounting.** `tcache_count` and `tcache_max` reduce cached chunks, but not the fixed per-thread tcache metadata, because `malloc.c` still initializes `tcache_perthread_struct` on first malloc (`malloc/malloc.c:3118-3125,3241-3278,3301-3318`).

## Part B new-lever table

| ID | Verdict | Lever | Evidence | Expected saving | Perf cost vs 5-10% budget | Rollout/risk |
|---|---|---|---|---|---|---|
| B1 | FEASIBLE-WITH-CAVEATS | Tune static TLS surplus per service: test `GLIBC_TUNABLES=glibc.rtld.nns=1:glibc.rtld.optional_static_tls=0` where no audit/dlmopen/static-TLS-heavy plugins are used. | Tunables at `elf/dl-tunables.list:120-131`; formula at `elf/dl-tls.c:103-137`; optional usage/fallback at `elf/dl-reloc.c:63-101`; per-thread allocation at `elf/dl-tls.c:441-502`. | Formula-level saving: default surplus 1664 bytes can drop to 288 bytes with `nns=1,optional_static_tls=0`, before page/alignment effects. | Usually zero unless a service relies on optimized static TLS for dlopened modules; hot TLS paths can regress and must be benchmarked. | Env-only, AT_SECURE-gated. Risk is dlmopen/audit capacity and TLS model fallout. |
| B2 | FEASIBLE-WITH-CAVEATS | For high-thread-count services, use `pthread_setattr_default_np` or explicit `pthread_attr_setguardsize` to reduce guard size only where stack-overflow detection is not required. | Default guard is one page at `nptl/pthread_attr_init.c:45-46`; stack allocation adds guard and uses `PROT_NONE` when guard is nonzero at `nptl/allocatestack.c:335-367`. | VA saving is page-sized per live thread on armv7l; RSS/PSS saving is normally near zero because guard pages are not committed. | No allocator hot-path cost. Correctness risk is loss of guard-page overflow detection. | Service code change, not glibc. Treat as VA-pressure lever, not RSS lever. |
| B3 | FEASIBLE-WITH-CAVEATS | Measure disabling `dlconf_all_dirs`, or disabling `dlconf` entirely for TV profiles that do not require loader isolation. | Spec enables both at `packaging/glibc.spec:27-28,396-402`; loader calls dlconf in `elf/dl-load.c:2071-2107` and `elf/dl-open.c:593-598`; dlconf maps/allocates state at `elf/dlconf.c:77-91,2251-2267,2381-2440,2555-2584`. | KiB-class text/data and transient loader allocation/mmap reductions; exact RSS/PSS needs built-image measurement. | Likely improves startup/dlopen cost if isolation is unnecessary. | Spec/build lever. Risk is policy/security behavior for dlopen/cache isolation. |
| B4 | FEASIBLE | Extend service-launcher env hygiene to block `GCONV_PATH`, `LD_PROFILE`, `LD_AUDIT`, `LD_DEBUG*`, and unintended `LD_PRELOAD`. | `GCONV_PATH` disables gconv cache at `iconv/gconv_cache.c:54-58`; `LD_DEBUG`, `LD_AUDIT`, `LD_PROFILE`, `LD_PRELOAD`, and profile output parsing are in `elf/rtld.c:2674-2760`; profiling allocates/maps output state in `elf/dl-profile.c:180-235,318-328`. | Prevents pathological I/O, mappings, audit DSOs, cache bypass, and profiling buffers. No steady-state saving if already clean. | No perf cost; positive if it catches bad env. | Launcher lint/systemd audit. Also closes a trust-boundary hole in G2. |
| B5 | FEASIBLE-WITH-CAVEATS | For services with many idle `FILE *` handles, set smaller/user buffers or `_IONBF` using `setvbuf`, or close idle streams. | `BUFSIZ` is 8192 at `libio/stdio.h:100`; `_IO_file_doallocate` mallocs up to `BUFSIZ` at `libio/filedoalloc.c:74-105`; `setvbuf` can set unbuffered/custom buffers at `libio/iosetvbuf.c:34-95`; memory streams allocate `BUFSIZ` at `libio/memstream.c:48-63`. | About 8 KiB per default-buffered active stream, workload-dependent. | Can exceed budget on I/O-heavy paths if buffering is removed; safe for idle/control streams after measurement. | Service code audit, not glibc. |
| B6 | FEASIBLE-WITH-CAVEATS | Keep gconv cache usable and avoid service-level `GCONV_PATH`; if a TV gconv allowlist ships, regenerate `gconv-modules.cache` for the pruned set. | Cache load returns early on success at `iconv/gconv_conf.c:467-472`; cache mmap/fallback heap path at `iconv/gconv_cache.c:47-107`; spec/post-upgrade creates/updates cache at `packaging/glibc.spec:540-542` and `packaging/glibc_post_upgrade.c:121-128`. | KiB-class in iconv-using processes by avoiding config parsing and heap fallback; also improves lookup time. | No expected regression if cache matches installed modules. | Packaging plus env hygiene. Risk is stale cache after gconv pruning. |

## negative_facts

- No scoped diff against `upstream/2.40` for `nptl`, `sysdeps/nptl`, `sysdeps/pthread`, `locale`, `iconvdata`, `iconv`, or `elf/dl-tunables*`.
- No `tcache` commit appears in `git log upstream/2.40..HEAD -- malloc nptl sysdeps/nptl sysdeps/pthread elf/dl-tunables.c elf/dl-tunables.list`.
- Current build sets `CPPFLAGS-malloc.c += -DUSE_TCACHE=1`; only `malloc-debug.c` uses `-DUSE_TCACHE=0` (`malloc/Makefile:339-340`).
- `glibc.malloc.top_pad=0` is already allocator default (`malloc/malloc.c:936-937,1917`).
- `glibc.malloc.arena_test` is not a cap when `arena_max` is set (`malloc/arena.c:830-852`).
- `glibc.pthread.rseq=0` cannot remove the embedded 32-byte `rseq_area` from `struct pthread` (`nptl/descr.h:407-419`).
- Locale archive minimization is already the spec default (`packaging/glibc.spec:59-76,547-556,796-800`).
- `--disable-nscd` is already in the configure flags (`packaging/glibc.spec:372-376`).
- armv7l/aarch64 fall under the spec's non-x86 `--disable-multi-arch` branch (`packaging/glibc.spec:386-388`), so arm string/memory multiarch pruning is already default for this build.

## cannot-verify list

- Per-service `AT_SECURE` status on target TV devices.
- Actual RSS/PSS/PSI savings and allocation-path regressions for L1-L6 and B1-B6.
- Whether TV services use `dlmopen`, audit modules, or dlopened IE/static TLS modules that would make B1 unsafe.
- Whether reducing pthread guard size is safe for any target service.
- Final TV image package set, including accidental `glibc-locale`, `glibc-i18ndata`, `glibc-profile`, `glibc-devel-static`, `glibc-devel-utils`, or `libc_malloc_debug.so.0`.
- Final device `/etc/nsswitch.conf`.
- Product encoding inventory for gconv allowlisting.
- Whether service launchers are clean of `GLIBC_TUNABLES`, `MALLOC_*`, `LD_*`, and `GCONV_PATH` surprises.
- Kernel THP/hugetlb state for `glibc.malloc.hugetlb` and `glibc.pthread.stack_hugetlb`.
- Flash delta from `.symtab`/`.strtab`, `dlconf`, gconv allowlists, or `-Os` experiments; requires package/build artifacts.
