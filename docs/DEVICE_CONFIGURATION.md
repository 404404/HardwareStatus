# Device configuration

Device v2 configuration establishes identity and least-privilege collection;
it is not a remote-control configuration format. The repository is
HardwareStatus, while the documented `hermesstatus` container paths remain
intentional compatibility paths.

## Paths and mounts

Canonical unified Client configuration paths are:

| Host | Host path | Container path |
| --- | --- | --- |
| Linux/GK50 | `/home/hermes/status/config/client-config.json` | `/run/secrets/hermesstatus/client-config.json` |
| Synology DSM | `/volume1/docker/status/config/client-config.json` | `/run/secrets/hermesstatus/client-config.json` |

Mount the Device v2 token separately at
`/run/secrets/hermesstatus-device-token`. Keep configuration, token, CA,
UniFi password/API-key/known-hosts, and Lucky token files root-owned regular
files with restrictive permissions and read-only mounts. Do not print their
contents during diagnosis.

## Identity and transport

The Server Registry owns device ID, browser display name, enablement, and
credential digest. Use one identity/token per active Client. Configure an
HTTPS Server URL, TLS verification, an optional CA file where necessary, and
bounded connect/read timeouts. Do not let a hostname, a Client config display
string, or an observed remote name overwrite a Registry display name.

The strict unified schema is the preferred format. Retain an exact legacy
configuration only as rollback material; do not start two configurations or
two containers that report as the same device.

## Reviewed hardware access

Authorize each physical SMART device and filesystem probe explicitly. A disk
requires a corresponding read-only `devices:` mapping; a filesystem probe
requires only the narrow read-only host path it needs. Do not mount all disks,
the host root, `/proc` broadly, or arbitrary data directories.

Explicit SMART device entries remain authoritative. Automatic discovery is
bounded and uses qualified transport evidence; it does not hard-code Synology
or disk-model transport types. A collector must retain a genuine invalid field
or failed health result instead of probing alternative transports to find a
passing result.

## Optional integrations

Enable each collector explicitly. Disabled collectors are shown as not
configured in component diagnostics; they are not collection errors. Optional
Hermes/Lucky/EasyTier/UniFi failures remain scoped to their domain and do not
rename, deauthenticate, or take the host Device v2 Client offline.

For UniFi, profile, target, credential file, strict `known_hosts`, optional API
key file, and TLS pin are bounded fields. A profile selects only fixed sources;
runtime verified Catalog identity controls static capability. No field can add
a remote command, arbitrary path, or arbitrary controller URL.

## Preflight checklist

1. Validate Registry and Client JSON before deployment.
2. Verify file owner, permissions, regular-file status, and read-only mounts
   without reading secret contents.
3. Verify one Device v2 writer per identity.
4. Pin an approved Server/Client image digest and record the OCI revisions.
5. Confirm the next natural report is accepted, current, and attributed to the
   Registry device.
