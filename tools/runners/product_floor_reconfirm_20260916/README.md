# 产品 floor 只读复确认

旧入口 `run_readonly.py` 只在 host 执行，不推送任何脚本/产物，不提权；
本轮新授权的 `/tmp` 只读脚本入口见末节，两份合同和历史记录分别保留。
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
报告使用 `<PRODUCT_BOARD_IP>`，命令记录与完整 smaps 只留本地。

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
