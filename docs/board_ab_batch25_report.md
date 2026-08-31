> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# alloc_bench Batch 2.5 board run report

## Header

- Date: 2026-07-09 Asia/Shanghai; run window from `2026-07-09T12:24:18+08:00` to `2026-07-09T13:35:19+08:00` per `board_results/batch25/host_run.log`.
- Board IP: `<TEST_BOARD_IP>`.
- sdb path: `<USER_HOME>/tizen-studio/tools/sdb`.
- Remote execution directory: `/root` (`/root/alloc_bench.armv7l`, `/root/alloc_bench_batch25/...`) per board execution restriction.
- Result JSON count in summary: `80`; expected from table expansion: `80` (`A=50`, `B=18`, `C=3`, `D=9`).
- Nonzero benchmark exit rows: `0`; JSON status not `ok`: `0`.
- Smoke checks: `burst-free-small` and `unsorted-drain` with `--ops-per-thread 1000`, both parsed as JSON and exited 0.

### Board identity

`sdb version`:

```text
Smart Development Bridge version 4.2.25
```

`sdb connect` / `sdb devices`:

```text
<TEST_BOARD_IP>:26101 is already connected
List of devices attached 
<TEST_BOARD_IP>:26101	device    	rpi4
```

`sdb root on` and effective identity:

```text
(empty output; command RC=0 in host_run.log)
uid=0(root) gid=0(root) groups=0(root),29(audio),44(video),201(display),1901(log),6505(pulse-access),6506(pulse-rt),6525(usb_device),10001(priv_externalstorage),10013(priv_tee_client),10014(priv_peripheralio),10212(priv_platform),10501(priv_camera),10502(priv_mediastorage),10503(priv_recorder),10704(priv_internet),10705(priv_network_get),10711(priv_tethering_admin),10901(priv_email),10903(priv_message_read),11103(priv_mapservice),11201(priv_appdebugging) context="User::Shell"
```

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

### Governor and initial covariates

Governor original values:

```text
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
```

Governor after setting `performance`:

```text
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=performance
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=performance
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=performance
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=performance
```

Initial covariates:

```text
---overcommit---
0
---free---
               total        used        free      shared  buff/cache   available
Mem:         3978536      184500     3526304        1548      312752     3794036
Swap:        1591412           0     1591412
---uptime---
 13:24:26 up 22:08,  1 user,  load average: 0.13, 0.25, 0.24
---thermal---
/sys/class/thermal/thermal_zone0/temp=32615
```

## Run Summary Table

| Part | profile | 格 | rep | 退出码 | throughput_ops_per_s | p50 | p99 | measure_rss_kb_median | idle_rss_kb | idle_free_delta_kB | idle_trim_ret | 运行前温度 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | thread-churn | C0 | 1 | 0 | 1780256.547 | 250 | 1657 | 72708 | 72740 | n/a | n/a | 33102 |
| A | thread-churn | C0 | 2 | 0 | 1784744.698 | 253 | 1644 | 72620 | 72652 | n/a | n/a | 34563 |
| A | thread-churn | C0 | 3 | 0 | 1772269.656 | 252 | 1645 | 72700 | 72732 | n/a | n/a | 35050 |
| A | thread-churn | C0 | 4 | 0 | 1783898.127 | 254 | 1645 | 73632 | 73664 | n/a | n/a | 35050 |
| A | thread-churn | C0 | 5 | 0 | 1787600.775 | 255 | 1647 | 73656 | 73688 | n/a | n/a | 35050 |
| A | thread-churn | arena2 | 1 | 0 | 1013691.546 | 387 | 18663 | 117644 | 117652 | n/a | n/a | 34076 |
| A | thread-churn | arena2 | 2 | 0 | 1015562.039 | 387 | 19295 | 85952 | 85960 | n/a | n/a | 35537 |
| A | thread-churn | arena2 | 3 | 0 | 978837.531 | 358 | 20576 | 94528 | 94536 | n/a | n/a | 36024 |
| A | thread-churn | arena2 | 4 | 0 | 978459.02 | 348 | 21333 | 102624 | 102632 | n/a | n/a | 35537 |
| A | thread-churn | arena2 | 5 | 0 | 993351.503 | 366 | 20493 | 78408 | 78416 | n/a | n/a | 36511 |
| A | thread-churn | arena3 | 1 | 0 | 1446699.559 | 280 | 14330 | 94844 | 94852 | n/a | n/a | 35050 |
| A | thread-churn | arena3 | 2 | 0 | 1418755.856 | 276 | 15868 | 117324 | 117336 | n/a | n/a | 36024 |
| A | thread-churn | arena3 | 3 | 0 | 1427316.674 | 276 | 15541 | 83212 | 83220 | n/a | n/a | 36024 |
| A | thread-churn | arena3 | 4 | 0 | 1439283.106 | 279 | 15477 | 84016 | 84024 | n/a | n/a | 36024 |
| A | thread-churn | arena3 | 5 | 0 | 1398229.377 | 278 | 15936 | 90992 | 91000 | n/a | n/a | 36024 |
| A | thread-churn | arena4 | 1 | 0 | 1695717.39 | 251 | 2683 | 85464 | 85472 | n/a | n/a | 34076 |
| A | thread-churn | arena4 | 2 | 0 | 1726895.422 | 249 | 2461 | 80480 | 80488 | n/a | n/a | 35537 |
| A | thread-churn | arena4 | 3 | 0 | 1677435.548 | 249 | 2840 | 78644 | 78652 | n/a | n/a | 36511 |
| A | thread-churn | arena4 | 4 | 0 | 1667743.656 | 255 | 2883 | 83968 | 83976 | n/a | n/a | 36024 |
| A | thread-churn | arena4 | 5 | 0 | 1637949.153 | 257 | 3076 | 85436 | 85444 | n/a | n/a | 36024 |
| A | mixed | C0 | 1 | 0 | 1999048.768 | 260 | 1228 | 115076 | 115112 | n/a | n/a | 33589 |
| A | mixed | C0 | 2 | 0 | 2008889.295 | 257 | 1219 | 114588 | 114624 | n/a | n/a | 34563 |
| A | mixed | C0 | 3 | 0 | 2013608.426 | 251 | 1210 | 115424 | 115460 | n/a | n/a | 35537 |
| A | mixed | arena2 | 1 | 0 | 1087237.599 | 423 | 17670 | 108348 | 108360 | n/a | n/a | 36511 |
| A | mixed | arena2 | 2 | 0 | 1096420.329 | 423 | 17489 | 109500 | 109512 | n/a | n/a | 34563 |
| A | mixed | arena2 | 3 | 0 | 1086463.451 | 424 | 17580 | 109188 | 109200 | n/a | n/a | 35537 |
| A | mixed | arena3 | 1 | 0 | 1575262.628 | 270 | 5411 | 110128 | 110140 | n/a | n/a | 34563 |
| A | mixed | arena3 | 2 | 0 | 1561580.052 | 279 | 6891 | 111016 | 111028 | n/a | n/a | 36024 |
| A | mixed | arena3 | 3 | 0 | 1567803.86 | 279 | 6766 | 110936 | 110948 | n/a | n/a | 36024 |
| A | mixed | arena4 | 1 | 0 | 2029256.103 | 247 | 1189 | 113448 | 113460 | n/a | n/a | 35050 |
| A | mixed | arena4 | 2 | 0 | 2025102.072 | 242 | 1188 | 113344 | 113356 | n/a | n/a | 34563 |
| A | mixed | arena4 | 3 | 0 | 2029159.323 | 246 | 1187 | 114688 | 114700 | n/a | n/a | 35050 |
| A | large-transient | C0 | 1 | 0 | 96986.553 | 352 | 59065 | 107436 | 107448 | n/a | n/a | 35537 |
| A | large-transient | C0 | 2 | 0 | 97273.05 | 342 | 53776 | 107540 | 107552 | n/a | n/a | 35050 |
| A | large-transient | C0 | 3 | 0 | 96602.178 | 345 | 61648 | 107112 | 107124 | n/a | n/a | 35050 |
| A | large-transient | arena2 | 1 | 0 | 93257.452 | 348 | 71553 | 97008 | 97024 | n/a | n/a | 35050 |
| A | large-transient | arena2 | 2 | 0 | 95512.479 | 351 | 58456 | 96432 | 96444 | n/a | n/a | 34076 |
| A | large-transient | arena2 | 3 | 0 | 95290.525 | 341 | 60838 | 95092 | 95104 | n/a | n/a | 35537 |
| A | large-transient | arena3 | 1 | 0 | 95452.519 | 330 | 58267 | 102432 | 102452 | n/a | n/a | 36024 |
| A | large-transient | arena3 | 2 | 0 | 97307.982 | 343 | 57277 | 102956 | 102972 | n/a | n/a | 34563 |
| A | large-transient | arena3 | 3 | 0 | 97148.46 | 340 | 60691 | 99656 | 99680 | n/a | n/a | 35537 |
| A | large-transient | arena4 | 1 | 0 | 95969.52 | 336 | 62046 | 103920 | 103932 | n/a | n/a | 36511 |
| A | large-transient | arena4 | 2 | 0 | 96546.12 | 338 | 54200 | 107056 | 107080 | n/a | n/a | 34076 |
| A | large-transient | arena4 | 3 | 0 | 95632.017 | 339 | 61498 | 105680 | 105692 | n/a | n/a | 35537 |
| A | mixed-t2 | C0 | 1 | 0 | 1196878.99 | 241 | 934 | 58668 | 58688 | n/a | n/a | 35537 |
| A | mixed-t2 | C0 | 2 | 0 | 1194254.887 | 242 | 931 | 57868 | 57888 | n/a | n/a | 34563 |
| A | mixed-t2 | C0 | 3 | 0 | 1194537.579 | 239 | 926 | 57796 | 57816 | n/a | n/a | 34076 |
| A | mixed-t2 | arena2 | 1 | 0 | 1204550.602 | 228 | 900 | 56616 | 56628 | n/a | n/a | 34563 |
| A | mixed-t2 | arena2 | 2 | 0 | 1204864.112 | 229 | 881 | 56224 | 56236 | n/a | n/a | 34563 |
| A | mixed-t2 | arena2 | 3 | 0 | 1199942.924 | 228 | 900 | 56776 | 56788 | n/a | n/a | 34076 |
| B | burst-free-small | C0 | 1 | 0 | 10490015.898 | 112 | 627 | 1464 | 1488 | n/a | n/a | 34076 |
| B | burst-free-small | C0 | 2 | 0 | 10534439.088 | 112 | 613 | 1464 | 1492 | n/a | n/a | 35537 |
| B | burst-free-small | C0 | 3 | 0 | 10591056.114 | 112 | 601 | 1464 | 1492 | n/a | n/a | 36024 |
| B | burst-free-small | mxfast0 | 1 | 0 | 10006246.859 | 164 | 380 | 1432 | 1456 | n/a | n/a | 36024 |
| B | burst-free-small | mxfast0 | 2 | 0 | 9944215.511 | 164 | 388 | 1432 | 1456 | n/a | n/a | 36024 |
| B | burst-free-small | mxfast0 | 3 | 0 | 9869320.232 | 164 | 400 | 1432 | 1456 | n/a | n/a | 35537 |
| B | burst-free-small | tcache_unsorted3 | 1 | 0 | 10408738.723 | 112 | 666 | 1464 | 1488 | n/a | n/a | 36024 |
| B | burst-free-small | tcache_unsorted3 | 2 | 0 | 10458960.381 | 112 | 659 | 1464 | 1488 | n/a | n/a | 36024 |
| B | burst-free-small | tcache_unsorted3 | 3 | 0 | 10463636.127 | 112 | 662 | 1464 | 1492 | n/a | n/a | 35537 |
| B | unsorted-drain | C0 | 1 | 0 | 2425487.869 | 492 | 10640 | 138376 | 138444 | n/a | n/a | 36998 |
| B | unsorted-drain | C0 | 2 | 0 | 2420848.642 | 486 | 10679 | 138484 | 138552 | n/a | n/a | 36024 |
| B | unsorted-drain | C0 | 3 | 0 | 2431634.008 | 486 | 10651 | 138656 | 138724 | n/a | n/a | 35050 |
| B | unsorted-drain | mxfast0 | 1 | 0 | 2422228.959 | 490 | 10605 | 138696 | 138732 | n/a | n/a | 35537 |
| B | unsorted-drain | mxfast0 | 2 | 0 | 2421615.469 | 488 | 10673 | 138364 | 138432 | n/a | n/a | 35537 |
| B | unsorted-drain | mxfast0 | 3 | 0 | 2428174.142 | 485 | 10561 | 138628 | 138696 | n/a | n/a | 35537 |
| B | unsorted-drain | tcache_unsorted3 | 1 | 0 | 2432474.955 | 482 | 10589 | 138768 | 138836 | n/a | n/a | 35537 |
| B | unsorted-drain | tcache_unsorted3 | 2 | 0 | 2419955.977 | 487 | 10714 | 138828 | 138896 | n/a | n/a | 35050 |
| B | unsorted-drain | tcache_unsorted3 | 3 | 0 | 2433467.376 | 489 | 10539 | 138568 | 138636 | n/a | n/a | 35537 |
| C | thread-churn | L1_L3 | 1 | 0 | 1780686.498 | 254 | 1655 | 68676 | 68708 | n/a | n/a | 36024 |
| C | thread-churn | L1_L3 | 2 | 0 | 1789267.787 | 252 | 1649 | 71180 | 71212 | n/a | n/a | 36024 |
| C | thread-churn | L1_L3 | 3 | 0 | 1785091.975 | 256 | 1645 | 70224 | 70256 | n/a | n/a | 36024 |
| D | mixed | D-C0 | 1 | 0 | 2016951.805 | 253 | 1216 | 114404 | 114444 | 48538.220 | -1 | 36024 |
| D | mixed | D-C0 | 2 | 0 | 2010617.271 | 254 | 1216 | 113660 | 113700 | 50359.020 | -1 | 35537 |
| D | mixed | D-C0 | 3 | 0 | 2004777.211 | 256 | 1220 | 114584 | 114624 | 48121.684 | -1 | 35050 |
| D | mixed | D-C0-idle-trim | 1 | 0 | 2012834.046 | 248 | 1213 | 113764 | 53500 | 50905.817 | 1 | 35537 |
| D | mixed | D-C0-idle-trim | 2 | 0 | 2009791.078 | 258 | 1225 | 115348 | 54012 | 49680.904 | 1 | 35050 |
| D | mixed | D-C0-idle-trim | 3 | 0 | 2010910.556 | 253 | 1218 | 114792 | 52896 | 49341.146 | 1 | 35050 |
| D | mixed | D-T-L3 | 1 | 0 | 2007878.461 | 251 | 1224 | 112736 | 112776 | 48330.726 | -1 | 34563 |
| D | mixed | D-T-L3 | 2 | 0 | 2010702.283 | 259 | 1218 | 115172 | 115212 | 50616.012 | -1 | 34076 |
| D | mixed | D-T-L3 | 3 | 0 | 2010069.406 | 258 | 1229 | 114664 | 114704 | 49022.708 | -1 | 35050 |

