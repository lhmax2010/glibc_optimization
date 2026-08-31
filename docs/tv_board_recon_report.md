> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# TV Board Recon Report

## 1. 身份区

- Date: `2026-07-10` Asia/Shanghai.
- Board IP: `<PRODUCT_BOARD_IP>`.
- sdb path: `<USER_HOME>/tizen-studio/tools/sdb`.
- sdb connectivity: connected, `devices` state is `device`.
- Root obtained: yes, `sdb root on` succeeded and `sdb shell id` reports `uid=0(root)`.
- TV image marking from task context: real TV image, GCC `-Os` build, trimmed command set. Board commands confirmed GCC 14.2.0 strings; optimization flags are not directly printed by the queried commands.
- glibc exact runtime version: `glibc-2.40-1.7.armv7l`; `/usr/lib/libc.so.6` and `/lib/libc.so.6` report GNU libc stable release version `2.40`, compiled by GNU CC `14.2.0`.
- Local note: this run was performed after the separate SDB recovery task; SDB recovery details are in `docs/tv_sdbd_recovery_guide.md`.

`sdb version`:

```text
Smart Development Bridge version 4.2.25
```

`sdb connect` / `sdb devices`:

```text
<PRODUCT_BOARD_IP>:26101 is already connected
List of devices attached 
<PRODUCT_BOARD_IP>:26101	device    	0
```

`sdb root on` / `sdb shell id`:

```text
(empty output; command RC=0)
uid=0(root) gid=0(root) groups=0(root),29(audio),44(video),201(display),1901(log),6505(pulse-access),6506(pulse-rt),6525(usb_device),10001(priv_externalstorage),10013(priv_tee_client),10014(priv_peripheralio),10212(priv_platform),10501(priv_camera),10502(priv_mediastorage),10503(priv_recorder),10704(priv_internet),10705(priv_network_get),10711(priv_tethering_admin),10901(priv_email),10903(priv_message_read),11103(priv_mapservice),11201(priv_appdebugging) context="User::Shell"
```

`/etc/os-release`:

```text
NAME=Tizen
VERSION="10.0.0 (<PRODUCT_IMAGE>)"
ID=tizen
VERSION_ID=10.0.0
PRETTY_NAME="<PRODUCT_IMAGE>"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:10.0.0"
BUILD_ID=<PRODUCT_IMAGE_A>
```

`uname -a`:

```text
Linux localhost 5.4.261 #1 SMP PREEMPT Fri May 29 07:36:31 UTC 2026 armv7l GNU/Linux
```

`cat /proc/version`:

```text
Linux version 5.4.261 (abuild@ci2532) (gcc version 14.2.0 (Tizen GCC 14.2.0 20240801 1.1)) #1 SMP PREEMPT Fri May 29 07:36:31 UTC 2026
```

glibc version probes:

`/usr/lib/libc.so.6`:

```text
GNU C Library (GNU libc) stable release version 2.40.
Copyright (C) 2024 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.
There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.
Compiled by GNU CC version 14.2.0.
libc ABIs: UNIQUE ABSOLUTE
Minimum supported kernel: 3.2.0
For bug reporting instructions, please see:
<https://www.gnu.org/software/libc/bugs.html>.
```

`/lib/libc.so.6`:

```text
GNU C Library (GNU libc) stable release version 2.40.
Copyright (C) 2024 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.
There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.
Compiled by GNU CC version 14.2.0.
libc ABIs: UNIQUE ABSOLUTE
Minimum supported kernel: 3.2.0
For bug reporting instructions, please see:
<https://www.gnu.org/software/libc/bugs.html>.
```

`rpm -q glibc`:

```text
glibc-2.40-1.7.armv7l
```

`ls -l /usr/lib/libc-*.so /lib/libc.so.6`:

```text
lrwxrwxrwx 1 root root      12 May 29 07:18 /lib/libc.so.6 -> libc-2.40.so
-rwxr-xr-x 1 root root 1449444 May 29 07:20 /usr/lib/libc-2.40.so
```

## 2. 命令矩阵

