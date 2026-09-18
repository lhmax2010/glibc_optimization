# 产品 floor 只读复确认

## 2026-09-17 PM 授权的不落盘驱动

当前轮采用 `run_diskless.py`，不再调用下述历史脚本入口。板上零文件、零 push，
仅发送一条短读取及固定 RC/DONE 包装；实际发送前校验只读 allowlist 和 200 字节
上限。脚本签名失败的历史保留，本方法不申请签名也不绕过镜像文件执行校验。
显式授权参数仅表示本轮 PM 已许可的 root on/off，不是对未来轮次的默认授权。

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_diskless.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --previous-private-snapshot board_results/product_floor_reconfirm_20260916/root_authorized_20260917/permissions.json \
  --push-receipt board_results/product_floor_reconfirm_20260916/diskless_push.json \
  --output board_results/product_floor_reconfirm_20260916/diskless_20260917 \
  --pm-authorized-readonly-root
```

私有候选名快照必须经既有映射后与公开冻结快照逐值一致；不能用地址判板。
新合同 `product-floor-diskless-contract-20260917` 必须是已推送 annotated tag，
合同/分析器/候选快照逐字节核对，双时钟证明推送至连接至少 600 s。
不写板端文件，不使用 timeout/sha256sum，不安装、不注入、不发送目标信号。
root on/off 各一次，失败亦查询 id；完成条件含恢复 UID5001 的原文证明。

每目标至少 600 s，初始目标 1 s，最近 10 批间隔中位 >1.5 s 时只降级一次至
目标 2 s。保留所有实际起止时刻，不重跑、不补点。完整 smaps 20 s 超时才
改为短 awk 只传映射头与 Private_Dirty，由原 parser 在 host 汇总；再失败即停。
该模式仍保留全部四个 PD 数字，但必须披露减少了传输字段及不同的读取窗口。
全局量与目标量分任务读，不能当作原子快照；实际抖动/偏移是报告的一部分。

host-only 重放入口（仅当本轮存在完整成功序列）：

```sh
python3 tools/runners/product_floor_reconfirm_20260916/analyze_diskless.py \
  --timeseries '<公开 timeseries.tsv>' --timing '<公开 sampling_timing.json>' \
  --output /tmp/product-floor-diskless-summary.json
cmp /tmp/product-floor-diskless-summary.json '<公开 summary.json>'
```

确定性验收：合同字节、冻结候选集合、身份、逐请求 RC、字段齐全、PD 分桶相加、
PID/start 稳定、每目标实际时长、真实降级记录、零文件传输、root 恢复。
数值容差：不要求产品自然业务 floor 重现历史活动增量；不以结果修改分类阈值。
历史 heap 分类是映射启发式，并非 allocator live/bin 或可 trim 收益的直接测量。

## 历史入口（保留原合同，不用于当前轮）

旧入口 `run_readonly.py` 只在 host 执行，不推送任何脚本/产物，不提权；
后续授权的 `/tmp` 只读脚本入口见后文，各轮合同和历史记录分别保留。
连接前必须有本轮已推送 annotated 合同及 600 s 间隔回执。
合同与分析器已经冻结，采集器通过该 tag 中的字节逐个比较，不能以新数据改口径。

```sh
python3 -m unittest discover -s tools/runners/product_floor_reconfirm_20260916 -p 'test_*.py'
python3 tools/runners/product_floor_reconfirm_20260916/run_readonly.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --push-receipt board_results/product_floor_reconfirm_20260916/contract_push.json \
  --output board_results/product_floor_reconfirm_20260916/attempt1
