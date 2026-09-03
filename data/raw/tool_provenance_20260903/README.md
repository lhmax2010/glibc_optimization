# Tool provenance compact evidence (2026-09-03)

This directory is the deterministic output of
[`audit_tool_provenance.py`](../../../tools/runners/tool_provenance_20260903/audit_tool_provenance.py)
against every repository URL in [`gbs_llvm.conf`](../../../config/gbs_llvm.conf)
and [`gbs.conf`](../../../config/gbs.conf).

- `repos.tsv` records each `repomd.xml` revision/hash, referenced primary and
  filelists hashes, package count, and tool-hit count.
- `tool_hits.tsv` is intentionally header-only: package-name, Provides, and full
  file-path searches produced zero hits for all three tool-name families.
- `buildrequires.tsv` records every armv7l match or absence for every spec
  `BuildRequires` in every repository.
- `summary.json` records the normalized matching rule and stop-gate outcome.

The two `reference` URLs are moving pointers. Their rows preserve the revision and
checksums observed by this audit; the immutable Toolchain snapshot rows are the
reproduction baseline.
