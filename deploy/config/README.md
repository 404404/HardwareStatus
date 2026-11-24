# Unified Client configuration

This is the HardwareStatus public project. New templates use
`HARDWARESTATUS_CONFIG_FILE`; `HERMESSTATUS_CONFIG_FILE` remains an accepted
alias. Supplying both with different paths fails closed. New templates use
HardwareStatus container paths and retain read-only old-path aliases for
existing config documents.

The Client reads one JSON document selected by `HARDWARESTATUS_CONFIG_FILE`
(legacy alias `HERMESSTATUS_CONFIG_FILE`), conventionally mounted at
`/run/secrets/hardwarestatus/client-config.json`. The document
uses schema_version: 1, rejects unknown fields, and names every collector
explicitly. The Device v2 token remains a separate read-only mount at
`/run/secrets/hardwarestatus-device-token`. Old explicit token paths remain
valid input; deployment examples retain legacy in-container credential mount
aliases to the same host-side files.

Collector credentials may be present only in the root-owned configuration file.
At startup the Client validates the document and materializes Lucky and UniFi
credentials into private ephemeral files below /run/hardwarestatus; no secret is
placed in an environment variable, argument list, status payload, or log.

Profiles contain symbolic, fixed sources only. Arbitrary commands, paths,
containers, RPC endpoints, and remote hosts are rejected. Keep the config file
root:root and mode 0600 and mount it read-only. Use a tmpfs at /run/hardwarestatus
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

Both locations mount read-only at `/run/secrets/hardwarestatus/client-config.json`.
The examples retain `/run/secrets/hermesstatus/client-config.json` as a
compatibility alias to the same host file.
