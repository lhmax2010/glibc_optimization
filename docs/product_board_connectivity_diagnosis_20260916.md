# 产品板连接分层诊断（2026-09-16）

## 1. 结论与范围

**故障已定位到目标端点的 TCP/26101 服务可达性层，而不是整机网络中断，也没有
进入可证实的 sdbd 握手/授权阶段。** 该端点 ping 正常、SSH 22 开放，26101 则立即
返回 `Connection refused`。最直接的待查项是 sdbd 未监听/未开启网络调试，但
防火墙主动拒绝、转发目标不对、共享地址换机也能造成相同现象；尚不能仅凭 host
观测断言 sdbd 进程不存在。SSH 已到认证阶段，未认证成功，未取得板型或进程证据。

另有**本机客户端异常**：显式 `sdb start-server` 报 `protocol fault: no status`，
host RC 却为 0，紧随其后的本机 26099 没有监听。随后 `sdb connect` 自动拉起本地
server，最终能观察到新 server 的监听，但目标连接仍失败。不能把本地异常等同于
目标握手失败，也不能将 RC=0 当作连接成功。

按 PM 本轮扩展诊断授权执行；不同于前两轮“connect 失败立即停”，本轮继续完成
网络、两种 connect 写法与一次 SSH 排障，**没有重复测量、采样或进入 floor 流程**。
不推送文件、不装卸包、不改板端配置、不注入、不提权、不重启。仅重启本机 sdb server。
实际基线 main 为 `f90d613f5f64f1c3e4a59c8668d1898f601f61d7`，包含用户提供的
`f325489` 及[上次续跑停止记录](product_floor_reconfirm_20260916.md#5-pm-确认恢复后的续跑2026-09-16)，未回退历史。

主诊断窗口：UTC `14:26:04.164256` 至 `14:26:10.729601`（北京时间 `22:26`）。
随后只补本机路由、最终监听与可执行路径读取，未再连接远端。
全部逐条时间戳、命令、stdout/stderr 原文（含空流）见
[完整诊断转录](../data/raw/product_board_connectivity_diagnosis_20260916/transcript.md)；
[机器命令记录](../data/raw/product_board_connectivity_diagnosis_20260916/commands.jsonl)
和[host 补充记录](../data/raw/product_board_connectivity_diagnosis_20260916/host_followup/commands.jsonl)
分别保留。公开件仅端点、host 路径与既有别名脱敏，板端未生成任何文件。

## 2. 网络层：IP 可达，26101 拒绝，22 可达

### 2.1 ping 原文

`ping -n -c 4 -W 2 <PRODUCT_BOARD_IP>`，host RC=0；stderr 为空。
[原始公开件](../data/raw/product_board_connectivity_diagnosis_20260916/raw/ping.stdout.txt)：

```text
PING <PRODUCT_BOARD_IP> (<PRODUCT_BOARD_IP>) 56(84) bytes of data.
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=1 ttl=63 time=0.400 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=2 ttl=63 time=0.725 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=3 ttl=63 time=1.47 ms
64 bytes from <PRODUCT_BOARD_IP>: icmp_seq=4 ttl=63 time=0.557 ms

--- <PRODUCT_BOARD_IP> ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3078ms
rtt min/avg/max/mdev = 0.400/0.786/1.465/0.408 ms
```

### 2.2 逐端口连接

Python socket 等价于 `/dev/tcp` 连接测试：每端口一次、超时上限 3 s，不发送应用载荷。

| 端点 | 结果 / host RC | 原文证据 |
|---|---|---|
| `<PRODUCT_BOARD_IP>:26101` | `ConnectionRefusedError` / `[Errno 111] Connection refused`；RC=1，未建立 TCP | [完整输出](../data/raw/product_board_connectivity_diagnosis_20260916/raw/tcp_26101.stdout.txt) |
| `<PRODUCT_BOARD_IP>:22` | `tcp_connected: true`；RC=0 | [完整输出](../data/raw/product_board_connectivity_diagnosis_20260916/raw/tcp_22.stdout.txt) |
| 本机 `127.0.0.1:26099`（重启前） | `tcp_connected: true`；RC=0 | [完整输出](../data/raw/product_board_connectivity_diagnosis_20260916/raw/tcp_local_26099_before.stdout.txt) |
| 本机 `127.0.0.1:26099`（显式 start-server 后） | `[Errno 111] Connection refused`；RC=1 | [完整输出](../data/raw/product_board_connectivity_diagnosis_20260916/raw/tcp_local_26099_after.stdout.txt) |

这里的 26099 是 host sdb server，不是板上端口。网络 ICMP/SSH 可达，故不符合
“ping/端口全不通”的情形；26101 是明确拒绝，而不是等待超时。

### 2.3 ARP 与设备同一性

`ip neigh show to <PRODUCT_BOARD_IP>`，host RC=0，stdout/stderr **均为空**，
没有目标 MAC 可记录或与历史比较。[原文](../data/raw/product_board_connectivity_diagnosis_20260916/raw/arp.stdout.txt)
保留零字节，不能把空结果写成设备不存在。

为解释该限制，补读本机 `ip route get <PRODUCT_BOARD_IP>`，RC=0：

```text
<PRODUCT_BOARD_IP> via <INTERNAL_ENDPOINT> dev enp128s31f6 src <INTERNAL_ENDPOINT> uid 1000 
    cache 
```

[路由原文](../data/raw/product_board_connectivity_diagnosis_20260916/host_followup/raw/route_to_target.stdout.txt)
显示经网关到达，目标不是本机直接二层邻居；不能用网关 MAC 替代板的 MAC。
`uid 1000` 是 host 路由查询属性，**不是板端 UID**。本次无法用 MAC 证明同板，
也未完成 uname/os-release 身份门，故不能认定该端点就是期望的产品 TV 或旧 RPI4。

## 3. sdb 层：本机重启异常与目标拒绝分别记录

本机可执行文件解析为 `<USER_HOME>/tizen-studio/tools/sdb`；
版本原文（RC=0）：

```text
Smart Development Bridge version 4.2.25
```

重启前 `ss -ltnp 'sport = :26099'` 和 `pgrep -a -x sdb` 均 RC=0：

```text
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      4            0.0.0.0:26099      0.0.0.0:*    users:(("sdb",pid=1949533,fd=5))
```

```text
1949533 sdb fork-server server --only-detect-tizen
```

观察到一个 sdb listener，未发现第二个非 sdb 程序占用 26099；现有 server 本身
不是冲突的充分证据。

| 顺序 | 操作 | host RC | 完整输出情况 |
|---|---|---|---|
| 1 | `sdb kill-server` | 0 | stdout/stderr 均空 |
| 2 | `sdb start-server` | 0 | stdout 空；stderr 见下方错误 |
| 3 | 本机 ss / pgrep / TCP 检查 | 0 / 1 / 1 | ss 仅表头；pgrep 空；TCP 拒绝 |
| 4 | `sdb connect <PRODUCT_BOARD_IP>` | 0 | 自动启动本机 server，然后连接错误 |
| 5 | `sdb devices` | 0 | 只有表头，无设备 |
| 6 | `sdb connect <PRODUCT_BOARD_IP>:26101` | 0 | 同样连接错误，无成功设备证据 |

显式 start-server 的 stderr 原文：

```text
error: protocol fault: no status
```

随后 ss 只输出：

```text
State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
```

不带端口 connect 的 stdout 原文：

```text
* Server is not running. Start it now on port 26099 *
* Server has started successfully *
error: failed to connect to remote target '<PRODUCT_BOARD_IP>'
```

devices 原文：

```text
List of devices attached 
```

显式端口 connect 原文：

```text
error: failed to connect to remote target '<PRODUCT_BOARD_IP>'
```

两种写法均失败，没有可证实的行为改善；错误文本省略端口不表示实际输入没有端口，
实际 argv 已记录。所有上述 sdb 子命令 host RC 都为 0，却包含明确错误或空设备表，
再次说明不能信任客户端 RC 作为成功证明。

最终只读 host 检查确认 connect 后存在新本机监听：

```text
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      4            0.0.0.0:26099      0.0.0.0:*    users:(("sdb",pid=1960524,fd=5))
```

```text
1960524 sdb fork-server server --only-detect-tizen
```

**banner 未执行**：原始 TCP/26101 测试已被拒绝，不满足“TCP 建连后握手失败”的
触发条件。没有返回字节可用于识别 sdbd 协议，更不能归因到具体 sdbd 版本或授权。
`protocol fault: no status` 出现在本机 start-server，不能作为板端 banner 证据。

## 4. SSH 层：可到认证阶段，但不允许登录

22 开放，故依 PM 要求尝试一次非交互 SSH；保留 BatchMode、5 s ConnectTimeout、
StrictHostKeyChecking=no，并显式 ConnectionAttempts=1。为避免 host 配置中的代理/
转发混入，使用 `-F /dev/null`；known-hosts 指向 `/dev/null`，不写持久主机密钥记录。
完整 argv 见[逐条记录](../data/raw/product_board_connectivity_diagnosis_20260916/transcript.md#ssh_uname_a)。

远端请求为 `uname -a`。host RC=255，stdout 空，stderr 原文：

```text
Warning: Permanently added '<PRODUCT_BOARD_IP>' (ED25519) to the list of known hosts.
root@<PRODUCT_BOARD_IP>: Permission denied (publickey,keyboard-interactive).
```

上述 known-hosts 提示为客户端原文；本次存储目标是 `/dev/null`，未保存密钥。
认证失败意味着请求的 `uname -a` 未执行；后续 uname -r、uname -m、os-release、
sdbd 进程与 systemctl 五项全部未执行。未尝试密码、未生成或上传密钥。

历史“sdb-only、不支持 SSH”不能直接替代本次观察：当前端点确有 SSH 认证响应，
但没有 root 登录授权。差异可能来自地址复用、镜像/服务配置改变或网络转发；
本次无板型/MAC 证据，不能在这些原因中确定一个。

## 5. 给 PM 的具体行动清单

1. **先核实实际设备**：在产品 TV 的本地界面/串口确认当前 IP、镜像身份与网卡 MAC；
   对照交换机或 DHCP 租约确认共享地址当前绑定。提供 MAC 后才能做同板比较；不要
   仅凭本次 ping 或 SSH 响应认板。
2. **在板本地检查网络调试服务**：确认开发者模式/网络 sdb 是否开启，查看 sdbd
   进程及 26101 的监听地址。若未启动/未启用，请 PM 在板本地启用；若只绑定回环
   或其他接口，按板的受控配置流程处理。本轮没有执行这些变更。
3. **若板本地已经监听**：核对 host 到板这条路径上的 ACL、防火墙主动 REJECT、
   端口转发/NAT 目的设备；本次 TCP 明确拒绝，需先解决这一层，再查 sdb 协议。
4. **通道恢复后再授权下一次连接确认**：先要求 26101 TCP 可连及 sdb devices
   出现有效设备，再重新走产品身份门。若届时变成 TCP 可连但 sdb 失败，才执行
   受限 banner/版本/授权排查；本次没有据此更换客户端或改板端授权。
5. **SSH 不作为自动绕过通道**：当前 root 认证被拒绝；如 PM 决定用 SSH 辅助
   运维，应另行提供/批准受控访问方式，而不是尝试密码或擅自布置密钥。本轮到此停止。

本机 start-server 异常为附带未定根因项，最终 listener 已恢复；不能宣称重启本机
server 修好了目标。优先处理目标身份及 26101 的监听/路径，不进行无上限重连。

## 6. 复现、证据与收线

[harness](../tools/runners/product_board_connectivity_diagnosis_20260916/README.md)
仅包含本次诊断，不调用任何测量入口。参数：ping 4 次，端口/只接收探测 3 s，
SSH 连接 5 s、一次尝试；两种 sdb connect 各一次。输出目录拒绝覆盖；命令原始
stdout/stderr 分别存档并计算 SHA-256。[发布清单](../data/raw/product_board_connectivity_diagnosis_20260916/publication.json)
覆盖 45 个执行记录文件的原始/公开双哈希；完整未脱敏件本地留存，可按请求提供。

```sh
python3 -m unittest discover -s tools/runners/product_board_connectivity_diagnosis_20260916 -p 'test_*.py'
```

8 项 host 测试通过：关闭端口时跳过 SSH/banner、开放端口后的单次路径、SSH
精确五项范围与请求长度、socket 零发送、输出拒绝覆盖、sdb RC=0 错误文本不当成功、
缺远端标志即停、非交互且不保存主机密钥。没有新性能/内存测量数字。
IP 使用 `<PRODUCT_BOARD_IP>`；无可发布的目标 MAC。仅推 main，不切 demo。
