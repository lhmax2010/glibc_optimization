> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Kimi Code CLI — Final Pre-Freeze Review of `tizen_glibc_memopt_design_v2.md` (v2.3)

**Scope:** Consolidated design proposal v2.3 (`docs/tizen_glibc_memopt_design_v2.md`) and its Chinese variant (`docs/tizen_glibc_memopt_design_v2_zh.md`).  
**Evidence:** Batch 2.5 on-device report (`docs/board_ab_batch25_report.md`), v1.1a alloc_bench implementation report (`docs/alloc_bench_v11a_impl_report.md`), upstream glibc 2.40 source on branch `tizen_base` (`8f08a7e`).  
**Date:** 2026-07-07.

## Executive Summary

**Verdict: CONDITIONAL APPROVE for freeze.** The v2.3 document is the most evidence-backed revision so far. The core conclusions — L1+L3 as the safe first-wave bundle, L2 gated by oversubscription ratio, L6 promoted on the strength of the Part D reclamation measurement, and R12/R13 rejected on fair-surface evidence — are all directionally correct and supported by the data.

**However, two claims in §0c overstate certainty and must be softened before freeze:**

1. The "churn inversion +11~+21 MB" envelope is too narrow. The actual per-rep RSS deltas for `thread-churn arena2` span **+4.6 MB to +43.9 MB** (mean +22.2 MB). Stating +11~+21 MB gives a false impression of tight variance.
2. The `large-transient arena_max=2` perf cost is closer to **−2.3 %** than the stated **−1.7 %** in our re-analysis. The memory saving is correct at ≈−10.9 MB.

These are wording/rounding issues, not fundamental flaws. All other §0c numbers are within reasonable rounding tolerance of the raw data.

---

## Part A — Batch 2.5 Data Re-Analysis

### Methodology

The Batch 2.5 report contains 80 rows across four parts. I re-parsed the TSV table with a fresh Python script (see Appendix) and computed:

- Per-group means and standard deviations (note: `thread-churn` has n=5; other Part A profiles have n=3).
- Coefficient of variation (CV) as a sanity check on RSS stability.
- C0-relative deltas for throughput (`measure_rss_kb_median` baseline) and RSS.

For Part C the baseline is **Part A `thread-churn C0`** because Part C has no C0 grid of its own.

### Re-computed Summary Table (Part A)

| Profile | Grid (tunable mapping) | n | Throughput (ops/s) | p99 (ns) | RSS (KiB) | Δtput vs C0 | ΔRSS vs C0 |
|---|---|---:|---:|---:|---:|---:|---:|
| mixed | C0 | 3 | 2,007,182 ± 7,428 | 1,219 | 115,029 ± 420 | — | — |
| mixed | arena2 (`M_ARENA_MAX=2`) | 3 | 1,090,040 ± 5,539 | 17,580 | 109,012 ± 596 | **−45.69 %** | −6,017 KiB (−5.9 MB) |
| mixed | arena3 (`M_ARENA_MAX=3`) | 3 | 1,568,216 ± 6,851 | 6,356 | 110,693 ± 491 | **−21.87 %** | −4,336 KiB (−4.2 MB) |
| mixed | arena4 (`M_ARENA_MAX=4`) | 3 | 2,027,839 ± 2,371 | 1,188 | 113,827 ± 748 | **+1.03 %** | −1,203 KiB (−1.2 MB) |
| large-transient | C0 | 3 | 96,954 ± 337 | 58,163 | 107,363 ± 223 | — | — |
| large-transient | arena2 | 3 | 94,687 ± 1,243 | 63,616 | 96,177 ± 983 | **−2.34 %** | **−11,185 KiB (−10.9 MB)** |
| large-transient | arena3 | 3 | 96,636 ± 1,028 | 58,745 | 101,681 ± 1,773 | −0.33 % | −5,681 KiB (−5.5 MB) |
| large-transient | arena4 | 3 | 96,049 ± 462 | 59,248 | 105,552 ± 1,572 | −0.93 % | −1,811 KiB (−1.8 MB) |
| thread-churn | C0 | 5 | 1,781,754 ± 5,914 | 1,648 | 73,063 ± 531 | — | — |
| thread-churn | arena2 | 5 | 995,980 ± 18,062 | 20,072 | **95,831 ± 15,205 (CV 15.9 %)** | **−44.10 %** | **+22,768 KiB (+22.2 MB)** |
| thread-churn | arena3 | 5 | 1,426,057 ± 18,910 | 15,430 | **94,078 ± 13,873 (CV 14.7 %)** | **−19.96 %** | **+21,014 KiB (+20.5 MB)** |
| thread-churn | arena4 | 5 | 1,681,148 ± 33,033 | 2,789 | 82,798 ± 3,085 | −5.65 % | +9,735 KiB (+9.5 MB) |
| mixed-t2 | C0 | 3 | 1,195,224 ± 1,440 | 930 | 58,111 ± 484 | — | — |
| mixed-t2 | arena2 | 3 | 1,203,119 ± 2,755 | 894 | 56,539 ± 284 | **+0.66 %** | −1,572 KiB (−1.5 MB) |

