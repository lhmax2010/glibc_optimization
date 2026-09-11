# 单项收尾原文：STOP（2026-09-11）

执行器先推 `9f839b25e5b07fdbd489043050dd59969bd0497e`；本组仅为只读收尾，21 格不重跑。
[audit.json](audit.json) 为真实终态 STOP，未改写；[manifest.json](manifest.json) 记录
16 个原文文件的编辑前后 SHA。完整原始件本地留存，可按请求提供。
编辑仅 CR、测试板路由地址与 host home 既有映射；板上路径保留，BUILD_ID 有意公开。

[commands.json](commands.json) 中 14 个调用包括 12 条独立 shell 请求，正文 70–106 字节，
均有远端 RC/DONE/FAIL；没有长度试探。ps RC=0 但缺 PID 1，不能证明完整性，停止后仅
复核 id=5001。目录 `Permission denied` 已存入 audit 的部分权限清单，未完成全扫，
没有提权，也没有修改、删除或安装任何板端文件/包。

只读 host 复算：

```sh
python3 tools/runners/system_level_before_after_20260908/analyze_single_cleanup_stop.py \
  data/raw/system_level_before_after_20260908/cleanup_single_20260911
```

完整预期输出为 [host_replay.json](host_replay.json)，可使用 `--output <new-file>` 后 cmp。
该派生件及 README/host_checks 不冒充原始采集件；16 件原文清单不包含后补说明。
开始快照的 dmesg/zram 成功不能填补未执行的结束健康/包/残留/governor/df。
host 回归加入实际 RC=0 缺行样本；不放宽完整性门，不授权再次连板。

详见[报告 §10](../../../../docs/system_level_before_after_20260908.md#10-2026-09-11-单项收尾进程清单完整性-stop)。
