# HardwareStatus 命名与迁移约定

新开发与新部署的产品身份统一为 HardwareStatus。Compose service 与容器名为
`hardwarestatus-server`、`hardwarestatus-client`；未来 GHCR 包名为
`ghcr.io/404404/hardwarestatus-server`、`ghcr.io/404404/hardwarestatus-client`。
新的 Device v2 部署优先使用 `HARDWARESTATUS_*` 环境变量前缀。

## 保留的兼容接口

以下名称在迁移期仍受支持，但不再作为新资源的默认名称：

- Device v2 的 `HERMESSTATUS_*` 配置输入、旧 Client 构建元数据输入、Server
  Device endpoint 设置与部署别名。新旧前缀同时设置时值必须相同；冲突时
  fail closed。新 Client 镜像只输出 `HARDWARESTATUS_*` 构建元数据与
  `io.hardwarestatus.*` 产品标签。
- `/etc/hermesstatus`、`/run/secrets/hermesstatus`、
  `/run/secrets/hermesstatus-device-token`、`/run/hermesstatus` 等旧容器内路径仍可用。
  新模板使用 HardwareStatus 路径，并保留指向同一宿主机文件的只读旧凭据目标别名。
  既有宿主机目录与 `/var/lib/serverstatus-client` 状态数据保持可用；不会移动或删除宿主机数据。
- `/usr/local/bin/serverstatus` 保留为指向
  `/usr/local/bin/hardwarestatus-server` 的调用符号链接；两个入口的 `--version`
  均输出 canonical `hardwarestatus-server` 元数据。
- 旧 `ghcr.io/404404/hermesstatus-*` 镜像包及其不可变产物。本次不会重打 tag 或重发；
  未核实、也不宣称新的 GHCR 包已存在。
- `X-HermesStatus-Device-ID` Device v2 HTTP header、Go import path
  `github.com/cppla/serverstatus/server`、旧 TCP transport 的 `SERVER`/`PORT`，以及
  Hermes Agent 集成的 `HERMES_*`、`HERMES_STATUS_*`。它们分别属于协议、源码、旧传输
  或第三方集成边界。
- 既有 `service/status-*.service` 与 `status.sh` 作为旧 ServerStatus 安装资料保留；
  新 systemd unit 示例使用 `hardwarestatus-*` 命名。

2.5、2.6、2.7 已发布镜像与 stable tag 保持不变。候选发布 bootstrap 收紧 package 写权限，
并阻止 2.7 pull request 发布。新的 2.8 候选镜像仅使用 canonical package、精确源码 SHA
及 HardwareStatus 身份。意外生成的
`ghcr.io/404404/hermesstatus-server:2.7-83934eb3f692` 与
`ghcr.io/404404/hermesstatus-client:2.7-83934eb3f692` 仅登记待清理审核，本次不删除。
发布 2.8 前仍须核实 GHCR package provisioning 与权限。

## 安全切换流程

Compose service 或 `container_name` 改名可能使旧 service 成为 orphan。未检查旧项目之前
不可直接使用新模板执行 `docker compose up`。对每个 Client identity：

1. 记录旧镜像 digest/revision、Compose project 与渲染配置、mount、device、network/PID/
   security 设置、配置 revision、受保护凭据引用和状态路径。
2. 私有备份并校验配置与 Server 持久化状态（含 `~` 备份），记录 hash、属主和权限。
3. 停止旧 Client，确认已停止且该 identity 的活跃 writer 数为零。不得用同一 token 创建第二个 Client。
4. 按批准结果仅替换 Client image/name；保留原 mount、device、host network/PID、权限和状态路径。
5. 核对唯一 writer、不可变 image digest/revision、零重启，并等待自然采集及接受的新报告。
6. 回滚时先停止新 Client 并确认 writer 为零，再恢复匹配的旧 Server/Client 镜像、Compose/配置、
   升级前状态及其 `~` 备份。除非已验证精确降级，不得让旧 Server 读取新版本写出的状态。

本仓库改名任务不会在 GK50 或 RS820 执行该切换。
