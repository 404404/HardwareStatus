# Operations

## Read status correctly

The Server clock determines Device v2 lifecycle and freshness. A restored
state is useful evidence but stale until the next accepted report. Collection
success, data freshness, and business/hardware health are separate signals.

Examples of non-fault limitations include an optional component that is not
configured, a valid empty EasyTier set, and USB SMART that provides a trusted
attribute-based health result but not native return status. These remain visible
as partial/limited diagnostics. A SMART `failed` health result, invalid SMART
field, rejected Device v2 update, authentication failure, or required transport
failure remains fault evidence.

## Use the diagnostics tab

The Diagnostics tab is a Server-side explanation of the current stats
projection. Read the affected component, stable resource identity, source,
field, code, and bounded reason together. It is not a request log and should
not contain credentials or complete raw payloads.

`observed_count`, `displayed_count`, and `truncated` distinguish a bounded UI
list from the complete observed set. A healthy-looking first rows list does not
cancel a retained fault from another resource. After a valid recovery report,
current diagnostics resolve; any historical audit belongs outside the current
projection.

## Routine diagnosis

Compare the Client's accepted collection time, Server receive time, current
image digest/OCI revision, component freshness, and resource diagnostics. Do
not diagnose a display issue by opening an arbitrary shell in a container,
changing a router, changing a disk setting, or executing an undocumented
command. Use fixed read-only diagnostics only.

For EasyTier, use `null`/not observable rather than false when direct/relay or
IPv6 UDP evidence is insufficient. For UniFi, verify device/interface identity
before associating a WAN result, fan, port, or static capability.

## Backup, restart, and rollback

Before changing a Server, privately back up the exact state file and its `~`
backup, configuration/Registry revision, and prior immutable image digests.
Ensure the copy is consistent and checksum it. A controlled Server restart
must preserve persisted state, then receive a natural report before freshness
is declared current.

`version: 2` in a state file is not a universal downgrade promise. Newer
collection-diagnostics state can be accepted by the current Server while an
exact pre-change 2.7 Server may retain affected data as a corrupt orphan.
Rollback requires the matching previous Server/Client images, configuration,
and pre-upgrade state. Stop the newer Client first, preserve single-writer
identity, then restore the older Server state before restarting it.
