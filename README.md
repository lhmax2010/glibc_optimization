[中文](README.zh-CN.md) | English

# Tizen glibc gated-trim Demo

> This English entry is derived from the Chinese technical documentation. If
> wording is ambiguous, the Chinese technical documents are authoritative.

## What this is

This is the frozen Demo delivery for a Tizen glibc (ptmalloc) memory
optimization: treat visible automatic reclaim as an anti-signal, confirm
allocator-held free space with M7, then call `malloc_trim(0)` only at a known
release phase and accept it together with reclaim, refault, latency, and health
evidence. On the frozen RPI4/Tizen glibc 2.40 matrix, the mechanism anchors are
about 50%, gated trim reclaimed about 80%–85% of released payload for about
1.2 ms median, and the GStreamer business-p99 gate did not detect a visible
cost. These are mechanism and scale results, not a product-memory promise.

## Headline results

| Comparison | Frozen result | Report | Compact evidence |
|---|---|---|---|
| New-image instant-release anchors | mixed `51.07%`; medium-only `50.39%` | [HTML summary](docs/demo_report.html#summary) | [`a_cells.tsv`](data/raw/s4_retention_20260901/a_cells.tsv) |
| Gated valley trim vs none | `80.18%–85.45%` of released payload; about `1.2 ms` median; next-cycle `+1351/+1465 minflt`, `majflt=0` | [S4 effect](docs/demo_report.html#s4) | [`b_cycles.tsv`](data/raw/s4_retention_20260901/b_cycles.tsv), [`b_cells.tsv`](data/raw/s4_retention_20260901/b_cells.tsv) |
| GStreamer trim vs none | repeat-median p99 `+6.229 ms`, below the `6.784 ms` none-repeat dispersion; not visible by the preregistered gate | [Real concurrency](docs/demo_report.html#gst) | [`comparison.json`](data/raw/gst_trim_cost_20260901/comparison.json), [`cycles.tsv`](data/raw/gst_trim_cost_20260901/cycles.tsv) |

## Three ways to start

1. **Read offline — minutes.** Open
   [`docs/demo_report.html`](docs/demo_report.html). It is one self-contained
   file with evidence-built inline SVG charts, no CDN and no external images.
2. **Verify on a host — minutes.** From the repository root run:

   ```sh
   bash tools/reproduce/reproduce.sh
   ```

   The default `verify` mode runs every public L1 recalculation and byte
   comparison, rebuilds the HTML, checks links, and exits nonzero on any failure.
3. **Repeat on a board — hours.** Prepare an RPI4 with
   `BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`, glibc
   2.40, SDB, and the SHA-pinned internal ARM/media bundle, then run:

   ```sh
   bash tools/reproduce/reproduce.sh board --ip <addr>
   ```

   Read the [L2 guide and prerequisites](docs/demo_reproduction_guide_20260901.md#l2-prerequisites)
   before the run. Board identity is established by the three-part gate, never by
   the address.

## Repository map

- [`docs/`](docs/) contains the reports and guides. The technical body is in
  Chinese; the [HQ reproduction guide](docs/demo_reproduction_guide_20260901.md)
  is the authoritative process reference.
- [`tools/`](tools/) contains benchmark harnesses, analyzers, the report builder,
  and the one-command workflow.
- [`data/raw/`](data/raw/) contains the sanitized compact evidence required to
  reproduce every public Demo number.
- `board_results/` is deliberately not published. Full raw board artifacts are
  retained locally and can be provided on request through the project owner.

## Environment and acceptance

The single machine-readable contract is
[`acceptance_bands.json`](tools/reproduce/acceptance_bands.json). Deterministic
items are frozen payload bytes, 4 KiB reclaim alignment, `majflt=0`, zero deltas
for the three zram counters, and zero dmesg OOM/LMK matches. Cross-run quantities
use preregistered tolerance bands: S4 B is evaluated as the per-profile median of
three repetitions (`80% ±5 pp`), release-point trim in S4 B and GStreamer is
`<5 ms`, and the S4 A anchor has a separate `<20 ms` limit that is not a hook-cost
number.

Stability-monitor v2 has one expected-alert registration: at most two S4 A
`alloc_bench` `cpu.relative` livedumps. A match is `EXPECTED`, not ignored: it
must be recorded, archived, removed by exact path, and rechecked. Unregistered
attributable alerts still fail.

## Boundaries

- The synthetic proxy does not provide product-candidate M7 live/bin separation,
  product-side business latency, or a direct all-arena lock-stall distribution
  while other threads allocate.
- GStreamer trim is triggered after the pipeline reaches NULL. It measures the
  release point and next-loop effect, not a trim injected into a hot allocation
  phase.
- “p99 cost not detected” does **not** mean zero cost; it means the frozen
  three-repeat result did not cross the preregistered none-repeat dispersion gate.
- A fixed seed does not pin arena assignment. A single repetition can move by an
  approximately 1 MiB page step, so reclaim bytes are not deterministic; the
  protocol uses the three-repeat median.
- Product enablement remains closed until all three hard gates pass: automatic-
  reclaim anti-signal exclusion, M7 retention confirmation, and a cost budget.
  See the [product landing recommendation](docs/product_landing_recommendation_20260901.md#1-启用门清单).

This `demo` branch is a frozen snapshot. Corrections land on `main` first; a new
snapshot is then cut with the next `demo-vN` tag. Do not develop directly here.