```

`--mapping` 为本地既有映射，不随公开仓库发布。新现场需维护者提供该映射；不可用时
本地失败，不猜真实目标。输出目录必须不存在；任何已完成采样不得覆盖或重跑。
报告使用 `<PRODUCT_BOARD_IP>`，完整未脱敏命令记录与 smaps 只留本地；脱敏命令回执公开。

采集器只允许列举的读取指令（固定路径或严格数字 PID 路径）；复用单请求 RC/DONE
解析与 200 字节上限，额外禁止历史清理模块中的一切写动作。
`rpi4` 命中后不再读架构、镜像或其他数据。开发镜像/未知产品身份同样停止。
PID 1 及 ps/目录相互校验用于过程完整性；无法证明完整就停止，不提权补读。

固定 1 s 截止时间内并行读取候选及全局量；任一批越过下一截止时间即停止，保留
已完成部分，不扩时伪称正常一秒采样。首/末分钟 floor 使用首/末 60 个固定秒槽，
同时保留实际读取区间。无目标刺激，不能复现历史按键下的 floor 增量。
冻结判别器在零基线处的 10% 门退化，零 PD 不能按其原始标签宣称自动释放或滞留；
必须结合绝对数与分桶记录报告限制。独立 analyzer 不替代采集时序与输入完整性核验。

公开重放仅在有效完整序列存在时执行：

```sh
python3 tools/runners/product_floor_reconfirm_20260916/analyze_floor.py \
  --timeseries '<timeseries.tsv>' --output '<summary.json>'
```

发布脚本 `publish_compact.py` 只做 host 脱敏和原文/公开件双哈希，不接触板端。
`commands.jsonl` 留逐条 RC 与原始件哈希；全量 smaps/进程原文留本地，可按请求提供。
STOP 只表示本段未完成，不撤销已经推库的平行英文报告；不切 demo。

## 2026-09-16 PM 确认恢复后的续跑

继续使用同一合同/tag 与原始推送回执，不覆盖 `attempt1`。新输出使用 `attempt2`。
按续跑要求增加三个精确只读请求：`/lib/libc.so.6` 版本输出、CPU `online` 列表、
`getconf CLK_TCK`（进程年龄换算所需）；仍包含 RC 标志并受 200 字节限制。
不扩展通用 shell/执行权限，不允许这两个可执行项附带其他参数。
活着的非内核进程返回空 smaps 时，不把它静默剔除来声称 Top 10 完整；停止并
记录读取范围不明，等 PM 决定是否授权提高读取权限。合同、样本数、分桶与判别器不改。

## PM 解决连接后的正式执行：板端只读脚本

本轮新授权替代旧的禁推送传输方式；旧入口与旧合同保留作历史记录，不改其定义。
新入口 `run_board_script.py` 只采用
`product-floor-board-script-contract-20260916` annotated tag 与
`board_script_contract.json`，合同/分析器字节核验及推送后 600 s 间隔仍是硬门。
架构严格 armv7l，kernel rpi4 或非 Tizen TV 产品镜像立即停止。

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_board_script.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --push-receipt board_results/product_floor_reconfirm_20260916/board_script_push.json \
  --output board_results/product_floor_reconfirm_20260916/formal_board_script
```

先做身份/能力读取，再生成并推送唯一 `/tmp/pf_20260916_<hex>.sh`，按字节哈希确认后
执行。inventory 与 collect 采用同一模板；只有脚本文件落板，样本经 sdb stdout
直达 host。脚本只读 `/proc`/`/sys`，不调用 vk_send、gdb、trim 或业务负载。
时间槽并行读取并等待所有子进程，任一失败停止；板端 timeout 只约束本轮探针进程，
不向目标 PID 发送信号。完整结果需 601 点、固定 1 s deadline、PID/start 一致、
分桶相加正确、远端 RC 证明、冻结分析器成功。

收尾先读进程表确认本轮脚本不再运行；仅删除路径与哈希匹配的自身脚本，复核普通
路径与符号链接均不存在。任何失败只进行必要的自身收尾，不继续业务诊断/采样。
读不到全系统视图或 smaps 不做提权，列出受限项；文件/目录可写不等于可以安装或 attach。
本轮不使用旧入口的 host 高频请求采样，不重跑已有窗口。

