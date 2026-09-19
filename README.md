# HardwareStatus

[English](README_EN.md) · [中文文档](docs/zh-CN/README.md) · [English docs](docs/README.md) · [GitHub](https://github.com/404404/HardwareStatus)

HardwareStatus 是一个自托管、多设备、只读的状态与硬件观测系统。Python
Client 在主机边界采集经过显式授权的观测；Go Server 严格校验、持久化并生成
唯一的 `/json/stats.json` 投影；浏览器从该投影展示主机、硬件、Docker、Hermes、
Lucky、EasyTier、UniFi 与组件诊断。

> **命名兼容性**：GitHub 仓库与公开文档名称为 **HardwareStatus**。为了不破坏
> 已部署环境，当前二进制 `serverstatus`、`HERMESSTATUS_*` 环境变量、
> `/etc/hermesstatus` 与 `/run/secrets/hermesstatus` 路径，以及
> `ghcr.io/404404/hermesstatus-server` / `hermesstatus-client` 镜像包名保持不变。
> 这些是兼容接口，不是应替换成新字符串的配置项。

## 能力与边界

- **设备身份**：Device v2 使用 Registry、每设备 token digest、TLS、重放/冲突
  检查和服务端生命周期时钟。Registry `display_name` 是 UI 名称的权威来源。
- **主机与硬件**：CPU、内存、系统、文件系统、物理磁盘、SMART、温度和容器摘要。
  磁盘与挂载点都必须被显式授权；不会扫描整个宿主机根目录或完整 `/dev`。
- **可选本地组件**：Hermes、Lucky 与 EasyTier 均采用固定只读输入。未安装、未配置
  或合法空结果与真实采集故障严格区分。
- **UniFi**：Client 通过固定只读 SSH/API 输入采集已配置目标。运行时身份经验证后，
  静态端口、PoE、存储、电源与处理器能力仅来自随镜像固定的 UniFi Catalog；未知
  身份不会获得推测的静态能力。
- **组件诊断**：Server 将当前投影的 freshness、采集质量、硬件健康、字段/资源错误和
  有界截断分开表达。诊断页面是服务端已接收状态的解释，不会执行新的采集或控制操作。

不提供远程命令执行、网络扫描、自动注册、设备管理、风扇/PWM 控制、告警服务、时序
数据库或任意路径/命令配置。

## 数据流

```text
显式授权的主机输入 / Docker / Hermes / Lucky / EasyTier / UniFi
                                ↓
                         Python Client
                                ↓
                 Device v2 HTTPS（或显式 Legacy TCP）
                                ↓
                           Go Server
                                ↓
          /json/stats.json · /api/health · Web UI
```

Server 不读取 Docker socket、Client 原始配置、凭据、EasyTier 原始输出或 UniFi 原始
响应。Client 在边界执行固定 allowlist、长度、类型和秘密过滤；Server 只接受严格的
标准化投影。

## 部署原则

生产与资格验证使用 GitHub CI 构建的不可变镜像引用：

```yaml
image: ghcr.io/404404/hermesstatus-server@sha256:<已批准的 server digest>
image: ghcr.io/404404/hermesstatus-client@sha256:<同一源码 revision 的 client digest>
```

不要以 `latest`、宽泛版本标签或本地 `--build` 替代已经批准的 digest。部署前核验：

1. Server 与 Client OCI revision 相同，并等于目标源码 SHA；Client 的 Catalog revision
   与 bundle SHA 也符合候选记录。
2. Server 配置、Registry、设备凭据引用和持久化状态目录已备份；状态备份与其 `~`
   备份都要计算校验值。
3. 先更新 Server，再对每个 Device v2 identity 停止旧 Client、确认没有 writer，最后
   启动新 Client。旧/新 Client 绝不能同时使用同一 identity/token。

详细 Compose、验证和回滚流程见[部署指南](docs/zh-CN/DEPLOYMENT.md)。默认 Web
地址为 `http://127.0.0.1:8080/`，健康端点为 `/api/health`，投影端点为
`/json/stats.json`。

## 最小权限硬件采集

不要使用 `privileged`、`SYS_ADMIN`、完整 `/dev` 或宿主机根目录。仅映射已经确认的
只读设备和 probe 根路径，例如：

```yaml
cap_add: [SYS_RAWIO]
devices: [/dev/sda:/dev/sda:r]
```

多盘使用统一 Client 配置中的 `collectors.smart.devices` allowlist；文件系统只通过
固定的 `collectors.filesystem.probes` 和只读 bind mount 采集。参见[设备配置](docs/zh-CN/DEVICE_CONFIGURATION.md)
与[硬件监控设计](docs/zh-CN/HARDWARE_MONITORING.md)。

## 文档与验证

- [架构](docs/zh-CN/ARCHITECTURE.md) · [配置](docs/zh-CN/CONFIGURATION.md) · [部署](docs/zh-CN/DEPLOYMENT.md)
- [安全](docs/zh-CN/SECURITY.md) · [运维](docs/zh-CN/OPERATIONS.md) · [开发](docs/zh-CN/DEVELOPMENT.md)
- [Device v2 配置](docs/zh-CN/DEVICE_CONFIGURATION.md) · [统一 Client 配置](docs/UNIFIED_CLIENT_CONFIG.md)
- [EasyTier](docs/zh-CN/EASYTIER_MONITORING.md) · [硬件](docs/zh-CN/HARDWARE_MONITORING.md) · [UniFi](docs/zh-CN/UNIFI_MONITORING.md)

常规检查：

```bash
(cd server && go test ./...)
(cd clients && python3 -m unittest discover)
(cd scripts/tests && python3 -m unittest discover)
node --test web/js/app.test.js
docker compose -f docker-compose-client.yml config --quiet
```

## 许可

[MIT License](LICENSE)
