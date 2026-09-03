> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Tizen glibc Memory Optimization — TV-Phase Protocol v1

- Status: DRAFT — to be frozen alongside design doc v2.4 after review
- Upstream: design doc v2.4 (freeze candidate), TV-board recon `docs/tv_board_recon_report.md`, three-reviewer Part C convergence
- Target: real TV image, <PRODUCT_IMAGE> TV, armv7l, kernel 5.4.261, **GCC -Os build**, glibc 2.40
- Framing: the board (rpi4) phase answered "what might work"; this protocol answers "how to prove it and ship it safely on real hardware"

## 0. Environment baseline (recon-fixed, protocol-wide covariates)

| Dimension | TV board | rpi4 (board phase) | Protocol impact |
|---|---|---|---|
| glibc | 2.40 (same version) | 2.40 | Source-conclusion portability mostly holds; TV-branch patch delta pending §1 re-derivation |
| Build | **-Os** | -O2 | Absolute perf not cross-image comparable; same-image A/B deltas valid; recorded as M5 covariate |
| PSI | **present** | present | North-star measurable at last (§5) |
| smaps_rollup / auxv | present | present | Measurement and inventory collectable |
| THP | **absent** | absent | L13 formally retired for this target (R-candidate) |
| Kernel | 5.4.261 | 6.12 | MGLRU (needs 6.1+) unavailable this TV gen; adjacent track keeps only zram/KSM/overcommit |
| cgroup | v1 | — | PSI via `/proc/pressure/memory`, not cgroup-v2 memory.pressure |
| Exec policy | **UEP signature enforcement** | none | See §0.1 |
| Cores | recon-recorded value | 4 | L2 gate `arena_max=cores` takes the real TV core count |

### 0.1 UEP bypass (validated, see recon report UEP section)

