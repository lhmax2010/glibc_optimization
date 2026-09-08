# 系统级前后对照：事前合同与派生入口

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
