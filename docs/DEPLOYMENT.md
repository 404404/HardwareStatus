# Deployment

Deploy only immutable GitHub-CI images from a recorded candidate. The currently
published package names intentionally remain `hermesstatus-server` and
`hermesstatus-client` after the repository rename.

```yaml
image: ghcr.io/404404/hermesstatus-server@sha256:<approved-server-digest>
image: ghcr.io/404404/hermesstatus-client@sha256:<approved-client-digest>
```

Do not replace these with `latest`, a broad version tag, or a local build.
Before any change, verify each image OCI revision equals the approved source
SHA. For a Client with UniFi support, also verify the recorded Catalog revision
and bundle hash.

## Prepare a rollback set

Record the current Server/Client image digests, Compose/configuration revision,
mounts, network/PID/security options, and Device v2 identities. Make a private,
checksummed copy of the Server state file and its `~` backup while avoiding a
concurrent write. Retain the old images and configuration until the candidate
is accepted.

Do not share writable Server state between qualification and production
projects. Preserve existing read-only mounts, tmpfs, device mappings, TLS/SSH
material, and the single-writer identity contract.

## Normal sequence

1. Validate the rendered Compose configuration without starting containers.
2. Update/recreate the Server using only the approved image reference; verify
   image digest/revision, health, dashboard, and stats while the old Client
   remains the sole writer.
3. Stop the old Client for one Device v2 identity and confirm no Client writer
   remains for that identity.
4. Recreate only that Client with the matching immutable image. Confirm the
   intended digest/revision, `restart_count=0`, and exactly one writer.
5. Observe natural Client reports; do not count browser refreshes or Server
   reads as collection cycles. Verify online/non-stale lifecycle, enabled
   component freshness, and relevant resource diagnostics.

For a controlled Server restart, verify restored state is diagnosed as stale
until a natural new report is accepted. Do not manufacture failures on live
hardware merely to exercise a diagnostic branch.

## Synology DSM

The DSM host normally needs only the Client image. The operator edits only the
image reference in the existing Compose service after preserving its current
configuration and state. Keep host network/PID mode, read-only rootfs, bounded
tmpfs, reviewed device mappings, and protected token/configuration mounts. Do
not run an old and new Client concurrently with the same Device v2 token.

Use the templates in `deploy/compose/` as a reviewed starting point, not as a
reason to broaden mounts or privileges.

## Rollback

Rollback is a versioned set, not simply stopping the new Client:

1. Stop the newer Client and confirm the identity has no writer.
2. Stop the newer Server.
3. Restore the matching prior Server/Client images, Compose/configuration, and
   the pre-upgrade state plus its `~` backup.
4. Validate Compose, start the prior Server, then start the matching Client.
5. Confirm one writer, fresh accepted reports, and expected diagnostics.

The state format still uses `version: 2`, but that string is not a downgrade
guarantee. The first collection-diagnostics state written after 2.7 is not a
qualified input for an exact pre-change 2.7 Server. Never clear persistence or
replay protection to force a downgrade; use the captured pre-upgrade state.
