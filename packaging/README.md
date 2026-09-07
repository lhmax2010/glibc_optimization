# GBS package for the Demo harnesses

`glibc-memopt-tools.spec` builds one `glibc-memopt-tools-1.0.0-1.armv7l` RPM
containing these three executables:

- `/usr/bin/alloc_bench`
- `/usr/bin/gst_loop_decode`
- `/usr/bin/reclaim_probe`

The frozen LLVM-image build uses the immutable repositories in
[`config/gbs_llvm.conf`](../config/gbs_llvm.conf): Unified Toolchain
`20260814.092727` and the Base Toolchain `20260813.050338` named by that Unified
snapshot's build metadata. From a clean, committed Git clone, the only operational
build entry is:

```sh
bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle
```

The repository is the GBS source tree; no Gerrit import or separate source archive
is required. The resulting RPM identity, RPM SHA-256, buildroot versions, and ELF
SHA-256 values are recorded in
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json) and
the [`host build record`](../data/raw/gbs_package_20260903/README.md). The alloc_bench
ELF participated in the fixed-contract H-V calibration sample, which is not
independent validation. GBS is the default L2 path after a separate **alloc_bench-only**
held-out run passed 4/4; the frozen bundle is the fallback. See the
[`held-out report`](../docs/gbs_heldout_validation_20260904.md) and
[`A-anchor replication`](../docs/a_anchor_replication_20260904.md). The GBS ELF
identity chain covers all three tools, but gst_loop_decode/reclaim_probe board
behavior is based on September 3 retry2, not the four held-out cells; the existing
[`gst compact evidence`](../data/raw/gbs_rebaseline_20260903/gst_retry2/README.md)
is publicly replayable.

The entrypoint's default `verify` mode performs portable spec/`%files` checks but
does not build. Its explicit `gbs` mode creates one unique temporary buildroot per
run, acquires the cross-process lock, and uses the fixed payload `source_commit`
from the manifest (not the checkout's latest tools sources). The checkout HEAD
identifies the executing workflow separately. Do not substitute a raw GBS command
or a shared buildroot: the checker is the single source for the actual command,
artifact extraction, and hash gates.

After acquiring the lock and before invoking GBS, the checker writes
`execution_provenance.json` (workflow HEAD, clean/dirty status, entrypoint/checker
hashes, Python version and UTC capture time). Dirty snapshots are rejected. The
publisher only validates and copies this file, requiring the exact same clean
HEAD at publication. A later delivery commit must retain the recorded script bytes.
See [`workflow provenance`](../tools/reproduce/README.md#gbs-execution-provenance).

Schema v2 also binds `config/gbs_llvm.conf`, `config/gbs.conf`,
`tools/reproduce/deliverables_manifest.json` and tracked `packaging/*.spec` to Git
object bytes, including skip-worktree-hidden changes. After GBS returns, proof
bytes are re-read and compared with their pre-build digest before JSON validation;
output and publication copies are checked again. The raw GBS log hash is recorded
and required by the publisher. This self-recorded proof is not signed remote
attestation; `entrypoint_sha256` identifies repository file bytes, not the caller.

That explicit mode needs the configured network repositories, a root-capable GBS
environment, buildroot disk space, and substantially more time than host verify.
