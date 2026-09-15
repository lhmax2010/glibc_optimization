# Accepted 18 + 3 observations, with separately closed cleanup

[composition.json](composition.json) binds the two original STOP receipts,
verified per-cell pull manifests and the new cleanup proof. It does not rewrite
history or claim one uninterrupted execution. All 21 accepted cells are retained;
none were rerun. Original contract/analyzer bytes remain unchanged.

[point_source.json](point_source.json) and [gst_cycles.tsv](gst_cycles.tsv) are
public parsed transcriptions. The original raw archives were fully rechecked
before composition; full originals stay local and are available on request.
[manifest.json](manifest.json) binds the composed files. README is explanatory,
not a measurement input. [L1 instructions](../../../../docs/demo_reproduction_guide_20260901.md#l1-system-before-after).

The fixed analyzer regenerates five byte-identical derived files. Summary uses
cycle 1 and three repeats; pre/post/drop each have their own median. MiB = KiB/1024;
the legacy `memavailable_*_mb` fields are decimal MB (divide by 1.048576 for MiB).
G1 system net is negative. None zero refers to RSS decrease, not MemAvailable.
G4 has no none arm and no next-cycle metric; its idle faults and gdb/ptrace timing
are independent. Nonempty GDB directories remain REPORT_ONLY, not "all removed".

## Display-scope correction (2026-09-15; N12-01/02, V12-5)

G3's headline is cycle 1. The 51-cycle, three-repeat pool (153 points) has RSS-drop
median 16.038164%, range 13.282648–21.043165%; it is not a median of cycle medians.
Business-cost `primary_cycles="2-51"` excludes cycle 1. Neither input nor frozen
derivation has changed. See the [corrected report](../../../../docs/system_level_before_after_20260908.md#13-已验收矩阵合成与优化效果).

In [gst_arms.tsv](gst_arms.tsv), `trim_max_ms_across_repeats` means the **median of
the per-repeat maxima**, not the maximum of the combined pool. Its trim value
1.097408 ms is the median of 1.376555 / 1.097408 / 0.972963 ms in
[gst_repetitions.tsv](gst_repetitions.tsv); the true pooled maximum is 1.376555 ms
from [gst_cycles.tsv](gst_cycles.tsv). The misleading legacy header is retained
to preserve frozen byte-for-byte replay; this note is its explicit schema gloss.