- Scripts: **stdin pipe injection** `sdb shell sh -s` (the executed binary is the board's signed sh; append `exit` to the payload to guarantee EOF exit).
- Pressure injection: **tmpfs balloon** `dd → /dev/shm/balloon`, incremental append for rate control, `rm` to release (binary-free, validated: clean 64 MB drop and recovery).
- alloc_bench does NOT go on TV: the microbenchmark is a board-side pre-screen; the TV gate is the real service. If calibration is wanted, go via develkey signing / develmode — not a protocol blocker.

## 1. Precondition gates (before protocol start)

- **PG1. TV-branch T1 re-derivation.** The TV image glibc is also 2.40 but comes from an -Os product branch that may carry a different patch set than the audited baseline `tizen_base@8f08a7e` (-O2). Re-run a T1-level diff on the TV-branch glibc source (malloc/nptl/tunables paths + dlconf) to confirm no mechanism drift. **This is the trust precondition for the whole protocol.**
- **PG2. Tunables efficacy on device.** alloc_bench is unavailable on TV; use a signed process instead — pick a non-secure target, inject `GLIBC_TUNABLES=glibc.malloc.arena_max=1` via systemd drop-in + restart, compare `malloc_info()` arena count, proving tunables actually take effect on the TV image (TV-side confirmation of the board-phase T2 result).
- **PG3. AT_SECURE target confirmation.** For each high-value target from the §2 funnel, confirm AT_SECURE (the inventory already gives the full distribution: 99 non-secure / 122); secure targets go to Plan B (v2.4 §8), non-secure go to env.

## 2. Target-process funnel (122 → 5–10)

Single collection, extended inventory script via `sdb shell sh -s`, over all processes:

- Base (existing script): AT_SECURE / elf_class / threads / Rss / Pss / env blacklist
- New: `smaps_rollup` **Private_Dirty** (true private dirty pages, L6 upper bound)
- New: **arena count approximation** = count of `rw-p` anon / `[heap]` segments in `/proc/pid/maps` (L2/L6 relevance)
- New: `/proc/pid/task` count and **two-sample turnover rate** (L2 churn classifier, required by the v2.4 gate)
- New: instance count (TV launchpad forks share pages; weight by copies)

**Rank**: `Private_Dirty(Pss) × instance_count` (launchpad multi-copy processes weighted).
**Stratify** top-N:
- high threads + stable task count (turnover ≈0) → L1/L2 candidate
- high arena count + high heap Rss → L6 candidate
- churn type (sustained turnover > 0) → L2 forbidden, L1/L3/L6 only
- secure → Plan B channel

Expected high-value target classes: web-runtime, media pipeline, launcher/EFL residents, resource manager (ServiceR).

## 3. First experiment batch (TV Batch 1)

Lead with the v2.4 first-wave bundle **L1+L3** (combo-verified), per target:

| Cell | GLIBC_TUNABLES (env, systemd drop-in) |
|---|---|
| C0 | baseline |
| L1+L3 | `glibc.pthread.stack_cache_size=1048576:glibc.malloc.mmap_threshold=131072:glibc.malloc.trim_threshold=131072` |
| +L2 | add `glibc.malloc.arena_max=<cores>` (only for non-churn targets passing the §2 gate) |

- Injection: `/etc/systemd/system/<unit>.d/memopt.conf` (written via stdin injection; if the persistent partition is read-only, use systemd runtime drop-in `/run/systemd/...` — recon did not cover partition writability, so TV Batch 1 step 0 probes it).
- Measurement: M1 (smaps_rollup Rss+Pss, ≥3 runs median) + M2 (malloc_info before/after) + **M5 covariates** (record -Os, overcommit, cores, no THP).
- Perf gate: no alloc_bench on TV — use **real-scenario scripts** (app switch, channel change, UI scroll) with in-scenario latency observation; ≤5% target / ≤10% ceiling remains the shipping gate (M3).

## 4. L6 pilot (priority, v2.4 headline lever)

- **Landing point (three-reviewer consensus)**: prefer a UI app's `pause`/`app_pause` lifecycle callback (backgrounding = release-then-quiesce, exact match to board-phase Part D); secondary is ServiceR memory-pressure/LMK-event-driven trim (binds L6 directly to the PSI north-star).
- **Mandatory cost measurements (v2.4 required)**:
  1. **Foreground-resume refault latency** — first-frame/first-response time after re-foregrounding a trimmed backgrounded app;
  2. **Trim-time all-arena lock stall** — if the target still has active allocating threads during trim, measure the stall (board-phase Part D was threads-idle; this is the TV first measurement).
- Landing form: product code change, normal build+signing chain (UEP-independent).
- Three-cell measurement (M6, board-phase Part D shape): {background-no-trim / background+trim / L3-pinned-threshold control}, isolating retention, active reclaim, threshold mechanics.

## 5. PSI north-star measurement (idle until now; must land this phase)

- Collect: 1 Hz `/proc/pressure/memory` (some/full avg10/avg60) + `/proc/vmstat` `workingset_refault`/`pgmajfault`, aligned to the smaps_rollup timeline.
- Inject: tmpfs balloon (§0.1, validated), incremental append to hold system `MemAvailable` at a target level (calibrate PSI some avg10 into the 5–10 band).
- A/B: same injection curve + same representative TV scenario (app switch / channel change), target service with vs without the lever bundle; compare **PSI some/full avg10 area-under-curve (AUC)** + refault counts.
- Precondition: recon confirmed PSI present; protocol step 0 re-checks that `/proc/pressure/memory` values actually respond under pressure (already seen responding during balloon validation).

## 6. Rollout unit and rollback

- env levers: per-service systemd drop-in, never image-global; rollback = delete drop-in + restart.
- L6: product code, released/rolled back with the version.
- Each target's A/B adjudicated independently, not bundle-shipped.
- Post-experiment restore discipline follows the board phases (delete config, re-scan inventory to confirm zero LIVE hits).

## 7. Phase completion criteria

- PG1–PG3 pass; §2 funnel yields the confirmed top target set;
- TV Batch 1 (L1+L3±L2) has Rss/PSS + scenario perf + PSI AUC per target;
- L6 has at least one pilot with reclaim + refault + lock-stall (all three);
- each lever×target passes the M3 dual gate to be marked "shippable", else stays experimental.
- Produce the TV-phase adjudication → decide production rollout scope.

## 8. Known-open (honest list)

- TV partition writability (drop-in to /etc vs /run) — TV Batch 1 step 0.
- -Os L2 intermediate-cap cost curve offset vs rpi4 (-O2) — TV-measured, not extrapolated.
- L6 refault and lock-stall device magnitudes — first measured this phase.
- TV-branch glibc patch delta (PG1 output).
