# GBS host build record (2026-09-03)

This compact record describes a host-only build. No board was contacted and the
generated ELF files subsequently passed the preregistered A-anchor board
rebaseline through the H-V decision; see
[`docs/a_anchor_replication_20260904.md`](../../../docs/a_anchor_replication_20260904.md).

## Source/repository mapping

- BUILD_ID family: `tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`
- Unified snapshot: `tizen-unified-toolchain_20260814.092727`
- Unified `build.xml` base dependency: `tizen-base-toolchain_20260813.050338`
- Selected config: [`config/gbs_llvm.conf`](../../../config/gbs_llvm.conf)
- Alternate [`config/gbs.conf`](../../../config/gbs.conf) follows moving
  `reference` repositories and is not used for the frozen-image package.

The selected snapshot indexes resolve the spec's exact `-devel` list to:

- `glibc-devel-2.40-1.6.armv7l`
- `glib2-devel-2.80.5-0.armv7l`
- `gstreamer-devel-1.24.11-38.armv7l`

## Command and result

```text
gbs -c config/gbs_llvm.conf build -A armv7l --overwrite
```

The immutable machine record is [`build_summary.json`](build_summary.json). It
contains the exact source commit built, package NVR/arch/size/SHA, buildroot
compiler/glibc versions, and extracted ELF hashes. The checked-in RPM and ELF
binaries are intentionally omitted; the manifest is the hash contract.
The exact recorded RPM and full GBS log remain in the private local
`board_results/gbs_package_20260903/` archive and are available on request.

The RPM SHA is the identity of the archived host-build instance. Repeating GBS can
change source/payload archive metadata even when the three extracted ELF hashes are
identical. Therefore verification records any wrapper-SHA difference as
`REPORT_ONLY` and gates on source commit, NVR/arch, `%files`, and the three ELF
hashes; this does not weaken the recorded RPM's SHA-256 identity.
