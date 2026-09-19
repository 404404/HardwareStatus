# HardwareStatus

[中文](README.md) · [English docs](docs/README.md) · [中文文档](docs/zh-CN/README.md) · [GitHub](https://github.com/404404/HardwareStatus)

HardwareStatus is a self-hosted, multi-device, read-only status and hardware
observability system. The Python Client collects explicitly authorized
observations at the host boundary; the Go Server strictly validates, persists,
and produces the single `/json/stats.json` projection; the browser renders
host, hardware, Docker, Hermes, Lucky, EasyTier, UniFi, and component diagnostics
from that projection.

> **Naming compatibility:** the GitHub repository and public documentation are
> named **HardwareStatus**. Existing runtime interfaces remain unchanged:
> `serverstatus`, `HERMESSTATUS_*`, `/etc/hermesstatus`,
> `/run/secrets/hermesstatus`, and the
> `ghcr.io/404404/hermesstatus-server` / `hermesstatus-client` packages. They
> are compatibility contracts for deployed installations, not strings to replace.

## Capabilities and boundaries

- **Device identity** — Device v2 uses a Registry, per-device token digest,
  TLS, replay/conflict checks, and a Server lifecycle clock. Registry
  `display_name` is authoritative for the UI.
- **Host and hardware** — CPU, memory, operating system, filesystems, physical
  disks, SMART, temperatures, and bounded container summaries. Every disk and
  mountpoint is explicitly authorized; the Client never scans host `/` or the
  complete `/dev` tree.
- **Optional local components** — Hermes, Lucky, and EasyTier use fixed,
  read-only inputs. Not-installed, not-configured, and valid empty observations
  are distinct from collection failures.
- **UniFi** — the Client uses fixed read-only SSH/API inputs for configured
  targets. After verified runtime identity, static ports, PoE, storage, power,
  and processor capabilities come only from the frozen UniFi Catalog. Unknown
  identity never gains inferred static capability.
- **Component diagnostics** — the Server separates current freshness,
  collection quality, hardware health, field/resource errors, and bounded
  truncation. The Diagnostics tab explains Server-received state; it neither
  triggers collection nor controls a component.

There is no remote command execution, network scanning, automatic registration,
device management, fan/PWM control, alerting service, time-series database, or
arbitrary command/path configuration.

## Data flow

```text
authorized host inputs / Docker / Hermes / Lucky / EasyTier / UniFi
                                ↓
                         Python Client
                                ↓
                Device v2 HTTPS (or explicit Legacy TCP)
                                ↓
                           Go Server
                                ↓
          /json/stats.json · /api/health · Web UI
```

The Server never reads a Docker socket, Client raw configuration, credentials,
raw EasyTier output, or raw UniFi responses. The Client applies fixed
allowlists, bounds, type checks, and secret filtering; the Server accepts only
strict normalized projections.

## Deployment principle

Production and qualification use GitHub-CI-built immutable image references:

```yaml
image: ghcr.io/404404/hermesstatus-server@sha256:<approved-server-digest>
image: ghcr.io/404404/hermesstatus-client@sha256:<client-digest-from-the-same-source-revision>
```

Do not substitute `latest`, a broad version tag, or local `--build` for an
approved digest. Before deployment verify that:

1. Server and Client OCI revisions match each other and the intended source
   SHA; the Client Catalog revision and bundle SHA match the candidate record.
2. Server configuration, Registry, credential references, and persistent state
   (including its `~` backup) have private, checksummed backups.
3. The Server is updated first. For each Device v2 identity, stop the old
   Client, confirm no writer remains, then start the new Client. Old and new
   Clients must never share an identity/token concurrently.

See the [deployment guide](docs/DEPLOYMENT.md) for Compose, verification, and
rollback. The default web address is `http://127.0.0.1:8080/`; health is
`/api/health`; the stats projection is `/json/stats.json`.

## Least-privilege hardware collection

Do not use `privileged`, `SYS_ADMIN`, all of `/dev`, or the host root. Map only
confirmed read-only devices and probe roots, for example:

```yaml
cap_add: [SYS_RAWIO]
devices: [/dev/sda:/dev/sda:r]
```

Use the unified Client `collectors.smart.devices` allowlist for multiple disks,
and fixed `collectors.filesystem.probes` with read-only bind mounts for
filesystems. See the [Device v2 guide](docs/DEVICE_CONFIGURATION.md) and
[hardware-monitoring design](docs/design/HARDWARE_MONITORING.md).

## Documentation and checks

- [Architecture](docs/ARCHITECTURE.md) · [Configuration](docs/CONFIGURATION.md) · [Deployment](docs/DEPLOYMENT.md)
- [Security](docs/SECURITY.md) · [Operations](docs/OPERATIONS.md) · [Development](docs/DEVELOPMENT.md)
- [Device v2 configuration](docs/DEVICE_CONFIGURATION.md) · [Unified Client configuration](docs/UNIFIED_CLIENT_CONFIG.md)
- [EasyTier](docs/design/EASYTIER_MONITORING.md) · [Hardware](docs/design/HARDWARE_MONITORING.md) · [UniFi](docs/design/UNIFI_MONITORING.md)

```bash
(cd server && go test ./...)
(cd clients && python3 -m unittest discover)
(cd scripts/tests && python3 -m unittest discover)
node --test web/js/app.test.js
docker compose -f docker-compose-client.yml config --quiet
```

## License

[MIT License](LICENSE)
