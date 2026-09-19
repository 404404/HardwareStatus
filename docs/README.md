# HardwareStatus documentation

[中文文档](zh-CN/README.md) · [Repository](https://github.com/404404/HardwareStatus)

These documents describe the current `2.0` main branch after the 2.7 release
and the first collection-diagnostics work merged in PR #37. They describe
current source behavior; they do not announce a new stable release or replace
candidate provenance requirements.

The repository is HardwareStatus. Runtime compatibility names beginning with
`hermesstatus` remain intentionally unchanged; see the root [README](../README_EN.md).

| Document | Purpose |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Components, one-projection data flow, identity, diagnostics, and boundaries. |
| [Configuration](CONFIGURATION.md) | Server, Device v2, unified Client, optional collectors, and compatibility names. |
| [Device configuration](DEVICE_CONFIGURATION.md) | Registry identity, credential files, strict config, and reviewed mounts. |
| [Deployment](DEPLOYMENT.md) | Immutable images, upgrade sequence, verification, persistence, and rollback. |
| [Security](SECURITY.md) | Trust boundaries, secrets, TLS/SSH, and least privilege. |
| [Operations](OPERATIONS.md) | Freshness, diagnostics, backup/recovery, and troubleshooting. |
| [Development](DEVELOPMENT.md) | Checks, documentation expectations, and PR workflow. |
| [EasyTier design](design/EASYTIER_MONITORING.md) | Read-only collection, aggregate/display bounds, and uncertainty. |
| [Hardware design](design/HARDWARE_MONITORING.md) | SMART, filesystems, resource diagnostics, and safe fallbacks. |
| [UniFi design](design/UNIFI_MONITORING.md) | Catalog authority, runtime identity, WAN/port ownership, and read-only transport. |

Keep English and Chinese documents semantically synchronized in one change.
