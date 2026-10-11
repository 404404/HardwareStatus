# Unified Client configuration

This configuration belongs to the ServerStatus product in the
`404404/HardwareStatus` source repository. New deployments use the current
`SERVERSTATUS_*` names; explicit legacy aliases remain available during
migration.

The Client reads one JSON document at SERVERSTATUS_CONFIG_FILE (canonical
container path /run/secrets/serverstatus/client-config.json). The document
uses schema_version: 1, rejects unknown fields, and names every collector
explicitly. The Device v2 token remains a separate read-only mount at
/run/secrets/serverstatus-device-token.

Collector credentials may be present only in the root-owned configuration file.
At startup the Client validates the document and materializes Lucky and UniFi
credentials into private ephemeral files below /run/serverstatus; no secret is
placed in an environment variable, argument list, status payload, or log.

Profiles contain symbolic, fixed sources only. Arbitrary commands, paths,
containers, RPC endpoints, and remote hosts are rejected. Keep the config file
root:root and mode 0600 and mount it read-only. Use a tmpfs at /run/serverstatus
(mode 0700, nosuid,nodev,noexec) for materialized credentials.

The legacy client-v2.json schema remains accepted for rollback compatibility;
new deployments should use this unified document.

Collector support is platform-specific: `linux` and `synology` are the current
host-collected targets; `macos` and `windows` remain schema-compatible but do
not imply complete parity for SMART, Docker, DSM or UniFi sources. Configuration
enum support and collector implementation coverage are separate concerns.

Canonical host locations:

- GK50/Linux: `/home/hermes/status/config/client-config.json`
- Synology DSM: `/volume1/docker/status/config/client-config.json`

Both locations mount read-only at `/run/secrets/serverstatus/client-config.json`.
