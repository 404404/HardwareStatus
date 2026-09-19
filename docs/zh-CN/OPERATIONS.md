# 运维

## 正确理解状态

Server 时钟决定 Device v2 生命周期和 freshness。恢复的 state 是有用证据，但在下一次 report
被接受前仍为 stale。采集成功、数据 freshness 与业务/硬件健康是独立信号。

非故障限制包括：未配置的可选组件、合法空 EasyTier 集合，以及 USB SMART 能提供可信属性健康
结果但没有 native return status。这些会以 partial/limited 诊断保留。SMART `failed`、SMART
字段非法、Device v2 上报被拒绝、认证失败或必需 transport 失败仍是故障证据。

## 使用组件诊断页

组件诊断页是 Server 对当前 stats 投影的解释。应同时查看 component、稳定 resource identity、
source、field、code 与有界 reason。它不是请求日志，不能含有凭据或完整原始 payload。

`observed_count`、`displayed_count` 和 `truncated` 区分有界 UI 列表与完整观测集合。第一行看似
健康不能取消其他资源保留的 fault。有效恢复 report 到达后，当前诊断会消失；历史审计应在当前
投影之外保存。

## 日常诊断

比较 Client accepted collection time、Server receive time、运行 image digest/OCI revision、组件
freshness 和资源诊断。不要通过进入容器执行任意 shell、改 router、改磁盘设置或执行未文档化
命令排查展示问题；仅使用固定只读诊断。

EasyTier 对 Direct/Relay/IPv6 UDP 缺乏证据时应显示 `null`/不可观测，而不是 false。UniFi 在关联
WAN、风扇、端口或静态能力前必须先核对设备/接口 identity。

## 备份、重启与回滚

修改 Server 前，私有备份并校验准确 state 文件及其 `~` 备份、配置/Registry revision 和旧不可变
image digest。受控 Server restart 必须保留 persistence，并在收到自然 report 后才宣布 freshness
恢复。

state 的 `version: 2` 不是通用降级承诺。新的 collection-diagnostics state 可由当前 Server
读取，而 exact pre-change 2.7 Server 可能将受影响数据保留为 corrupt orphan。回滚需要匹配的旧
Server/Client image、配置和升级前 state：先停新 Client 保证单 writer，再恢复旧 Server state 后
启动旧 Server。
