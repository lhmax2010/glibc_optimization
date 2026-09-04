# HQ one-command reproduction

```sh
bash tools/reproduce/reproduce.sh
bash tools/reproduce/reproduce.sh verify
bash tools/reproduce/reproduce.sh gbs
bash tools/reproduce/reproduce.sh board --ip <address>
```

`verify` is the default, is host-only, and finishes in minutes. It must run from a
real `git clone`; GitHub ZIP/source exports are unsupported because delivery
identity is part of the contract. It runs every L1 recalculation, byte comparison,
v4 acceptance check, local-link check, report rebuild, static GBS package contract,
and host test. It never starts a real GBS build. Any failed row makes the process
exit nonzero.

The default mode has only two separately installed system prerequisites: **Git and
Python 3**. The `bash` entrypoint and ordinary base-image shell utilities
(`sh`, `cmp`, `cp`, `dirname`, `find`, `grep`, `ln`, `mkdir`, `mktemp`, `sed`,
and `tr`) are treated as the operating-system userland, not project toolchains.
`gbs`, `rpm`, `rpm2cpio`, `cpio`, `rpmspec`, an ARM compiler, SDB, network access,
and root are not default-verify prerequisites. Optional syntax/build checks emit an
explicit `SKIPPED` reason when their environment is absent; their real execution is
reserved for the explicit `gbs` or `board` mode.

Development-only overrides are explicit: `REPRODUCE_ALLOW_DIRTY=1` permits a dirty
tree, `REPRODUCE_SKIP_TESTS=1` skips the nested host-test row, and
`REPRODUCE_EXPECTED_SHA=<commit-or-ref>` overrides the recorded delivery reference.
Without an override, `verify` requires `HEAD` to resolve to the delivery ref in
[`delivery_refs.json`](delivery_refs.json).

## Mandatory pre-delivery clone matrix

After cutting a frozen snapshot and before declaring it ready, run the remote-only
pre-delivery gate:

```sh
bash tools/reproduce/predelivery_check.sh \
  --repo-url "$(git remote get-url origin)" \
  --branch demo \
  --tag demo-v6
```

The script performs three fresh HQ-shaped clones from the supplied remote:

```sh
git clone --branch demo <url>
git clone --branch demo-v6 <url>
git clone <url>                 # remote default must be main
```

Each clone is verified under four controlled PATH profiles: GBS/RPM both
discoverable, only RPM discoverable, only GBS discoverable, and neither
discoverable (`minimal-git-python`). Discoverable optional tools are deterministic
fail-if-invoked stubs, so this gate proves that default verify does not execute them;
`rpmspec -P` alone uses a local parser fixture because that optional syntax branch is
intentionally exercised. This is `3 × 2 × 2 = 12` complete verifies with nested host
tests enabled. The demo branch and detached tag must pass required delivery identity;
main keeps its recorded `REPORT_ONLY` identity semantics. Every check must print
`host-tests=PASS OVERALL=PASS`, and the final row must be
`OVERALL PASS checks=12`, or the snapshot is not delivery-ready. Future snapshots
pass their new annotated tag with `--tag demo-vN`; the script also defaults that
value from [`delivery_refs.json`](delivery_refs.json).

## Default host-test dependency audit

The current entrypoint executes eleven test files (the ten analysis/report groups
plus the mocked board-workflow group). Their external-command boundary is:

| Test file | Commands beyond Python code | Default-verify treatment |
|---|---|---|
| `tools/runners/s4_retention_20260901/test_host.py` | `python3`, `sh` for a local sampler fixture | Base runtime only; no board command |
| `tools/runners/gst_trim_cost_20260901/test_host.py` | `python3` | Required runtime |
| `tools/runners/a_anchor_replication_20260904/test_host.py` | `python3` | Required runtime |
| `tools/runners/gbs_heldout_validation_20260904/test_host.py` | `python3` | Required runtime |
| `tools/runners/tizen_native_evidence_20260904/test_host.py` | `python3`, `sh -n` | Shell syntax check only; no SDB/gdb |
| `tools/runners/tizen_native_evidence_b2_20260904/test_host.py` | `sh -n` | Shell syntax check only; no SDB/gdb |
| `tools/analysis/test_trimmable_estimator.py` | current Python interpreter | Required runtime |
| `tools/report/test_build_demo_report.py` | `python3`, `git` | Required delivery provenance check |
| `tools/reproduce/test_host.py` | `git`, `python3`, base shell utilities | RPM/GBS paths use self-contained stubs; ARM build check is explicit `SKIPPED` without its environment |
| `tools/reproduce/test_board_workflow_mocked_sdb.py` | `sh`; creates its own `sdb` stub | No real SDB or board connection |
| `tools/runners/tool_provenance_20260903/test_host.py` | `python3`; local XML fixtures | No network or repository download |

The top-level static GBS check parses the spec and manifest in Python. `rpmspec -P`
is optional and reports `SKIPPED` when absent. The path-reproducibility check requires
`DEMO_TOOLCHAIN_ROOT` and `DEMO_GST_SYSROOT`; without both it reports a reasoned
`SKIPPED`. No test may use `assertIsNotNone(shutil.which(...))` to promote an
optional RPM/GBS/ARM command into a default dependency.

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

The explicit GBS build entry is
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`, which uses
[`packaging/glibc-memopt-tools.spec`](../../packaging/glibc-memopt-tools.spec) and
produces one RPM with all three ELF files. It requires network access to the pinned
repositories, a root-capable GBS environment, sufficient buildroot disk space, and
substantially more time than the minutes-scale host verify. Its buildroot is unique
per run and protected by a cross-process lock. A GBS command/environment failure is
`SKIPPED/REPORT_ONLY`; a static contract defect or drift in a successfully produced
RPM/ELF remains a hard failure.

The GBS artifacts participated in the fixed-contract H-V calibration sample, so
that sample alone is not independent evidence. A separately tagged four-cell
GBS-only held-out contract, excluded from band construction, passed 4/4. GBS is now
the L2 default; select the archived fallback explicitly with
`--artifact-source frozen`. The media file is never built by either path and must
come from the delivery location supplied with the package. See the
[held-out report](../../docs/gbs_heldout_validation_20260904.md).

Both modes read [`acceptance_bands.json`](acceptance_bands.json). `PASS` means a
deterministic item, validity gate, or tolerance band passed. `EXPECTED` means an
observed registered stability-monitor alert matched its waiver and was archived,
cleaned, and rechecked; an unobserved registration is
`REGISTERED/NOT-EVALUATED`. The gst p99 direction and foreign/unattributed state are
`REPORT_ONLY`; neither direction can fail acceptance when the fixed-contract
nearest-rank/dispersion rule was executed correctly. If a board reports
`visible=true`, retain the output and all three repeats, report the margin over the
none-arm dispersion, do not relabel it as workflow failure, and escalate it as a
batch-specific business-cost finding.

Acceptance v4 uses the fixed-contract H-V A-anchor calibration shared by frozen and GBS:
mixed `52.794499% ±4.304705 pp` and medium-only
`50.669791% ±4.918088 pp`, each from eight combined observations. The derivation
and public replay are in the
[A-anchor report](../../docs/a_anchor_replication_20260904.md). The values remain
calibration limits; independent GBS status comes from the excluded four-cell
[held-out run](../../docs/gbs_heldout_validation_20260904.md), which passed 4/4
without modifying them.

## Board-round evidence ordering

For every new board round, commit the immutable contract and its analyzer first and
create a lightweight pre-run tag. Only then may the board run start. Board results,
compact evidence, and conclusions land in a separate later commit. Without the
pre-run commit/tag, historical wording is “fixed-contract replay”, not
“preregistered”.

The board preflight hard-gates remote `id -u=0`, writability of all four governor
controls, and writability of `/opt/usr`. Without the internal bundle described by
the manifest, board mode cannot start. Manual commands and evidence interpretation
remain governed by the [HQ reproduction guide](../../docs/demo_reproduction_guide_20260901.md).

> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.
