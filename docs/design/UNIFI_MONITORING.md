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

## Optional USP-RPS component

RPS telemetry is a separate optional `unifi.rps` component. It reuses the
existing bounded, read-only `legacy_stat_device` API observation; it does not
add an arbitrary endpoint or remote command. The controller device list is
resolved through the pinned Catalog's exact verified `USP RPS` API identity,
then joined to the legacy observation only by an exact internal device
identity. Names, IPs, list positions, and model capability alone never create
a protected-device relationship.

Catalog model schema v2 represents six numbered DC outputs separately from the
RJ45 management interface. Static 11.5 V / 350 W and 52 V / 600 W rail ratings
remain two independent capabilities. They are not added as one available
capacity, copied into runtime measurements, or assigned to an individual
output without evidence. Runtime telemetry stays on the observed 12 V and 54 V
output buses for each port; these bus labels are not mapped onto the differently
named static Catalog ratings.

`connected_standby` and `delivering_power` are distinct states; `power_active`
and `power_delivering` are independently nullable observations. Measured
output watts are shown only when both same-port output-bus power readings are
available. The total is shown only as a complete six-port same-snapshot sum,
explicitly labeled `same_sample_port_sum`; otherwise power remains null. No
`power_source` numeric mapping is interpreted, and RPS delivery is not an AC
failure signal—the protected device may intentionally have its AC input
disconnected.

RPS has its own bounded schema version and `unifi/rps` component diagnostic.
`not_observed`, `partial`, `unavailable`, and `stale` remain scoped to RPS and
do not degrade ordinary UniFi device monitoring. No failover or supply-switch
operation is performed to obtain telemetry.

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
