# Hardware monitoring design

The hardware domain is a bounded, fault-isolated observation pipeline. A SMART
failure must not remove CPU, memory, filesystem, Docker, or other hardware
observations.

## Resource model

The Client separates physical disks from volumes/filesystems. Physical disk
properties include identity, capacity, SMART, temperature, and power-on hours;
filesystem observations describe an explicitly configured mountpoint, source,
type, capacity, and use. This prevents invented ownership for DSM RAID, mdraid,
LVM, and device-mapper volumes.

Server diagnostics identify the affected disk or filesystem with a stable
resource key. Equal errors from two disks remain two diagnostics. Diagnostic
lists are bounded but retain count/truncation evidence and prioritize faults.

## SMART semantics

Explicit `smart_devices` configuration is authoritative. Automatic discovery
prefers qualified open-device scan evidence, falls back safely, and
deduplicates by device path so a known transport is not duplicated as an empty
transport candidate. It does not hard-code a NAS vendor, disk model, or
transport type.

Native SMART return status is preferred. If it is unavailable but attributes
and thresholds support a trustworthy fallback, the disk can report
`health=passed` or `health=failed`, `health_source=attribute_check`, and
`completeness=partial`. The native-status limitation is visible but, for a
passed result, is not by itself a hardware/device fault. A failed result remains
a real disk health failure.

Field-quality failures are independent evidence. For example, an invalid
temperature remains an invalid-value diagnostic even if an attribute fallback
also provides a usable health result. Valid fields remain available; an old
single-error field, where retained for compatibility, has a deterministic
primary error but does not erase the other structured diagnostic.

Do not re-probe alternative transports after a valid failed health result, add
`-T permissive`, replace `-x` with `-a`, or weaken SMART validation to hide an
error.

## Least privilege

Use explicit read-only device mappings and `SYS_RAWIO` only where needed. Do
not use privileged mode, `SYS_ADMIN`, broad `/dev`, `/dev/sg*`, host root, or
arbitrary probe paths. Filesystem and DSM identity probes are fixed narrow
read-only mounts.
