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
files have not yet passed the board rebaseline; frozen artifacts remain the L2
acceptance default until that follow-up closes.

Run `python3 tools/reproduce/check_gbs_package.py` for the portable spec/`%files`
check. It also performs and inspects a real GBS build when `gbs` is installed;
otherwise it reports that part as `SKIPPED`.
