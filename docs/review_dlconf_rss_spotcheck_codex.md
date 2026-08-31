> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# dlconf Steady-State RSS Spot-Check

## Header

- Model: Codex (GPT-5)
- Date: 2026-07-07
- Tree: `<WORKSPACE>`
- Branch/commit: `tizen_base`, `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Method: static trace of Tizen dlconf only: `elf/dlconf.c`, `elf/dlconf.h`, `elf/dl-cache.c`, `elf/dl-load.c`, `elf/dl-open.c`, `elf/rtld.c`, and fd/mmap helpers.

## Verdict

REFUTED. The main dlconf config/cache file mappings are transient and are unmapped at the cited points, and the static dlconf globals are under 100 B; however, `dl-cache.c` can allocate a per-cache `glibc_hwcaps_priorities` array and `dlconf_unload_cache()` frees the enclosing `struct caches` without freeing that array. That is a surviving heap allocation, so the "nothing retained" claim is false.

## Evidence Walk

| Path | Finding | Evidence |
|---|---|---|
| P1. Unload sites and allocation/mapping matching | `dlconf_unload_cache()` walks `cache_list`, unmaps each cache mapping, frees `cache_name` and the `struct caches`, frees dlconf global string-list arrays, and unmaps `conf_data`. It also resets `conf_data_size`. | `elf/dlconf.c:2555-2584` |
| P1. `/run/dlconf.dat` mapping | `/run/dlconf.dat` is mapped by `load_conf_dat` via `_dl_sysdep_read_whole_file`; on success the mapping is stored in `conf_data`/`conf_data_size`; on invalid header it is immediately unmapped. | `elf/dlconf.c:2231-2248`, `elf/dlconf.c:2578-2583` |
| P1. dlconf entry heap | Runtime `conf_dat_entry` objects and their `string_list` nodes are allocated while reading `dlconf.dat`; list strings point into the mapped file and are not separately allocated; callers free the nodes and entry with `free_centry`. | `elf/dlconf.c:1908-1924`, `elf/dlconf.c:2135-2152`, `elf/dlconf.c:2381-2407`, `elf/dlconf.c:263-268`, `elf/dlconf.c:2470-2515`, `elf/dlconf.c:2530-2552` |
| P1. cache file mapping | Custom cache files are loaded through `dlconf_load_cache_lookup_from`; the map and size are stored in the per-cache `struct caches`, then later unmapped by `dlconf_unload_cache`. | `elf/dl-cache.c:478-587`, `elf/dlconf.c:2410-2440`, `elf/dlconf.c:2560-2566` |
| P1. unmatched heap allocation | REFUTE: the DLCONF branch stores `glibc_hwcaps_priorities` inside `struct caches`; `glibc_hwcaps_priorities_init` allocates `length * sizeof(uint32_t)`, but `dlconf_unload_cache` only zeroes `glibc_hwcaps_priorities_length` and frees the wrapper. It never calls `glibc_hwcaps_priorities_free(the_cache)`, even though that helper exists. | `elf/dlconf.h:45-63`, `elf/dl-cache.c:53-64`, `elf/dl-cache.c:128-158`, `elf/dl-cache.c:221-241`, `elf/dl-cache.c:383-389`, `elf/dlconf.c:2567-2573` |
| P1. additional correctness issue | `dlconf_find_cache` allocates `struct caches` with `malloc` and initializes cache pointers, size, next, and name, but does not initialize the `glibc_hwcaps_priorities*` fields under `#ifdef SHARED`. This makes the hwcaps path even less safe to certify as "nothing retained." | `elf/dlconf.c:2410-2440`, `elf/dlconf.h:51-62` |
| P2. dlopen failure | For errors raised inside `dl_open_worker`, `_dl_open` catches the exception, calls `_dl_unload_cache()`, then does error cleanup/reraises. Thus dlconf mappings made during `_dl_map_object` or `dlconf_allowed_dlopen` are cleaned on those failure paths. | `elf/dl-open.c:916-960` |
| P2. pre-catch dlopen errors | Invalid mode and invalid namespace errors happen before `_dl_catch_exception` and before `_dl_unload_cache`, but these branches occur before dlconf lookup/mapping in `_dl_map_object`/`dlconf_allowed_dlopen`, so they do not create new dlconf maps. | `elf/dl-open.c:854-902`, `elf/dl-open.c:580-599` |
| P2. missing `dlconf.dat` | If `conf_data == NULL`, dlconf checks `file_exists(DLCONF_DAT_PATH)` first. Missing file means no map is created and lookup returns no entry. | `elf/dlconf.c:1977-1979`, `elf/dlconf.c:2251-2267` |
| P2. malformed/version mismatch | If both magic and version fail, `load_conf_dat` unmaps immediately. Correction: the header check uses `magic matches OR version matches`, not AND, so a file with matching magic but wrong version is accepted transiently until the normal unload point. | `elf/dlconf.c:2215-2229`, `elf/dlconf.c:2231-2248`, `elf/dlconf.c:2578-2583` |
| P3. repeated dlopen | On Linux targets, `MAP_COPY` is not provided by the Linux mmap headers, so `_dl_unload_cache()` is compiled. Each normal `dlopen` maps dlconf/cache data on demand and then calls `_dl_unload_cache()` after `_dl_catch_exception`. However, the hwcaps array leak can repeat per triggering cache lookup. | `sysdeps/unix/sysv/linux/bits/mman-linux.h:41-56`, `elf/dl-open.c:20-27`, `elf/dl-open.c:916-922`, `elf/dl-cache.c:652-662` |
| P4. `dl_close`, `dlmopen`, namespaces | No dlconf references were found in `elf/dl-close.c`. `dlmopen` uses the same `_dl_open` path and same post-catch `_dl_unload_cache()`. dlconf state is global (`conf_data`, `cache_list`, `g_caches`, `g_dlopen_paths`), not per namespace. | `elf/dl-open.c:854-922`, `elf/dlconf.c:77-89` |
| P5. retained globals | Static dlconf globals are under 100 B: 40 B on armv7l, 72 B on aarch64, computed from the source types. The reviewer's BSS-only number is correct but incomplete because of the orphanable heap allocation above. | `elf/dlconf.c:77-89`, `misc/search.h:97-102` |
| P6. file descriptors | `_dl_sysdep_read_whole_file` opens with `O_RDONLY | O_CLOEXEC`, maps the file, and closes the fd before returning. Runtime dlconf/cache maps therefore do not retain fds. Generator-only code also closes `DIR *` and output fd on its normal paths. | `elf/dl-misc.c:35-62`, `elf/dlconf.c:310-348`, `elf/dlconf.c:1518-1577`, `elf/dlconf.c:2076-2119` |
| P7. mapping flags | Runtime `dlconf.dat` and cache reads pass `PROT_READ`; `_dl_sysdep_read_whole_file` maps with `MAP_PRIVATE` on Linux because `MAP_COPY` is absent. While mapped, pages are file-backed read-only/transient, not private dirty RSS. | `elf/dlconf.c:2231-2235`, `elf/dl-cache.c:512-518`, `elf/dl-misc.c:35-62`, `sysdeps/unix/sysv/linux/bits/mman-linux.h:41-56` |
| P8. `dlconf_all_dirs=1` | Tizen enables all-dirs in the spec. With `DLCONF_ALL_DIRS`, the path filter in `dlconf_get_cached_path` is compiled out, so more programs can trigger transient dlconf work and the hwcaps leak path, but unload behavior is unchanged. | `packaging/glibc.spec:23-28`, `packaging/glibc.spec:396-402`, `elf/dlconf.c:2518-2530`, `elf/dlconf.c:2555-2584` |
| P9. ld.so.cache hook interaction | DLCONF replaces upstream static cache globals with per-cache `struct caches` nodes. `_dl_unload_cache()` delegates to `dlconf_unload_cache`, so cache mappings are not retained, but the DLCONF per-cache hwcaps allocation is not freed. | `elf/dl-cache.c:30-38`, `elf/dl-cache.c:486-498`, `elf/dl-cache.c:580-587`, `elf/dl-cache.c:652-662`, `elf/dlconf.c:2555-2584` |

