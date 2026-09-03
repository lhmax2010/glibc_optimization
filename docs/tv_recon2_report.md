> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# TV Recon 2 Report - LLVM 22.1.8 / `-Os` Image

Date: `2026-08-06` (Asia/Shanghai)  
Board: `<PRODUCT_BOARD_IP>`, armv7l  
Image declaration supplied by the user: platform packages were rebuilt with LLVM `22.1.8` and `-Os`; glibc itself remained GCC-built. This declaration is kept separate from artifact-derived facts below.  
Board evidence root: `board_results/tv_recon2_llvm2218_20260806/`  
Workspace evidence root: `board_results/tv_recon2_llvm2218_20260806/E/` and `F/`

## Method and Boundary

- SSH was attempted first with `ssh -T root@<PRODUCT_BOARD_IP> ...`; TCP port 22 returned `Connection refused`. All board probes therefore used fallback SDB `4.2.25`, device `<PRODUCT_BOARD_IP>:26101 device`, after `sdb root on`; `sdb shell id` returned `uid=0(root)`. SDB supplied a remote PTY (`/dev/pts/0`).
- Collection commands wrote to board-side files before `sdb pull`. The SDB stdin collector reached `collector.done`; because the SDB PTY did not propagate stdin EOF, its waiting `sh -s` was then terminated, giving wrapper rc `143`. Every completed probe has its own rc and all were `0` except the intentionally attempted board-side `readelf` command, which was missing and returned `127`.
- No service was restarted. The 256 MiB maximum tmpfs balloon and all copied `/bin/true` files were removed immediately. `/tmp/tv_recon2_llvm2218_20260806` was pulled, removed, and verified absent. A later three-file tunables probe was also removed and verified absent.
- Workspace source is only the declared audit baseline `tizen_base@8f08a7e30396822a8d969d357822a6ffd56b43fb`; it is not treated as the board's product source.

## Board-Side Facts

### Identity and Product glibc (E1-E4)

| Item | Channel | Command | Result | Unlocks protocol v2 decision |
|---|---|---|---|---|
| Image identity | SDB root | `cat /etc/os-release; uname -a; cat /proc/version` | Tizen `11.0.0`, build `<TEST_IMAGE_A>`; kernel `6.12.80-arm-rpi4-v7l`. Kernel reports GCC `14.2.0` and binutils `2.43`. | Fixes the product image/kernel identity for all measurements in this report. |
| E1 libc compiler | SDB root, then host parser on pulled board ELF | Board `readelf -p .comment /usr/lib/libc.so.6` failed because `readelf` is absent. SHA-256-matched board ELF was pulled; host `readelf` found no `.comment`. Directly executing board `/usr/lib/libc.so.6` reported `GNU libc 2.40` and `Compiled by GNU CC version 14.2.0`. | Confirms product libc is GCC `14.2.0`, independently of the workspace spec. |
| E1 loader compiler | SDB root, then host parser on pulled board ELF | `/lib/ld-linux.so.3 -> /usr/lib/ld-linux.so.3`; size `187708` bytes. Pulled ELF has no `.comment`, so its compiler version cannot be recovered from this artifact. | Keeps the loader compiler identity open instead of inheriting it from libc or workspace. |
| E2 RPM provenance | SDB root | `rpm -q glibc`; source-RPM query; changelog head | `glibc-2.40-3.12.armv7l`, source package `glibc-2.40-3.12.src.rpm`. The exposed changelog head contains only old 2013-2014 entries; RPM fields report no build host/time. No product branch or commit can be recovered from these fields. | Product package release is identified, while product source commit remains unknown. |
| E3 tunables | SDB root | Requested `strings` counts plus `/usr/lib/ld-linux.so.3 --list-tunables` | `strings /usr/lib/libc.so.6` returned `arena_max=0`, `tcache=0`; the loader self-query succeeded with rc `0` and listed 31 tunables, including `arena_max`, `mmap_threshold`, `trim_threshold`, `mxfast`, `tcache_count`, `tcache_max`, `tcache_unsorted_limit`, and `pthread.stack_cache_size`. Thus the string-count heuristic is false-negative on this product ELF, while the runtime registry is present. | Confirms these product tunable names are actually registered without using workspace behavior as a proxy. |
| E3 dlconf | SDB root | `ls -l /run/dlconf.dat` | Present, mode `0644`, size `373` bytes. | Confirms dlconf is active in this booted product image. |
| E4 size/strip | SDB root, then host parser on pulled board ELF | `/usr/lib/libc.so.6` is `1450052` bytes. Host `file` says stripped; no `.symtab`, `.strtab`, or `.comment`. Build ID `2d4df69000f90d393c8841cdc9b97b8ff4702a8e`. | Supplies PG1 flash/strip facts from the product artifact. |
| Image build-flavor cross-check | SDB root | `rpm --eval '%{optflags}'`; `rpm --eval '%{__cc}'` | Installed RPM macros expand to `-O2 -g ...` and `armv7l-tizen-linux-gnueabi-gcc`. These are current macro values, not proof of how already-installed platform binaries were built. Pulled `/bin/true` is stripped and has no `.comment`, so the user-supplied LLVM `22.1.8`/`-Os` image declaration cannot be independently recovered from this ELF. | Separates the declared platform toolchain from facts recoverable from product binaries. |

