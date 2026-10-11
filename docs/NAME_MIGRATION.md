# ServerStatus naming migration

The product-facing name is now **ServerStatus**. The source repository remains
[`404404/HardwareStatus`](https://github.com/404404/HardwareStatus); its GitHub
URL is not part of this product rename.

New deployments should use:

- GHCR packages `ghcr.io/404404/serverstatus-server` and
  `ghcr.io/404404/serverstatus-client`;
- Compose containers `serverstatus-server-2x` and
  `serverstatus-client-2x` (the root development Compose uses the shorter
  `serverstatus-server` and `serverstatus-client` names);
- the `SERVERSTATUS_*` configuration prefix;
- `/etc/serverstatus`, `/run/secrets/serverstatus`,
  `/run/secrets/serverstatus-device-token`, and `/run/serverstatus` paths;
- the `X-ServerStatus-Device-ID` Device v2 identity header.

## Compatibility window

New Server and Client builds accept the former `HERMESSTATUS_*` environment
prefix, the former fixed secret/config paths when they remain mounted, and the
former `X-HermesStatus-Device-ID` header. New Clients send both identity header
spellings with the same device ID so they can communicate with an older Server;
new Servers accept either spelling and reject conflicting or duplicate values.
For Client configuration, supplying both environment prefixes with different
values is a fail-closed error. On the Server, a non-empty `SERVERSTATUS_*`
value takes precedence over its legacy alias.

The runtime secret materializer uses `/run/serverstatus` when that tmpfs is
mounted, otherwise it can use the already-mounted `/run/hermesstatus` path.
The default Device v2 token path falls back only to the fixed prior token path
when the new path does not exist. Existing explicit token paths remain subject
to the same regular-file, owner, mode, and size checks.

The browser uses `ServerStatusDashboard` and migrates the selected-device
preference from the old local-storage key. The old JavaScript global remains a
temporary alias for custom integrations.

The old GHCR package names and digests are separate historical artifacts. This
change does not retag or delete them. A newly built candidate is published
under the new package names and must be qualified by its own immutable digest;
do not assume an old tag exists in the new package namespace.

## Controlled migration and rollback

This source change does not deploy to GK50 or RS820. For a later deployment,
record the exact old Server and Client digests, Compose files, config revision,
mounts, and checksummed persistence backup. Upgrade the Server first; it accepts
old Client headers and settings. Then stop the old Client and verify its
Device v2 identity has no writer before starting the matching new Client. Never
run two Clients with the same identity/token concurrently.

Rollback as a matched set: stop the new Client and Server, restore the prior
Server/Client digests and Compose/configuration, restore the pre-upgrade state
file and its backup, then start the old Server before its matching Client. Do
not point an old Server at state written by a newer release. The rename does
not change the JSON payload schema, device IDs, credential digests, TLS policy,
or replay-protection state.
