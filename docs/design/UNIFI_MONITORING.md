# UniFi monitoring design

UniFi is a profile-driven, read-only remote-observation domain. It is neither a
controller manager, device-discovery service, inventory database, remote shell,
nor configuration channel.

```text
fixed symbolic sources → bounded SSH/API observations → runtime identity
       → verified frozen Catalog alias → static capability + runtime telemetry
       → Device v2 → Server → /json/stats.json → UniFi and Diagnostics tabs
```

## Authority and ownership

The vendored deterministic bundle in `clients/unifi_catalog/` is the sole
authority for maintained static hardware facts. A collection profile selects
fixed sources; it is not hardware identity. API/SSH identity must resolve
through a verified Catalog alias before static ports, connector type, PoE,
storage, power, or processor data is projected. Unknown/candidate identity
retains runtime observations but receives no inferred static facts.

Physical port ownership uses `(device_id, port_idx)`. Runtime port records,
static rows, WAN data, uplinks, fan readings, storage, and power remain attached
to the verified device/interface they belong to. Numeric management-IP ordering
is independent from physical port ordering. Latest speed-test data attaches
only to an explicitly qualified WAN identity; it never becomes link speed.

## Capability and observation semantics

`supported`, `present`, and `observed` are separate. Unsupported storage or
power telemetry is hidden rather than rendered as an empty failure; supported
but unpopulated media remains visible as not installed. Static hardware capacity
is not overwritten by mounted filesystem usable capacity.

Runtime fan RPM is an observation, not proof of a physical-fan fault. A zero
RPM reading can be `observed_zero_rpm`; missing input is `not_observed`.
Physical capability remains what the verified Catalog or qualified evidence
states. No fan/PWM or storage control path is read for control or written.

PoE visibility and maximum port speed are static capability decisions. Runtime
absence is not proof of non-PoE, and negotiated speed is not a hardware maximum.

## Failure and security boundary

Host-key, authentication, timeout, TLS, transport, and parsing failures keep a
previous valid UniFi snapshot where available, mark that domain stale, and
expose a bounded safe error. They do not change the collector host Device v2
identity or unrelated domain health. Recovery clears current UniFi error/stale
state after a valid observation.

Sources are code-side symbolic IDs. Transport uses fixed argv, bounded output,
timeouts, strict known-host verification, protected file-backed credentials,
and API TLS pinning. No remote command, arbitrary path, raw response, private
configuration, or credential reaches persistence or the UI.
