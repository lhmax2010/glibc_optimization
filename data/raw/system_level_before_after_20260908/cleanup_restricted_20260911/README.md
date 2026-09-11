# 受限 root 续审原文（2026-09-11）

只补收尾；21 格未重跑。执行器 `418181e8b3766343e434fe04d86117a371faf6a9` 先推 main。
结果 **STOP**：五个无当前 RPM 归属的 GDB 目录内容/归属未闭合，未删除；不是包卸载、
进程完整性或已采健康失败。一次 root round 后首次 root off 成功，UID=5001。

- [audit.json](audit.json)：不可改写的终态回执，首个未知目录触发停止。
- [commands.json](commands.json)：2614 个客户端调用；2610 个 shell 正文 70–189 字节。
- [permission_denied.json](permission_denied.json)：root on 前已落盘的五项受限清单。
- [manifest.json](manifest.json)：2619 个原文/回执文件的原始与公开 SHA，逐项记录脱敏编辑。
- [host_replay.json](host_replay.json)：离线复核全部已采记录及五目录全表；不是板上新采集。

完整原始件本地留存，可按请求提供。板端运行路径保留；点分地址及 TCP 表中可还原 IP
的小端十六进制端点映射为 `<TEST_BOARD_IP>` / `<HOST_IP>`，保留端口/状态；host home
映射为 `<USER_HOME>`，CR 编辑明示。没有改动测量、未编辑本地原文。

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_restricted_cleanup.py \
  data/raw/system_level_before_after_20260908/cleanup_restricted_20260911
```

输出应与 host_replay.json 逐字节一致。报告见[§11](../../../../docs/system_level_before_after_20260908.md#111-执行结果与原文)。
