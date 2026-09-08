> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# Demo 三方评审修复闭环（2026-09-03）

涉及证据等级和交付判读的 PM 裁决集中记录在
[`pm_decisions.md`](pm_decisions.md)；本文件继续保留逐项“发现 → 修复提交 → 验证”映射。

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
| P1-11 | `2433431` | BUILD_ID 标明为复现而有意公开；构建 host 编辑为 `abuild@<CI_HOST>`；统一说明“host 路径已脱敏、板端运行路径保留”；修正 `/opt/usr/home/owner`；link-check 纳入双语 README 与 INDEX；基线上 74 个 `board_results` Markdown 链接全部改非链接，连同双语入口的 2 处本地原始件说明合计闭合评审所列 76 处，并注明可按请求提供。 | 敏感字面量扫描零命中；`git grep` 对 `board_results` Markdown 链接零命中；local-link-check PASS。 |
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
- GBS 产物登记与派生 HTML 提交：`a6cf8fccc8478b5f06573d4189c5f7841fb55c5b`
- 后续交付：本轮不切 `demo`；两轮板上重基线完成后统一切 `demo-v3`

第一轮表格作为当时裁决和实施记录保留。下面凡标“更正”的条目，以本轮为当前口径，
不回写抹除第一轮记录。

| 第 2 轮编号 | 修复提交 | 闭环内容 | 验证方式 |
|---|---|---|---|
| A-1 | `20ab8c8`, `a6cf8fc` | 更正第一轮 P0-2：取消“合并中位”口径；S4 按 profile 报 mixed `1.233269 ms`、medium-only `1.218361 ms`。HTML 表逐档显示，指南 L1 字段为 `trim_ms_median_by_profile`；S4 原报告、状态报告、叙事、包、双语入口同步。builder 直接从 `b_cycles.tsv` 的逐行 `trim_elapsed_ms` 独立重算两档中位。 | builder 正控 + `test_customer_surfaces_share_headline_contract` 跨载体检查；提交版 HTML byte-cmp。 |
| A-2 | `20ab8c8` | S4/gst remote runner 不再内置 ELF/media SHA；`board_workflow.sh` 按 `frozen_sha256` / `reproducible_build_sha256` / `gbs_build_sha256` 选择 manifest 字段，并通过环境合同注入执行器。 | `test_board_workflow_mocked_sdb.py` 用 fake SDB 对 frozen/reproducible/gbs 三路径逐一核验两次 remote invocation 所见 SHA。 |
| A-3 | `20ab8c8` | manifest 删除内部渠道/责任人占位；媒体交付固定写为“由交付方随交付邮件提供获取位置,收到后按本清单 SHA-256 核对”，指南与双语入口一致。 | manifest schema host test + 旧 `external-package`/占位措辞扫描零命中。 |
| A-4 | `20ab8c8` | 更正第一轮 P0-4 的测试名：改为 `check_reproducible_build_paths.py` 并纳入 verify；只有同时给出 `DEMO_TOOLCHAIN_ROOT`/`DEMO_GST_SYSROOT` 才做双路径真实构建，否则明确 `SKIPPED` 和缺失变量。 | 显式指向本轮 GBS scratch 后，两条临时 checkout 路径的三 ELF 各自逐字节一致并匹配 manifest；不设置变量的标准 verify 仍明确 `SKIPPED`，不伪装成已执行。 |
| A-5 | `20ab8c8`, `a6cf8fc` | `6212 KiB` 的二进制换算统一为 `6.07 MiB`；撤销第一轮 P2 中错误的 `6.2 MiB` 展示。 | builder 用 Decimal 正控 `6212/1024=6.06640625` 且两位显示 `6.07`；跨文档旧换算扫描、HTML byte-cmp。 |
| A-6 | `20ab8c8` | 修复 graphics diagnosis/install 两处指向错误层级的 `gbs.conf` 链接。更正第一轮 P1-11 计数说明：基线实际是 **74 个 Markdown 链接，分布在 45 行**；双语入口 2 处只是本地原始件说明，不属于链接，不能相加称为“76 条链接”。 | 对基线 `9183bcc` 的 Markdown 链接正则复算为 74/45；当前树 `board_results` Markdown 链接零命中；local-link-check。 |
| A-7 | `20ab8c8` | L2 手工 S4/gst 命令各补负载前后 stability-monitor 快照，字段和筛选逻辑与 workflow 同源；手工 remote invocation 同样显式注入选择后的 SHA。 | 指南命令静态审计 + shell harness 合同测试；本轮 host-only 不执行板命令。 |
| A-8 | `20ab8c8` | `delivery_refs.json` 升为分支感知：`demo` 强制匹配 `demo-v2`，`main` 仅输出开发快照 `REPORT_ONLY` 并提示切换冻结标签；显式 `REPRODUCE_EXPECTED_SHA` 仍可覆盖。 | `test_delivery_identity_marks_main_report_only`；verify 的 clean-environment 行在 main 显式显示 REPORT_ONLY。 |
| A-9 | `20ab8c8` | workflow README 解释两个构建环境变量与 `--artifact-source`；template README 的 root-relative 链接说明只在复制到快照根目录后检查；acceptance replay 只读本轮已生成的 `$tmp/gst`。 | 文档关键词/链接审计；`reproduce.sh verify` 的 gst replay → acceptance 数据流通过。 |
| A-10 | `20ab8c8`, `a6cf8fc` | `deliverables_manifest.json` 升到 v2；三 ELF 均增加 `gbs_build_sha256`，顶层登记 GBS source commit、RPM NVR/arch/size/SHA 和 buildroot 版本；媒体该字段为 null。 | JSON schema host test；`check_gbs_package.py` 提取 RPM 后逐个核对三 ELF。 |
| GBS-11 | `20ab8c8` | 新增 `glibc-memopt-tools-1.0.0-1` spec，一个 armv7l RPM 的 `%files` 精确包含 `/usr/bin/alloc_bench`、`/usr/bin/gst_loop_decode`、`/usr/bin/reclaim_probe`。BuildRequires 的 `-devel` 集合固定为 `glibc-devel`、`glib2-devel`、`gstreamer-devel`。 | `rpmspec -P`、portable static checker、实际 RPM `rpm -qpl` 三重核验。 |
| GBS-12 | `20ab8c8`, `a6cf8fc` | 使用 `config/gbs_llvm.conf`，固定 Unified `20260814.092727` 与其 build metadata 指向的 Base `20260813.050338`；成功构建 armv7l RPM，登记 clang/LLVM/GCC、glibc 与三项 devel 的 buildroot 版本、RPM 和 ELF 哈希。 | [`build_summary.json`](../data/raw/gbs_package_20260903/build_summary.json)；`check_gbs_package.py` 对精确 source commit 重建 NVR、架构、`%files` 和三 ELF；RPM wrapper SHA 作为该次构建身份记录，后续 archive metadata 差异只报告。 |
| GBS-13 | `20ab8c8` | main README、HQ 指南和双语交付模板新增 GBS 路径：HQ 首选 GBS，冻结件/固定目录交叉构建为备选；明确 GBS 产物待板上重基线，闭合前 L2 仍以冻结件为准，媒体仍须包外交付。 | 跨载体 GBS 状态测试 + local-link-check。 |
| GBS-14 | `20ab8c8` | verify 新增 spec name/version/BuildRequires/`%files` 静态检查与 `rpmspec -P`；有 GBS 时实跑并检查 RPM/ELF，无 GBS 时显式 SKIPPED。 | `test_gbs_spec_static_contract_without_gbs` 覆盖无 GBS；本机 GBS 2.0.8 路径实际构建通过。 |

