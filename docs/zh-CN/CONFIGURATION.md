# 配置

HardwareStatus 配置显式且 fail-closed。公开项目名称为 HardwareStatus；
`HERMESSTATUS_CONFIG_FILE` 等兼容路径和变量保持不变。

## Server 与 Device Registry

Server 需要 Device Registry、只保存凭据 digest 的目录和持久化状态路径。Registry/配置文件
应在容器中只读，状态只能写入专用数据路径。启动前执行：

```sh
serverstatus --validate-device-config \
  --device-registry /absolute/path/devices.json \
  --device-credentials /absolute/path/credentials.d \
  --legacy-device-mapping /absolute/path/legacy-device-mapping.json
```

每个 Client 必须使用独立 Device v2 identity/token，Registry display name 是权威名称。不得把
Device token、Server admin token 或 CA 私钥写入仓库、环境变量、命令行或状态文档。

## 统一 Client 配置

新部署使用由 `HERMESSTATUS_CONFIG_FILE` 选择的严格 JSON，惯例只读挂载到
`/run/secrets/hermesstatus/client-config.json`。Device v2 token 单独只读挂载到
`/run/secrets/hermesstatus-device-token`。

文档使用 `schema_version: 1`，并显式声明 `server`、`device`、`collection` 与
`collectors`。未知字段、未知采集 source、任意命令字段和任意 probe path 都会被拒绝。Legacy
`client-v2.json` 仅用于有计划的回滚，不应与 unified 配置混用。

使用 root-owned、`0600`（或更严格）常规文件和只读挂载。采集器秘密只在 Client 私有
`/run/hermesstatus` tmpfs 中短暂 materialize，不得出现在环境变量、参数、遥测、日志、fixture
或 UI。

## 硬件与 Docker

硬件采集需要显式设备和文件系统 allowlist。仅只读映射已批准磁盘，并且只在 SMART 必需时
授予 `SYS_RAWIO`。禁止 `privileged`、`SYS_ADMIN`、完整 `/dev`、`/dev/sg*` 或宿主机根目录
挂载。文件系统 probe 只能使用经过审核的只读 bind mount 下固定路径。

Docker socket 只读挂载本身并不够；Client 的实现限制为固定只读 Docker 查询，不得暴露通用
Docker API 或 Docker CLI 配置字段。

## 可选采集器

- **Hermes**：可选 profile 观测；`not_installed` 不是设备故障。
- **Lucky**：固定 loopback HTTP(S) target 与文件 token；不支持任意 URL、redirect 或环境变量 token。
- **EasyTier**：固定只读 CLI 与 loopback RPC 策略；管理预期只诊断观测结果，不认证或注册设备。
- **UniFi**：显式启用状态、profile、固定 target/SSH/API 策略、受保护的 password/API-key/
  known_hosts 文件及 API TLS pin。profile 不会授予任意命令、host、path 或静态硬件能力。

示例和挂载规则见[统一 Client 配置](../UNIFIED_CLIENT_CONFIG.md)与[设备配置](DEVICE_CONFIGURATION.md)。
