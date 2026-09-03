> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Pre-Freeze Review — `docs/tizen_glibc_protocol_v2_zh.md` (Dual-Track Execution Protocol v2)

## 1. Reviewer header

- **Reviewer**: Claude Opus 4.8 (`claude-opus-4-8[1m]`)
- **Date**: 2026-08-06
- **Materials**: protocol v2, design v2.4, `tv_recon2_report.md` (RPI4 `.25`), `tv_recon3_report.md` (TV `.26`), v1 four-reviewer set, board chain, `bench/alloc_bench/`, glibc tree @ `8f08a7e303`.
- **Standard**: what causes execution rework / crash / un-adjudicable data. Not completeness.
- **Verification method**: traced the three v2 fixes to source — `decorate_maps` gating (`sysdeps/unix/sysv/linux/setvmaname.c`), the arena label string (`malloc/arena.c:448`), the tunable definition (`elf/dl-tunables.list:146`); read the funnel heuristic (`board_results/.../parse_smaps.pl`) line by line; read the recon balloon generator (`board_results/tv_recon3_20260806/product_board/collect_b5_psi.sh`); cross-checked every protocol claim against the recon raw evidence rather than its prose.

**One environment change since v1**: the TV board is now kernel **6.12.60** (recon3), not the 5.4.261 of v1's recon. The v1 "decorate_maps needs ≥5.17" blocker is therefore gone — but see Part A.3 for what replaced it.

---

## 2. Part A — did v2 fix v1's three hard failures?

| v1 failure | v2 fix | Verdict | Basis |
|---|---|---|---|
| **Funnel metric wrong** (ranked by RSS/%) | rank by absolute glibc heap+arena Private_Dirty; recon3 shows 28–45 % on Top-5 | **PARTIALLY-FIXED** | Metric *concept* is correct and refutes v1's over-pessimism (below). But the 28–45 % numbers come from the `parse_smaps.pl` **heuristic**, an *upper bound* on glibc-reclaimable memory, and the funnel ranks on it before the exact method (A-2) validates it. See A.1. |
| **PSI self-cancelling** (closed-loop) | open-loop fixed 30 % injection | **PARTIALLY-FIXED** | Self-cancellation is genuinely removed. But the injection is `dd if=/dev/zero` into tmpfs under `swappiness=100` + active zram — a maximally compressible, maximally swappable balloon that **evaporates**. The cited `some avg2=6.95` is a swap-to-zram ramp transient, not sustained pressure. See A.2. |
| **`malloc_info()` unreachable** | `decorate_maps=1` + 6.12 kernel labels arenas exactly | **PARTIALLY-FIXED** | Source-confirmed (tunable + gate + label string all match). But a one-shot `prctl_supported` latch + unverified kernel *config* + the launchpad-injection dependency make on-target efficacy unproven. See A.3. |

### A.1 — Funnel metric
**FIXED (concept), PARTIALLY-FIXED (measurement).** The switch to *absolute glibc heap+arena Private_Dirty* is the right correction of my v1 objection, and recon3 earns it: glibc heap is a material 28–45 % of Top-5 private dirty (`tv_recon3` §6 C1/C2), so v1's "managed heaps, nothing reachable" was too pessimistic. **But** `parse_smaps.pl` classifies an "arena" as `rw-p` + anonymous + **1 MiB-aligned start** + length ≤ 1 MiB. This signature:
- *Correctly excludes* the big managed heaps — CoreCLR GC segments/regions are multi-MB (dropped by `≤1 MiB`), JIT code is `r-xp`/`rwxp` (dropped by the `rw-p` filter). So it does **not** wholesale miscount the .NET GC heap as arena. (negative_fact.)
- *Cannot distinguish* a glibc arena from **any other 1-MiB-aligned ≤1 MiB rw-p anon** mapping — small thread stacks (these apps run 40–55 threads), or small 1-MiB-aligned CoreCLR/bmalloc bookkeeping allocations. Those inflate the count.
- *Miscounts arenas as heaps*: one grown arena chains multiple 1 MiB `HEAP_MAX_SIZE` regions (`malloc/arena.c:30`), each counted separately — so "arena≈17" is a **heap** count, not an arena count.

