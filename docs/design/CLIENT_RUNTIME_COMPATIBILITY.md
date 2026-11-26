# Client Runtime Compatibility

## Runtime baseline

The 2.8 Client image remains based on `alpine:3.13`, whose packaged Python
runtime is Python 3.8. The first repository commit that introduced this base
was `d1ad6b0` (2026-02-27, “client alpine images”). Its Dockerfile diff
replaced `python:3.11-slim` plus apt/pip-installed tools with Alpine and
apk-packaged Python, psutil, iproute2, and procps. Neither that commit nor
current documentation records an explicit reason for choosing or pinning
Alpine 3.13; this is not a verified Synology-specific requirement.

This hotfix preserves the existing base because the observed failure is an
application API-compatibility bug, not evidence that the base image is
insufficient. Changing Alpine would also change the Python patch/runtime,
musl-linked packages such as `psutil`, and host-probe tools including
`smartmontools` and OpenSSH. Those changes can affect DSM host-kernel probes,
SMART transport/output, and mounted host-device behavior; they require a
separate compatibility qualification rather than being bundled into this
repair.

## Required checks

The `client-runtime` CI job first reproduces the failed candidate's
`removeprefix` exception from its exact historical source SHA, then runs the
complete Client unit suite and compiles all Python files copied into the image
with Python 3.8. A static compatibility test scopes known post-3.8 APIs and
runtime-evaluated annotations to files copied by `Dockerfile.client`. The suite
also exercises canonical/legacy metadata, Catalog V2 and USP-RPS fixtures, and
Pro Max 24 PoE resolution.

The `images` job builds the actual `linux/amd64` Server and Client images,
checks their revision and Catalog labels, records the Client image's Python
version, loads the embedded Catalog from that image, and runs the normal Client
entrypoint against an isolated real Server. A generated test token and test
Device ID are used over verified TLS through a narrowly trusted test proxy. CI
requires an accepted Device v2 report, matching Client revision, a running
Client, and zero restarts. No production device or credential is used.

The 2.8 candidate source gate requires both `client-runtime` and `images` to
succeed for the exact PR head SHA. Candidate publication remains protected by
the `hardwarestatus-2.8-candidate-publish` GitHub Environment approval.
