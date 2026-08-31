> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# TV 产品板环境基线侦察 3 与 glibc 优化等级判定

- 采集日期：2026-08-06（Asia/Shanghai）
- TV 目标：`<PRODUCT_BOARD_IP>`
- RPI4 对照：`<TEST_BOARD_IP>:26101`
- workspace：`<WORKSPACE>`
- 原始证据根目录：`board_results/tv_recon3_20260806/`
- 操作边界：TV 未安装包、未推送或执行外部 ELF、未重启 service、未修改持久配置；只执行只读探测及立即删除的 `/bin/true` 路径副本、`/etc` 写探针和 tmpfs 气球。

## 1. 板子身份自检

| 项 | TV `.26` 实测 | RPI4 `.25` 实测 |
|---|---|---|
| 身份门 | `IDENTITY_OK=PRODUCT_BOARD_NOT_RPI4_NOT_UNIFIED_DEV` | `IDENTITY_OK=RPI4_25` |
| `uname -r` | `6.12.60` | `6.12.80-arm-rpi4-v7l` |
| OS | Tizen `10.0.0 (<PRODUCT_IMAGE>)` | Tizen `11.0.0 (Tizen11.0/Unified)` |
| Build ID | `<PRODUCT_BUILD_ID>` | `<TEST_IMAGE_A>` |
| 架构 | `armv7l` | `armv7l` |

所有 TV 采集脚本在第一项采集前读取 `uname -r` 和 `/etc/os-release`；命中 `rpi4` 或 `unified-dev` 分别以 97/98 退出。证据：`product_board/final_pull/tv_recon3_product_board/identity.out`、`test_board/remote/identity.out`。

## 2. 组 G：glibc 实际优化等级

### 2.1 G4 结论

| 对象 | 编译器 | 优化等级 | 判定依据 | 置信度 |
|---|---|---|---|---|
| TV 产品板 `.26` | Tizen GCC 14.2.0 | **`-O2`** | G1 `.comment` 给出 GCC 14.2.0；G2 RPM `%{OPTFLAGS}` 直接含 `-O2`；G3 到本地 O2/Os 复合距离分别为 `0.3284%`/`13.4500%` | 高，优化等级有直接证据 |
| RPI4 产品板 `.25` | GNU GCC 14.2.0 | **`-O2`** | libc 自报 GCC 14.2.0；RPM `%{OPTFLAGS}` 直接含 `-O2`；除 20-byte Build ID 和 4-byte debuglink CRC 外，与 workspace O2 libc 字节一致 | 高，优化等级有直接证据 |
| workspace O2 构建 | GNU GCC 14.2.0 | **`-O2`** | GBS 的 `malloc.c` 实际命令和 debuginfo `DW_AT_producer` 都含最终 `-O2` | 高 |
| workspace Os 构建 | GNU GCC 14.2.0 | **`-Os`** | GBS 的 `malloc.c` 实际命令和 debuginfo `DW_AT_producer` 都显示后置 `-Os`；GBS RC=0 并出包 | 高（见 G3 构建偏差） |

### 2.2 G1 直接 ELF 证据

| 对象 | 文件尺寸 | Build ID | `.comment` | `.GCC.command.line` | 调试/符号状态 |
|---|---:|---|---|---|---|
| TV libc | 1,453,496 B | `3ae1c54ac466fc89a8033bac6e7c6253cf00942a` | `GCC: (Tizen GCC 14.2.0 20240801 1.3) 14.2.0` | 不存在 | `file` 判定 stripped；无 `.symtab` |
| TV loader | 180,600 B | `212a232b44489198c04abc35da2bba8272d48d12` | 同上 | 不存在 | stripped；无 `.symtab` |
| RPI4 libc | 1,450,052 B | `2d4df69000f90d393c8841cdc9b97b8ff4702a8e` | 不存在 | 不存在 | stripped；保留 `.gnu_debuglink` |
| RPI4 loader | 187,708 B | `09c3cff0ccb843a6ba92ff3e1f39f163c4682687` | 不存在 | 不存在 | stripped；保留 `.gnu_debuglink` |

TV 产品 libc 虽然 stripped，实际仍保留 `.comment`；“产品 libc 无 `.comment`”在本镜像上不成立。原文：`G/product_board_g1_host.out`、`G/test_board_g1_host.out`。

### 2.3 G2 包与构建证据

