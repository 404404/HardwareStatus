# HardwareStatus 2.8 Candidate Publication

The 2.8 candidate publisher is a `workflow_dispatch` workflow that must be
present on the default `2.0` branch. Dispatch it on `2.0` with one input:
the full lowercase SHA of the current, non-draft head of a same-repository PR
to `2.0` (or that PR's merged head). The source gate also requires the latest
`CI` pull-request run for that exact SHA and PR to be successful, including
the `contracts`, `go`, `python`, `client-runtime`, `frontend`, `compose`,
`images`, and `security` jobs. `client-runtime` runs the complete Client test
suite under Python 3.8; `images` depends on it and performs actual image startup
and an authenticated Device v2 report smoke against an isolated Server. The
workflow checks out and builds that SHA, never a moving branch name.

Publication is limited to `ghcr.io/404404/hardwarestatus-server` and
`ghcr.io/404404/hardwarestatus-client`, each tagged
`2.8-<full-source-sha>`. No `latest`, stable, 2.5, 2.6, or 2.7 tag is written.
The publisher verifies OCI revision, component, platform, Catalog V2 revision,
and Catalog bundle SHA256 before accepting an existing image. Image digests
are reported after verification; consumers should pin those digests.

New 2.8 outputs use only `io.hardwarestatus.*` product/Catalog labels and
`HARDWARESTATUS_*` Client build metadata. A manifest containing
`io.hermesstatus.*` labels or legacy `HERMESSTATUS_CLIENT_*` /
`HERMESSTATUS_UNIFI_CATALOG_*` build metadata is rejected. Hermes Agent
monitoring remains a separate optional Client integration.

## Registry state and recovery

The publisher authenticates to GHCR and probes each image manifest
independently. Only a successful authenticated `MANIFEST_UNKNOWN` or
`NAME_UNKNOWN` response proves absence. Authentication failures, malformed
responses, timeouts, rate limits, or other registry errors are unknown and
stop publication.

| Server | Client | Result |
| --- | --- | --- |
| Absent | Absent | Publish both images |
| Present with exact provenance | Absent | Publish only Client |
| Absent | Present with exact provenance | Publish only Server |
| Present with exact provenance | Present with exact provenance | Idempotent no-op |
| Present with conflicting provenance | Any | Fail closed; never overwrite |
| Any | Present with conflicting provenance | Fail closed; never overwrite |
| Unknown | Any | Fail closed |
| Any | Unknown | Fail closed |

For a one-sided interrupted publication, the existing image's exact source,
Catalog identity, architecture, creation timestamp, and manifest digest are
validated. A retry builds only the missing image and reuses the existing
timestamp. A bad or unreadable existing image is terminal for that tag; do not
delete, replace, or manually retag it. Escalate for a separately reviewed
recovery decision.

Concurrency is keyed by the full source SHA and is non-canceling. This
serializes retries for the same immutable candidate while full-SHA tags keep
different sources distinct. The workflow's no-overwrite rule is an application
policy; registry administrators can still delete package versions, so retain
the final digest record and do not treat a tag as a substitute for a digest.

## Approval and package permissions

The only job granted `packages: write` is `publish`. It runs in the
`hardwarestatus-2.8-candidate-publish` GitHub Environment. Before the first
publication, repository administrators must configure that Environment with
required reviewer(s) and restrict deployment branches to `2.0`; merely naming
an Environment in YAML does not create reviewer protection rules.

The historical 2.5, 2.6, and 2.7 publishers also scope package-write access to
their `publish` jobs. The 2.7 publisher can publish only on a `codex/2.7-*`
branch push or manual dispatch on that branch; pull-request runs never publish.

The publish job uses its repository-scoped `GITHUB_TOKEN` with `packages:
write`, and the image carries `org.opencontainers.image.source` pointing to
this repository so the package is linked to the workflow repository. The
repository owner must retain package-creation rights. This workflow does not
perform a test push during bootstrap.

After first package creation, verify both package settings and the repository
link. Public GHCR packages permit anonymous pulls. Private packages require a
separately provisioned pull credential/access grant on each deployment host;
never embed that credential in an image or source file. Package visibility and
Actions access are registry settings, not guaranteed solely by this workflow.

Pending cleanup review only (not deleted by this workflow):

- `ghcr.io/404404/hermesstatus-server:2.7-83934eb3f692`
- `ghcr.io/404404/hermesstatus-client:2.7-83934eb3f692`

This workflow does not create a formal release, update old package names,
deploy containers, or modify existing 2.5/2.6/2.7 artifacts.

The Client Python baseline and its upgrade risks are recorded in
[Client Runtime Compatibility](design/CLIENT_RUNTIME_COMPATIBILITY.md).