Evidence: `remote/E/e0_board_identity.out`, `remote/E/e1_compiler_comments.out`, `remote/E/e2_rpm_provenance.out`, `remote/E/e3_product_features.out`, `remote/E/e3b_runtime_and_ld_strings.out`, `remote/E/tv_recon2_e3_list_tunables.out`, `E/e1_e4_host_readelf_product_elf.out`.

### Group A - Channel and Execution

| Item | Channel | Command | Result | Unlocks protocol v2 decision |
|---|---|---|---|---|
| A1 SSH root | SSH attempt | `ssh -T -o ConnectTimeout=10 root@<PRODUCT_BOARD_IP> ...` | rc `255`: `connect to host <PRODUCT_BOARD_IP> port 22: Connection refused`. Authentication mode and no-PTY behavior could not be tested on this image. | SSH cannot be selected as the current protocol channel. |
| A1 SDB fallback | SDB | `sdb connect`; `sdb devices`; `sdb root on`; `sdb shell id` | Device state `device`; root identity obtained; remote SDB shell is PTY-backed. | SDB root is the working channel, with the documented stdin-EOF caveat. |
| A2 `/proc` walk | SDB stdin, board-file output | `for p in /proc/[0-9]*; do echo "$p $(cat $p/comm 2>/dev/null)"; done` | 207 matches; all 207 basenames were numeric. No `4kbtin` or damaged process name appeared. Because the image changed, this run cannot by itself distinguish whether the old-image anomaly was channel corruption or a transient non-PID `/proc` entry. | Current data are clean; old `4kbtin` causality remains unproven. |
| A3 signed native ELF path | SDB root | Copy board `/bin/true` to `/root` and `/opt/usr/home`, execute both original-copy and renamed-copy paths, then remove | `/root` copy failed: read-only filesystem. Both `/opt/usr/home` copies executed with rc `0` and were removed. No external ELF was injected. | `/opt/usr/home` is a tested writable execution location for a board-native ELF; `/root` is not writable on this image. |
| A4 detached tools | SDB root | `command -v systemd-run setsid nohup` | All exist under `/usr/bin`. | Long sampling can be detached using installed tools. |

### Group B - Memory and Reclaim Environment