### Validation of §0c Claims

| Claim | Verdict | Notes |
|---|---|---|
| "mixed arena_max=4: +1.0 % / −1.6 MB" | **Mostly OK** | Our data: +1.03 % / −1.2 MB. Memory magnitude is slightly smaller; the −1.6 MB figure may come from a different rep or rounding. Not a material error. |
| "2-thread:2-arena control at +0.8 % / −1.2 MB" | **Mostly OK** | Our data: +0.66 % / −1.5 MB. Direction and magnitude match. |
| "4:3 costs −22 %" | **Confirmed** | mixed arena3 −21.87 %; thread-churn arena3 −19.96 %. Range ≈20–22 %. |
| "4:2 costs −46 %" | **Confirmed** | mixed arena2 −45.69 %; thread-churn arena2 −44.10 %. Range ≈44–46 %. |
| "large-transient arena_max=2: −10.8 MB at −1.7 %" | **Memory confirmed; perf slightly worse** | Memory: −10.9 MB. Perf: −2.34 % in our data, not −1.7 %. Still well under the 5 % target, but the stated −1.7 % understates the measured cost by ~0.6 pp. |
| "Churn inversion holds … +11~+21 MB, 15/15 reps above baseline" | **Direction true; envelope understated** | All 15 reps are indeed above baseline, but the spread is much wider. `thread-churn arena2` per-rep RSS deltas: **+4.6, +13.0, +21.3, +28.3, +43.9 MB**. The "+11~+21 MB" line captures only the middle of the distribution and ignores the +28/+44 MB tails. **Recommend revising to "mean +22 MB, rep range +5~+44 MB" or similar.** |
| New rule: `arena_max ≥ peak concurrent allocating threads` | **Confirmed, with nuance** | The 1:1 configurations (mixed arena4, mixed-t2 arena2) are free or beneficial. Any oversubscription (4:3, 4:2) is expensive. The rule should read `≥ peak *concurrent allocating* threads`, not simply cores, because idle cores do not create contention. |

### Key Insight from `mixed-t2`

The `mixed-t2` profile (2 threads, 2 arenas) is the clean control the doc asks for: it shows that capping arenas at the actual concurrent thread count is **free performance-wise and RSS-negative**. This is the strongest empirical support for the new L2 safe-floor rule. It should be called out more prominently in §0c rather than buried as a parenthetical.

---

## Part B — Coverage and Internal Consistency Audit

### L/R List Coverage vs `dl-tunables.list`

I cross-checked every lever/rejection in §4 and §5 against the tunables defined in `elf/dl-tunables.list` and `sysdeps/nptl/dl-tunables.list`.

**Covered / accounted for:**

