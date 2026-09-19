# 硬件监控设计

硬件域是有界、故障隔离的观测 pipeline。SMART failure 不得移除 CPU、memory、filesystem、Docker
或其他硬件观测。

## 资源模型

Client 区分物理磁盘与 volume/filesystem。物理磁盘包含 identity、capacity、SMART、temperature 和
power-on hours；filesystem 描述显式配置的 mountpoint、source、type、capacity 与 use。这避免为
DSM RAID、mdraid、LVM 和 device-mapper volume 伪造磁盘归属。

Server diagnostics 使用稳定 resource key 标识受影响 disk 或 filesystem。两个磁盘的相同 error
仍是两条诊断。诊断列表有界但保留 count/truncation 证据，并优先保留 fault。

## SMART 语义

显式 `smart_devices` 配置始终权威。自动发现优先使用合格的 open-device scan evidence，安全
fallback，并按 device path 去重，避免已知 transport 又以空 transport 候选重复出现。不硬编码
NAS vendor、disk model 或 transport type。

优先使用 native SMART return status。若其不可用但 attribute 与 threshold 能提供可信 fallback，
磁盘可上报 `health=passed` 或 `health=failed`、`health_source=attribute_check` 和
`completeness=partial`。native-status limitation 仍可见，但 passed 时本身不降低 hardware/device；
failed 仍是实际 disk health failure。

字段质量 failure 是独立证据。例如 temperature invalid 即使同时有可用 attribute fallback，仍保留
invalid-value diagnostic。有效字段继续可用；兼容保留的单一 error field 若存在，必须确定性选择
primary error，但不能抹掉其他结构化 diagnostic。

不得在合法 failed health 后重 probe 其他 transport，不得添加 `-T permissive`、将 `-x` 改为
`-a` 或弱化 SMART validation 来隐藏错误。

## 最小权限

仅使用显式只读 device mapping 和确有必要的 `SYS_RAWIO`。禁止 privileged、`SYS_ADMIN`、广泛
`/dev`、`/dev/sg*`、host root 或任意 probe path。filesystem 和 DSM identity probe 必须是固定、
窄范围只读 mount。
