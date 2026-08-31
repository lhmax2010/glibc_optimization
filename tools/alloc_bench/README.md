> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# alloc_bench

`alloc_bench` is a single-process libc allocator microbenchmark for the Tizen
glibc memory-optimization matrix. It dynamically links against libc and
pthread so `GLIBC_TUNABLES` follows the same path as production services.

## Build

```sh
make host
make host-asan
make armv7l
```

The `armv7l` target uses `ARMV7L_CC` and optional `ARMV7L_SYSROOT` from the
Makefile top section. In this workspace the default `ARMV7L_CC` wraps the GBS
armv7l scratch root with `bwrap` because the Tizen cross compiler's helper
programs expect `/emul`, `/usr`, and `/lib` to point inside that scratch root:

```sh
make armv7l ARMV7L_ROOT=/path/to/scratch.armv7l.0
make armv7l ARMV7L_CC=/path/to/armv7l-tizen-linux-gnueabi-gcc
make armv7l ARMV7L_CC=/path/to/gcc ARMV7L_SYSROOT=/path/to/sysroot
```

## CLI

```text
alloc_bench [options]
  --profile NAME              small-churn|mixed|medium-only|large-transient|thread-churn|burst-free-small|unsorted-drain|external:FILE
  --threads N                 worker threads; default is online CPUs
  --seed N                    global seed; per-thread seed is seed ^ ordinal
  --warmup S                  warmup seconds; default 5
  --duration S                measure seconds for duration mode; default 30
  --idle S                    idle seconds; default 10
  --ops-per-thread N          fixed-op measure mode; overrides --duration
  --live-set N                live objects per thread
  --churn-period-ms N         thread-churn generation period; default 2000
  --stagger-churn             stagger thread-churn deadlines by thread ordinal
  --touch-full                fully write-touch every allocation
  --idle-release PCT          release PCT% of live pool at idle entry; default 0
  --release-order ORDER       high|low|random|interleave; default high
  --idle-trim                 call malloc_trim(0) after idle release, before idle
  --post-trim-ops-per-thread N  unmeasured live-pool ops after trim; default 0
  --cycles N                  controlled allocation/release cycles; max 64
  --cycle-rise S              paced allocation duration/cycle; default 3.4
  --cycle-peak S              peak hold duration/cycle; default 4.7
  --release-duration S        paced release duration; default 0 (instant)
  --cycle-valley S            valley hold duration/cycle; default 0
  --trim-at POINT             none|peak|fall-mid|valley|valley+N
  --burst-size N              burst-free-small burst pool size; default 2048
  --burst-hold-ops N          burst-free-small hold ops; default 4096
  --unsorted-batch N          unsorted-drain fill batch size; default 4096
  --outdir DIR                malloc_info XML output dir; default .
```

Use `--duration` for throughput comparisons. Use `--ops-per-thread` for
determinism checks because each thread then executes a fixed number of measured
operations independent of host speed.

Stdout is one JSON object. `malloc_info()` XML files are written under
`--outdir` at measure and idle phase boundaries.

## Built-In Profiles

| profile | size distribution | weights | live-set/thread | extra behavior |
|---|---|---|---:|---|
| `small-churn` | 16, 32, 64, 128, 256 B | uniform 1:1:1:1:1 | 256 | tight random replacement in live pool |
| `mixed` | 16 B, 64 B, 256 B, 1 KiB, 4 KiB, 16 KiB, 32 KiB, 64 KiB | 8, 12, 18, 24, 18, 12, 6, 2 | 4096 | random replacement in live pool |
| `medium-only` | 1, 2, 4, 8, 16 KiB | uniform 1:1:1:1:1 | 4096 | random replacement in live pool; intended for medium-allocation sensitivity checks |
| `large-transient` | same base distribution as `mixed`; every 100th op uses 256 KiB, 512 KiB, 1 MiB, or 2 MiB uniformly | base weights as `mixed`; large sizes uniform when triggered | 4096 | each large allocation is held for 100 ops before replacement |
| `thread-churn` | same distribution as `mixed` | 8, 12, 18, 24, 18, 12, 6, 2 | 4096 | worker threads really `pthread_exit`; main recreates them every 2000 ms by default |
| `burst-free-small` | burst pool: 16, 24, 32, 40, 48, 56, 64 B; background live pool uses the same distribution | uniform | 256 | allocate `--burst-size` objects, free 50% in deterministic PRNG order, hold survivors for `--burst-hold-ops`; background live ops interleave at 1:8 |
| `unsorted-drain` | fill group: 256, 512, 1024, 2048, 4096 B; request group: 96, 128, 160, 192 B; background live pool uses `mixed` | uniform within fill/request groups; mixed weights for background | 4096 | fill `--unsorted-batch`, free all in deterministic order, allocate `batch/2` request objects, repeat; background live ops interleave at 1:8 |

