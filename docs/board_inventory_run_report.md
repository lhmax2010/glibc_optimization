> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# Tizen memopt inventory board run report

## Header

- Date: 2026-07-08T15:13:50+08:00 to 2026-07-08T15:21:02+08:00
- Board IP: `<TEST_BOARD_IP>`
- sdb binary used: `<USER_HOME>/tizen-studio/tools/sdb`
- sdb version: `Smart Development Bridge version 4.2.25`
- Root obtained: yes
- Script SHA-256 before push: `42f257bb11bd80b4c77eddf7a2a69cf6958f4133b435202fd7debf6336d7f820`

`/etc/os-release`:

```text
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=<TEST_IMAGE_C>
```

`uname -a`:

```text
Linux localhost 6.12.80-arm-rpi4-v7l #1 SMP Fri Jul  3 10:06:01 UTC 2026 armv7l GNU/Linux
```

## Execution record

Initial local PATH note:

```text
$ sdb version
/bin/bash: line 1: sdb: command not found
```

Located and used `<USER_HOME>/tizen-studio/tools/sdb`.

Commands run:

```sh
<USER_HOME>/tizen-studio/tools/sdb version
<USER_HOME>/tizen-studio/tools/sdb connect <TEST_BOARD_IP>
<USER_HOME>/tizen-studio/tools/sdb devices
<USER_HOME>/tizen-studio/tools/sdb root on
<USER_HOME>/tizen-studio/tools/sdb shell id
<USER_HOME>/tizen-studio/tools/sdb shell cat /etc/os-release
<USER_HOME>/tizen-studio/tools/sdb shell uname -a
<USER_HOME>/tizen-studio/tools/sdb shell 'which od awk tr sed hostname date; od --help 2>&1 | head -2'
<USER_HOME>/tizen-studio/tools/sdb shell 'for x in sh od awk tr sed hostname date; do if command -v "$x" >/dev/null 2>&1; then command -v "$x"; else echo MISSING:$x; fi; done; printf A | od -A n -j 0 -N 1 -t x1'
<USER_HOME>/tizen-studio/tools/sdb push docs/tizen_memopt_inventory.sh /tmp/
<USER_HOME>/tizen-studio/tools/sdb shell 'chmod +x /tmp/tizen_memopt_inventory.sh'
<USER_HOME>/tizen-studio/tools/sdb shell 'sh /tmp/tizen_memopt_inventory.sh > /tmp/inventory.tsv 2> /tmp/inventory_summary.txt; echo EXIT=$?'
<USER_HOME>/tizen-studio/tools/sdb shell 'ls -d /proc/[0-9]* | wc -l'
<USER_HOME>/tizen-studio/tools/sdb shell 'total=0; nonempty=0; empty=0; for d in /proc/[0-9]*; do total=$((total+1)); cmd=$(tr "\0" " " < "$d/cmdline" 2>/dev/null); if [ -n "$cmd" ]; then nonempty=$((nonempty+1)); else empty=$((empty+1)); fi; done; echo total=$total nonempty_cmdline=$nonempty empty_cmdline=$empty'
<USER_HOME>/tizen-studio/tools/sdb shell 'LD_SHOW_AUXV=1 /bin/true | grep -i secure'
<USER_HOME>/tizen-studio/tools/sdb pull /tmp/inventory.tsv ./board_results/
<USER_HOME>/tizen-studio/tools/sdb pull /tmp/inventory_summary.txt ./board_results/
<USER_HOME>/tizen-studio/tools/sdb shell 'rm /tmp/tizen_memopt_inventory.sh /tmp/inventory.tsv /tmp/inventory_summary.txt'
<USER_HOME>/tizen-studio/tools/sdb shell 'ls -l /tmp/tizen_memopt_inventory.sh /tmp/inventory.tsv /tmp/inventory_summary.txt 2>&1 || true'
```

Device connection:

```text
<TEST_BOARD_IP>:26101 is already connected
List of devices attached 
<TEST_BOARD_IP>:26101	device    	rpi4
```

Root:

```text
Switched to 'root' account mode
uid=0(root) gid=0(root) groups=0(root),29(audio),44(video),201(display),1901(log),6505(pulse-access),6506(pulse-rt),6525(usb_device),10001(priv_externalstorage),10013(priv_tee_client),10014(priv_peripheralio),10212(priv_platform),10501(priv_camera),10502(priv_mediastorage),10503(priv_recorder),10704(priv_internet),10705(priv_network_get),10711(priv_tethering_admin),10901(priv_email),10903(priv_message_read),11103(priv_mapservice),11201(priv_appdebugging) context="User::Shell"
```

Preflight:

```text
/bin/sh: which: command not found
Usage: od [OPTION]... [FILE]...
  or:  od [-abcdfilosx]... [FILE] [[+]OFFSET[.][b]]

/usr/bin/sh
/usr/bin/od
/usr/bin/awk
/usr/bin/tr
/usr/bin/sed
MISSING:hostname
/usr/bin/date
 41
```

Required tools (`sh`, `od`, `awk`, `tr`, `sed`) were present; `od -A/-j/-N/-t` probe returned `41`. `hostname` was missing but the script falls back to `unknown` for its header.

Execution exit:

```text
EXIT=0
```

sdb stderr/noise observed:

```text
WARNING: Your data are to be sent over an unencrypted connection and could be read by others.
```

Cleanup verification:

```text
ls: cannot access /tmp/tizen_memopt_inventory.sh: No such file or directory
ls: cannot access /tmp/inventory.tsv: No such file or directory
ls: cannot access /tmp/inventory_summary.txt: No such file or directory
```

## Sanity checks

### C1 row-count integrity

Raw counts:

```text
/proc PID count: 208
non-empty cmdline processes: 52
empty cmdline processes: 156
TSV data rows: 52
```

The non-empty cmdline counting command saw transient process races:

```text
/bin/sh: /proc/20818/cmdline: No such file or directory
/bin/sh: /proc/20819/cmdline: No such file or directory
/bin/sh: /proc/20820/cmdline: No such file or directory
```

### C2 elf32 auxv cross-check

Fresh non-secure process:

```text
LD_SHOW_AUXV=1 /bin/true | grep -i secure
AT_SECURE:            0
```

TSV non-secure elf32 example and independent hex auxv read:

```text
TSV: pid=1 comm=systemd elf_class=elf32 at_secure=0 cmd=/sbin/init
Independent: pid=1 AT_SECURE_hex=00000000
```

TSV secure elf32 example and independent hex auxv read:

```text
TSV: pid=409 comm=esd elf_class=elf32 at_secure=1 cmd=/usr/bin/esd
Independent: pid=409 AT_SECURE_hex=00000001
```

Setuid check:

```text
-rwsr-xr-x 1 root root 31108 Jul  3 15:42 /usr/bin/su
pgrep -a su:
81 [sugov:0]
```

No live `su` process was present in the TSV run.

### C3 unknown-rate

```text
total=52 at_secure_NA=0 elf_class_unknown=0 either=0 pct=0.00
```

## inventory_summary.txt

```text
/tmp/tizen_memopt_inventory.sh: line 49: /proc/18818/cmdline: No such file or directory
/tmp/tizen_memopt_inventory.sh: line 49: /proc/18819/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=52  AT_SECURE=1: 11  AT_SECURE=0: 41  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

## Quick TSV stats

- Total rows: 52
- `at_secure=1`: 11
- `at_secure=0`: 41
- `at_secure=NA`: 0
- Rows with LIVE env hits: 0

LIVE env hit rows:

```text
none
```

Top 10 by `rss_kb`:

| pid | comm | rss_kb | pss_kb | threads |
|---:|---|---:|---:|---:|
| 409 | esd | 5332 | 3516 | 9 |
| 413 | ServiceR | 4228 | 2656 | 12 |
| 868 | sdbd | 4120 | 2827 | 10 |
| 439 | ServiceV | 3320 | 2487 | 14 |
| 1 | systemd | 3260 | 2114 | 1 |
| 445 | deviced | 3172 | 1969 | 4 |
| 405 | buxton2d | 2904 | 2038 | 4 |
| 751 | AppU | 2892 | 2358 | 9 |
| 505 | pulseaudio | 2784 | 2548 | 5 |
| 778 | efl_config | 2684 | 2650 | 5 |

Top 10 by `threads`:

| pid | comm | threads | rss_kb | pss_kb |
|---:|---|---:|---:|---:|
| 439 | ServiceV | 14 | 3320 | 2487 |
| 413 | ServiceR | 12 | 4228 | 2656 |
| 868 | sdbd | 10 | 4120 | 2827 |
| 751 | AppU | 9 | 2892 | 2358 |
| 409 | esd | 9 | 5332 | 3516 |
| 802 | pass | 8 | 1616 | 867 |
| 408 | ServiceS | 8 | 2208 | 1927 |
| 860 | mtp-responder | 7 | 2136 | 1879 |
| 386 | hal-backend-ser | 7 | 944 | 936 |
| 925 | security-manage | 6 | 1868 | 1185 |

## Retrieved artifacts

- TSV: `board_results/inventory.tsv`
  - Size: 5605 bytes
  - SHA-256: `08dafbad93c41f1e3b9b4aba1ed37b69f92f1ed4b70c75939a9d4c1a4c142c7e`
- Summary: `board_results/inventory_summary.txt`
  - Size: 404 bytes
  - SHA-256: `5511b41e42749bde699723ac98b9e94d1096d0ad0440d4ff79aaa0b4c3599f1c`
