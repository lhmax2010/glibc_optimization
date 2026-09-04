[中文](README.zh-CN.md) | English

# Tizen glibc gated-trim Demo

> This English entry is derived from the Chinese technical documentation. If
> wording is ambiguous, the Chinese technical documents are authoritative.

## What this is

This frozen Demo delivers a gated Tizen glibc (ptmalloc) trim method: exclude
visible automatic reclaim as an anti-signal, confirm allocator-retained free space
with M7, then call `malloc_trim(0)` only at a known release phase while accepting
reclaim, refault, latency, and health evidence together. On the frozen RPI4/Tizen
glibc-2.40-1.6.armv7l matrix, anchors were about 50%, gated trim reclaimed about
80%–85% of released payload; per-profile median calls were mixed 1.233269 ms and
medium-only 1.218361 ms, and the gst p99
direction was not visible by the preregistered rule. These are mechanism and scale
results, not a product-memory-benefit promise.

## Headline results

| Comparison | Accepted result | Report | Compact evidence |
|---|---|---|---|
| Instant-release anchors | mixed `52.794499% ±4.304705 pp`, medium-only `50.669791% ±4.918088 pp`; each combines `n=8`, denominator is pre-trim heap | [HTML summary](docs/demo_report.html#summary) | [`decision.json`](data/raw/a_anchor_replication_20260904/decision.json), [`a_cells.tsv`](data/raw/a_anchor_replication_20260904/a_cells.tsv) |
| Gated valley trim vs none | `80.18%–85.45%` of released payload; median call mixed `1.233269 ms` / medium-only `1.218361 ms`; next-cycle `+1351/+1465 minflt`, `majflt=0` | [S4 effect](docs/demo_report.html#s4) | [`b_cycles.tsv`](data/raw/s4_retention_20260901/b_cycles.tsv), [`b_cells.tsv`](data/raw/s4_retention_20260901/b_cells.tsv) |
| gst trim vs none | p99 `+6.228611 ms` vs none dispersion `6.784167 ms`: margin `0.555556 ms`, 91.8% of threshold, `REPORT_ONLY` not visible; the same p50 rule is visible (`+1.870462` vs `0.173927 ms`); `+359 minflt/cycle` | [Real concurrency](docs/demo_report.html#gst) | [`comparison.json`](data/raw/gst_trim_cost_20260901/comparison.json), [`cycles.tsv`](data/raw/gst_trim_cost_20260901/cycles.tsv) |
| Tizen native cross-witness | enlightenment M7 showed about `5.84 MiB` rest; project heap PD and Tizen `memps` both observed `272/4/4 KiB` reclaim. Completion limits: gst `1/5`, UI release-phase `0/1`, and two intervals just below 120 s | [Native process evidence](docs/demo_report.html#native) | [`cells_derived.tsv`](data/raw/tizen_native_evidence_20260904/cells_derived.tsv), [`summary.json`](data/raw/tizen_native_evidence_20260904/summary.json) |

The batch release reference `48.9% / 1.36 MiB × 8 processes` comes from
`<TEST_IMAGE_B>` / `glibc-2.40-2.8`; it is a compatibility comparison, not part of
the frozen matrix ([evidence](data/raw/demo_reproduction_20260901/batch_release_phase.tsv)).

## Three ways to start

1. **Read offline — minutes.** Open [`docs/demo_report.html`](docs/demo_report.html).
2. **Verify on a host — minutes.** Use a real `git clone` (ZIP/source exports are
   unsupported), then run `bash tools/reproduce/reproduce.sh`. Development-only
   overrides are documented in [`tools/reproduce/README.md`](tools/reproduce/README.md).
3. **Repeat on a board — hours.** Run
   `bash tools/reproduce/reproduce.sh board --artifact-source gbs --ip <addr>` only after the prerequisites
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

### Preferred HQ GBS build

For the three ELF files, the preferred HQ path is a real `git clone` followed by
`gbs -c config/gbs_llvm.conf build -A armv7l --overwrite`. The pinned config and
[`glibc-memopt-tools.spec`](packaging/glibc-memopt-tools.spec) build one RPM containing
`alloc_bench`, `gst_loop_decode`, and `reclaim_probe`; verify its NVR and all hashes
against [`deliverables_manifest.json`](tools/reproduce/deliverables_manifest.json).
The exact extraction commands are in the
[L2 GBS section](docs/demo_reproduction_guide_20260901.md#l2-gbs-build). The
[tool provenance audit](docs/tool_provenance_20260903.md) records the zero result
from package-name, Provides, and file-list searches across all four configured
official repositories and independently resolves every spec BuildRequires.

The GBS artifacts passed the preregistered A-anchor board rebaseline through the
H-V decision. GBS is now the preferred HQ L2 path; the frozen artifacts and
fixed-directory cross-build are fallbacks. GBS does not provide the media file,
which remains an out-of-repository delivery prerequisite. See the
[A-anchor replication](docs/a_anchor_replication_20260904.md).

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

The current A-anchor bands are shared by frozen and GBS: mixed
`52.794499% ±4.304705 pp` and medium-only `50.669791% ±4.918088 pp`, each from
eight combined observations. The preregistered H-V result replaces the former
current `n=1` limitation while retaining the original single observations as
historical evidence.

Thus “the same data” means exact deterministic payload bytes, tolerance items in
band, and all validity gates passing. A fixed seed does not pin arena assignment;
one repeat may move by about 1 MiB, so reclaim bytes are banded, not deterministic.

The stability v2 known-alert waiver covers at most two registered S4 A
`alloc_bench cpu.relative` livedumps. A matching observation is `EXPECTED` only
after record/archive/exact cleanup/recheck; no observation is
`REGISTERED/NOT-EVALUATED`. The trigger and window are reproducible, but root cause
is not proven.

## Boundaries and glossary

- Synthetic evidence lacks product-candidate M7 live/bin separation, product
  latency, and direct all-arena lock-stall measurement while peers allocate.
- gst trim runs after NULL; it is not injected into a hot allocation phase.
- The Tizen-native matrix is not a full success: only one of five gst cells and
  none of the UI release-phase cell completed, while the three enlightenment
  observations have two `119.806876910/119.856460299 s` intervals below the
  preregistered 120 seconds. Cite only the completed measurements.
- “p99 cost not detected” does not mean zero cost. If another board reports visible,
  preserve all repeats and report its margin; direction remains `REPORT_ONLY`.
- Product enablement remains closed pending anti-signal exclusion, M7 retention
  confirmation, and a cost budget. See the
  [landing recommendation](docs/product_landing_recommendation_20260901.md#1-启用门清单).
- **Retained floor:** Private_Dirty that stays elevated after a release observation;
  smaps alone cannot prove whether it is live or allocator-held.
- **Nearest-rank:** sort `n` samples and select rank `ceil(p×n)`; with 50 gst primary
  samples, p99 is the observed maximum.

Host-side paths are sanitized; board runtime paths are retained. This `demo` branch
is frozen: corrections land on `main`, then a new snapshot/tag is cut.
