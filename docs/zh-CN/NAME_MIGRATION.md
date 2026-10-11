# ServerStatus 更名迁移

当前产品名为 **ServerStatus**。源码仓库仍是
[`404404/HardwareStatus`](https://github.com/404404/HardwareStatus)；GitHub 仓库地址不属于本次产品更名。

新部署统一使用：

- GHCR 包 `ghcr.io/404404/serverstatus-server` 与
  `ghcr.io/404404/serverstatus-client`；
- Compose 容器 `serverstatus-server-2x` 与 `serverstatus-client-2x`（根目录开发 Compose 使用较短的
  `serverstatus-server` 和 `serverstatus-client`）；
- `SERVERSTATUS_*` 配置变量前缀；
- `/etc/serverstatus`、`/run/secrets/serverstatus`、
  `/run/secrets/serverstatus-device-token` 和 `/run/serverstatus` 路径；
- Device v2 身份头 `X-ServerStatus-Device-ID`。

## 兼容窗口

新 Server 和 Client 仍接受旧 `HERMESSTATUS_*` 环境变量前缀、仍被挂载的旧固定配置/秘密路径以及旧
`X-HermesStatus-Device-ID` 身份头。新 Client 会同时发送两个身份头且 device ID 相同，因此可连接尚未升级的
旧 Server；新 Server 可接受任一身份头，并拒绝冲突或重复值。Client 配置若同时提供两个前缀且值不同，启动会
fail-closed。Server 在新变量非空时优先使用 `SERVERSTATUS_*`，否则才回退旧别名。

秘密物化目录在 `/run/serverstatus` tmpfs 已挂载时优先使用它，否则使用已挂载的旧 `/run/hermesstatus`。
默认 Device v2 token 路径只有在新路径不存在时才回退到固定旧 token 路径；显式 token 路径继续执行相同的常规
文件、owner、权限和长度检查。

浏览器全局对象使用 `ServerStatusDashboard`，并会把已选设备偏好从旧 local-storage key 迁移过来。为兼容自定义
集成，旧 JavaScript 全局对象暂时保留为 alias。

旧 GHCR 包名和 digest 是独立历史制品。本次更名不重新打标签或删除旧镜像。新候选会发布到新包名下，必须按
自己的不可变 digest 重新资格验证；不要假设旧 tag 已存在于新的包命名空间。

## 受控迁移与回滚

本次源码修改不会部署到 GK50 或 RS820。后续部署前记录旧 Server/Client 的精确 digest、Compose 文件、配置
revision、mount，以及带校验值的持久化状态备份。先更新 Server；新 Server 可接受旧 Client 的身份头和设置。然后
停止旧 Client 并确认该 Device v2 identity 已无 writer，才启动匹配的新 Client。相同 identity/token 绝不能由两个
Client 同时上报。

回滚必须作为一组执行：停止新 Client 和 Server，恢复成套的旧 Server/Client digest 与 Compose/配置，恢复升级前
状态文件及其备份，再先启动旧 Server、后启动匹配 Client。不得让旧 Server 读取新版本写出的状态。此次更名不改
JSON payload schema、device ID、credential digest、TLS 策略或 replay protection 状态。
