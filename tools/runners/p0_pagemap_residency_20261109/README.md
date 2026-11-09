# P0：pagemap 驻留态、malloc_trim 导入符号与 zram 侦察

## 目的与预测

验证预测文件中的 H1–H4。预测写入时间为 2026-11-09 19:17:02（UTC+8），
SHA-256：`ab68cc2645f08a30069d58f562993811746b24e17e396d6904b594925ddeab14`。
本轮首次 heap 测量请求开始于 2026-11-09 23:05:43.874437+08:00，晚于预测。
原预测全文、逐次原文与时刻见 [原始证据目录](../../../data/raw/p0_pagemap_residency_20261109/)。

## 首次执行与七次续跑

日期均为 2026-11-09，时间为 UTC+8；这是首次执行加七次续跑，共八次尝试。

|批次|时间|停止原因或结果|
|---|---|---|
|首次|19:17|sdb 连接失败|
|resume1|19:40|身份门后交互会话 Broken pipe|
|resume2|20:19|非 root|
|resume3|20:39|板上无 readelf|
|resume4|20:57|板上无 gdb，仓库注入工具依赖 gdb|
|resume5|21:31|可执行文件字符串 grep RC=2；保留部分命中，zram 侦察已完成|
|resume6|22:19|固定 grep -A20 截断 heap 块，缺少 SwapPss；符号确认、便携 GDB 已完成|
|resume7|23:05 开始 heap 采集|三次 trim 完成；23:07 收尾并恢复 UID5001|

符号确认沿用 resume5 的给定列表，不声称补齐了 RC=2 未枚举到的文件。
31 条路径中30条为 UND 导入、1条定义、0条字符串误命中；路径包含别名，
不能当作30个独立程序，也不能据静态导入证明实际调用。
resourced、libappcore-common、libapp-core-cpp、liblaunchpad 均为 UND。

## 板子身份与环境

以下来自 resume7，身份不依赖连接地址。

```text
6.12.80-arm-rpi4-v7l
```

```text
armv7l
```

```text
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20261106.063932_tizen-headed-armv7l
```

```text
0
```

```text
MemTotal:        3976468 kB
```

目标 enlightenment，PID555，starttime1581，与 resume6 一致。
AT_SECURE=0；采集窗口不包含历史累积 faults。板端只写 /opt/usr/p0；收尾目录已删除、UID5001。

## GDB 来源与便携解包

指定源码来自完整 Git 克隆的 demo-v14 commit
`7289a47b9d24791944cd3b02c00f24b8cb76aa3b`。
GDB RPM 唯一来源为 Tizen Base Toolchain snapshot `20261030.120529` 的 armv7l 仓库。
六包名称、完整URL、SHA-256、大小、repodata 比对结果保存在
[resume6_rpm_verification.json](../../../data/raw/p0_pagemap_residency_20261109/resume6_rpm_verification.json)。
所有包均与 primary 元数据一致；primary 校验链见 resume6_repodata_proof.json。

宿主在独立空目录中，逐包使用 `rpm2cpio <rpm> | cpio -idm` 解入同一 gdbroot，
生成便携 tar；未在板上安装或卸载 RPM。GDB 归档为54579200字节，SHA-256
`ab4f53de6506a3597479008510b80e870de140e9b995a527c08b8288b146e736`。
resume7 校验后复用；没有重新下载。板上 GDB16.3 版本确认通过。
包、归档、解包树与 ELF 均不在本目录内。

## 宿主复算（不连接板子）

在仓库根目录执行：

```sh
python3 -B tools/runners/p0_pagemap_residency_20261109/recompute.py
```

重建派生表并与固定参考表核对：

```sh
python3 -B tools/runners/p0_pagemap_residency_20261109/recompute.py --write
```

输入为 resume7_data 中的六份 smaps/maps/pagemap/stat、三份 pre XML、auxv，
以及 resume7_state.json 的 host 纳秒时间戳与原始 trim 回执。
注入耗时由 end_ns−start_ns 直接计算，包含 sdb、脚本、gdb/ptrace，不是函数自身耗时。
采集按顺序进行，并非同一时刻冻结的原子快照；faults 的 pre stat 在 XML 采集之后。

`derived/manual_*.tsv` 为从原文逐项核对后单独固定的参考表，未调用 recompute.py 生成。
residency 参考值来自原始smaps、pagemap位计数、stat与日志；XML参考表按各arena条目相加与相减核对。
脚本独立使用 ElementTree 解析，并逐值、逐字节比对两张参考表和派生表。

XML表严格按本次指定定义：rest 为该arena的 total[type=rest].size；
top = rest − sizes 下所有 size/unsorted 的 total 之和。
`sorted_ge_page_total` 按 size.to≥4096 分类，`sorted_lt_page_total` 按 size.to<4096 分类。
这些 size 条目可能含 fastbin 范围；本表不另行扣除或重定义，top 列是指定公式结果。
整页内腔仅统计 sorted≥1页条目，不含 unsorted 或 top；用整数算式
`count × max(0, (total − 24×count) // (4096×count)) × 4096`，与指定公式完全等价。
该列是直方图派生量，不等同于实测可回收页。

## 板上复现步骤（本次整理没有执行）

