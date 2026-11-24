# HardwareStatus 2.8 候选镜像发布

2.8 候选发布器使用 `workflow_dispatch`，因此 workflow 必须先存在于默认
`2.0` 分支。只能在 `2.0` 上调度，并提供一个输入：同仓库、目标为
`2.0` 的当前非 Draft PR HEAD 完整小写 SHA（或该 PR 已合并的 HEAD）。
源码门禁还要求该 SHA/PR 对应的最新 `CI` pull-request run 成功，且
`contracts`、`go`、`python`、`frontend`、`compose`、`images`、`security`
任务全部成功。workflow 按固定 SHA checkout/build，不跟随可移动分支名。

发布范围严格限定为 `ghcr.io/404404/hardwarestatus-server` 和
`ghcr.io/404404/hardwarestatus-client`，标签为
`2.8-<完整源码 SHA>`。不写入 `latest`、stable、2.5、2.6 或 2.7 标签。
发布前后校验 OCI revision、组件、平台、Catalog V2 revision 与 bundle
SHA256；完成后记录镜像 digest，使用时优先固定 digest。

## Registry 状态与恢复

发布器先认证 GHCR，再分别探测两个镜像的 manifest。只有认证成功后得到
明确的 `MANIFEST_UNKNOWN` 或 `NAME_UNKNOWN` 才视为不存在。认证失败、响应
格式错误、超时、限流或其他 Registry 错误均视为未知并停止发布。

| Server | Client | 处理 |
| --- | --- | --- |
| 不存在 | 不存在 | 发布两侧 |
| 存在且 provenance 完全匹配 | 不存在 | 只发布 Client |
| 不存在 | 存在且 provenance 完全匹配 | 只发布 Server |
| 存在且匹配 | 存在且匹配 | 幂等 no-op |
| 已有 provenance 冲突 | 任意 | fail closed，绝不覆盖 |
| 任意 | 已有 provenance 冲突 | fail closed，绝不覆盖 |
| 状态未知 | 任意 | fail closed |
| 任意 | 状态未知 | fail closed |

若发布中断且只有一侧成功，重试会校验已存在镜像的源码、Catalog 身份、
架构、创建时间和 manifest digest，只构建缺失的一侧，并沿用原创建时间。
若已有镜像错误或无法读取，该标签按终止状态处理；不得删除、替换或手动
重新打标签，应升级到单独审核的恢复决策。

并发组按完整源码 SHA 区分且不取消正在运行的任务。同一候选的重试会串行；
不同源码使用不同完整 SHA 标签。workflow 的“不覆盖”属于应用层策略；
Registry 管理员仍可删除 package version，因此需保存最终 digest，不能把
标签当成 digest 的替代品。

## 人工审批与 Package 权限

只有 `publish` job 获得 `packages: write`，并使用
`hardwarestatus-2.8-candidate-publish` GitHub Environment。首次实际发布前，
仓库管理员必须为该 Environment 配置 required reviewer，并将可部署分支
限制为 `2.0`；仅在 YAML 中声明 Environment 不会自动设置审批规则。

历史 2.5、2.6、2.7 发布器也仅在各自的 `publish` job 授予 package 写权限。
2.7 发布器只允许在 `codex/2.7-*` 分支 push 或该分支手动调度时发布；
pull request 运行绝不发布镜像。

发布 job 使用仓库范围的 `GITHUB_TOKEN` 并仅授予 `packages: write`；镜像
包含指向本仓库的 `org.opencontainers.image.source`，以建立 package 与
workflow 仓库的关联。仓库所有者仍须具有创建 package 的权限。本 bootstrap
任务不进行试推送。

首次创建 package 后，须检查两侧 package 设置及仓库关联。公开 GHCR package
允许匿名拉取；私有 package 则要求每台部署主机另行获得 pull 凭证/访问授权，
不得把凭证写入镜像或源码。Package 可见性和 Actions 访问属于 Registry
设置，不能仅凭 workflow 推断已正确配置。

本 workflow 不创建正式 Release，不改旧 package 名称，不部署容器，也不修改
已有 2.5/2.6/2.7 artifacts。
