# 部署

只能部署已记录 candidate 的 GitHub CI 不可变镜像。仓库已更名，但当前已发布包名仍特意保留
`hermesstatus-server` 与 `hermesstatus-client`。

```yaml
image: ghcr.io/404404/hermesstatus-server@sha256:<已批准的-server-digest>
image: ghcr.io/404404/hermesstatus-client@sha256:<已批准的-client-digest>
```

不得改用 `latest`、宽泛版本 tag 或本地 build。任何变更前，确认每个 image 的 OCI revision
等于已批准源码 SHA；含 UniFi 的 Client 还须核对 candidate 记录中的 Catalog revision 与 bundle
hash。

## 准备回滚集合

记录当前 Server/Client digest、Compose/配置 revision、mount、network/PID/security option 和
Device v2 identity。避开并发写入，私有地备份并校验 Server 状态文件及其 `~` 备份。旧 image
和配置要保留到 candidate 被接受之后。

资格环境与生产环境不得共享可写 Server state。保持既有只读 mount、tmpfs、设备 mapping、
TLS/SSH 材料和单 writer 身份约束。

## 标准顺序

1. 不启动容器，先验证渲染后的 Compose。
2. 仅用已批准 image 更新/重建 Server；在旧 Client 仍是唯一 writer 时核对 digest/revision、
   health、dashboard 和 stats。
3. 停止某个 Device v2 identity 的旧 Client，确认该 identity 已无 writer。
4. 仅以匹配的不可变 image 重建该 Client，确认 digest/revision、`restart_count=0` 和唯一 writer。
5. 观察自然 Client report；浏览器刷新或读取 Server 不能算采集周期。核对 online/non-stale、
   已启用组件 freshness 和资源级诊断。

进行受控 Server restart 时，恢复状态在下一次自然 report 被接受前必须显示 stale。不要在实机
上人为制造故障来覆盖某条诊断分支。

## Synology DSM

DSM 通常只需要 Client image。操作员在保留当前配置与状态后，只改既有 Compose service 的
image 引用。保持 host network/PID、只读 rootfs、有界 tmpfs、已审核设备 mapping 和受保护的
token/配置 mount。旧/新 Client 绝不能同时使用同一个 Device v2 token。

`deploy/compose/` 模板是经过审核的起点，不能作为扩大 mount 或权限的理由。

## 回滚

回滚是一套有版本关联的材料，不只是停止新 Client：

1. 停止新 Client，并确认 identity 没有 writer。
2. 停止新 Server。
3. 恢复匹配的旧 Server/Client image、Compose/配置和升级前 state 及其 `~` 备份。
4. 验证 Compose，先启动旧 Server，再启动匹配的旧 Client。
5. 核对唯一 writer、fresh accepted report 和预期诊断。

状态格式仍使用 `version: 2`，但该字符串不是降级兼容承诺。2.7 之后首次写入的 collection-
diagnostics 状态不是 exact pre-change 2.7 Server 的已资格验证输入。不得清空 persistence 或
replay protection 强行降级；必须使用已捕获的升级前 state。
