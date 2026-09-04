[中文](README.zh-CN.md) | English

# Tizen glibc gated-trim Demo

> This English entry is derived from the Chinese technical documentation. If
> wording is ambiguous, the Chinese technical documents are authoritative.

## What this is

This frozen Demo delivers a gated Tizen glibc (ptmalloc) trim method: exclude
visible automatic reclaim as an anti-signal, confirm allocator-retained free space
with M7, require a same-target, same-phase trim probe to meet a precommitted reclaim
threshold, then call `malloc_trim(0)` only at a known release phase while accepting
refault, latency, and health evidence together. On the frozen RPI4/Tizen
glibc-2.40-1.6.armv7l matrix, the calibration centers are 51%–53%, and gated trim reclaimed about
80%–85% of released payload; per-profile median calls were mixed 1.233269 ms and
medium-only 1.218361 ms, and the gst p99
direction was not visible by the fixed comparison rule. These are mechanism and scale
results, not a product-memory-benefit promise.

## Headline results

| Comparison | Accepted result | Report | Compact evidence |
|---|---|---|---|
| Instant-release anchors | calibration: mixed `52.794499% ±4.304705 pp`, medium-only `50.669791% ±4.918088 pp` (`n=8` each, pre-trim heap); excluded GBS held-out passed 4/4 | [HTML summary](docs/demo_report.html#summary) | [`calibration`](data/raw/a_anchor_replication_20260904/decision.json), [`held-out`](data/raw/gbs_heldout_validation_20260904/decision.json) |
| Gated valley trim vs none | `80.18%–85.45%` of released payload; median call mixed `1.233269 ms` / medium-only `1.218361 ms`; next-cycle `+1351/+1465 minflt`, `majflt=0` | [S4 effect](docs/demo_report.html#s4) | [`b_cycles.tsv`](data/raw/s4_retention_20260901/b_cycles.tsv), [`b_cells.tsv`](data/raw/s4_retention_20260901/b_cells.tsv) |
| gst trim vs none | p99 `+6.228611 ms` vs none dispersion `6.784167 ms`: margin `0.555556 ms`, 91.8% of threshold, `REPORT_ONLY` not visible; the same p50 rule is visible (`+1.870462` vs `0.173927 ms`); `+359 minflt/cycle` | [Real concurrency](docs/demo_report.html#gst) | [`comparison.json`](data/raw/gst_trim_cost_20260901/comparison.json), [`cycles.tsv`](data/raw/gst_trim_cost_20260901/cycles.tsv) |
| Tizen native cross-witness | Historical enlightenment cells: about `5.84 MiB` rest and `272/4/4 KiB` reclaim. B2: official gst `5/5`, reclaim `8/16/16/20/16 KiB`; five verified UI cycles then E4′ rest `6019572 B`, reclaim `36 KiB`. Project heap PD and Tizen `memps` match exactly | [Native process evidence](docs/demo_report.html#native) | [`B2 cells`](data/raw/tizen_native_evidence_b2_20260904/cells_derived.tsv), [`B2 summary`](data/raw/tizen_native_evidence_b2_20260904/summary.json), [`historical summary`](data/raw/tizen_native_evidence_20260904/summary.json) |

The batch release reference `48.9% / 1.36 MiB × 8 processes` comes from
`<TEST_IMAGE_B>` / `glibc-2.40-2.8`; it is a compatibility comparison, not part of
the frozen matrix ([evidence](data/raw/demo_reproduction_20260901/batch_release_phase.tsv)).

## Three ways to start

1. **Read offline — minutes.** Open [`docs/demo_report.html`](docs/demo_report.html).
2. **Verify on a host — minutes.** Use a real `git clone` (ZIP/source exports are
   unsupported), then run `bash tools/reproduce/reproduce.sh`. Development-only
   overrides are documented in [`tools/reproduce/README.md`](tools/reproduce/README.md).
3. **Repeat on a board — hours.** Run
   `bash tools/reproduce/reproduce.sh board --ip <addr>` only after the prerequisites
   below and the [L2 guide](docs/demo_reproduction_guide_20260901.md#l2-prerequisites)
   are satisfied.

### L2 prerequisites

- RPI4 with intentionally public
  `BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`;
- exact `glibc-2.40-1.6.armv7l`, SDB 4.2.25 reference, and the three-part identity gate;
- remote `id -u=0`, writable four-core governor controls, and writable `/opt/usr`;
- the SHA-pinned ARM/media bundle described by
  [`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json); the
  deliverer supplies the media acquisition location with the delivery email, and
  the recipient verifies it against the manifest SHA-256.

Without that internal bundle, board mode cannot start. The media asset has no
established redistributable provenance and is delivered outside this repository.

### Preferred HQ GBS build (held-out 4/4 passed)

For the three ELF files, GBS can be evaluated from a real `git clone` with
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`. This explicit path requires repository
network access, a root-capable GBS environment, buildroot disk space, and more than
the minutes-scale host verify. The pinned [`gbs_llvm.conf`](config/gbs_llvm.conf) and
[`glibc-memopt-tools.spec`](packaging/glibc-memopt-tools.spec) build one RPM containing
`alloc_bench`, `gst_loop_decode`, and `reclaim_probe`; verify its NVR and all hashes
against [`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json).
The exact extraction commands are in the
[L2 GBS section](docs/demo_reproduction_guide_20260901.md#l2-gbs-build). The
[tool provenance audit](docs/tool_provenance_20260903.md) records the zero result
from package-name, Provides, and file-list searches across all four configured
official repositories and independently resolves every spec BuildRequires.

The GBS artifacts participated in the fixed-contract H-V calibration sample, so
that sample alone does not independently validate GBS. A separately tagged
GBS-only held-out contract, excluded from band construction, then passed 4/4;
GBS is now the default L2 path and frozen/fixed-directory builds are alternatives.
GBS does not provide the media file, which remains an out-of-repository delivery
prerequisite. See the
[held-out report](docs/gbs_heldout_validation_20260904.md) and
[`decision.json`](data/raw/gbs_heldout_validation_20260904/decision.json).

## Repository map

- [`docs/`](docs/) contains reports and guides. The technical body is Chinese; the
  [HQ reproduction guide](docs/demo_reproduction_guide_20260901.md) is authoritative.
- [`tools/`](tools/) contains harnesses, analyzers, the workflow, and report builder.
- [`data/raw/`](data/raw/) contains public compact evidence.
- `board_results/` is not published. Full raw artifacts remain local and are
  available on request through the project owner.

## Environment and acceptance

[`acceptance_bands.json`](tools/reproduce/acceptance_bands.json) is the single
machine-readable contract. The only deterministic numeric item is released-payload
bytes. Validity gates require 4 KiB reclaim alignment, `majflt=0`, zero deltas for
three zram counters, and zero dmesg OOM/LMK matches. Tolerance items include S4 B
three-repeat medians anchored at mixed `81.661264% ±5 pp` and medium-only
`84.446566% ±5 pp`; `n=3` tolerates one outlier, not two. Release-point trim in S4 B
and gst is a single call `<5 ms`; the S4 A anchor has a separate `<20 ms` bound and
is not a hook-cost number.

The current A-anchor calibration bands are shared by frozen and GBS: mixed
`52.794499% ±4.304705 pp` and medium-only `50.669791% ±4.918088 pp`, each from
eight combined observations. They remain calibration limits because GBS observations
helped construct them. Independent evidence comes from the later, excluded four-cell
held-out run, which passed 4/4 without changing the bands. The fixed-contract H-V replay
replaces the former `n=1` limitation while retaining the original single observations
as historical evidence.

Thus “the same data” means exact deterministic payload bytes, tolerance items in
band, and all validity gates passing. A fixed seed does not pin arena assignment;
one repeat may move by about 1 MiB, so reclaim bytes are banded, not deterministic.

The stability v2 known-alert waiver covers at most two registered S4 A
`alloc_bench cpu.relative` livedumps. A matching observation is `EXPECTED` only
after record/archive/exact cleanup/recheck; no observation is
`REGISTERED/NOT-EVALUATED`. The trigger and window are reproducible, but root cause
is not proven.

## Four product enablement gates

Product enablement must pass four hard gates in order: **exclude the automatic-reclaim
anti-signal → confirm M7 retention → show that a same-target, same-phase trim probe
meets its precommitted reclaim threshold → pass the cost budget**. Register the
target/phase threshold before seeing results; no measurement, a below-threshold result,
or unstable repeats keeps the feature off. M7, `rest`/`unsorted`, and histogram estimates
cannot replace gate three. See the dated finalization and preserved older wording in the
[landing recommendation](docs/product_landing_recommendation_20260901.md#1-启用门清单).

## Boundaries and glossary

- Synthetic evidence lacks product-candidate M7 live/bin separation, product
  latency, and direct all-arena lock-stall measurement while peers allocate.
- gst trim runs after NULL; it is not injected into a hot allocation phase.
- B2 completed a fixed-contract official-gst `5/5` replay and a five-cycle
  native-UI activity E4′ cell; its four injection intervals are
  `120.122271759–120.142672892 s`. Historical T1 `1/5`, UI `0/1`, and the old
  `119.806876910/119.856460299 s` E1–E3 deviations remain on record and are not
  retroactively passed.
- M7 retention is not reclaim capacity. The `<size>` estimator missed all `15/15`
  paired validation cells and estimated `2200–7976 KiB` for the `36 KiB` E4′
  reclaim. It is diagnostic only, not a quantitative enablement threshold; see
  the [estimator report](docs/trimmable_estimator_20260905.md).
- The enlightenment daemon had about `5.84 MiB rest`, but its historical cells reclaimed
  only `272/4/4 KiB`, and E4′ after real UI activity reclaimed only `36 KiB`. Fragmented
  retention had little measured benefit in these cells; this does not extrapolate to
  other daemons or phases.
- “p99 cost not detected” does not mean zero cost. If another board reports visible,
  preserve all repeats and report its margin; direction remains `REPORT_ONLY`.
- Product enablement remains closed pending anti-signal exclusion, M7 retention
  confirmation, a same-target measured benefit above its precommitted threshold, and
  a cost budget: four hard gates. See the
  [landing recommendation](docs/product_landing_recommendation_20260901.md#1-启用门清单).
- **Retained floor:** Private_Dirty that stays elevated after a release observation;
  smaps alone cannot prove whether it is live or allocator-held.
- **Nearest-rank:** sort `n` samples and select rank `ceil(p×n)`; with 50 gst primary
  samples, p99 is the observed maximum.

Host-side paths are sanitized; board runtime paths are retained. This `demo` branch
is frozen: corrections land on `main`, then a new snapshot/tag is cut.
