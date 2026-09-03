> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# glibc 优化项目公开仓库迁移审计

- 执行日期：2026-08-14
- 目标：公开 GitHub 仓库 `lhmax2010/glibc_optimization`
- 边界：全程仅做 host 本地文件操作，未连接任何开发板；除本报告外，原 workspace 文件未改动

## 1. S1 清点与分类

清点以迁移前 workspace 为准，四类互斥；详细逐文件 manifest 只保留在本地迁移审计目录。

| 类别 | 文件数 | 总体积 | 纳入公开仓库 |
|---|---:|---:|---|
| 文档 | 60 | 1,028,336 B（约 1005 KiB） | 是；59 份 `docs/*.md` 加根目录可行性报告，后者迁入 `docs/` |
| 代码/工具 | 74 | 431,188 B（约 422 KiB） | 是；9 个核心源码/构建文件和 65 个采集、分析 runner |
| 派生数据 | 45 | 102,770 B（约 101 KiB） | 是；矩阵、直方图、汇总与 `derived/*.tsv` |
| 原始证据 | 7,646 | 473,194,571 B（约 452 MiB） | 否；仅保留在本地 |

初始拟发布集合为 179 个文本文件、1,562,294 B；新增公开索引和本迁移审计后另行计入最终仓库统计。

## 2. S2 敏感信息扫描与脱敏

### 2.1 初扫命中

初扫覆盖拟发布的文档、工具和派生数据。详细的文件、行号和原文片段仅保存在本地，不进入公开仓库。

| 类型 | 命中数 |
|---|---:|
| 私网 IPv4 | 75 |
| 产品 BUILD_ID | 7 |
| 产品/测试镜像标识 | 102 |
| 内部应用 ID | 139 |
| 内部 `DN_*` 进程名 | 203 |
| 内部 service/进程名 | 689 |
| 本地绝对路径 | 64 |
| 主机名/账号/人名 | 56 |
| 凭据类 | 1 |
| 内部仓库地址 | 1 |
| 其他内部主机名 | 0 |
| **合计** | **1,337** |

### 2.2 一致替换规则

真实值到代号的 `desensitize_map.tsv` 只保留在本地，并被 `.gitignore` 明确排除。公开规则只说明类型：

| 类型 | 公开形式 |
|---|---|
| 测试板/产品板地址 | `<TEST_BOARD_IP>` / `<PRODUCT_BOARD_IP>`；按报告中的板角色做上下文一致映射 |
| 产品 BUILD_ID 与镜像串 | `<PRODUCT_BUILD_ID>` / `<PRODUCT_IMAGE*>` |
| 测试镜像串 | `<TEST_IMAGE_*>`，保留不同镜像之间的可比性边界 |
| 内部应用/进程/service | `App*` / `AppProc*` / `Service*`，同一实体全文一致 |
| 本地 workspace 与用户目录 | `<WORKSPACE>` / `<USER_HOME>` |
| 主机、账号与人名 | `<HOST>` / `<USER>` |
| 内部仓库与域名 | `<INTERNAL_REPO>` |
| 凭据 | `<REDACTED>` |

所有测量数值、性能与内存结论、源码 `file:line` 锚点、命令语义和失败记录均保留。历史板标签也被替换为角色代号；每份公开 Markdown 均标注原始证据仅在本地保存。

### 2.3 脱敏后硬门

脱敏后对全文和文件路径重跑全部模式，结果如下：

| 模式 | 剩余命中 |
|---|---:|
| 私网 IP / BUILD_ID / 镜像标识 | 0 |
| 内部应用、进程与 service 名 | 0 |
| 本地路径 / 主机 / 用户 / 人名 | 0 |
| 凭据 / 私钥片段 | 0 |
| 内部仓库 / 域名 | 0 |
| **总计** | **0** |

另行检查旧板标签、敏感文件名和 Markdown 公开说明覆盖率，分别为 0 个残留、0 个残留、61/61 已标注。加入 README 与本报告后共复扫 181 个文本文件，全部模式总命中仍为 0，推送硬门通过。

