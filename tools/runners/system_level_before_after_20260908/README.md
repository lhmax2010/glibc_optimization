# 系统级前后对照：事前合同与派生入口

[合同/报告](../../../docs/system_level_before_after_20260908.md) / [机器合同](contract.json)。
当前为事前提交：无板端数据，不能据此生成 Demo 新数字。annotated 合同 tag 推送完成后
至少 600 s 才允许连接板；任何停止门命中即终止整个批量任务。

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