Net: 28–45 % is an **upper bound** on the glibc-reclaimable surface. The exact method exists (A-2 / decorate_maps) and *can even separate* arenas (`" glibc: malloc arena"`, `arena.c:448`) from large mmap chunks (`" glibc: malloc"`, `malloc/malloc.c:2432,2519`) — but it has not yet been run on the funnel, and if it shows the heuristic overcounts by, say, 1.5–2×, the target ranking re-orders. **The funnel that selects the whole TV campaign's targets rests on an unvalidated proxy.**

### A.2 — PSI open-loop injection
**FIXED (self-cancellation), NOT-FIXED (injection validity).** Removing the closed loop was correct and necessary. But the validated pressure source is `dd if=/dev/zero of=/dev/shm/...` (`collect_b5_psi.sh:70`), and the covariates are `swappiness=100` + `/dev/zram0` in active use (recon3 B1). Three consequences:
- **Compressible fill + zram = the balloon reclaims to near-nothing.** Zero pages pushed to zram compress ~1000:1, returning their RAM. Under `swappiness=100` the kernel *will* push idle tmpfs pages to zram. So a *held* zero-balloon does not hold a RAM deficit — it produces a one-time swap-out burst, then MemAvailable partially recovers and ongoing stall ceases.
- **PSI accrues from ongoing stall, not from low free memory.** The `6.95` is the reclaim burst of swapping the zero pages; a static occupant thereafter generates ~0 stall. The protocol's "one-shot to level and **hold**" (§4.5) is *worse* for signal than the recon's ramp — a held balloon likely settles to **~0 steady-state PSI**, and there is nothing to A/B against.
- **The identical 30 %/40 % readings (some `6.95/3.12/1.99`, full `6.32/2.83/1.81`) are the tell.** Two different pressure levels yielding byte-identical EWMAs across all three windows is unrefreshed-transient behavior (reads < the 2 s `avg2` window apart during a ramp), **not** a settled plateau. Steady-state PSI under a held balloon was never measured.
- **zram compression ratio is itself a confounder** *and* the fill choice makes it dominant: the A and B arms differ in reclaimable content by exactly the lever's saving, so the amount swapped-to-zram (and thus the compression work and stall) differs between arms — the desired signal, but riding on a pressure source that may be near-zero.

**Fix before executing §4.5**: use an **incompressible, mlock'd** balloon (anonymous mmap + `mlock`, or `/dev/urandom` fill without swap), and validate it **holds PSI `some` nonzero and settled for ≥120 s** before any A/B. Until then the north-star has no demonstrated operating point.

### A.3 — arena attribution via `decorate_maps`
**Source-CONFIRMED, on-target efficacy PARTIALLY-FIXED.** The chain is real: `glibc.mem.decorate_maps` (INT_32, default 0, `elf/dl-tunables.list:146`) → `__set_vma_name` reads `TUNABLE_GET(glibc, mem, decorate_maps, ...)` (`setvmaname.c:40`) → labels arena VMAs `" glibc: malloc arena"` (`arena.c:448`). The protocol's description matches source exactly. But two source-level sharp edges the protocol doesn't account for:
- **One-shot `prctl_supported` latch** (`setvmaname.c:33-48`): the tunable is consulted only while `prctl_supported==1`. The **first** `__set_vma_name` call (first arena / first large mmap, during early startup) decides forever: if `decorate_maps` was off at that instant, or if the kernel returns `-EINVAL`, the latch flips to 0 and **no VMA is ever labelled again, silently**. Consequence: `decorate_maps=1` must be in the process env **at exec** — it cannot be turned on later, and for the launchpad Top-5 that means injecting it into the pool and restarting (the unproven Layer-2 path, Part B.1).
- **Syscall present ≠ `CONFIG_ANON_VMA_NAME=y`.** 6.12.60 has the syscall number, but if the TV kernel built the config off, `prctl` returns `-EINVAL`, the latch trips, and PG2 sees **zero labels with no error** — indistinguishable from "arena_max worked, arenas gone." glibc's own `elf/tst-decorate-maps.c:188` `FAIL_UNSUPPORTED`s for exactly this. **PG2 must first prove labels appear** (inject `decorate_maps=1` into one test process, grep its `maps` for the label, assert nonzero) before trusting the "precise" method; keep the heuristic primary until then.

---

## 3. Part B — do v2's new pieces hold?

