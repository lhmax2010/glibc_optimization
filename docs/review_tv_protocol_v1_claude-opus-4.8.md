> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Pre-Freeze Review — `docs/tv_phase_protocol_v1.md` (TV-Phase Protocol v1)

## 1. Reviewer header

- **Reviewer**: Claude Opus 4.8 (`claude-opus-4-8[1m]`)
- **Date**: 2026-07-10
- **Materials**: `tv_phase_protocol_v1.md`, `tv_board_recon_report.md`, `tv_sdbd_recovery_guide.md`, design v2.4 (`tizen_glibc_memopt_design_v2.md` §0d), board chain (Batch 1/2/2.5), `bench/alloc_bench/`, glibc tree @ `8f08a7e303`.
- **Standard applied**: what causes TV-phase **rework / crash / untrustworthy data**. Not document completeness. This is process review; numbers were re-verified in the v2.3 round and are not re-litigated.
- **Method**: walked every protocol step against the recon-confirmed TV capability matrix; verified four mechanism claims against source (`decorate_maps`→prctl, `check_may_shrink_heap`, `mtrim` vs `trim_threshold`, `thread_arena` stickiness); cross-checked protocol assumptions against the recon's own raw evidence (especially the balloon/PSI trace and the top-RSS process table).

**Verdict legend**: EXECUTABLE / RISKY (+mitigation) / BLOCKED (+dependency).

---

## 2. Part A — precondition gates and step-by-step executability

