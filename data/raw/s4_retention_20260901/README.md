# S4 compact evidence (2026-09-01)

Sanitized, derived evidence for
[`docs/s4_reference_and_retention_trim_20260901.md`](../../../docs/s4_reference_and_retention_trim_20260901.md).
The complete 200-file board pull, per-file manifest, XML, JSON, dmesg and 1 s
series remain in the private local `board_results/` archive.

- `a_cells.tsv`: two new-image instantaneous-release anchors.
- `b_cells.tsv`: one row per frozen B grid cell (two-cycle medians).
- `b_cycles.tsv`: exact per-cycle trim/M7/fault metrics.
- `external_summary.tsv`: completeness and faults summary for every 1 s series.
- `health.json`: dmesg, zram and governor verdict.
- `preflight_and_integrity.txt`: sanitized identity, asset and pull/cleanup gates.

Regenerate the derived tables from the private pull with
`tools/runners/s4_retention_20260901/analyze_s4.py`.
