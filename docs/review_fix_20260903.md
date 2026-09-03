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
| P2 | `2433431`, `05bc5cf` | ServiceA 单位标作 KiB/MiB；第 2 轮进一步订正精确换算为 `6212 KiB（6.07 MiB）`；gst p99 图显示基线保留 6 位小数；builder 注明断言是正控漂移设计。 | builder 正控与 HTML byte-cmp；旧单位/换算扫描零命中。 |

## P0-6 已知项裁决

PM 裁决——demo 阶段接受为已知项,正式 release 前统一处理提交身份与仓库可见性策略。

本轮按裁决不重写任何历史、不修改提交身份，也不在 README 增加身份声明。

## 最终验证合同

必须同时满足：全部 host unittest 通过；`reproduce.sh verify` 全行 PASS（p99 方向为
REPORT_ONLY、未观测告警为 REGISTERED/NOT-EVALUATED）；报告可按 source marker 逐字节
重建；双语入口与 INDEX 链接通过；脱敏扫描零命中；demo 分支只有 README 入口与 main
快照不同；`demo-v2` 为 annotated tag。

## 第 2 轮复审与 GBS 闭环

- 同步基线：`24ab0125eb09c1bcdcb3656a9685537e54e7dc98`（执行时的 `origin/main`）
- 范围：host-only；没有连接测试板，没有产生新板上测量数字
- 源码修复提交：`20ab8c80d7b357254542dd841212ed8d7e7085c8`
- GBS 产物登记与派生 HTML 提交：`EVIDENCE_COMMIT`
- 后续交付：本轮不切 `demo`；两轮板上重基线完成后统一切 `demo-v3`

第一轮表格作为当时裁决和实施记录保留。下面凡标“更正”的条目，以本轮为当前口径，
不回写抹除第一轮记录。