| 项 | TV `.26` | RPI4 `.25` | workspace |
|---|---|---|---|
| RPM | `glibc-2.40-1.12.armv7l` | `glibc-2.40-3.12.armv7l` | `glibc-2.40-0.armv7l` |
| Source RPM | `glibc-2.40-1.12.src.rpm` | `glibc-2.40-3.12.src.rpm` | `glibc-2.40-0.src.rpm` |
| `%{OPTFLAGS}` 起始项 | `-O2 -fno-inline-functions ...` | `-O2 -fno-inline-functions ...` | spec 后置 `-O2` |
| CPU flags | `-mtune=cortex-a53 -march=armv8-a+crc` | `-mtune=cortex-a8 -march=armv7-a` | `-mtune=cortex-a8 -march=armv7-a` |
| 对应 debuginfo | 未安装；板上无 repo 配置/包管理器 | 未安装；未找到对应产品 repo | O2/Os debuginfo 均成功出包 |

workspace O2 的 `malloc.c` 命令含 `... -O2 ... -O2 ...`；Os 命令含 `... -O2 ... -Os ...`，后出现的优化等级生效。O2/Os 的 DWARF producer 分别记录 `-O2 -O2` 和 `-O2 -Os`。证据：`G/g2_workspace_o2_compile_commands.out`、`G/g2_workspace_os_compile_commands.out`。

### 2.4 G3 差分指纹

| 对象 | 文件 B | `.text` B | `.rodata` B | 动态函数数 | 动态函数尺寸和 B | 平均 B |
|---|---:|---:|---:|---:|---:|---:|
| TV 产品 | 1,453,496 | 1,133,824 | 123,157 | 3,003 | 606,980 | 202.125 |
| RPI4 产品 | 1,450,052 | 1,136,672 | 122,805 | 3,003 | 609,056 | 202.816 |
| workspace O2 | 1,450,052 | 1,136,672 | 122,805 | 3,003 | 609,056 | 202.816 |
| workspace Os | 1,282,064 | 975,768 | 116,436 | 3,003 | 541,668 | 180.376 |

| 函数 | TV | RPI4 | workspace O2 | workspace Os |
|---|---:|---:|---:|---:|
| `malloc` | 900 | 912 | 912 | 668 |
| `free` | 292 | 292 | 292 | 200 |
| `calloc` | 1,108 | 1,120 | 1,120 | 784 |
| `memcpy` | 784 | 784 | 784 | 784 |
| `strlen` | 220 | 220 | 220 | 220 |
| `_int_malloc` | stripped/不可取 | stripped/不可取 | 4,052 | 3,396 |
| `_int_free` | stripped/不可取 | stripped/不可取 | 1,052 | 968 |

距离定义：文件尺寸距离、`.text` 距离、动态函数尺寸和距离及五个导出标志函数的 MAPE 四项等权平均。

| 目标 | 候选 | 文件距离 | `.text` 距离 | 动态函数和距离 | 标志函数 MAPE | 复合距离 |
|---|---|---:|---:|---:|---:|---:|
| TV | workspace O2 | 0.2369% | 0.2512% | 0.3420% | 0.4833% | **0.3284%** |
| TV | workspace Os | 11.7945% | 13.9401% | 10.7602% | 17.3053% | **13.4500%** |
| RPI4 | workspace O2 | 0.0000% | 0.0000% | 0.0000% | 0.0000% | **0.0000%** |
| RPI4 | workspace Os | 11.5850% | 14.1557% | 11.0643% | 17.6522% | **13.6143%** |

RPI4 与 workspace O2 的 `cmp -l` 仅有 24 个差异字节：20-byte Build ID 和 4-byte `.gnu_debuglink` CRC；节表和动态符号尺寸无差异。TV 与 workspace 的 CPU flags、release 和产品分支不同，所以 G3 对 TV 只构成推断；G2 已直接证明 TV 为 O2。原始表：`G/fingerprint_metrics.tsv`、`G/fingerprint_distances.tsv`、`G/test_board_vs_workspace_o2_raw_diff.out`。

**G3 构建偏差：**纯 `-Os` 首次构建在 Tizen-only `libnss_optfiles.so` 链接失败，报隐藏符号 `__feof_unlocked` 未定义。最终成功构建在临时 clone 中仅对 `DATAFILE_PREFIX_PATH` 分支使用同一头文件内联体 `__feof_unlocked_body`；普通 `nss_files` 分支和 libc 主体逻辑不变。该偏差完整保留于 `F/g3_os_pure_build_failure_excerpt.out` 和 `F/g3_os_local_build.patch`。成功命令为：

