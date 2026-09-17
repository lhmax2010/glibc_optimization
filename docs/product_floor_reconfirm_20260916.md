# 产品板 floor 只读复确认（2026-09-16）

历史续跑状态见 §5；本轮正式执行的新增合同与结果见 §6。
§3 保留首次阻塞原记录；两次连接属于分别授权的两轮尝试，不是失败后自动重试。

## 1. 事前规格与边界

第 1 段英文影响报告已独立完成并推送 `9a8f10913af9d4cd31701f4abfb7359a95bd3125`；
本段任何停止不撤销它。板地址仅记 `<PRODUCT_BOARD_IP>`，不按 IP 判板。
本段只读，不推文件、不生成板端临时文件、不运行负载、不装卸包、不改配置、
不提权、不注入、不重启。

[机器合同](../tools/runners/product_floor_reconfirm_20260916/contract.json)与
[分析器](../tools/runners/product_floor_reconfirm_20260916/analyze_floor.py)先提交，
annotated tag `product-floor-contract-20260916` 推送后至少 600 s 才首次连接。
推送完成时间及实际间隔在后续证据中记录；合同与结果分提交。

身份门顺序：`uname -r` 不含 `rpi4` → `uname -m` 原样记录 → `/etc/os-release`
确认为产品 TV、非 unified-toolchain 开发镜像。发现测试板立即停，后续项不执行。
主候选 enlightenment / ServiceH / ServiceA 的原名只从既有本地脱敏映射恢复；
另列全系统可读进程中堆 PD 最高十项。对存活主候选与补充候选的并集静置采样，
每秒一次、持续 600 s（含两端 601 点）；无按键、无目标刺激。

字段与 smaps 分类严格沿用 08-14；单请求单项，包含远端 RC/DONE/FAIL 的请求体
不得超过 200 字节。记录主机采样截止时间、各读取区间与延误，不假称跨进程同时采得。
过程消失/重启、必要字段缺失或 RC 证明失败立即停，不伪造补点。
glibc 非 2.40 本身是版本告警而非替换镜像的授权。

分类直接复用[既有双标签判别器](../tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py)。
另审计 zram 正增长、majflt、total PD 与 other-anon 变化；标签不能单独证明具体
归还机制。floor 并列最小绝对值、首/末分钟最小值及差值；绝不把绝对 PD 当作历史
活动造成的增量，也不把 PD 当作可释放 bin。静置窗口不同于历史按键协议。

## 2. 历史对照定义

[08-14 归因后的候选清单](cyclic_fall_mechanism_attribution_v2_20260901.md)：
enlightenment `+1736 KiB` 是 retained 增量；ServiceH `2360 KiB` 是平台高度上界；
ServiceA `+788 KiB` 是逐轮谷底增量。不同 PID/启动历程、负载/按键、镜像和全局压力
均可改变值；本轮无 live/bin 分解，不能直接据 smaps 开启 trim。

## 3. 执行状态

**STOP_CONNECTION_FAILED，产品板身份未判定。** 首次连接即失败，未重试，
未执行任何板端 shell 请求。第 1 段英文报告已完成，不受本段停止影响。
本段不能判断该地址是否为 RPI4，也不能确认产品镜像；需 PM 确认当前产品板地址与
sdb 服务状态。没有依据把历史或测试板数值填为本次产品板观测。

### 3.1 通道与事前门时间线（UTC）

| 项目 | 实际记录 | 证据 |
|---|---|---|
| 第 1 段 main | `9a8f10913af9d4cd31701f4abfb7359a95bd3125`，先于本段已推送 | 本轮 Git 提交 |
| 合同 commit | `50da737f9976588472b66f5650929c60b7fca38a` | [间隔及字节门](../data/raw/product_floor_reconfirm_20260916/contract_gate.json) |
| annotated tag 对象 | `91f67a1d29c6f1a0a29957bee5dda5b9e2faf5c5` | [推送回执](../data/raw/product_floor_reconfirm_20260916/contract_push.json) |
| 远端推送完成确认 | `2026-09-16T11:25:09.822545+00:00` | 同上 |
| 首次操作前间隔核验 | `615.630770927 s`，超过 `600 s`，合同/分析器/历史判别器字节均一致 | 间隔及字节门 |
| 采集器版本 | `b408157`，本轮 23 项 host 测试通过后推送 | [harness](../tools/runners/product_floor_reconfirm_20260916/run_readonly.py) |
| 本机 sdb version | `11:35:25.454865` 开始，host RC=0 | [原文](../data/raw/product_floor_reconfirm_20260916/raw/sdb_version.txt) |
| 首次 sdb connect | `11:35:25.456995` → `11:35:28.479277`；host RC=1，输出明确 failed | [原文](../data/raw/product_floor_reconfirm_20260916/raw/connect.txt) |
| 终态 | `11:35:28.479647` STOP，无重试、无后续 devices/身份/采样请求 | [终态](../data/raw/product_floor_reconfirm_20260916/state.json)、[逐条命令](../data/raw/product_floor_reconfirm_20260916/commands.jsonl) |

