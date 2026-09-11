# 延期收尾审计：2026-09-11 STOP 证据

仅补收尾；已验收的 21 格没有重跑，也未改原测量数据。
[audit.json](audit.json) 是最终回执；[commands.json](commands.json) 是执行顺序与时间，
每条远端命令原文单列。原 18 格/G4 的历史回执保持不变。

首批残留查询服务请求 3474 字节仍被客户端拒绝，正文
[PACKAGE_RESIDUE_0000.txt](PACKAGE_RESIDUE_0000.txt) 无远端 RC/DONE。
3500 是未成功闭合实际客户端限制的本地预算，不能作为板端可用性保证。
此后只完成授权 root-off 收尾，首次成功回到 UID=5001，没有重试。

[manifest.json](manifest.json) 校验 39 件选定原始日志的原始/公开 SHA。
只去 CR、脱敏测试板地址及 host home，板端运行路径保留；完整原始件本地留存，
可按请求提供。本文和 [host_checks.tsv](host_checks.tsv) 是归档后的说明，不冒充原始日志。

host 可只读复核已经采到的 audit_start 健康（**不是审计完成**）：

```sh
PYTHONPATH=tools/runners/system_level_before_after_20260908 python3 - <<'PY'
from pathlib import Path
from audit_cleanup_20260911 import SOURCE, health_delta
p = Path('data/raw/system_level_before_after_20260908/cleanup_audit_20260911/raw/round_health')
lines = health_delta(
    (SOURCE / 'raw/round_health/dmesg_before.txt').read_text(),
    (p / 'dmesg_audit_start.txt').read_text(),
    (SOURCE / 'raw/round_health/zram_before.txt').read_text(),
    (p / 'zram_audit_start.txt').read_text())
print('PASS_PARTIAL_ONLY audit_start dmesg_prefix=retained increment_lines=%d OOM_LMK=0 zram_delta=0,0,0' % len(lines))
PY
```

预期：

```text
PASS_PARTIAL_ONLY audit_start dmesg_prefix=retained increment_lines=29 OOM_LMK=0 zram_delta=0,0,0
```

未采集 audit_end/最终 boot，包文件残留没有完成查询；不得把部分健康快照当整轮通过。
[报告 §9](../../../../docs/system_level_before_after_20260908.md#9-2026-09-11-只补收尾再次停止)
列已完成/未完成项与待裁事项。当前有效交付仍是 demo-v11。
