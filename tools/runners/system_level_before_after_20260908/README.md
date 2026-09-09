# 系统级前后对照：事前合同与派生入口

## PM 2026-09-10 单轮授权包装层

**执行结果追注：本轮已结束并 root-off 回到 UID=5001，不得直接再次运行。** G4 三格已观测
并校验；`PACKAGE_RESIDUE_0000` 的 11800 字节请求被 SDB 拒绝，残留清单与后置健康
未闭合，最终 STOP。下面仅记录当时授权入口，不是新的运行许可；见[报告 §8](../../../docs/system_level_before_after_20260908.md#8-pm-方案-a-授权续跑三格已观测收尾-stop)。

仅本轮可以显式使用 `run_authorized_g4_20260910.py --pm-authorization PM-G4-20260910`，
其余参数与下方 G4-only 入口相同（不接受 `--preflight-only`）。它先核验三项身份和
UID=5001，再记录 root-on / id；继承完整前置门与仅 G4 三格执行，退出时 root-off / id，
至多一次降权重试。失败停止后续；不会清除旧 PID、重跑旧 18 格或更改合同。
这是[单轮授权](../../../docs/pm_decisions.md#2026-09-10-g4-单轮提权授权方案-a)，
不是默认复现行为，也不是只读预检。最终 `execution.json` 的 `root_authorization.root_off`
必须为 `PASS_NONROOT`，不能只看父入口中间输出。

`publish_g4_observations.py --run /path/to/terminal-g4-run --output-dir /path/to/new-public-observations`
仅保留 STOP 下已观测的三格，原 analyzer 重建 `g4_cycles.tsv/g4_summary.tsv` 并与拉回
派生件 cmp；输出显式 `STOP_NOT_ACCEPTED_FOR_DEMO`。不拼接旧 18 格、不生成完整矩阵。
日志发布器加入授权/降权及后置审计原文选集，拒绝尚未结束的 root 生命周期。

## 2026-09-09 续跑入口（host 闭合后使用）

本次实际终态：host 114 项测试与既有 verify 通过；只读连接后 UID=5001，不满足合同的
root 门，因此 G4 NOT_EXECUTED。禁止自行 root-on/重启或再次执行测量；等待 PM 裁决。
代码的 host 验证不等于已在本镜像完成 G4。见[本次停止原文](../../../docs/system_level_before_after_20260908.md#74-本次终态uid-门-stopg4-not_executed)。

只用 [execute_g4_resume.py](execute_g4_resume.py) 续跑 G4 三格；**不得重新执行已验收的
G1/G2/G3 18 格**。该入口没有 alloc/gst 参数，只推采集 probe，连板前核对历史证据与已推
执行提交。`--preflight-only` 只读核验，无推送/安装/测量；正式调用用另一个全新输出目录。
完整参数、确定性/有效性门和报告项见[报告 §7.3](../../../docs/system_level_before_after_20260908.md#73-复现与分段门)。
不修改原 contract/analyzer。PM 手动重启闭合旧 FILE*/FD 恢复事项；新现场状态以本次
原文核验为准，旧失败记录保留如下。旧 21 格命令仅为历史出处，不是本次重跑授权。

**2026-09-08 续跑停止：执行器当前不可作为已验证的完整复跑入口。**
G1/G2/G3 共 18 格通过；G4 首格 M7 使用 `$fp` 赋值报错，未 trim。未修复/重跑，
不改变合同，demo-v11 保持有效。目录/包/辅助进程/governor 检查通过不代表目标内可能的
FILE*/FD 状态已恢复；见 [失败与恢复边界](../../../docs/system_level_before_after_20260908.md#62-g4-失败证据与覆盖缺口)。
后文命令保留执行出处，不是再次运行授权；先闭合 G4 兼容性和目标内部状态再议续跑。

[合同/报告](../../../docs/system_level_before_after_20260908.md) / [机器合同](contract.json)。
首次状态（历史）：**只读占用门 STOP，零个实验格执行**。当时两个已有 `sh -l` 交互会话归属未明，
不清理、不抢占；第 2、3 段不执行，当前交付保持 demo-v11。详见
[晨间汇总](../../../docs/overnight_summary_20260908.md)。合同与 analyzer 保持 tag 中原字节。

实际执行入口是 [preflight.py](preflight.py)：先确认 annotated tag 已推送并记录 UTC/
monotonic 时间，至少 600 s 后才做只读检查；自动身份/环境检查不代替人工占用核查。
本轮多路复用 sdb 只呈现一条 TCP 连接，但仍有两条交互 shell，最终判定为 STOP。

```sh
python3 -m unittest tools/runners/system_level_before_after_20260908/test_host.py
python3 tools/runners/system_level_before_after_20260908/build_observer.py \
  --toolchain-root /path/to/scratch.armv7l.0 --output-dir /path/to/build
python3 tools/runners/system_level_before_after_20260908/analyze_system_level.py \
  --raw /path/to/verified-pull --output-dir /path/to/derived
```

构建为本轮专用 alloc 观测副本，不覆盖原源文件；两臂共享 ELF。`fd 3` 发出
`PRE 01`/`POST 01`（换行结尾），`fd 4` 等待一个 `K` 字节。控制器必须设置
超时并只终止其自身创建且 PID/starttime 已复核的目标。

完整原始输入布局：`<cell>/cell.json`（退出码、PID、健康记录）、`metrics.json`
（逐周期内部记录转录，需与原始 JSON/log 核对）与
`points/<cycle>_pre|post/{meta.json,stat.txt,stat_check.txt,status.txt,profile.json,meminfo.txt,zram.txt,memps.txt}`。
meta 为 nanosecond start/end 窗口；probe JSON 保持原 schema，memps 原文保持未修改。
输出 `cycles.tsv` 与 `summary.tsv`，缺任何格/周期/有效性项拒绝完整矩阵 PASS。
未完成矩阵只归档原始件和阻塞报告，不补值、不产头条。

## 未执行准备件（不可作为可用复现入口）

`capture_point.sh` / `run_cell_remote.sh` 是等待间隔内准备的草稿，**从未推送或运行到板上**；
在首次停止提交中以无条件 `NOT-EVALUATED` / RC=2 阻断执行，保留源码便于审计而非声称完成。
`collect_cell.py` 是相应 host 转录准备件，亦未处理新测量数据。
恢复工作前需要闭合：stability 管道各段错误传播、G4 fopen 非NULL与PID复核、
point父路径/符号链接验证、异常退出/限时子进程清理回归。不能删除阻断行便直接复跑。
观测副本仅通过 [host 握手测试](test_observer_protocol.py)，不是板上验证。

## 2026-09-08 续跑入口

PM 已确认专供板并批准两条会话处置，见 [报告 §5](../../../docs/system_level_before_after_20260908.md#5-pm-裁决后续跑占用处置与执行器闭合)。
修复与故障路径测试闭合后启用 [execute_contract.py](execute_contract.py)，不修改冻结合同/analyzer。
先运行下列全套 host 测试并提交执行器，再以已核验资产路径运行；不会重试任何测量格。

```sh
python3 -m unittest discover -s tools/runners/system_level_before_after_20260908 -p 'test_*.py'
python3 tools/runners/system_level_before_after_20260908/execute_contract.py \
  --ip <TEST_BOARD_IP> --output-dir /path/to/new-local-run \
  --occupancy-receipt /path/to/closure_corrected.json \
  --contract-receipt /path/to/contract_push_receipt.json \
  --alloc /path/to/alloc_bench_observer.armv7l \
  --gst /path/to/gst_loop_decode.armv7l --probe /path/to/reclaim_probe.armv7l \
  --media /path/to/small_320x240.mp4 --gdb-cache /path/to/official-six-rpm-cache
```

输出 `PASS_CELL` 只表示该格已完整拉回并通过冻结有效性门；须全部 `PASS_COMPLETE_MATRIX`
且 cleanup PASS 才能进入 Demo 集成。失败保留 execution.json、原始输出与已校验归档，
停止后续；不能用部分样本补全三重复中位。占用处置脚本只适用于本次 PM 批准的精确 PID/start tick，
不是通用清理命令，未来不可照搬这两个 PID。gdb 原已存在则不获取卸载权；本轮新增六包在退出路径卸载。

## Host 归档工具与未使用的完整发布入口

`publish_stopped_measurement.py` 仅接受本次 STOP、已完整通过的 G1/G2/G3 前缀和终态清理
回执；重验原件/归档哈希后调用冻结 analyzer，输出 330 点及逐周期派生，不生成汇总头条。
`publish_execution_log.py` 保留身份、命令、健康、G4 报错和清理原文选集，可归档 STOP，
编辑仅 CR/路由地址/host home 映射，逐件记录编辑前后 SHA。原始件仍本地留存，可按请求提供。

`publish_measurement.py` / `replay_compact.py` 是完整 21 格的 host 发布/复算准备件，
仅在合成 fixture 上通过五派生件 cmp；本次 STOP 被完整发布门拒绝，未对真实矩阵发布
完整结果，也未进入 HQ 的 Demo L1 入口。它们的 host 测试通过不构成 G4 板上可用性证据。