实际运行状态：产品身份通过，`command -v timeout` 远端 RC=1，依赖门立即 STOP。
尚未 push 或开始采样，不能认为本入口已在产品板完成验证。当前实现需要板端独立
`timeout` 命令；本轮不安装、不提权、不换方案重试。缺口与原文见
[报告 §6](../../../docs/product_floor_reconfirm_20260916.md#61-本轮结果与停止原因)。

## 2026-09-17 可移植入口与权限分流

`run_portable.py` 使用本轮 `portable_contract.json` / annotated tag
`product-floor-portable-contract-20260917`；保留旧入口作为历史，不再调用 timeout。
先提交合同并记录推送回执，至少 600 s 后才允许连接。不会安装工具或自行提权。

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_portable.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --push-receipt board_results/product_floor_reconfirm_20260916/portable_push.json \
  --output board_results/product_floor_reconfirm_20260916/portable_20260917
```

身份门后用单条工具探测一次列全缺失项；sed/grep 不存在时使用既有 shell/read 与
host 解析，无 sha256sum 时回读脚本全部字节，在 host 比较 SHA-256，明确记录方法。
采样脚本开头再次汇总其命令依赖。时间控制为 shell 601 点循环与 uptime 截止时间，
epoch 秒加单调增量构成 epoch_ns，字段单位不代表墙钟精度；不使用 date 的 `%N`。

推送前先对每个存活实名候选各 cat 一次 status/smaps，保存错误原文；全不可读立即
停止、零 push；部分可读则只选可读者。补充排名只覆盖可读视图，不要求非 root 的 ps
一定含 PID1，也不据受限视图声称全系统完整。不可读/空数据绝不补零。
采样完成的远端 RC 证明（脚本已 wait 子进程）允许清理自身脚本；若丢失退出证明，
必须另证自身已停止，无法证明则保留并报告，不向目标进程发信号。

复现确定性门：合同/分析器固定字节、远端标志、可读候选 PID/start、分桶合计、601 点、
截止时间、脚本传输与清理；容差项：不规定真实 floor 必须等于历史增量，镜像/业务/
压力与视图差异原样披露。完整数据经 analyze_floor.py 重放并字节比较，STOP 不造结论。

## 2026-09-16 PM 单轮授权；2026-09-17 执行

`run_authorized_root.py` 是本轮授权的独立入口，不改变上述入口的默认权限行为。
使用 `root_authorization_contract.json` / annotated tag
`product-floor-root-contract-20260917`，合同推送后至少 600 s 才连接。
仅替代旧合同中的本轮禁提权条款，采样模板、字段、601 点、分桶与判别器原字节不变。
该授权不可复用于后续轮次；以下命令不是一般性提权许可。

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_authorized_root.py \
  --pm-authorization-20260916 --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --push-receipt board_results/product_floor_reconfirm_20260916/root_push.json \
  --output board_results/product_floor_reconfirm_20260916/root_authorized_20260917
```

产品身份通过且 id=5001 后才 root on；id=0 与产品身份再核验。root ps 与 proc 均需
含 PID1，排名仍逐项披露退出/不可读等排除，并非全系统同时快照。读取目标 status
用于凭据与 TracerPid 等风险侦察；`/proc/self/status` 对应查询命令本身，不是 attach
实测。任何情况下都不执行 gdb attach、注入、kill 或包操作。

成功或停止均进入收尾：有退出证明才按原字节哈希删除自己的唯一 /tmp 脚本、确认
路径与符号链接均不存在，然后 root off 并复核 id=5001；失败原样报告，不自动重试。
公开 COMPLETE 回执额外要求已记录 root-off UID=5001，不能只凭 sdb 返回码判过。

本轮实测状态为 STOP：产品身份、提权与候选读取通过，但产品设备以
`[uep][bash] the file is NOT signed!!` 拒绝执行 /tmp 脚本，远端 RC=1，未产生采样槽。
没有绕过签名检查或重跑；自有脚本已删除，root off 后 id=5001 已核验。
详见[报告 §8](../../../docs/product_floor_reconfirm_20260916.md#82-执行结果权限门通过未签名脚本执行被拒绝)。
后续板上复现先需 PM 确认受支持的签名交付方式并重新授权；host 回执复算不受影响。

## 2026-09-18 单会话长驻、不落盘采样

**现场状态：STOP，尚不是可再次连板的完成版入口。** 首次现场执行在候选 PID
变化后复用了旧的逐 PID 短连接重发现路径；在开采样前由 host 主动中断并降权。
单会话采样本体仅有 host 协议测试，产品板未开跑。下述命令记录规格，不是重试许可；
先闭合候选重发现传输缺口、经 PM 确认续跑后才能使用。详见报告 §10。

本轮 PM 允许把命令文本直接送入一次 `sdb shell` 的 stdin，不推送/执行脚本文件，
不绕过镜像签名门。`run_persistent.py` 是新入口；旧入口与旧停止证据保留，勿运行
`run_diskless.py` 的并行短连接采样。只允许当前一轮只读 root 授权，不能作为默认提权。

```sh
python3 tools/runners/product_floor_reconfirm_20260916/run_persistent.py \
  --ip '<PRODUCT_BOARD_IP>' --mapping desensitize_map.tsv \
  --previous-private-snapshot board_results/product_floor_reconfirm_20260916/diskless_20260917/candidates.json \
  --push-receipt board_results/product_floor_reconfirm_20260916/persistent_push.json \
  --output board_results/product_floor_reconfirm_20260916/persistent_20260918 \
  --pm-authorized-readonly-root
```

[合同](persistent_contract.json)与[分析器](analyze_persistent.py)在 annotated tag
`product-floor-persistent-contract-20260918` 固定；推送回执后至少 600 s 才能连接。
私有候选快照须先按映射脱敏后与公开固定快照一致；地址只用于路由，不用于判板。
本地完整原始件可按请求提供，公开仓库不包含私有映射或完整 smaps 流。

连接前 `devices` + 极短 id 自检；仅失败时允许一次 host server reset/connect 与一次
自检重试。身份门后提权，重新确认身份/基线/候选。采样会话以 nonce 标记每批及
每次只读输出，每读保留 RC/DONE；完成整批才接收 host ACK。EOF 不开启下一批，
15 s 无任何输出或连接断开立即 STOP，不重连、不重跑。任何 root-on 尝试后都执行
root off 与 UID5001 核验。命令白名单无文件创建/上传/删除、attach、kill 或包操作。
短查询请求体与每一条 stdin 程序行均不超过 200 字节；完整循环是 stdin 文本，不是
超长 `sdb shell <command>` 参数。HISTFILE 仅在本次 shell 内清空，避免保存输入历史。

时间口径：目标 1 s，名义 601 点，实际每候选在板端 epoch 与 host 单调时钟均覆盖
至少 600 s；不以补点凑数。板端 `date +%s` 为 1 秒精度（输出单位 ns 不代表精度），
准确抖动由 host 接收标记的单调时钟测量。顺序扫描并非同时快照，公开批次/读区间。
分桶输入为所有映射头与 Private_Dirty 行，复用原 smaps 分类函数；不依赖 timeout。

成功结果的 host L1 复算：

```sh
python3 tools/runners/product_floor_reconfirm_20260916/analyze_persistent.py \
  --source data/raw/product_floor_reconfirm_20260916/persistent_20260918 \
  --output /tmp/product-floor-persistent-summary.json
cmp /tmp/product-floor-persistent-summary.json \
  data/raw/product_floor_reconfirm_20260916/persistent_20260918/summary.json
```

仅 COMPLETE 才能使用上述成功路径；STOP 的部分点不生成分类结论。确定性验收为
合同/分析器字节、11 候选集合、完整标记、身份不变、PD 求和、600 s 覆盖、root 恢复；
真实 floor 没有必须等于历史增量的容差带，也不因结果改分类器。采样器的只读开销
不是零；产品 hook/probe 落地必须走签名/正规构建链，本次 stdin 授权不替代该要求。
