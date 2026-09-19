# EasyTier monitoring design

EasyTier is a read-only Client domain. It obtains a bounded projection of node,
peer, route, connector, and traffic state through a fixed local CLI and a
fixed loopback RPC policy. It never manages EasyTier.

## Evidence and failure semantics

Each fixed command records its own collection time, duration, status, and last
successful collection. A failed cycle does not replace previously collected
command evidence with an invented empty payload. Timeout, CLI execution,
RPC-unavailable, and parse failures remain distinct diagnostics.

`last_success_at` means the last successful command result; it does not move to
the current attempt time on a failure. Current data is fresh only after an
accepted Client report under the Server clock.

## Aggregates, display bounds, and uncertainty

The Client filters the local peer by its own peer ID. Aggregates such as total,
direct, relay, unknown path, and IPv6 UDP direct are computed from the full
validated observation set, not merely the rows retained for display. Display
lists are bounded independently: peers, routes, connectors, and traffic-by-
instance rows are limited to 16; traffic samples are limited to 64.

For every bounded list, `total`, `displayed_total`, and `truncated` preserve
the distinction between observed and rendered data. Order changes must not
change aggregate conclusions. IPv6 UDP direct is true only with positive direct
IPv6/UDP evidence, false only when the relevant observation is conclusive, and
null/not observable when evidence is insufficient.

Traffic baselines are tied to the observed network and instance identity.
Network/instance change, known restart, counter reset, or an excessive sampling
gap starts a new baseline rather than reporting a misleading instantaneous rate.

## Safety boundary

The runtime allowlist contains read-only queries only. It excludes connector,
route, credential, whitelist, port-forward, logging, and service-lifecycle
commands. Raw configuration, endpoint secrets, credentials, and arbitrary
feature objects are not projected. The UI reads the existing stats document and
does not create a control endpoint.