```text
/usr/bin/time -v gbs -c <WORKSPACE>/gbs.conf build -A armv7l -B <WORKSPACE>/tmp/GBS-ROOT-RECON3-OS --include-all --define '_smp_mflags -j8'
```

成功尝试耗时 `4:48.42`，RC=0；主 RPM 和 debuginfo 均生成。未安装、未上板。

## 3. 组 E：glibc 身份与机制

通道均为 SSH root、无 PTY；命令在板上重定向到 `/tmp/tv_recon3_product_board/` 后用 SCP 拉回。E1=`/usr/lib/libc.so.6`，E2=`rpm -q/qi/--qf`，E3=`/usr/lib/ld-linux.so.3 --list-tunables`，E4=`ls/sha256sum` 后在 host 执行 `file/readelf/nm`。

| 项 | TV `.26` 事实 | 解锁的轨 B 决策 |
|---|---|---|
| E1 运行版本 | glibc 2.40，`Compiled by GNU CC version 14.2.0` | 固定产品 libc 主版本与编译器 |
| E2 包身份 | release `1.12`，与 RPI4 `3.12`、workspace `0` 均不同 | PG1 必须按产品分支实测，不携带 release 假设 |
| E3 tunables | `arena_max`、`mmap_threshold`、`trim_threshold`、`pthread.stack_cache_size` 全部由 loader 列出；stack cache 默认 `0x2800000` | 这些 tunable 在产品 loader 中注册 |
| E4 dlconf | `/run/dlconf.dat` 不存在 | TV 当前稳态没有该运行时文件 |
| E4 strip | libc/loader stripped，但保留 `.comment`；无 `.symtab` | 内部函数尺寸不能从产品 ELF 直接读取 |

命令：板上执行 libc、`rpm -q/qi/--qf`、loader `--list-tunables`；ELF 经 SSH pull 后由 host `readelf/file/nm` 解析。原文：`product_board/final_pull/tv_recon3_product_board/e1_e2_package.out`、`e3_tunables.out`、`e4_artifacts.out`。

## 4. 组 A：通道与执行策略

| 项 | 通道与命令 | 结果 | 解锁的轨 B 决策 |
|---|---|---|---|
| A1 SSH | SSH 22，`ssh -T root@<PRODUCT_BOARD_IP>` | root 可用；认证方式为 `keyboard-interactive`，无 PTY；默认公钥均不匹配 | 长采集使用 SSH stdin，具有真实退出码 |
| A1 SDB 回退 | host TCP/SDB 探测 | `26101` connection refused，SDB 未列出 `.26` | 本轮不能依赖 SDB 回退 |
| A2 UEP 路径 | 板上 `/bin/true` 原样复制后执行 | `/root` RC=0；`/tmp` 与 `/opt/usr/home` RC=126、`Operation not permitted`；均已删除 | 已签名板上 ELF 的可执行落点只有 `/root` 被本探针证实；外部 ELF 未测试 |
| A3 工具 | `command -v` | `systemd-run setsid nohup awk sed grep od dd rpm systemctl journalctl pmap` 存在；`readelf nm` 缺失 | 长采样脱离 SSH 所需工具存在；ELF 分析必须在 host |
| A4 `/etc` | `touch /etc/.wtest && rm` | 成功，探针已删 | drop-in 持久落点的写权限存在性已确认 |

## 5. 组 B：内存、回收与 PSI

通道均为 SSH root、无 PTY，输出先落板上文件再拉回。B1=`cat /proc/meminfo /proc/swaps`、`free`、读取 swappiness/zram；B2=`cat /proc/1/smaps_rollup`；B3=读取 overcommit、THP、CPU/governor、thermal、PSI、`df /dev/shm`；B4=读取 `/etc/ServiceR/*.conf` 和 ServiceR journal；B5=`dd` 向 `/dev/shm` 单文件分档追加并逐档读取 PSI/MemAvailable/dmesg。