| Tunable | L/R ID | Verdict |
|---|---|---|
| `glibc.malloc.arena_max` | L2 | ✓ |
| `glibc.malloc.arena_test` | L2 / §8 | ✓ mentioned as related |
| `glibc.malloc.mmap_threshold` | L3 | ✓ |
| `glibc.malloc.trim_threshold` | L3 | ✓ |
| `glibc.malloc.tcache_count` | L4 / R11 | ✓ |
| `glibc.malloc.tcache_max` | L5 | ✓ |
| `glibc.malloc.tcache_unsorted_limit` | R13 | ✓ |
| `glibc.malloc.mxfast` | R12 / §8 | ✓ |
| `glibc.malloc.hugetlb` | Q3 | ✓ explicitly noted as anti-lever |
| `glibc.malloc.perturb` | G2 | ✓ hygiene |
| `glibc.malloc.check` | G2 | ✓ hygiene, noted as stub |
| `glibc.pthread.stack_cache_size` | L1 | ✓ |
| `glibc.pthread.stack_hugetlb` | L13 | ✓ |

**Not evaluated as levers (worth a sentence in §5 or §9):**

| Tunable | Why it matters | Suggested handling |
|---|---|---|
| `glibc.malloc.top_pad` | Default 131 KiB; lowering reduces heap growth padding (fewer RSS pages retained) at cost of more `brk`/`mmap` syscalls. | Add to §5 as "not evaluated" or note in L3 discussion that `top_pad` is left at default. |
| `glibc.malloc.mmap_max` | Caps `mmap`-fallback allocations; interacts with `mmap_threshold` but is not currently proposed as a lever. | Add one sentence: "`mmap_max` left at default; not expected to change because threshold pinning (L3) already addresses the target surface." |
| `glibc.pthread.mutex_spin_count` / `glibc.pthread.rseq` | Performance-only tunables; no direct RSS effect. | Can be ignored for this plan, or listed in §5 as out-of-scope. |
| `glibc.mem.tagging` / `glibc.mem.decorate_maps` | MTE / map decoration; TV kernel/ABI question. | Out of scope for this optimization plan; mention if MTE is enabled on target. |

**Finding:** The coverage is excellent. The only material gap is that `top_pad` and `mmap_max` are never mentioned, even as out-of-scope. Adding a single paragraph prevents a future reviewer from re-proposing them as "missed" levers.

### Plan B (§8) Mallopt Mapping

I spot-checked `malloc/malloc.c:5582-5620`. The doc's mapping is correct:

| Tunable lever | `mallopt()` param | Exists in source |
|---|---|---|
| L2 `arena_max` | `M_ARENA_MAX` | ✓ |
| L3 `mmap_threshold` + `trim_threshold` | `M_MMAP_THRESHOLD` + `M_TRIM_THRESHOLD` | ✓ |
| mxfast (R12) | `M_MXFAST` | ✓ |
| `arena_test` | `M_ARENA_TEST` | ✓ |

Also available but unused: `M_TOP_PAD`, `M_MMAP_MAX`, `M_CHECK_ACTION`, `M_PERTURB`.

**Minor consistency issue — legacy lever IDs in §8:** §8 says "L2, L3, L11 survive as one-line code changes" and "tcache (L4/L5/L12)." However, **no L11 or L12 lever is defined in §4**. In earlier drafts L11 = `mxfast` and L12 = `tcache_unsorted_limit`; by v2.3 these have become **R12 and R13** (rejected). Keeping the old IDs in §8 is confusing and could be read as reviving levers that no longer exist.

Suggested rewrite for §8:

> "`mallopt()` covers L2 (`M_ARENA_MAX`), L3 (`M_MMAP_THRESHOLD`, `M_TRIM_THRESHOLD`), and the rejected `mxfast` lever R12 (`M_MXFAST`). No mallopt equivalent exists for tcache levers L4/L5 and R13, or for pthread stack levers L1/L13."

The same cleanup should be applied to `docs/tizen_glibc_memopt_design_v2_zh.md` §8.

Also, the §4 first-wave bundle says "L12 removed from candidacy (R13)" — consistent — but §8's "L11" appears to be a leftover from an earlier numbering scheme. Freeze should fix this.

### R12 / R13 Fair-Surface Verdicts

