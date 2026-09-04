# HQ one-command reproduction

```sh
bash tools/reproduce/reproduce.sh
bash tools/reproduce/reproduce.sh verify
bash tools/reproduce/reproduce.sh board --artifact-source gbs --ip <address>
```

`verify` is the default, is host-only, and finishes in minutes. It must run from a
real `git clone`; GitHub ZIP/source exports are unsupported because delivery
identity is part of the contract. It runs every L1 recalculation, byte comparison,
v4 acceptance check, local-link check, report rebuild, and host test. Any failed
row makes the process exit nonzero.

Development-only overrides are explicit: `REPRODUCE_ALLOW_DIRTY=1` permits a dirty
tree, `REPRODUCE_SKIP_TESTS=1` skips the nested host-test row, and
`REPRODUCE_EXPECTED_SHA=<commit-or-ref>` overrides the recorded delivery reference.
Without an override, `verify` requires `HEAD` to resolve to the delivery ref in
[`delivery_refs.json`](delivery_refs.json).

`board` is an hours-scale workflow. It requires an RPI4 running the frozen Tizen
Unified image, SDB, and the internal SHA-256-pinned ARM/media bundle described in
the [deliverables manifest](deliverables_manifest.json) and
[HQ guide](../../docs/demo_reproduction_guide_20260901.md#l2-prerequisites).
It orchestrates the existing S4 and gst runners; it does not copy their workload
or statistical logic. Set `DEMO_ARTIFACT_DIR` or pass `--artifact-dir` for the
bundle. Results default to a new `board_results/demo_workflow_<UTC timestamp>`
directory.

For the fallback fixed-directory cross-build, set both
`DEMO_TOOLCHAIN_ROOT=/path/to/scratch.armv7l.0` and
`DEMO_GST_SYSROOT=/path/to/gstreamer/scratch.armv7l.0`. The first supplies the
ARM compiler/sysroot used by `alloc_bench` and `reclaim_probe`; the second must
contain the GStreamer/GLib ARM headers, pkg-config metadata, and link libraries for
`gst_loop_decode`. `check_reproducible_build_paths.py` builds from two different
checkout paths and compares all three hashes; if either variable is absent it
prints an explicit `SKIPPED` row.

The preferred HQ build is now
`gbs -c config/gbs_llvm.conf build -A armv7l --overwrite`, which uses
[`packaging/glibc-memopt-tools.spec`](../../packaging/glibc-memopt-tools.spec) and
produces one RPM with all three ELF files. `check_gbs_package.py` always validates
spec syntax/`%files` and runs GBS when available. The artifacts passed the
preregistered A-anchor board rebaseline through H-V; GBS is now the L2 default and
the frozen bundle is the fallback. Select the GBS hashes with
`--artifact-source gbs`. The media file is never built by either path and must come
from the delivery location supplied with the package.

Both modes read [`acceptance_bands.json`](acceptance_bands.json). `PASS` means a
deterministic item, validity gate, or tolerance band passed. `EXPECTED` means an
observed preregistered stability-monitor alert matched its waiver and was archived,
cleaned, and rechecked; an unobserved registration is
`REGISTERED/NOT-EVALUATED`. The gst p99 direction and foreign/unattributed state are
`REPORT_ONLY`; neither direction can fail acceptance when the preregistered
nearest-rank/dispersion rule was executed correctly. If a board reports
`visible=true`, retain the output and all three repeats, report the margin over the
none-arm dispersion, do not relabel it as workflow failure, and escalate it as a
batch-specific business-cost finding.

Acceptance v4 uses the preregistered H-V A-anchor result shared by frozen and GBS:
mixed `52.794499% ±4.304705 pp` and medium-only
`50.669791% ±4.918088 pp`, each from eight combined observations. The derivation
and public replay are in the
[A-anchor report](../../docs/a_anchor_replication_20260904.md).

The board preflight hard-gates remote `id -u=0`, writability of all four governor
controls, and writability of `/opt/usr`. Without the internal bundle described by
the manifest, board mode cannot start. Manual commands and evidence interpretation
remain governed by the [HQ reproduction guide](../../docs/demo_reproduction_guide_20260901.md).

> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.
