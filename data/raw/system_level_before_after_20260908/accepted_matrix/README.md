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