### B.1 — Layer-2 group injection (the declared main benefit surface)
The reasoning chain is **half-proven, and the unproven half is decisive.** recon3 shows the launchpad children's `exe` differs from the parent pool (`/usr/bin/ServiceH`, `/usr/bin/wrt`, …) — so *an* exec happened, and `__tunables_init` does run at exec (`csu/libc-start.c:267`). That establishes tunables *would* re-parse. It does **not** establish the load-bearing premise: **that `ServiceJ` propagates `GLIBC_TUNABLES` into the child's environment.** App frameworks routinely `clearenv`/whitelist env at candidate handoff for Smack/privilege hygiene; if GLIBC_TUNABLES isn't whitelisted, every Layer-2 injection silently no-ops. recon3 tested exe-inequality, never env-propagation. Also: because a candidate execs into the loader **once at pool-creation**, the env must be present at *pool* start — injection requires a pool restart (or reboot), not a live poke.

**Minimal on-board experiment (make it a hard gate, PG0):**
1. *Read-only first*: `cat /proc/<pool_pid>/environ` vs `/proc/<app_child_pid>/environ` (tr `\0` `\n`) — does the child carry the pool's vars at all?
2. *Decisive*: inject `GLIBC_TUNABLES=glibc.mem.decorate_maps=1` into the pool unit, restart pool (or reboot), launch a .NET app, then (a) grep `/proc/<app>/environ` for the marker → env propagates; (b) grep `/proc/<app>/maps` for `" glibc: malloc arena"` → the tunable *took effect*. One experiment proves both propagation and efficacy. **No Layer-2 batch should run before this passes.**

### B.2 — Handoff non-portability anchor
The three stated reasons (build flavor / CPU flags / memory env) are sound. Assessment of the "glibc mechanism is comparable" anchor:
- **Holds for allocation *decisions*.** The allocator algorithm is source-identical across a8/armv7 and a53/armv8; only codegen differs (recon3 G3: `malloc` 900 B TV vs 912 B RPI4 — instruction selection under `-march=armv8-a+crc`, not policy). Arena/bin/tcache layout is codegen-invariant. So RSS *mechanism* direction is portable — correct.
- **One thing to name explicitly**: armv8 atomics/barriers change the **cost of the arena lock**, so the L2 oversubscription *cost curve magnitude* measured on rpi4 (a8) is only a proxy for TV — likely an over-estimate (a53 atomics are cheaper), i.e. conservative, but it must be **re-measured on TV**, not extrapolated. The protocol already forbids porting perf numbers, so this is within its rules; it deserves a sentence so nobody reuses the rpi4 4:3=−22 % curve on TV.
- **`memcpy`/`memset` are NOT a divergence** (a live worry a priori): ARM multiarch is disabled (recon3 §7), so there is no ifunc runtime selection, and recon3 G3 shows `memcpy` byte-identical (784 B) across TV/RPI4/workspace. negative_fact — the CPU-flags difference does not reach the string routines.
- **The under-weighted item**: 1.6 GB + active zram (TV) vs 8.1 GB + idle zram (RPI4) changes the *reclaim regime* so much that a mechanism-level RSS delta may not predict a **PSI/swap** delta — retained arena fragmentation that is free on 8 GB can drive zram thrash on 1.6 GB. "Mechanism comparable" is true for the allocator; the *system consequence* of that mechanism (does the retained memory cost stall?) is TV-only. Emphasize that RSS-portable ≠ PSI-portable.

### B.3 — M3 statistical criterion (paired A-B-A-B, n≥20, CI-in-gate)
**Feasible for Layer 1, structurally hard for Layer 2 — the main surface.** For Layer-1 systemd services (drop-in + `systemctl restart`, seconds), interleaved n≥20 is achievable. For Layer 2, **toggling the lever requires restarting `ServiceJ`**, which §6 itself denylists ("重启会牵动全部 app") and steers to whole-device reboot. So each A↔B flip = a reboot/app-layer teardown + re-navigate to the scenario + settle (~1–3 min each, cold caches, fresh app launch). n≥20 *interleaved* A-B-A-B = 40+ reboots with non-identical post-toggle states → you are forced into **block design (all-A, reboot, all-B)**, which reintroduces exactly the temporal drift the interleaving was meant to cancel. Scenario latency (app-switch / channel-change) is also intrinsically high-variance (GPU/content/network). **So M3's rigor and Layer-2's injection cost are in direct tension.** Mitigations: (a) make Layer-2's **RSS/arena delta** (reboot-tolerant, robust) the *primary* adjudication and treat scenario latency as a coarse ≤10 % gate only; (b) if interleaving is impossible, run frequent C0-null blocks between A and B to bound drift and pre-register that only large effects (>10 %) are resolvable; (c) hunt for a pool refresh short of full reboot (unlikely) before committing.

