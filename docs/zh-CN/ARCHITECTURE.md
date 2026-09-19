# 架构

HardwareStatus 是一个只有一份浏览器权威投影的只读监控系统。公开仓库已更名为
HardwareStatus；现有 `hermesstatus` 运行时命名空间仍是兼容边界。

```text
已授权的主机输入 → Python Client → Device v2 HTTPS → Go Server
                                                   ↓
                                         已接受的持久化状态
                                                   ↓
                         /json/stats.json → Web UI 与组件诊断页
```

## 身份、接收与持久化

Device Registry 是 `device_id`、`display_name`、启用状态和协议的权威来源。上报的
hostname 只是观测值，不能重命名 Registry 设备。Device v2 使用 TLS、服务端仅保存
digest 的每设备凭据、重放/冲突检查和服务端生命周期时钟；Legacy TCP 只在显式配置时
保留。

已接受的更新是原子的。非法、过期、冲突或未授权上报不会覆盖最后一次已接受状态。Server
重启恢复的状态可供诊断，但在下一次自然上报被接受前保持 stale。

## 单一投影与独立域

Server 校验 Client extension 后生成所有页面共用的 stats 文档；浏览器不拼接原始 Client
数据，也不单独轮询采集器。当前域包括硬件/OS、Docker、Hermes、Lucky、EasyTier 和已配置
的 UniFi target。

以下信号必须分开解释：

| 信号 | 含义 |
| --- | --- |
| 设备生命周期 | 认证后的 Client 是否按 Server 时钟在线。 |
| freshness | 某个观测是否仍在该采集策略的有效时间内。 |
| 采集质量 | 采集器完成、部分成功、不可用、禁用或未配置。 |
| 硬件/业务健康 | 对磁盘、服务、路由或远端 target 的健康解释。 |
| 诊断 | 解释当前错误或限制的有界、资源级证据。 |

采集成功不等于硬件健康。反之，未配置的可选组件、合法空集合或可信 SMART 属性回退不会
让设备离线。

## 组件诊断

诊断与 freshness 在同一投影时刻生成。它保留严格解码/校验证据，并加入当前域证据；后续
有效观测解决问题时，当前诊断会清除。每项诊断具有稳定的 domain、component、code、可选
field/source/reason 与受影响资源身份，因此不同磁盘、文件系统、profile 或 API endpoint 的
相同错误不会被错误合并。

列表保持有界。Server 同时记录 observed/displayed 数量与截断标记，并优先保留故障证据；UI
显示数量不能被理解为观测总数。

## UniFi 权威边界

Client 仅通过显式 profile 选择固定只读 SSH/API source。profile 选择采集来源，并非硬件
身份。API/SSH 运行时身份必须匹配 `clients/unifi_catalog/` 固定 bundle 中的 verified alias，
才会投影端口、PoE、存储、电源或处理器静态事实。未知或候选 alias 仍可保留有界运行时
观测，但绝不会获得推测的静态能力。

静态端口数据只可按 `(device_id, port_idx)` 与运行时观测关联。WAN、uplink、风扇、存储和
电源观测必须依附于经过验证的设备/接口身份，不能跨设备泄漏。

## 明确不在范围内

HardwareStatus 不是远程 shell、EasyTier/UniFi/Lucky 管理器、自动注册服务、网络扫描器、
告警系统、时序数据库或任意命令/路径执行器。Server 不读取 Docker socket、采集器秘密、
原始 Client 配置或原始远端响应。