| Command | TV status | Evidence |
|---|---|---|
| `sh` | 存在 | `/usr/bin/sh` |
| `od` | 存在 | `/usr/bin/od` |
| `awk` | 存在 | `/usr/bin/awk` |
| `sed` | 存在 | `/usr/bin/sed` |
| `tr` | 存在 | `/usr/bin/tr` |
| `grep` | 存在 | `/usr/bin/grep` |
| `cut` | 存在 | `/usr/bin/cut` |
| `sort` | 存在 | `/usr/bin/sort` |
| `head` | 存在 | `/usr/bin/head` |
| `tail` | 存在 | `/usr/bin/tail` |
| `wc` | 存在 | `/usr/bin/wc` |
| `date` | 存在 | `/usr/bin/date` |
| `hostname` | 缺失 | `/bin/sh: busybox: command not found` |
| `sleep` | 存在 | `/usr/bin/sleep` |
| `cat` | 存在 | `/usr/bin/cat` |
| `ls` | 存在 | `/usr/bin/ls` |
| `rm` | 存在 | `/usr/bin/rm` |
| `chmod` | 存在 | `/usr/bin/chmod` |
| `mkdir` | 存在 | `/usr/bin/mkdir` |
| `df` | 存在 | `/usr/bin/df` |
| `free` | 存在 | `/usr/bin/free` |
| `uptime` | 存在 | `/usr/bin/uptime` |
| `pgrep` | 存在 | `/usr/bin/pgrep` |
| `pkill` | 存在 | `/usr/bin/pkill` |
| `ps` | 存在 | `/usr/bin/ps` |
| `top` | 存在 | `/usr/bin/top` |
| `file` | 存在 | `/usr/bin/file` |
| `readlink` | 存在 | `/usr/bin/readlink` |
| `systemctl` | 存在 | `/usr/bin/systemctl` |
| `journalctl` | 存在 | `/usr/bin/journalctl` |
| `rpm` | 存在 | `/usr/sbin/rpm` |
| `pmap` | 存在 | `/usr/bin/pmap` |

BusyBox probe:

```text
MISSING:busybox
```

## 3. 内核能力矩阵

| Capability | TV result |
|---|---|
| overcommit_memory | `1` |
| THP path | `ls: cannot access /sys/kernel/mm/transparent_hugepage/: No such file or directory` |
| PSI memory | `some avg2=0.00 avg6=0.00 avg10=0.00 total=452503<br>full avg2=0.00 avg6=0.00 avg10=0.00 total=204222` |
| cgroup root listing | `blkio<br>cpu<br>cpuacct<br>cpuset<br>devices<br>freezer` |
| cgroup v2 controllers | `cat: /sys/fs/cgroup/cgroup.controllers: No such file or directory` |
| /proc/1/smaps_rollup | `00466000-be1e2000 ---p 00000000 00:00 0          [rollup]<br>Rss:                8356 kB<br>Pss:                5138 kB<br>Pss_Anon:           4352 kB<br>Pss_File:            772 kB` |
| /proc/1/smaps fallback | `00466000-0054d000 r-xp 00000000 b3:1b 19508      /usr/lib/systemd/systemd<br>Size:                924 kB<br>KernelPageSize:        4 kB<br>MMUPageSize:           4 kB<br>Rss:                 828 kB<br>cat: write error: Broken pipe` |
| /proc/1/auxv | `AUXV_OK` |
| /proc/1/task count | `1` |
| CPU count | `4<br>4` |
| CPU governor | `performance<br>---available---<br>performance ` |
| MemTotal | `MemTotal:        1602608 kB` |

CPU info excerpt:

```text
processor	: 0
model name	: ARMv7 Processor rev 4 (v7l)
BogoMIPS	: 24.00
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm aes pmull sha1 sha2 crc32 
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x0
CPU part	: 0xd03
CPU revision	: 4

processor	: 1
model name	: ARMv7 Processor rev 4 (v7l)
BogoMIPS	: 24.00
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm aes pmull sha1 sha2 crc32 
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x0
CPU part	: 0xd03
CPU revision	: 4

processor	: 2
model name	: ARMv7 Processor rev 4 (v7l)
BogoMIPS	: 24.00
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm aes pmull sha1 sha2 crc32 
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x0
CPU part	: 0xd03
CPU revision	: 4

processor	: 3
model name	: ARMv7 Processor rev 4 (v7l)
BogoMIPS	: 24.00
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm aes pmull sha1 sha2 crc32 
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x0
CPU part	: 0xd03
CPU revision	: 4

Hardware	: Novatek Cortex-A53
Revision	: 0000
Serial		: 0000000000000000
```