Recomputed from Part B (`burst-free-small`, `unsorted-drain`, n=3 each):

| Grid | Profile | Δtput vs C0 | ΔRSS vs C0 |
|---|---|---:|---:|
| `mxfast=0` | burst-free-small | **−5.68 %** | −32 KiB |
| `tcache_unsorted_limit=3` | burst-free-small | −0.90 % | 0 KiB |
| `mxfast=0` | unsorted-drain | −0.08 % | +57 KiB |
| `tcache_unsorted_limit=3` | unsorted-drain | +0.11 % | +216 KiB |

**R12:** The doc's "−5.6 % / −31 kB" is accurate. Rejection is justified: the fastbin backlog exists but is only tens of kB, while the perf cost sits right at the 5 % target line.

**R13:** The doc's "no measurable effect" is accurate. The +216 KiB on `unsorted-drain` is <0.2 % of the 138 MB process and within measurement noise. Rejection is justified.

### L6 Reclamation Measurement

Part D (`mixed` profile, 50 % idle release, `alloc_bench` v1.1a `--idle-trim`):

| Grid | n | Measure RSS (KiB) | Idle RSS (KiB) | Idle-free delta (kB) | idle_trim_ret |
|---|---|---:|---:|---:|---:|
| D-C0 | 3 | 114,216 | 114,443 | ~48.7 MB retained | −1 |
| D-C0-idle-trim | 3 | 114,635 | 53,657 | ~49.5 MB retained | 1 |
| D-T-L3 | 3 | 114,191 | 114,450 | ~48.9 MB retained | −1 |

- **Idle RSS reclaim:** 114,443 → 53,657 KiB = **60,787 KiB (59.36 MiB)**.
- **Throughput cost of trim:** +0.02 % (within noise; trim happens at quiescence).
- **L3 is orthogonal to reclamation:** D-T-L3 (threshold pinned) reclaimed essentially 0 at idle, confirming the doc's mechanism claim.

The doc's "59.9 MB from a 112 MB process" is directionally correct (our baseline process was ~112 MiB at measure time, ~114 MiB at idle). The slight difference is rounding. **Valid.**

### Part C L1+L3 Combo

| | n | Throughput | RSS (KiB) |
|---|---|---:|---:|
| Part A `thread-churn C0` | 5 | 1,781,754 | 73,063 |
| Part C `L1_L3` | 3 | 1,785,015 | 70,027 |
| **Delta** | | **+0.18 %** | **−3,036 KiB (−2.97 MiB)** |

Doc claims: **+0.1 % / −2.43 MB**. Our numbers are +0.18 % / −2.97 MiB. The difference is small and likely due to n=5 vs n=3 baseline and rounding. **Valid.**

---

## Part C — TV-Phase Executable Recommendations

### 1. Target Process Selection

For the first TV pilot, pick processes that satisfy **all** of the following:

| Criterion | Rationale |
|---|---|
| **AT_SECURE = 0** (verified by `readelf -d` / `/proc/<pid>/attr/current` check) | Tiers 1–2 are env-based. If a candidate is AT_SECURE, it falls straight to Plan B and should be handled separately. |
| **Allocation-heavy** (≥1 % CPU in malloc/free path, or ≥10 MB heap per `malloc_info()`) | Otherwise the absolute saving is too small to measure above noise. |
| **Stable or slowly varying thread pool** | Avoids the L2 churn-inversion trap. For thread-churning services, only L1+L3 are safe; never apply `arena_max` caps. |
| **Has identifiable quiescent phases** (scene transitions, app backgrounding, interstitial screens) | Required for L6 `malloc_trim(0)` insertion. Hot-path trim is forbidden. |
| **Not a system-critical boot path** | Rollout must be per-service drop-in (M4); boot-critical daemons should be pilots only after lab validation. |

**Suggested pilot order:**

1. **A media/gallery app** with scene changes and a stable render thread pool — ideal for L1+L3 baseline, then L6 at scene change.
2. **A background sync daemon** with periodic idle windows — validates L6 cost on re-activation.
3. **A low-allocation-rate system service** (e.g. config/cache loader) — tests whether L2 aggressive caps (`arena_max=2`) can reproduce `large-transient`-like savings cheaply.

