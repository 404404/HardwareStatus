# Canonical Compose contract

New deployments use ServerStatus image packages, container names, variables,
and paths. The source repository URL remains `404404/HardwareStatus`. See the
[rename migration guide](../../docs/NAME_MIGRATION.md) for legacy aliases.

Published deployments set `SERVERSTATUS_SERVER_TAG` and
`SERVERSTATUS_CLIENT_TAG` to the same approved candidate revision. Prefer an
exact image digest in the final Compose service; do not use `latest`, an
unqualified broad version tag, or local qualification tags. Verify the Server
and Client OCI revision before creating either container.

Mount unified Client configuration read-only at the new path. These examples
also mount the same files at the prior fixed paths for a staged migration of
existing configuration documents:

```text
Linux/GK50:  /home/hermes/status/config/client-config.json:/run/secrets/serverstatus/client-config.json:ro
Synology DSM: /volume1/docker/status/config/client-config.json:/run/secrets/serverstatus/client-config.json:ro
Legacy alias: same source mounted at /run/secrets/hermesstatus/client-config.json:ro
```

Mount the Device v2 token separately:

```text
/etc/serverstatus/secrets/device-token:/run/secrets/serverstatus-device-token:ro
Legacy alias: same source mounted at /run/secrets/hermesstatus-device-token:ro
```

The Client needs a private tmpfs:

```text
/run/serverstatus:size=4m,mode=0700,nosuid,nodev,noexec
```

Do not pass collector secrets through environment values or command arguments.
The operator verifies the candidate digest and OCI revision before recreation.
The Synology template preserves host network/PID, read-only rootfs,
no-new-privileges, bounded tmpfs, reviewed read-only Docker socket/DSM version
mounts, and only explicitly approved SMART/data-volume mounts.

Never overlap an old and new Client that share `device.id` and token. Keep the
old image/container and the corresponding Server state backup as rollback
material until the candidate is accepted.