| Item | Channel | Command | Result | Unlocks protocol v2 decision |
|---|---|---|---|---|
| B1 swap | SDB root | `cat /proc/swaps; free; cat /proc/sys/vm/swappiness` | zram `/dev/zram0`, size `3248600` KiB, used `0`; swappiness `60`. | L6 refault accounting must allow swap-backed behavior even though swap was unused at capture time. |
| B2 rollup fields | SDB root | `cat /proc/1/smaps_rollup` | `Private_Dirty` exists (`1100` KiB for PID 1); full rollup also includes `Pss_Anon`, `Pss_File`, `LazyFree`, and `SwapPss`. | `Private_Dirty` remains available for the target funnel. |
| B3 `/dev/shm` | SDB root | `df /dev/shm; ls -la /dev/shm; du -sk /dev/shm` | tmpfs size `4060752` KiB, used `256` KiB. Existing appfw/pkgmgr shared files are present. | Establishes capacity and pre-existing shared occupancy for pressure guards. |
| B4 ServiceR/LMK | SDB root | List `/etc/ServiceR`; grep memory/LMK/OOM settings | New config layout: `limiter.conf`, `monitor.conf`, `optimizer.conf`, `process.conf`. `CriticalLevel=10%`, `OomLevel=7%`, `MemoryLimitTrigger=oom`; zram and background-LRU swappiness `80` are configured. | Supplies current low-memory thresholds; old-image `memory.conf` thresholds are invalid. |
| B5 PSI window | SDB root | Grow `/dev/shm/tv_recon2_new_balloon` through 64/128/192/256 MiB; capture full PSI, MemAvailable, dmesg/journal; stop on new LMK; remove | All four levels completed. PSI averages and totals were unchanged; LMK-relevant dmesg count stayed `3`; no new LMK event. Balloon cleanup was verified. | No responsive PSI window was observed within the mandated 256 MiB probe range on this 8 GiB image. |

#### B5 PSI Curve

| Balloon MiB | MemAvailable KiB | PSI `some avg10/60/300` | `some total` | PSI `full avg10/60/300` | `full total` | New LMK/OOM |
|---:|---:|---|---:|---|---:|---|
| Baseline | 6894508 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | baseline count 3 |
| 64 | 6825188 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | no |
| 128 | 6766240 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | no |
| 192 | 6748244 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | no |
| 256 | 6665040 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | no |
| After removal | 6914856 | `0.00/0.00/0.00` | 147493 | `0.00/0.00/0.00` | 136187 | balloon absent |

Initial 60%-of-MemAvailable cap was `4039` MiB, so every requested level satisfied the guard. Evidence: `remote/B/b5_psi_balloon.out`.

### Group C - Current Process Topology

#### C0 Inventory

The unmodified `docs/tizen_memopt_inventory.sh` completed with script rc `0` through SDB stdin fallback:

```text
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=61  AT_SECURE=1: 16  AT_SECURE=0: 45  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

The TSV contains 61 data rows and no unknown ELF/AT_SECURE rows. Evidence: `remote/C/c0_inventory.tsv`, `remote/C/c0_inventory_summary.txt`.

#### C1 Top-RSS Identity and Reachability

| PID | comm | RSS KiB | exe / ancestry fact | cgroup unit fact | Per-target env fact |
|---:|---|---:|---|---|---|
| 966 | `runner` | 50084 | App ELF; parent 738 is `ServiceJ` | user `ServiceJ.service` | App has an exec boundary, but no standalone per-app systemd unit was found. |
| 556 | `enlightenment` | 21948 | `/usr/bin/enlightenment` | `display-manager.service` | Direct system service mapping exists. |
| 1016 | `AppUIA.dll` | 21496 | exe remains `/usr/bin/dotnet-hydra-loader`; parent 864 has the same exe | user `ServiceJ.service` | Same-loader parent/child chain is fork/load-without-new-exec evidence; no per-app loader startup exists for a fresh tunables parse. |
| 754 | `ise-default` | 16712 | App ELF; parent 738 is `ServiceJ` | user `ServiceJ.service` | App has an exec boundary, but no standalone per-app systemd unit was found. |
| 406 | `esd` | 13968 | `/usr/bin/esd` | `esd.service` | Direct system service mapping exists. |
| 1015 | `dotnet-hydra-lo` | 12620 | exe `/usr/bin/dotnet-hydra-loader`; parent 864 same exe | user `ServiceJ.service` | Pool/hydra scope, not a standalone app unit. |
| 864 | `dotnet-hydra-lo` | 11396 | child of launchpad process pool | user `ServiceJ.service` | Pool/hydra scope. |
| 403 | `ServiceS` | 11336 | `/usr/bin/ServiceS` | `central-ServiceS.service` | Direct system service mapping exists. |
| 428 | `ServiceV` | 11208 | `/usr/bin/ServiceV` | `ac.service` | Direct system service mapping exists. |
| 471 | `deviced` | 9780 | `/usr/bin/deviced` | `deviced.service` | Direct system service mapping exists. |

The old-image DN_* and `ServiceE` targets are not in this image's Top-RSS set. Evidence: `remote/C/c0_process_table.out`, `remote/C/c1_targets.out`, `remote/C/c1b_parent_chains.out`, `remote/C/c4_pid_unit_mapping.out`.

#### C2 glibc Heap/Arena Proxy

Metric definition: main heap is `[heap]`; an arena-like VMA is anonymous `rw-p`, starts on a 1 MiB boundary, and is no larger than 1 MiB. Named thread stacks and larger anonymous mappings are excluded. This is a maps/smaps proxy, not proof that every counted page is allocator-owned.

| PID | comm | Total Private_Dirty KiB | Main heap KiB | Arena-like count | Arena-like KiB | Combined KiB | Combined % |
|---:|---|---:|---:|---:|---:|---:|---:|
| 966 | `runner` | 32140 | 2584 | 19 | 6176 | 8760 | 27.3 |
| 1016 | `AppUIA.dll` | 10416 | 2340 | 11 | 760 | 3100 | 29.8 |
| 754 | `ise-default` | 8716 | 3056 | 1 | 44 | 3100 | 35.6 |
| 556 | `enlightenment` | 6748 | 2760 | 2 | 20 | 2780 | 41.2 |
| 1015 | `dotnet-hydra-lo` | 4464 | 1420 | 9 | 176 | 1596 | 35.8 |
| 554 | `pulseaudio` | 2672 | 1348 | 1 | 16 | 1364 | 51.0 |
| 406 | `esd` | 2584 | 248 | 5 | 300 | 548 | 21.2 |
| 428 | `ServiceV` | 2408 | 504 | 2 | 36 | 540 | 22.4 |
| 403 | `ServiceS` | 2036 | 596 | 3 | 80 | 676 | 33.2 |
| 408 | `ServiceR` | 1796 | 408 | 3 | 160 | 568 | 31.6 |
| 471 | `deviced` | 1504 | 304 | 3 | 36 | 340 | 22.6 |
| 864 | `dotnet-hydra-lo` | 292 | 136 | 7 | 12 | 148 | 50.7 |

Full reproducible output: `c2_heap_arena_summary.tsv`; parser: `parse_smaps.pl`.

#### C3 Arena Signature and C4 Injection Map

| Native target | Arena-like VMAs | Main heap | systemd unit | Direct systemd env surface |
|---|---:|---|---|---|
| `pulseaudio` | 1 | present | `pulseaudio.service` | yes |
| `ServiceV` | 2 | present | `ac.service` | yes |
| `ServiceR` | 3 | present | `ServiceR.service` | yes |
| `enlightenment` | 2 | present | `display-manager.service` | yes |
| `esd` | 5 | present | `esd.service` | yes |
| `ServiceS` | 3 | present | `central-ServiceS.service` | yes |
| `deviced` | 3 | present | `deviced.service` | yes |

Top app processes `runner`, `AppUIA.dll`, and `ise-default` are grouped under the user-level `ServiceJ.service`, not standalone per-app units. This exposes a pool-wide unit identity but not a per-app systemd drop-in surface.

### Group D - Stability Covariates

| Item | Channel | Command | Result | Unlocks protocol v2 decision |
|---|---|---|---|---|
| D1 CPU/governor | SDB root | `nproc` fallback; CPU online; all governor files | `nproc` missing; 4 processors; online `0-3`; all four governors `schedutil`. | Core count is 4 and frequency policy is not pre-pinned to performance. |
| D2 thermal | SDB root | List thermal class and read all zone type/temp | One zone: `cpu-thermal`, `33102` milli-C at capture. | Standard thermal covariate is available on this image. |
| D3 VM/memory | SDB root | `vm.overcommit_memory`; `MemTotal`; `MemAvailable` | `overcommit_memory=0`; `MemTotal=8121508` KiB; sampled `MemAvailable=6925092` KiB. | Replaces old 1.6 GiB/overcommit=1 assumptions. |
| D4 restart metadata | SDB root | `systemctl show` on mapped/candidate units; no restart | All captured units: `StartLimitBurst=5`, interval `10s`, watchdog `0`. Restart policies are listed below. | Supplies denylist inputs without changing service state. |

| Unit | Restart | StartLimitBurst | Interval | Watchdog |
|---|---|---:|---|---|
| `ac.service` | `on-failure` | 5 | `10s` | 0 |
| `central-ServiceS.service` | `no` | 5 | `10s` | 0 |
| `deviced.service` | `on-failure` | 5 | `10s` | 0 |
| `display-manager.service` | `always` | 5 | `10s` | 0 |
| `esd.service` | `on-failure` | 5 | `10s` | 0 |
| `ServiceJ.service` | `no` | 5 | `10s` | 0 |
| `pulseaudio.service` | `always` | 5 | `10s` | 0 |
| `rServiceVisk-flush.service` | `no` | 5 | `10s` | 0 |
| `ServiceR.service` | `on-failure` | 5 | `10s` | 0 |

## Workspace Source and Build Facts

### E5 Workspace Identity

- Commit: `8f08a7e30396822a8d969d357822a6ffd56b43fb`.
- Branch: `tizen_base`; tracks `origin/tizen_base`.
- Describe: `accepted/tizen/base/dev/20260707.085244`.
- Last commit subject: `Merge "dlconf: Fix NULL file handling in dlopen() and add logging for blocked attempts" into tizen_base`.
- The build used the committed tree at the exact commit; untracked `bench/`, `board_results/`, `docs` content, and local config files were not exported into the source package.

Evidence: `E/e5_workspace_identity.out`, `F/f1_gbs_build.stdout`.

### E6 Workspace Spec Facts

These statements apply only to workspace `packaging/glibc.spec`:

- GCC is forced by `%define _toolchain_override gcc`.
- `BuildFlags` starts from `%{optflags}` and explicitly appends `-O2 -g`; build-log compile commands confirm GCC `14.2.0` and `-O2`.
- Configure enables profile, bind-now, stackguard randomization, static PIE, dlconf, and dlconf-all-dirs; it disables nscd, experimental malloc, and multi-arch on armv7l.
- dlconf data path is `/run/dlconf.dat`.
- The spec declares `STRIP_KEEP_SYMTAB=*.so*`, but the actual F1 RPM's `libc.so.6` and `ld-linux.so.3` are stripped and have no `.symtab`; therefore the declaration did not produce retained symbol tables in this GBS output.
- `build_locales=0`; the base package still creates non-archive `en_US.UTF-8`. The locale subpackage contains `locale.alias` and the gconv directory; full locale installation is conditional and disabled.

Evidence with spec line numbers: `E/e6_workspace_spec_config.out`; actual artifact: `F/f1_workspace_artifact_inspection.out`.

### F1 Build Capability

Command:

```sh
/usr/bin/time -v gbs -c gbs.conf build -A armv7l --clean --commit 8f08a7e30396822a8d969d357822a6ffd56b43fb --define '_smp_mflags -j8'
```

Result: PASS, exit `0`. GBS `2.0.6` exported the exact commit, initialized a clean armv7l rootstrap from the configured Tizen Base/Unified reference repositories, built one package successfully, and generated 15 binary RPMs plus one source RPM. Wall time `9:46.58`; build-system completion time `536s`; maximum reported process RSS `251720` KiB.

Primary artifacts:

- `tmp/GBS-ROOT-TOOLCHAIN-GCC-PATCHES2/local/repos/tizen_unified_standard/armv7l/RPMS/glibc-2.40-0.armv7l.rpm`
- `tmp/GBS-ROOT-TOOLCHAIN-GCC-PATCHES2/local/repos/tizen_unified_standard/armv7l/SRPMS/glibc-2.40-0.src.rpm`
- Full list and sizes: `board_results/tv_recon2_llvm2218_20260806/F/f1_artifacts.tsv`.
- Logs: `F/f1_gbs_build.stdout`, `F/f1_gbs_build.stderr`, `F/f1_build.log`.

No package was installed and no artifact was sent to the board.

### F2 Signing Chain Probe

Facts from the generated main RPM and source RPM:

- `rpm -Kv` reports valid SHA-256/SHA-1/MD5 digests but no cryptographic signature line.
- `SIGPGP`, `SIGGPG`, `RSAHEADER`, and `DSAHEADER` are all `(none)`.
- `FILESIGNATURES`, `FILESIGNATURELENGTH`, `VERITYSIGNATUREALGO`, and `VERITYSIGNATURES` are all `(none)`.
- Extracted `libc.so.6` and `ld-linux.so.3` contain only GNU build-ID/ABI notes; no ELF signature note was found.
- A3 proves that board-native `/bin/true` executes after copy/rename under `/opt/usr/home`; it does not test an external or GBS-produced ELF and therefore does not prove that the local GBS output satisfies UEP.

F2 finding: GBS produced an unsigned RPM and unsigned payload files in this run. No verified post-GBS product signing flow was found or executed, so `alloc_bench` deployment through a signing chain remains unverified. Evidence: `F/f2_rpm_signature.out`, `F/f1_workspace_artifact_inspection.out`, `remote/A/a3_uep_path.out`.

## Product-vs-Workspace Comparison (PG1)

| Property | Board product glibc | Workspace/source or F1 artifact | Status |
|---|---|---|---|
| Upstream version | `2.40` | `2.40` | Consistent at version-number level only |
| Package release | `2.40-3.12.armv7l` | spec/build `2.40-0.armv7l` | **Inconsistent** |
| Source identity | Product branch/commit not exposed by RPM metadata | `tizen_base@8f08a7e...` | Cannot determine equivalence |
| libc compiler | Runtime reports GNU CC `14.2.0` | spec forces GCC; F1 commands use GCC `14.2.0` | Consistent compiler family/version |
| Optimization | Product libc's exact flags are not recoverable; `.comment` and command-line sections are absent | F1 is explicitly `-O2 -g` | Cannot determine; workspace `-O2` must not be assigned to product |
| libc size | `1450052` bytes | `1450052` bytes | Consistent size |
| loader size | `187708` bytes | `187708` bytes | Consistent size |
| Build IDs | libc `2d4df690...`; loader `09c3cff0...` | libc `20bee9a6...`; loader `8db3e866...` | **Inconsistent; artifacts are not bit-identical** |
| Strip result | stripped; no `.symtab` | F1 artifact also stripped; no `.symtab` | Consistent actual output; both conflict with workspace spec's keep-symtab declaration |
| Tunables registry | Loader lists 31 tunables; required malloc/pthread names present | Source lists the same named knobs | Consistent named interface; behavior/patch equivalence remains unproven |
| Tunable string representation | Product libc and loader `strings` checks returned zero for arena/tcache patterns | F1 libc: tcache count 5; F1 loader: arena count 1, tcache count 3 | **Inconsistent representation** |
| dlconf | `/run/dlconf.dat` exists | spec enables dlconf and all-dirs at same path | Consistent runtime feature/path; source equivalence unproven |
| Locale/gconv product payload | Not enumerated in this board probe | workspace facts recorded in E6 | Cannot determine |

The equal file sizes do not override the different build IDs, package releases, and tunable-string layout. The board product must remain a separate PG1 object.

## Protocol v2 Decision Table

| Decision | New-image fact |
|---|---|
| Can `alloc_bench` go to board through signing? | Not yet verified. `/opt/usr/home` executes copied board-native ELF, but F1 GBS RPM/payload has no PGP/RSA/file/verity signatures and no product signing stage was demonstrated. |
| Is there a usable PSI response window? | Not within 64-256 MiB: all PSI averages/totals remained unchanged and no LMK fired. |
| Are top targets per-app env-reachable? | `AppUIA.dll` is a same-exe hydra child and has no fresh loader startup; `runner` and `ise-default` do exec app ELFs but have no standalone units. All are grouped under user `ServiceJ.service`, not individually targetable by system service drop-ins. |
| Which targets have direct systemd env surfaces? | `enlightenment/display-manager`, `esd`, `ServiceS/central-ServiceS`, `ServiceV/ac`, `deviced`, `pulseaudio`, and `ServiceR`. |
| What is the glibc heap/arena proxy share? | Selected targets range from `21.2%` (`esd`) to `51.0%` (`pulseaudio`) of Private_Dirty; Top-RSS `runner` is `27.3%`, `AppUIA.dll` `29.8%`, and `ise-default` `35.6%`. Exact rows are in C2. |

## Key Differences from Invalidated Old-Image Recon

| Fact | Old image (reference only) | Current image |
|---|---|---|
| OS/kernel | Tizen 10, kernel `5.4.261` | Tizen 11, kernel `6.12.80` |
| Product glibc package | `2.40-1.7.armv7l` | `2.40-3.12.armv7l` |
| MemTotal | `1602608` KiB | `8121508` KiB |
| zram swap | `1041420` KiB, partly used; swappiness 100 | `3248600` KiB, unused; swappiness 60 |
| overcommit | `1` | `0` |
| CPU governor | `performance` | `schedutil` |
| Thermal interface | absent | `cpu-thermal`, 33102 milli-C |
| `/dev/shm` size/used | `801304/2532` KiB | `4060752/256` KiB |
| PSI at 256 MiB | non-zero | unchanged zero averages/totals |
| A3 writable execution path | `/root` worked; `/opt/usr/home` failed | `/root` read-only; `/opt/usr/home` worked for board-native ELF |
| `/proc/4kbtin` | observed | not reproduced; 207/207 glob matches numeric |
| Top workload | DN_*/WRT-heavy | native/appfw/hydra set led by `runner` |
| inventory AT_SECURE | old distribution invalid for current image | `16 secure / 45 non-secure / 0 unknown` |

## Cleanup and Evidence Integrity

- Board A3 copies: absent.
- `/dev/shm/tv_recon2_new_balloon`: absent.
- `/tmp/tv_recon2_llvm2218_20260806`: absent after pull.
- Supplemental `/tmp/tv_recon2_e3_list_tunables.*`: absent.
- No service restart and no persistent board write were performed.
- Pulled product libc/loader hashes match the board-side SHA-256 values exactly.

Key raw locations:

- Board collection: `board_results/tv_recon2_llvm2218_20260806/remote/`
- Product ELF copies and host inspection: `product_elf/`, `E/e1_e4_host_readelf_product_elf.out`
- Inventory: `remote/C/c0_inventory.tsv`, `remote/C/c0_inventory_summary.txt`
- smaps proxy: `c2_heap_arena_summary.tsv`, `parse_smaps.pl`, `remote/smaps/`
- Build/signing: `F/f1_gbs_build.*`, `F/f1_build.log`, `F/f1_artifacts.tsv`, `F/f2_rpm_signature.out`
- Cleanup: `cleanup_remote.stdout`, `e3_tunable_cleanup.stdout`