## Retained-State Inventory

| Survivor | Size | Lifetime | Evidence |
|---|---:|---|---|
| `conf_data` | 4 B armv7l / 8 B aarch64 | Static BSS; value reset to NULL after unload. | `elf/dlconf.c:77`, `elf/dlconf.c:2578-2582` |
| `conf_data_size` | 4 B armv7l / 8 B aarch64 | Static BSS; value reset to 0 after unload. | `elf/dlconf.c:78`, `elf/dlconf.c:2580-2582` |
| `path_htab` (`struct hsearch_data`) | 12 B armv7l / 16 B aarch64 | Static BSS. Generator path creates/destroys its table; normal runtime does not use it. | `elf/dlconf.c:79`, `misc/search.h:97-102`, `elf/dlconf.c:1669-1700`, `misc/hsearch_r.c:96-102`, `misc/hsearch_r.c:120-125` |
| `g_caches` | 8 B armv7l / 16 B aarch64 | Static BSS; element array freed/reset by unload/generator cleanup. | `elf/dlconf.c:81-87`, `elf/dlconf.c:2003-2012`, `elf/dlconf.c:2341-2345`, `elf/dlconf.c:2577` |
| `g_dlopen_paths` | 8 B armv7l / 16 B aarch64 | Static BSS; element array freed/reset by unload/generator cleanup. | `elf/dlconf.c:81-87`, `elf/dlconf.c:2003-2012`, `elf/dlconf.c:2341-2345`, `elf/dlconf.c:2577` |
| `cache_list` | 4 B armv7l / 8 B aarch64 | Static BSS; set to NULL after unload. | `elf/dlconf.c:89`, `elf/dlconf.c:2555-2577` |
| Orphaned `glibc_hwcaps_priorities` heap array | `4 * N` bytes per triggering cache, plus allocator overhead; `N = cache_extension_tag_glibc_hwcaps.size / 4` | Survives after unload because the containing `struct caches` is freed without freeing the array. Repeated dlopen can repeat the leak. | `elf/dl-cache.c:128-158`, `elf/dl-cache.c:221-241`, `elf/dl-cache.c:383-389`, `elf/dlconf.c:2567-2573` |
| Runtime dlconf/cache mappings | 0 B steady-state if unload runs | Mapped transiently, then unmapped. | `elf/dlconf.c:2231-2248`, `elf/dl-cache.c:512-587`, `elf/dlconf.c:2555-2584` |
| Runtime dlconf/cache fds | 0 | Closed before returning from `_dl_sysdep_read_whole_file`. | `elf/dl-misc.c:35-62` |