GBS RPM 哈希依赖被打包源码提交。为避免 manifest 自引用，先以 `20ab8c8` 固定
spec、源码、配置和文档，再对该精确提交构建；`a6cf8fc` 只登记产物哈希、构建
摘要和由同一输入重建的 HTML。该语义与现有 HTML parent-source marker 一致。

## 第 3 轮终审 A 段闭环（2026-09-04）

- 同步基线：`344e14461d070c709c505eba11748cf6846a0fe1`
- host 修复提交：`8e117142211f8a66bef0de56337fb51017dec126`
- 范围：host-only；没有连接测试板、没有新增测量数字
- PM 裁决：[`pm_decisions.md`](pm_decisions.md)

| 发现编号 | 修复提交 | 闭环内容 | 验证方式 |
|---|---|---|---|
| N4-01 / V4-3 | `8e117142211f8a66bef0de56337fb51017dec126` | 默认 verify 只保留 spec/`%files`/manifest 静态硬门；真实构建移到 `reproduce.sh gbs`。GBS 命令/环境失败为 `SKIPPED/REPORT_ONLY`，成功产物的 NVR、文件表和 ELF SHA 漂移仍硬失败；buildroot 每次唯一并由跨进程锁保护。 | fake GBS RC=42 仍 `OVERALL PASS`；默认 verify 在 PATH 有/无 GBS 时均不调用 GBS；唯一 config/buildroot 与锁占用提示测试；完整 host verify。 |
| V4-1 | `8e117142211f8a66bef0de56337fb51017dec126` | acceptance v4 保持原数值但降级为“校准带”；manifest/board workflow/全部对客载体撤回 GBS 独立通过与首选路径，冻结件恢复默认，等待 held-out。 | acceptance/manifest schema 测试；跨载体 `held-out`/校准/冻结默认断言；HTML builder 正控。 |
| V4-2 | `8e117142211f8a66bef0de56337fb51017dec126` | B2 host 归档与报告日期按原始纳秒时间戳订正为 2026-09-04；无独立事前 tag 的证据称固定合同重放。执行 contract/runner 内保留原 remote 字面量以维持已发布 SHA；新增“先合同+analyzer 提交/tag，后板上运行，再单独结果提交”长期规则。 | contract/runner SHA 与 `run_record.txt` 逐值一致；B/B2 host 测试；旧日期路径与锚点扫描。 |
| V4-4 | `8e117142211f8a66bef0de56337fb51017dec126` | 新增 PM 裁决台账，覆盖身份/tag waiver、p50/追加重复驳回、S4 n=3 中位、gst 方向、v4 校准降级和 B2 证据等级。 | 本文件与 changes 索引均链接台账；local-link-check。 |
| A-minor | `8e117142211f8a66bef0de56337fb51017dec126` | 修正 changes 无效 SHA 并增加全 40 位提交可解析测试；v3 异常文案、51%–53% 概述、6 个板端 home 路径、模板入口链接检查和 B2 公开重放缺口全部闭环。 | `git rev-parse` 参数化测试；`INFO template-entry-links`；敏感/旧路径扫描；完整 host verify。 |