本机原文：

```text
Smart Development Bridge version 4.2.25
```

连接原文（仅端点按既有映射脱敏，保留行结构）：

```text
connecting to <PRODUCT_BOARD_IP>:26101 ...
failed to connect to <PRODUCT_BOARD_IP>:26101
```

判断同时依据明确失败文本与 host RC，不把 sdb RC 当作成功证明。板端命令数为 0，
没有远端 RC/DONE 可记录，不能伪造身份门原文。200 字节/只读 allowlist/远端标志门
已做 host 回归，但本次未到达可现场验证它们的阶段。

### 3.2 身份、环境、候选与注入可行性状态

| 要求 | 状态 / 原因 |
|---|---|
| `uname -r` 不含 rpi4 | NOT_EXECUTED；连接门先失败，未产生原文 |
| `uname -m` 原样记录 | NOT_EXECUTED；未产生原文 |
| `/etc/os-release` 全文与产品 TV 判定 | NOT_EXECUTED；未产生原文 |
| glibc / MemTotal / uptime / date | NOT_EXECUTED；不沿用测试板 2.40 或内存容量 |
| enlightenment / ServiceH / ServiceA 存活、PID、启动时长 | NOT_EXECUTED；没有本次存活或近似候选结论 |
| 全系统 glibc 堆 PD Top 10 | NOT_EXECUTED |
| 10 分钟 smaps、fault、MemAvailable、zram 画像 | NOT_EXECUTED；未产生 timeseries 或 floor 派生件 |
| 与 08-14 的分类/floor 对照 | 无本次数据，§2 仅定义历史口径，不能判变化或一致 |
| gdb、ptrace_scope、id、df 侦察 | NOT_EXECUTED；未安装、未提权、未注入 |

### 3.3 结论与待 PM 事项

a) 尚不能确认任何候选 floor 仍在，也不能判定其量级足以进入注入轮。
b) 尚不能判断分类相对 08-14 是否变化；连接失败不是分类变化的证据。
c) 请 PM 先确认当前产品板地址及 sdb 可用状态。待只读复确认完成，再按实际 PID、
角色和释放时机提交目标/次数/窗口/暂停风险清单；本轮不请求或推定任何注入权限。
UI 合成器附加暂停可能影响画面，其他目标的实际职责和可观察影响须完成存活及角色
核验后再评估，不能仅据 Service 别名推断。

所有已采原文与公开件的双哈希见[发布清单](../data/raw/product_floor_reconfirm_20260916/publication.json)。
本轮没有板端产物，无需清理；没有配置、包、governor 或提权变更。不切 demo，
`demo-v14` 交付快照保持原样。

收线 host 核验：本轮测试最终为 25 项通过，包含只读 allowlist、200 字节硬闸、
连接失败/RPI4/开发镜像立即停止、无 RC 证明拒绝、进程完整性、采样超时停止与
发布双哈希。发布器首次 host 调用发现动态导入与脱敏函数返回值适配问题，
已修正并补发布回归；不涉及板端请求重试、不改合同或冻结分析器。

## 4. 复现

harness：[本轮目录](../tools/runners/product_floor_reconfirm_20260916/)。
冻结参数见 §1 与机器合同；host 测试：

```sh
python3 -m unittest discover -s tools/runners/product_floor_reconfirm_20260916 -p 'test_*.py'
```