Static BSS total: 40 B on armv7l and 72 B on aarch64. Corrected total after no hwcaps trigger is that BSS total only. Corrected total after a hwcaps-triggering cache lookup is: static BSS total + `4 * N` bytes per triggered cache lookup instance, plus malloc metadata/rounding. The source tree does not contain the target `/run/dlconf.dat` or cache files, so `N` cannot be fixed from source alone.

## Per-dlopen Transient Cost

For a dlopen that reaches dlconf lookup, the transient cost is:

- `access(DLCONF_DAT_PATH)` from `file_exists`, then `open`/`fstat`/`mmap(PROT_READ, MAP_PRIVATE)`/`close` for `/run/dlconf.dat` if present (`elf/dlconf.c:1977-1979`, `elf/dlconf.c:2231-2248`, `elf/dl-misc.c:35-62`).
- Heap allocation for one `conf_dat_entry` and list nodes pointing into `conf_data`, freed before return from `dlconf_allowed_dlopen` or `dlconf_get_cached_path` (`elf/dlconf.c:2381-2407`, `elf/dlconf.c:2470-2515`, `elf/dlconf.c:2530-2552`).
- For each configured cache path consulted: `malloc`/`strdup` for `struct caches`, `open`/`fstat`/`mmap(PROT_READ, MAP_PRIVATE)`/`close` for the cache file, search, then unload unmaps/free wrappers (`elf/dlconf.c:2410-2440`, `elf/dl-cache.c:512-587`, `elf/dlconf.c:2555-2577`).
- If a named glibc-hwcaps cache entry is evaluated, `glibc_hwcaps_priorities_init` may allocate `4 * N` bytes. That allocation is not freed by unload and is the RSS-cleanliness refutation (`elf/dl-cache.c:128-158`, `elf/dl-cache.c:383-389`, `elf/dlconf.c:2567-2573`).

Even after fixing the leak, this remains a CPU/latency concern: every dlopen can remap/read `/run/dlconf.dat` and one or more cache files because steady-state cleanup intentionally drops those mappings.

## negative_facts

- No runtime fd for `/run/dlconf.dat` or cache files survives `_dl_sysdep_read_whole_file`; fds are closed before the mapped pointer is returned (`elf/dl-misc.c:35-62`).
- Missing `/run/dlconf.dat` creates no mapping (`elf/dlconf.c:1977-1979`, `elf/dlconf.c:2251-2267`).
- If both magic and version fail the header check, the partial `dlconf.dat` mapping is unmapped immediately (`elf/dlconf.c:2215-2248`).
- `conf_dat_entry` and runtime string-list nodes are freed on the normal `dlconf_allowed_dlopen` and `dlconf_get_cached_path` paths (`elf/dlconf.c:263-268`, `elf/dlconf.c:2470-2515`, `elf/dlconf.c:2530-2552`).
- No dlconf per-namespace state was found; dlmopen uses the same `_dl_open` cleanup path, and no dlconf references were found in `elf/dl-close.c` (`elf/dl-open.c:854-922`, `elf/dlconf.c:77-89`).
- `DLCONF_ALL_DIRS` changes the set of callers that use dlconf, not the unload routine (`elf/dlconf.c:2518-2530`, `elf/dlconf.c:2555-2584`).
- The rejected mapping-retention story is not the problem: cache/config mappings are unmapped. The surviving state is a conditional heap leak in the dl-cache hwcaps helper path.

## Corrected R9

R9 should not say "disable dlconf is not an RSS lever because nothing is retained." Corrected wording:

`disable dlconf` is not a large config/cache-mapping RSS lever, because those mappings are transient and normally unmapped. However, this Tizen dlconf implementation has a conditional steady-state heap leak in the glibc-hwcaps cache path: `4 * N` bytes per triggering cache lookup instance plus allocator overhead, repeatable across dlopen. Treat R9 as open until `struct caches` initializes its hwcaps fields and `dlconf_unload_cache()` frees `glibc_hwcaps_priorities` before freeing each cache node; after that fix, disabling dlconf should be rejected as an RSS lever and kept only as a CPU/latency/flash-policy discussion.
