# Configuration

HardwareStatus configuration is explicit and fail-closed. The public project
name is HardwareStatus; compatibility paths and variables such as
`HERMESSTATUS_CONFIG_FILE` remain unchanged.

## Server and Device Registry

The Server needs a Device Registry, a digest-only credential directory, and a
persistent state path. Keep registry/configuration files read-only in the
container and state writable only at its dedicated data path. Validate the
device configuration before start:

```sh
serverstatus --validate-device-config \
  --device-registry /absolute/path/devices.json \
  --device-credentials /absolute/path/credentials.d \
  --legacy-device-mapping /absolute/path/legacy-device-mapping.json
```

Use a separate Device v2 identity and token for every Client. Registry display
names are authoritative. Do not put device tokens, Server admin tokens, or CA
private material in the repository, environment, command line, or status
document.

## Unified Client configuration

New deployments use the strict JSON document selected by
`HERMESSTATUS_CONFIG_FILE`, conventionally mounted read-only at
`/run/secrets/hermesstatus/client-config.json`. The Device v2 token stays in a
separate read-only file at `/run/secrets/hermesstatus-device-token`.

The document has `schema_version: 1` and explicit `server`, `device`,
`collection`, and `collectors` sections. Unknown fields, unknown collector
sources, arbitrary command fields, and arbitrary probe paths are rejected.
Legacy `client-v2.json` is retained only for planned rollback compatibility;
do not mix its authority with a unified configuration in one Client.

Use root-owned regular files with mode `0600` (or a stricter documented mode)
and read-only mounts. Collector secrets materialize only into the Client's
private `/run/hermesstatus` tmpfs; they never belong in environment values,
arguments, telemetry, logs, fixtures, or UI text.

## Hardware and Docker

Hardware collection needs explicit device and filesystem allowlists. Map an
individual approved disk read-only and grant `SYS_RAWIO` only when SMART needs
it. Do not use `privileged`, `SYS_ADMIN`, complete `/dev`, `/dev/sg*`, or host
root mounts. Filesystem probes must use fixed probe paths under reviewed
read-only bind mounts.

A read-only Docker socket mount is not sufficient security by itself. The
Client is constrained to its fixed read-only Docker query set; never expose a
general Docker API or Docker CLI configuration field.

## Optional collectors

- **Hermes**: optional profile observation; `not_installed` is not a device
  failure.
- **Lucky**: fixed loopback HTTP(S) target and file-backed token. No arbitrary
  URL, redirect, or token-in-environment support.
- **EasyTier**: fixed read-only CLI path and loopback RPC policy. Administrative
  expectations diagnose observed state; they do not authenticate or register a
  device.
- **UniFi**: explicit enabled state, profile, fixed target/SSH/API policy,
  protected password/API-key/known-hosts files, and TLS pinning when API is
  enabled. A profile never grants an arbitrary command, host, path, or static
  hardware capability.

See [Unified Client configuration](UNIFIED_CLIENT_CONFIG.md) and
[Device configuration](DEVICE_CONFIGURATION.md) for examples and mount rules.
