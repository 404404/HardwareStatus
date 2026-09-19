# Security

HardwareStatus is intentionally read-only. The repository rename does not
change the established `hermesstatus` credential paths, environment names, or
image package names used by deployed installations.

## Identity and secrets

Device v2 uses TLS and a per-device token; the Server stores only its digest.
Clients read tokens, CAs, Lucky tokens, and UniFi credentials from protected
read-only files. Do not put a secret in source control, arguments, environment
values, labels, fixtures, logs, status documents, diagnostic reasons, or UI.

## Collection and remote boundaries

Collectors use fixed source allowlists and argv arrays. They reject arbitrary
commands, paths, hosts, redirects, raw configurations, credentials, and
sensitive EasyTier objects. Lucky is loopback-only; EasyTier uses a fixed
read-only CLI and loopback RPC; UniFi uses fixed bundled read-only sources,
strict host-key checking, protected keyboard-interactive credentials, and API
TLS pinning where configured.

No collector installs keys, scans networks, changes a remote configuration,
controls a fan/PWM, changes storage settings, or exposes a management endpoint.
Host-key or TLS verification failure is a telemetry error, never authority to
weaken verification.

## Least privilege and data handling

Do not use privileged containers, `SYS_ADMIN`, a broad Docker API, whole
`/dev`, `/dev/sg*`, or the host root. Grant only reviewed read-only mounts,
explicit SMART device mappings, and `SYS_RAWIO` where essential. The Server
strictly bounds counts, strings, counters, timestamps, and enums, discards
unknown sensitive fields, and applies accepted updates atomically.

Diagnostics are bounded, resource-specific, and secret-filtered. They retain
enough code/field/source evidence to operate safely without becoming request
or configuration dumps.

## Reporting vulnerabilities

Do not include secrets or live infrastructure identifiers in a public issue.
Use a private maintainer/security channel with the smallest sanitized
reproduction.
