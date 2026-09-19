# Architecture

HardwareStatus is a read-only monitoring system with one authoritative browser
projection. The public repository has been renamed to HardwareStatus; the
existing `hermesstatus` runtime namespace remains a compatibility boundary.

```text
authorized host inputs → Python Client → Device v2 HTTPS → Go Server
                                                    ↓
                                      persisted accepted state
                                                    ↓
                           /json/stats.json → Web UI and Diagnostics tab
```

## Identity, acceptance, and persistence

The Device Registry is authoritative for `device_id`, `display_name`,
enablement, and protocol. A reported hostname is observation data and cannot
rename a Registry device. Device v2 uses TLS, a per-device credential stored by
the Server as a digest, replay/conflict checks, and a Server-side lifecycle
clock. Legacy TCP reports remain only where explicitly configured.

An accepted update is atomic. Invalid, stale, conflicting, or unauthorized
updates do not overwrite the last accepted observation. Restored state is
available for diagnosis after a Server restart but remains stale until a new
report is accepted.

## One projection, independent domains

The Server validates Client extensions and produces the single stats document
consumed by every UI tab. It does not make the browser join raw Client data or
poll collectors independently. Current domains are hardware/OS, Docker,
Hermes, Lucky, EasyTier, and configured UniFi targets.

The following signals are deliberately independent:

| Signal | Meaning |
| --- | --- |
| Device lifecycle | Whether the authenticated Client is online under the Server clock. |
| Freshness | Whether a particular observation is recent enough for its collection policy. |
| Collection quality | Whether a collector completed, was partial, unavailable, disabled, or not configured. |
| Hardware/business health | The interpreted health of an observed disk, service, route, or remote target. |
| Diagnostics | Bounded, resource-specific evidence explaining current errors or limitations. |

A healthy collection does not imply healthy hardware. Conversely, an optional
component that is not configured, a valid empty collection, or a supported
SMART attribute fallback does not make the device offline.

## Diagnostics model

Diagnostics are built for the same projection time as freshness. They preserve
strict decode/validation evidence and add current domain evidence, then clear
when a later valid observation resolves it. A diagnostic has a stable domain,
component, code, optional field/source/reason, and affected resource identity.
This prevents equal errors from different disks, filesystems, profiles, or API
endpoints from being merged accidentally.

Lists remain bounded. The Server records observed and displayed counts with a
truncation marker, prioritizing fault evidence over normal rows. A UI list is
therefore not a claim that the displayed count is the total count.

## UniFi authority boundary

The Client collects only fixed, read-only SSH/API sources selected by an
explicit profile. A profile chooses collection sources; it is not a hardware
identity. Runtime API/SSH identity must match a verified alias in the frozen
`clients/unifi_catalog/` bundle before static ports, PoE, storage, power, or
processor facts are projected. Unknown or candidate aliases retain bounded
runtime observations but never receive fabricated static capability.

Static port data joins runtime observations only by `(device_id, port_idx)`.
WAN, uplink, fan, storage, and power observations remain attached to their
verified device/interface identity; they must not leak across devices.

## Deliberate exclusions

HardwareStatus is not a remote shell, EasyTier/UniFi/Lucky manager, automatic
registration service, network scanner, alerting system, time-series database,
or arbitrary command/path runner. The Server never reads a Docker socket,
collector secret, raw client configuration, or raw remote response.
