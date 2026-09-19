# 安全

HardwareStatus 被设计为只读。仓库更名不改变已部署环境的 `hermesstatus` 凭据路径、环境变量或
镜像包名。

## 身份与秘密

Device v2 使用 TLS 和每设备 token；Server 只保存其 digest。Client 从受保护的只读文件读取
token、CA、Lucky token 和 UniFi 凭据。不得将任何 secret 放入源码、参数、环境变量、label、
fixture、日志、状态文档、诊断 reason 或 UI。

## 采集和远端边界

Collector 使用固定 source allowlist 与 argv array，拒绝任意 command、path、host、redirect、
原始配置、credential 和敏感 EasyTier 对象。Lucky 仅 loopback；EasyTier 使用固定只读 CLI 与
loopback RPC；UniFi 使用固定打包的只读 source、严格 host-key checking、受保护的 keyboard-
interactive credential 以及配置时的 API TLS pinning。

任何 collector 都不安装 key、不扫描网络、不修改远端配置、不控制 fan/PWM、不改存储设置，也
不暴露管理 endpoint。host-key 或 TLS verification 失败只是 telemetry error，绝不是弱化验证的
授权。

## 最小权限与数据处理

禁止 privileged container、`SYS_ADMIN`、宽泛 Docker API、完整 `/dev`、`/dev/sg*` 或 host root。
仅授予已审核只读 mount、显式 SMART device mapping 和确有需要的 `SYS_RAWIO`。Server 严格限制
count、string、counter、timestamp 和 enum，丢弃未知敏感字段，并原子应用已接受更新。

诊断有界、资源级且经过 secret filter：保留足够 code/field/source 证据用于安全运维，但不会成为
请求或配置转储。

## 漏洞报告

公开 issue 中不要包含 secret 或真实基础设施标识。通过私有维护者/安全渠道提交最小化、脱敏的
复现材料。
