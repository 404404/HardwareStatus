# HardwareStatus naming and migration contract

HardwareStatus is the canonical product identity for new work. New Compose
services and container names are `hardwarestatus-server` and
`hardwarestatus-client`; future GHCR packages are
`ghcr.io/404404/hardwarestatus-server` and
`ghcr.io/404404/hardwarestatus-client`. New Device v2 deployments should use
the `HARDWARESTATUS_*` environment prefix.

## Compatibility retained

The following are supported compatibility interfaces, not canonical names:

- `HERMESSTATUS_*` Device v2 settings, client build metadata, server device
  endpoint settings, and deployment metadata. Where a canonical and legacy
  spelling are both supplied, values must match; conflicts fail closed.
- `/etc/hermesstatus`, `/run/secrets/hermesstatus`,
  `/run/secrets/hermesstatus-device-token`, `/run/hermesstatus`,
  `/var/lib/serverstatus-client`, and existing host directories. No path is
  renamed or copied implicitly.
- `/usr/local/bin/serverstatus`, retained as an invocation symlink to the
  canonical `/usr/local/bin/hardwarestatus-server`. Both invocation paths emit
  the canonical `hardwarestatus-server` version metadata.
- The old `ghcr.io/404404/hermesstatus-*` packages and their immutable
  artifacts. This change neither retags nor republishes them. Availability of
  the new GHCR packages has not been verified or assumed.
- The `X-HermesStatus-Device-ID` Device v2 HTTP header, Go import path
  `github.com/cppla/serverstatus/server`, `SERVER`/`PORT` legacy TCP settings,
  and the Hermes Agent integration (`HERMES_*`, `HERMES_STATUS_*`). These are
  protocol, source, legacy-transport, or third-party integration contracts.
- Existing `service/status-*.service` units and `status.sh` are retained as
  legacy ServerStatus installation artifacts. New systemd unit examples use
  `hardwarestatus-*` naming.

Historical workflows for 2.5, 2.6, and 2.7 remain unchanged so their published
provenance is not rewritten. New candidate publication is defined separately
and uses the canonical package namespace, an exact source SHA, and immutable
candidate tags. Package provisioning/permissions must be confirmed in GHCR
before a publication can succeed.

## Safe deployment cutover

Changing a Compose service or `container_name` can leave an old service
orphaned. It is not safe to run `docker compose up` with the new template
before checking the old project. For each Client identity:

1. Record old image digest/revision, Compose project and rendered config,
   mounts, devices, network/PID/security options, configuration revision,
   protected credentials references, and state paths.
2. Make and verify private backups of configuration and persistent Server
   state (including its `~` backup), with hashes and ownership/mode recorded.
3. Stop the old Client; verify it is stopped and that the identity has zero
   active writers. Do not create a second Client with the same token.
4. Replace only the Client image/name as approved, preserving mounts,
   devices, host networking/PID settings, privileges, and persistent paths.
5. Verify exactly one writer, exact immutable image digest/revision, zero
   restarts, and fresh naturally collected/accepted reports.
6. For rollback, stop the new Client first and verify zero writers. Restore
   the matching old Server/Client images, Compose/configuration and the
   pre-upgrade state plus `~` backup. Do not make an old Server read a state
   written by a newer Server unless that exact downgrade has been qualified.

This repository change does not execute this procedure on GK50 or RS820.