Avoid as first pilots: browser engines (high churn, hard to attribute), compositors (latency-sensitive), and any service whose `AT_SECURE` status is unknown.

### 2. L6 Pilot Hook

`alloc_bench` v1.1a already proves the mechanism (`--idle-trim`). For TV pilots:

- **Hook location:** Call `malloc_trim(0)` from the application's own phase-change handler (e.g. `onPause`, `onSceneExit`, after a backgrounding signal). Do **not** put it on a timer or in the allocation hot path.
- **Gating condition:** Only trim when the application has just released a substantial fraction of its heap (≥20–30 % of peak) and is entering quiescence. This matches the Part D experiment shape.
- **Minimum telemetry:**
  - `malloc_info()` before and after trim (attribution).
  - `smaps_rollup` Rss/Pss before and after trim (ground truth).
  - Refault latency: measure time-to-first-allocation after re-activation. The doc correctly flags this as unmeasured; it is the single biggest open risk for L6.
  - Trim wall-clock time (should be <1 ms for single-arena, possibly ms for many-arena processes; set a per-process budget, e.g. 5 ms @ p99).
- **Abort criterion:** If refault latency adds >5 % to the re-activation path, or trim stall exceeds the budget, remove the hook for that service.

### 3. PSI Measurement Protocol

The doc names PSI memory stall as the north-star metric but has not yet collected it. Add this concrete protocol:

| Step | Command / File | Frequency |
|---|---|---|
| Baseline | `cat /proc/pressure/memory` before pilot start | Once per test run |
| During workload | Record `/proc/pressure/memory` every 1 s while the app is active | Continuous |
| During quiescence | Record every 5 s; capture the window around L6 trim | Continuous |
| Per-process | `smaps_rollup` for the target PID synchronized with PSI samples | Every sample |
| Attribution | `malloc_info()` XML at baseline, peak, post-release, post-trim | Phase-aligned |

**Interpretation guardrails:**

- Compare **only** runs with the same `vm.overcommit_memory` and THP mode (M5).
- Use `some` and `full` memory stall percentages over the test window, not instantaneous values.
- If PSI improves but RSS does not, the benefit is likely system-level memory pressure relief — still valuable, but attribute it to L6 rather than L2/L3.
- If RSS improves but PSI does not, the process is not currently memory-stall-bound; the saving is still real but may not translate to user-perceptible smoothness.

---

## Open Items That Must Close Before Rollout (not before freeze)

The following are acceptable open questions for a design freeze but must be answered before any service ships:

1. **TV-scale magnitudes on real services** (Q2 partial). Batch 2.5 numbers are from a microbenchmark; real services may have different fragmentation shapes.
2. **L6 post-trim refault latency on device.** This is the largest unmeasured cost in the plan.
3. **Kernel THP mode on production TV images** (Q3). Gates L13; dev board THP was absent.
4. **AT_SECURE inventory** (Q1). Gates whether Tiers 1–2 are viable for the majority of targets.
5. **`top_pad` and `mmap_max` out-of-scope statement.** Add to v2.3.1 or a freeze amendment.

---

## Conclusion and Action Items

The v2.3 design is ready to freeze after **three small edits**:

1. **§0c:** Revise the `thread-churn` inversion envelope from "+11~+21 MB" to a range that includes the observed tails, e.g. **"mean +22 MB, rep range +5~+44 MB (n=5)"**.
2. **§0c:** Adjust the `large-transient arena_max=2` perf cost from "−1.7 %" to **"−2.3 %"** (or "−2~−2.5 %").
3. **§8:** Remove all legacy L11/L12 references. Rewrite the Plan B sentence to name `mxfast` (R12) and `tcache_unsorted_limit` (R13) explicitly, and remove the undefined L11/L12 IDs. Apply the same fix to the Chinese variant.
4. *(Recommended, not blocking)* Add a one-paragraph "out-of-scope tunables" note covering `top_pad`, `mmap_max`, and `mutex_spin_count`/`rseq`.