## 4. 探测件结果

### Inventory

- Push: succeeded.
- Run command: `sh /tmp/tizen_memopt_inventory.sh > /tmp/tv_inventory.tsv 2> /tmp/tv_inventory_summary.txt; echo EXIT=$?`.
- Script exit inside board command: `EXIT=1`.
- Result: FAILED before collection due to TV execution/signing policy, not due to missing POSIX commands or script syntax.
- Gap list: UEP rejects unsigned script execution from `/tmp`; no inventory TSV rows were produced.

inventory stderr/summary:

```text
[1;31m[uep][bash] the file is NOT signed!! : /tmp/tizen_memopt_inventory.sh[0m
```

### alloc_bench smoke

- Push: succeeded.
- Run command: `/tmp/alloc_bench.armv7l --profile small-churn --threads 2 --seed 1 --warmup 0 --ops-per-thread 1000 --idle 0 --outdir /tmp/tv_alloc_smoke`.
- Exit code: `126`.
- Compatibility verdict: NOT VERIFIED for glibc symbol versioning because the binary was blocked before dynamic loader execution.
- Result: FAILED due to TV execution policy: `/bin/sh: /tmp/alloc_bench.armv7l: Operation not permitted`.
- JSON output: empty.

alloc_bench stderr:

```text
/bin/sh: /tmp/alloc_bench.armv7l: Operation not permitted
```

alloc_bench file probe:

```text
---tmp-ls---
drwxrwxrwt 27 root root   4320 Jul 10 00:16 /tmp
-rwxr-xrwx  1 root root 124268 Jul  8 21:13 /tmp/alloc_bench.armv7l
-rwxr-xrwx  1 root root   4182 Jul  8 00:11 /tmp/tizen_memopt_inventory.sh
---mount-tmp---
tmpfs on /tmp type tmpfs (rw,relatime,posixacl)
---proc-mounts-tmp---
tmpfs /tmp tmpfs rw,posixacl,relatime 0 0
---smack---
System /tmp/alloc_bench.armv7l	System /tmp/tizen_memopt_inventory.sh
```

### Tunables quick probe

- Result: NOT_RUN.
- Reason: baseline alloc_bench smoke did not execute; no `malloc_info` XML was produced for arena comparison.

### Cleanup

```text
---verify---
ls: cannot access /tmp/tizen_memopt_inventory.sh: No such file or directory
ls: cannot access /tmp/tv_inventory.tsv: No such file or directory
ls: cannot access /tmp/tv_inventory_summary.txt: No such file or directory
ls: cannot access /tmp/alloc_bench.armv7l: No such file or directory
ls: cannot access /tmp/tv_alloc_smoke: No such file or directory
```

## 5. 与 rpi4 环境的差异对照表

| Item | rpi4 development board | TV board |
|---|---|---|
| sdb connection | `<PRODUCT_BOARD_IP>:26101 device rpi4` in earlier reports | `<PRODUCT_BOARD_IP>:26101 device 0` after SDB recovery |
| root | `sdb root on` succeeded | `sdb root on` succeeded |
| OS | Tizen 11.0.0 Unified, `BUILD_ID=<TEST_IMAGE_C>` | <PRODUCT_IMAGE> TV, `BUILD_ID=<PRODUCT_IMAGE_A>` |
| kernel | `6.12.80-arm-rpi4-v7l` | `5.4.261` |
| compiler strings | prior rpi4 report did not capture libc/compiler version | `/proc/version` and libc report GCC 14.2.0 |
| glibc runtime | prior rpi4 report did not capture runtime glibc package | `glibc-2.40-1.7.armv7l`; libc 2.40 |
| command set | inventory preflight: `hostname` missing; required sh/od/awk/tr/sed present | all requested commands present except `hostname`; BusyBox missing |
| overcommit | `0` | `1` |
| THP | inventory summary `thp=NA` | no `/sys/kernel/mm/transparent_hugepage/` path |
| PSI | not captured in prior rpi4 report | `/proc/pressure/memory` present |
| cgroup | not captured in prior rpi4 report | cgroup v1-style directories; no `cgroup.controllers` |
| smaps_rollup | memory workflows succeeded; explicit probe not in prior rpi4 report | `/proc/1/smaps_rollup` present |
| AUXV | inventory cross-check succeeded | `/proc/1/auxv` readable |
| CPU | 4 cores on rpi4 reports | 4 cores, `Novatek Cortex-A53` |
| governor | original `schedutil`; performance could be set | current `performance`; available list only `performance` |
| MemTotal | Batch 2.5 `3978536 kB` | `1602608 kB` |
| inventory probe | succeeded; post Batch 2.5: 52 rows, AT_SECURE 12/40/0, LIVE hits 0 | failed: UEP unsigned script rejection from `/tmp` |
| alloc_bench smoke | succeeded in Batch 2/2.5 from `/root` | failed from `/tmp`: `Operation not permitted` |
| tunables quick probe | Batch 2/2.5 tunable runs succeeded from `/root` | not run because alloc_bench blocked before execution |
| remote execution path | prior rpi4 note: `/root` required for execution | task-mandated `/tmp` permits write but execution is blocked for unsigned probes |

