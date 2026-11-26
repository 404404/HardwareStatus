# HardwareStatus naming and migration contract

HardwareStatus is the canonical product identity for new work. New Compose
services and container names are `hardwarestatus-server` and
`hardwarestatus-client`; future GHCR packages are
`ghcr.io/404404/hardwarestatus-server` and
`ghcr.io/404404/hardwarestatus-client`. New Device v2 deployments should use
the `HARDWARESTATUS_*` environment prefix.

## Compatibility retained

The following are supported compatibility interfaces, not canonical names:

- `HERMESSTATUS_*` Device v2 configuration inputs, legacy client build-metadata
  inputs, server device endpoint settings, and deployment aliases. Where
  canonical and legacy spellings are both supplied, values must match;
  conflicts fail closed. New Client images emit only `HARDWARESTATUS_*` build
  metadata and `io.hardwarestatus.*` product labels.
- Legacy in-container paths such as `/etc/hermesstatus`,
  `/run/secrets/hermesstatus`, `/run/secrets/hermesstatus-device-token`, and
  `/run/hermesstatus` remain accepted. New templates use HardwareStatus paths
  and retain read-only legacy credential aliases to the same unchanged host
  files. Existing host directories and `/var/lib/serverstatus-client` data
  remain available; no host data is moved or deleted.
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

Existing 2.5, 2.6, and 2.7 published images and stable tags remain untouched.
The candidate workflow bootstrap tightens package-write scope and prevents
2.7 pull-request runs from publishing. New 2.8 candidate publication uses only
the canonical package namespace, exact source SHA, and HardwareStatus identity.
The two unintended tags `ghcr.io/404404/hermesstatus-server:2.7-83934eb3f692`
and `ghcr.io/404404/hermesstatus-client:2.7-83934eb3f692` are recorded for
separate cleanup review; this change does not delete them. GHCR package
provisioning/permissions must be verified before a 2.8 publication.

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