| 第 2 轮编号 | 修复提交 | 闭环内容 | 验证方式 |
|---|---|---|---|
| A-1 | `20ab8c8`, `EVIDENCE_COMMIT` | 更正第一轮 P0-2：取消“合并中位”口径；S4 按 profile 报 mixed `1.233269 ms`、medium-only `1.218361 ms`。HTML 表逐档显示，指南 L1 字段为 `trim_ms_median_by_profile`；S4 原报告、状态报告、叙事、包、双语入口同步。builder 直接从 `b_cycles.tsv` 的逐行 `trim_elapsed_ms` 独立重算两档中位。 | builder 正控 + `test_customer_surfaces_share_headline_contract` 跨载体检查；提交版 HTML byte-cmp。 |
| A-2 | `20ab8c8` | S4/gst remote runner 不再内置 ELF/media SHA；`board_workflow.sh` 按 `frozen_sha256` / `reproducible_build_sha256` / `gbs_build_sha256` 选择 manifest 字段，并通过环境合同注入执行器。 | `test_board_workflow_mocked_sdb.py` 用 fake SDB 对 frozen/reproducible/gbs 三路径逐一核验两次 remote invocation 所见 SHA。 |
| A-3 | `20ab8c8` | manifest 删除内部渠道/责任人占位；媒体交付固定写为“由交付方随交付邮件提供获取位置,收到后按本清单 SHA-256 核对”，指南与双语入口一致。 | manifest schema host test + 旧 `external-package`/占位措辞扫描零命中。 |
| A-4 | `20ab8c8` | 更正第一轮 P0-4 的测试名：改为 `check_reproducible_build_paths.py` 并纳入 verify；只有同时给出 `DEMO_TOOLCHAIN_ROOT`/`DEMO_GST_SYSROOT` 才做双路径真实构建，否则明确 `SKIPPED` 和缺失变量。 | 显式指向本轮 GBS scratch 后，两条临时 checkout 路径的三 ELF 各自逐字节一致并匹配 manifest；不设置变量的标准 verify 仍明确 `SKIPPED`，不伪装成已执行。 |
| A-5 | `20ab8c8`, `EVIDENCE_COMMIT` | `6212 KiB` 的二进制换算统一为 `6.07 MiB`；撤销第一轮 P2 中错误的 `6.2 MiB` 展示。 | builder 用 Decimal 正控 `6212/1024=6.06640625` 且两位显示 `6.07`；跨文档旧换算扫描、HTML byte-cmp。 |
| A-6 | `20ab8c8` | 修复 graphics diagnosis/install 两处指向错误层级的 `gbs.conf` 链接。更正第一轮 P1-11 计数说明：基线实际是 **74 个 Markdown 链接，分布在 45 行**；双语入口 2 处只是本地原始件说明，不属于链接，不能相加称为“76 条链接”。 | 对基线 `9183bcc` 的 Markdown 链接正则复算为 74/45；当前树 `board_results` Markdown 链接零命中；local-link-check。 |
| A-7 | `20ab8c8` | L2 手工 S4/gst 命令各补负载前后 stability-monitor 快照，字段和筛选逻辑与 workflow 同源；手工 remote invocation 同样显式注入选择后的 SHA。 | 指南命令静态审计 + shell harness 合同测试；本轮 host-only 不执行板命令。 |
| A-8 | `20ab8c8` | `delivery_refs.json` 升为分支感知：`demo` 强制匹配 `demo-v2`，`main` 仅输出开发快照 `REPORT_ONLY` 并提示切换冻结标签；显式 `REPRODUCE_EXPECTED_SHA` 仍可覆盖。 | `test_delivery_identity_marks_main_report_only`；verify 的 clean-environment 行在 main 显式显示 REPORT_ONLY。 |
| A-9 | `20ab8c8` | workflow README 解释两个构建环境变量与 `--artifact-source`；template README 的 root-relative 链接说明只在复制到快照根目录后检查；acceptance replay 只读本轮已生成的 `$tmp/gst`。 | 文档关键词/链接审计；`reproduce.sh verify` 的 gst replay → acceptance 数据流通过。 |
| A-10 | `20ab8c8`, `EVIDENCE_COMMIT` | `deliverables_manifest.json` 升到 v2；三 ELF 均增加 `gbs_build_sha256`，顶层登记 GBS source commit、RPM NVR/arch/size/SHA 和 buildroot 版本；媒体该字段为 null。 | JSON schema host test；`check_gbs_package.py` 提取 RPM 后逐个核对三 ELF。 |
| GBS-11 | `20ab8c8` | 新增 `glibc-memopt-tools-1.0.0-1` spec，一个 armv7l RPM 的 `%files` 精确包含 `/usr/bin/alloc_bench`、`/usr/bin/gst_loop_decode`、`/usr/bin/reclaim_probe`。BuildRequires 的 `-devel` 集合固定为 `glibc-devel`、`glib2-devel`、`gstreamer-devel`。 | `rpmspec -P`、portable static checker、实际 RPM `rpm -qpl` 三重核验。 |
| GBS-12 | `20ab8c8`, `EVIDENCE_COMMIT` | 使用 `config/gbs_llvm.conf`，固定 Unified `20260814.092727` 与其 build metadata 指向的 Base `20260813.050338`；成功构建 armv7l RPM，登记 clang/LLVM/GCC、glibc 与三项 devel 的 buildroot 版本、RPM 和 ELF 哈希。 | [`build_summary.json`](../data/raw/gbs_package_20260903/build_summary.json)；`check_gbs_package.py` 对精确 source commit 重建 NVR、架构、`%files` 和三 ELF；RPM wrapper SHA 作为该次构建身份记录，后续 archive metadata 差异只报告。 |
| GBS-13 | `20ab8c8` | main README、HQ 指南和双语交付模板新增 GBS 路径：HQ 首选 GBS，冻结件/固定目录交叉构建为备选；明确 GBS 产物待板上重基线，闭合前 L2 仍以冻结件为准，媒体仍须包外交付。 | 跨载体 GBS 状态测试 + local-link-check。 |
| GBS-14 | `20ab8c8` | verify 新增 spec name/version/BuildRequires/`%files` 静态检查与 `rpmspec -P`；有 GBS 时实跑并检查 RPM/ELF，无 GBS 时显式 SKIPPED。 | `test_gbs_spec_static_contract_without_gbs` 覆盖无 GBS；本机 GBS 2.0.8 路径实际构建通过。 |

GBS RPM 哈希依赖被打包源码提交。为避免 manifest 自引用，先以 `20ab8c8` 固定
spec、源码、配置和文档，再对该精确提交构建；`EVIDENCE_COMMIT` 只登记产物哈希、构建
摘要和由同一输入重建的 HTML。该语义与现有 HTML parent-source marker 一致。
