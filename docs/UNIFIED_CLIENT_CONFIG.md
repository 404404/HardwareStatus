# Unified Client configuration

The preferred Client configuration is the strict JSON document validated by
`schemas/client-config.schema.json`. Set `SERVERSTATUS_CONFIG_FILE` to a
read-only mount, conventionally
`/run/secrets/serverstatus/client-config.json`; keep the Device v2 token as the
separate read-only `/run/secrets/serverstatus-device-token` mount.

For existing deployments, the Client still accepts the old environment prefix
and fixed token/config paths. If both old and new environment spellings are
provided with different values, startup fails closed. New Compose examples use
only the ServerStatus names.

`schema_version: 1` contains explicit `server`, `device`, `collection`, and
`collectors` objects. Current collector objects are `hardware`, `filesystem`,
`smart`, `docker`, `hermes`, `lucky`, `easytier`, and `unifi`. Unknown fields,
unknown symbolic sources, arbitrary commands, and arbitrary host/probe paths
are rejected.

The root-owned configuration may reference collector secret files. At startup
the Client materializes only the required values into its private
`/run/serverstatus` tmpfs (`0700`, `nosuid,nodev,noexec`); it never puts them in
environment values, arguments, logs, Device v2, diagnostics, or the UI.

UniFi settings are conditional on the enabled collector and include only
bounded target, profile, protected credential/known-hosts/API-key files, and
TLS-pinning information. A profile is not a remote shell or hardware identity.
Lucky and EasyTier remain fixed-policy collectors. The legacy `client-v2.json`
schema remains a rollback input, not a reason to loosen the unified schema.

Hardware entries are allowlists: specify each approved SMART device and each
fixed filesystem probe. Explicit SMART transport configuration wins over auto
discovery; automatic candidates are path-deduplicated and use qualified
transport evidence. Do not hard-code model-specific transports or use a
permissive `smartctl` mode merely to suppress validation.
