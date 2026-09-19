# HardwareStatus 文档

[English documentation](../README.md) · [仓库](https://github.com/404404/HardwareStatus)

本文档描述 `2.0` 当前主线：包含已发布的 2.7 功能以及 PR #37 合入的第一轮采集诊断
改进。它们说明当前源码行为，不代表新的稳定版发布，也不能替代候选镜像 provenance
要求。

仓库公开名称为 HardwareStatus。为保证现有部署兼容，所有以 `hermesstatus` 开头的运行时
名称仍保持不变，详见根目录 [README](../../README.md)。

| 文档 | 内容 |
| --- | --- |
| [架构](ARCHITECTURE.md) | 组件、单一投影数据流、身份、诊断与边界。 |
| [配置](CONFIGURATION.md) | Server、Device v2、统一 Client、可选采集器与兼容名称。 |
| [设备配置](DEVICE_CONFIGURATION.md) | Registry 身份、凭据文件、严格配置与已审核挂载。 |
| [部署](DEPLOYMENT.md) | 不可变镜像、升级顺序、验证、持久化与回滚。 |
| [安全](SECURITY.md) | 信任边界、秘密、TLS/SSH 与最小权限。 |
| [运维](OPERATIONS.md) | freshness、诊断、备份恢复与排障。 |
| [开发](DEVELOPMENT.md) | 检查、文档要求与 PR 流程。 |
| [EasyTier 设计](EASYTIER_MONITORING.md) | 只读采集、汇总/展示上限与不确定性。 |
| [硬件设计](HARDWARE_MONITORING.md) | SMART、文件系统、资源诊断与安全回退。 |
| [UniFi 设计](UNIFI_MONITORING.md) | Catalog 权威性、运行时身份、WAN/端口归属与只读传输。 |

同一次文档更新中应保持中英文语义同步。
