> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc Memory Optimization v2.3 Pre-freeze Review (GPT-5 Codex)

## Reviewer Header

- Reviewer: GPT-5 Codex
- Date: 2026-07-09
- Audited commit: `8f08a7e30396822a8d969d357822a6ffd56b43fb`
- Scope: `docs/tizen_glibc_memopt_design_v2.md` v2.3, `docs/board_ab_batch25_report.md`, Batch 1/2 evidence, inventory, `bench/alloc_bench/` v1.1a, and current glibc source.
- Recompute method: parsed `board_results/batch25/run_summary.tsv`; compared medians by profile/grid against the matching C0; RSS metric is `measure_rss_kb_median`; Part D reclaim is `measure_rss_kb_median - idle_rss_kb`; thread-churn direction was checked both against C0 max and same-rep paired deltas. XML spot-check parsed final aggregate `<total type="fast|rest">` from Batch 2.5 `malloc_info_*_measure.xml`.
- External anchors used for TV protocol: Linux PSI docs (`/proc/pressure/*` semantics), Linux cgroup v2 memory controller docs, Linux procfs `smaps_rollup` docs.

## Part A: Batch 2.5 Data -> Conclusion Verdicts

| §0c item | Verdict | Recomputed numbers | Challenge |
|---|---|---|---|
| L2 oversubscription knee | NEEDS-MORE-DATA | `mixed` 4t C0 median 2,008,889 ops/s / 115,076 kB. `arena4`: +1.01%, -1,628 kB. `arena3`: -21.96%, -4,140 kB. `arena2`: -45.88%, -5,888 kB. `mixed-t2 arena2`: +0.84%, -1,252 kB. `large-transient arena2`: -1.75%, -11,004 kB. | The 4-core board supports "contention tracks thread:arena ratio" inside this grid. It does not yet define "peak concurrent allocating threads" for TV services. On an 8-core TV, `arena_max >= cores` is an untested proxy unless the service's allocating TID concurrency is measured. Treat the rule as a measurement gate, not a portable constant. Evidence: `docs/board_ab_batch25_report.md:114-143`, runner matrix at `board_results/batch25/run_batch25_alloc_bench.sh:366-397`. |
| L2 churn ban and magnitude | SUPPORTED for ban; OVERREACHING for quoted range | C0 RSS median 72,708 kB, max 73,656 kB. Treatment RSS medians: `arena4` 83,968 kB (+11.00 MiB), `arena3` 90,992 kB (+17.86 MiB), `arena2` 94,528 kB (+21.31 MiB). All 15 treatment reps exceed C0 max. Same-rep paired deltas range: `arena2` +4.64..+43.88 MiB, `arena3` +10.14..+43.66 MiB, `arena4` +5.80..+12.46 MiB. | "Thread-churn services forbidden at any cap" is well supported. The `+11~+21 MB` phrase is only the per-cap median-vs-C0-median range, not the observed per-rep range. If v2.3 uses it as expected TV magnitude, it is too tight. Evidence: `docs/board_ab_batch25_report.md:94-113`. |
| R12 / `mxfast=0` rejection | OVERREACHING | `burst-free-small`: C0 median 10,534,439 ops/s / 1,464 kB; `mxfast0` median 9,944,216 ops/s / 1,432 kB -> -5.60%, -32 kB. p50 worsens 112 ns -> 164 ns. Batch XML C0 fast aggregate was 65,816 / 94,056 / 168,232 bytes, not consistently "~50 kB"; `mxfast0` fast=0 but rest bytes remain. | Rejecting `mxfast=0` for the first wave is justified. The stronger claim that the fair-surface obligation is fully discharged is too broad: the profile caps backlog with `burst_size=2048`, 50% release, 4 threads, and no burst-size sweep. A real tiny-object service with long idle fastbin accumulation or cross-thread frees is still a possible counterexample, though the measured cost-return ratio is bad. Evidence: `docs/board_ab_batch25_report.md:144-149`, profile design at `docs/alloc_bench_spec_v1_1_delta_zh.md:6-14`, implementation at `bench/alloc_bench/alloc_bench.c:561-604`. |
| R13 / `tcache_unsorted_limit=3` rejection | SUPPORTED | `unsorted-drain`: C0 median 2,425,488 ops/s / 138,484 kB; `tcache_unsorted3` median 2,432,475 ops/s / 138,768 kB -> +0.29%, +284 kB. p50/p99 essentially unchanged: 486/10,651 ns -> 487/10,589 ns. | This is a fairer negative than R12: the profile creates large rest/unsorted pressure and hits the intended path. A size/batch sweep would be cheap, but current data support keeping it rejected for TV freeze. Evidence: `docs/board_ab_batch25_report.md:153-161`, profile design at `docs/alloc_bench_spec_v1_1_delta_zh.md:15-19`, implementation at `bench/alloc_bench/alloc_bench.c:620-656`. |
| L6 `malloc_trim(0)` promotion | SUPPORTED as pilot; not as magnitude promise | Part D medians: release-only reclaim -40 kB; release+trim reclaim 61,336 kB = 59.9 MiB; L3 threshold-control reclaim -40 kB. `idle_free_delta_kB` median under trim was 49,680.9 kB, so trim reclaimed more than the newly released live-pool bytes. `idle_trim_ret=1` in 3/3 trim runs. | The mechanism and number are real, and L6 deserves a TV pilot. What can still flip the pilot: trim duration was not recorded; the benchmark calls trim after workers quiesce, so all-arena lock contention is excluded; only one size mix and 50% release ratio were tested; reactivation refault cost is still unmeasured. Source confirms all-arena lock walk: `malloc/malloc.c:5209-5228`; interior `MADV_DONTNEED`: `malloc/malloc.c:5151-5195`. Evidence: `docs/board_ab_batch25_report.md:165-173`. |
| First-wave bundle L1+L3 | SUPPORTED | `thread-churn` C0 median 1,783,898 ops/s / 72,708 kB. L1+L3 median 1,785,092 ops/s / 70,224 kB -> +0.07%, -2,484 kB (-2.43 MiB), n=3. | Conservative and interaction-safe on the one tested churn profile. Do not read this as a universal TV saving; it is a safe starter bundle, not the main RSS win. Evidence: `docs/board_ab_batch25_report.md:162-164`, runner at `board_results/batch25/run_batch25_alloc_bench.sh:414-416`. |
| M6 three-cell reclamation shape | SUPPORTED | The three cells separate retention (`D-C0`), active reclaim (`D-C0-idle-trim`), and threshold mechanics (`D-T-L3`), and the controls cleanly isolate L6 from L3. | Keep M6, but extend TV protocol with two fields: trim wall time and next-activation refault/latency. Without those, the largest RSS win can still fail UX/perf budget. Evidence: `docs/alloc_bench_spec_v1_1a_zh.md:15-31`, `bench/alloc_bench/README.md:81-87`. |