## 6. 阻塞项清单

| Blocker | Current fact |
|---|---|
| Unsigned `/tmp` script execution | `sh /tmp/tizen_memopt_inventory.sh` fails with `[uep][bash] the file is NOT signed!!`. |
| Unsigned `/tmp` ELF execution | `/tmp/alloc_bench.armv7l` fails with `Operation not permitted`; `/tmp` is mounted `rw,posixacl` and not `noexec`. |
| Inventory data | No TV AT_SECURE distribution collected because inventory script was blocked before collection. |
| alloc_bench compatibility | glibc symbol compatibility remains unknown because the binary did not reach dynamic loader startup. |
| Tunables effectiveness | Arena-count comparison not available because alloc_bench smoke did not run. |
| Execution location/signing policy | TV accepts SDB push to `/tmp`, but this image blocks unsigned execution from `/tmp`; probe signing or an approved execution path is unresolved for TV protocol. |

Raw evidence is under `board_results/tv_recon_live/`.

## Raw File Index

- `board_results/tv_recon_live/host_run.log`
- `board_results/tv_recon_live/local_artifacts.sha256`
- `board_results/tv_recon_live/local_artifacts.txt`
- `board_results/tv_recon_live/s1/glibc_lib_exec.rc`
- `board_results/tv_recon_live/s1/glibc_lib_exec.txt`
- `board_results/tv_recon_live/s1/glibc_usr_lib_exec.rc`
- `board_results/tv_recon_live/s1/glibc_usr_lib_exec.txt`
- `board_results/tv_recon_live/s1/id.rc`
- `board_results/tv_recon_live/s1/id.txt`
- `board_results/tv_recon_live/s1/libc_ls.rc`
- `board_results/tv_recon_live/s1/libc_ls.txt`
- `board_results/tv_recon_live/s1/os_release.rc`
- `board_results/tv_recon_live/s1/os_release.txt`
- `board_results/tv_recon_live/s1/proc_version.rc`
- `board_results/tv_recon_live/s1/proc_version.txt`
- `board_results/tv_recon_live/s1/rpm_glibc.rc`
- `board_results/tv_recon_live/s1/rpm_glibc.txt`
- `board_results/tv_recon_live/s1/sdb_connect.rc`
- `board_results/tv_recon_live/s1/sdb_connect.txt`
- `board_results/tv_recon_live/s1/sdb_devices.rc`
- `board_results/tv_recon_live/s1/sdb_devices.txt`
- `board_results/tv_recon_live/s1/sdb_root_on.rc`
- `board_results/tv_recon_live/s1/sdb_root_on.txt`
- `board_results/tv_recon_live/s1/sdb_version.rc`
- `board_results/tv_recon_live/s1/sdb_version.txt`
- `board_results/tv_recon_live/s1/uname.rc`
- `board_results/tv_recon_live/s1/uname.txt`
- `board_results/tv_recon_live/s2/busybox.rc`
- `board_results/tv_recon_live/s2/busybox.txt`
- `board_results/tv_recon_live/s2/command_matrix.rc`
- `board_results/tv_recon_live/s2/command_matrix.stderr`
- `board_results/tv_recon_live/s2/command_matrix.tsv`
- `board_results/tv_recon_live/s3/auxv.rc`
- `board_results/tv_recon_live/s3/auxv.txt`
- `board_results/tv_recon_live/s3/cgroup_controllers.rc`
- `board_results/tv_recon_live/s3/cgroup_controllers.txt`
- `board_results/tv_recon_live/s3/cgroup_ls.rc`
- `board_results/tv_recon_live/s3/cgroup_ls.txt`
- `board_results/tv_recon_live/s3/cpu_count.rc`
- `board_results/tv_recon_live/s3/cpu_count.txt`
- `board_results/tv_recon_live/s3/cpuinfo_head.rc`
- `board_results/tv_recon_live/s3/cpuinfo_head.txt`
- `board_results/tv_recon_live/s3/governor.rc`
- `board_results/tv_recon_live/s3/governor.txt`
- `board_results/tv_recon_live/s3/memtotal.rc`
- `board_results/tv_recon_live/s3/memtotal.txt`
- `board_results/tv_recon_live/s3/overcommit.rc`
- `board_results/tv_recon_live/s3/overcommit.txt`
- `board_results/tv_recon_live/s3/psi_memory.rc`
- `board_results/tv_recon_live/s3/psi_memory.txt`
- `board_results/tv_recon_live/s3/smaps.rc`
- `board_results/tv_recon_live/s3/smaps.txt`
- `board_results/tv_recon_live/s3/smaps_rollup.rc`
- `board_results/tv_recon_live/s3/smaps_rollup.txt`
- `board_results/tv_recon_live/s3/task_count.rc`
- `board_results/tv_recon_live/s3/task_count.txt`
- `board_results/tv_recon_live/s3/thp.rc`
- `board_results/tv_recon_live/s3/thp.txt`
- `board_results/tv_recon_live/s4/alloc_smoke/exit_code.txt`
- `board_results/tv_recon_live/s4/alloc_smoke/pull.rc`
- `board_results/tv_recon_live/s4/alloc_smoke/pull.txt`
- `board_results/tv_recon_live/s4/alloc_smoke/push.rc`
- `board_results/tv_recon_live/s4/alloc_smoke/push.txt`
- `board_results/tv_recon_live/s4/alloc_smoke/result.json`
- `board_results/tv_recon_live/s4/alloc_smoke/run.rc`
- `board_results/tv_recon_live/s4/alloc_smoke/run.txt`
- `board_results/tv_recon_live/s4/alloc_smoke/stderr.txt`
- `board_results/tv_recon_live/s4/inventory/pull_summary.rc`
- `board_results/tv_recon_live/s4/inventory/pull_summary.txt`
- `board_results/tv_recon_live/s4/inventory/pull_tsv.rc`
- `board_results/tv_recon_live/s4/inventory/pull_tsv.txt`
- `board_results/tv_recon_live/s4/inventory/push.rc`
- `board_results/tv_recon_live/s4/inventory/push.txt`
- `board_results/tv_recon_live/s4/inventory/run.rc`
- `board_results/tv_recon_live/s4/inventory/run.txt`
- `board_results/tv_recon_live/s4/inventory/tv_inventory.tsv`
- `board_results/tv_recon_live/s4/inventory/tv_inventory_summary.txt`
- `board_results/tv_recon_live/s4/security_context/tmp_exec_policy.rc`
- `board_results/tv_recon_live/s4/security_context/tmp_exec_policy.txt`
- `board_results/tv_recon_live/s5/cleanup.rc`
- `board_results/tv_recon_live/s5/cleanup.txt`