### 2.4 二进制处置

共发现并排除 6 个编译产物：3 个 alloc_bench、2 个 reclaim_probe、1 个 gst_loop_decode。对其执行 `strings -a` 后共命中 22 处身份信息：

| 产物组 | 文件数 | `strings` 命中 | 处置 |
|---|---:|---:|---|
| alloc_bench | 3 | 6 | 不推送，仅发布源码与 Makefile |
| reclaim_probe | 2 | 4 | 不推送，仅发布源码与 Makefile |
| gst_loop_decode | 1 | 12 | 不推送，仅发布源码 |
| **合计** | **6** | **22** | **全部剔除** |

命中均属于本地路径或用户标识。公开集合的文件类型复核未发现二进制或非文本文件。

## 3. S3 最终仓库结构

```text
README.md
docs/
tools/
  alloc_bench/
  reclaim_probe/
  gst_loop_decode/
  inventory/
  runners/
data/
  derived/
```

公开仓库 `.gitignore` 内容：

```gitignore
# Local migration audit material and the real-value replacement map.
.migration-local/
desensitize_map.tsv

# Build products are reproducible from the published sources.
*.armv7l
*.host
*.host-asan
*.o

# Raw board evidence stays in the private local archive.
board_results/
raw/
**/raw/
data/raw/
*.xml
*.dlog
*.dmesg
*.log
```

没有沿用原 workspace 对 `docs/` 的忽略规则；公开仓库明确收录文档。

## 4. S4 提交与推送结果

主题提交：

| 提交 | 哈希 | 内容 |
|---|---|---|
| 文档 | `22ca17db781cbb4a0866e3d79d71baef40bcb485` | 脱敏后的设计、评审与实验报告 |
| 工具 | `8224138a3f594aff062978729e19931bd079cc50` | 测量工具源码与 runner |
| 派生数据 | `11a136522227672666743634813c94dc461db86e` | 矩阵、直方图与派生 TSV |
| 仓库索引与迁移审计 | `7d999d2d9d0992eb291a8a48fe77fb8d648a7e77` | README、`.gitignore` 与本报告的首次发布版本 |

首次推送原文为 `main -> main`（新分支），远端 `refs/heads/main` 随后解析为 `7d999d2d9d0992eb291a8a48fe77fb8d648a7e77`。从 GitHub 重新做干净克隆后的核验结果：

| 项 | 结果 |
|---|---:|
| 跟踪文件 | 182 |
| 跟踪文件总字节 | 1,576,334 B |
| 干净克隆工作树（含 `.git`） | 3.0 MiB |
| `.git` 目录 | 776 KiB |
| Git pack | 565.64 KiB |
| 意外编译产物 | 0 |
| 原始证据路径 | 0 |
| 被跟踪的真实映射表 | 0 |

本节的推送后补记由最后一个审计提交发布；该提交自身的哈希以远端 `main` 为准，无法在不制造下一次提交的情况下自引用写入本文件。最终提交哈希同时记录在迁移执行回执中。

## 5. 未推送内容

| 内容 | 原因 |
|---|---|
| `board_results/` 原始证据 | 约 452 MiB，包含大块日志和高敏感度运行环境细节；本地保留 |
| `desensitize_map.tsv` | 含真实值与公开代号的对应关系；仅本地保留并忽略 |
| `.migration-local/` | 含逐文件 manifest、初扫原文片段、扫描脚本和审计中间件；仅本地保留 |
| `*.armv7l` / `*.host*` / `*.o` | 可重建，且 `strings` 检出本地路径/用户标识 |
| malloc_info XML、smaps/dlog/dmesg、T0-T5 快照 | 属于原始证据，报告中的汇总与派生数字已公开 |
| glibc 上游源码树与构建缓存 | 不属于本项目产出，且会无谓复制上游仓库 |