## 第 4 轮终审闭环（demo-v6，2026-09-07）

基线 main `43f11a6` / demo-v6 `1c637e1`；修复引用为 `demo-v7^`（最终 main）。本轮
host-only，未连接板端。测量、验收带与技术结论没有变更；补公开的是已有 retry2 记录。
[`PM 裁决`](pm_decisions.md) 与 [`版本差异`](changes_since_demo_v2.md#13-demo-v6-demo-v7)
提供逐编号追溯。

| 发现编号 | 修复提交 | 修复内容 | 验证方式 |
|---|---|---|---|
| P0-1 / N6-01 / V6-02 | `demo-v7^` | 显式构建必须生成、提取并落盘完整 RPM/三 ELF；环境不可用/锁超时非零 `NOT-EVALUATED`，缺产物/漂移硬失败；root 属主清理残留单列 REPORT_ONLY | 自包含 GBS/RPM/提取桩覆盖成功、缺 GBS、锁超时、缺 RPM、逐个缺 ELF、SHA 漂移；EPERM 测试；[`真实构建摘要`](../data/raw/demo_v7_delivery_20260907/gbs/build_summary.json) 与 [`输出`](../data/raw/demo_v7_delivery_20260907/gbs/workflow_summary.tsv) |
| P0-2 / V6-01 | `demo-v7^` | 最小环境只软链显式白名单；确认并披露 22 个命令与 Python ≥3.10；增加损坏工具形态 | 白名单不包含额外 host 命令的正控；真最小完整 verify；三克隆 × 五 PATH 矩阵；旧 Python 前置失败测试 |
| P0-3 / N6-02 / V6-1 | `demo-v7^` | rpmspec 非零、超时或不可执行只 SKIPPED，静态合同仍硬失败 | 损坏 rpmspec RC=42 完整 verify 通过；缺失 rpmspec 路径通过；静态合同缺陷测试 |
| P1-1 / N6-03 | `demo-v7^` | 对客载体限定 held-out 只覆盖 alloc_bench；补公开 retry2 gst 紧凑件及三 ELF/媒体身份范围 | 全 pull manifest/大小/资产 SHA 检查；六个派生件与原归档逐字节相同；公开 cycles 三派生 cmp |
| P1-2 / V6-2 | `demo-v7^` | 历史调用与固定 source commit 的 checker 复跑命令区分，四处一致说明 | manifest/build_summary 命令一致性与实际构建 argv 记录 |
| P1-3 | `demo-v7^` | pending 按实际 held-out/旧 retry2 分范围订正并保留日期追注 | 记录与范围文档相互链接 |
| P1-4 / V6-5 | `demo-v7^` | B 直接 unsorted 节点缺席记 0、B2 sizes 直方图求和的差异和低计方向披露 | 对照两个原分析器；原数值未重写 |
| P1-5 / V6-6 | `demo-v7^` | 估算器/落点追注日期按 B2 实际执行日统一，恢复“按终审裁决订正” | 日期/链接检查；历史路径明确为任务标识 |
| P1-6 / V6-7 | `demo-v7^` | INDEX 补 GBS rebaseline 与 PM 台账 | 本地链接检查 |
| P1-7 / N6-04 / V6-4 | `demo-v7^` | 新合同 annotated tag、tagger/推送时间与 ≥10 分钟审计间隔 | 交付流程/README/PM 台账一致，历史轻量 tag 不改 |

历史 v4/v6 的退出与依赖表述保留在上方旧轮次；现行行为以上表和 workflow README 为准。

## 第 5 轮终审闭环（demo-v7，2026-09-07）

范围：仅 host 交付工具自证与文档；未连接板端，不改测量、验收带或技术结论。
修复提交用 `demo-v8^` 定位最终 main（避免自写自身 SHA）；旧标签/旧构建记录保留。
裁决依据见 [`PM 台账`](pm_decisions.md#2026-09-07-第五轮裁决demo-v7-demo-v8)。

| 发现编号 | 修复提交 | 修复 | 验证方式 |
|---|---|---|---|
| P0 / N7-01 | `demo-v8^` | checker 取锁后、调用前写指纹；干净提交硬门；publisher 原样搬运、不补写哈希；旧记录另存 | git show 执行 commit 两脚本字节哈希与归档/交付相等；缺失、伪造、dirty、HEAD 变化拒绝测试；真实 GBS 干净快照归档 |
| P1 / N7-02 | `demo-v8^` | 锁不可写/RPM 工具损坏/未知 GBS 错误 NOT-EVALUATED RC=2；源码编译缺陷与缺产物 FAIL RC=1 | 环境/编译诊断桩；逐个缺 RPM/ELF、SHA 漂移、锁超时测试 |
| P1 / N7-03 | `demo-v8^` | 白名单逐项检查真实可执行文件 | awk/dirname/python3 函数与别名冒充拒绝；真最小完整 verify |
| P1 / N7-02b / N7-06 | `demo-v8^` | README 标题限定 alloc_bench；packaging 唯一入口、source commit/buildroot/路径/范围统一 | packaging 纳入跨载体 host 测试 |
| P1 / V6-8 | `demo-v8^` | 固定 repo 行 cmp；移动 reference 单独记录、不比较历史字节 | 固定行投影测试；保留历史四仓原值，无新扫描结论 |
| P1 / V6-9 | `demo-v8^` | 导语中心按 medium-only/mixed 写 50.67% / 52.79% | 与现有校准中心对应的跨载体测试 |
| P1 / F12 | `demo-v8^` | 指南披露同轮连续会话与跨轮指认依据、唯一硬件标识证据缺失 | 文档/链接检查，不增加同板证明 |

交付门保持三克隆 × 五 PATH = 15 次完整 verify；结果与真实构建身份摘要随收尾记录。

N7-01 实施提交为 `707920125d6c0af6993f297214242dd4723e6b94`。该 clean HEAD 的真实
GBS 构建及 publisher 校验均已通过，两个 JSON 搬运前后 cmp 静默，三 ELF 与 manifest
一致；执行 UTC/耗时/残留路径见 [`归档说明`](../data/raw/demo_v7_delivery_20260907/gbs/README.md)。
新增公开归档测试把 entrypoint/checker 哈希同时绑定到执行 commit 的文件字节和当前
交付文件字节；结果提交不得更改这两个脚本，否则必须重新构建、重新归档。

## 第 6 轮终审闭环（demo-v8，2026-09-07）

仅交付工具校验加固与文档，不改测量或结论。批准依据见
[`PM 第六轮台账`](pm_decisions.md#2026-09-07-第六轮裁决demo-v8-demo-v9)。
修复提交通过 `demo-v9^` 解析，保留 `demo-v8` 原标签与原构建 JSON/TSV。

| 评审编号 | 修复提交 | 验证方式 |
|---|---|---|
| P0 N8-01（1–4） | `demo-v9^` | `test_build_time_proof_attacks_are_hard_failures` 四攻击；`test_output_proof_attacks_fail_checker_and_publisher` 两复制边界 × 四攻击；均无 PASS，checker RC=1 |
| P0 N8-02（5） | `demo-v9^` | `test_exported_command_and_target_functions_cannot_bypass_preflight`：command 与 dirname/python3/awk 同时导出函数，RC=2 且不进入 verify |
| P0 N8-02（6） | `demo-v9^` | `test_recursive_entrypoint_is_refused_before_any_child_command`：空 PATH、继承标记即拒绝；受控 host fixture 独立调用仍完成 |
| P1 CC N8-01（7） | `demo-v9^` | `test_skip_worktree_build_input_mutation_is_rejected`：两 config/manifest/spec 逐项加合法空白、porcelain 为空，仍在 GBS 前 RC=1；成功 proof 集合逐文件对 Git 对象 |
| P1 N8-03/V8-1（8） | `demo-v9^` | 缺头文件 unknown/manual、明确环境优先、其他源码错误 FAIL 的分类回归；README 表同步 |
| P1 CC N8-02/N8-03/N8-04（9） | `demo-v9^` | 原始 gbs.log 缺失/篡改/符号链接的 publisher 拒绝测试；脏快照标签测试；双语 README/packaging 能力边界与链接核验 |

根因复现记录：旧 checker 在内容改写、截断、同字节符号链接替换三例均 RC=0；删除例
RC=2，被误分环境。修复后四例都为 proof integrity RC=1，且不生成成功摘要。

实现提交 `de89a10bb187d0a1576aaf24a45b9586c55ba3c1` 的干净快照已实际完成 GBS 构建与
同 HEAD publisher 校验，六文件哈希与 Git 对象一致；公开导入 cmp 静默。执行自证及
日志哈希见 [`v9 构建归档`](../data/raw/demo_v9_delivery_20260907/gbs/README.md)。
`test_v9_public_execution_proof_matches_commit_and_delivery_files` 把公开指纹同时绑定到
执行提交、交付 HEAD 与当前文件。旧 v8 JSON/TSV 不变，仍单独按历史执行提交复核。
文档另明确 RPM wrapper SHA 漂移为 REPORT_ONLY，避免把它与 ELF/身份硬门混称。

## 第 7 轮终审闭环（demo-v9，2026-09-08）

仅 host 入口执行环境净化与文档；没有板端连接，不改测量、验收带或结论。
修复提交用 `demo-v10^` 定位最终 main；历史 demo-v9 与既有构建 JSON/TSV 保留。
批准依据见 [`第七轮 PM 台账`](pm_decisions.md#2026-09-08-第七轮裁决demo-v9-demo-v10)。

| 评审编号 | 修复提交 | 闭环与验证方式 |
|---|---|---|
| P0 Codex N9-01（1–2） | `demo-v10^` | 在真实 Python 前只用 shell 内建采集当前函数/别名；拒绝自清/自删标记后遗留的未导出函数；Python execve 新的 `bash --noprofile --norc -p` 并删除全部启动/导出函数字段；预置净化标记（含空值）拒绝。`test_startup_self_clearing_unexported_functions_fail_before_mode` 五变体均 RC=2、无 MODE/成功输出 |
| P0 N9-01（3） | `demo-v10^` | `predelivery_check.sh` 增 startup-injection 环境；三种克隆各做五变体拒绝，再真跑完整 verify，共 18 次完整验收，不把拒绝计作复算成功 |
| P1 Kimi V9-1（4） | `demo-v10^` | `runtime-injection` 与 `runtime-preflight missing default-verify command` 分开；旧 exported command+target、函数/别名和缺 awk 回归保持 |
| P1 CC N9-02（5） | `demo-v10^` | 明示包括 module 在内的全量函数拒绝，提供 env -i + 无启动文件 shell 的规避命令；双语模板同步 |
| 台账（6） | `demo-v10^` | CC N9-01 整体 proof 伪造、F01/F05 包外交付不做实现改动，记录正式 release 待处理与三家正常使用判断 |

根因复现：旧入口在“自清标记”“未导出函数单独存在”“启动文件自删除”三个场景
均实际输出 RC=0 / OVERALL PASS，公开分析器与 cmp 被函数截获。新增回归在修复前
五个子例均失败；修复后全部在 MODE 之前拒绝。真实 shell 工作流正文仍在同一
`reproduce.sh` 内，未把执行逻辑移出已有 provenance 文件字节覆盖集合。

实现提交 `6a10812848f31170bacb70022b1b35fe9d161892` 的干净快照已完成真实 GBS 构建
与同 HEAD publisher 校验；新记录见 [v10 构建归档](../data/raw/demo_v10_delivery_20260908/gbs/README.md)。
三 ELF 与 manifest 相同，原始日志/proof 均由 checker 校验；旧 v9 JSON/TSV 不变。
`test_v10_public_execution_proof_matches_commit_and_delivery_files` 把新归档同时绑定到
执行 commit、交付 HEAD 与当前六文件字节。另有 exec/exit 异常返回不落入未净化正文
的回归，以及 Modules 拒绝与干净进程规避命令的正反测试。

切库前检查另发现 Modules 正向 fixture 清空环境时丢弃临时 identity override；已把该
环境测试的身份固定为自身 HEAD，避免依赖尚未创建的交付标签。独立的 required /
REPORT_ONLY 身份测试与最终远端克隆门保持原语义。

## 第 8 轮定向闭环（demo-v10，2026-09-08）

仅 host 入口信任边界与注入拒绝路径加固，不改测量、验收带、held-out 或技术结论。
依据见 [`N10-01 PM 裁决`](pm_decisions.md#2026-09-08-定向裁决demo-v10-demo-v11)。
保留 demo-v10 及上节记录，但上节“exec/exit 不落入未净化正文”不足以关闭原 N9-01：
旧测试在 exec+exit 同时存在时特意没有断言退出码，也没有要求非空诊断或零调用。
本轮增强测试在旧实现上出现 29 个失败子例，包括空输出 RC=0、拒绝时调用冒充函数、
以及禁用 builtin 后把枚举失败当作空表并输出 OVERALL PASS；这些不能算拒绝成功。

| 评审编号 | 修复提交 | 闭环与验证方式 |
|---|---|---|
| N10-01（1） | `demo-v11^` | 脚本最后的真实绝对路径 Python 直接返回状态；拒绝不调用 shell exec/exit/printf；惰性正文移至最后调用之前，不留成功尾命令覆盖 RC |
| N10-01（2） | `demo-v11^` | POSIX lookup 的特殊内建优先于函数，转义名称不展开别名；先用 readonly 检查 builtin 名称，再严格校验 declare/alias 枚举状态；被遮蔽或禁用即失败关闭 |
| N10-01（3） | `demo-v11^` | `test_bootstrap_cannot_fall_through_to_unclean_workflow_body` 六函数集合 × 六上下文；原五变体强化诊断/零调用；另测 builtin/declare 禁用，共 43 个拒绝变体。每例 RC=2、明确非空 FAIL、无 MODE/PASS、调用哨兵文件不存在 |
| N10-01（4） | `demo-v11^` | `predelivery_check.sh` 从测试同源读取变体数；每克隆 43 次预期拒绝后真跑完整 verify；三克隆六环境 = 18 次完整 verify + 129 次拒绝探针，不把拒绝算复算 PASS |

代码仍在 provenance 覆盖的单个入口文件内。普通环境的递归/缺依赖/旧 Python、
Modules 净化命令、required 与 REPORT_ONLY 交付身份、GBS proof 完整性回归均保留。
旧 Python 诊断统一到 stderr；递归自链接改为执行前文件身份识别，不启动递归子脚本。

实现提交 `3fe95c18a52e86ef45ad97ab0b6323737eecd311` 的 clean HEAD 已实际完成 GBS 与
同状态 publisher 校验，入口/两配置/manifest/spec/checker 六文件身份一致，公开导入
cmp 静默；[v11 构建归档](../data/raw/demo_v11_delivery_20260908/gbs/README.md)
由 `test_v11_public_execution_proof_matches_commit_and_delivery_files` 同时校验执行
commit、交付 HEAD 与当前文件字节。旧 v10 JSON/TSV 保留为历史，不冒充 v11 证据。
