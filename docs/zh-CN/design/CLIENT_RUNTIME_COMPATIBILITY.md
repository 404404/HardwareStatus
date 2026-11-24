# Client 运行时兼容性

## 运行时基线

2.8 Client 镜像继续基于 `alpine:3.13`，其系统包提供 Python 3.8。仓库中首次
引入该基础镜像的是提交 `b8baa951`（2026-07-14，“Complete HermesStatus
Release A host data pipeline”）。当时 Dockerfile 注释解释了 `smartmontools`
和 `util-linux` 的用途，但提交说明和现有文档都没有记录选择或固定 Alpine 3.13
的原因，因此不能把它描述为已证实的群晖专属要求。

本次保留现有基础镜像，因为已观察到的问题是应用调用了不兼容的 Python API，并无
证据表明基础镜像本身不足。升级 Alpine 也会改变 Python 运行时/补丁版本、依赖
musl 的包（如 `psutil`）及 `smartmontools`、OpenSSH 等宿主机探测工具，可能影响
DSM 内核探测、SMART transport/输出和挂载设备行为。应另行资格验证，不与本次修复
捆绑。

## 必需检查

`client-runtime` CI job 使用 Python 3.8 运行完整 Client 单元测试，并编译镜像中
复制的全部 Python 源文件。测试覆盖构建元数据别名、Catalog V2、USP-RPS fixture
和 Pro Max 24 PoE 型号解析。

`images` job 构建实际 `linux/amd64` Server/Client 镜像，校验 revision 与 Catalog
标签，记录 Client 镜像内 Python 版本，从镜像加载内嵌 Catalog，并通过正常 Client
entrypoint 向隔离的真实 Server 上报。测试使用生成的测试 token/Device ID，通过已验证
TLS 和仅信任测试代理地址的 proxy 进行；必须收到有效 Device v2 报告、revision 匹配，
且 Client 持续运行、重启次数为零。不会使用生产设备或凭据。

2.8 候选源码门禁要求精确 PR HEAD SHA 对应的 `client-runtime` 和 `images` 均成功。
候选发布仍受 `hardwarestatus-2.8-candidate-publish` GitHub Environment 人工审批保护。