1. 在隔离本地目录准备预测、指定demo-v14工具与已校验的便携GDB；读档案驱动前核对其本地路径。
2. root on 后重做 uname-r/uname-m/os-release 与 root、/opt/usr空间及挂载门。
3. 仅在 /opt/usr/p0 恢复GDB；校验版本。确认目标PID与starttime，采auxv。
4. 每次pre用awk从heap头读至VmFlags；取maps并按4096字节页读取pagemap。
   按指定工具模板采malloc_info，再读stat；调用指定trim_via_gdb.sh；完整采post。
   三次之间不加负载，不重启目标。
5. 每条sdb请求≤200字节，相邻调用≥0.5秒，总数≤150；仅一次性调用、串行。
6. 归档拉回后删除 /opt/usr/p0 并核验，root off，复核UID5001。

历史驱动按原字节保存，包含原会话的路径与状态约定；不是可直接在公开目录启动的板上入口。
原始 FILES/SHA256SUMS 是当时完整本地材料的清单，含本次明确排除的二进制条目，不能作为公开目录完整性清单。
copy_manifest.json 记录本次白名单复制件哈希；recompute 检查这些复制件，缺失或改动即失败。

## 判据结果

|次数|present前→后|PD/RSS前→后 KiB|reclaimed_bytes|faults增量 min/maj|trim返回|注入ms|H1|H3|
|---|---|---|---|---|---|---|---|---|
|1|848→840|3392→3360|32768|0/0|1|1560.724471|成立|成立|
|2|840→840|3360→3360|0|0/0|1|1900.282497|成立|成立|
|3|840→840|3360→3360|0|0/0|1|1569.708798|成立|成立|

H1三次差额均0字节；H2第二、三次均0页/0字节；H3三次差额均0字节；
H4六份pagemap的swapped页数均0。三份XML均完整。上述为本次同一进程的观测。

## 脱敏说明

板子地址使用字面量 `<TEST_BOARD_IP>`，串口形式保留端口为 `<TEST_BOARD_IP>:26101`。
仅修改候选副本，local_review 源目录只读。原测量数值、时间戳、原始哈希及判据结果不变。
驱动通过 P0_BOARD_IP 环境变量或已有命令行参数显式接收地址，默认空值，缺省退出码2；本次不启动板上流程。
历史采集脚本除地址参数化外未变，其旧路径/状态约定仍需在隔离本地目录准备。

本次改动文件清单见 derived/redaction_manifest.json；公开 diff 的删除行使用 `<ORIGINAL_BOARD_IP>` 隐藏原地址，
因此它是脱敏后的差分，不是含原始端点的逐字节差分。diff 中只含端点替换与地址输入参数化。
其余新增文本形式和复算支持不属于该差分，未改原始证据。
copy_manifest.json 中原始 sha256 字段不变；脱敏副本由 derived/public_copy_hashes.json 独立校验。

七个二进制证据文件扫描零命中，原字节保留，同时新增六份不含PFN的 pagemap_bits.tsv（page_index从0开始）与 auxv.tsv。
复算以文本形式为主，并与二进制形式独立重算的两张派生表逐字节比对；另外逐页比对四个标志位。
二进制原始哈希同时登记在 derived/local_only_FILES.tsv：

|文件|字节数|原始 SHA-256|
|---|---:|---|
|resume7_data/t1_post_pm.bin|16768|dcc9626d73fb65ef3cc01a8b53f7d3075a6863d48805b7505ad4a3548f770b82|
|resume7_data/t1_pre_pm.bin|16784|1dd301877219292a0c1fa0f25c270bb54cd91f940673860872a85ab76d4d7c71|
|resume7_data/t2_post_pm.bin|16768|dcc9626d73fb65ef3cc01a8b53f7d3075a6863d48805b7505ad4a3548f770b82|
|resume7_data/t2_pre_pm.bin|16768|dcc9626d73fb65ef3cc01a8b53f7d3075a6863d48805b7505ad4a3548f770b82|
|resume7_data/t3_post_pm.bin|16768|dcc9626d73fb65ef3cc01a8b53f7d3075a6863d48805b7505ad4a3548f770b82|
|resume7_data/t3_pre_pm.bin|16768|dcc9626d73fb65ef3cc01a8b53f7d3075a6863d48805b7505ad4a3548f770b82|
|resume7_data/auxv.bin|176|5e4cc2c5072654345372d4f3016b3970628e6aa5df6813fc555fec95e19c9093|

### readelf 原始转储与派生符号表

readelf 原始转储因含符号地址（会触发端点扫描的十六进制规则）留本地，仓内为派生符号表。
31份原文的字节数和原始SHA-256登记到 derived/local_only_FILES.tsv，原有七份.bin条目保留；
.bin仍在仓内，表名不表示它们被排除。copy_manifest与public_copy_hashes中原readelf哈希作为历史记录保留，
recompute 对这31份明确排除的转储核对清单，不再要求仓内原文；测量证据仍全部按哈希校验。

宿主复算（LOCAL_P0_RAW 指向本地原readelf转储目录，缺失则报错，不连接板子）：

```sh
python3 -B tools/runners/p0_pagemap_residency_20261109/extract_symbols.py --raw-dir "$LOCAL_P0_RAW"
```

生成或更新表时加 `--write`。输入映射见 derived/readelf_sources.tsv；
脚本检查31份原文SHA-256/大小、与resume6报告逐路径判定一致，再逐字节核对两张派生表。
输出只含 board_path、realpath、bind、type、ndx、symbol；未采集 readlink -f，realpath 全部留空，
不根据别名或归档解引用结果推测实际路径。符号字符串误命中与readelf失败均按原记录独立标记。