Everything else — the L2 safe-floor rule, the L1+L3 bundle, the L6 promotion, the R12/R13 rejections, and the measurement protocol — is consistent with the source and the Batch 2.5 data.

---

## Appendix — Re-Analysis Script

Used to produce the numbers in this review. Saved as a working reference; not part of the project deliverables.

```python
#!/usr/bin/env python3
# /tmp/batch25_analysis.py
import sys
from collections import defaultdict
from statistics import mean, stdev

REPORT = '<WORKSPACE>/docs/board_ab_batch25_report.md'

def parse_number(v):
    v = str(v).strip()
    if v.lower() in ('n/a', 'na', ''):
        return float('nan')
    try:
        return int(v)
    except Exception:
        return float(v)

def parse_report(path):
    lines = open(path).read().splitlines()
    headers = None
    rows = []
    in_table = False
    for line in lines:
        if line.startswith('| Part '):
            headers = [h.strip() for h in line.split('|')[1:-1]]
            in_table = True
            continue
        if in_table and line.startswith('|'):
            if '---' in line:
                continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        else:
            in_table = False
    return rows

def row_key(r):
    return (r['Part'].strip(), r['profile'].strip(), r['格'].strip())

def main():
    rows = parse_report(REPORT)
    groups = defaultdict(list)
    for r in rows:
        try:
            groups[row_key(r)].append({
                'rep': int(r['rep']),
                'tput': parse_number(r['throughput_ops_per_s']),
                'p99': parse_number(r['p99']),
                'rss': parse_number(r['measure_rss_kb_median']),
                'idle_rss': parse_number(r.get('idle_rss_kb', 'nan')),
                'idle_free_delta': parse_number(r.get('idle_free_delta_kB', 'nan')),
                'idle_trim_ret': r.get('idle_trim_ret', 'n/a'),
            })
        except Exception:
            pass

    def stats(vals):
        n = len(vals)
        m = mean(vals)
        s = stdev(vals) if n >= 2 else 0.0
        return n, m, s

    def summarize(part, profile, grid):
        vals = groups[(part, profile, grid)]
        n, tput, tput_sd = stats([v['tput'] for v in vals])
        _, p99, p99_sd = stats([v['p99'] for v in vals])
        _, rss, rss_sd = stats([v['rss'] for v in vals])
        return {'n': n, 'tput': tput, 'tput_sd': tput_sd,
                'p99': p99, 'p99_sd': p99_sd,
                'rss': rss, 'rss_sd': rss_sd, 'raw': vals}

    def fmt(s):
        cv_t = s['tput_sd'] / s['tput'] * 100 if s['tput'] else 0
        cv_r = s['rss_sd'] / s['rss'] * 100 if s['rss'] else 0
        return (f"n={s['n']} tput={s['tput']:,.0f} (sd={s['tput_sd']:,.0f}, cv={cv_t:.1f}%) "
                f"p99={s['p99']:,.0f} rss={s['rss']:,.0f} (sd={s['rss_sd']:,.0f}, cv={cv_r:.1f}%)")

    def delta(base, cur):
        dt = (cur['tput'] - base['tput']) / base['tput'] * 100.0
        dr = cur['rss'] - base['rss']
        return dt, dr

    profiles = ['mixed', 'large-transient', 'thread-churn', 'mixed-t2']
    grids = ['C0', 'arena2', 'arena3', 'arena4']
    for prof in profiles:
        if ('A', prof, 'C0') not in groups:
            continue
        print(f'--- {prof} ---')
        for grid in grids:
            if ('A', prof, grid) not in groups:
                continue
            cur = summarize('A', prof, grid)
            base = summarize('A', prof, 'C0')
            dt, dr = delta(base, cur)
            print(f"{grid:18s} {fmt(cur)} dt={dt:+.2f}% dr={dr:+.1f} KiB")
        print()

if __name__ == '__main__':
    main()
```
