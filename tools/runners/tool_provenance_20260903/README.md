# Tool provenance metadata audit

This host-only runner reads every RPM repository URL from the supplied GBS
configuration files. It downloads and checksum-verifies `repomd.xml`, `primary`,
and `filelists`, then searches package names, Provides, and complete file paths for the
three Demo tools. It also resolves every spec `BuildRequires` for `armv7l`.

```sh
python3 tools/runners/tool_provenance_20260903/audit_tool_provenance.py \
  --config config/gbs_llvm.conf \
  --config config/gbs.conf \
  --spec packaging/glibc-memopt-tools.spec \
  --cache-dir /tmp/glibc-memopt-tool-provenance-cache \
  --output /tmp/glibc-memopt-tool-provenance-output
```

Exit code `0` means no tool hit. Exit code `3` means an unexpected hit was written
to `tool_hits.tsv` and requires review before a zero-origin conclusion is made.
`--reuse-cache` is available for a checksum-verified reparse of previously downloaded
metadata; omit it for a fresh audit of moving `reference` URLs.
