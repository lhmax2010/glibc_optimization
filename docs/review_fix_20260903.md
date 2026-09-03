> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# Demo 三方评审修复闭环（2026-09-03）

- 执行基线：`9183bccd41608c3981b3147cb86e4a81f158a8f9`
- 范围：host-only；没有连接测试板，没有产生新测量数字
- 机器合同：[`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)
- 对客派生：[`demo_report.html`](demo_report.html)

## 修复提交

| 提交 | 作用 |
|---|---|
| `dc0aafc` | workflow、acceptance schema v3、资产 manifest、可复现构建、preflight 与 host 测试 |
| `2433431` | HTML builder、双语交付入口模板、指南/报告同步、单位与脱敏一致性 |
| `05bc5cf` | 用父源提交 `2433431` 重建并提交单文件 HTML 与 source marker |

`source_commit.txt`/HTML 页脚指向父源提交是有意设计：先固定输入源码与文档，再单独提交
派生产物；重建测试要求该 marker 产生逐字节相同 HTML。

## 逐项闭环

| 评审编号 | 修复提交 | 闭环内容 | 验证方式 |
|---|---|---|---|
| P0-1 | `dc0aafc` | gst `preregistered-p99-direction` 改为 `REPORT_ONLY`；删除 `expected_direction` 通过条件，只硬校验 nearest-rank、重复中位、none 离散带与严格比较；文档给出板上判可见时保留三重复、量化 margin 并上报的解释。 | `test_gst_visible_direction_is_report_only_when_rule_is_valid` 人为构造 `visible=true` 仍通过；`reproduce.sh verify` 的规则行 PASS、方向行 REPORT_ONLY。 |
| P0-2 | `2433431`, `05bc5cf` | 面向交付的 S4 trim 中位统一为 `1.233269 ms`；builder 对 ServiceA、两套表型计数、候选 floor、batch、A/B、gst p99/p50/minflt/首次 release/trim 分布增加正控断言；新增跨载体一致性测试。 | `tools/report/test_build_demo_report.py` 5 项测试通过；提交版 HTML byte-cmp 通过。 |
| P0-3 | `2433431`, `05bc5cf` | HTML 表型卡分成 release-ratio 与 plateau/cyclic 两个作用域；分别断言 `a/b/c/N=1/4/1/5` 与 `a/b/c/N/U=1/2/1/6/1`；披露 ServiceD 的 `b-retention` / `N-subthreshold` 跨表冲突。 | builder 正控断言 + phenotype 两份 TSV 的既有 byte-cmp。 |
| P0-4 | `dc0aafc`, `2433431` | 新增四资产 SHA/体积/内部渠道/责任人占位 manifest；媒体标作包外交付；三 ELF 固定构建目录并加入 `-fdebug-prefix-map`；preflight 新增 root、governor 可写、`/opt/usr` 可写硬门；双语 L2 前置明确“无内部 bundle 不可启动”。 | `test_reproducible_build_paths.py` 在两个不同临时路径产出三个相同 SHA，且均匹配 manifest；preflight/manifest 静态 host 测试通过。 |
| P0-5 | `dc0aafc`, `2433431`, `05bc5cf` | clean-environment 每个门给出具体失败原因；明确只支持 git clone；文档化三个开发覆盖变量；默认校验 HEAD 对交付引用；source marker 改为显式构建时记录。交付标签按 P0-6 创建 annotated `demo-v2`。 | `test_verify_entrypoint_passes`、source-record 测试、最终干净快照 `reproduce.sh verify`。 |
| P0-6 | `2433431` | 维持 `demo` 从修复后 `main` 重切、双语 README 仅存在于交付快照、annotated `demo-v2`；不重写历史、不改提交身份、README 不加身份声明。 | 分支树差异检查、`git cat-file -t demo-v2=tag`、最终 SHA 记录。 |
| P1-7 | `2433431`, `05bc5cf` | gst 头条补 `0.555556 ms` margin（91.8%）、p50 同规则可见与 `+359 minflt/循环`；A 锚点标各 n=1/分母；batch 标明 `<TEST_IMAGE_B>` / `glibc-2.40-2.8` 相容性、非冻结矩阵；公开 `68.169197%` rep2 紧凑证据；叙事补真实释放上界。 | 跨载体测试、builder 正控、batch transcription checker、rep2 TSV 链接检查。 |
| P1-8 | `dc0aafc`, `2433431` | schema v3 仅把 released payload 列为 deterministic；页对齐/majflt/zram/dmesg 移为 validity gates；逐周期回收量列为 banded；S4 public replay 新增 acceptance JSON byte-cmp；“同样的数据”三段语义统一。 | `test_acceptance_v3_separates_determinism_validity_and_direction`、`s4-public-replay` cmp。 |
| P1-9 | `dc0aafc`, `2433431` | B 组分档锚定 mixed `81.661264% ±5 pp`、medium-only `84.446566% ±5 pp`；写明 n=3 中位只能吸收一个离群。 | evaluator 对公开证据 PASS；out-of-band fixture FAIL。 |
| P1-10 | `dc0aafc`, `2433431` | v2 使用 known-alert waiver；v1 历史 HARD FAIL 保留；“无害”收窄为触发/窗口可复现且根因未证明；未观测输出 `REGISTERED/NOT-EVALUATED`。 | stability fixture 实际匹配后 EXPECTED；host verify 无观测时 REGISTERED/NOT-EVALUATED。 |
| P1-11 | `2433431` | BUILD_ID 标明为复现而有意公开；构建 host 编辑为 `abuild@<CI_HOST>`；统一说明“host 路径已脱敏、板端运行路径保留”；修正 `/opt/usr/<USER_HOME>`；link-check 纳入双语 README 与 INDEX；基线上 74 个 `board_results` Markdown 链接全部改非链接，连同双语入口的 2 处本地原始件说明合计闭合评审所列 76 处，并注明可按请求提供。 | 敏感字面量扫描零命中；`git grep` 对 `board_results` Markdown 链接零命中；local-link-check PASS。 |
| P1-12 | `2433431` | 英文入口补 `not a product-memory-benefit promise`、`single call <5 ms`、精确 glibc RPM、retained floor 与 nearest-rank 词条及完整 L2 prerequisites。 | 双语模板链接检查、跨载体测试、关键词审计。 |
| P2 | `2433431`, `05bc5cf` | ServiceA 统一写 `6212 KiB（6.2 MiB）`；gst p99 图显示基线保留 6 位小数；builder 注明断言是正控漂移设计。 | builder 正控与 HTML byte-cmp；旧 `6212 kB/6.2 MB` 扫描零命中。 |

## P0-6 已知项裁决

PM 裁决——demo 阶段接受为已知项,正式 release 前统一处理提交身份与仓库可见性策略。

本轮按裁决不重写任何历史、不修改提交身份，也不在 README 增加身份声明。

## 最终验证合同

必须同时满足：全部 host unittest 通过；`reproduce.sh verify` 全行 PASS（p99 方向为
REPORT_ONLY、未观测告警为 REGISTERED/NOT-EVALUATED）；报告可按 source marker 逐字节
重建；双语入口与 INDEX 链接通过；脱敏扫描零命中；demo 分支只有 README 入口与 main
快照不同；`demo-v2` 为 annotated tag。
