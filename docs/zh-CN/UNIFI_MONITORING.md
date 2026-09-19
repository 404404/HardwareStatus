# UniFi 监控设计

UniFi 是 profile 驱动的只读远端观测域；不是 controller manager、设备发现服务、资产数据库、
remote shell 或配置通道。

```text
固定 symbolic source → 有界 SSH/API 观测 → 运行时 identity
       → verified frozen Catalog alias → 静态能力 + 运行时 telemetry
       → Device v2 → Server → /json/stats.json → UniFi 与组件诊断页
```

## 权威性与归属

`clients/unifi_catalog/` 中随镜像固定的 deterministic bundle 是已维护静态硬件事实的唯一权威。
collection profile 只选择固定 source，不是硬件 identity。API/SSH identity 必须通过 verified Catalog
alias resolve，才可投影静态 port、connector、PoE、storage、power 或 processor 数据。未知/候选
identity 仍可保留运行时观测，但不会获得推测静态事实。

物理端口归属键为 `(device_id, port_idx)`。运行时 port record、static row、WAN、uplink、fan、
storage 和 power 都必须附着于它们所属的 verified device/interface。numeric management-IP 排序独立
于 physical port 排序。latest speed-test 只能附着于显式合格的 WAN identity，不能成为 link speed。

## 能力与观测语义

`supported`、`present` 和 `observed` 相互独立。unsupported storage 或 power telemetry 应隐藏，
而非渲染为空 failure；supported 但未安装的介质仍显示为未安装。静态 hardware capacity 不能被
mounted filesystem usable capacity 覆盖。

运行时 fan RPM 是观测，不是 physical-fan fault 证明。零 RPM 可为 `observed_zero_rpm`；缺失输入
为 `not_observed`。物理能力以 verified Catalog 或已资格验证的 evidence 为准；不读取 fan/PWM
或 storage control path 用于控制，更不会写入。

PoE column visibility 和 maximum port speed 都是静态能力决策。运行时缺失不是非 PoE 证明，协商
速度也不是硬件 maximum。

## 失败与安全边界

host-key、authentication、timeout、TLS、transport 和 parsing failure 会在有旧快照时保留它、标记
该 UniFi domain stale，并展示有界安全 error；不会改变 collector host 的 Device v2 identity 或
无关 domain health。有效观测恢复后，当前 UniFi error/stale 会清除。

source 是代码侧 symbolic ID。transport 使用固定 argv、有界 output、timeout、严格 known-host
verification、受保护 file-backed credential 和 API TLS pinning。remote command、任意 path、原始
response、私有配置和 credential 都不会进入 persistence 或 UI。