| 项 | TV `.26` 实测 | 解锁的轨 B 决策 |
|---|---|---|
| B1 RAM | `MemTotal=1,599,416 kB`；初始 `MemAvailable=986,248 kB` | 按本板容量标定压力比例 |
| B1 swap | `/dev/zram0`，总计 1,039,320 kB、已用 48,268 kB；`swappiness=100` | L6 refault 可能涉及 zram swap，不能预设只有 minor fault |
| B2 rollup | `/proc/1/smaps_rollup` 可读且含 `Private_Dirty=2,384 kB` | 漏斗可使用 Private Dirty |
| B3 VM/THP | `overcommit_memory=1`；THP 目录不存在 | 固定回收协变量；THP 不构成本镜像协变量 |
| B3 CPU | 4 CPU，online `0-3`；四核 governor 均为 `performance`，可用列表也仅 `performance` | arena cores 基数=4；无需改 governor |
| B3 thermal | `/sys/class/thermal` 不存在 | 无 thermal-zone 协变量可采 |
| B3 shm | 799,708 kB，总已用 2,508 kB，探测前可用 797,200 kB | 40% 气球目标小于 shm 可用量 |

### B5 PSI 曲线

基线 `MemAvailable=990,900 kB`；最大目标 387 MiB，为基线的 40%，低于 60% 安全上限 580 MiB。表中值均为每档增长后的原文。

| 档 | 气球目标 | MemAvailable | PSI some `avg2/avg6/avg10` | PSI full `avg2/avg6/avg10` | LMK 匹配数 |
|---:|---:|---:|---|---|---:|
| 0% | 0 | 990,900 kB | `0.00/0.00/0.00` | `0.00/0.00/0.00` | 0 |
| 10% | 96 MiB | 898,616 kB | `0.00/0.00/0.00` | `0.00/0.00/0.00` | 0 |
| 20% | 193 MiB | 797,060 kB | `0.00/0.00/0.00` | `0.00/0.00/0.00` | 0 |
| 30% | 290 MiB | 695,676 kB | `6.95/3.12/1.99` | `6.32/2.83/1.81` | 0 |
| 40% | 387 MiB | 598,552 kB | `6.95/3.12/1.99` | `6.32/2.83/1.81` | 0 |

删除气球后 `MemAvailable=976,136 kB`，`BALLOON_CLEANUP_OK`。本次探针的 **PSI 可用响应窗口为 30%–40% 档**；四档均无新增 LMK 日志匹配。原文：`product_board/final_pull/tv_recon3_product_board/b5_psi_balloon.out`。

### B4 ServiceR/LMK 配置

`/etc/ServiceR/memory.conf` 的 `[Memory2048]` 节记录：`ThresholdSwap=300 MB`、`ThresholdLow=160 MB`、`ThresholdMedium=120 MB`、`ThresholdLeave=200 MB`、`ThresholdExtraMemFree=250 MB`、`ThresholdExtraMemAlloc=350 MB`。`[PSI-KILLING]` 记录 `startPSIKillAt=250`、`psiTriggerPercent=55`、`psiWindowSize=2000000`、`swapFreeLowPercentage=10`。`memory_product.conf` 只列 VIP process/app 覆盖；ServiceR journal 未打印所选 Memory 档，因此**运行时活动档无法从本轮证据确认**。原文：`product_board/b4_ServiceR_configs.out`、`product_board/b4_runtime.out`。

## 6. 组 C：真实进程拓扑

通道均为 SSH root、无 PTY。C0 将未经修改的 `docs/tizen_memopt_inventory.sh` 接在身份断言后经 `sh -s` 执行；C1/C3 读取 `readlink /proc/PID/exe`、cgroup、父链及 `systemctl`；C2 用 `cat /proc/PID/smaps` 拉回后在 host 运行既有 `parse_smaps.pl`；C4=`systemctl show UNIT -p ...`。全部输出先落板上文件再拉回。

### C0 inventory

- 111 个有效进程行；`AT_SECURE=1: 20`、`AT_SECURE=0: 91`、unknown 0；LIVE env 命中 0。
- 两条 `/proc/PID/cmdline` ENOENT 是遍历期间进程退出。
- `/proc/4kbtin` 不是通道损坏：它是产品内核真实存在的只读 proc 节点，且是 `/proc/[0-9]*` 唯一数字开头的非 PID 节点。原文：`product_board/proc_glob_check.out`。

### C1/C2/C3 Top-RSS 与 glibc 堆口径

下表的 heap 比例沿用 RPI4 `parse_smaps.pl`：`[heap]` 加 1 MiB 对齐、`rw-p`、匿名且长度不超过 1 MiB 的段，其 Private Dirty 占总 Private Dirty。

