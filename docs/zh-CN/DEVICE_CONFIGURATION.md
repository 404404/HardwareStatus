# 设备配置

Device v2 配置用于建立身份和最小权限采集，不是远程控制配置格式。仓库名称为
HardwareStatus，而本文中的 `hermesstatus` 容器路径是刻意保留的兼容路径。

## 路径与挂载

统一 Client 配置的标准路径：

| 主机 | 主机路径 | 容器路径 |
| --- | --- | --- |
| Linux/GK50 | `/home/hermes/status/config/client-config.json` | `/run/secrets/hermesstatus/client-config.json` |
| Synology DSM | `/volume1/docker/status/config/client-config.json` | `/run/secrets/hermesstatus/client-config.json` |

Device v2 token 必须单独挂载到 `/run/secrets/hermesstatus-device-token`。配置、token、CA、
UniFi password/API-key/known_hosts 和 Lucky token 都应为 root-owned、权限受限的常规文件并
只读挂载；诊断时不得输出文件内容。

## 身份与传输

Server Registry 拥有 device ID、浏览器 display name、启用状态和 credential digest。每个活动
Client 使用一个 identity/token；配置 HTTPS Server URL、TLS verification、必要时的 CA 文件和
有界 connect/read timeout。hostname、Client 配置 display string 或远端观测名称都不能覆盖
Registry display name。

严格 unified schema 是首选格式。Legacy 配置只应作为准确的 rollback 材料保留；不得启动两个
配置或两个容器来上报同一设备。

## 已审核的硬件访问

每个物理 SMART 设备和 filesystem probe 都必须显式授权。磁盘需要相应的只读 `devices:`
mapping；文件系统 probe 只需要它实际使用的窄范围只读 host path。禁止挂载所有磁盘、宿主机
根目录、广泛 `/proc` 或任意数据目录。

显式 SMART device 条目始终优先。自动发现有界并使用合格 transport 证据，不硬编码 Synology、
磁盘型号或 transport。不能在真实字段非法或 health failed 后重试其他 transport 来寻找 passed。

## 可选集成

每个 collector 必须显式启用。禁用 collector 在组件诊断中显示“未配置”，不是采集错误。
Hermes/Lucky/EasyTier/UniFi 的可选故障仅属于各自 domain，不会重命名、去认证或让宿主 Device
v2 Client 离线。

UniFi 的 profile、target、credential file、严格 `known_hosts`、可选 API-key file 和 TLS pin 都
是有界字段。profile 只选择固定 source；经过验证的 Catalog 身份控制静态能力。任何字段都不能
增加远程命令、任意路径或任意 controller URL。

## 预检清单

1. 部署前验证 Registry 与 Client JSON。
2. 不读取秘密内容，核对 owner、mode、regular-file 状态和只读 mount。
3. 核对每个 identity 只有一个 Device v2 writer。
4. 固定已批准的 Server/Client digest，并记录 OCI revision。
5. 确认下一次自然 report 已接受、fresh 且归属正确的 Registry 设备。