## Part B: Finalization Completeness

### L/R Coverage Closure

| Area | Result | Finding |
|---|---|---|
| `glibc.malloc.*` tunables | Mostly closed | `check`/`perturb` are in G2; `mmap_threshold`/`trim_threshold` in L3; `arena_max` in L2; `tcache_max`/`tcache_count` in L5/L4/R11; `tcache_unsorted_limit` in R13; `mxfast` in R12; legacy mallopt-covered knobs are referenced by R1-R7. Source list: `elf/dl-tunables.list:26-85`. |
| `glibc.malloc.hugetlb` | Gap | It is mentioned only inside Q3 as an anti-lever, not assigned L/R. Before freeze, make it explicit as `R14` or a named negative fact. Source: `elf/dl-tunables.list:81-84`, setter at `malloc/malloc.c:5541-5558`. |
| `glibc.pthread.*` tunables | Needs explicit exclusions | `stack_cache_size` is L1 and `stack_hugetlb` is L13. `mutex_spin_count` and `rseq` are not RSS/PSS levers but should be explicitly excluded for closure. Source: `sysdeps/nptl/dl-tunables.list:18-42`. |
| Other tunable namespaces | Acceptable if excluded | `rtld.dynamic_sort`, `elision.*`, `gmon.*`, `mem.tagging`, `mem.decorate_maps` are not direct RSS/PSS optimization levers for this plan. A one-line exclusion list prevents future reopen. Source: `elf/dl-tunables.list:87-173`. |

### Reference And Consistency Checks

