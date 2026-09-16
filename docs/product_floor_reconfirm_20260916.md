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

尚未连接；等待事前凭证推送、间隔门及执行器 host 测试。身份、基线、存活、画像、
floor 与注入可行性结论均未产生，不沿用旧测试板结果冒充产品板结果。

## 4. 复现

harness：[本轮目录](../tools/runners/product_floor_reconfirm_20260916/)。
冻结参数见 §1 与机器合同；host 测试：

```sh
python3 -m unittest discover -s tools/runners/product_floor_reconfirm_20260916 -p 'test_*.py'
```

公开采样若完成，用本轮 `analyze_floor.py --timeseries <timeseries.tsv> --output <summary.json>`
重放。确定性检查：公开输入字节、派生件重建、PID/start identity、PD 分桶加和、远端
RC 证明；实板数值没有人为相等容差，不以历史增量作验收带。采样时延、压力、PID
与版本差异如实披露。完整原始件留本地 board_results，可按请求提供。
