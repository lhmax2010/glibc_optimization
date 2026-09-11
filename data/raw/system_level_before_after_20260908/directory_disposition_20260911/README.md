# PM 2026-09-11 directory disposition and delayed cleanup

[audit.json](audit.json) is the terminal record; [manifest.json](manifest.json)
binds 116 original/redacted files. [commands.json](commands.json) contains 111
commands, including 107 single-operation shell requests of 70–161 bytes.
Raw IP/host-home aliases are explicit; board runtime paths are retained.

All four directories were nonempty; no rmdir/rm/kill was issued. Their contents
were listed, left pending and accepted as REPORT_ONLY under PM's explicit rule.
This is not a zero-residue claim. The image Python directory is preserved.
UID went 5001 → 0 → 5001 in one root round; original 21 cells were never rerun.

Replay only (host):

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_directory_disposition.py \
  data/raw/system_level_before_after_20260908/directory_disposition_20260911
```

Prior STOP receipts remain unchanged. The full originals stay in local
`board_results/` and are available on request. Detailed PM decision, raw listings,
health checks and limitations are in the [report](../../../../docs/system_level_before_after_20260908.md).