- Missing evidence files: v2.3 references `docs/ab_batch1_adjudication_zh.md`, `docs/ab_batch2_adjudication_zh.md`, and implies Batch 2.5 adjudication; none exist in this checkout. Present arbitration file is `docs/v22_review_arbitration_zh.md`.
- Missing provenance file: v2.3 lists `docs/review_glibc_memopt_Gemini-Code-Assist.md`, but the checkout has only Codex, Claude, and Kimi base reviews plus v2.2 reviews.
- Stale heading: `### Recommended first-wave bundle (v2.2)` should be v2.3 (`docs/tizen_glibc_memopt_design_v2.md:99`).
- Minor count wording: status says "two rounds of on-device evidence" while listing Batch 1, Batch 2, and Batch 2.5 (`docs/tizen_glibc_memopt_design_v2.md:3`).
- R numbering order is odd but not blocking: R10 appears after R13 (`docs/tizen_glibc_memopt_design_v2.md:107-112`).

### Plan B Check

Plan B is stale and should be fixed before freeze. It says mallopt keeps "L2, L3, L11" alive (`docs/tizen_glibc_memopt_design_v2.md:137`), but L11 is now R12, and the surviving priority code-change lever is L6 (`malloc_trim(0)`), which is not a mallopt knob. Correct coverage:

- `mallopt()` covers L2 via `M_ARENA_MAX` and L3 via `M_MMAP_THRESHOLD`/`M_TRIM_THRESHOLD`; it also covers rejected or legacy knobs `M_MXFAST`, `M_TOP_PAD`, `M_MMAP_MAX`, `M_ARENA_TEST`, `M_CHECK_ACTION`, `M_PERTURB` (`malloc/malloc.c:5582-5621`).
- No mallopt equivalent exists for L1, L4, L5, L13, or R13/tcache knobs.
- L6 is viable under `AT_SECURE` only as an in-process code hook, not via environment or mallopt.

## Part C: TV-stage Protocol Inputs

| Item | Feasibility | Protocol | Evidence / anchor | Expected magnitude and budget cost | Verification cost |
|---|---|---|---|---|---|
| One-shot target selection for 5-10 services | FEASIBLE | First pass over all PIDs: collect `cmdline`, unit/cgroup, `AT_SECURE`, `Threads`, `VmHWM`, `smaps_rollup` RSS/PSS/Private_Dirty/Anonymous/Swap, stack mappings, heap/anon rw mappings, and `maps` deleted DSOs. Rank by `Pss_Anon + Private_Dirty + heap/anon RSS + thread_count + lifecycle-hook quality`. Second pass only for top ~20: get `malloc_info`-class data through an in-process diagnostic endpoint, lab-only attach, or restart-with-instrumentation. For L2, define peak allocating concurrency as distinct TIDs with malloc/free events in 100 ms buckets over a 60 s eBPF/uProbe sample; fall back to LD_PRELOAD only for non-secure lab targets. | Current inventory already proves auxv/env/process enumeration works and found 52 non-empty processes, 0 unknown AT_SECURE, and 0 live env hits (`docs/board_inventory_run_report.md:120-190`). Kernel docs describe `smaps_rollup` as pre-summed PSS/RSS data: https://www.kernel.org/doc/Documentation/filesystems/proc.rst and https://www.kernel.org/doc/Documentation/ABI/testing/procfs-smaps_rollup. | No shipped perf cost. Expected output is not a memory saving itself; it should eliminate low-value services and identify candidates with >8-16 MiB heap/free opportunity or high thread churn. | 1-2 days for script and scoring; one TV image pass <30 min; second-pass instrumentation 0.5-1 day per unusual service class. |
| L6 first pilot landing | FEASIBLE-WITH-CAVEATS | Start with a process that owns the freed heap and has a natural release->idle phase. Best candidates: web/app runtime or launchpad worker after app/page teardown and before returning to pool; media scanner/thumbnailer after batch decode/scan completion; app lifecycle host only if the large heap is inside that process. Avoid audio/input/hot-daemon timers. Hook shape: after known release, call `malloc_trim(0)` once, debounce 30-60 s, only if `malloc_info` free bytes exceed 8 MiB or 25% of arena system bytes; record trim wall time and next activation latency/faults. | Batch 2.5 Part D gives 59.9 MiB reclaim only when trim is called (`docs/board_ab_batch25_report.md:165-173`). glibc source shows all-arena locks plus `MADV_DONTNEED` (`malloc/malloc.c:5151-5228`). Batch 1 shows `ServiceV/ac.service` is targetable but AT_SECURE and env-inert (`docs/board_ab_batch1_report.md:80-110`), so code hook matters. | Potential tens of MiB if TV service has release-heavy phases; zero if heap free bytes are low. Budget risk is not steady-state throughput but trim pause plus refault on reactivation; current data do not quantify it. | 2-4 days for first service hook and logging; 3-5 scenario repeats per service: close/background/reactivate, under idle and pressure. |
| PSI pressure protocol | FEASIBLE | Use system-wide `/proc/pressure/memory` plus per-service RSS/PSS. Phases per run: baseline action, pressure-only action, pressure+lever action. Pressure injector: a controlled anonymous-memory toucher in its own cgroup, with safety `memory.max` and high `oom_score_adj`; step allocation until MemAvailable or PSI `some avg10` reaches the target band, then hold. Sample `/proc/pressure/memory` every 1 s and compute `total` deltas for `some` and `full`; collect `/proc/vmstat` pgfault/majfault/pgscan/pgsteal, zram/swap counters, dmesg OOM, and target `smaps_rollup`. | PSI docs define `some`, `full`, avg10/60/300, and `total` stall time: https://docs.kernel.org/accounting/psi.html. cgroup v2 docs define `memory.high`, `memory.max`, `memory.reclaim`, `memory.events`, and note proactive reclaim caveats: https://docs.kernel.org/admin-guide/cgroup-v2.html. v2.3 north-star requires PSI but Batch 1/2/2.5 do not record it. | No shipped cost. A lever passes only if RSS/PSS reduction does not increase PSI `full total`, OOM events, or user action p95/p99 beyond the 5% target / 10% ceiling. | 1 day for injector/collector; 1 day per TV image profile; more if cgroup v2 is absent or Tizen service placement is nonstandard. |

