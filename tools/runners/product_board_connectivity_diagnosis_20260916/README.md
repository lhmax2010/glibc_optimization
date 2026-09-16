# 产品板连接诊断（不采样）

host 上顺序执行 PM 2026-09-16 指定的网络/sdb/SSH 排障步骤；不使用历史采样器，
不推文件、不安装、不改板端配置、不提权、不重启。唯一状态变更是已授权的本机
`sdb kill-server` / `sdb start-server`。失败不自动重试，显式端口 connect 是 PM
要求的第二种地址写法，不是循环重试。

```sh
python3 -m unittest discover -s tools/runners/product_board_connectivity_diagnosis_20260916 -p 'test_*.py'
python3 tools/runners/product_board_connectivity_diagnosis_20260916/diagnose.py \
  --ip '<PRODUCT_BOARD_IP>' --output '<new-host-output-directory>'
```

输出目录必须不存在。每条命令分别保存 stdout/stderr 原字节、host RC、UTC 时间、
SHA-256。网络测试各一次，socket connect/只接收 banner 上限 3 s，零发送载荷。
单项 TCP refused 不是整个诊断的停止门：本轮专门授权继续其他层排障。

SSH 仅 TCP/22 可达才尝试一次 `uname -a`，BatchMode/5 s/ConnectionAttempts=1，
不尝试密码、不生成/上传密钥；可使用本机已有公钥认证环境，不扩展权限。
`-F /dev/null` 防止既有代理/转发等配置混入；known-hosts 指向 `/dev/null`，
不保存远端主机密钥。命令成功后仅允许五项只读请求，带 RC/DONE/FAIL 且 ≤200 字节。
未认证则不执行这五项；即使成功也不进入测量。

host 补充检查仅 `ip route get <PRODUCT_BOARD_IP>`、`ss -ltnp 'sport = :26099'`、
`pgrep -a -x sdb`、`readlink -f <local-sdb-path>`，用于解释无 ARP 项及本机 server
状态。实际逐条命令由[公开记录](../../../data/raw/product_board_connectivity_diagnosis_20260916/transcript.md)给出。

发布仅在 host 执行，原始件保留，公开件按映射脱敏并保留双哈希：

```sh
python3 tools/runners/product_board_connectivity_diagnosis_20260916/publish.py \
  --source '<host-raw-directory>' --output '<new-public-directory>' \
  --mapping desensitize_map.tsv --ip '<PRODUCT_BOARD_IP>'
```

`desensitize_map.tsv` 为本地既有映射，不公开。诊断只支持分层判断：连接拒绝不能
单独区分无监听/防火墙拒绝/转发目标差异；空 banner 也不能证明非 sdbd。