---

## 4. Part C — gaps and risks

### C.1 — Uncovered execution collisions
- **L6 — the headline priority lever — has no demonstrated execution path on *either* track.** It is app product code (a `pause` callback); TV "不能装包" and the protocol admits "L6 需随产品版本出", but no product build→sign→flash pipeline exists in the recon; Track A (rpi4) builds *glibc*, not TV apps, and cannot run the TV app set. So the project's largest measured lever (board 59.9 MB) cannot be piloted as written. Establish a signed-test-app (develmode) path or a product-image pipeline, or L6 stays paper on TV.
- **Layer-2 toggling ⇒ whole-device reboot** (Part B.3): enumerate the reboot cadence and boot-to-steady-UI settle time; it dominates the schedule and the achievable n.
- **`/proc/<app>/environ` readability**: reading a launchpad child's env to *verify* injection (B.1) assumes it isn't scrubbed/protected; if unreadable, verification needs the maps-label proof alone.

### C.2 — Safety on a production board
The guardrail is **reactive and under-specified against a ServiceR config the recon couldn't fully read.**
- The recon measured balloon-**only** (no scenario). The protocol runs balloon **+ scenario** together; an app-switch on a .NET/WRT app can transiently allocate hundreds of MB on top of the 40 % balloon's 598 MB floor, pushing MemAvailable toward `ThresholdSwap=300`/`startPSIKillAt=250`. A ServiceR kill of a backgrounded target both invalidates the run **and** masquerades as a memory win.
- **The active ServiceR profile is unconfirmed** ("运行时活动档无法确认", recon3 B4) — so we don't actually know which thresholds are live; `[Memory2048]` may not be the operative section.
- `startPSIKillAt=250` / `psiTriggerPercent=55` / `psiWindowSize=2000000` semantics are unresolved (MB vs %). Measured `some avg2=6.95` is far under 55 %, so PSI-killing is probably not balloon-triggered *alone* — but balloon+scenario combined is untested.
- **Fix**: (a) confirm the live ServiceR profile first; (b) replace "stop on LMK" (reactive) with a **proactive MemAvailable floor abort** with margin (e.g. abort if MemAvailable < 350 MB, safely above 300/250); (c) live-monitor PSI% against `psiTriggerPercent`; (d) a balloon+scenario dry-run before any real A/B.

### C.3 — Implicit assumptions beyond §8's five
1. Launchpad env propagation (B.1) — the biggest.
2. L6 has no Track-B execution path (C.1).
3. `decorate_maps` kernel *config* + the `prctl_supported` latch (A.3).
4. Balloon fill compressibility × zram makes the pressure non-stationary (A.2).
5. Active ServiceR profile unknown → guardrail thresholds unknown (C.2).
6. M3 interleaving vs reboot-per-toggle incompatibility (B.3).
7. Funnel ranks on the unvalidated heuristic before A-2 calibration (A.1).

---

## 5. Top-3 — most likely to force rework

**#1 — The main benefit surface may be unreachable, and it's one unread `/proc/environ` away from being known.** Layer-2 group injection assumes `ServiceJ` passes `GLIBC_TUNABLES` to its app children. recon3 proved only that the children exec'd — not that env survives the handoff. If launchpad `clearenv`s or whitelists (standard app-framework security practice), all five top targets silently no-op and the campaign's headline surface yields zero — discovered only after building the Layer-2 harness. This is verifiable **read-only, today** (`/proc/<pool>/environ` vs `/proc/<child>/environ`), then decisively with a one-shot marker+maps test. Make it PG0.

**#2 — The PSI north-star still has no valid pressure source.** v1's self-cancellation is fixed, but the *validated* injector is `dd if=/dev/zero` into tmpfs under `swappiness=100` + zram — maximally compressible and swappable, so a held balloon evaporates to zram and PSI decays to ~0 after a ramp transient. The `6.95` the protocol calibrates against is that transient (proven by the byte-identical 30 %/40 % readings). Build the whole A/B harness on this and the north-star returns null. Fix before executing: incompressible, mlock'd balloon, validated to hold `some` PSI nonzero and settled ≥120 s.

**#3 — L6, the priority lever, cannot be run on the real board as written.** TV can't install packages; L6 is app code that "ships with the product version"; no build→sign→flash pipeline is described; Track A can't run TV apps. The project's biggest measured win has no execution path on Track B and none on Track A. Without a signed-test-app or product-image route, the L6 pilot in §4.4 is unexecutable — a rework discovered at pilot time.