Default write touching is v1.1 policy: objects smaller than 128 KiB use the v1
first/last 64 B strategy (objects smaller than 128 B are fully written), while
allocations at least 128 KiB are fully written. `--touch-full` fully writes all
allocations.

During measure, the main thread samples `/proc/self/smaps_rollup` every 2 s and
adds `measure_rss_kb_p50`, `measure_rss_kb_p95`, `measure_rss_kb_max`, and
`measure_rss_kb_n_samples` under `memory`. The old three end-of-measure samples
and median fields are retained.

`--idle-release PCT` asks workers to stop at the idle boundary, release PCT% of
their live pool, then idle normally. `--release-order` selects deterministic
high-address, low-address, random, or interleaved order. Interleaved order sorts
objects by address and releases even positions before odd positions, so 50%
means every other object. Random order uses a per-thread stream derived from the
global seed and does not consume the measured op stream. JSON reports the order,
released object/payload counts, `idle_release_pct`, and
`idle_rss_kb_after_release`.

`--idle-trim` is opt-in instrumentation for active trimming. It only takes
effect together with `--idle-release`: after worker release completion and
before the idle sleep, the main thread calls `malloc_trim(0)`. JSON reports
top-level `idle_trim`, `idle_trim_ret`, `idle_free_bytes_measure`, and
`idle_free_bytes_idle`. The free-byte fields are computed in-process from the
measure/idle `malloc_info()` XML top-level `fast + rest` totals; the XML files
are still written for manual inspection.

For applicability scans, the benchmark also writes release and immediate
post-trim XML snapshots. `memory.malloc_info_stats` reports fast, rest,
unsorted, and arena counts for all four boundaries. The `memory` object reports
glibc-heap Private_Dirty before/after trim using the project-wide `[heap]` plus
1 MiB-aligned anonymous-arena heuristic, exact trim call time, and process fault
counters. `--post-trim-ops-per-thread N` performs N unmeasured live-pool ops per
worker after trim and reports the resulting elapsed time and minflt/majflt
counters; it requires both `--idle-release` and `--idle-trim`.

## Controlled Cycles

`--cycles N` selects a separate controlled mode for repeated allocation and
release phases. Each worker owns a persistent live pool and allocator arena.
At the start of each cycle it fills empty slots evenly over `--cycle-rise`,
holds the full pool for `--cycle-peak`, releases `--idle-release PCT` evenly
over `--release-duration`, then waits for `--cycle-valley`. A zero release
duration preserves the original instantaneous-release behavior.

`--trim-at` controls the in-process `malloc_trim(0)` call: `peak`,
`fall-mid`, `valley`, or `valley+N` seconds. `none` is the baseline. Delayed
trim requires `--cycle-valley` to be at least N. Cyclic mode accepts the normal
size profiles and release orders, but rejects fixed-op mode, thread-churn,
burst-free-small, and unsorted-drain because their phase machines are separate.

The JSON schema name remains `alloc_bench_v1_1`; cyclic runs use
`"mode":"cyclic"` and add `cycle_data`. Every cycle reports heap
Private_Dirty at start/peak/fall-mid/valley/trim boundaries, released payload,
trim return/time, next-cycle faults, four `malloc_info` summaries and XML paths,
and 25/50/75/100% release checkpoint times. Existing non-cyclic JSON is
unchanged.

## External Histogram Format

Use `--profile external:<file>`. The file is plain text:

```text
# size_bytes weight
16 120
64 90
4096 12
65536 1
```

Blank lines and `#` comments are ignored. `size_bytes` and `weight` must be
positive integers. The live-set defaults to 4096 objects per thread unless
overridden with `--live-set`.

## Self-Test

```sh
./selftest.sh
```

The self-test runs:

- A1 deterministic op counts and per-thread FNV-1a size-sequence hashes.
- A2 ASan+UBSan runs for all seven built-in profiles.
- A3 RSS lower-bound sanity check.
- A4 JSON parse check with `python3 -m json.tool`.
- A5 armv7l cross-build `file` check.
- A6 `burst-free-small` fastbin residual check from measure-phase `malloc_info`.
- A7a `mixed --idle-release 50` retained-free-byte and RSS-staleness check.
- A7b `mixed --idle-release 50 --idle-trim` OS reclaim check.
- A8 deterministic checks for `burst-free-small` and `unsorted-drain`.
- A9 old-field compatibility checks for the v1 four profiles.
- A10 all four release orders and the applicability-scan JSON/XML fields.
- A11 cyclic progressive-release timing and four-stage instrumentation.