本次仅有连接停止证据，不提供虚构的画像复算命令结果。今后公开采样若完成，
用本轮 `analyze_floor.py --timeseries <timeseries.tsv> --output <summary.json>`
重放。确定性检查：公开输入字节、派生件重建、PID/start identity、PD 分桶加和、远端
RC 证明；实板数值没有人为相等容差，不以历史增量作验收带。采样时延、压力、PID
与版本差异如实披露。完整原始件留本地 board_results，可按请求提供。

## 5. PM 确认恢复后的续跑（2026-09-16）

**STOP_CONNECTION_FAILED。** PM 确认板恢复正常并授权重新执行后，host 同步至
`f325489d8e7a5e1219c47ab74cd9e88df53d0b35`，沿用原事前合同、annotated tag
和推送回执。此次只尝试连接一次，仍返回明确失败；立即停止，未做额外网络探测、
重试、身份读取或提权。前轮阻塞不覆盖，本次证据独立存放于
[续跑证据目录](../data/raw/product_floor_reconfirm_20260916/resume_20260916/README.md)。

### 5.1 实际时间线与原文（UTC）

| 项目 | 记录 | 证据 |
|---|---|---|
| 执行开始 | `2026-09-16T13:58:47.865025+00:00` | [终态](../data/raw/product_floor_reconfirm_20260916/resume_20260916/state.json) |
| 合同核验 | `13:58:48.992148`；距原推送确认 `9219.169548731 s`，超过 `600 s`；三个冻结文件字节均相同 | [合同门](../data/raw/product_floor_reconfirm_20260916/resume_20260916/contract_gate.json)、[原推送回执](../data/raw/product_floor_reconfirm_20260916/resume_20260916/contract_push.json) |
| `sdb version` | `13:58:49.015136` → `13:58:49.055863`；host RC=0 | [原文](../data/raw/product_floor_reconfirm_20260916/resume_20260916/raw/sdb_version.txt) |
| `sdb connect <PRODUCT_BOARD_IP>` | `13:58:49.056201` → `13:58:55.065807`；host RC=1 | [原文](../data/raw/product_floor_reconfirm_20260916/resume_20260916/raw/connect.txt) |
| 终止 | `13:58:55.066236`；STOP，未执行 devices 或任何 shell 请求 | [逐条命令](../data/raw/product_floor_reconfirm_20260916/resume_20260916/commands.jsonl) |

客户端原文：

```text
Smart Development Bridge version 4.2.25
```

连接原文（只替换端点，行结构保留）：

```text
* Server is not running. Start it now on port 26099 *
* Server has started successfully *
connecting to <PRODUCT_BOARD_IP>:26101 ...
failed to connect to <PRODUCT_BOARD_IP>:26101
```

前两行是客户端在 host 自动启动本地 sdb server，**不是板端连接成功**；随后对
26101 的连接明确失败。本轮没有主动执行 kill-server/start-server，也没有任何板端
shell 请求，因而不存在可记录的远端 RC/DONE/FAIL；不能用 host RC 冒充远端证明。

### 5.2 尚未执行的项与结论

| 核验项 | 本轮状态 |
|---|---|
| `uname -r` / `uname -m` / 完整 `/etc/os-release` | 全部 NOT_EXECUTED，无原文；产品 TV 或 RPI4 身份均未确立 |
| glibc RPM 与 libc 版本输出、MemTotal、CPU/核数、uptime/date/df | NOT_EXECUTED；没有版本或容量可与机制基线比较 |
| 三个主候选、近似匹配与 Top 10、PID/启动时长 | NOT_EXECUTED；不据历史存在推定本轮存活 |
| 10 分钟画像、分类、floor 与历史对照 | NOT_EXECUTED；没有 timeseries 或 summary，不产生新数字 |
| gdb、ptrace_scope、id 与 attach 风险现场依据 | NOT_EXECUTED；不安装、不注入、不提权 |

a) 不能确认任何候选 floor 仍在或足够大，不能推荐具体目标进入注入轮。
b) 不能判定分类相对 08-14 是否变化；镜像、业务与时段差异只能作为后续待验证因素。
c) 请 PM 再确认当前产品板地址、sdb 26101 服务及 host 至板的可达性。完成只读候选
与角色确认后，下一轮注入仍需单独批准目标/PID、次数、业务时机、暂停与看门狗风险、
异常时停止后续调用和解除附加的回退方式；本次不预授权安装、注入或重启。
d) **本轮没有已证实需要 root 的读取项**：权限检查根本未开始。连接失败不能据此
归因为 UID 或读取权限，不能把提权作为本次补救。若后续遇到不可读项，须单列等 PM 授权。

