> Public archive note: application/process names are aliases and board identifiers are sanitized. Referenced raw evidence under `board_results/` is retained locally and is not published.

# alloc_bench Batch 2 board run report

## Header

- Date: 2026-07-08 Asia/Shanghai; run window from `2026-07-08T21:47:53+08:00` to `2026-07-08T23:13:04+08:00` per `board_results/batch2/host_run.log`.
- Board IP: `<TEST_BOARD_IP>`.
- sdb path: `<USER_HOME>/tizen-studio/tools/sdb`.
- Remote execution directory: `/root` (`/root/alloc_bench.armv7l`, `/root/alloc_bench_batch2/...`) per board execution restriction.
- Result JSON count: `99`; run-summary data rows: `99`.
- Nonzero benchmark exit rows: `0`; JSON status not `ok`: `0`.

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

Governor restore evidence:

```text
RESTORE_DATE=2026-07-08T23:12:58+08:00
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor	schedutil

/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor	schedutil

/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor	schedutil

RESTORE:/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
--- verify ---
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
```

Independent final governor/tmp check:

```text
---GOV---
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
---ROOT-MATCH---
---TMP-MATCH---
```

Initial covariates (`vm.overcommit_memory`, `free`, `uptime`, thermal):

```text
---overcommit---
0
---free---
               total        used        free      shared  buff/cache   available
Mem:         3978536      183600     3537504        1504      302408     3794936
Swap:        1591412           0     1591412
---uptime---
 22:48:00 up  7:31,  1 user,  load average: 0.31, 0.19, 0.22
---thermal---
/sys/class/thermal/thermal_zone0/temp=34076
```

## Execution Notes

- Smoke command executed from `/root` with `env -u GLIBC_TUNABLES /root/alloc_bench.armv7l --profile small-churn --threads 2 --seed 1 --warmup 0 --ops-per-thread 1000 --idle 0 --outdir /root/alloc_batch2_smoke`.
- Smoke exit record:

```text
EXIT=0
0
```

- Pre-run inventory LIVE env hits: `0`, from summary below.

```text
/root/tizen_memopt_inventory.sh: line 49: /proc/30074/cmdline: No such file or directory
/root/tizen_memopt_inventory.sh: line 49: /proc/30075/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=52  AT_SECURE=1: 11  AT_SECURE=0: 41  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

## Run Summary Table

| profile | 格 | rep | 退出码 | throughput_ops_per_s | p50 | p99 | measure_rss_kb_median | idle_rss_kb | 运行前温度 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small-churn | C0 | 1 | 0 | 3225587.54 | 111 | 453 | 968 | 996 | 34563 |
| small-churn | C0 | 2 | 0 | 3227333.759 | 111 | 452 | 960 | 988 | 36511 |
| small-churn | C0 | 3 | 0 | 3229490.164 | 111 | 453 | 960 | 984 | 36998 |
| small-churn | T-L3 | 1 | 0 | 3222663.059 | 111 | 451 | 960 | 984 | 36511 |
| small-churn | T-L3 | 2 | 0 | 3226276.791 | 111 | 453 | 964 | 992 | 38459 |
| small-churn | T-L3 | 3 | 0 | 3156766.432 | 111 | 452 | 960 | 984 | 37972 |
| small-churn | T-L4a | 1 | 0 | 3155363.42 | 112 | 454 | 956 | 984 | 37485 |
| small-churn | T-L4a | 2 | 0 | 3156023.267 | 112 | 455 | 952 | 980 | 36998 |
| small-churn | T-L4a | 3 | 0 | 3150670.916 | 112 | 449 | 948 | 972 | 37972 |
| small-churn | T-L4b | 1 | 0 | 2902975.813 | 183 | 461 | 944 | 968 | 37485 |
| small-churn | T-L4b | 2 | 0 | 2900580.497 | 181 | 458 | 944 | 968 | 37972 |
| small-churn | T-L4b | 3 | 0 | 2901149.792 | 183 | 459 | 944 | 968 | 38459 |
| small-churn | T-L11 | 1 | 0 | 3220656.3 | 111 | 410 | 960 | 984 | 37485 |
| small-churn | T-L11 | 2 | 0 | 3221760.437 | 111 | 406 | 960 | 988 | 37485 |
| small-churn | T-L11 | 3 | 0 | 3127587.831 | 111 | 405 | 960 | 984 | 37972 |
| small-churn | T-L12 | 1 | 0 | 3226247.514 | 111 | 450 | 960 | 988 | 37972 |
| small-churn | T-L12 | 2 | 0 | 3132334.711 | 111 | 448 | 964 | 992 | 37972 |
| small-churn | T-L12 | 3 | 0 | 3220562.214 | 111 | 450 | 960 | 988 | 37972 |
| small-churn | T-L2 | 1 | 0 | 3146528.627 | 112 | 638 | 944 | 960 | 36998 |
| small-churn | T-L2 | 2 | 0 | 3159956.525 | 111 | 640 | 940 | 964 | 38946 |
| small-churn | T-L2 | 3 | 0 | 3160118.4 | 111 | 643 | 948 | 964 | 37972 |
| small-churn | T-B1 | 1 | 0 | 3159429.809 | 111 | 632 | 948 | 964 | 36998 |
| small-churn | T-B1 | 2 | 0 | 3159376.783 | 112 | 623 | 944 | 960 | 37972 |
| small-churn | T-B1 | 3 | 0 | 3134898.528 | 112 | 670 | 944 | 960 | 37972 |
| mixed | C0 | 1 | 0 | 2149401.274 | 250 | 1174 | 114508 | 114544 | 36998 |
| mixed | C0 | 2 | 0 | 2156430.793 | 249 | 1172 | 115176 | 115212 | 37485 |
| mixed | C0 | 3 | 0 | 2158741.366 | 245 | 1168 | 115488 | 115524 | 37485 |
| mixed | T-L3 | 1 | 0 | 2155256.818 | 250 | 1170 | 112544 | 112580 | 37972 |
| mixed | T-L3 | 2 | 0 | 2154860.121 | 254 | 1178 | 115208 | 115244 | 37485 |
| mixed | T-L3 | 3 | 0 | 2149950.686 | 247 | 1173 | 113496 | 113532 | 37485 |
| mixed | T-L4a | 1 | 0 | 2106398.975 | 272 | 1162 | 115328 | 115364 | 37972 |
| mixed | T-L4a | 2 | 0 | 2071469.464 | 266 | 1145 | 113452 | 113488 | 36998 |
| mixed | T-L4a | 3 | 0 | 2117006.979 | 265 | 1152 | 114560 | 114596 | 37485 |
| mixed | T-L4b | 1 | 0 | 1979554.717 | 318 | 1213 | 115788 | 115824 | 36998 |
| mixed | T-L4b | 2 | 0 | 1983165.703 | 317 | 1209 | 115344 | 115380 | 37972 |
| mixed | T-L4b | 3 | 0 | 1979512.707 | 318 | 1214 | 114684 | 114720 | 37972 |
| mixed | T-L11 | 1 | 0 | 2147057.683 | 253 | 1156 | 112644 | 112680 | 38946 |
| mixed | T-L11 | 2 | 0 | 2156335.452 | 249 | 1148 | 114692 | 114728 | 38459 |
| mixed | T-L11 | 3 | 0 | 2145316.442 | 249 | 1142 | 114804 | 114840 | 36998 |
| mixed | T-L12 | 1 | 0 | 2150095.584 | 251 | 1178 | 114552 | 114588 | 37485 |
| mixed | T-L12 | 2 | 0 | 2152263.965 | 253 | 1179 | 114264 | 114300 | 37485 |
| mixed | T-L12 | 3 | 0 | 2154626.856 | 244 | 1167 | 114452 | 114488 | 36998 |
| mixed | T-L2 | 1 | 0 | 1018058.051 | 285 | 26700 | 105316 | 105328 | 37972 |
| mixed | T-L2 | 2 | 0 | 1013340.329 | 291 | 26902 | 105920 | 105932 | 37485 |
| mixed | T-L2 | 3 | 0 | 1135574.556 | 422 | 17486 | 108376 | 108388 | 36998 |
| mixed | T-B1 | 1 | 0 | 1122987.391 | 423 | 17749 | 108572 | 108584 | 37972 |
| mixed | T-B1 | 2 | 0 | 1130040.035 | 423 | 17577 | 108424 | 108436 | 37972 |
| mixed | T-B1 | 3 | 0 | 1131166.456 | 416 | 17701 | 109172 | 109184 | 36998 |
| large-transient | C0 | 1 | 0 | 1405876.008 | 294 | 29477 | 115388 | 115424 | 36998 |
| large-transient | C0 | 2 | 0 | 1402009.469 | 287 | 29355 | 114440 | 114476 | 36998 |
| large-transient | C0 | 3 | 0 | 1386668.497 | 287 | 29439 | 114620 | 114688 | 36998 |
| large-transient | T-L3 | 1 | 0 | 1332664.171 | 290 | 32640 | 113676 | 113712 | 36998 |
| large-transient | T-L3 | 2 | 0 | 1340250.846 | 300 | 31072 | 112928 | 112964 | 36511 |
| large-transient | T-L3 | 3 | 0 | 1329736.606 | 297 | 31241 | 114080 | 114116 | 37485 |
| large-transient | T-L4a | 1 | 0 | 1373177.958 | 305 | 30666 | 115508 | 115544 | 35537 |
| large-transient | T-L4a | 2 | 0 | 1378283.601 | 306 | 30113 | 114784 | 114820 | 37485 |
| large-transient | T-L4a | 3 | 0 | 1389958.941 | 313 | 28553 | 114636 | 114672 | 36024 |
| large-transient | T-L4b | 1 | 0 | 1321560.014 | 359 | 30006 | 115860 | 115896 | 36511 |
| large-transient | T-L4b | 2 | 0 | 1343888.556 | 350 | 30819 | 115040 | 115076 | 36998 |
| large-transient | T-L4b | 3 | 0 | 1313497.533 | 368 | 30162 | 114668 | 114704 | 36024 |
| large-transient | T-L11 | 1 | 0 | 1394107.25 | 286 | 30543 | 115548 | 115584 | 36024 |
| large-transient | T-L11 | 2 | 0 | 1394628.44 | 286 | 29429 | 114280 | 114316 | 36511 |
| large-transient | T-L11 | 3 | 0 | 1396526.179 | 286 | 29608 | 114620 | 114656 | 37485 |
| large-transient | T-L12 | 1 | 0 | 1404586.119 | 289 | 28321 | 115452 | 115488 | 36998 |
| large-transient | T-L12 | 2 | 0 | 1369632.678 | 293 | 30583 | 114524 | 114560 | 36998 |
| large-transient | T-L12 | 3 | 0 | 1393383.12 | 297 | 29758 | 115240 | 115276 | 36511 |
| large-transient | T-L2 | 1 | 0 | 775583.103 | 339 | 35525 | 105156 | 105168 | 36998 |
| large-transient | T-L2 | 2 | 0 | 887203.429 | 422 | 35224 | 109444 | 109456 | 36024 |
| large-transient | T-L2 | 3 | 0 | 772146.974 | 325 | 34522 | 105404 | 105416 | 36024 |
| large-transient | T-B1 | 1 | 0 | 878079.625 | 433 | 33764 | 108640 | 108652 | 36511 |
| large-transient | T-B1 | 2 | 0 | 865374.231 | 435 | 36185 | 108248 | 108260 | 35537 |
| large-transient | T-B1 | 3 | 0 | 757602.411 | 328 | 36257 | 105532 | 105544 | 36511 |
| thread-churn | C0 | 1 | 0 | 1895411.318 | 251 | 1481 | 73784 | 73816 | 35537 |
| thread-churn | C0 | 2 | 0 | 1889923.251 | 248 | 1487 | 73800 | 73832 | 36511 |
| thread-churn | C0 | 3 | 0 | 1895265.335 | 249 | 1476 | 73684 | 73716 | 36024 |
| thread-churn | T-L3 | 1 | 0 | 1888709.607 | 249 | 1485 | 73696 | 73728 | 37972 |
| thread-churn | T-L3 | 2 | 0 | 1890974.241 | 251 | 1481 | 73388 | 73420 | 36998 |
| thread-churn | T-L3 | 3 | 0 | 1894861.902 | 249 | 1474 | 73576 | 73608 | 36511 |
| thread-churn | T-L4a | 1 | 0 | 1859295.484 | 271 | 1440 | 74976 | 75008 | 37485 |
| thread-churn | T-L4a | 2 | 0 | 1865342.011 | 274 | 1434 | 75544 | 75576 | 36998 |
| thread-churn | T-L4a | 3 | 0 | 1861369.12 | 274 | 1426 | 74612 | 74644 | 36511 |
| thread-churn | T-L4b | 1 | 0 | 1750984.849 | 319 | 1484 | 75496 | 75528 | 36511 |
| thread-churn | T-L4b | 2 | 0 | 1749437.628 | 318 | 1509 | 75388 | 75420 | 36998 |
| thread-churn | T-L4b | 3 | 0 | 1747975.369 | 320 | 1496 | 75388 | 75420 | 36998 |
| thread-churn | T-L11 | 1 | 0 | 1901503.637 | 245 | 1495 | 74944 | 74976 | 36998 |
| thread-churn | T-L11 | 2 | 0 | 1899314.938 | 248 | 1503 | 74884 | 74916 | 36998 |
| thread-churn | T-L11 | 3 | 0 | 1894855.652 | 248 | 1496 | 75028 | 75060 | 36998 |
| thread-churn | T-L12 | 1 | 0 | 1894650.008 | 248 | 1474 | 73680 | 73712 | 37485 |
| thread-churn | T-L12 | 2 | 0 | 1895695.282 | 250 | 1481 | 74096 | 74128 | 36998 |
| thread-churn | T-L12 | 3 | 0 | 1898993.732 | 251 | 1475 | 74100 | 74132 | 36998 |
| thread-churn | T-L2 | 1 | 0 | 1032507.205 | 357 | 20252 | 100228 | 100236 | 36511 |
| thread-churn | T-L2 | 2 | 0 | 1030451.033 | 375 | 19397 | 92700 | 92708 | 36511 |
| thread-churn | T-L2 | 3 | 0 | 1046441.057 | 393 | 18302 | 81044 | 81052 | 36511 |
| thread-churn | T-B1 | 1 | 0 | 1068269.155 | 393 | 18135 | 116168 | 116176 | 36511 |
| thread-churn | T-B1 | 2 | 0 | 1022770.723 | 357 | 20917 | 104696 | 104704 | 36024 |
| thread-churn | T-B1 | 3 | 0 | 1064355.58 | 393 | 18296 | 106672 | 106680 | 36511 |
| thread-churn | T-L1 | 1 | 0 | 1895780.165 | 253 | 1479 | 70696 | 70728 | 35537 |
| thread-churn | T-L1 | 2 | 0 | 1898762.826 | 247 | 1472 | 72748 | 72780 | 37485 |
| thread-churn | T-L1 | 3 | 0 | 1895215.591 | 249 | 1483 | 72864 | 72896 | 37485 |

## 异常清单

- `board_results/batch2/exceptions.log` is empty.
- `board_results/batch2/thermal_waits.log` is absent/empty; no thermal wait event was logged by the harness.
- Nonzero exit rows in `run_summary.tsv`: `0`.
- JSON status not `ok` rows in `run_summary.tsv`: `0`.

Pre-final archived attempts, not part of the 99-row matrix:

```text
board_results/batch2_tmp_permission_failure_20260708T214536
  smoke/run.log: EXIT=126
  smoke/stderr.txt: env: /tmp/alloc_bench.armv7l: Permission denied

