# glibc Memory Optimization for Tizen

This repository is the long-term, sanitized workspace for source audits, controlled benchmarks, board measurements, and implementation evidence related to reducing glibc runtime memory and image footprint on 32-bit ARM Tizen systems.

文中应用/进程名为代号，板标识与路径已脱敏。报告引用的大块原始证据（完整 dlog、dmesg、smaps 快照和 malloc_info XML 全集）保留在本地；直接支撑结论的小型时间序列和执行记录收录在 `data/raw/`。

**Current stage:** source and mechanism audit is complete, Batch 1/2/2.5 and the L6 applicability curve are measured, product-process allocation shapes are profiled read-only, and the cyclic trim-timing benchmark is implemented. The RPI4 SDB channel and new-image baseline are restored. The product cyclic PD fall is now classified as an automatic-reclaim anti-signal, the original S3 semantic is retired, and S4 has closed the gated-trim effect/cost baseline on the synthetic retention proxy. See the [consolidated status](docs/glibc_memopt_program_status_report_zh.md) and [Demo narrative](docs/demo_narrative_20260901.md).

## Current Findings

- **Surviving runtime levers:** L1 reduces the pthread stack cache; L3 pins malloc mmap/trim thresholds; L2 caps arenas only when the measured thread-to-arena ratio leaves sufficient headroom. The validated L1+L3 combination measured `+0.1%` throughput and `-2.43 MB` memory in its tested workload.
- **Phase-triggered reclaim (L6):** `malloc_trim(0)` is useful when the process's own glibc heap experiences bulk allocation followed by concentrated frees. Controlled media release phases reclaimed `48.52-49.37%`, totaling `10.902 MiB` across eight processes.
- **Applicability curve:** at the measured 50% release point, reclaim was `27.91%` for 16-256 B objects, `53.55%` for mixed 16 B-64 KiB objects, and `50.60%` for medium 1-16 KiB objects. Interleaved release reduced the mixed case from `53.55%` to `40.58%`.
- **Product allocation shapes:** the cyclic target's visible PD fall is an automatic-reclaim anti-signal rather than a trim opportunity; retained floors and residuals remain candidates only until M7 separates live data from allocator-held free space. See the [mechanism attribution](docs/cyclic_fall_mechanism_attribution_v2_20260901.md).
- **S2 replication gate:** frozen mixed and medium-only runs paced rise/release at about `3.400/19.703 s` and placed about `6.4 MiB` per cycle into rest/unsorted, but neither internal nor external board sampling showed a PD fall. The proxy therefore does not yet reproduce the product cyclic shape.
- **Rejected or deferred directions:** mechanisms with no RSS surface include rseq disablement, guard-page removal, repeated `__libc_freeres`, and disabling dlconf for steady-state RSS. Disabling tcache, disabling fastbins, and limiting unsorted-to-tcache transfers remain experimentally rejected unless real workloads show materially larger retained structures. A whole-libc `-Os` build remains deferred pending a dedicated performance and build-compatibility program.
- **Flash levers:** locale/gconv/NSS packaging, debug-symbol policy, cold-DSO optimization, and command-line subpackaging remain source-verified candidates whose product savings depend on the final image manifest.

The figures above are measurements for the documented builds and workloads, not universal glibc guarantees. See the individual reports for version gates, workload definitions, and limitations.

## Recommended Reading Order

1. [Program status and consolidated evidence](docs/glibc_memopt_program_status_report_zh.md)
2. [Source feasibility audit](docs/glibc_memopt_feasibility_report.md)
3. [Design v2.4](docs/tizen_glibc_memopt_design_v2.md) and [Chinese edition](docs/tizen_glibc_memopt_design_v2_zh.md)
4. [L6 applicability curve](docs/l6_applicability_curve.md)
5. [Product plateau profile](docs/product_plateau_probe.md) and [cyclic-target profile](docs/product_cyclic_target_probe.md)
6. [Controlled cyclic replication status](docs/cyclic_profile_replication.md)
7. [Complete chronological document index](docs/INDEX.md)

The design and audit establish version-gated mechanisms. The curve report quantifies controlled behavior. Product reports show which allocation shapes occur in real processes. Individual Batch and probe reports retain commands, quality gates, failure records, and measurement limitations.

## Directory Guide

- [`docs/`](docs/) contains designs, specifications, reviews, arbitration, board reconnaissance, experiment reports, and the chronological index.
- [`tools/`](tools/) contains measurement source, self-tests, collectors, and sanitized experiment runners.
- [`patches/`](patches/) contains local build-only patches retained as reproducibility evidence; none are implied to be product changes.
- [`data/derived/`](data/derived/) contains matrix definitions, histograms, and compact derived result tables.
- [`data/raw/`](data/raw/) contains selected command records, key timelines, and small directly cited time series. Complete raw evidence remains in the private local archive.
- `temp/` is the ignored local work area for build roots, migration audits, and large evidence.

## Tools

- [`tools/alloc_bench/`](tools/alloc_bench/) contains the deterministic allocation microbenchmark and self-tests.
- [`tools/reclaim_probe/`](tools/reclaim_probe/) profiles mapping classes and probes page-level reclaim where supported.
- [`tools/gst_loop_decode/`](tools/gst_loop_decode/) constructs a persistent media decode/release phase.
- [`tools/inventory/`](tools/inventory/) contains the read-only process inventory collector.
- [`tools/runners/`](tools/runners/) contains sanitized collection and analysis runners used by the reports.

Only source and scripts are published. ARM and host binaries are intentionally excluded because they are reproducible and may retain local build paths in string tables.

## Data

[`data/derived/`](data/derived/) contains matrix definitions, histograms, and compact derived TSV summaries. [`data/raw/`](data/raw/) is deliberately limited to small evidence required to reproduce report calculations; bulk captures are excluded for size and privacy reasons.

## Archive Notes

The reports retain source `file:line` anchors, measured values, workload parameters, and failure records. Identity-bearing board addresses, image identifiers, application/process names, local paths, users, and repository endpoints have been replaced consistently with aliases. The private replacement map is ignored by Git and is not published.
