# Canonical Compose contract

The repository is HardwareStatus. Existing Compose variable names, container
names, mount paths, and GHCR packages beginning with `hermesstatus` are
compatibility contracts and remain unchanged.

Published deployments set `HERMESSTATUS_SERVER_TAG` and
`HERMESSTATUS_CLIENT_TAG` to the same approved candidate revision. Prefer an
exact image digest in the final Compose service; do not use `latest`, an
unqualified broad version tag, or local qualification tags. Verify the Server
and Client OCI revision before creating either container.

Mount unified Client configuration read-only as:

```text
Linux/GK50:  /home/hermes/status/config/client-config.json:/run/secrets/hermesstatus/client-config.json:ro
Synology DSM: /volume1/docker/status/config/client-config.json:/run/secrets/hermesstatus/client-config.json:ro
```

Mount the Device v2 token separately:

```text
/etc/hermesstatus/secrets/device-token:/run/secrets/hermesstatus-device-token:ro
```

The Client needs a private tmpfs:

```text
/run/hermesstatus:size=4m,mode=0700,nosuid,nodev,noexec
```

Do not pass collector secrets through environment values or command arguments.
The operator verifies the candidate digest and OCI revision before recreation.
The Synology template preserves host network/PID, read-only rootfs,
no-new-privileges, bounded tmpfs, reviewed read-only Docker socket/DSM version
mounts, and only explicitly approved SMART/data-volume mounts.

Never overlap an old and new Client that share `device.id` and token. Keep the
old image/container and the corresponding Server state backup as rollback
material until the candidate is accepted.