board_results/batch2_harness_smoke_exit_format_20260708T214724
  host_run.log: smoke failed: exit code EXIT=0
  smoke/run.log: EXIT=0
  smoke/exit_code.txt: EXIT=0
```

## 恢复现场证据

Post-run inventory summary:

```text
/root/tizen_memopt_inventory.sh: line 49: /proc/22677/cmdline: No such file or directory
/root/tizen_memopt_inventory.sh: line 49: /proc/22679/cmdline: No such file or directory
=== G1/G2/Q7 inventory summary ===
overcommit_memory=0  thp=NA
processes=53  AT_SECURE=1: 12  AT_SECURE=0: 41  unknown: 0
processes with LIVE env blacklist hits: 0
VERDICT HINT: majority non-secure -> Tier 1/2 env levers viable
```

Board cleanup listing from harness:

```text
---ROOT---
total 28
dr-xr-x---  3 root root  4096 Jul  9 00:13 .
drwxr-xr-x 17 root root  4096 Jul  8 15:31 ..
drwx------  3 root root  4096 Jul  8 20:37 .config
-rwxrwxrwx  1 root root 12496 Jul  8 14:43 setup_zypper.sh
---TMP---
total 8
-rw-r--r-- 1 location  location 28 Jan  1  1970 dump_gps.log
drwxrwxrwx 2 owner     users    80 Jan  1  1970 focus
prw-rw-rw- 1 pulse     pulse     0 Jan  1  1970 keytone
drwxrwxrwt 2 root      users    40 Jan  1  1970 pkgmgr
-rw-r--r-- 1 root      root      0 Jan  1  1970 rsc_mgr_ready
-rw-r----- 1 root      root      0 Jan  1  1970 sm-cleanup-tmp-flag
drwx------ 3 root      root     60 Jan  1  1970 systemd-private-b2a783b8ff4443e3a14b4e722dc1dd0e-systemd-logind.service-g4fihM
-rw-rw-r-- 1 system_fw users     8 Jan  1  1970 ttrace_tag
```

Independent final check:

```text
---GOV---
/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu1/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor=schedutil
/sys/devices/system/cpu/cpu3/cpufreq/scaling_governor=schedutil
---ROOT-MATCH---
---TMP-MATCH---
```

## Raw File Paths

Total files under `board_results/batch2`: `1131`.

```text
board_results/batch2/chmod_binary.log
board_results/batch2/exceptions.log
board_results/batch2/governor/after_set.log
board_results/batch2/governor/original_raw.txt
board_results/batch2/governor/set_performance.log
board_results/batch2/governor_original.tsv
board_results/batch2/host_run.log
board_results/batch2/initial/covariates.txt
board_results/batch2/large-transient/C0/rep1/cmd.txt
board_results/batch2/large-transient/C0/rep1/exit_code.txt
board_results/batch2/large-transient/C0/rep1/malloc_info_large-transient_24536_idle.xml
board_results/batch2/large-transient/C0/rep1/malloc_info_large-transient_24536_measure.xml
board_results/batch2/large-transient/C0/rep1/mkdir_remote.log
board_results/batch2/large-transient/C0/rep1/pull.log
board_results/batch2/large-transient/C0/rep1/result.json
board_results/batch2/large-transient/C0/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/C0/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/C0/rep1/stderr.txt
board_results/batch2/large-transient/C0/rep1/thermal.txt
board_results/batch2/large-transient/C0/rep2/cmd.txt
board_results/batch2/large-transient/C0/rep2/exit_code.txt
board_results/batch2/large-transient/C0/rep2/malloc_info_large-transient_25730_idle.xml
board_results/batch2/large-transient/C0/rep2/malloc_info_large-transient_25730_measure.xml
board_results/batch2/large-transient/C0/rep2/mkdir_remote.log
board_results/batch2/large-transient/C0/rep2/pull.log
board_results/batch2/large-transient/C0/rep2/result.json
board_results/batch2/large-transient/C0/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/C0/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/C0/rep2/stderr.txt
board_results/batch2/large-transient/C0/rep2/thermal.txt
board_results/batch2/large-transient/C0/rep3/cmd.txt
board_results/batch2/large-transient/C0/rep3/exit_code.txt
board_results/batch2/large-transient/C0/rep3/malloc_info_large-transient_26922_idle.xml
board_results/batch2/large-transient/C0/rep3/malloc_info_large-transient_26922_measure.xml
board_results/batch2/large-transient/C0/rep3/mkdir_remote.log
board_results/batch2/large-transient/C0/rep3/pull.log
board_results/batch2/large-transient/C0/rep3/result.json
board_results/batch2/large-transient/C0/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/C0/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/C0/rep3/stderr.txt
board_results/batch2/large-transient/C0/rep3/thermal.txt
board_results/batch2/large-transient/T-B1/rep1/cmd.txt
board_results/batch2/large-transient/T-B1/rep1/exit_code.txt
board_results/batch2/large-transient/T-B1/rep1/malloc_info_large-transient_17303_idle.xml
board_results/batch2/large-transient/T-B1/rep1/malloc_info_large-transient_17303_measure.xml
board_results/batch2/large-transient/T-B1/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-B1/rep1/pull.log
board_results/batch2/large-transient/T-B1/rep1/result.json
board_results/batch2/large-transient/T-B1/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-B1/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-B1/rep1/stderr.txt
board_results/batch2/large-transient/T-B1/rep1/thermal.txt
board_results/batch2/large-transient/T-B1/rep2/cmd.txt
board_results/batch2/large-transient/T-B1/rep2/exit_code.txt
board_results/batch2/large-transient/T-B1/rep2/malloc_info_large-transient_18503_idle.xml
board_results/batch2/large-transient/T-B1/rep2/malloc_info_large-transient_18503_measure.xml
board_results/batch2/large-transient/T-B1/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-B1/rep2/pull.log
board_results/batch2/large-transient/T-B1/rep2/result.json
board_results/batch2/large-transient/T-B1/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-B1/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-B1/rep2/stderr.txt
board_results/batch2/large-transient/T-B1/rep2/thermal.txt
board_results/batch2/large-transient/T-B1/rep3/cmd.txt
board_results/batch2/large-transient/T-B1/rep3/exit_code.txt
board_results/batch2/large-transient/T-B1/rep3/malloc_info_large-transient_19701_idle.xml
board_results/batch2/large-transient/T-B1/rep3/malloc_info_large-transient_19701_measure.xml
board_results/batch2/large-transient/T-B1/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-B1/rep3/pull.log
board_results/batch2/large-transient/T-B1/rep3/result.json
board_results/batch2/large-transient/T-B1/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-B1/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-B1/rep3/stderr.txt
board_results/batch2/large-transient/T-B1/rep3/thermal.txt
board_results/batch2/large-transient/T-L11/rep1/cmd.txt
board_results/batch2/large-transient/T-L11/rep1/exit_code.txt
board_results/batch2/large-transient/T-L11/rep1/malloc_info_large-transient_6548_idle.xml
board_results/batch2/large-transient/T-L11/rep1/malloc_info_large-transient_6548_measure.xml
board_results/batch2/large-transient/T-L11/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L11/rep1/pull.log
board_results/batch2/large-transient/T-L11/rep1/result.json
board_results/batch2/large-transient/T-L11/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L11/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L11/rep1/stderr.txt
board_results/batch2/large-transient/T-L11/rep1/thermal.txt
board_results/batch2/large-transient/T-L11/rep2/cmd.txt
board_results/batch2/large-transient/T-L11/rep2/exit_code.txt
board_results/batch2/large-transient/T-L11/rep2/malloc_info_large-transient_7741_idle.xml
board_results/batch2/large-transient/T-L11/rep2/malloc_info_large-transient_7741_measure.xml
board_results/batch2/large-transient/T-L11/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L11/rep2/pull.log
board_results/batch2/large-transient/T-L11/rep2/result.json
board_results/batch2/large-transient/T-L11/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L11/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L11/rep2/stderr.txt
board_results/batch2/large-transient/T-L11/rep2/thermal.txt
board_results/batch2/large-transient/T-L11/rep3/cmd.txt
board_results/batch2/large-transient/T-L11/rep3/exit_code.txt
board_results/batch2/large-transient/T-L11/rep3/malloc_info_large-transient_8933_idle.xml
board_results/batch2/large-transient/T-L11/rep3/malloc_info_large-transient_8933_measure.xml
board_results/batch2/large-transient/T-L11/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L11/rep3/pull.log
board_results/batch2/large-transient/T-L11/rep3/result.json
board_results/batch2/large-transient/T-L11/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L11/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L11/rep3/stderr.txt
board_results/batch2/large-transient/T-L11/rep3/thermal.txt
board_results/batch2/large-transient/T-L12/rep1/cmd.txt
board_results/batch2/large-transient/T-L12/rep1/exit_code.txt
board_results/batch2/large-transient/T-L12/rep1/malloc_info_large-transient_10127_idle.xml
board_results/batch2/large-transient/T-L12/rep1/malloc_info_large-transient_10127_measure.xml
board_results/batch2/large-transient/T-L12/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L12/rep1/pull.log
board_results/batch2/large-transient/T-L12/rep1/result.json
board_results/batch2/large-transient/T-L12/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L12/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L12/rep1/stderr.txt
board_results/batch2/large-transient/T-L12/rep1/thermal.txt
board_results/batch2/large-transient/T-L12/rep2/cmd.txt
board_results/batch2/large-transient/T-L12/rep2/exit_code.txt
board_results/batch2/large-transient/T-L12/rep2/malloc_info_large-transient_11322_idle.xml
board_results/batch2/large-transient/T-L12/rep2/malloc_info_large-transient_11322_measure.xml
board_results/batch2/large-transient/T-L12/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L12/rep2/pull.log
board_results/batch2/large-transient/T-L12/rep2/result.json
board_results/batch2/large-transient/T-L12/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L12/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L12/rep2/stderr.txt
board_results/batch2/large-transient/T-L12/rep2/thermal.txt
board_results/batch2/large-transient/T-L12/rep3/cmd.txt
board_results/batch2/large-transient/T-L12/rep3/exit_code.txt
board_results/batch2/large-transient/T-L12/rep3/malloc_info_large-transient_12522_idle.xml
board_results/batch2/large-transient/T-L12/rep3/malloc_info_large-transient_12522_measure.xml
board_results/batch2/large-transient/T-L12/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L12/rep3/pull.log
board_results/batch2/large-transient/T-L12/rep3/result.json
board_results/batch2/large-transient/T-L12/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L12/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L12/rep3/stderr.txt
board_results/batch2/large-transient/T-L12/rep3/thermal.txt
board_results/batch2/large-transient/T-L2/rep1/cmd.txt
board_results/batch2/large-transient/T-L2/rep1/exit_code.txt
board_results/batch2/large-transient/T-L2/rep1/malloc_info_large-transient_13717_idle.xml
board_results/batch2/large-transient/T-L2/rep1/malloc_info_large-transient_13717_measure.xml
board_results/batch2/large-transient/T-L2/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L2/rep1/pull.log
board_results/batch2/large-transient/T-L2/rep1/result.json
board_results/batch2/large-transient/T-L2/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L2/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L2/rep1/stderr.txt
board_results/batch2/large-transient/T-L2/rep1/thermal.txt
board_results/batch2/large-transient/T-L2/rep2/cmd.txt
board_results/batch2/large-transient/T-L2/rep2/exit_code.txt
board_results/batch2/large-transient/T-L2/rep2/malloc_info_large-transient_14914_idle.xml
board_results/batch2/large-transient/T-L2/rep2/malloc_info_large-transient_14914_measure.xml
board_results/batch2/large-transient/T-L2/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L2/rep2/pull.log
board_results/batch2/large-transient/T-L2/rep2/result.json
board_results/batch2/large-transient/T-L2/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L2/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L2/rep2/stderr.txt
board_results/batch2/large-transient/T-L2/rep2/thermal.txt
board_results/batch2/large-transient/T-L2/rep3/cmd.txt
board_results/batch2/large-transient/T-L2/rep3/exit_code.txt
board_results/batch2/large-transient/T-L2/rep3/malloc_info_large-transient_16110_idle.xml
board_results/batch2/large-transient/T-L2/rep3/malloc_info_large-transient_16110_measure.xml
board_results/batch2/large-transient/T-L2/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L2/rep3/pull.log
board_results/batch2/large-transient/T-L2/rep3/result.json
board_results/batch2/large-transient/T-L2/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L2/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L2/rep3/stderr.txt
board_results/batch2/large-transient/T-L2/rep3/thermal.txt
board_results/batch2/large-transient/T-L3/rep1/cmd.txt
board_results/batch2/large-transient/T-L3/rep1/exit_code.txt
board_results/batch2/large-transient/T-L3/rep1/malloc_info_large-transient_28115_idle.xml
board_results/batch2/large-transient/T-L3/rep1/malloc_info_large-transient_28115_measure.xml
board_results/batch2/large-transient/T-L3/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L3/rep1/pull.log
board_results/batch2/large-transient/T-L3/rep1/result.json
board_results/batch2/large-transient/T-L3/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L3/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L3/rep1/stderr.txt
board_results/batch2/large-transient/T-L3/rep1/thermal.txt
board_results/batch2/large-transient/T-L3/rep2/cmd.txt
board_results/batch2/large-transient/T-L3/rep2/exit_code.txt
board_results/batch2/large-transient/T-L3/rep2/malloc_info_large-transient_29309_idle.xml
board_results/batch2/large-transient/T-L3/rep2/malloc_info_large-transient_29309_measure.xml
board_results/batch2/large-transient/T-L3/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L3/rep2/pull.log
board_results/batch2/large-transient/T-L3/rep2/result.json
board_results/batch2/large-transient/T-L3/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L3/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L3/rep2/stderr.txt
board_results/batch2/large-transient/T-L3/rep2/thermal.txt
board_results/batch2/large-transient/T-L3/rep3/cmd.txt
board_results/batch2/large-transient/T-L3/rep3/exit_code.txt
board_results/batch2/large-transient/T-L3/rep3/malloc_info_large-transient_30503_idle.xml
board_results/batch2/large-transient/T-L3/rep3/malloc_info_large-transient_30503_measure.xml
board_results/batch2/large-transient/T-L3/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L3/rep3/pull.log
board_results/batch2/large-transient/T-L3/rep3/result.json
board_results/batch2/large-transient/T-L3/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L3/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L3/rep3/stderr.txt
board_results/batch2/large-transient/T-L3/rep3/thermal.txt
board_results/batch2/large-transient/T-L4a/rep1/cmd.txt
board_results/batch2/large-transient/T-L4a/rep1/exit_code.txt
board_results/batch2/large-transient/T-L4a/rep1/malloc_info_large-transient_31697_idle.xml
board_results/batch2/large-transient/T-L4a/rep1/malloc_info_large-transient_31697_measure.xml
board_results/batch2/large-transient/T-L4a/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L4a/rep1/pull.log
board_results/batch2/large-transient/T-L4a/rep1/result.json
board_results/batch2/large-transient/T-L4a/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4a/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4a/rep1/stderr.txt
board_results/batch2/large-transient/T-L4a/rep1/thermal.txt
board_results/batch2/large-transient/T-L4a/rep2/cmd.txt
board_results/batch2/large-transient/T-L4a/rep2/exit_code.txt
board_results/batch2/large-transient/T-L4a/rep2/malloc_info_large-transient_459_idle.xml
board_results/batch2/large-transient/T-L4a/rep2/malloc_info_large-transient_459_measure.xml
board_results/batch2/large-transient/T-L4a/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L4a/rep2/pull.log
board_results/batch2/large-transient/T-L4a/rep2/result.json
board_results/batch2/large-transient/T-L4a/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4a/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4a/rep2/stderr.txt
board_results/batch2/large-transient/T-L4a/rep2/thermal.txt
board_results/batch2/large-transient/T-L4a/rep3/cmd.txt
board_results/batch2/large-transient/T-L4a/rep3/exit_code.txt
board_results/batch2/large-transient/T-L4a/rep3/malloc_info_large-transient_1768_idle.xml
board_results/batch2/large-transient/T-L4a/rep3/malloc_info_large-transient_1768_measure.xml
board_results/batch2/large-transient/T-L4a/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L4a/rep3/pull.log
board_results/batch2/large-transient/T-L4a/rep3/result.json
board_results/batch2/large-transient/T-L4a/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4a/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4a/rep3/stderr.txt
board_results/batch2/large-transient/T-L4a/rep3/thermal.txt
board_results/batch2/large-transient/T-L4b/rep1/cmd.txt
board_results/batch2/large-transient/T-L4b/rep1/exit_code.txt
board_results/batch2/large-transient/T-L4b/rep1/malloc_info_large-transient_2965_idle.xml
board_results/batch2/large-transient/T-L4b/rep1/malloc_info_large-transient_2965_measure.xml
board_results/batch2/large-transient/T-L4b/rep1/mkdir_remote.log
board_results/batch2/large-transient/T-L4b/rep1/pull.log
board_results/batch2/large-transient/T-L4b/rep1/result.json
board_results/batch2/large-transient/T-L4b/rep1/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4b/rep1/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4b/rep1/stderr.txt
board_results/batch2/large-transient/T-L4b/rep1/thermal.txt
board_results/batch2/large-transient/T-L4b/rep2/cmd.txt
board_results/batch2/large-transient/T-L4b/rep2/exit_code.txt
board_results/batch2/large-transient/T-L4b/rep2/malloc_info_large-transient_4162_idle.xml
board_results/batch2/large-transient/T-L4b/rep2/malloc_info_large-transient_4162_measure.xml
board_results/batch2/large-transient/T-L4b/rep2/mkdir_remote.log
board_results/batch2/large-transient/T-L4b/rep2/pull.log
board_results/batch2/large-transient/T-L4b/rep2/result.json
board_results/batch2/large-transient/T-L4b/rep2/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4b/rep2/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4b/rep2/stderr.txt
board_results/batch2/large-transient/T-L4b/rep2/thermal.txt
board_results/batch2/large-transient/T-L4b/rep3/cmd.txt
board_results/batch2/large-transient/T-L4b/rep3/exit_code.txt
board_results/batch2/large-transient/T-L4b/rep3/malloc_info_large-transient_5354_idle.xml
board_results/batch2/large-transient/T-L4b/rep3/malloc_info_large-transient_5354_measure.xml
board_results/batch2/large-transient/T-L4b/rep3/mkdir_remote.log
board_results/batch2/large-transient/T-L4b/rep3/pull.log
board_results/batch2/large-transient/T-L4b/rep3/result.json
board_results/batch2/large-transient/T-L4b/rep3/sdb_run_stderr.txt
board_results/batch2/large-transient/T-L4b/rep3/sdb_run_stdout.txt
board_results/batch2/large-transient/T-L4b/rep3/stderr.txt
board_results/batch2/large-transient/T-L4b/rep3/thermal.txt
board_results/batch2/mixed/C0/rep1/cmd.txt
board_results/batch2/mixed/C0/rep1/exit_code.txt
board_results/batch2/mixed/C0/rep1/malloc_info_mixed_28114_idle.xml
board_results/batch2/mixed/C0/rep1/malloc_info_mixed_28114_measure.xml
board_results/batch2/mixed/C0/rep1/mkdir_remote.log
board_results/batch2/mixed/C0/rep1/pull.log
board_results/batch2/mixed/C0/rep1/result.json
board_results/batch2/mixed/C0/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/C0/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/C0/rep1/stderr.txt
board_results/batch2/mixed/C0/rep1/thermal.txt
board_results/batch2/mixed/C0/rep2/cmd.txt
board_results/batch2/mixed/C0/rep2/exit_code.txt
board_results/batch2/mixed/C0/rep2/malloc_info_mixed_29303_idle.xml
board_results/batch2/mixed/C0/rep2/malloc_info_mixed_29303_measure.xml
board_results/batch2/mixed/C0/rep2/mkdir_remote.log
board_results/batch2/mixed/C0/rep2/pull.log
board_results/batch2/mixed/C0/rep2/result.json
board_results/batch2/mixed/C0/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/C0/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/C0/rep2/stderr.txt
board_results/batch2/mixed/C0/rep2/thermal.txt
board_results/batch2/mixed/C0/rep3/cmd.txt
board_results/batch2/mixed/C0/rep3/exit_code.txt
board_results/batch2/mixed/C0/rep3/malloc_info_mixed_30500_idle.xml
board_results/batch2/mixed/C0/rep3/malloc_info_mixed_30500_measure.xml
board_results/batch2/mixed/C0/rep3/mkdir_remote.log
board_results/batch2/mixed/C0/rep3/pull.log
board_results/batch2/mixed/C0/rep3/result.json
board_results/batch2/mixed/C0/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/C0/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/C0/rep3/stderr.txt
board_results/batch2/mixed/C0/rep3/thermal.txt
board_results/batch2/mixed/T-B1/rep1/cmd.txt
board_results/batch2/mixed/T-B1/rep1/exit_code.txt
board_results/batch2/mixed/T-B1/rep1/malloc_info_mixed_20888_idle.xml
board_results/batch2/mixed/T-B1/rep1/malloc_info_mixed_20888_measure.xml
board_results/batch2/mixed/T-B1/rep1/mkdir_remote.log
board_results/batch2/mixed/T-B1/rep1/pull.log
board_results/batch2/mixed/T-B1/rep1/result.json
board_results/batch2/mixed/T-B1/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-B1/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-B1/rep1/stderr.txt
board_results/batch2/mixed/T-B1/rep1/thermal.txt
board_results/batch2/mixed/T-B1/rep2/cmd.txt
board_results/batch2/mixed/T-B1/rep2/exit_code.txt
board_results/batch2/mixed/T-B1/rep2/malloc_info_mixed_22130_idle.xml
board_results/batch2/mixed/T-B1/rep2/malloc_info_mixed_22130_measure.xml
board_results/batch2/mixed/T-B1/rep2/mkdir_remote.log
board_results/batch2/mixed/T-B1/rep2/pull.log
board_results/batch2/mixed/T-B1/rep2/result.json
board_results/batch2/mixed/T-B1/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-B1/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-B1/rep2/stderr.txt
board_results/batch2/mixed/T-B1/rep2/thermal.txt
board_results/batch2/mixed/T-B1/rep3/cmd.txt
board_results/batch2/mixed/T-B1/rep3/exit_code.txt
board_results/batch2/mixed/T-B1/rep3/malloc_info_mixed_23338_idle.xml
board_results/batch2/mixed/T-B1/rep3/malloc_info_mixed_23338_measure.xml
board_results/batch2/mixed/T-B1/rep3/mkdir_remote.log
board_results/batch2/mixed/T-B1/rep3/pull.log
board_results/batch2/mixed/T-B1/rep3/result.json
board_results/batch2/mixed/T-B1/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-B1/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-B1/rep3/stderr.txt
board_results/batch2/mixed/T-B1/rep3/thermal.txt
board_results/batch2/mixed/T-L11/rep1/cmd.txt
board_results/batch2/mixed/T-L11/rep1/exit_code.txt
board_results/batch2/mixed/T-L11/rep1/malloc_info_mixed_10144_idle.xml
board_results/batch2/mixed/T-L11/rep1/malloc_info_mixed_10144_measure.xml
board_results/batch2/mixed/T-L11/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L11/rep1/pull.log
board_results/batch2/mixed/T-L11/rep1/result.json
board_results/batch2/mixed/T-L11/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L11/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L11/rep1/stderr.txt
board_results/batch2/mixed/T-L11/rep1/thermal.txt
board_results/batch2/mixed/T-L11/rep2/cmd.txt
board_results/batch2/mixed/T-L11/rep2/exit_code.txt
board_results/batch2/mixed/T-L11/rep2/malloc_info_mixed_11342_idle.xml
board_results/batch2/mixed/T-L11/rep2/malloc_info_mixed_11342_measure.xml
board_results/batch2/mixed/T-L11/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L11/rep2/pull.log
board_results/batch2/mixed/T-L11/rep2/result.json
board_results/batch2/mixed/T-L11/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L11/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L11/rep2/stderr.txt
board_results/batch2/mixed/T-L11/rep2/thermal.txt
board_results/batch2/mixed/T-L11/rep3/cmd.txt
board_results/batch2/mixed/T-L11/rep3/exit_code.txt
board_results/batch2/mixed/T-L11/rep3/malloc_info_mixed_12536_idle.xml
board_results/batch2/mixed/T-L11/rep3/malloc_info_mixed_12536_measure.xml
board_results/batch2/mixed/T-L11/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L11/rep3/pull.log
board_results/batch2/mixed/T-L11/rep3/result.json
board_results/batch2/mixed/T-L11/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L11/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L11/rep3/stderr.txt
board_results/batch2/mixed/T-L11/rep3/thermal.txt
board_results/batch2/mixed/T-L12/rep1/cmd.txt
board_results/batch2/mixed/T-L12/rep1/exit_code.txt
board_results/batch2/mixed/T-L12/rep1/malloc_info_mixed_13730_idle.xml
board_results/batch2/mixed/T-L12/rep1/malloc_info_mixed_13730_measure.xml
board_results/batch2/mixed/T-L12/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L12/rep1/pull.log
board_results/batch2/mixed/T-L12/rep1/result.json
board_results/batch2/mixed/T-L12/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L12/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L12/rep1/stderr.txt
board_results/batch2/mixed/T-L12/rep1/thermal.txt
board_results/batch2/mixed/T-L12/rep2/cmd.txt
board_results/batch2/mixed/T-L12/rep2/exit_code.txt
board_results/batch2/mixed/T-L12/rep2/malloc_info_mixed_14924_idle.xml
board_results/batch2/mixed/T-L12/rep2/malloc_info_mixed_14924_measure.xml
board_results/batch2/mixed/T-L12/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L12/rep2/pull.log
board_results/batch2/mixed/T-L12/rep2/result.json
board_results/batch2/mixed/T-L12/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L12/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L12/rep2/stderr.txt
board_results/batch2/mixed/T-L12/rep2/thermal.txt
board_results/batch2/mixed/T-L12/rep3/cmd.txt
board_results/batch2/mixed/T-L12/rep3/exit_code.txt
board_results/batch2/mixed/T-L12/rep3/malloc_info_mixed_16112_idle.xml
board_results/batch2/mixed/T-L12/rep3/malloc_info_mixed_16112_measure.xml
board_results/batch2/mixed/T-L12/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L12/rep3/pull.log
board_results/batch2/mixed/T-L12/rep3/result.json
board_results/batch2/mixed/T-L12/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L12/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L12/rep3/stderr.txt
board_results/batch2/mixed/T-L12/rep3/thermal.txt
board_results/batch2/mixed/T-L2/rep1/cmd.txt
board_results/batch2/mixed/T-L2/rep1/exit_code.txt
board_results/batch2/mixed/T-L2/rep1/malloc_info_mixed_17298_idle.xml
board_results/batch2/mixed/T-L2/rep1/malloc_info_mixed_17298_measure.xml
board_results/batch2/mixed/T-L2/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L2/rep1/pull.log
board_results/batch2/mixed/T-L2/rep1/result.json
board_results/batch2/mixed/T-L2/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L2/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L2/rep1/stderr.txt
board_results/batch2/mixed/T-L2/rep1/thermal.txt
board_results/batch2/mixed/T-L2/rep2/cmd.txt
board_results/batch2/mixed/T-L2/rep2/exit_code.txt
board_results/batch2/mixed/T-L2/rep2/malloc_info_mixed_18492_idle.xml
board_results/batch2/mixed/T-L2/rep2/malloc_info_mixed_18492_measure.xml
board_results/batch2/mixed/T-L2/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L2/rep2/pull.log
board_results/batch2/mixed/T-L2/rep2/result.json
board_results/batch2/mixed/T-L2/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L2/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L2/rep2/stderr.txt
board_results/batch2/mixed/T-L2/rep2/thermal.txt
board_results/batch2/mixed/T-L2/rep3/cmd.txt
board_results/batch2/mixed/T-L2/rep3/exit_code.txt
board_results/batch2/mixed/T-L2/rep3/malloc_info_mixed_19688_idle.xml
board_results/batch2/mixed/T-L2/rep3/malloc_info_mixed_19688_measure.xml
board_results/batch2/mixed/T-L2/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L2/rep3/pull.log
board_results/batch2/mixed/T-L2/rep3/result.json
board_results/batch2/mixed/T-L2/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L2/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L2/rep3/stderr.txt
board_results/batch2/mixed/T-L2/rep3/thermal.txt
board_results/batch2/mixed/T-L3/rep1/cmd.txt
board_results/batch2/mixed/T-L3/rep1/exit_code.txt
board_results/batch2/mixed/T-L3/rep1/malloc_info_mixed_31699_idle.xml
board_results/batch2/mixed/T-L3/rep1/malloc_info_mixed_31699_measure.xml
board_results/batch2/mixed/T-L3/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L3/rep1/pull.log
board_results/batch2/mixed/T-L3/rep1/result.json
board_results/batch2/mixed/T-L3/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L3/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L3/rep1/stderr.txt
board_results/batch2/mixed/T-L3/rep1/thermal.txt
board_results/batch2/mixed/T-L3/rep2/cmd.txt
board_results/batch2/mixed/T-L3/rep2/exit_code.txt
board_results/batch2/mixed/T-L3/rep2/malloc_info_mixed_467_idle.xml
board_results/batch2/mixed/T-L3/rep2/malloc_info_mixed_467_measure.xml
board_results/batch2/mixed/T-L3/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L3/rep2/pull.log
board_results/batch2/mixed/T-L3/rep2/result.json
board_results/batch2/mixed/T-L3/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L3/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L3/rep2/stderr.txt
board_results/batch2/mixed/T-L3/rep2/thermal.txt
board_results/batch2/mixed/T-L3/rep3/cmd.txt
board_results/batch2/mixed/T-L3/rep3/exit_code.txt
board_results/batch2/mixed/T-L3/rep3/malloc_info_mixed_1775_idle.xml
board_results/batch2/mixed/T-L3/rep3/malloc_info_mixed_1775_measure.xml
board_results/batch2/mixed/T-L3/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L3/rep3/pull.log
board_results/batch2/mixed/T-L3/rep3/result.json
board_results/batch2/mixed/T-L3/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L3/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L3/rep3/stderr.txt
board_results/batch2/mixed/T-L3/rep3/thermal.txt
board_results/batch2/mixed/T-L4a/rep1/cmd.txt
board_results/batch2/mixed/T-L4a/rep1/exit_code.txt
board_results/batch2/mixed/T-L4a/rep1/malloc_info_mixed_2968_idle.xml
board_results/batch2/mixed/T-L4a/rep1/malloc_info_mixed_2968_measure.xml
board_results/batch2/mixed/T-L4a/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L4a/rep1/pull.log
board_results/batch2/mixed/T-L4a/rep1/result.json
board_results/batch2/mixed/T-L4a/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4a/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4a/rep1/stderr.txt
board_results/batch2/mixed/T-L4a/rep1/thermal.txt
board_results/batch2/mixed/T-L4a/rep2/cmd.txt
board_results/batch2/mixed/T-L4a/rep2/exit_code.txt
board_results/batch2/mixed/T-L4a/rep2/malloc_info_mixed_4202_idle.xml
board_results/batch2/mixed/T-L4a/rep2/malloc_info_mixed_4202_measure.xml
board_results/batch2/mixed/T-L4a/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L4a/rep2/pull.log
board_results/batch2/mixed/T-L4a/rep2/result.json
board_results/batch2/mixed/T-L4a/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4a/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4a/rep2/stderr.txt
board_results/batch2/mixed/T-L4a/rep2/thermal.txt
board_results/batch2/mixed/T-L4a/rep3/cmd.txt
board_results/batch2/mixed/T-L4a/rep3/exit_code.txt
board_results/batch2/mixed/T-L4a/rep3/malloc_info_mixed_5394_idle.xml
board_results/batch2/mixed/T-L4a/rep3/malloc_info_mixed_5394_measure.xml
board_results/batch2/mixed/T-L4a/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L4a/rep3/pull.log
board_results/batch2/mixed/T-L4a/rep3/result.json
board_results/batch2/mixed/T-L4a/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4a/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4a/rep3/stderr.txt
board_results/batch2/mixed/T-L4a/rep3/thermal.txt
board_results/batch2/mixed/T-L4b/rep1/cmd.txt
board_results/batch2/mixed/T-L4b/rep1/exit_code.txt
board_results/batch2/mixed/T-L4b/rep1/malloc_info_mixed_6583_idle.xml
board_results/batch2/mixed/T-L4b/rep1/malloc_info_mixed_6583_measure.xml
board_results/batch2/mixed/T-L4b/rep1/mkdir_remote.log
board_results/batch2/mixed/T-L4b/rep1/pull.log
board_results/batch2/mixed/T-L4b/rep1/result.json
board_results/batch2/mixed/T-L4b/rep1/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4b/rep1/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4b/rep1/stderr.txt
board_results/batch2/mixed/T-L4b/rep1/thermal.txt
board_results/batch2/mixed/T-L4b/rep2/cmd.txt
board_results/batch2/mixed/T-L4b/rep2/exit_code.txt
board_results/batch2/mixed/T-L4b/rep2/malloc_info_mixed_7770_idle.xml
board_results/batch2/mixed/T-L4b/rep2/malloc_info_mixed_7770_measure.xml
board_results/batch2/mixed/T-L4b/rep2/mkdir_remote.log
board_results/batch2/mixed/T-L4b/rep2/pull.log
board_results/batch2/mixed/T-L4b/rep2/result.json
board_results/batch2/mixed/T-L4b/rep2/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4b/rep2/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4b/rep2/stderr.txt
board_results/batch2/mixed/T-L4b/rep2/thermal.txt
board_results/batch2/mixed/T-L4b/rep3/cmd.txt
board_results/batch2/mixed/T-L4b/rep3/exit_code.txt
board_results/batch2/mixed/T-L4b/rep3/malloc_info_mixed_8958_idle.xml
board_results/batch2/mixed/T-L4b/rep3/malloc_info_mixed_8958_measure.xml
board_results/batch2/mixed/T-L4b/rep3/mkdir_remote.log
board_results/batch2/mixed/T-L4b/rep3/pull.log
board_results/batch2/mixed/T-L4b/rep3/result.json
board_results/batch2/mixed/T-L4b/rep3/sdb_run_stderr.txt
board_results/batch2/mixed/T-L4b/rep3/sdb_run_stdout.txt
board_results/batch2/mixed/T-L4b/rep3/stderr.txt
board_results/batch2/mixed/T-L4b/rep3/thermal.txt
board_results/batch2/os_release.txt
board_results/batch2/precheck/batch2_pre_inventory.tsv
board_results/batch2/precheck/batch2_pre_inventory_summary.txt
board_results/batch2/precheck/inventory_run.log
board_results/batch2/precheck/pull_inventory_summary.log
board_results/batch2/precheck/pull_inventory_tsv.log
board_results/batch2/precheck/push_inventory.log
board_results/batch2/push_binary.log
board_results/batch2/restore/batch2_post_inventory.tsv
board_results/batch2/restore/batch2_post_inventory_summary.txt
board_results/batch2/restore/final_independent_check.log
board_results/batch2/restore/governor_restore.log
board_results/batch2/restore/inventory_run.log
board_results/batch2/restore/pull_inventory_summary.log
board_results/batch2/restore/pull_inventory_tsv.log
board_results/batch2/restore/push_inventory.log
board_results/batch2/restore/tmp_cleanup.log
board_results/batch2/root_id.txt
board_results/batch2/run_batch2_alloc_bench.sh
board_results/batch2/run_summary.tsv
board_results/batch2/sdb_connect.txt
board_results/batch2/sdb_devices.txt
board_results/batch2/sdb_root_on.txt
board_results/batch2/sdb_version.txt
board_results/batch2/small-churn/C0/rep1/cmd.txt
board_results/batch2/small-churn/C0/rep1/exit_code.txt
board_results/batch2/small-churn/C0/rep1/malloc_info_small-churn_31657_idle.xml
board_results/batch2/small-churn/C0/rep1/malloc_info_small-churn_31657_measure.xml
board_results/batch2/small-churn/C0/rep1/mkdir_remote.log
board_results/batch2/small-churn/C0/rep1/pull.log
board_results/batch2/small-churn/C0/rep1/result.json
board_results/batch2/small-churn/C0/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/C0/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/C0/rep1/stderr.txt
board_results/batch2/small-churn/C0/rep1/thermal.txt
board_results/batch2/small-churn/C0/rep2/cmd.txt
board_results/batch2/small-churn/C0/rep2/exit_code.txt
board_results/batch2/small-churn/C0/rep2/malloc_info_small-churn_395_idle.xml
board_results/batch2/small-churn/C0/rep2/malloc_info_small-churn_395_measure.xml
board_results/batch2/small-churn/C0/rep2/mkdir_remote.log
board_results/batch2/small-churn/C0/rep2/pull.log
board_results/batch2/small-churn/C0/rep2/result.json
board_results/batch2/small-churn/C0/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/C0/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/C0/rep2/stderr.txt
board_results/batch2/small-churn/C0/rep2/thermal.txt
board_results/batch2/small-churn/C0/rep3/cmd.txt
board_results/batch2/small-churn/C0/rep3/exit_code.txt
board_results/batch2/small-churn/C0/rep3/malloc_info_small-churn_1734_idle.xml
board_results/batch2/small-churn/C0/rep3/malloc_info_small-churn_1734_measure.xml
board_results/batch2/small-churn/C0/rep3/mkdir_remote.log
board_results/batch2/small-churn/C0/rep3/pull.log
board_results/batch2/small-churn/C0/rep3/result.json
board_results/batch2/small-churn/C0/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/C0/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/C0/rep3/stderr.txt
board_results/batch2/small-churn/C0/rep3/thermal.txt
board_results/batch2/small-churn/T-B1/rep1/cmd.txt
board_results/batch2/small-churn/T-B1/rep1/exit_code.txt
board_results/batch2/small-churn/T-B1/rep1/malloc_info_small-churn_24532_idle.xml
board_results/batch2/small-churn/T-B1/rep1/malloc_info_small-churn_24532_measure.xml
board_results/batch2/small-churn/T-B1/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-B1/rep1/pull.log
board_results/batch2/small-churn/T-B1/rep1/result.json
board_results/batch2/small-churn/T-B1/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-B1/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-B1/rep1/stderr.txt
board_results/batch2/small-churn/T-B1/rep1/thermal.txt
board_results/batch2/small-churn/T-B1/rep2/cmd.txt
board_results/batch2/small-churn/T-B1/rep2/exit_code.txt
board_results/batch2/small-churn/T-B1/rep2/malloc_info_small-churn_25727_idle.xml
board_results/batch2/small-churn/T-B1/rep2/malloc_info_small-churn_25727_measure.xml
board_results/batch2/small-churn/T-B1/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-B1/rep2/pull.log
board_results/batch2/small-churn/T-B1/rep2/result.json
board_results/batch2/small-churn/T-B1/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-B1/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-B1/rep2/stderr.txt
board_results/batch2/small-churn/T-B1/rep2/thermal.txt
board_results/batch2/small-churn/T-B1/rep3/cmd.txt
board_results/batch2/small-churn/T-B1/rep3/exit_code.txt
board_results/batch2/small-churn/T-B1/rep3/malloc_info_small-churn_26921_idle.xml
board_results/batch2/small-churn/T-B1/rep3/malloc_info_small-churn_26921_measure.xml
board_results/batch2/small-churn/T-B1/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-B1/rep3/pull.log
board_results/batch2/small-churn/T-B1/rep3/result.json
board_results/batch2/small-churn/T-B1/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-B1/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-B1/rep3/stderr.txt
board_results/batch2/small-churn/T-B1/rep3/thermal.txt
board_results/batch2/small-churn/T-L11/rep1/cmd.txt
board_results/batch2/small-churn/T-L11/rep1/exit_code.txt
board_results/batch2/small-churn/T-L11/rep1/malloc_info_small-churn_13718_idle.xml
board_results/batch2/small-churn/T-L11/rep1/malloc_info_small-churn_13718_measure.xml
board_results/batch2/small-churn/T-L11/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L11/rep1/pull.log
board_results/batch2/small-churn/T-L11/rep1/result.json
board_results/batch2/small-churn/T-L11/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L11/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L11/rep1/stderr.txt
board_results/batch2/small-churn/T-L11/rep1/thermal.txt
board_results/batch2/small-churn/T-L11/rep2/cmd.txt
board_results/batch2/small-churn/T-L11/rep2/exit_code.txt
board_results/batch2/small-churn/T-L11/rep2/malloc_info_small-churn_14911_idle.xml
board_results/batch2/small-churn/T-L11/rep2/malloc_info_small-churn_14911_measure.xml
board_results/batch2/small-churn/T-L11/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L11/rep2/pull.log
board_results/batch2/small-churn/T-L11/rep2/result.json
board_results/batch2/small-churn/T-L11/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L11/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L11/rep2/stderr.txt
board_results/batch2/small-churn/T-L11/rep2/thermal.txt
board_results/batch2/small-churn/T-L11/rep3/cmd.txt
board_results/batch2/small-churn/T-L11/rep3/exit_code.txt
board_results/batch2/small-churn/T-L11/rep3/malloc_info_small-churn_16107_idle.xml
board_results/batch2/small-churn/T-L11/rep3/malloc_info_small-churn_16107_measure.xml
board_results/batch2/small-churn/T-L11/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L11/rep3/pull.log
board_results/batch2/small-churn/T-L11/rep3/result.json
board_results/batch2/small-churn/T-L11/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L11/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L11/rep3/stderr.txt
board_results/batch2/small-churn/T-L11/rep3/thermal.txt
board_results/batch2/small-churn/T-L12/rep1/cmd.txt
board_results/batch2/small-churn/T-L12/rep1/exit_code.txt
board_results/batch2/small-churn/T-L12/rep1/malloc_info_small-churn_17302_idle.xml
board_results/batch2/small-churn/T-L12/rep1/malloc_info_small-churn_17302_measure.xml
board_results/batch2/small-churn/T-L12/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L12/rep1/pull.log
board_results/batch2/small-churn/T-L12/rep1/result.json
board_results/batch2/small-churn/T-L12/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L12/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L12/rep1/stderr.txt
board_results/batch2/small-churn/T-L12/rep1/thermal.txt
board_results/batch2/small-churn/T-L12/rep2/cmd.txt
board_results/batch2/small-churn/T-L12/rep2/exit_code.txt
board_results/batch2/small-churn/T-L12/rep2/malloc_info_small-churn_18498_idle.xml
board_results/batch2/small-churn/T-L12/rep2/malloc_info_small-churn_18498_measure.xml
board_results/batch2/small-churn/T-L12/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L12/rep2/pull.log
board_results/batch2/small-churn/T-L12/rep2/result.json
board_results/batch2/small-churn/T-L12/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L12/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L12/rep2/stderr.txt
board_results/batch2/small-churn/T-L12/rep2/thermal.txt
board_results/batch2/small-churn/T-L12/rep3/cmd.txt
board_results/batch2/small-churn/T-L12/rep3/exit_code.txt
board_results/batch2/small-churn/T-L12/rep3/malloc_info_small-churn_19694_idle.xml
board_results/batch2/small-churn/T-L12/rep3/malloc_info_small-churn_19694_measure.xml
board_results/batch2/small-churn/T-L12/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L12/rep3/pull.log
board_results/batch2/small-churn/T-L12/rep3/result.json
board_results/batch2/small-churn/T-L12/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L12/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L12/rep3/stderr.txt
board_results/batch2/small-churn/T-L12/rep3/thermal.txt
board_results/batch2/small-churn/T-L2/rep1/cmd.txt
board_results/batch2/small-churn/T-L2/rep1/exit_code.txt
board_results/batch2/small-churn/T-L2/rep1/malloc_info_small-churn_20886_idle.xml
board_results/batch2/small-churn/T-L2/rep1/malloc_info_small-churn_20886_measure.xml
board_results/batch2/small-churn/T-L2/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L2/rep1/pull.log
board_results/batch2/small-churn/T-L2/rep1/result.json
board_results/batch2/small-churn/T-L2/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L2/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L2/rep1/stderr.txt
board_results/batch2/small-churn/T-L2/rep1/thermal.txt
board_results/batch2/small-churn/T-L2/rep2/cmd.txt
board_results/batch2/small-churn/T-L2/rep2/exit_code.txt
board_results/batch2/small-churn/T-L2/rep2/malloc_info_small-churn_22127_idle.xml
board_results/batch2/small-churn/T-L2/rep2/malloc_info_small-churn_22127_measure.xml
board_results/batch2/small-churn/T-L2/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L2/rep2/pull.log
board_results/batch2/small-churn/T-L2/rep2/result.json
board_results/batch2/small-churn/T-L2/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L2/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L2/rep2/stderr.txt
board_results/batch2/small-churn/T-L2/rep2/thermal.txt
board_results/batch2/small-churn/T-L2/rep3/cmd.txt
board_results/batch2/small-churn/T-L2/rep3/exit_code.txt
board_results/batch2/small-churn/T-L2/rep3/malloc_info_small-churn_23332_idle.xml
board_results/batch2/small-churn/T-L2/rep3/malloc_info_small-churn_23332_measure.xml
board_results/batch2/small-churn/T-L2/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L2/rep3/pull.log
board_results/batch2/small-churn/T-L2/rep3/result.json
board_results/batch2/small-churn/T-L2/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L2/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L2/rep3/stderr.txt
board_results/batch2/small-churn/T-L2/rep3/thermal.txt
board_results/batch2/small-churn/T-L3/rep1/cmd.txt
board_results/batch2/small-churn/T-L3/rep1/exit_code.txt
board_results/batch2/small-churn/T-L3/rep1/malloc_info_small-churn_2933_idle.xml
board_results/batch2/small-churn/T-L3/rep1/malloc_info_small-churn_2933_measure.xml
board_results/batch2/small-churn/T-L3/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L3/rep1/pull.log
board_results/batch2/small-churn/T-L3/rep1/result.json
board_results/batch2/small-churn/T-L3/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L3/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L3/rep1/stderr.txt
board_results/batch2/small-churn/T-L3/rep1/thermal.txt
board_results/batch2/small-churn/T-L3/rep2/cmd.txt
board_results/batch2/small-churn/T-L3/rep2/exit_code.txt
board_results/batch2/small-churn/T-L3/rep2/malloc_info_small-churn_4130_idle.xml
board_results/batch2/small-churn/T-L3/rep2/malloc_info_small-churn_4130_measure.xml
board_results/batch2/small-churn/T-L3/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L3/rep2/pull.log
board_results/batch2/small-churn/T-L3/rep2/result.json
board_results/batch2/small-churn/T-L3/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L3/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L3/rep2/stderr.txt
board_results/batch2/small-churn/T-L3/rep2/thermal.txt
board_results/batch2/small-churn/T-L3/rep3/cmd.txt
board_results/batch2/small-churn/T-L3/rep3/exit_code.txt
board_results/batch2/small-churn/T-L3/rep3/malloc_info_small-churn_5340_idle.xml
board_results/batch2/small-churn/T-L3/rep3/malloc_info_small-churn_5340_measure.xml
board_results/batch2/small-churn/T-L3/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L3/rep3/pull.log
board_results/batch2/small-churn/T-L3/rep3/result.json
board_results/batch2/small-churn/T-L3/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L3/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L3/rep3/stderr.txt
board_results/batch2/small-churn/T-L3/rep3/thermal.txt
board_results/batch2/small-churn/T-L4a/rep1/cmd.txt
board_results/batch2/small-churn/T-L4a/rep1/exit_code.txt
board_results/batch2/small-churn/T-L4a/rep1/malloc_info_small-churn_6542_idle.xml
board_results/batch2/small-churn/T-L4a/rep1/malloc_info_small-churn_6542_measure.xml
board_results/batch2/small-churn/T-L4a/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L4a/rep1/pull.log
board_results/batch2/small-churn/T-L4a/rep1/result.json
board_results/batch2/small-churn/T-L4a/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4a/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4a/rep1/stderr.txt
board_results/batch2/small-churn/T-L4a/rep1/thermal.txt
board_results/batch2/small-churn/T-L4a/rep2/cmd.txt
board_results/batch2/small-churn/T-L4a/rep2/exit_code.txt
board_results/batch2/small-churn/T-L4a/rep2/malloc_info_small-churn_7738_idle.xml
board_results/batch2/small-churn/T-L4a/rep2/malloc_info_small-churn_7738_measure.xml
board_results/batch2/small-churn/T-L4a/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L4a/rep2/pull.log
board_results/batch2/small-churn/T-L4a/rep2/result.json
board_results/batch2/small-churn/T-L4a/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4a/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4a/rep2/stderr.txt
board_results/batch2/small-churn/T-L4a/rep2/thermal.txt
board_results/batch2/small-churn/T-L4a/rep3/cmd.txt
board_results/batch2/small-churn/T-L4a/rep3/exit_code.txt
board_results/batch2/small-churn/T-L4a/rep3/malloc_info_small-churn_8932_idle.xml
board_results/batch2/small-churn/T-L4a/rep3/malloc_info_small-churn_8932_measure.xml
board_results/batch2/small-churn/T-L4a/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L4a/rep3/pull.log
board_results/batch2/small-churn/T-L4a/rep3/result.json
board_results/batch2/small-churn/T-L4a/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4a/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4a/rep3/stderr.txt
board_results/batch2/small-churn/T-L4a/rep3/thermal.txt
board_results/batch2/small-churn/T-L4b/rep1/cmd.txt
board_results/batch2/small-churn/T-L4b/rep1/exit_code.txt
board_results/batch2/small-churn/T-L4b/rep1/malloc_info_small-churn_10128_idle.xml
board_results/batch2/small-churn/T-L4b/rep1/malloc_info_small-churn_10128_measure.xml
board_results/batch2/small-churn/T-L4b/rep1/mkdir_remote.log
board_results/batch2/small-churn/T-L4b/rep1/pull.log
board_results/batch2/small-churn/T-L4b/rep1/result.json
board_results/batch2/small-churn/T-L4b/rep1/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4b/rep1/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4b/rep1/stderr.txt
board_results/batch2/small-churn/T-L4b/rep1/thermal.txt
board_results/batch2/small-churn/T-L4b/rep2/cmd.txt
board_results/batch2/small-churn/T-L4b/rep2/exit_code.txt
board_results/batch2/small-churn/T-L4b/rep2/malloc_info_small-churn_11321_idle.xml
board_results/batch2/small-churn/T-L4b/rep2/malloc_info_small-churn_11321_measure.xml
board_results/batch2/small-churn/T-L4b/rep2/mkdir_remote.log
board_results/batch2/small-churn/T-L4b/rep2/pull.log
board_results/batch2/small-churn/T-L4b/rep2/result.json
board_results/batch2/small-churn/T-L4b/rep2/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4b/rep2/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4b/rep2/stderr.txt
board_results/batch2/small-churn/T-L4b/rep2/thermal.txt
board_results/batch2/small-churn/T-L4b/rep3/cmd.txt
board_results/batch2/small-churn/T-L4b/rep3/exit_code.txt
board_results/batch2/small-churn/T-L4b/rep3/malloc_info_small-churn_12523_idle.xml
board_results/batch2/small-churn/T-L4b/rep3/malloc_info_small-churn_12523_measure.xml
board_results/batch2/small-churn/T-L4b/rep3/mkdir_remote.log
board_results/batch2/small-churn/T-L4b/rep3/pull.log
board_results/batch2/small-churn/T-L4b/rep3/result.json
board_results/batch2/small-churn/T-L4b/rep3/sdb_run_stderr.txt
board_results/batch2/small-churn/T-L4b/rep3/sdb_run_stdout.txt
board_results/batch2/small-churn/T-L4b/rep3/stderr.txt
board_results/batch2/small-churn/T-L4b/rep3/thermal.txt
board_results/batch2/smoke/exit_code.txt
board_results/batch2/smoke/json_tool.err
board_results/batch2/smoke/malloc_info_small-churn_31593_idle.xml
board_results/batch2/smoke/malloc_info_small-churn_31593_measure.xml
board_results/batch2/smoke/pull.log
board_results/batch2/smoke/result.json
board_results/batch2/smoke/result.pretty.json
board_results/batch2/smoke/run.log
board_results/batch2/smoke/stderr.txt
board_results/batch2/thread-churn/C0/rep1/cmd.txt
board_results/batch2/thread-churn/C0/rep1/exit_code.txt
board_results/batch2/thread-churn/C0/rep1/malloc_info_thread-churn_20897_idle.xml
board_results/batch2/thread-churn/C0/rep1/malloc_info_thread-churn_20897_measure.xml
board_results/batch2/thread-churn/C0/rep1/mkdir_remote.log
board_results/batch2/thread-churn/C0/rep1/pull.log
board_results/batch2/thread-churn/C0/rep1/result.json
board_results/batch2/thread-churn/C0/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/C0/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/C0/rep1/stderr.txt
board_results/batch2/thread-churn/C0/rep1/thermal.txt
board_results/batch2/thread-churn/C0/rep2/cmd.txt
board_results/batch2/thread-churn/C0/rep2/exit_code.txt
board_results/batch2/thread-churn/C0/rep2/malloc_info_thread-churn_22204_idle.xml
board_results/batch2/thread-churn/C0/rep2/malloc_info_thread-churn_22204_measure.xml
board_results/batch2/thread-churn/C0/rep2/mkdir_remote.log
board_results/batch2/thread-churn/C0/rep2/pull.log
board_results/batch2/thread-churn/C0/rep2/result.json
board_results/batch2/thread-churn/C0/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/C0/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/C0/rep2/stderr.txt
board_results/batch2/thread-churn/C0/rep2/thermal.txt
board_results/batch2/thread-churn/C0/rep3/cmd.txt
board_results/batch2/thread-churn/C0/rep3/exit_code.txt
board_results/batch2/thread-churn/C0/rep3/malloc_info_thread-churn_23459_idle.xml
board_results/batch2/thread-churn/C0/rep3/malloc_info_thread-churn_23459_measure.xml
board_results/batch2/thread-churn/C0/rep3/mkdir_remote.log
board_results/batch2/thread-churn/C0/rep3/pull.log
board_results/batch2/thread-churn/C0/rep3/result.json
board_results/batch2/thread-churn/C0/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/C0/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/C0/rep3/stderr.txt
board_results/batch2/thread-churn/C0/rep3/thermal.txt
board_results/batch2/thread-churn/T-B1/rep1/cmd.txt
board_results/batch2/thread-churn/T-B1/rep1/exit_code.txt
board_results/batch2/thread-churn/T-B1/rep1/malloc_info_thread-churn_15064_idle.xml
board_results/batch2/thread-churn/T-B1/rep1/malloc_info_thread-churn_15064_measure.xml
board_results/batch2/thread-churn/T-B1/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-B1/rep1/pull.log
board_results/batch2/thread-churn/T-B1/rep1/result.json
board_results/batch2/thread-churn/T-B1/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-B1/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-B1/rep1/stderr.txt
board_results/batch2/thread-churn/T-B1/rep1/thermal.txt
board_results/batch2/thread-churn/T-B1/rep2/cmd.txt
board_results/batch2/thread-churn/T-B1/rep2/exit_code.txt
board_results/batch2/thread-churn/T-B1/rep2/malloc_info_thread-churn_16327_idle.xml
board_results/batch2/thread-churn/T-B1/rep2/malloc_info_thread-churn_16327_measure.xml
board_results/batch2/thread-churn/T-B1/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-B1/rep2/pull.log
board_results/batch2/thread-churn/T-B1/rep2/result.json
board_results/batch2/thread-churn/T-B1/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-B1/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-B1/rep2/stderr.txt
board_results/batch2/thread-churn/T-B1/rep2/thermal.txt
board_results/batch2/thread-churn/T-B1/rep3/cmd.txt
board_results/batch2/thread-churn/T-B1/rep3/exit_code.txt
board_results/batch2/thread-churn/T-B1/rep3/malloc_info_thread-churn_17593_idle.xml
board_results/batch2/thread-churn/T-B1/rep3/malloc_info_thread-churn_17593_measure.xml
board_results/batch2/thread-churn/T-B1/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-B1/rep3/pull.log
board_results/batch2/thread-churn/T-B1/rep3/result.json
board_results/batch2/thread-churn/T-B1/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-B1/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-B1/rep3/stderr.txt
board_results/batch2/thread-churn/T-B1/rep3/thermal.txt
board_results/batch2/thread-churn/T-L1/rep1/cmd.txt
board_results/batch2/thread-churn/T-L1/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L1/rep1/malloc_info_thread-churn_18860_idle.xml
board_results/batch2/thread-churn/T-L1/rep1/malloc_info_thread-churn_18860_measure.xml
board_results/batch2/thread-churn/T-L1/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L1/rep1/pull.log
board_results/batch2/thread-churn/T-L1/rep1/result.json
board_results/batch2/thread-churn/T-L1/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L1/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L1/rep1/stderr.txt
board_results/batch2/thread-churn/T-L1/rep1/thermal.txt
board_results/batch2/thread-churn/T-L1/rep2/cmd.txt
board_results/batch2/thread-churn/T-L1/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L1/rep2/malloc_info_thread-churn_20118_idle.xml
board_results/batch2/thread-churn/T-L1/rep2/malloc_info_thread-churn_20118_measure.xml
board_results/batch2/thread-churn/T-L1/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L1/rep2/pull.log
board_results/batch2/thread-churn/T-L1/rep2/result.json
board_results/batch2/thread-churn/T-L1/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L1/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L1/rep2/stderr.txt
board_results/batch2/thread-churn/T-L1/rep2/thermal.txt
board_results/batch2/thread-churn/T-L1/rep3/cmd.txt
board_results/batch2/thread-churn/T-L1/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L1/rep3/malloc_info_thread-churn_21373_idle.xml
board_results/batch2/thread-churn/T-L1/rep3/malloc_info_thread-churn_21373_measure.xml
board_results/batch2/thread-churn/T-L1/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L1/rep3/pull.log
board_results/batch2/thread-churn/T-L1/rep3/result.json
board_results/batch2/thread-churn/T-L1/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L1/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L1/rep3/stderr.txt
board_results/batch2/thread-churn/T-L1/rep3/thermal.txt
board_results/batch2/thread-churn/T-L11/rep1/cmd.txt
board_results/batch2/thread-churn/T-L11/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L11/rep1/malloc_info_thread-churn_3712_idle.xml
board_results/batch2/thread-churn/T-L11/rep1/malloc_info_thread-churn_3712_measure.xml
board_results/batch2/thread-churn/T-L11/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L11/rep1/pull.log
board_results/batch2/thread-churn/T-L11/rep1/result.json
board_results/batch2/thread-churn/T-L11/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L11/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L11/rep1/stderr.txt
board_results/batch2/thread-churn/T-L11/rep1/thermal.txt
board_results/batch2/thread-churn/T-L11/rep2/cmd.txt
board_results/batch2/thread-churn/T-L11/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L11/rep2/malloc_info_thread-churn_4976_idle.xml
board_results/batch2/thread-churn/T-L11/rep2/malloc_info_thread-churn_4976_measure.xml
board_results/batch2/thread-churn/T-L11/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L11/rep2/pull.log
board_results/batch2/thread-churn/T-L11/rep2/result.json
board_results/batch2/thread-churn/T-L11/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L11/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L11/rep2/stderr.txt
board_results/batch2/thread-churn/T-L11/rep2/thermal.txt
board_results/batch2/thread-churn/T-L11/rep3/cmd.txt
board_results/batch2/thread-churn/T-L11/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L11/rep3/malloc_info_thread-churn_6233_idle.xml
board_results/batch2/thread-churn/T-L11/rep3/malloc_info_thread-churn_6233_measure.xml
board_results/batch2/thread-churn/T-L11/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L11/rep3/pull.log
board_results/batch2/thread-churn/T-L11/rep3/result.json
board_results/batch2/thread-churn/T-L11/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L11/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L11/rep3/stderr.txt
board_results/batch2/thread-churn/T-L11/rep3/thermal.txt
board_results/batch2/thread-churn/T-L12/rep1/cmd.txt
board_results/batch2/thread-churn/T-L12/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L12/rep1/malloc_info_thread-churn_7489_idle.xml
board_results/batch2/thread-churn/T-L12/rep1/malloc_info_thread-churn_7489_measure.xml
board_results/batch2/thread-churn/T-L12/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L12/rep1/pull.log
board_results/batch2/thread-churn/T-L12/rep1/result.json
board_results/batch2/thread-churn/T-L12/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L12/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L12/rep1/stderr.txt
board_results/batch2/thread-churn/T-L12/rep1/thermal.txt
board_results/batch2/thread-churn/T-L12/rep2/cmd.txt
board_results/batch2/thread-churn/T-L12/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L12/rep2/malloc_info_thread-churn_8747_idle.xml
board_results/batch2/thread-churn/T-L12/rep2/malloc_info_thread-churn_8747_measure.xml
board_results/batch2/thread-churn/T-L12/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L12/rep2/pull.log
board_results/batch2/thread-churn/T-L12/rep2/result.json
board_results/batch2/thread-churn/T-L12/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L12/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L12/rep2/stderr.txt
board_results/batch2/thread-churn/T-L12/rep2/thermal.txt
board_results/batch2/thread-churn/T-L12/rep3/cmd.txt
board_results/batch2/thread-churn/T-L12/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L12/rep3/malloc_info_thread-churn_10007_idle.xml
board_results/batch2/thread-churn/T-L12/rep3/malloc_info_thread-churn_10007_measure.xml
board_results/batch2/thread-churn/T-L12/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L12/rep3/pull.log
board_results/batch2/thread-churn/T-L12/rep3/result.json
board_results/batch2/thread-churn/T-L12/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L12/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L12/rep3/stderr.txt
board_results/batch2/thread-churn/T-L12/rep3/thermal.txt
board_results/batch2/thread-churn/T-L2/rep1/cmd.txt
board_results/batch2/thread-churn/T-L2/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L2/rep1/malloc_info_thread-churn_11264_idle.xml
board_results/batch2/thread-churn/T-L2/rep1/malloc_info_thread-churn_11264_measure.xml
board_results/batch2/thread-churn/T-L2/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L2/rep1/pull.log
board_results/batch2/thread-churn/T-L2/rep1/result.json
board_results/batch2/thread-churn/T-L2/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L2/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L2/rep1/stderr.txt
board_results/batch2/thread-churn/T-L2/rep1/thermal.txt
board_results/batch2/thread-churn/T-L2/rep2/cmd.txt
board_results/batch2/thread-churn/T-L2/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L2/rep2/malloc_info_thread-churn_12533_idle.xml
board_results/batch2/thread-churn/T-L2/rep2/malloc_info_thread-churn_12533_measure.xml
board_results/batch2/thread-churn/T-L2/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L2/rep2/pull.log
board_results/batch2/thread-churn/T-L2/rep2/result.json
board_results/batch2/thread-churn/T-L2/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L2/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L2/rep2/stderr.txt
board_results/batch2/thread-churn/T-L2/rep2/thermal.txt
board_results/batch2/thread-churn/T-L2/rep3/cmd.txt
board_results/batch2/thread-churn/T-L2/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L2/rep3/malloc_info_thread-churn_13799_idle.xml
board_results/batch2/thread-churn/T-L2/rep3/malloc_info_thread-churn_13799_measure.xml
board_results/batch2/thread-churn/T-L2/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L2/rep3/pull.log
board_results/batch2/thread-churn/T-L2/rep3/result.json
board_results/batch2/thread-churn/T-L2/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L2/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L2/rep3/stderr.txt
board_results/batch2/thread-churn/T-L2/rep3/thermal.txt
board_results/batch2/thread-churn/T-L3/rep1/cmd.txt
board_results/batch2/thread-churn/T-L3/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L3/rep1/malloc_info_thread-churn_24715_idle.xml
board_results/batch2/thread-churn/T-L3/rep1/malloc_info_thread-churn_24715_measure.xml
board_results/batch2/thread-churn/T-L3/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L3/rep1/pull.log
board_results/batch2/thread-churn/T-L3/rep1/result.json
board_results/batch2/thread-churn/T-L3/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L3/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L3/rep1/stderr.txt
board_results/batch2/thread-churn/T-L3/rep1/thermal.txt
board_results/batch2/thread-churn/T-L3/rep2/cmd.txt
board_results/batch2/thread-churn/T-L3/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L3/rep2/malloc_info_thread-churn_25969_idle.xml
board_results/batch2/thread-churn/T-L3/rep2/malloc_info_thread-churn_25969_measure.xml
board_results/batch2/thread-churn/T-L3/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L3/rep2/pull.log
board_results/batch2/thread-churn/T-L3/rep2/result.json
board_results/batch2/thread-churn/T-L3/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L3/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L3/rep2/stderr.txt
board_results/batch2/thread-churn/T-L3/rep2/thermal.txt
board_results/batch2/thread-churn/T-L3/rep3/cmd.txt
board_results/batch2/thread-churn/T-L3/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L3/rep3/malloc_info_thread-churn_27226_idle.xml
board_results/batch2/thread-churn/T-L3/rep3/malloc_info_thread-churn_27226_measure.xml
board_results/batch2/thread-churn/T-L3/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L3/rep3/pull.log
board_results/batch2/thread-churn/T-L3/rep3/result.json
board_results/batch2/thread-churn/T-L3/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L3/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L3/rep3/stderr.txt
board_results/batch2/thread-churn/T-L3/rep3/thermal.txt
board_results/batch2/thread-churn/T-L4a/rep1/cmd.txt
board_results/batch2/thread-churn/T-L4a/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L4a/rep1/malloc_info_thread-churn_28480_idle.xml
board_results/batch2/thread-churn/T-L4a/rep1/malloc_info_thread-churn_28480_measure.xml
board_results/batch2/thread-churn/T-L4a/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L4a/rep1/pull.log
board_results/batch2/thread-churn/T-L4a/rep1/result.json
board_results/batch2/thread-churn/T-L4a/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4a/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4a/rep1/stderr.txt
board_results/batch2/thread-churn/T-L4a/rep1/thermal.txt
board_results/batch2/thread-churn/T-L4a/rep2/cmd.txt
board_results/batch2/thread-churn/T-L4a/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L4a/rep2/malloc_info_thread-churn_29743_idle.xml
board_results/batch2/thread-churn/T-L4a/rep2/malloc_info_thread-churn_29743_measure.xml
board_results/batch2/thread-churn/T-L4a/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L4a/rep2/pull.log
board_results/batch2/thread-churn/T-L4a/rep2/result.json
board_results/batch2/thread-churn/T-L4a/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4a/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4a/rep2/stderr.txt
board_results/batch2/thread-churn/T-L4a/rep2/thermal.txt
board_results/batch2/thread-churn/T-L4a/rep3/cmd.txt
board_results/batch2/thread-churn/T-L4a/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L4a/rep3/malloc_info_thread-churn_30999_idle.xml
board_results/batch2/thread-churn/T-L4a/rep3/malloc_info_thread-churn_30999_measure.xml
board_results/batch2/thread-churn/T-L4a/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L4a/rep3/pull.log
board_results/batch2/thread-churn/T-L4a/rep3/result.json
board_results/batch2/thread-churn/T-L4a/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4a/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4a/rep3/stderr.txt
board_results/batch2/thread-churn/T-L4a/rep3/thermal.txt
board_results/batch2/thread-churn/T-L4b/rep1/cmd.txt
board_results/batch2/thread-churn/T-L4b/rep1/exit_code.txt
board_results/batch2/thread-churn/T-L4b/rep1/malloc_info_thread-churn_32257_idle.xml
board_results/batch2/thread-churn/T-L4b/rep1/malloc_info_thread-churn_32257_measure.xml
board_results/batch2/thread-churn/T-L4b/rep1/mkdir_remote.log
board_results/batch2/thread-churn/T-L4b/rep1/pull.log
board_results/batch2/thread-churn/T-L4b/rep1/result.json
board_results/batch2/thread-churn/T-L4b/rep1/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4b/rep1/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4b/rep1/stderr.txt
board_results/batch2/thread-churn/T-L4b/rep1/thermal.txt
board_results/batch2/thread-churn/T-L4b/rep2/cmd.txt
board_results/batch2/thread-churn/T-L4b/rep2/exit_code.txt
board_results/batch2/thread-churn/T-L4b/rep2/malloc_info_thread-churn_1191_idle.xml
board_results/batch2/thread-churn/T-L4b/rep2/malloc_info_thread-churn_1191_measure.xml
board_results/batch2/thread-churn/T-L4b/rep2/mkdir_remote.log
board_results/batch2/thread-churn/T-L4b/rep2/pull.log
board_results/batch2/thread-churn/T-L4b/rep2/result.json
board_results/batch2/thread-churn/T-L4b/rep2/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4b/rep2/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4b/rep2/stderr.txt
board_results/batch2/thread-churn/T-L4b/rep2/thermal.txt
board_results/batch2/thread-churn/T-L4b/rep3/cmd.txt
board_results/batch2/thread-churn/T-L4b/rep3/exit_code.txt
board_results/batch2/thread-churn/T-L4b/rep3/malloc_info_thread-churn_2451_idle.xml
board_results/batch2/thread-churn/T-L4b/rep3/malloc_info_thread-churn_2451_measure.xml
board_results/batch2/thread-churn/T-L4b/rep3/mkdir_remote.log
board_results/batch2/thread-churn/T-L4b/rep3/pull.log
board_results/batch2/thread-churn/T-L4b/rep3/result.json
board_results/batch2/thread-churn/T-L4b/rep3/sdb_run_stderr.txt
board_results/batch2/thread-churn/T-L4b/rep3/sdb_run_stdout.txt
board_results/batch2/thread-churn/T-L4b/rep3/stderr.txt
board_results/batch2/thread-churn/T-L4b/rep3/thermal.txt
board_results/batch2/uname.txt
```
