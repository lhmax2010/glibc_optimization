# GBS package for the Demo harnesses

`glibc-memopt-tools.spec` builds one `glibc-memopt-tools-1.0.0-1.armv7l` RPM
containing these three executables:

- `/usr/bin/alloc_bench`
- `/usr/bin/gst_loop_decode`
- `/usr/bin/reclaim_probe`

The frozen LLVM-image build uses the immutable repositories in
[`config/gbs_llvm.conf`](../config/gbs_llvm.conf): Unified Toolchain
`20260814.092727` and the Base Toolchain `20260813.050338` named by that Unified
snapshot's build metadata. Build with:

```sh
gbs -c config/gbs_llvm.conf build -A armv7l --overwrite
```

The repository is the GBS source tree; no Gerrit import or separate source archive
is required. The resulting RPM identity, RPM SHA-256, buildroot versions, and ELF
SHA-256 values are recorded in
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json) and
the [`host build record`](../data/raw/gbs_package_20260903/README.md). These ELF
files participated in the fixed-contract H-V calibration sample; GBS remains pending
held-out validation, and the frozen bundle is the current default L2 path. See the
[`A-anchor replication`](../docs/a_anchor_replication_20260904.md).

Run `python3 tools/reproduce/check_gbs_package.py` for the portable spec/`%files`
check. A real build is deliberately separate:
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`.
That explicit mode needs the configured network repositories, a root-capable GBS
environment, buildroot disk space, and substantially more time than host verify.
