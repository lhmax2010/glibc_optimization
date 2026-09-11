# demo-v12 候选交付停止记录（2026-09-11）

**STOP_HOST_REPLAY_TAG_DEPENDENCY；不切 demo-v12，demo-v11 保持有效。**
板上延期收尾已经完成，原 21 格验收不受影响；停止发生在 host 交付自检。
依据 PM“再次命中停止门即停”的裁决，不继续修复该依赖或切库，不跳过测试绕过门。

## 1. 已完成部分

- [目录处置与收尾](system_level_before_after_20260908.md#121-实际处置与收尾结果)：
  四目录非空全部保留待查；镜像 python 未动；UID 5001→0→5001，root-off 首次成功，
  进程/包清单/governor/健康核验通过。没有目录/进程删除、测量重跑或重启。
- [21 格组合](../data/raw/system_level_before_after_20260908/accepted_matrix/README.md)：
  原 18+3 格、333 对点、五份派生件逐字节复算一致；独立审计确认合同与数据未改。
  HTML、双语入口模板与指南的新数字是工程集成预览，不代表新交付快照已就绪。
- 本轮 runner 240 项及 HTML 10 项测试已通过；不是完整交付测试全通过。
- [真实 GBS 候选构建](../data/raw/demo_v12_delivery_20260911/gbs/README.md)：
  clean HEAD `4539139956b89d82864a93c57ce68b7b07bdc850`，RC=0、三 ELF SHA 一致，
  执行 proof 原样发布；host buildroot 残留依既有规则 REPORT_ONLY。

## 2. 失败命令与证据

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tools.reproduce.test_host tools.report.test_build_demo_report
```

现场输出节录（不含临时 host 路径）：

```text
FAIL	system-before-after-public-replay-cmp	RC=1
PASS system-before-after compact replay cells=21 cycles=333 group_arms=7
fatal: invalid object name 'system-before-after-contract-20260908'.
OVERALL	FAIL	items=1
Ran 64 tests in 39.143s
FAILED (failures=8)
```

[机器转录](../data/raw/demo_v12_delivery_20260911/host_gate_result.json)明确区分测试方法数与
子用例失败数。三种 HEAD 源形态 × 两种身份校验共六个子用例失败，另两个独立身份用例
同因失败；并非八次板端重试。当前工作区直接单项 verify 入口测试可通过，但不能代替
克隆隔离验证，不能据此宣告整体 PASS。

## 3. 已定位边界与待裁决项

新 host 收尾重放的调用链是 `analyze_directory_disposition.replay → sources()`。
[sources()](../tools/runners/system_level_before_after_20260908/audit_single_cleanup_20260911.py)
以 `git show TAG:<path>` 验证合同与 analyzer；TAG 固定为
`system-before-after-contract-20260908`。
[交付身份 fixture](../tools/reproduce/test_host.py)刻意使用 `git clone --no-tags`，只获取
当前 HEAD，以覆盖普通 main/demo/detached 克隆且不依赖交付 tag 的语义。
因此即使两个合同文件本身正确，命名 tag 不可解析仍使新增复算硬失败。
失败 fixture 的源 HEAD 是上述 clean 提交；不是更改验收数字造成的失败。

待 PM 授权下一轮闭合：让 host 公开件复算在无命名 tag 的克隆中仍能以已固定的合同
commit/Git 对象严格校验原字节，或明确分离板端开跑的 annotated tag 门与 host 重放。
这里只提出修复方向，**未实施、不弱化合同完整性、不修改 fixture 为漏检**。
本轮新增工作仍保存在 main 供修复；main 的该 host 测试回归尚未闭合，不用于 HQ 交付。

## 4. 未执行与有效快照

远端 18 次完整 verify / 129 次启动拒绝矩阵、demo-v12 分支/标签发布、v12_review_brief
均为 NOT_EXECUTED_STOP_GATE。不是跳过后判过，也没有重跑任何已验收测量。
保留 `demo` 与 annotated `demo-v11`：commit
`0e8a2f731b13690009badf1ca2acbd57018e7bc8`，tag 对象
`f1266c0be6c225a2ceb962836380c656758f9427`。
最终提交清单见[两日汇总](twoday_summary_20260910.md)。