## 7. UEP 绕行验证

Raw evidence is under `board_results/tv_recon_live/uep_bypass/`.

### V1. stdin 管道注入脚本

Verdict: PASS.

The minimal stdin smoke executed as root and printed the expected marker, but plain EOF did not close the interactive `sdb shell sh -s` session automatically. Adding an explicit trailing `exit` made it return cleanly.

Original minimal smoke evidence:

```text
echo PIPE_OK $(id -u) $(uname -r)
sh-3.2# echo PIPE_OK $(id -u) $(uname -r)
PIPE_OK 0 5.4.261
sh-3.2#
```

Clean-return smoke with trailing `exit`:

```text
echo PIPE_OK2 $(id -u) $(uname -r)
exit
sh-3.2# echo PIPE_OK2 $(id -u) $(uname -r)
PIPE_OK2 0 5.4.261
sh-3.2# exit
exit
```

Full inventory was then injected over stdin and redirected on the TV to `/tmp/tv_inventory_pipe.tsv` and `/tmp/tv_inventory_pipe_summary.txt`; both files were pulled and then removed. The `sdb shell` stdout echoed the script body, but the redirected TSV/summary files were usable.

Inventory summary:

```text
sh: line 49: /proc/2831/cmdline: No such file or directory
sh: line 49: /proc/4kbtin/cmdline: Not a directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=1  thp=NA
processes=122  AT_SECURE=1: 23  AT_SECURE=0: 99  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

Inventory TSV quick stats:

```text
total_rows 122
at_secure_1 23
at_secure_0 99
at_secure_NA 0
live_env_hit_rows 0
```

Top 10 RSS rows from the TV inventory:

| pid | comm | rss_kb | pss_kb | threads | env_hits | cmdline |
|---:|---|---:|---:|---:|---|---|
| 314 | AppProcD | 86596 | 51603 | 55 | - | `/opt/usr/apps/AppD/bin/ServiceT.dll` |
| 2342 | AppProcB | 85552 | 41385 | 42 | - | `/usr/apps/AppS/bin/AppT` |
| 436 | ServiceE | 68688 | 47102 | 47 | - | `/usr/bin/ServiceE     0` |
| 1013 | AppProcE | 50896 | 20829 | 40 | - | `/opt/usr/apps/AppH/bin/SearchAll.dll` |
| 3810 | ServiceH | 36292 | 15725 | 9 | - | `/usr/bin/ServiceH     0` |
| 599 | ServiceD | 33564 | 15136 | 28 | - | `/opt/usr/apps/AppF/bin/ServiceD ...` |
| 258 | enlightenment | 33516 | 14617 | 26 | - | `/usr/bin/enlightenment` |
| 505 | ServiceL | 26744 | 7809 | 26 | - | `/usr/apps/AppY/bin/ServiceL ...` |
| 627 | ServiceC | 22548 | 10271 | 32 | - | `/usr/bin/ServiceC` |
| 1452 | ServiceF | 21588 | 3705 | 32 | - | `/bin/issue_report_agent` |

Cleanup evidence for the stdin inventory files:

```text
ls: cannot access /tmp/tv_inventory_pipe.tsv: No such file or directory
ls: cannot access /tmp/tv_inventory_pipe_summary.txt: No such file or directory
```

### V2. tmpfs 气球注入器

Verdict: PASS.

`/dev/shm` exists and is tmpfs with enough capacity:

```text
Filesystem           1K-blocks      Used Available Use% Mounted on
tmpfs                   801304      2532    798772   1% /dev/shm
```

64 MiB balloon run:

```text
---before-free---
               total        used        free      shared  buff/cache   available