---

## 6. negative_facts (verified — do not re-litigate)

- **`decorate_maps` source chain is exactly as the protocol describes**: tunable `elf/dl-tunables.list:146` (INT_32, default 0); gate `setvmaname.c:40` (`TUNABLE_GET(glibc, mem, decorate_maps)`); labels `" glibc: malloc arena"` (`arena.c:448`) and `" glibc: malloc"` for large mmap chunks (`malloc/malloc.c:2432,2519`) — so the exact method can separate arenas from mmap chunks, finer than the heuristic.
- **`parse_smaps.pl` does not wholesale miscount the .NET GC heap**: the `≤1 MiB` length filter drops multi-MB CoreCLR segments/regions; the `rw-p` filter drops `r-xp`/`rwxp` JIT code. False-positive exposure is limited to *small* 1-MiB-aligned rw-p anon (thread stacks, small aligned allocs) — an over-count, not a category error.
- **CPU-flags difference does not reach `memcpy`/`memset`**: ARM multiarch disabled (recon3 §7); `memcpy` byte-identical (784 B) across TV/RPI4/workspace (recon3 G3). Only `malloc` codegen differs (900 vs 912 B) — instruction selection, not policy.
- **The funnel *concept* is a correct fix of v1**: glibc heap is a material 28–45 % of Top-5 private dirty (recon3 §6), refuting v1's "nothing reachable."
- **Open-loop injection genuinely removes v1's closed-loop self-cancellation** — the mechanism fix is correct in principle (the residual problem is the *fill*, A.2).
- **TV kernel 6.12.60 ≥ 5.17** ⇒ the `PR_SET_VMA_ANON_NAME` *syscall* exists (v1's 5.4 blocker is retired — different board).
- **Track-A build channel works**: GBS produced 15 RPMs, RC=0, 9:46 (recon2 F1) — glibc-side changes (§9 dlconf patch) have a validated build path on rpi4. (But GBS output is **unsigned**; alloc_bench-through-signing on TV remains unverified — recon2 F2.)
- **TV `overcommit_memory=1`** ⇒ malloc never fails, so pressure goes straight to ServiceR/OOM — the guardrail must assume kills, not allocation failures.
- **Exec paths are board-opposite and both captured**: rpi4 execs from `/opt/usr/home` (`/root` read-only, recon2 A3); TV execs only from `/root` (`/tmp`, `/opt/usr/home` rejected, recon3 A2). The protocol's §0 table matches.
- **Identity self-check is warranted**: `/proc/4kbtin` is a real product-kernel proc node, not channel corruption (recon3 §6 C0) — the v1-recon `4kbtin` anomaly is explained.

## 7. cannot-verify (probe before/at protocol start)

- Whether `ServiceJ` propagates `GLIBC_TUNABLES` to app children (clearenv/whitelist?) — **gates the entire main surface** (B.1).
- Whether the TV kernel has `CONFIG_ANON_VMA_NAME=y` (syscall present ≠ config on); if off, `decorate_maps` silently no-ops via the `-EINVAL` latch (A.3).
- Steady-state PSI under a **held** balloon, and the real RAM pressure of a `/dev/zero` balloon over a sustained hold under zram+`swappiness=100` (likely evaporates; recon only ramped-and-read transients) (A.2).
- Which ServiceR Memory profile is **live** at runtime, and the semantics of `startPSIKillAt=250` / `psiTriggerPercent=55` (C.2).
- Whether balloon **+ scenario** combined trough crosses `ThresholdSwap=300`/`startPSIKillAt` and triggers a kill.
- **L6 execution path on TV** — product build→sign→flash pipeline is undescribed; can't install packages (C.1).
- The heuristic-vs-`decorate_maps` **overcount factor** (A-2 not yet run) → true glibc-reclaimable share vs the 28–45 % upper bound.
- Whether `/proc/<app>/environ` is readable for launchpad children (needed to verify injection).
- Whether a pool restart / whole-device reboot yields a low-enough-variance post-toggle state for n≥20 paired M3 on Layer 2 (B.3).
- L2 oversubscription cost-curve **magnitude** on a53/armv8 atomics (rpi4 a8 curve is only a proxy) (B.2).
- The active ServiceR profile aside, whether any Top-5 target is a `churn`-class process under the §4.2 TID-turnover classifier (only measurable live).
