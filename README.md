# glibc Memory Optimization for Tizen

This repository is a sanitized archive of a source audit, controlled benchmarks, and board measurements for reducing glibc-related runtime memory and image footprint on 32-bit ARM Tizen systems.

文中应用/进程名为代号，板标识已脱敏。报告引用的大块原始证据（dlog、dmesg、smaps、malloc_info XML 和逐轮快照）保留在本地，不在公开仓库发布。

## Current Findings

- **Surviving runtime levers:** L1 reduces the pthread stack cache; L3 pins malloc mmap/trim thresholds; L2 caps arenas only when the measured thread-to-arena ratio leaves sufficient headroom. The validated L1+L3 combination measured `+0.1%` throughput and `-2.43 MB` memory in its tested workload.
- **Phase-triggered reclaim (L6):** `malloc_trim(0)` is useful when the process's own glibc heap experiences bulk allocation followed by concentrated frees. Controlled media release phases reclaimed `48.52-49.37%`, totaling `10.902 MiB` across eight processes.
- **Applicability curve:** at the measured 50% release point, reclaim was `27.91%` for 16-256 B objects, `53.55%` for mixed 16 B-64 KiB objects, and `50.60%` for medium 1-16 KiB objects. Interleaved release reduced the mixed case from `53.55%` to `40.58%`.
- **Rejected or deferred directions:** mechanisms with no RSS surface include rseq disablement, guard-page removal, repeated `__libc_freeres`, and disabling dlconf for steady-state RSS. Disabling tcache, disabling fastbins, and limiting unsorted-to-tcache transfers remain experimentally rejected unless real workloads show materially larger retained structures. A whole-libc `-Os` build remains deferred pending a dedicated performance and build-compatibility program.
- **Flash levers:** locale/gconv/NSS packaging, debug-symbol policy, cold-DSO optimization, and command-line subpackaging remain source-verified candidates whose product savings depend on the final image manifest.

The figures above are measurements for the documented builds and workloads, not universal glibc guarantees. See the individual reports for version gates, workload definitions, and limitations.

## Documentation

- [Program status and consolidated evidence](docs/glibc_memopt_program_status_report_zh.md)
- [Source feasibility audit](docs/glibc_memopt_feasibility_report.md)
- [Design v2](docs/tizen_glibc_memopt_design_v2.md) and [Chinese edition](docs/tizen_glibc_memopt_design_v2_zh.md)
- [Review arbitration](docs/v22_review_arbitration_zh.md)
- [L6 applicability curve](docs/l6_applicability_curve.md)
- [L6 release-phase scale test](docs/l6_release_phase_scale.md)
- [Real UI release-phase probe](docs/l6_ui_release_phase.md)
- [Product cyclic-target peak/valley probe](docs/product_cyclic_target_probe.md)
- [Allocator benchmark specification](docs/alloc_bench_spec_v1_1a_zh.md)
- [Board and protocol reports](docs/)

## Tools

- [`tools/alloc_bench/`](tools/alloc_bench/) contains the deterministic allocation microbenchmark and self-tests.
- [`tools/reclaim_probe/`](tools/reclaim_probe/) profiles mapping classes and probes page-level reclaim where supported.
- [`tools/gst_loop_decode/`](tools/gst_loop_decode/) constructs a persistent media decode/release phase.
- [`tools/inventory/`](tools/inventory/) contains the read-only process inventory collector.
- [`tools/runners/`](tools/runners/) contains sanitized collection and analysis runners used by the reports.

Only source and scripts are published. ARM and host binaries are intentionally excluded because their string tables contained local build paths.

## Data

[`data/derived/`](data/derived/) contains matrix definitions, histograms, and compact derived TSV summaries. Raw board captures are excluded for size and privacy reasons.

## Archive Notes

The reports retain source `file:line` anchors, measured values, workload parameters, and failure records. Identity-bearing board addresses, image identifiers, application/process names, local paths, users, and repository endpoints have been replaced consistently with aliases. The private replacement map is ignored by Git and is not published.
