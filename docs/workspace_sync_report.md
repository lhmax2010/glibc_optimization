> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Long-Term Workspace Sync Report

- Date: 2026-08-31 (Asia/Shanghai)
- Operation: host-only collection, sanitization, validation, and incremental public-repository sync
- Previous public HEAD: `7341d8bfff20872fa5c8e355111ff496b551e807`
- Long-term workspace: `<WORKSPACE>`
- Board access: none

## 1. Workspace Structure

The existing public clone was retained and updated in place. No tracked path from the previous public HEAD was deleted.

| Directory | Files | Bytes | Contents |
|---|---:|---:|---|
| `docs/` | 65 | 1,087,590 at verified push | Designs, specifications, reviews, arbitration, reconnaissance, experiment reports, and `INDEX.md` |
| `tools/` | 79 | 482,384 | Benchmark/probe source, Makefiles, self-tests, inventory, and sanitized runners |
| `patches/` | 1 | 1,597 | Reproducibility patch for the local size-optimized glibc comparison build |
| `data/derived/` | 54 | 178,252 | Matrix definitions, histograms, and derived TSV summaries |
| `data/raw/` | 457 | 1,622,574 | Selected compact execution records and directly cited time series |
| `temp/` | ignored | local-only | Sanitization audit, validation builds, archive links, build roots, and large evidence locations |

`temp/local_archive/` contains ignored local links to the original source workspace, complete board evidence, and build/runtime temporary trees. The original files remain in place; no source artifact was moved or deleted.

## 2. Collection And Publication Decisions

### Published

| Class | Files considered | Publication result |
|---|---:|---|
| Markdown documents | 63 source documents plus `README.md`, `INDEX.md`, and this report | All published after sanitization |
| Tool source and runners | 79 | All text source/scripts published; cyclic alloc_bench delta included |
| Patches | 1 | Published under `patches/` |
| Derived data | 54 | Published under `data/derived/`; existing canonical copies preserved when source differences were only line endings or alias spelling |
| Compact raw evidence | 472 considered; 457 published | Published under `data/raw/`; 179 command records, 179 thermal records, 92 run records/error streams, 3 time series, 3 key timelines, and 1 operation log |

The selected raw set is 1,622,574 bytes, below the 20 MB publication ceiling. It contains command/key timelines and small result series needed to audit report calculations.

### Local Only

The counts below describe overlapping source categories and are not additive:

| Class | Local inventory | Reason not published |
|---|---:|---|
| Build artifacts and packages | 5,413 files, at least 640,581,351 bytes | Reproducible binaries/objects/RPMs; may retain local build strings |
| Complete dlog/dmesg/smaps/XML evidence | 1,176 files, 86,394,410 bytes | Large, identity-rich, and superseded publicly by compact cited evidence |
| Complete `board_results/` archive | 7,787 files, 474,180,304 bytes | Private full-fidelity evidence; final 457-file compact subset published |
| Encoded Chromium process timelines | 15 files, 571,991 bytes | Excluded after expanded scan found reversible launch bundles, a board account, and a one-time launch token; aggregate run records remain published |
| GBS roots, sysroots, source clones, temporary runtimes | five top-level local trees, about 4.4 GB | Build cache and intermediate state, retained through ignored local archive links |
| Real-value replacement map | 1 file | Contains sensitive source values and is explicitly ignored |

No credential or cookie file was selected for publication.

## 3. Sanitization Audit

The previous local `desensitize_map.tsv` was reused without changing existing aliases. One new credential-class mapping was appended for an opaque launch token found by the expanded scan (`1` appended entry).

The scanner checked file paths and contents for private IPv4 addresses, product build/image identifiers, internal application/process/service names, local user paths, hosts/users, credentials, private keys, and internal repository/host names.

| Pattern class | Post-sanitization hits |
|---|---:|
| Private IPv4 | 0 |
| Product build ID | 0 |
| Product image identifier | 0 |
| Internal application ID | 0 |
| Internal process/service name | 0 |
| Local path | 0 |
| Host/user identity | 0 |
| Board account identity | 0 |
| Opaque launch token | 0 |
| Credential/private key | 0 |
| Internal repository/host | 0 |
| **Total** | **0** |

No binary candidate is tracked. ARM binaries, host binaries, objects, and RPMs are excluded by `.gitignore`; therefore no binary string-table exception was needed.

## 4. Index And Validation

- `README.md` now states the current project stage, surviving/rejected levers, L6 quantitative findings, directory roles, and recommended reading order.
- `docs/INDEX.md` provides a chronological experiment table with date, target class, activity, one-line result, and report link.
- alloc_bench validation in the ignored temporary copy passed `13/13`, including ASan/UBSan profiles, determinism, cyclic progressive-release timing, and ARMv7l dynamic-ELF cross-build.
- All shell runners pass syntax checks using the interpreter declared by their shebang.
- All Python runners compile as source.
- `git diff --check` passed and no executable/package build artifact is tracked.

The cyclic timing report remains explicit that its board scan was blocked before board identity verification; only implementation, host validation, and cross-build evidence are published for that step.

## 5. Incremental Commits

| Theme | Commit | Change |
|---|---|---|
| docs | `a112954f7880c7fb4114c817d1709fd4f117dfc0` | Refreshed archive note, current status report, cyclic replication report, README, and chronological index |
| tools | `963a580640a11b7c8806331deca3e6136894d76c` | Added cyclic allocator controls and repaired syntax-neutral public placeholders |
| patches | `5b184b5bf2f797de4fb7d3cab059b3c07c54d031` | Added the local glibc size-build compatibility patch |
| data | `95431057525899bb5c6ef6a8c13ae0f644686767` | Added selected compact execution evidence and updated ignore policy |
| sync report | `540fea7705e063513de2b7e2d9a96b01877642f4` | Recorded workspace inventory, validation, and local commit set |
| security | `65d271c97a32fadc5d3c86d96ffffc9485a0126e` | Removed 15 encoded identity-bearing process timelines and sanitized board-account/token references |
| audit | `9a9d431c72a5844211010295fe87302a174f7114` | Recorded the expanded zero-hit sanitization gate |

Relative to `7341d8b`, the current cumulative change adds 461 files and modifies 78 files, with zero deletions of paths that existed at the previous public HEAD. The repository has 658 tracked files and 3,378,287 tracked bytes at this verification point.

## 6. Push Result

The incremental range `7341d8b..9a9d431` was pushed to `origin/main` by fast-forward. Before push, `origin/main` was re-fetched and verified as an ancestor of the local HEAD.

Clean-clone verification of the public repository produced:

```text
remote_clone_head=9a9d431c72a5844211010295fe87302a174f7114
remote_main=9a9d431c72a5844211010295fe87302a174f7114
tracked_files=658
worktree_bytes=3378852
clone_size=8.1M
sensitive_scan_hits=0
binary_artifacts=0
```

The public diff from the previous HEAD contains 461 added and 78 modified paths. No path tracked at `7341d8b` was deleted or overwritten by a replacement tree. This report-status update is carried by the subsequent documentation-only HEAD; the final remote HEAD is verified after that push.

## 7. Content Not Uploaded

- Full dlog and dmesg captures;
- per-point smaps snapshots and complete malloc_info XML sets;
- GBS roots, sysroots, downloaded packages, and build products;
- temporary LLDB runtime files and source/build clones;
- the real-value sanitization map;
- complete private board evidence not directly required by a published calculation.

Reports referring to excluded evidence now state that the complete originals remain in the private local archive. The public subset preserves measured values, source anchors, commands, timing records, matrices, and the compact series needed for review.