Mem:         1602608      546968      211740        5540      889548     1055640
---before-psi---
some avg2=0.00 avg6=0.00 avg10=0.00 total=460566
full avg2=0.00 avg6=0.00 avg10=0.00 total=209599
---dd---
64+0 records in
64+0 records out
67108864 bytes (67 MB) copied, 0.203849 s, 329 MB/s
DD_RC=0
---after-free---
               total        used        free      shared  buff/cache   available
Mem:         1602608      612072      146636       71000      955008      990536
---after-psi---
some avg2=0.00 avg6=0.00 avg10=0.00 total=460567
full avg2=0.00 avg6=0.00 avg10=0.00 total=209599
---rm---
RM_RC=0
---final-free---
               total        used        free      shared  buff/cache   available
Mem:         1602608      547792      210912        5576      889588     1054816
---final-psi---
some avg2=0.00 avg6=0.00 avg10=0.00 total=460568
full avg2=0.00 avg6=0.00 avg10=0.00 total=209599
---verify---
ls: cannot access /dev/shm/balloon: No such file or directory
```

Observed deltas:

- `dd` was not blocked by UEP or permissions.
- `MemAvailable` changed from `1055640` KiB to `990536` KiB after the 64 MiB file, a drop of `65104` KiB.
- After `rm`, `MemAvailable` was `1054816` KiB.
- PSI memory was readable before, during, and after.
- `/dev/shm/balloon` was removed and verified absent.