### 5.3 host 闭环与复现

采集器提交 `733b5e5` 补齐本次要求的 libc 版本、CPU online 和进程年龄换算读取，
仍为固定只读命令，带远端标志并受 200 字节本地硬闸约束。增加活进程空 smaps
不得静默排除的完整性检查；相关 host 测试共 26 项通过。合同、冻结分析器与历史
判别器未改；上述新读取本次均未在板端执行。

本次实际使用的采集入口如下（端点及映射为本地输入；**不是失败后可自动重试的授权**）：

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_readonly.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --push-receipt board_results/product_floor_reconfirm_20260916/contract_push.json \
  --output board_results/product_floor_reconfirm_20260916/attempt2
```

输出目录已留存，不得覆盖。重新连接需另行确认；host 测试与固定口径复算入口仍见 §4。
[发布清单](../data/raw/product_floor_reconfirm_20260916/resume_20260916/publication.json)
记录原始/脱敏件双哈希；完整原始件本地留存，可按请求提供。
本轮无板端文件、包、配置、governor 或 UID 变更，无板端清理动作；只推 main，
不切 demo，既有 `demo-v14` 不变。

## 6. 正式执行：PM 解决连接并授权 /tmp 只读采样脚本（2026-09-16）

本节先于本轮连接提交。PM 明确将采样传输方式改为：只读 shell 脚本推送至 `/tmp`
执行，输出回收后删除脚本，不留下板端产物。旧合同的禁推送条款不覆盖本次新授权；
旧文件、旧 tag 和前三次通道记录均保留，不作事后改写。

本轮使用[新增机器合同](../tools/runners/product_floor_reconfirm_20260916/board_script_contract.json)，
annotated tag `product-floor-board-script-contract-20260916`，推送确认至少 600 s 后
才连接。原 [analyze_floor.py](../tools/runners/product_floor_reconfirm_20260916/analyze_floor.py)
及历史判别器原字节复用；不改变样本数、分桶、阈值或 floor 派生定义。

硬身份门为：内核不得含 rpi4、架构严格 armv7l、OS 确认为 Tizen10/TV 产品镜像而非
unified-toolchain 开发镜像。历史 6.12.60 仅作对照；`command -v vk_send` 仅查存在，
缺失记录但不否决，绝不实际调用按键工具。不走 SSH、不提权、不装卸包、不注入、
不改配置或 governor、不重启、不干预业务。

采样对象为存活主候选与完整可读进程 Top 10 的并集，601 点覆盖 600 s。板端按
单调 uptime 定时，每槽并行读取进程与全局量，逐批记录读取区间；超出下一槽截止时间
即停并保留部分原文，不调周期或伪造数据。全量进程视图无法证明、活进程 smaps
不可读/为空、目标 PID/start 变化或必需字段缺失均停止；待授权读取项单列。

只允许本轮唯一命名 `/tmp/pf_20260916_<hex>.sh` 脚本文件，推送前检查不存在，
执行前复核 SHA-256，结束（含失败）时仅清理本轮自身且字节匹配的脚本并复核缺失。
输出通过 sdb 直接保存在 host，不在板上落采样结果文件。安装可行性仅查询已装包、
工具存在、RPM 数据库权限和空间，不做试装，不能把文件可写等同于已获安装/attach 权限。

事前状态：合同已写定，等待事前门及执行器 host 核验；下方另记实际结果，不以本段代替
身份原文、数据或收尾证明。

### 6.1 本轮结果与停止原因

**连接恢复，产品身份门通过；画像未执行。** 本轮在板端依赖检查时，
`command -v timeout` 返回远端 `RC=1 / FAIL`、无路径输出。执行器把独立 `timeout`
作为限制自身探针存活时间的必要依赖，故立即停止。这是本轮执行器引入的兼容性缺口，
不是产品身份失败、不是 sdb 再次故障，也没有证据表明是读取权限不足。
未临场安装工具、改用另一入口或重新连接重试；不把未经验证的替代方式当作已完成采样。

本轮实际只有 26 条 sdb 调用，其中 23 条为带远端标志的只读 shell 请求；
没有 push、脚本执行、候选盘点或采样请求。没有本轮板端文件需要删除，
[收尾动作列表](../data/raw/product_floor_reconfirm_20260916/formal_board_script/cleanup.json)为空。
这是“尚未创建产物”的操作证据，不是对整板既有文件的卫生审计结论。

| 时间线（UTC） | 实际记录 | 证据 |
|---|---|---|
| 新合同提交 | `495f627e0751b71e1bc93e879be7187d1bf43d23` | [推送回执](../data/raw/product_floor_reconfirm_20260916/formal_board_script/contract_push.json) |
| annotated tag 对象 | `9f8f504c12fb182df42cd593ea001582427e00e4` | 同上 |
| 推送完成确认 | `2026-09-16T14:46:42.431004+00:00` | 同上 |
| 事前字节/间隔门 | `14:57:44.081515`；`661.650452998 s`，超过 600 s；四个冻结文件哈希一致 | [合同门](../data/raw/product_floor_reconfirm_20260916/formal_board_script/contract_gate.json) |
| 执行器提交 | `80332940df48db7b85db0e5101a9c553a192b714`，连接前已推 main，38 项 host 测试通过 | [终态与执行器哈希](../data/raw/product_floor_reconfirm_20260916/formal_board_script/state.json) |
| sdb connect | `14:57:44.085947` → `14:57:46.091852`，明确 connected，devices 为 device | [connect 原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/connect.txt)、[devices 原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/devices.txt) |
| 三项硬身份门 | `14:57:46.096765` → `14:57:46.482732`，全部远端 RC=0 / DONE | [逐条记录](../data/raw/product_floor_reconfirm_20260916/formal_board_script/commands.jsonl) |
| timeout 依赖门 | `14:57:49.017944` → `14:57:49.134222`，host RC=0，但远端 RC=1 / FAIL | [失败原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/timeout_path.txt) |
| STOP | `14:57:49.134735`，其后无板端请求 | 终态与逐条记录 |

最后一条请求及完整输出：

```sh
sdb -s '<PRODUCT_BOARD_IP>:26101' shell 'LC_ALL=C command -v timeout;r=$?;echo;echo RC=$r;test $r = 0 && echo DONE || echo FAIL'
```

```text