| RSS 排名 | PID | comm | RSS kB | exe/父拓扑 | systemd unit | heap+arena kB | 占总 Private Dirty | arena 近似数 |
|---:|---:|---|---:|---|---|---:|---:|---:|
| 1 | 2556 | `AppProcB` | 99,116 | `/usr/bin/ServiceH`；父为 launchpad pool | 无，`init.scope` | 14,872 | 44.5% | 17 |
| 2 | 562 | `AppProcD` | 90,656 | `/usr/bin/ServiceI`；父为 launchpad pool | 无，`init.scope` | 10,080 | 28.4% | 13 |
| 3 | 572 | `ServiceE` | 73,372 | `/usr/bin/wrt`；父为 launchpad pool | 无，`init.scope` | 7,912 | 40.6% | 11 |
| 4 | 3772 | `AppProcA` | 44,588 | `/usr/bin/ServiceH`；父为 launchpad pool | 无，`init.scope` | 4,960 | 37.3% | 12 |
| 5 | 265 | `enlightenment` | 42,184 | exe 自身；父 PID 1 | 无，`init.scope` | 2,936 | 20.4% | 6 |
| 6 | 1048 | `ServiceD` | 38,328 | app ELF；父为 launchpad pool | 无，`init.scope` | 1,948 | 25.5% | 5 |
| 7 | 4042 | `ServiceH` | 35,076 | `/usr/bin/ServiceH`；父为 launchpad pool | 无，`init.scope` | 3,412 | 31.2% | 11 |
| 8 | 1595 | `ServiceF` | 33,200 | `/usr/bin/issue_report_agent`；父 PID 1 | `issue_report_agent.service` | 996 | 14.9% | 4 |
| 9 | 669 | `ServiceC` | 29,552 | `/usr/bin/ServiceC`；父 PID 1 | `ServiceG.service` | 1,072 | 15.7% | 5 |
| 10 | 613 | `ServiceL` | 27,964 | app ELF；父为 launchpad pool | 无，`init.scope` | 964 | 23.7% | 1 |

这些 launchpad 后代的当前 `exe` 与父进程 `/usr/bin/ServiceJ` 不同，故本轮证据**不支持“纯 fork-without-exec”**；它们是 launchpad 拓扑且没有 per-app systemd unit。Top-10 中可由独立 systemd unit 注入环境的只有 `issue_report_agent.service` 和 `ServiceG.service`。

额外原生 service 的同口径数据：`ServiceV` 33.0%（928 kB，arena 6）、`pulseaudio` 29.6%（356 kB，arena 3）、`ServiceR` 22.8%（284 kB，arena 6）。完整排序：`product_board/C_glibc_heap_ratios.tsv`；原始 smaps：`product_board/final_pull/tv_recon3_product_board/C/smaps_retry/`。

### C4 systemd 属性

| unit | MainPID | Restart | StartLimit | Watchdog |
|---|---:|---|---|---|
| `issue_report_agent.service` | 1595 | `always` | 5 / 10s | 0 |
| `ServiceG.service` | 669 | `on-failure` | 5 / 10s | 0 |
| `ac.service` | 654 | `on-failure` | 5 / 10s | 0 |
| `pulseaudio.service` | 1309 | `always` | 5 / 10s | 0 |
| `ServiceR.service` | 2899 | `on-failure` | 5 / 10s | 0 |

没有实际 restart。原文：`product_board/C4_pull/c4_units.out`、`product_board/C_pull/C/c3_unit_map.out`。

## 7. workspace 源码/构建事实

- HEAD：`8f08a7e30396822a8d969d357822a6ffd56b43fb`，分支 `tizen_base`。这只是 workspace 审计基线，不等于 TV release `1.12` 产品分支。
- `packaging/glibc.spec:329-330` 从 `%{optflags}` 生成 BuildFlags，并后置 `-O2 -g`。
- configure：`--enable-add-ons=,libidn`、`--enable-kernel`、`--enable-bind-now`、`--disable-nscd`、`--disable-experimental-malloc`；ARM 禁用 multi-arch。
- spec 设置 `STRIP_KEEP_SYMTAB=*.so*`，但两块产品板的实际 libc 均 stripped；不能把 workspace strip 声明外推到产品。
- 基础包总是生成非 archive 的 `en_US.UTF-8`；locale 子包在 `build_locales` 时包含 `/usr/lib/locale/*`（排除基础 en_US）和整个 `%{_libdir}/gconv`。
- workspace O2 既有构建 RC=0；本轮 Os 构建 RC=0。两者都只在 host 出包，未安装、未上板。

