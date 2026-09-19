# EasyTier 监控设计

EasyTier 是只读 Client domain。它通过固定本地 CLI 和固定 loopback RPC 策略采集 node、peer、
route、connector 与 traffic 的有界投影，不管理 EasyTier。

## 证据与失败语义

每条固定 command 独立记录 collection time、duration、status 和 last successful collection。
失败周期不能用虚构的空 payload 覆盖已有 command evidence。timeout、CLI execution、RPC
unavailable 和 parse failure 保持不同诊断。

`last_success_at` 表示最后成功 command result；失败时不能改写为本次 attempt time。当前数据仅在
Client report 被 Server 时钟接受后才 fresh。

## 汇总、展示上限与不确定性

Client 按 own peer ID 排除本机 peer。total、direct、relay、unknown path 和 IPv6 UDP direct 等
汇总基于完整已校验观测集，而不是 display 保留的行。展示列表独立限额：peer、route、connector、
traffic-by-instance 最多 16 条，traffic sample 最多 64 条。

每个有界列表的 `total`、`displayed_total` 和 `truncated` 区分观测数据与渲染数据；改变输入顺序
不能改变汇总结论。IPv6 UDP direct 仅在有正向 direct IPv6/UDP 证据时为 true；仅在相关观测
确凿时为 false；证据不足时为 null/不可观测。

traffic baseline 绑定观测到的 network 与 instance identity。network/instance 变化、已知 restart、
counter reset 或过长采样间隔会重新建立 baseline，而不是报告误导性的瞬时速率。

## 安全边界

运行时 allowlist 只有只读 query，不含 connector、route、credential、whitelist、port-forward、
logging 或 service lifecycle command。原始配置、endpoint secret、credential 和任意 feature object
不会投影。UI 只读取已有 stats 文档，不创建控制 endpoint。