RC=1
FAIL
```

只可判定当前 SDB 会话 PATH 中查不到该独立命令；没有检查其他路径或工具的同类功能，
不能扩大为“整份固件没有任何超时机制”。host RC=0 未被误认成功。

### 6.2 产品身份原文

`uname -r`（[原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/uname_r.txt)）：

```text
6.12.60

RC=0
DONE
```

`uname -m`（[原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/uname_m.txt)）：

```text
armv7l

RC=0
DONE
```

`cat /etc/os-release`（[全文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/os_release.txt)，
镜像名称及 BUILD_ID 按既有映射脱敏，未删行；判板在脱敏前完成）：

```text
NAME=Tizen
VERSION="10.0.0 (<PRODUCT_IMAGE>)"
ID=tizen
VERSION_ID=10.0.0
PRETTY_NAME="<PRODUCT_IMAGE>"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:10.0.0"
BUILD_ID=<PRODUCT_BUILD_ID>

RC=0
DONE
```

原镜像标识为 Tizen10/TV 产品系列，不是 unified-toolchain；内核与历史 6.12.60 系一致，
无 rpi4，架构符合本轮 armv7l 硬门。旁证 `command -v vk_send`
（[原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/vk_send_path.txt)）：

```text
/usr/bin/vk_send

RC=0
DONE
```

只查询存在，未调用按键工具；身份来自这些实际特征，不以共享 IP 判板。

### 6.3 环境基线与能力实测

| 项目 | 本轮读取值 / 限定 | 原文 |
|---|---|---|
| glibc RPM | `glibc-2.40-1.12.armv7l` | [rpm](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/glibc.txt) |
| libc 版本与编译器 | GNU libc 2.40；GNU CC 14.2.0 | [完整版本输出](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/libc_version.txt) |
| MemTotal / MemAvailable | `1599416 / 1002980 kB`，一次快照，不是 10 分钟趋势 | [meminfo 全文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/meminfo.txt) |
| CPU | armv7l；online `0-3`，即 4 个在线核；CLK_TCK=250 | [online](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/cpu_online.txt)、[CLK_TCK](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/clk_tck.txt) |
| uptime / load | `up 2:14`；load `29.01, 29.00, 29.02`，不据单次值推断业务类别 | [uptime](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/uptime.txt) |
| 单调 uptime | `8058.09 22970.45` | [proc uptime](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/proc_uptime.txt) |
| 板端 UTC | `Wed Sep 16 14:58:27 UTC 2026` | [date](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/date.txt) |
| 根目录可见 overlay / `/opt` | 各显示可用 `2.5G`、36%；为同一底层空间，不能相加 | [df 全文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/df.txt) |
| 只读镜像下层 / 临时目录 | `/.org_rootfs` 可用 0；`/tmp` 可用 781M；`/mnt/systemrw` 可用 11M | 同上 |
| 当前 UID | `5001(owner)`，`context="User::Shell"`，未提权 | [id 全文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/id.txt) |
| gdb | `gdb-15.1-1.2.armv7l` 已安装；没有调用 gdb | [rpm -q gdb](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/gdb.txt) |
| yama | `/proc/sys/kernel/yama/ptrace_scope` 不存在，远端 RC=1；不是 Permission denied | [原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/ptrace_scope.txt) |
| 包工具 / 数据库路径 | rpm=`/usr/bin/rpm`；zypper 未找到；`%{_dbpath}`=`/var/lib/rpm` | [rpm](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/rpm_path.txt)、[zypper](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/zypper_path.txt)、[dbpath](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/rpm_dbpath.txt) |
| 会话权限旁证 | 同会话执行的 `cat /proc/self/status`：Uid=5001，CapPrm/CapEff/CapAmb=0 | [原文](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/shell_status.txt) |
| 探针依赖 | `/tmp` 可写检查成功，awk=`/usr/bin/awk`；timeout 查询失败导致 STOP | [tmp](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/tmp_writable.txt)、[awk](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/awk_path.txt)、[timeout](../data/raw/product_floor_reconfirm_20260916/formal_board_script/raw/timeout_path.txt) |

glibc 上游版本仍为 2.40，未触发 2.41+ 版本迁移告警；RPM 构建修订与测试板不同，
不能据版本相同假定 allocator 布局、floor 或产品收益相同。板端 date 与 host UTC
约差 40 s，uptime 自带时刻字段亦与 date 不同，均保留原文，未校时/改时区。
没有实际采样序列，不能把这些时钟快照充当相位对齐证明。

meminfo 自带 zram 汇总为 `97652 kB OrigDataSize / 26087 kB ComprDataSize /
35608 kB MemUsedTotal`；这是单次内核展示值，不是合同要求的逐秒 sysfs 字节序列，
不能据此判 zram 平坦或排除换出。`shell_status` 是采集标签，其 `/proc/self`
指向读取命令 cat 本身，不是父 shell 或候选进程的状态；不能由它证明 attach 能力。

**历史记录 vs 本轮实测**：历史产品侧“只读与环境变量方式、不支持 lldb 注入”及
[不可装包约束](product_m7_feasibility_20260902.md#41-前置与建议采集形态)保留为当时结论；
PM 现告知可安装 gdb，而本轮已直接查询到 gdb 包。已安装不等于当前 UID 可以安装、
删除包或 attach。RPM 数据库可写检查尚未执行，未尝试包事务，不能判“安装权限已通过”。
yama 文件缺失也不能排除其他 ptrace、凭据或安全策略限制；本轮未查询 lldb，
未把测试板历史能力外推为产品板当前能力。

### 6.4 候选、floor 与下一轮权限边界

| 候选 / 要求 | 本轮状态 | 历史对照仅作待验证项 |
|---|---|---|
| enlightenment | 存活/PID/启动时长、角色现场核验、画像均 NOT_EXECUTED | retained 增量 `+1736 KiB`，不是当前绝对 floor |
| ServiceH | 同上；未检查真实原名或近似候选 | 平台高度上界 `2360 KiB`，不能直接当可回收量 |
| ServiceA | 同上 | 谷底增量 `+788 KiB`，不能直接当当前驻留量 |
| 堆 PD Top 10 | NOT_EXECUTED，未获得全系统进程视图 | 不按历史排名补齐 |
| 10 分钟 smaps / faults / MemAvailable / zram | NOT_EXECUTED，无 timeseries 或 summary | 没有本轮分类、floor、换出排除或变化归因 |

历史量出处仍见 §2。当前不能选择“floor 仍在且值得注入”的目标，也不能判断分类变化。
镜像、业务和采样时段差异只能作为后续待核对因素，不能在没有序列时给出变化归因。

下一轮风险评估仍待进程核验：enlightenment 若确为在用 UI 合成器，attach 暂停可能
表现为画面/输入停顿；ServiceH、ServiceA 的具体职责、关键性和看门狗不能仅凭别名
推定，需 owner 确认是否会造成服务超时或恢复动作。本轮没有 attach，因此没有实测
暂停风险或“可安全注入”的结论。

需 PM 单独批准的后续注入事项应包括：确认后的目标 PID/启动身份、实际角色、调用种类
及次数、自然空闲/释放时机、最大允许暂停时间、画面/服务/watchdog 观察项、异常时停止
后续调用并解除附加的回退方案；不得默认授权杀服务、重启或改安全配置。
**当前没有已证实需 root 才能读取的项**；完整 ps、候选 smaps 与 sysfs 读取尚未开始，
只能标“未测试”，不能把 UID=5001 当作必须提权的证据。

### 6.5 收线与复现状态

本轮未改 governor/包/配置/UID，未注入、未执行业务负载或 SSH；没有板端脚本/结果
落盘，没有清理删除。全部 26 条调用的原文公开，完整私有原文仍本地留存，可按请求提供。
[发布清单](../data/raw/product_floor_reconfirm_20260916/formal_board_script/publication.json)
记录 31 个证据文件的原始/公开双哈希；新增镜像字段与端点按既有映射脱敏，保留行结构。

复现入口为[本轮 harness](../tools/runners/product_floor_reconfirm_20260916/README.md)，
参数与分析器仍按 §6 新合同；§4 host 测试命令可直接运行，收线共 39 项通过。
本次只有 STOP 原文，没有画像派生件可重放，不能声称 601 点、1 s 时序、目标身份或
PD 分类已在板上验收。确定性项与采样质量门不放宽，不拿历史值替代本轮缺失值。

待闭合的是 **host 执行器对产品工具集的兼容性**：先在 host 设计并测试不需要安装/提权
的有界探针执行方式，保持原合同的采样口径与安全门；如需改合同定义，须另行裁决。
本轮依停止门不实现现场替代、不重连；需明确续跑后才再次执行。连接故障已恢复，
不再把“请 PM 开启 sdb”作为当前建议。只推 main，`demo-v14` 保持不变。

## 7. 可移植执行器与可读范围续跑（2026-09-17）

本节为连接前登记。PM 本轮明确授权：去除板端 timeout 依赖；工具缺失一次列全；
主候选 smaps/status 先只读预检，全不可读不推脚本，部分可读只采可读者。
旧合同与 §6 原文保留；本轮按[portable_contract.json](../tools/runners/product_floor_reconfirm_20260916/portable_contract.json)
执行，annotated tag 为 `product-floor-portable-contract-20260917`，推送确认后至少
600 s 才连接。分析器、历史分桶、601 点/600 s、判别器与 floor 定义原字节沿用。

计时使用 shell 循环和 `/proc/uptime` 截止时间，不调用 timeout；`date +%s` 只用于
墙钟锚点，逐点 epoch_ns 由该锚点加单调时钟增量构造，不声称纳秒墙钟精度。
没有 sha256sum 时明确记录，回读脚本完整字节在 host 比较；不跳过脚本身份核验。
Top 10 仅覆盖实际可读进程，排除项/视图限制逐项披露，不冒充全系统排名。

所有板端请求仍受 200 字节和远端 RC/DONE/FAIL 约束；不提权、不注入、不装卸包、
不改配置、不重启、不干预业务。先提交合同与分析器再连接；结果另行追加。