证据：`G/workspace_e5_e6_raw.out`、`packaging/glibc.spec:320-390,529-555,690-824`、`F/g3_os_gbs_build.*`。

## 8. 三方对照（PG1）

| 项 | TV 产品 `.26` | RPI4 产品 `.25` | workspace 构建 | 对照结果 |
|---|---|---|---|---|
| glibc | 2.40-1.12 | 2.40-3.12 | 2.40-0 | **不一致** |
| compiler | Tizen GCC 14.2.0 | GNU GCC 14.2.0 | GNU GCC 14.2.0 | 主版本一致，发行串不同 |
| glibc optimization | O2 | O2 | O2 基线；Os 对照 | TV/RPI 基线一致 |
| CPU flags | cortex-a53 / armv8-a+crc | cortex-a8 / armv7-a | cortex-a8 / armv7-a | **TV 不一致** |
| libc Build ID | `3ae1c54a...` | `2d4df690...` | O2 `20bee9a6...`; Os `2467914e...` | **不一致** |
| libc size | 1,453,496 B | 1,450,052 B | O2 1,450,052 B; Os 1,282,064 B | TV 不同；RPI/O2 相同 |
| `.text` | 1,133,824 B | 1,136,672 B | O2 1,136,672 B; Os 975,768 B | TV 不同；RPI/O2 相同 |
| requested tunables | 四项全存在 | 四项全存在 | 源码/构建包含 | 一致 |
| `/run/dlconf.dat` | 不存在 | 存在，373 B | spec/code 支持，host 无运行态 | **板间不一致** |
| ELF residue | `.comment` 有；无 debuglink | `.comment` 无；有 debuglink | debuginfo 可出包 | **不一致** |

PG1 的明确不一致项是产品 release、CPU flags、Build ID、libc/`.text` 尺寸、dlconf 运行态及 ELF 残留节；workspace 源码结论不能替代 TV 产品实测。

## 9. 判定表

| 判定项 | 事实判定 |
|---|---|
| glibc 优化等级 | TV=GCC `-O2`；RPI4=GCC `-O2`；workspace 基线=GCC `-O2` |
| UEP 可执行路径 | 板上已签名 ELF 在 `/root` 可执行；在 `/tmp`、`/opt/usr/home` 被拒。外部/重新签名 alloc_bench 未测试，不能判定 |
| PSI 可用窗口 | 本次 30% 和 40% 气球档出现非零 PSI，未出现新增 LMK 匹配 |
| Top 目标 env 可达 | Top-10 中 2 个有独立 systemd unit；7 个是 launchpad 后代且无 per-app unit；`enlightenment` 位于 `init.scope` |
| 额外可注入原生 unit | `ac.service`、`pulseaudio.service`、`ServiceR.service` |
| glibc 堆排序最高三项 | `AppProcB` 44.5%、`ServiceE` 40.6%、`AppProcA` 37.3% |
| drop-in 落点 | `/etc` 写探针成功；`/run` 未做写探针 |
| cleanup | `RECON_TMP_CLEAN`、`BALLOON_CLEAN`、`SIGNED_TRUE_PROBES_CLEAN`，RC=0 |

## 10. 可比性声明

TV 产品平台的声明构建口味为全 GCC `-O2`；RPI4 平台为 LLVM 22.1.8 `-Os`、但 glibc 由 GCC `-O2` 构建。本轮直接证据只证明两块板各自 glibc 的 GCC/O2 身份，不把平台 service 的编译口味从 libc 反推出来。因此两板真实 service 的 RSS/PSS/性能数值不可互推；可对照的是本轮共同存在的 glibc 2.40 tunable/allocator 机制。

## 11. 原始证据位置

- TV 完整板侧文件：`board_results/tv_recon3_20260806/product_board/final_pull/tv_recon3_product_board/`
- TV ELF：`board_results/tv_recon3_20260806/product_board/product_elf/`
- TV 通道、pull、清理证据：`board_results/tv_recon3_20260806/product_board/`
- RPI4 板侧/ELF：`board_results/tv_recon3_20260806/test_board/`
- G1/G2/G3 指纹：`board_results/tv_recon3_20260806/G/`
- Os 构建命令、日志、失败与成功记录：`board_results/tv_recon3_20260806/F/`