## Exceptions And Operational Notes

Exceptions log:

```text
[2026-07-09T12:24:26+08:00] matrix count note: prompt says approximately 89, table expansion is 80; executing table rows only
```

Thermal waits:

```text
none
```

Additional execution note: after an operator status check during Part D, the active `mixed/D-C0/rep1` process was observed still inside its expected run window/idle sleep and was allowed to continue; no process was killed, retried, or modified.

Nonzero exit rows: none.

Bad or missing JSON rows: none.

## Restore Evidence

Governor restore evidence:

```text
RESTORE_DATE=2026-07-09T13:35:13+08:00
RESTORE:/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
--- verify ---
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
```

Pre-run inventory summary:

```text
/root/tizen_memopt_inventory.sh: line 49: /proc/4084/cmdline: No such file or directory
/root/tizen_memopt_inventory.sh: line 49: /proc/4085/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=52  AT_SECURE=1: 11  AT_SECURE=0: 41  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

Post-run inventory summary:

```text
/root/tizen_memopt_inventory.sh: line 49: /proc/8663/cmdline: No such file or directory
/root/tizen_memopt_inventory.sh: line 49: /proc/8727/cmdline: No such file or directory
/root/tizen_memopt_inventory.sh: line 49: /proc/8729/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=52  AT_SECURE=1: 12  AT_SECURE=0: 40  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

Board cleanup evidence:

```text
---ROOT---
total 28
dr-xr-x---  3 root root  4096 Jul  9 14:35 .
drwxr-xr-x 17 root root  4096 Jul  8 15:31 ..
drwx------  3 root root  4096 Jul  8 20:37 .config
-rwxrwxrwx  1 root root 12496 Jul  8 14:43 setup_zypper.sh
---TMP---
total 12
drwxrwxrwt 12 root          root           580 Jul  9 14:35 .
drwxr-xr-x 17 root          root          4096 Jul  8 15:31 ..
drwxrwxrwt  2 root          root            40 Jan  1  1970 .ICE-unix
drwxrwxrwt  2 root          root            40 Jan  1  1970 .Test-unix
drwxrwxrwt  2 root          root            40 Jan  1  1970 .X11-unix
drwxrwxrwt  2 root          root            40 Jan  1  1970 .XIM-unix
srwxrwxrwx  1 root          root             0 Jan  1  1970 .central-ServiceS-api-control.sock
srwxrwxrwx  1 root          root             0 Jan  1  1970 .central-ServiceS-api-encryption.sock
srwxrwxrwx  1 root          root             0 Jan  1  1970 .central-ServiceS-api-extended.sock
srwxrwxrwx  1 root          root             0 Jan  1  1970 .central-ServiceS-api-ocsp.sock
srwxrwxrwx  1 root          root             0 Jan  1  1970 .central-ServiceS-api-storage.sock
srwxrwxrwx  1 security_fw   security_fw      0 Jan  1  1970 .cert-server.socket
srwxrwxrwx  1 security_fw   security_fw      0 Jan  1  1970 .device-policy-manager.sock
drwxrwxrwt  5 root          users          100 Jan  1  1970 .dotnet
srwxrwxrwx  1 root          root             0 Jan  1  1970 .download-provider.sock
-rw-r--r--  1 multimedia_fw multimedia_fw    0 Jan  1  1970 .focus_server_ready
drwxrwxrwt  2 root          root            40 Jan  1  1970 .font-unix
-rw-------  1 pulse         pulse            0 Jul  8 20:45 .pa_ready
drwx------  2 system_fw     system_fw       40 Jan  1  1970 .run
-rw-r--r--  1 root          root             0 Jan  1  1970 .security-manager.db.ok
-rw-r--r--  1 multimedia_fw multimedia_fw    0 Jan  1  1970 .sound_server_ready
-rw-r--r--  1 location      location        28 Jan  1  1970 dump_gps.log
drwxrwxrwx  2 owner         users           80 Jan  1  1970 focus
prw-rw-rw-  1 pulse         pulse            0 Jan  1  1970 keytone
drwxrwxrwt  2 root          users           40 Jan  1  1970 pkgmgr
-rw-r--r--  1 root          root             0 Jan  1  1970 rsc_mgr_ready
-rw-r-----  1 root          root             0 Jan  1  1970 sm-cleanup-tmp-flag
drwx------  3 root          root            60 Jan  1  1970 systemd-private-b2a783b8ff4443e3a14b4e722dc1dd0e-systemd-logind.service-g4fihM
-rw-rw-r--  1 system_fw     users            8 Jan  1  1970 ttrace_tag
```

## Raw File Paths

