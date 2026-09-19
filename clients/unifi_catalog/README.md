# HardwareStatus UniFi Catalog input

This directory is the deterministic UniFi Catalog bundle consumed by the
HardwareStatus Client. It is a build artifact, not a manually maintained model
table. The Client runtime and image package retain their existing
`hermesstatus` compatibility names.

The bundle is acquired only through the reviewed catalog workflow, pinned to an
upstream revision, and verified by the checked-in manifest SHA-256. Candidate
publication records the exact Catalog revision, schema version, and bundle hash
in the Client image provenance.

Profiles select fixed collection sources; they do not identify hardware or
unlock static capability. Model resolution accepts only verified runtime aliases
from the bundle. Unknown or candidate identity keeps bounded runtime telemetry
but withholds static port, PoE, storage, power, and processor claims.

Do not edit generated records, add a parallel model table, or change the bundle
without creating a new source revision, candidate image, and qualification.
