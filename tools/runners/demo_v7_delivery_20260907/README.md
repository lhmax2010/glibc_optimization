# demo-v7 host 交付验证补充件

本轮只修交付工具行为与文档，并补公开旧记录。以下两个脚本都不连接板端：

```sh
python3 tools/runners/demo_v7_delivery_20260907/publish_gst_retry2.py \
  --workflow board_results/gbs_rebaseline_20260903/workflow_retry2 \
  --output <new-public-gst-directory>
python3 tools/runners/demo_v7_delivery_20260907/publish_gbs_build.py \
  --bundle <successful-gbs-output-dir> --log <raw-workflow-log> \
  --output <new-public-build-directory>
```

首个脚本调用既有 gst 分析器校验完整 pull 并与原派生件逐字节比较，不复制统计逻辑。
第二个脚本复核已生成四件的哈希，归档构建摘要，脱敏 host 仓库路径。
公开件分别见 [`gst retry2`](../../../data/raw/gbs_rebaseline_20260903/gst_retry2/README.md)
与 [`真实 GBS 构建`](../../../data/raw/demo_v7_delivery_20260907/gbs/README.md)。
默认 verify 的真最小/损坏工具矩阵入口仍为
[`predelivery_check.sh`](../../reproduce/predelivery_check.sh)。