| § | Item | Verdict | Basis / mitigation |
|---|---|---|---|
| 0 | Covariate baseline table | **RISKY** | `Cores \| recon-recorded value` is an **unfilled placeholder** in a freeze candidate, yet `arena_max = cores` depends on it (recon: **4**, recon §3). Table omits three covariates M5 mandates and that *differ from the board*: `overcommit_memory` **1** (rpi4: 0), `MemTotal` **1602608 kB** (rpi4: 3978536), and swap presence. Add them; see negative_facts for why overcommit 0→1 does *not* break comparability. |
| 0.1 | stdin injection `sh -s` | **RISKY** | Works (recon V1 PASS) because the executed binary is the signed `/usr/bin/sh`. But: (a) it is a **PTY** — recon records "`sdb shell` stdout echoed the script body", so **stdout is unusable for data**; all collection must redirect on-device and `sdb pull`. (b) **No exit-code propagation** — a truncated run looks like success; mandate an in-band `EXIT=$?` + completion sentinel. (c) EOF does not close the session (recon: trailing `exit` required). (d) The one TV inventory that ran shows `/proc/4kbtin/cmdline: Not a directory` (recon L433) — `4kbtin` is not a PID. **The only TV dataset we have contains channel-or-parse corruption**, and PG3 depends on it. (e) A long-lived collector (§5's 1 Hz sampler) dies with the sdb session; `nohup`/`setsid`/`systemd-run` are unprobed. **Mitigation: use SSH.** The recovery guide already proves `ssh root@<PRODUCT_BOARD_IP>` works; `ssh host 'sh -s' < script` gives no PTY echo, real exit codes, and survivable background jobs — and still executes only the signed `sh`. |
| 0.1 | tmpfs balloon as pressure source | **RISKY→redesign** | Mechanically works (64 MiB → MemAvailable −65104 kB, clean `rm` recovery). But as a *PSI generator* it is mis-designed — see Part B.2. Also two unlisted hazards: `/dev/shm` is only **782 MiB** (`df`: 801304 1K-blocks) < 1.05 GB MemAvailable, and it is **shared with compositor/audio shm buffers** (`shared 5540 kB` at idle) — filling it can starve Wayland/EFL buffer allocation and break the UI for reasons unrelated to memory pressure. |
| 0.1 | "alloc_bench does NOT go on TV" | **RISKY — internally inconsistent** | §4 assumes we *can* ship product code through the "normal build+signing chain". If that chain exists for L6, it exists for a 124 kB benchmark. Recon only ever tried `/tmp`; UEP is **signature-based, not mount-based** (`/tmp` is `rw,posixacl`, *not* `noexec`, recon L251-254), so relocating won't help — but **signing would**, and it was never attempted. Abandoning the deterministic instrument is the single largest self-inflicted measurement loss (Part B.1). Cost to fix: one signed build. |
| 1 | **PG1** TV-branch T1 re-derivation | **BLOCKED** | Dependency: the TV-branch source is not identified, let alone obtained. The image self-contradicts: `VERSION_ID=10.0.0` / `PRETTY_NAME="<PRODUCT_IMAGE>"` but `BUILD_ID=<PRODUCT_IMAGE_A>` (recon L42-45). Runtime is `glibc-2.40-1.7.armv7l` (L95). **Unblock cheaply on-device**: `rpm -qi glibc`, `rpm -q --qf '%{SOURCERPM}\n' glibc`, `rpm -q --changelog glibc \| head` (rpm present) to name the branch/SRPM; `grep -a -c 'glibc.malloc.arena_max' /lib/ld-*.so* /usr/lib/libc-2.40.so` to prove tunables are compiled in; `ls /run/dlconf.dat` to see whether dlconf is enabled on TV. Define a **behavioural fallback** (PG2 + these probes) for the case where the product branch source is unobtainable — otherwise the whole protocol is gated on an external org. |
| 1 | **PG2** tunables efficacy via `malloc_info()` arena count | **BLOCKED as written** | `malloc_info()` is an in-process API. With alloc_bench blocked there is **no way to call it in a process you did not write** — no gdb/strace/perf in the recon matrix. So PG2 cannot execute. Worse, **the same defect silently kills M2** (design §6 "malloc_info pre/post") for every system service in §3. **Unblock**: count arenas from `/proc/<pid>/maps` using the glibc heap signature — a **1 MiB-aligned** anon span of exactly `HEAP_MAX_SIZE`=1 MiB (`malloc/arena.c:30` × `malloc/malloc.c:955`), typically an `rw-p` prefix plus a `---p` remainder. `arena_max=1` should drive secondary arenas to **zero**, a clean binary proof. Note the elegant method is unavailable here: glibc *does* label arena VMAs `" glibc: malloc arena"` (`malloc/arena.c:448`) under `glibc.mem.decorate_maps=1`, but that uses `prctl(PR_SET_VMA_ANON_NAME)` (`include/sys/prctl.h:6-8`), which **landed in kernel 5.17** — works on rpi4 (6.12), **not** on TV (5.4.261). |
| 1 | **PG3** AT_SECURE routing | **EXECUTABLE (data suspect)** | Distribution already collected: 122 procs, 23 secure / 99 non-secure (recon L436). But it came from the corrupted stdin run (see §0.1(d)); re-run over SSH and validate row count before routing. |
| 2 | Target funnel (122 → 5–10) | **BLOCKED for its stated purpose** | Three independent defects: (a) **ranking metric is misaligned with the levers' addressable surface** — see Top-3 #1; (b) "arena count approximation = count of `rw-p` anon / `[heap]` segments" **wildly overcounts** — every GC heap, JIT region, graphics buffer and thread stack is `rw-p` anon; use the 1 MiB-aligned signature above; (c) **the churn classifier is mis-specified**: v2.4 §0d requires *task-ID turnover*, but §2 degrades it to "`/proc/pid/task` **count** and two-sample turnover rate". A recycling thread pool (exit+create) holds count constant → turnover reads 0 → classified non-churn → `arena_max` applied → the **exact +11~+21 MB inversion the design forbids**. Also "single collection" cannot yield a two-sample rate. Fix: sample the *TID set* at 1 Hz for ≥60 s under an active scenario; turnover = \|new ∪ gone\| / interval. (d) `Private_Dirty` was never shown present in TV `smaps_rollup` (recon L157 truncates after `Pss_File`). |
| 3 | TV Batch 1 (L1+L3 ±L2) | **BLOCKED for launchpad-class targets; RISKY for systemd services** | Blocked: see Top-3 #1 — the highest-value targets have no systemd unit, so `/etc/systemd/system/<unit>.d/memopt.conf` cannot reach them. Risky for real services: (i) **no null arm** — the board phase's noise table is what saved it (`pass` band 92 kB vs `pulseaudio` 0); TV scenario latency is far noisier and §3 has no C0-vs-C0 sham; (ii) the **latency instrument is unnamed** ("in-scenario latency observation"); (iii) **restart hazards** (Part C.2) incl. a *demonstrated* `service-start-limit-hit` on this very unit (recovery guide L324); (iv) **M2 unavailable** (see PG2); (v) no **settle-time / steady-state criterion** after restart; (vi) `+L2` introduces an **untested L1+L3+L2 triple** (board combo-verified only L1+L3). |
| 4 | L6 pilot | **EXECUTABLE (landing point) / RISKY (measurement undefined)** | `app_pause` is the right hook and the product-code path is UEP-independent — sound. But both mandatory cost measurements are named, not specified, and one is aimed at the wrong counter: with **no swap and `MADV_DONTNEED`** on private anon (`malloc/malloc.c:5192`), refaults are **minor faults + page-zeroing, not major faults**. §5's `workingset_refault`/`pgmajfault` will read ≈0. Use `/proc/<pid>/stat` **minflt** delta. See Part B.3 for both methods. |
| 5 | PSI north-star | **RISKY→mandatory redesign** (partial hard block on attribution) | Four defects, one fatal-by-construction. See Part B.2. The protocol's claim "already seen responding during balloon validation" is **not supported by its own evidence**: across the 64 MiB balloon, `some avg2/avg6/avg10` stayed `0.00` and `some total` moved 460566→460567→460568, i.e. **~1 µs of stall** (recon L491-511). PSI is *readable*; it has not been shown to *respond*. Hard block: cgroup v1 (no `cgroup.controllers`, recon L156) ⇒ **no per-service PSI**, only system-wide — a single-service lever's effect is diluted across 122 processes. |
| 6 | Rollout / rollback | **RISKY** | No `systemctl reset-failed` between reps (start-limit is a demonstrated failure mode here); no **restart denylist**; no out-of-band recovery channel named (SSH exists and is proven); `/etc` vs `/run` writability unresolved (§8 admits) — note `/run` drop-ins vanish on reboot, which is *fine for experiments* and should be the **default**, not the fallback. |
| 7 | Completion criteria | **RISKY** | "passes the M3 dual gate ⇒ shippable" has **no statistical decision rule**: no estimator, no n, no paired design, no noise floor. On board data a 5 % effect was detectable because alloc_bench was deterministic; on TV scenarios it may not be. Require: paired/interleaved A-B-A-B, n≥20, median + Wilcoxon, and *ship only if the CI upper bound is inside the gate*, with the noise floor fixed by the C0/C0 null arm. |
| 8 | Known-open list | **incomplete** | Misses: launchpad addressability, glibc-heap share of targets, `malloc_info` unavailability (kills M2/PG2), PSI closed-loop cancellation, swap presence, `/dev/shm` ceiling and shm starvation, start-limit, TID-vs-count churn classifier, thermal covariate. |

---

## 3. Part B — measurement validity (the protocol's output-quality spine)

### B.1 The TV perf gate substitutes a different quantity for M3's gate

M3 gates on **"≤5 %/≤10 % regression on allocation-heavy paths."** §3 replaces the deterministic instrument with whole-scenario latency. These are not the same measurement, and the substitution is silently lossy in both directions:

- **Dilution (false pass).** App-switch / channel-change / UI-scroll are dominated by I/O, decode, GPU and compositor work. A −46 % malloc regression (the measured `4:2` arena cliff) could surface as ~1–2 % scenario latency and pass the gate — then bite under a different load mix. The gate is supposed to bound the *allocator*, not the scenario.
- **Noise (false fail / false pass).** Board precedent: `pass`'s 92 kB noise band swallowed all effects while `pulseaudio`'s was 0. Scenario latency variance is orders of magnitude worse. §3 provides no noise floor.

**Recommendations, in order of value:**
1. **Sign alloc_bench** and restore the deterministic pre-screen on TV (§4 already assumes the signing chain). This closes the largest hole for one build. If refused, at minimum probe whether unsigned exec is blocked from `/root` and `/opt/usr/home` too — recon only ever tried `/tmp`.
2. **Mandatory C0-vs-C0 null arm** per target, run first, to fix the false-positive floor. Without it no 5 % claim is defensible.
3. **Paired, interleaved A-B-A-B** ordering (not blocks) to cancel thermal/DVFS/cache drift; n≥20; report median + IQR; decide with a paired nonparametric test on the *CI bound*, not the point estimate.
4. **Pick an allocation-sensitive scenario**: cold app start / app switch (malloc-heavy) rather than UI scroll (GPU-bound).
5. **Record thermal** — TV thermal zones were never probed; governor is already `performance`-only (recon L162) so that confound is absent, but throttling is not.
6. **Never take the perf gate from a pressure run** — balloon-induced page-cache eviction inflates scenario latency in *both* arms and adds variance.

### B.2 PSI AUC design — one fatal flaw, three serious ones

**(a) FATAL — closed-loop targeting cancels the effect by construction.** §5 says "incremental append to hold system `MemAvailable` at a target level." If the lever frees 10 MB in the target, the controller must grow the balloon by 10 MB to hold `MemAvailable` fixed. **The injected pressure is therefore larger in the lever arm by exactly the amount the lever saved.** The A/B measures ≈0 by design, whatever the lever does. → **Use an open-loop, fixed-byte balloon** (same absolute size both arms); `MemAvailable` is then an *outcome*, and PSI is allowed to differ.

**(b) A static tmpfs balloon does not generate PSI.** PSI-memory accrues from time tasks spend stalled in **direct reclaim / refault / thrash** — not from low free memory. A tmpfs file that is never reclaimed produces no stall. This is exactly what the recon shows (`avg=0.00`, Δ`total`≈1 µs across 64 MiB). Moreover tmpfs is **swap-backed only**, and the TV `free` output has **no Swap row** at all (recon L488-508) — so tmpfs here is likely *unevictable*, a hard occupancy, not a graded pressure knob. **Add a demand side**: hold a fixed tmpfs floor, then drive reclaim with file-cache thrash (repeated large-file reads) and/or the scenario's own allocations, and ramp the floor until `some` rises. Expect a narrow window: with no swap, anon is unreclaimable, so once file cache is gone the system goes from "no stall" to OOM/LMK quickly.

**(c) LMK will silently invalidate runs, and it kills exactly the wrong things.** `overcommit_memory=1` means `malloc` never fails — the system goes straight to OOM/LMK. The balloon's pages are shmem, charged to no killable process, so the killer targets the **largest-RSS processes: `ServiceT` 86 MB, `menu` 85 MB, `ServiceE` 68 MB** — i.e. our targets. Tizen's `ServiceR` LMK will additionally kill **backgrounded** apps first, which is precisely the state §4's L6 pilot puts its app into. A run where LMK killed the target yields a beautiful RSS/PSI number and is worthless. → **Make LMK/OOM kill detection a run-invalidating guard** (`journalctl` grep for lowmemorykiller/oom_kill, plus a pre/post PID check on the target), and never co-schedule §4 and §5.

**(d) Metric and attribution.**
- The TV kernel exposes `some/full avg2 avg6 avg10` — **there is no `avg60`** (recon L154). §5's "avg10/avg60" is wrong for this device.
- The `total` field is a monotonic microsecond accumulator. **Use Δ(some.total) and Δ(full.total) over the window instead of an AUC of the EWMA fields** — exact, immune to 1 Hz aliasing and to the non-standard window set.
- cgroup v1 ⇒ system-wide PSI only. A one-service lever's PSI signal will be near noise. Either lever the whole selected target set for the PSI arm (accepting which-lever confounding, which is fine for a north-star sanity check), or pre-register a power analysis and report effect size + CI honestly.
- **Reproducibility**: `drop_caches` before each arm and fix the balloon in absolute bytes; otherwise the two arms start from different page-cache states and the `MemAvailable` curves cannot align.
- **Separate the confounds**: run scenario-only, balloon-only, and both, so the interaction term is visible rather than assumed additive.

### B.3 L6's two mandatory costs — executable methods

**Refault → first-frame latency.** L6 is product code, so instrument in-process; no glibc change:
- Timestamp `app_resume`/`app_control` entry → first frame (EFL/Evas render-post, or `Ecore_Evas` post-render callback). Report the trim-arm minus no-trim-arm delta on the same app, same content.
- **Corroborate with the right counter**: `MADV_DONTNEED` on private anon with no swap drops pages; re-touch yields a **minor fault + zero-fill**, not a major fault. Read `minflt` (field 10) from `/proc/<pid>/stat` before/after resume. `pgmajfault`/`workingset_refault` will read ≈0 and must **not** be used as the L6 refault metric (they remain correct for §5's page-cache pressure).
- Order of magnitude to expect: ~60 MB / 4 KiB ≈ 15 k minor faults + zeroing ≈ tens of ms — bounded, no I/O. Confirm, don't assume.

**Trim-time all-arena lock stall.** `__malloc_trim` locks each arena **serially** and, per arena, runs `malloc_consolidate` + interior `MADV_DONTNEED` (`malloc/malloc.c:5217-5226`, `:5155`, `:5192`). Two userspace-only measurements:
1. **Trim wall time**: bracket the `malloc_trim(0)` call with `clock_gettime(CLOCK_MONOTONIC)`. This is the upper bound on any single thread's stall.
2. **Canary thread** (the decisive one): a thread in the same process running a tight `malloc(64)/free` loop recording per-iteration latency. Its **max latency inside the trim window** *is* the observed stall, measured with zero glibc modification and no `perf`/`ftrace` (neither is on the TV command matrix). Run with the app's real background threads active — that is the condition board Part D never tested.
3. Note the **L2×L6 interaction**: fewer arenas ⇒ shorter serial lock walk. If `arena_max` ships on the same target, trim cost drops. Worth one cell; it is plausibly the project's only *positive* lever interaction.

---

## 4. Part C — missing items and risks

### C.1 Multi-lever interaction is under-covered
Board combo-verified exactly one pair (**L1+L3**, +0.1 %/−2.43 MB). §3 introduces **L1+L3+L2**, an untested triple, straight into the first TV batch. And L6 will eventually coexist with L1+L3 on the same target — also untested. **Recommend**: TV Batch 1 ships only the validated L1+L3 and, separately, L2 alone on a qualifying target; combine only after each passes; add one explicit L2×L6 cell (predicted positive: fewer arenas → cheaper trim). One mechanical orthogonality *is* already proven and need not be re-tested: `mtrim` never consults `trim_threshold` (it appears only on the free-path auto-trim at `malloc/malloc.c:4784` and in the setters), so **L3 ⊥ L6 by construction** — board Part D's zero-reclaim control was mechanically necessary, not luck.

### C.2 Restarting real services on a production TV image
The protocol's restore discipline is inherited from the rpi4 phase and is **not sufficient for TV**.

- **Demonstrated hazard on this exact unit**: `sdbd_tcp.socket: failed (Result: service-start-limit-hit)` (recovery guide L324). §3's design restarts a unit ≥4× (C0, C0_noise, L1+L3, +L2). With stock `StartLimitBurst`/`StartLimitIntervalSec` this **will** trip and leave the unit permanently failed. → Mandate `systemctl reset-failed <unit>` between reps and inter-restart spacing > `StartLimitIntervalSec`.
- **Pre-flight per unit** (all commands present): `systemctl show -p Restart,StartLimitBurst,StartLimitIntervalSec,WatchdogSec,PartOf,BindsTo,Conflicts <unit>` and `systemctl list-dependencies --reverse <unit>` — `PartOf`/`BindsTo` mean a restart **cascades**.
- **Explicit denylist** (protocol has none): `sdbd` (kills your own channel — and its develop-mode **IP gate** means a host IP change silently locks you out, recovery guide L45/L105-119); `enlightenment` (compositor — tears down the whole UI and every app surface); `launchpad`/`ServiceE`/`ServiceH` pools (kills every app forked from them); `ServiceR` (the LMK itself; restarting it during a pressure experiment is self-sabotage); anything boot-critical.
- **Out-of-band recovery must be live before touching anything**: confirm `ssh root@<tv>` works at session start. The recovery guide exists precisely because sdb died once; a protocol whose entire substrate is one `sdb shell` session has a single point of failure.
- **Snapshot** `systemctl list-units --failed` before and after every session; a nonempty delta invalidates the run.
- Prefer **`/run/systemd/system/<unit>.d/`** drop-ins as the default (reboot-clean, no rootfs write needed), not as the read-only fallback.

### C.3 The "shippable → production default" gap — yes, it belongs in the protocol
§7 stops at "this lever×target is shippable." The decision that actually costs money is *"turn it on by default in the mass-production image."* That gap should be a **named downstream artifact with entry criteria written now**, because two of its answers change §3 *today*:

- **Delivery mechanism**: who owns the drop-in in the shipped image — an RPM-owned file, an image-config fragment, or the app framework? If production will use RPM-owned files, the experiment should already inject via that path, not hand-written `/etc` files.
- **Kill-switch / field rollback**: env levers ship inside a systemd unit; there is no runtime disable short of OTA. Consider a vconf-gated launcher wrapper so a bad lever can be disabled without an image update.
- **Soak**: ≥72 h with fragmentation trend (`smaps_rollup` slope), LMK-kill counts, and PSI `total` accumulation. Every lever here changes *long-run* allocator behaviour; a 30 s benchmark cannot see arena fragmentation drift.
- **Whole-image regression**: per-target scenario latency ≠ product regression suite. Multiple levered services interact through the shared LMK/PSI substrate.
- **L6 as a platform API**: if trim-on-background is right for one app, it is probably right for the app framework's `pause` path — that is an app-model decision, not a per-app patch, and it should be raised before the pilot hard-codes it.

---

## 5. Top-3 — most likely to force TV rework

**#1 — The funnel will select targets that no glibc lever can reach, by either mechanism.**
§2 ranks by `Private_Dirty × instance_count`. Applied to the recon's own top-RSS table, that selects `AppProcD` (86 MB), `AppProcB` (85 MB), `ServiceE` (68 MB), `AppProcE` (51 MB) — i.e. **.NET/CoreCLR apps and the WebRuntime**. Two independent failures follow:
- *Memory surface*: CoreCLR's GC heap and WebKit's bmalloc are mmap'd directly, **not** glibc `malloc`. `malloc_trim(0)` cannot reclaim a GC heap; `arena_max`/`tcache` do not govern it. Most of that 86 MB is invisible to every lever in v2.4.
- *Injection surface*: `ServiceH` and `ServiceE` are **launchpad-style pools**; the `DN_*` processes are their **fork-without-exec** children (comm renamed via `prctl`, cmdline still the app `.dll`). Tunables are parsed once at process start (`__tunables_init`, `csu/libc-start.c:267`); a forked child never re-parses. So a per-app `GLIBC_TUNABLES` is **structurally impossible** — only a pool-global setting exists, which violates M4 ("per-service, never image-global"). This is the same class of obstacle the board phase already hit and logged (`board_ab_batch1_report.md`: *"skip AppV … ServiceJ …, not a targetable per-app unit"*) — the protocol did not carry that lesson forward.

**Fix before freeze**: add two screens *ahead of* ranking — (i) **addressability**: `readlink /proc/<pid>/exe` + `/proc/<pid>/cgroup` + `systemctl status <pid>` to confirm a targetable unit; (ii) **glibc-heap share**: from `/proc/<pid>/smaps`, sum `Private_Dirty` over `[heap]` plus 1 MiB-aligned arena-signature regions, and rank on *that*, not total private dirty. Expect the real env-lever targets to be the **native** residents — `enlightenment`(26 thr), `ServiceC`(32), `ServiceD`(28), `ServiceL`(26), `ServiceR` — with L6 reserved for app code.

**#2 — The PSI experiment cannot produce a trustworthy curve as designed.**
It is self-cancelling (closed-loop `MemAvailable` targeting grows the balloon by exactly the lever's saving), its pressure source generates occupancy rather than reclaim (recon's own 64 MiB run: `avg10 = 0.00`, Δ`total` ≈ 1 µs — so "PSI seen responding" is unsupported), it names an `avg60` window the kernel does not expose, it has no per-service attribution under cgroup v1, and it has no guard against LMK killing the target mid-run — an event that would *improve* every number it reports. Since PSI is the project's declared north-star and has never once been measured, shipping this design means the phase's headline metric comes back either null or fraudulent. Redesign per Part B.2 **before** execution: open-loop fixed bytes, a reclaim demand source, Δ`total` as the metric, LMK-kill as a run invalidator.

**#3 — `arena_max = cores` is being applied far outside the regime the board sampled, on a "safe by construction" argument that has a hole.**
v2.4 §0d argues the floor is safe because *running* allocating threads ≤ online cores. But arena binding is **sticky per thread** (`thread_arena`, `malloc/arena.c:129-139`) and assignment is round-robin (`next_to_use`, `:760-763`). TV targets run **26–55 threads on 4 cores**. Default cap is `2×cores = 8` arenas (`NARENAS_FROM_NCORES`, `malloc/malloc.c:1921`) ⇒ ~7 threads/arena; `arena_max=4` **doubles** that to ~14 threads/arena. The board's "1:1 is free" cells (4 threads / 4 arenas) had exactly **one thread per arena** — a regime with no sharing at all. The ≤cores-running argument also ignores **lock-holder preemption**, and this kernel is `PREEMPT` (recon L51): a preempted lock holder blocks the 13 threads queued behind it regardless of how many are runnable. Shipping `arena_max=4` to a 55-thread target on the strength of a 4-thread experiment is precisely the extrapolation this project has spent three rounds avoiding.
**Fix**: express the gate in **threads-per-arena**, and before `+L2` is allowed anywhere, sweep `arena_max ∈ {8 (default), 6, 4}` on one high-thread **native** target with p99 scenario latency and the maps-derived arena count.

---

## 6. negative_facts (verified — do not re-check)

- **UEP is signature-based, not mount-based.** `/tmp` is `rw,posixacl,relatime` and **not** `noexec` (recon L251-254); pushed files carry Smack `System` (L256). Relocating the binary to `/root` cannot help *if* enforcement is purely signature — but that was **never tested** (see cannot-verify). Signing, or inline `sh`, are the only proven paths.
- **stdin injection genuinely bypasses UEP** because the executed image is the signed `/usr/bin/sh` (recon V1 PASS). The bypass is sound; only the *channel quality* is at issue.
- **The tmpfs balloon mechanically works**: 64 MiB → `MemAvailable` −65104 kB, clean release on `rm` (recon L519-522).
- **PSI is readable and carries a monotonic `total` µs counter, but has NOT been shown to respond to pressure.** `some avg2/avg6/avg10 = 0.00` before, during and after the 64 MiB balloon; `some total` 460566→460567→460568 (recon L491-511). The protocol's §5 claim to the contrary is unsupported by its own evidence.
- **The TV kernel exposes `avg2/avg6/avg10`, not the mainline `avg10/avg60/avg300`** (recon L154).
- **overcommit 0→1 does not break board→TV mechanism comparability.** `check_may_shrink_heap()` returns true only for `AT_SECURE` **or** `overcommit_memory == '2'` (`sysdeps/unix/sysv/linux/malloc-sysdep.h:34-56`). Both boards are ≠2, so both take the `MADV_DONTNEED` (RSS-only, VA-retained) shrink path (`malloc/arena.c:525`). Record it as an M5 covariate; do not treat it as invalidating. (Corollary: the 23 `AT_SECURE` TV processes *do* take the commit-releasing `PROT_NONE` path — they are not comparable to the other 99.)
- **L3 ⊥ L6 is mechanically necessary, not an empirical accident.** `mtrim` calls `malloc_consolidate` then interior `MADV_DONTNEED` then `systrim(pad)`; `trim_threshold` is consulted only on the free-path auto-trim (`malloc/malloc.c:4784`) and in the setters. Board Part D's zero-reclaim L3 control could not have come out otherwise.
- **The clean arena-identification method is unavailable on TV.** glibc labels arena VMAs `" glibc: malloc arena"` (`malloc/arena.c:448`) under `glibc.mem.decorate_maps=1`, via `prctl(PR_SET_VMA_ANON_NAME)` (`include/sys/prctl.h:6-8`). That prctl exists from kernel 5.17; TV is 5.4.261. It **would** work on rpi4 (6.12) — useful for validating the maps heuristic on the board before trusting it on TV.
- **THP is absent as a config, not merely unset** (no `/sys/kernel/mm/transparent_hugepage/` directory, recon L153) ⇒ L13 and R14 are moot on this target; no re-probe needed.
- **Governor offers only `performance`** (recon L162) ⇒ no pinning step, no DVFS confound from the governor (thermal throttling is a separate, unprobed question).
- **The command set suffices for the funnel**: `awk sed grep cut sort head tail wc od tr cat ls rm mkdir df free ps pgrep pmap readlink systemctl journalctl rpm` all present; `busybox`/`hostname` absent but unused. `dd` works (recon V2) despite being absent from the command matrix — the matrix is incomplete, not the capability.
- **cgroup v1 confirmed** (no `cgroup.controllers`, recon L156) ⇒ per-cgroup `memory.pressure` does not exist; PSI is system-wide only.
- **Runtime glibc is 2.40** (`glibc-2.40-1.7.armv7l`, recon L95), matching the audited baseline's major/minor — the *patch set* is what PG1 must establish.
- **Plan B (mallopt) is UEP-immune** — it is product code, like L6.

## 7. cannot-verify (must be probed before/at protocol start)

- Whether TV `smaps_rollup` exposes **`Private_Dirty`** (recon excerpt truncates after `Pss_File`) — the funnel's ranking field.
- **Whether the TV has swap** (`free` prints no `Swap:` row, recon L488-508; `/proc/swaps` unprobed). Determines tmpfs evictability, whether anon can be reclaimed at all, and the fault class of L6 refaults.
- Whether unsigned ELF/script execution is blocked from **`/root` and `/opt/usr/home`**, not just `/tmp` (only `/tmp` was ever tried) — decides whether alloc_bench is truly impossible on TV.
- Existence of `systemd-run`, `setsid`, `nohup`, `chsmack`, `gdb`, `strace`, `perf`, `mount`, `dmesg` — several mitigations (durable background samplers, arena inspection) depend on them. `vconftool` is known present (recovery guide).
- Whether `DN_*` / `ServiceE` children are **fork-without-exec** launchpad processes (`readlink /proc/<pid>/exe`, `/proc/<pid>/cgroup`) — decides whether env levers can reach the top targets at all (Top-3 #1).
- The **glibc-heap share** of each top target's private dirty memory (needs per-region `/proc/<pid>/smaps`).
- `ServiceR` LMK thresholds and whether it fires during the balloon ramp — decides whether a usable PSI window exists at all.
- TV **thermal zones** and whether throttling occurs during scenario runs (never probed; rpi4 phase logged thermal).
- Whether all 4 CPUs stay online during scenarios (`/sys/devices/system/cpu/online`) — `arena_max = cores` depends on it, and the protocol left `Cores` as a placeholder.
- **TV-branch glibc patch set** and whether `dlconf` is enabled on the TV image (`/run/dlconf.dat`) — PG1's output.
- Rootfs (`/etc`) writability — §8 already lists it.
- Whether the `4kbtin` anomaly (recon L433) is a script parse bug or stdin-channel corruption — gates trust in the only TV dataset collected so far.