## Top-3 Challenges

1. L2 can still be misapplied. The data support a ratio knee on a 4-thread/4-core board; v2.3 still needs a TV definition and measurement method for "peak concurrent allocating threads." Without that, `arena_max=cores` is a slogan, not a gate.

2. L6 is now the biggest RSS opportunity and the biggest unmeasured UX risk. Batch 2.5 intentionally trims after worker quiescence; it does not measure all-arena lock pause under concurrent malloc traffic, trim wall time, or next-activation refault. TV should not freeze an L6 rollout protocol without those fields.

3. The document is better than its provenance hygiene. Missing adjudication files, a stale Plan B, and an unnumbered `glibc.malloc.hugetlb` exclusion are small individually, but together they are exactly the sort of loose ends that cause TV-stage rework.

## negative_facts

- Batch 2.5 had 80 expected result JSON files, zero nonzero exits, and zero bad JSON rows (`docs/board_ab_batch25_report.md:5-10`, `:183-193`).
- Batch 2.5 set all four CPU governors from `schedutil` to `performance`; no thermal waits were recorded, and initial thermal was 32615 mC (`docs/board_ab_batch25_report.md:55-88`, `:183-187`).
- `arena_max` churn RSS inversion is directionally robust in Batch 2.5: every arena-capped churn run exceeds the highest C0 RSS sample.
- `mxfast=0` eliminates fastbin totals in the tested surface, but the process RSS median only drops 32 kB and median throughput regresses 5.6%.
- `tcache_unsorted_limit=3` has no measurable memory win on `unsorted-drain` in Batch 2.5.
- L3 threshold pinning alone does not reclaim the released live pool in Part D; the L6 active trim call is the differentiator.
- `malloc_trim(0)` is not an env/mallopt lever; it requires an in-process call.
- `mallopt()` has no cases for tcache count/max/unsorted limit or pthread stack cache/hugetlb.
- Dev-board inventory reports THP as `NA`; L13 and `glibc.malloc.hugetlb` remain TV-kernel gated (`docs/board_inventory_run_report.md:180-189`).

## cannot-verify

- Contents of the referenced Batch 1/2/2.5 adjudication files, because those files are absent from this checkout.
- Exact TV SoC behavior for `arena_max >= cores`, especially on 8-core or heterogeneous-core products.
- Real TV services' peak concurrent allocating TID count; Batch 2.5 did not measure it.
- Real TV service fastbin and unsorted-bin backlog distributions beyond the two synthetic Batch 2.5 surfaces.
- L6 trim wall time, all-arena lock wait under live service concurrency, post-trim refault latency, and PSI impact.
- TV kernel covariates: cgroup v2 availability/layout, PSI support, zram/zswap parameters, MGLRU, KSM, and THP mode.
- aarch64 results; Batch 2.5 numbers are armv7l/rpi4 only.
