# 产品板 floor 只读复确认（2026-09-16）

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