- `board_results/batch25/burst-free-small/C0/rep1/cmd.txt`
- `board_results/batch25/burst-free-small/C0/rep1/exit_code.txt`
- `board_results/batch25/burst-free-small/C0/rep1/malloc_info_burst-free-small_3058_idle.xml`
- `board_results/batch25/burst-free-small/C0/rep1/malloc_info_burst-free-small_3058_measure.xml`
- `board_results/batch25/burst-free-small/C0/rep1/mkdir_remote.log`
- `board_results/batch25/burst-free-small/C0/rep1/pull.log`
- `board_results/batch25/burst-free-small/C0/rep1/result.json`
- `board_results/batch25/burst-free-small/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/C0/rep1/stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep1/thermal.txt`
- `board_results/batch25/burst-free-small/C0/rep2/cmd.txt`
- `board_results/batch25/burst-free-small/C0/rep2/exit_code.txt`
- `board_results/batch25/burst-free-small/C0/rep2/malloc_info_burst-free-small_4252_idle.xml`
- `board_results/batch25/burst-free-small/C0/rep2/malloc_info_burst-free-small_4252_measure.xml`
- `board_results/batch25/burst-free-small/C0/rep2/mkdir_remote.log`
- `board_results/batch25/burst-free-small/C0/rep2/pull.log`
- `board_results/batch25/burst-free-small/C0/rep2/result.json`
- `board_results/batch25/burst-free-small/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/C0/rep2/stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep2/thermal.txt`
- `board_results/batch25/burst-free-small/C0/rep3/cmd.txt`
- `board_results/batch25/burst-free-small/C0/rep3/exit_code.txt`
- `board_results/batch25/burst-free-small/C0/rep3/malloc_info_burst-free-small_5443_idle.xml`
- `board_results/batch25/burst-free-small/C0/rep3/malloc_info_burst-free-small_5443_measure.xml`
- `board_results/batch25/burst-free-small/C0/rep3/mkdir_remote.log`
- `board_results/batch25/burst-free-small/C0/rep3/pull.log`
- `board_results/batch25/burst-free-small/C0/rep3/result.json`
- `board_results/batch25/burst-free-small/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/C0/rep3/stderr.txt`
- `board_results/batch25/burst-free-small/C0/rep3/thermal.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/cmd.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/exit_code.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/malloc_info_burst-free-small_6634_idle.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep1/malloc_info_burst-free-small_6634_measure.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep1/mkdir_remote.log`
- `board_results/batch25/burst-free-small/mxfast0/rep1/pull.log`
- `board_results/batch25/burst-free-small/mxfast0/rep1/result.json`
- `board_results/batch25/burst-free-small/mxfast0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep1/thermal.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/cmd.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/exit_code.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/malloc_info_burst-free-small_7824_idle.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep2/malloc_info_burst-free-small_7824_measure.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep2/mkdir_remote.log`
- `board_results/batch25/burst-free-small/mxfast0/rep2/pull.log`
- `board_results/batch25/burst-free-small/mxfast0/rep2/result.json`
- `board_results/batch25/burst-free-small/mxfast0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep2/thermal.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/cmd.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/exit_code.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/malloc_info_burst-free-small_9014_idle.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep3/malloc_info_burst-free-small_9014_measure.xml`
- `board_results/batch25/burst-free-small/mxfast0/rep3/mkdir_remote.log`
- `board_results/batch25/burst-free-small/mxfast0/rep3/pull.log`
- `board_results/batch25/burst-free-small/mxfast0/rep3/result.json`
- `board_results/batch25/burst-free-small/mxfast0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/stderr.txt`
- `board_results/batch25/burst-free-small/mxfast0/rep3/thermal.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/cmd.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/exit_code.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/malloc_info_burst-free-small_10209_idle.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/malloc_info_burst-free-small_10209_measure.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/mkdir_remote.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/pull.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/result.json`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep1/thermal.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/cmd.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/exit_code.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/malloc_info_burst-free-small_11398_idle.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/malloc_info_burst-free-small_11398_measure.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/mkdir_remote.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/pull.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/result.json`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep2/thermal.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/cmd.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/exit_code.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/malloc_info_burst-free-small_12592_idle.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/malloc_info_burst-free-small_12592_measure.xml`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/mkdir_remote.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/pull.log`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/result.json`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/stderr.txt`
- `board_results/batch25/burst-free-small/tcache_unsorted3/rep3/thermal.txt`
- `board_results/batch25/chmod_binary.log`
- `board_results/batch25/exceptions.log`
- `board_results/batch25/governor/after_set.log`
- `board_results/batch25/governor/original_raw.txt`
- `board_results/batch25/governor/set_performance.log`
- `board_results/batch25/governor_original.tsv`
- `board_results/batch25/host_run.log`
- `board_results/batch25/initial/covariates.txt`
- `board_results/batch25/large-transient/C0/rep1/cmd.txt`
- `board_results/batch25/large-transient/C0/rep1/exit_code.txt`
- `board_results/batch25/large-transient/C0/rep1/malloc_info_large-transient_13881_idle.xml`
- `board_results/batch25/large-transient/C0/rep1/malloc_info_large-transient_13881_measure.xml`
- `board_results/batch25/large-transient/C0/rep1/mkdir_remote.log`
- `board_results/batch25/large-transient/C0/rep1/pull.log`
- `board_results/batch25/large-transient/C0/rep1/result.json`
- `board_results/batch25/large-transient/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/C0/rep1/stderr.txt`
- `board_results/batch25/large-transient/C0/rep1/thermal.txt`
- `board_results/batch25/large-transient/C0/rep2/cmd.txt`
- `board_results/batch25/large-transient/C0/rep2/exit_code.txt`
- `board_results/batch25/large-transient/C0/rep2/malloc_info_large-transient_15067_idle.xml`
- `board_results/batch25/large-transient/C0/rep2/malloc_info_large-transient_15067_measure.xml`
- `board_results/batch25/large-transient/C0/rep2/mkdir_remote.log`
- `board_results/batch25/large-transient/C0/rep2/pull.log`
- `board_results/batch25/large-transient/C0/rep2/result.json`
- `board_results/batch25/large-transient/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/C0/rep2/stderr.txt`
- `board_results/batch25/large-transient/C0/rep2/thermal.txt`
- `board_results/batch25/large-transient/C0/rep3/cmd.txt`
- `board_results/batch25/large-transient/C0/rep3/exit_code.txt`
- `board_results/batch25/large-transient/C0/rep3/malloc_info_large-transient_16251_idle.xml`
- `board_results/batch25/large-transient/C0/rep3/malloc_info_large-transient_16251_measure.xml`
- `board_results/batch25/large-transient/C0/rep3/mkdir_remote.log`
- `board_results/batch25/large-transient/C0/rep3/pull.log`
- `board_results/batch25/large-transient/C0/rep3/result.json`
- `board_results/batch25/large-transient/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/C0/rep3/stderr.txt`
- `board_results/batch25/large-transient/C0/rep3/thermal.txt`
- `board_results/batch25/large-transient/arena2/rep1/cmd.txt`
- `board_results/batch25/large-transient/arena2/rep1/exit_code.txt`
- `board_results/batch25/large-transient/arena2/rep1/malloc_info_large-transient_17441_idle.xml`
- `board_results/batch25/large-transient/arena2/rep1/malloc_info_large-transient_17441_measure.xml`
- `board_results/batch25/large-transient/arena2/rep1/mkdir_remote.log`
- `board_results/batch25/large-transient/arena2/rep1/pull.log`
- `board_results/batch25/large-transient/arena2/rep1/result.json`
- `board_results/batch25/large-transient/arena2/rep1/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena2/rep1/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena2/rep1/stderr.txt`
- `board_results/batch25/large-transient/arena2/rep1/thermal.txt`
- `board_results/batch25/large-transient/arena2/rep2/cmd.txt`
- `board_results/batch25/large-transient/arena2/rep2/exit_code.txt`
- `board_results/batch25/large-transient/arena2/rep2/malloc_info_large-transient_18636_idle.xml`
- `board_results/batch25/large-transient/arena2/rep2/malloc_info_large-transient_18636_measure.xml`
- `board_results/batch25/large-transient/arena2/rep2/mkdir_remote.log`
- `board_results/batch25/large-transient/arena2/rep2/pull.log`
- `board_results/batch25/large-transient/arena2/rep2/result.json`
- `board_results/batch25/large-transient/arena2/rep2/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena2/rep2/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena2/rep2/stderr.txt`
- `board_results/batch25/large-transient/arena2/rep2/thermal.txt`
- `board_results/batch25/large-transient/arena2/rep3/cmd.txt`
- `board_results/batch25/large-transient/arena2/rep3/exit_code.txt`
- `board_results/batch25/large-transient/arena2/rep3/malloc_info_large-transient_19825_idle.xml`
- `board_results/batch25/large-transient/arena2/rep3/malloc_info_large-transient_19825_measure.xml`
- `board_results/batch25/large-transient/arena2/rep3/mkdir_remote.log`
- `board_results/batch25/large-transient/arena2/rep3/pull.log`
- `board_results/batch25/large-transient/arena2/rep3/result.json`
- `board_results/batch25/large-transient/arena2/rep3/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena2/rep3/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena2/rep3/stderr.txt`
- `board_results/batch25/large-transient/arena2/rep3/thermal.txt`
- `board_results/batch25/large-transient/arena3/rep1/cmd.txt`
- `board_results/batch25/large-transient/arena3/rep1/exit_code.txt`
- `board_results/batch25/large-transient/arena3/rep1/malloc_info_large-transient_21010_idle.xml`
- `board_results/batch25/large-transient/arena3/rep1/malloc_info_large-transient_21010_measure.xml`
- `board_results/batch25/large-transient/arena3/rep1/mkdir_remote.log`
- `board_results/batch25/large-transient/arena3/rep1/pull.log`
- `board_results/batch25/large-transient/arena3/rep1/result.json`
- `board_results/batch25/large-transient/arena3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena3/rep1/stderr.txt`
- `board_results/batch25/large-transient/arena3/rep1/thermal.txt`
- `board_results/batch25/large-transient/arena3/rep2/cmd.txt`
- `board_results/batch25/large-transient/arena3/rep2/exit_code.txt`
- `board_results/batch25/large-transient/arena3/rep2/malloc_info_large-transient_22247_idle.xml`
- `board_results/batch25/large-transient/arena3/rep2/malloc_info_large-transient_22247_measure.xml`
- `board_results/batch25/large-transient/arena3/rep2/mkdir_remote.log`
- `board_results/batch25/large-transient/arena3/rep2/pull.log`
- `board_results/batch25/large-transient/arena3/rep2/result.json`
- `board_results/batch25/large-transient/arena3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena3/rep2/stderr.txt`
- `board_results/batch25/large-transient/arena3/rep2/thermal.txt`
- `board_results/batch25/large-transient/arena3/rep3/cmd.txt`
- `board_results/batch25/large-transient/arena3/rep3/exit_code.txt`
- `board_results/batch25/large-transient/arena3/rep3/malloc_info_large-transient_23434_idle.xml`
- `board_results/batch25/large-transient/arena3/rep3/malloc_info_large-transient_23434_measure.xml`
- `board_results/batch25/large-transient/arena3/rep3/mkdir_remote.log`
- `board_results/batch25/large-transient/arena3/rep3/pull.log`
- `board_results/batch25/large-transient/arena3/rep3/result.json`
- `board_results/batch25/large-transient/arena3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena3/rep3/stderr.txt`
- `board_results/batch25/large-transient/arena3/rep3/thermal.txt`
- `board_results/batch25/large-transient/arena4/rep1/cmd.txt`
- `board_results/batch25/large-transient/arena4/rep1/exit_code.txt`
- `board_results/batch25/large-transient/arena4/rep1/malloc_info_large-transient_24620_idle.xml`
- `board_results/batch25/large-transient/arena4/rep1/malloc_info_large-transient_24620_measure.xml`
- `board_results/batch25/large-transient/arena4/rep1/mkdir_remote.log`
- `board_results/batch25/large-transient/arena4/rep1/pull.log`
- `board_results/batch25/large-transient/arena4/rep1/result.json`
- `board_results/batch25/large-transient/arena4/rep1/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena4/rep1/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena4/rep1/stderr.txt`
- `board_results/batch25/large-transient/arena4/rep1/thermal.txt`
- `board_results/batch25/large-transient/arena4/rep2/cmd.txt`
- `board_results/batch25/large-transient/arena4/rep2/exit_code.txt`
- `board_results/batch25/large-transient/arena4/rep2/malloc_info_large-transient_25808_idle.xml`
- `board_results/batch25/large-transient/arena4/rep2/malloc_info_large-transient_25808_measure.xml`
- `board_results/batch25/large-transient/arena4/rep2/mkdir_remote.log`
- `board_results/batch25/large-transient/arena4/rep2/pull.log`
- `board_results/batch25/large-transient/arena4/rep2/result.json`
- `board_results/batch25/large-transient/arena4/rep2/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena4/rep2/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena4/rep2/stderr.txt`
- `board_results/batch25/large-transient/arena4/rep2/thermal.txt`
- `board_results/batch25/large-transient/arena4/rep3/cmd.txt`
- `board_results/batch25/large-transient/arena4/rep3/exit_code.txt`
- `board_results/batch25/large-transient/arena4/rep3/malloc_info_large-transient_26995_idle.xml`
- `board_results/batch25/large-transient/arena4/rep3/malloc_info_large-transient_26995_measure.xml`
- `board_results/batch25/large-transient/arena4/rep3/mkdir_remote.log`
- `board_results/batch25/large-transient/arena4/rep3/pull.log`
- `board_results/batch25/large-transient/arena4/rep3/result.json`
- `board_results/batch25/large-transient/arena4/rep3/sdb_run_stderr.txt`
- `board_results/batch25/large-transient/arena4/rep3/sdb_run_stdout.txt`
- `board_results/batch25/large-transient/arena4/rep3/stderr.txt`
- `board_results/batch25/large-transient/arena4/rep3/thermal.txt`
- `board_results/batch25/mixed-t2/C0/rep1/cmd.txt`
- `board_results/batch25/mixed-t2/C0/rep1/exit_code.txt`
- `board_results/batch25/mixed-t2/C0/rep1/malloc_info_mixed_28181_idle.xml`
- `board_results/batch25/mixed-t2/C0/rep1/malloc_info_mixed_28181_measure.xml`
- `board_results/batch25/mixed-t2/C0/rep1/mkdir_remote.log`
- `board_results/batch25/mixed-t2/C0/rep1/pull.log`
- `board_results/batch25/mixed-t2/C0/rep1/result.json`
- `board_results/batch25/mixed-t2/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/C0/rep1/stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep1/thermal.txt`
- `board_results/batch25/mixed-t2/C0/rep2/cmd.txt`
- `board_results/batch25/mixed-t2/C0/rep2/exit_code.txt`
- `board_results/batch25/mixed-t2/C0/rep2/malloc_info_mixed_29380_idle.xml`
- `board_results/batch25/mixed-t2/C0/rep2/malloc_info_mixed_29380_measure.xml`
- `board_results/batch25/mixed-t2/C0/rep2/mkdir_remote.log`
- `board_results/batch25/mixed-t2/C0/rep2/pull.log`
- `board_results/batch25/mixed-t2/C0/rep2/result.json`
- `board_results/batch25/mixed-t2/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/C0/rep2/stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep2/thermal.txt`
- `board_results/batch25/mixed-t2/C0/rep3/cmd.txt`
- `board_results/batch25/mixed-t2/C0/rep3/exit_code.txt`
- `board_results/batch25/mixed-t2/C0/rep3/malloc_info_mixed_30581_idle.xml`
- `board_results/batch25/mixed-t2/C0/rep3/malloc_info_mixed_30581_measure.xml`
- `board_results/batch25/mixed-t2/C0/rep3/mkdir_remote.log`
- `board_results/batch25/mixed-t2/C0/rep3/pull.log`
- `board_results/batch25/mixed-t2/C0/rep3/result.json`
- `board_results/batch25/mixed-t2/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/C0/rep3/stderr.txt`
- `board_results/batch25/mixed-t2/C0/rep3/thermal.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/cmd.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/exit_code.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/malloc_info_mixed_31781_idle.xml`
- `board_results/batch25/mixed-t2/arena2/rep1/malloc_info_mixed_31781_measure.xml`
- `board_results/batch25/mixed-t2/arena2/rep1/mkdir_remote.log`
- `board_results/batch25/mixed-t2/arena2/rep1/pull.log`
- `board_results/batch25/mixed-t2/arena2/rep1/result.json`
- `board_results/batch25/mixed-t2/arena2/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep1/thermal.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/cmd.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/exit_code.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/malloc_info_mixed_573_idle.xml`
- `board_results/batch25/mixed-t2/arena2/rep2/malloc_info_mixed_573_measure.xml`
- `board_results/batch25/mixed-t2/arena2/rep2/mkdir_remote.log`
- `board_results/batch25/mixed-t2/arena2/rep2/pull.log`
- `board_results/batch25/mixed-t2/arena2/rep2/result.json`
- `board_results/batch25/mixed-t2/arena2/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep2/thermal.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/cmd.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/exit_code.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/malloc_info_mixed_1857_idle.xml`
- `board_results/batch25/mixed-t2/arena2/rep3/malloc_info_mixed_1857_measure.xml`
- `board_results/batch25/mixed-t2/arena2/rep3/mkdir_remote.log`
- `board_results/batch25/mixed-t2/arena2/rep3/pull.log`
- `board_results/batch25/mixed-t2/arena2/rep3/result.json`
- `board_results/batch25/mixed-t2/arena2/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/stderr.txt`
- `board_results/batch25/mixed-t2/arena2/rep3/thermal.txt`
- `board_results/batch25/mixed/C0/rep1/cmd.txt`
- `board_results/batch25/mixed/C0/rep1/exit_code.txt`
- `board_results/batch25/mixed/C0/rep1/malloc_info_mixed_31878_idle.xml`
- `board_results/batch25/mixed/C0/rep1/malloc_info_mixed_31878_measure.xml`
- `board_results/batch25/mixed/C0/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/C0/rep1/pull.log`
- `board_results/batch25/mixed/C0/rep1/result.json`
- `board_results/batch25/mixed/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/C0/rep1/stderr.txt`
- `board_results/batch25/mixed/C0/rep1/thermal.txt`
- `board_results/batch25/mixed/C0/rep2/cmd.txt`
- `board_results/batch25/mixed/C0/rep2/exit_code.txt`
- `board_results/batch25/mixed/C0/rep2/malloc_info_mixed_705_idle.xml`
- `board_results/batch25/mixed/C0/rep2/malloc_info_mixed_705_measure.xml`
- `board_results/batch25/mixed/C0/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/C0/rep2/pull.log`
- `board_results/batch25/mixed/C0/rep2/result.json`
- `board_results/batch25/mixed/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/C0/rep2/stderr.txt`
- `board_results/batch25/mixed/C0/rep2/thermal.txt`
- `board_results/batch25/mixed/C0/rep3/cmd.txt`
- `board_results/batch25/mixed/C0/rep3/exit_code.txt`
- `board_results/batch25/mixed/C0/rep3/malloc_info_mixed_1946_idle.xml`
- `board_results/batch25/mixed/C0/rep3/malloc_info_mixed_1946_measure.xml`
- `board_results/batch25/mixed/C0/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/C0/rep3/pull.log`
- `board_results/batch25/mixed/C0/rep3/result.json`
- `board_results/batch25/mixed/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/C0/rep3/stderr.txt`
- `board_results/batch25/mixed/C0/rep3/thermal.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/cmd.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/exit_code.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/malloc_info_mixed_32534_idle.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/malloc_info_mixed_32534_measure.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/pull.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/result.json`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep1/thermal.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/cmd.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/exit_code.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/malloc_info_mixed_1636_idle.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/malloc_info_mixed_1636_measure.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/pull.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/result.json`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep2/thermal.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/cmd.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/exit_code.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/malloc_info_mixed_3066_idle.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/malloc_info_mixed_3066_measure.xml`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/pull.log`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/result.json`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/stderr.txt`
- `board_results/batch25/mixed/D-C0-idle-trim/rep3/thermal.txt`
- `board_results/batch25/mixed/D-C0/rep1/cmd.txt`
- `board_results/batch25/mixed/D-C0/rep1/exit_code.txt`
- `board_results/batch25/mixed/D-C0/rep1/malloc_info_mixed_28242_idle.xml`
- `board_results/batch25/mixed/D-C0/rep1/malloc_info_mixed_28242_measure.xml`
- `board_results/batch25/mixed/D-C0/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0/rep1/pull.log`
- `board_results/batch25/mixed/D-C0/rep1/result.json`
- `board_results/batch25/mixed/D-C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0/rep1/stderr.txt`
- `board_results/batch25/mixed/D-C0/rep1/thermal.txt`
- `board_results/batch25/mixed/D-C0/rep2/cmd.txt`
- `board_results/batch25/mixed/D-C0/rep2/exit_code.txt`
- `board_results/batch25/mixed/D-C0/rep2/malloc_info_mixed_29689_idle.xml`
- `board_results/batch25/mixed/D-C0/rep2/malloc_info_mixed_29689_measure.xml`
- `board_results/batch25/mixed/D-C0/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0/rep2/pull.log`
- `board_results/batch25/mixed/D-C0/rep2/result.json`
- `board_results/batch25/mixed/D-C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0/rep2/stderr.txt`
- `board_results/batch25/mixed/D-C0/rep2/thermal.txt`
- `board_results/batch25/mixed/D-C0/rep3/cmd.txt`
- `board_results/batch25/mixed/D-C0/rep3/exit_code.txt`
- `board_results/batch25/mixed/D-C0/rep3/malloc_info_mixed_31114_idle.xml`
- `board_results/batch25/mixed/D-C0/rep3/malloc_info_mixed_31114_measure.xml`
- `board_results/batch25/mixed/D-C0/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/D-C0/rep3/pull.log`
- `board_results/batch25/mixed/D-C0/rep3/result.json`
- `board_results/batch25/mixed/D-C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-C0/rep3/stderr.txt`
- `board_results/batch25/mixed/D-C0/rep3/thermal.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/cmd.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/exit_code.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/malloc_info_mixed_4487_idle.xml`
- `board_results/batch25/mixed/D-T-L3/rep1/malloc_info_mixed_4487_measure.xml`
- `board_results/batch25/mixed/D-T-L3/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/D-T-L3/rep1/pull.log`
- `board_results/batch25/mixed/D-T-L3/rep1/result.json`
- `board_results/batch25/mixed/D-T-L3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep1/thermal.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/cmd.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/exit_code.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/malloc_info_mixed_5903_idle.xml`
- `board_results/batch25/mixed/D-T-L3/rep2/malloc_info_mixed_5903_measure.xml`
- `board_results/batch25/mixed/D-T-L3/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/D-T-L3/rep2/pull.log`
- `board_results/batch25/mixed/D-T-L3/rep2/result.json`
- `board_results/batch25/mixed/D-T-L3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep2/thermal.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/cmd.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/exit_code.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/malloc_info_mixed_7319_idle.xml`
- `board_results/batch25/mixed/D-T-L3/rep3/malloc_info_mixed_7319_measure.xml`
- `board_results/batch25/mixed/D-T-L3/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/D-T-L3/rep3/pull.log`
- `board_results/batch25/mixed/D-T-L3/rep3/result.json`
- `board_results/batch25/mixed/D-T-L3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/stderr.txt`
- `board_results/batch25/mixed/D-T-L3/rep3/thermal.txt`
- `board_results/batch25/mixed/arena2/rep1/cmd.txt`
- `board_results/batch25/mixed/arena2/rep1/exit_code.txt`
- `board_results/batch25/mixed/arena2/rep1/malloc_info_mixed_3137_idle.xml`
- `board_results/batch25/mixed/arena2/rep1/malloc_info_mixed_3137_measure.xml`
- `board_results/batch25/mixed/arena2/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/arena2/rep1/pull.log`
- `board_results/batch25/mixed/arena2/rep1/result.json`
- `board_results/batch25/mixed/arena2/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena2/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena2/rep1/stderr.txt`
- `board_results/batch25/mixed/arena2/rep1/thermal.txt`
- `board_results/batch25/mixed/arena2/rep2/cmd.txt`
- `board_results/batch25/mixed/arena2/rep2/exit_code.txt`
- `board_results/batch25/mixed/arena2/rep2/malloc_info_mixed_4338_idle.xml`
- `board_results/batch25/mixed/arena2/rep2/malloc_info_mixed_4338_measure.xml`
- `board_results/batch25/mixed/arena2/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/arena2/rep2/pull.log`
- `board_results/batch25/mixed/arena2/rep2/result.json`
- `board_results/batch25/mixed/arena2/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena2/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena2/rep2/stderr.txt`
- `board_results/batch25/mixed/arena2/rep2/thermal.txt`
- `board_results/batch25/mixed/arena2/rep3/cmd.txt`
- `board_results/batch25/mixed/arena2/rep3/exit_code.txt`
- `board_results/batch25/mixed/arena2/rep3/malloc_info_mixed_5537_idle.xml`
- `board_results/batch25/mixed/arena2/rep3/malloc_info_mixed_5537_measure.xml`
- `board_results/batch25/mixed/arena2/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/arena2/rep3/pull.log`
- `board_results/batch25/mixed/arena2/rep3/result.json`
- `board_results/batch25/mixed/arena2/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena2/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena2/rep3/stderr.txt`
- `board_results/batch25/mixed/arena2/rep3/thermal.txt`
- `board_results/batch25/mixed/arena3/rep1/cmd.txt`
- `board_results/batch25/mixed/arena3/rep1/exit_code.txt`
- `board_results/batch25/mixed/arena3/rep1/malloc_info_mixed_6733_idle.xml`
- `board_results/batch25/mixed/arena3/rep1/malloc_info_mixed_6733_measure.xml`
- `board_results/batch25/mixed/arena3/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/arena3/rep1/pull.log`
- `board_results/batch25/mixed/arena3/rep1/result.json`
- `board_results/batch25/mixed/arena3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena3/rep1/stderr.txt`
- `board_results/batch25/mixed/arena3/rep1/thermal.txt`
- `board_results/batch25/mixed/arena3/rep2/cmd.txt`
- `board_results/batch25/mixed/arena3/rep2/exit_code.txt`
- `board_results/batch25/mixed/arena3/rep2/malloc_info_mixed_7929_idle.xml`
- `board_results/batch25/mixed/arena3/rep2/malloc_info_mixed_7929_measure.xml`
- `board_results/batch25/mixed/arena3/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/arena3/rep2/pull.log`
- `board_results/batch25/mixed/arena3/rep2/result.json`
- `board_results/batch25/mixed/arena3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena3/rep2/stderr.txt`
- `board_results/batch25/mixed/arena3/rep2/thermal.txt`
- `board_results/batch25/mixed/arena3/rep3/cmd.txt`
- `board_results/batch25/mixed/arena3/rep3/exit_code.txt`
- `board_results/batch25/mixed/arena3/rep3/malloc_info_mixed_9122_idle.xml`
- `board_results/batch25/mixed/arena3/rep3/malloc_info_mixed_9122_measure.xml`
- `board_results/batch25/mixed/arena3/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/arena3/rep3/pull.log`
- `board_results/batch25/mixed/arena3/rep3/result.json`
- `board_results/batch25/mixed/arena3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena3/rep3/stderr.txt`
- `board_results/batch25/mixed/arena3/rep3/thermal.txt`
- `board_results/batch25/mixed/arena4/rep1/cmd.txt`
- `board_results/batch25/mixed/arena4/rep1/exit_code.txt`
- `board_results/batch25/mixed/arena4/rep1/malloc_info_mixed_10315_idle.xml`
- `board_results/batch25/mixed/arena4/rep1/malloc_info_mixed_10315_measure.xml`
- `board_results/batch25/mixed/arena4/rep1/mkdir_remote.log`
- `board_results/batch25/mixed/arena4/rep1/pull.log`
- `board_results/batch25/mixed/arena4/rep1/result.json`
- `board_results/batch25/mixed/arena4/rep1/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena4/rep1/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena4/rep1/stderr.txt`
- `board_results/batch25/mixed/arena4/rep1/thermal.txt`
- `board_results/batch25/mixed/arena4/rep2/cmd.txt`
- `board_results/batch25/mixed/arena4/rep2/exit_code.txt`
- `board_results/batch25/mixed/arena4/rep2/malloc_info_mixed_11504_idle.xml`
- `board_results/batch25/mixed/arena4/rep2/malloc_info_mixed_11504_measure.xml`
- `board_results/batch25/mixed/arena4/rep2/mkdir_remote.log`
- `board_results/batch25/mixed/arena4/rep2/pull.log`
- `board_results/batch25/mixed/arena4/rep2/result.json`
- `board_results/batch25/mixed/arena4/rep2/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena4/rep2/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena4/rep2/stderr.txt`
- `board_results/batch25/mixed/arena4/rep2/thermal.txt`
- `board_results/batch25/mixed/arena4/rep3/cmd.txt`
- `board_results/batch25/mixed/arena4/rep3/exit_code.txt`
- `board_results/batch25/mixed/arena4/rep3/malloc_info_mixed_12694_idle.xml`
- `board_results/batch25/mixed/arena4/rep3/malloc_info_mixed_12694_measure.xml`
- `board_results/batch25/mixed/arena4/rep3/mkdir_remote.log`
- `board_results/batch25/mixed/arena4/rep3/pull.log`
- `board_results/batch25/mixed/arena4/rep3/result.json`
- `board_results/batch25/mixed/arena4/rep3/sdb_run_stderr.txt`
- `board_results/batch25/mixed/arena4/rep3/sdb_run_stdout.txt`
- `board_results/batch25/mixed/arena4/rep3/stderr.txt`
- `board_results/batch25/mixed/arena4/rep3/thermal.txt`
- `board_results/batch25/os_release.txt`
- `board_results/batch25/precheck/batch25_pre_inventory.tsv`
- `board_results/batch25/precheck/batch25_pre_inventory_summary.txt`
- `board_results/batch25/precheck/inventory_run.log`
- `board_results/batch25/precheck/pull_inventory_summary.log`
- `board_results/batch25/precheck/pull_inventory_tsv.log`
- `board_results/batch25/precheck/push_inventory.log`
- `board_results/batch25/push_binary.log`
- `board_results/batch25/restore/batch25_post_inventory.tsv`
- `board_results/batch25/restore/batch25_post_inventory_summary.txt`
- `board_results/batch25/restore/governor_restore.log`
- `board_results/batch25/restore/inventory_run.log`
- `board_results/batch25/restore/pull_inventory_summary.log`
- `board_results/batch25/restore/pull_inventory_tsv.log`
- `board_results/batch25/restore/push_inventory.log`
- `board_results/batch25/restore/root_cleanup.log`
- `board_results/batch25/root_id.txt`
- `board_results/batch25/run_batch25_alloc_bench.sh`
- `board_results/batch25/run_summary.tsv`
- `board_results/batch25/sdb_connect.txt`
- `board_results/batch25/sdb_devices.txt`
- `board_results/batch25/sdb_root_on.txt`
- `board_results/batch25/sdb_version.txt`
- `board_results/batch25/smoke/burst-free-small/exit_code.txt`
- `board_results/batch25/smoke/burst-free-small/json_tool.err`
- `board_results/batch25/smoke/burst-free-small/malloc_info_burst-free-small_5599_idle.xml`
- `board_results/batch25/smoke/burst-free-small/malloc_info_burst-free-small_5599_measure.xml`
- `board_results/batch25/smoke/burst-free-small/pull.log`
- `board_results/batch25/smoke/burst-free-small/result.json`
- `board_results/batch25/smoke/burst-free-small/result.pretty.json`
- `board_results/batch25/smoke/burst-free-small/run.log`
- `board_results/batch25/smoke/burst-free-small/stderr.txt`
- `board_results/batch25/smoke/unsorted-drain/exit_code.txt`
- `board_results/batch25/smoke/unsorted-drain/json_tool.err`
- `board_results/batch25/smoke/unsorted-drain/malloc_info_unsorted-drain_5630_idle.xml`
- `board_results/batch25/smoke/unsorted-drain/malloc_info_unsorted-drain_5630_measure.xml`
- `board_results/batch25/smoke/unsorted-drain/pull.log`
- `board_results/batch25/smoke/unsorted-drain/result.json`
- `board_results/batch25/smoke/unsorted-drain/result.pretty.json`
- `board_results/batch25/smoke/unsorted-drain/run.log`
- `board_results/batch25/smoke/unsorted-drain/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep1/cmd.txt`
- `board_results/batch25/thread-churn/C0/rep1/exit_code.txt`
- `board_results/batch25/thread-churn/C0/rep1/malloc_info_thread-churn_5693_idle.xml`
- `board_results/batch25/thread-churn/C0/rep1/malloc_info_thread-churn_5693_measure.xml`
- `board_results/batch25/thread-churn/C0/rep1/mkdir_remote.log`
- `board_results/batch25/thread-churn/C0/rep1/pull.log`
- `board_results/batch25/thread-churn/C0/rep1/result.json`
- `board_results/batch25/thread-churn/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/C0/rep1/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep1/thermal.txt`
- `board_results/batch25/thread-churn/C0/rep2/cmd.txt`
- `board_results/batch25/thread-churn/C0/rep2/exit_code.txt`
- `board_results/batch25/thread-churn/C0/rep2/malloc_info_thread-churn_6958_idle.xml`
- `board_results/batch25/thread-churn/C0/rep2/malloc_info_thread-churn_6958_measure.xml`
- `board_results/batch25/thread-churn/C0/rep2/mkdir_remote.log`
- `board_results/batch25/thread-churn/C0/rep2/pull.log`
- `board_results/batch25/thread-churn/C0/rep2/result.json`
- `board_results/batch25/thread-churn/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/C0/rep2/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep2/thermal.txt`
- `board_results/batch25/thread-churn/C0/rep3/cmd.txt`
- `board_results/batch25/thread-churn/C0/rep3/exit_code.txt`
- `board_results/batch25/thread-churn/C0/rep3/malloc_info_thread-churn_8213_idle.xml`
- `board_results/batch25/thread-churn/C0/rep3/malloc_info_thread-churn_8213_measure.xml`
- `board_results/batch25/thread-churn/C0/rep3/mkdir_remote.log`
- `board_results/batch25/thread-churn/C0/rep3/pull.log`
- `board_results/batch25/thread-churn/C0/rep3/result.json`
- `board_results/batch25/thread-churn/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/C0/rep3/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep3/thermal.txt`
- `board_results/batch25/thread-churn/C0/rep4/cmd.txt`
- `board_results/batch25/thread-churn/C0/rep4/exit_code.txt`
- `board_results/batch25/thread-churn/C0/rep4/malloc_info_thread-churn_9468_idle.xml`
- `board_results/batch25/thread-churn/C0/rep4/malloc_info_thread-churn_9468_measure.xml`
- `board_results/batch25/thread-churn/C0/rep4/mkdir_remote.log`
- `board_results/batch25/thread-churn/C0/rep4/pull.log`
- `board_results/batch25/thread-churn/C0/rep4/result.json`
- `board_results/batch25/thread-churn/C0/rep4/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/C0/rep4/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/C0/rep4/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep4/thermal.txt`
- `board_results/batch25/thread-churn/C0/rep5/cmd.txt`
- `board_results/batch25/thread-churn/C0/rep5/exit_code.txt`
- `board_results/batch25/thread-churn/C0/rep5/malloc_info_thread-churn_10731_idle.xml`
- `board_results/batch25/thread-churn/C0/rep5/malloc_info_thread-churn_10731_measure.xml`
- `board_results/batch25/thread-churn/C0/rep5/mkdir_remote.log`
- `board_results/batch25/thread-churn/C0/rep5/pull.log`
- `board_results/batch25/thread-churn/C0/rep5/result.json`
- `board_results/batch25/thread-churn/C0/rep5/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/C0/rep5/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/C0/rep5/stderr.txt`
- `board_results/batch25/thread-churn/C0/rep5/thermal.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/cmd.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/exit_code.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/malloc_info_thread-churn_24468_idle.xml`
- `board_results/batch25/thread-churn/L1_L3/rep1/malloc_info_thread-churn_24468_measure.xml`
- `board_results/batch25/thread-churn/L1_L3/rep1/mkdir_remote.log`
- `board_results/batch25/thread-churn/L1_L3/rep1/pull.log`
- `board_results/batch25/thread-churn/L1_L3/rep1/result.json`
- `board_results/batch25/thread-churn/L1_L3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep1/thermal.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/cmd.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/exit_code.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/malloc_info_thread-churn_25722_idle.xml`
- `board_results/batch25/thread-churn/L1_L3/rep2/malloc_info_thread-churn_25722_measure.xml`
- `board_results/batch25/thread-churn/L1_L3/rep2/mkdir_remote.log`
- `board_results/batch25/thread-churn/L1_L3/rep2/pull.log`
- `board_results/batch25/thread-churn/L1_L3/rep2/result.json`
- `board_results/batch25/thread-churn/L1_L3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep2/thermal.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/cmd.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/exit_code.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/malloc_info_thread-churn_26981_idle.xml`
- `board_results/batch25/thread-churn/L1_L3/rep3/malloc_info_thread-churn_26981_measure.xml`
- `board_results/batch25/thread-churn/L1_L3/rep3/mkdir_remote.log`
- `board_results/batch25/thread-churn/L1_L3/rep3/pull.log`
- `board_results/batch25/thread-churn/L1_L3/rep3/result.json`
- `board_results/batch25/thread-churn/L1_L3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/stderr.txt`
- `board_results/batch25/thread-churn/L1_L3/rep3/thermal.txt`
- `board_results/batch25/thread-churn/arena2/rep1/cmd.txt`
- `board_results/batch25/thread-churn/arena2/rep1/exit_code.txt`
- `board_results/batch25/thread-churn/arena2/rep1/malloc_info_thread-churn_12215_idle.xml`
- `board_results/batch25/thread-churn/arena2/rep1/malloc_info_thread-churn_12215_measure.xml`
- `board_results/batch25/thread-churn/arena2/rep1/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena2/rep1/pull.log`
- `board_results/batch25/thread-churn/arena2/rep1/result.json`
- `board_results/batch25/thread-churn/arena2/rep1/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep1/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena2/rep1/stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep1/thermal.txt`
- `board_results/batch25/thread-churn/arena2/rep2/cmd.txt`
- `board_results/batch25/thread-churn/arena2/rep2/exit_code.txt`
- `board_results/batch25/thread-churn/arena2/rep2/malloc_info_thread-churn_13488_idle.xml`
- `board_results/batch25/thread-churn/arena2/rep2/malloc_info_thread-churn_13488_measure.xml`
- `board_results/batch25/thread-churn/arena2/rep2/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena2/rep2/pull.log`
- `board_results/batch25/thread-churn/arena2/rep2/result.json`
- `board_results/batch25/thread-churn/arena2/rep2/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep2/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena2/rep2/stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep2/thermal.txt`
- `board_results/batch25/thread-churn/arena2/rep3/cmd.txt`
- `board_results/batch25/thread-churn/arena2/rep3/exit_code.txt`
- `board_results/batch25/thread-churn/arena2/rep3/malloc_info_thread-churn_14752_idle.xml`
- `board_results/batch25/thread-churn/arena2/rep3/malloc_info_thread-churn_14752_measure.xml`
- `board_results/batch25/thread-churn/arena2/rep3/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena2/rep3/pull.log`
- `board_results/batch25/thread-churn/arena2/rep3/result.json`
- `board_results/batch25/thread-churn/arena2/rep3/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep3/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena2/rep3/stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep3/thermal.txt`
- `board_results/batch25/thread-churn/arena2/rep4/cmd.txt`
- `board_results/batch25/thread-churn/arena2/rep4/exit_code.txt`
- `board_results/batch25/thread-churn/arena2/rep4/malloc_info_thread-churn_16015_idle.xml`
- `board_results/batch25/thread-churn/arena2/rep4/malloc_info_thread-churn_16015_measure.xml`
- `board_results/batch25/thread-churn/arena2/rep4/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena2/rep4/pull.log`
- `board_results/batch25/thread-churn/arena2/rep4/result.json`
- `board_results/batch25/thread-churn/arena2/rep4/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep4/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena2/rep4/stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep4/thermal.txt`
- `board_results/batch25/thread-churn/arena2/rep5/cmd.txt`
- `board_results/batch25/thread-churn/arena2/rep5/exit_code.txt`
- `board_results/batch25/thread-churn/arena2/rep5/malloc_info_thread-churn_17279_idle.xml`
- `board_results/batch25/thread-churn/arena2/rep5/malloc_info_thread-churn_17279_measure.xml`
- `board_results/batch25/thread-churn/arena2/rep5/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena2/rep5/pull.log`
- `board_results/batch25/thread-churn/arena2/rep5/result.json`
- `board_results/batch25/thread-churn/arena2/rep5/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep5/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena2/rep5/stderr.txt`
- `board_results/batch25/thread-churn/arena2/rep5/thermal.txt`
- `board_results/batch25/thread-churn/arena3/rep1/cmd.txt`
- `board_results/batch25/thread-churn/arena3/rep1/exit_code.txt`
- `board_results/batch25/thread-churn/arena3/rep1/malloc_info_thread-churn_18774_idle.xml`
- `board_results/batch25/thread-churn/arena3/rep1/malloc_info_thread-churn_18774_measure.xml`
- `board_results/batch25/thread-churn/arena3/rep1/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena3/rep1/pull.log`
- `board_results/batch25/thread-churn/arena3/rep1/result.json`
- `board_results/batch25/thread-churn/arena3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena3/rep1/stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep1/thermal.txt`
- `board_results/batch25/thread-churn/arena3/rep2/cmd.txt`
- `board_results/batch25/thread-churn/arena3/rep2/exit_code.txt`
- `board_results/batch25/thread-churn/arena3/rep2/malloc_info_thread-churn_20037_idle.xml`
- `board_results/batch25/thread-churn/arena3/rep2/malloc_info_thread-churn_20037_measure.xml`
- `board_results/batch25/thread-churn/arena3/rep2/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena3/rep2/pull.log`
- `board_results/batch25/thread-churn/arena3/rep2/result.json`
- `board_results/batch25/thread-churn/arena3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena3/rep2/stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep2/thermal.txt`
- `board_results/batch25/thread-churn/arena3/rep3/cmd.txt`
- `board_results/batch25/thread-churn/arena3/rep3/exit_code.txt`
- `board_results/batch25/thread-churn/arena3/rep3/malloc_info_thread-churn_21298_idle.xml`
- `board_results/batch25/thread-churn/arena3/rep3/malloc_info_thread-churn_21298_measure.xml`
- `board_results/batch25/thread-churn/arena3/rep3/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena3/rep3/pull.log`
- `board_results/batch25/thread-churn/arena3/rep3/result.json`
- `board_results/batch25/thread-churn/arena3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena3/rep3/stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep3/thermal.txt`
- `board_results/batch25/thread-churn/arena3/rep4/cmd.txt`
- `board_results/batch25/thread-churn/arena3/rep4/exit_code.txt`
- `board_results/batch25/thread-churn/arena3/rep4/malloc_info_thread-churn_22613_idle.xml`
- `board_results/batch25/thread-churn/arena3/rep4/malloc_info_thread-churn_22613_measure.xml`
- `board_results/batch25/thread-churn/arena3/rep4/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena3/rep4/pull.log`
- `board_results/batch25/thread-churn/arena3/rep4/result.json`
- `board_results/batch25/thread-churn/arena3/rep4/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep4/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena3/rep4/stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep4/thermal.txt`
- `board_results/batch25/thread-churn/arena3/rep5/cmd.txt`
- `board_results/batch25/thread-churn/arena3/rep5/exit_code.txt`
- `board_results/batch25/thread-churn/arena3/rep5/malloc_info_thread-churn_23872_idle.xml`
- `board_results/batch25/thread-churn/arena3/rep5/malloc_info_thread-churn_23872_measure.xml`
- `board_results/batch25/thread-churn/arena3/rep5/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena3/rep5/pull.log`
- `board_results/batch25/thread-churn/arena3/rep5/result.json`
- `board_results/batch25/thread-churn/arena3/rep5/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep5/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena3/rep5/stderr.txt`
- `board_results/batch25/thread-churn/arena3/rep5/thermal.txt`
- `board_results/batch25/thread-churn/arena4/rep1/cmd.txt`
- `board_results/batch25/thread-churn/arena4/rep1/exit_code.txt`
- `board_results/batch25/thread-churn/arena4/rep1/malloc_info_thread-churn_25355_idle.xml`
- `board_results/batch25/thread-churn/arena4/rep1/malloc_info_thread-churn_25355_measure.xml`
- `board_results/batch25/thread-churn/arena4/rep1/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena4/rep1/pull.log`
- `board_results/batch25/thread-churn/arena4/rep1/result.json`
- `board_results/batch25/thread-churn/arena4/rep1/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep1/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena4/rep1/stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep1/thermal.txt`
- `board_results/batch25/thread-churn/arena4/rep2/cmd.txt`
- `board_results/batch25/thread-churn/arena4/rep2/exit_code.txt`
- `board_results/batch25/thread-churn/arena4/rep2/malloc_info_thread-churn_26616_idle.xml`
- `board_results/batch25/thread-churn/arena4/rep2/malloc_info_thread-churn_26616_measure.xml`
- `board_results/batch25/thread-churn/arena4/rep2/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena4/rep2/pull.log`
- `board_results/batch25/thread-churn/arena4/rep2/result.json`
- `board_results/batch25/thread-churn/arena4/rep2/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep2/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena4/rep2/stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep2/thermal.txt`
- `board_results/batch25/thread-churn/arena4/rep3/cmd.txt`
- `board_results/batch25/thread-churn/arena4/rep3/exit_code.txt`
- `board_results/batch25/thread-churn/arena4/rep3/malloc_info_thread-churn_27872_idle.xml`
- `board_results/batch25/thread-churn/arena4/rep3/malloc_info_thread-churn_27872_measure.xml`
- `board_results/batch25/thread-churn/arena4/rep3/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena4/rep3/pull.log`
- `board_results/batch25/thread-churn/arena4/rep3/result.json`
- `board_results/batch25/thread-churn/arena4/rep3/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep3/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena4/rep3/stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep3/thermal.txt`
- `board_results/batch25/thread-churn/arena4/rep4/cmd.txt`
- `board_results/batch25/thread-churn/arena4/rep4/exit_code.txt`
- `board_results/batch25/thread-churn/arena4/rep4/malloc_info_thread-churn_29130_idle.xml`
- `board_results/batch25/thread-churn/arena4/rep4/malloc_info_thread-churn_29130_measure.xml`
- `board_results/batch25/thread-churn/arena4/rep4/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena4/rep4/pull.log`
- `board_results/batch25/thread-churn/arena4/rep4/result.json`
- `board_results/batch25/thread-churn/arena4/rep4/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep4/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena4/rep4/stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep4/thermal.txt`
- `board_results/batch25/thread-churn/arena4/rep5/cmd.txt`
- `board_results/batch25/thread-churn/arena4/rep5/exit_code.txt`
- `board_results/batch25/thread-churn/arena4/rep5/malloc_info_thread-churn_30392_idle.xml`
- `board_results/batch25/thread-churn/arena4/rep5/malloc_info_thread-churn_30392_measure.xml`
- `board_results/batch25/thread-churn/arena4/rep5/mkdir_remote.log`
- `board_results/batch25/thread-churn/arena4/rep5/pull.log`
- `board_results/batch25/thread-churn/arena4/rep5/result.json`
- `board_results/batch25/thread-churn/arena4/rep5/sdb_run_stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep5/sdb_run_stdout.txt`
- `board_results/batch25/thread-churn/arena4/rep5/stderr.txt`
- `board_results/batch25/thread-churn/arena4/rep5/thermal.txt`
- `board_results/batch25/uname.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/cmd.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/exit_code.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/malloc_info_unsorted-drain_13784_idle.xml`
- `board_results/batch25/unsorted-drain/C0/rep1/malloc_info_unsorted-drain_13784_measure.xml`
- `board_results/batch25/unsorted-drain/C0/rep1/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/C0/rep1/pull.log`
- `board_results/batch25/unsorted-drain/C0/rep1/result.json`
- `board_results/batch25/unsorted-drain/C0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep1/thermal.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/cmd.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/exit_code.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/malloc_info_unsorted-drain_14963_idle.xml`
- `board_results/batch25/unsorted-drain/C0/rep2/malloc_info_unsorted-drain_14963_measure.xml`
- `board_results/batch25/unsorted-drain/C0/rep2/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/C0/rep2/pull.log`
- `board_results/batch25/unsorted-drain/C0/rep2/result.json`
- `board_results/batch25/unsorted-drain/C0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep2/thermal.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/cmd.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/exit_code.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/malloc_info_unsorted-drain_16144_idle.xml`
- `board_results/batch25/unsorted-drain/C0/rep3/malloc_info_unsorted-drain_16144_measure.xml`
- `board_results/batch25/unsorted-drain/C0/rep3/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/C0/rep3/pull.log`
- `board_results/batch25/unsorted-drain/C0/rep3/result.json`
- `board_results/batch25/unsorted-drain/C0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/stderr.txt`
- `board_results/batch25/unsorted-drain/C0/rep3/thermal.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/cmd.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/exit_code.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/malloc_info_unsorted-drain_17329_idle.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/malloc_info_unsorted-drain_17329_measure.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/pull.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/result.json`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep1/thermal.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/cmd.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/exit_code.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/malloc_info_unsorted-drain_18512_idle.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/malloc_info_unsorted-drain_18512_measure.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/pull.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/result.json`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep2/thermal.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/cmd.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/exit_code.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/malloc_info_unsorted-drain_19693_idle.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/malloc_info_unsorted-drain_19693_measure.xml`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/pull.log`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/result.json`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/stderr.txt`
- `board_results/batch25/unsorted-drain/mxfast0/rep3/thermal.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/cmd.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/exit_code.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/malloc_info_unsorted-drain_20873_idle.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/malloc_info_unsorted-drain_20873_measure.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/pull.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/result.json`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep1/thermal.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/cmd.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/exit_code.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/malloc_info_unsorted-drain_22092_idle.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/malloc_info_unsorted-drain_22092_measure.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/pull.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/result.json`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep2/thermal.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/cmd.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/exit_code.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/malloc_info_unsorted-drain_23287_idle.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/malloc_info_unsorted-drain_23287_measure.xml`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/mkdir_remote.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/pull.log`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/result.json`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/sdb_run_stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/sdb_run_stdout.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/stderr.txt`
- `board_results/batch25/unsorted-drain/tcache_unsorted3/rep3/thermal.txt`
