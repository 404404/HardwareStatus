#!/usr/bin/env python3
"""Fail-closed GHCR state machine for HardwareStatus 2.8 image pairs.

Only the two fixed HardwareStatus package names are inspected. Raw registry,
Docker inspect, and image environment output is never printed or persisted.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


VERSION = "2.8"
SOURCE_URL = "https://github.com/404404/HardwareStatus"
IMAGE_REPOSITORIES = {
    "server": "ghcr.io/404404/hardwarestatus-server",
    "client": "ghcr.io/404404/hardwarestatus-client",
}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CATALOG_SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class CandidateStateError(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    state: str  # ABSENT, PRESENT, or UNKNOWN
    metadata: dict[str, Any] | None = None
    valid: bool = False
    digest: str | None = None
    created: str | None = None


def validate_inputs(source_sha: str, catalog_revision: str, catalog_schema_version: int, catalog_sha256: str) -> None:
    if not SHA_PATTERN.fullmatch(source_sha):
        raise CandidateStateError("source SHA is not a full lowercase Git SHA")
    if not SHA_PATTERN.fullmatch(catalog_revision):
        raise CandidateStateError("Catalog revision is not a full lowercase Git SHA")
    if catalog_schema_version != 2:
        raise CandidateStateError("2.8 candidate requires Catalog schema version 2")
    if not CATALOG_SHA_PATTERN.fullmatch(catalog_sha256):
        raise CandidateStateError("Catalog bundle SHA256 is malformed")


def candidate_tag(source_sha: str) -> str:
    if not SHA_PATTERN.fullmatch(source_sha):
        raise CandidateStateError("source SHA is not a full lowercase Git SHA")
    return f"{VERSION}-{source_sha}"


def _environment(config: dict[str, Any]) -> dict[str, str]:
    result = {}
    for item in config.get("Env") or []:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def safe_image_metadata(payload: Any, component: str) -> dict[str, Any]:
    if component not in IMAGE_REPOSITORIES:
        raise CandidateStateError("unknown image component")
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise CandidateStateError("Docker inspect response has an invalid shape")
    image = payload[0]
    config = image.get("Config") or {}
    labels = config.get("Labels") or {}
    env = _environment(config)
    repository = IMAGE_REPOSITORIES[component]
    repo_digests = {
        entry.split("@", 1)[1]
        for entry in (image.get("RepoDigests") or [])
        if isinstance(entry, str) and entry.startswith(repository + "@") and "@" in entry
    }
    digest = next(iter(repo_digests)) if len(repo_digests) == 1 else None
    created = labels.get("org.opencontainers.image.created")
    # Keep only explicitly allowlisted provenance fields; never return the full
    # Config, labels, or environment (which may contain sensitive values).
    return {
        "component": component,
        "os": image.get("Os"),
        "architecture": image.get("Architecture"),
        "entrypoint": config.get("Entrypoint"),
        "digest": digest,
        "created": created,
        "labels": {
            key: labels.get(key)
            for key in (
                "org.opencontainers.image.title",
                "org.opencontainers.image.description",
                "org.opencontainers.image.version",
                "org.opencontainers.image.revision",
                "org.opencontainers.image.created",
                "org.opencontainers.image.source",
                "org.opencontainers.image.licenses",
                "io.hardwarestatus.component",
                "io.hermesstatus.component",
                "io.hardwarestatus.unifi.catalog.revision",
                "io.hardwarestatus.unifi.catalog.schema_version",
                "io.hardwarestatus.unifi.catalog.sha256",
                "io.hermesstatus.unifi.catalog.revision",
                "io.hermesstatus.unifi.catalog.schema_version",
                "io.hermesstatus.unifi.catalog.sha256",
            )
        },
        "runtime": {
            key: env.get(key)
            for key in (
                "HERMESSTATUS_CLIENT_VERSION",
                "HERMESSTATUS_CLIENT_REVISION",
                "HERMESSTATUS_CLIENT_BUILD_TIME",
                "HERMESSTATUS_UNIFI_CATALOG_REVISION",
                "HERMESSTATUS_UNIFI_CATALOG_SCHEMA_VERSION",
                "HERMESSTATUS_UNIFI_CATALOG_SHA256",
            )
        }
        if component == "client"
        else {},
    }


def validate_image_metadata(
    metadata: dict[str, Any],
    *,
    component: str,
    source_sha: str,
    catalog_revision: str,
    catalog_schema_version: int,
    catalog_sha256: str,
    expected_created: str | None = None,
) -> tuple[bool, str]:
    if metadata.get("component") != component:
        return False, "component"
    if metadata.get("os") != "linux" or metadata.get("architecture") != "amd64":
        return False, "platform"
    expected_entrypoint = (
        ["/usr/local/bin/serverstatus"] if component == "server" else ["/app/entrypoint.sh"]
    )
    if metadata.get("entrypoint") != expected_entrypoint:
        return False, "entrypoint"
    if not isinstance(metadata.get("digest"), str) or not DIGEST_PATTERN.fullmatch(metadata["digest"]):
        return False, "digest"
    labels = metadata.get("labels") or {}
    expected_labels = {
        "org.opencontainers.image.title": f"HardwareStatus {component.title()}",
        "org.opencontainers.image.description": (
            "HardwareStatus Go server and read-only dashboard"
            if component == "server"
            else "HardwareStatus host and Hermes profile collector"
        ),
        "org.opencontainers.image.version": VERSION,
        "org.opencontainers.image.revision": source_sha,
        "org.opencontainers.image.source": SOURCE_URL,
        "org.opencontainers.image.licenses": "MIT",
        "io.hardwarestatus.component": component,
        "io.hermesstatus.component": component,
        "io.hardwarestatus.unifi.catalog.revision": catalog_revision,
        "io.hardwarestatus.unifi.catalog.schema_version": str(catalog_schema_version),
        "io.hardwarestatus.unifi.catalog.sha256": catalog_sha256,
        "io.hermesstatus.unifi.catalog.revision": catalog_revision,
        "io.hermesstatus.unifi.catalog.schema_version": str(catalog_schema_version),
        "io.hermesstatus.unifi.catalog.sha256": catalog_sha256,
    }
    for key, expected in expected_labels.items():
        if labels.get(key) != expected:
            return False, "label"
    created = metadata.get("created")
    if not isinstance(created, str) or not UTC_PATTERN.fullmatch(created):
        return False, "created"
    try:
        dt.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False, "created"
    if expected_created is not None and created != expected_created:
        return False, "created_pair_mismatch"
    if component == "client":
        runtime = metadata.get("runtime") or {}
        expected_runtime = {
            "HERMESSTATUS_CLIENT_VERSION": VERSION,
            "HERMESSTATUS_CLIENT_REVISION": source_sha,
            "HERMESSTATUS_CLIENT_BUILD_TIME": created,
            "HERMESSTATUS_UNIFI_CATALOG_REVISION": catalog_revision,
            "HERMESSTATUS_UNIFI_CATALOG_SCHEMA_VERSION": str(catalog_schema_version),
            "HERMESSTATUS_UNIFI_CATALOG_SHA256": catalog_sha256,
        }
        for key, expected in expected_runtime.items():
            if runtime.get(key) != expected:
                return False, "client_runtime"
    return True, "ok"


def classify_pair(
    server: Observation,
    client: Observation,
    *,
    source_sha: str,
    catalog_revision: str,
    catalog_schema_version: int,
    catalog_sha256: str,
) -> dict[str, Any]:
    validate_inputs(source_sha, catalog_revision, catalog_schema_version, catalog_sha256)
    observations = {"server": server, "client": client}
    for component, observation in observations.items():
        if observation.state == "UNKNOWN":
            raise CandidateStateError(f"registry state is unknown for {component}")
        if observation.state not in {"ABSENT", "PRESENT"}:
            raise CandidateStateError(f"invalid registry state for {component}")
        if observation.state == "PRESENT":
            if not observation.valid or observation.metadata is None:
                raise CandidateStateError(f"existing {component} image has invalid provenance")
            valid, reason = validate_image_metadata(
                observation.metadata,
                component=component,
                source_sha=source_sha,
                catalog_revision=catalog_revision,
                catalog_schema_version=catalog_schema_version,
                catalog_sha256=catalog_sha256,
            )
            if not valid:
                raise CandidateStateError(f"existing {component} image provenance mismatch: {reason}")

    server_present = server.state == "PRESENT"
    client_present = client.state == "PRESENT"
    if server_present and client_present:
        if server.created != client.created:
            raise CandidateStateError("existing image pair has inconsistent creation timestamps")
        action = "ALREADY_PUBLISHED"
        created = server.created
    elif server_present:
        action = "PUBLISH_CLIENT"
        created = server.created
    elif client_present:
        action = "PUBLISH_SERVER"
        created = client.created
    else:
        action = "PUBLISH_BOTH"
        created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not isinstance(created, str) or not UTC_PATTERN.fullmatch(created):
        raise CandidateStateError("existing image pair has no valid shared creation timestamp")
    return {
        "action": action,
        "publish_server": action in {"PUBLISH_SERVER", "PUBLISH_BOTH"},
        "publish_client": action in {"PUBLISH_CLIENT", "PUBLISH_BOTH"},
        "created": created,
        "server_digest": server.digest if server_present else "",
        "client_digest": client.digest if client_present else "",
        "candidate_tag": candidate_tag(source_sha),
    }


def interpret_manifest_response(status: int, headers: dict[str, str], body: bytes) -> tuple[str, str | None]:
    """Only an explicit OCI/Docker unknown-manifest response proves absence."""
    if status == 200:
        digest = next(
            (value for key, value in headers.items() if key.lower() == "docker-content-digest"),
            None,
        )
        if isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest):
            return "PRESENT", digest
        return "UNKNOWN", None
    if status == 404:
        try:
            payload = json.loads(body[:65536].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "UNKNOWN", None
        errors = payload.get("errors") if isinstance(payload, dict) else None
        codes = {
            error.get("code")
            for error in (errors or [])
            if isinstance(error, dict)
        }
        if codes and codes <= {"MANIFEST_UNKNOWN", "NAME_UNKNOWN"}:
            return "ABSENT", None
    return "UNKNOWN", None


def _registry_bearer(username: str, password: str, package: str) -> str:
    scope = f"repository:404404/{package}:pull"
    credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = Request(
        "https://ghcr.io/token?" + urlencode({"service": "ghcr.io", "scope": scope}),
        headers={"Authorization": "Basic " + credentials, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise CandidateStateError("registry token response exceeded its bound")
        payload = json.loads(raw.decode("utf-8"))
        token = payload.get("token") or payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise CandidateStateError("registry did not grant read access")
        return token
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateStateError("registry authorization failed; state is unknown") from exc


def _registry_manifest_state(component: str, tag: str, username: str, password: str) -> tuple[str, str | None]:
    package = IMAGE_REPOSITORIES[component].rsplit("/", 1)[1]
    bearer = _registry_bearer(username, password, package)
    reference = f"https://ghcr.io/v2/404404/{package}/manifests/{tag}"
    request = Request(
        reference,
        headers={
            "Authorization": "Bearer " + bearer,
            "Accept": ", ".join(
                (
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.docker.distribution.manifest.v2+json",
                )
            ),
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read(1048577)
            if len(body) > 1048576:
                return "UNKNOWN", None
            return interpret_manifest_response(response.status, dict(response.headers.items()), body)
    except HTTPError as exc:
        try:
            body = exc.read(65537)
        except OSError:
            body = b""
        if len(body) > 65536:
            return "UNKNOWN", None
        return interpret_manifest_response(exc.code, dict(exc.headers.items()) if exc.headers else {}, body)
    except (URLError, TimeoutError) as exc:
        raise CandidateStateError("registry query failed; state is unknown") from exc


def _docker(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CandidateStateError("registry or Docker query failed; state is unknown") from exc


def probe_component(
    component: str,
    *,
    source_sha: str,
    catalog_revision: str,
    catalog_schema_version: int,
    catalog_sha256: str,
    expected_created: str | None = None,
) -> Observation:
    if component not in IMAGE_REPOSITORIES:
        raise CandidateStateError("unknown image component")
    actor = os.environ.get("GITHUB_ACTOR", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not actor or not github_token:
        return Observation("UNKNOWN")
    reference = f"{IMAGE_REPOSITORIES[component]}:{candidate_tag(source_sha)}"
    registry_state, registry_digest = _registry_manifest_state(
        component, candidate_tag(source_sha), actor, github_token
    )
    if registry_state == "ABSENT":
        return Observation("ABSENT")
    if registry_state != "PRESENT":
        return Observation("UNKNOWN")

    pulled = _docker(["docker", "pull", reference], timeout=180)
    if pulled.returncode != 0:
        return Observation("UNKNOWN")
    image_inspect = _docker(["docker", "image", "inspect", reference], timeout=45)
    if image_inspect.returncode != 0:
        return Observation("UNKNOWN")
    try:
        metadata = safe_image_metadata(json.loads(image_inspect.stdout), component)
    except (json.JSONDecodeError, CandidateStateError):
        return Observation("PRESENT", valid=False)
    valid, _ = validate_image_metadata(
        metadata,
        component=component,
        source_sha=source_sha,
        catalog_revision=catalog_revision,
        catalog_schema_version=catalog_schema_version,
        catalog_sha256=catalog_sha256,
        expected_created=expected_created,
    )
    if metadata.get("digest") != registry_digest:
        valid = False
    return Observation(
        "PRESENT",
        metadata=metadata,
        valid=valid,
        digest=metadata.get("digest"),
        created=metadata.get("created"),
    )


def _emit_plan(plan: dict[str, Any]) -> None:
    for key, value in plan.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        print(f"{key.upper()}={rendered}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plan", "verify"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--catalog-revision", required=True)
    parser.add_argument("--catalog-schema-version", type=int, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--created")
    args = parser.parse_args()
    try:
        validate_inputs(args.source_sha, args.catalog_revision, args.catalog_schema_version, args.catalog_sha256)
        if args.mode == "plan":
            server = probe_component(
                "server", source_sha=args.source_sha, catalog_revision=args.catalog_revision,
                catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
            )
            client = probe_component(
                "client", source_sha=args.source_sha, catalog_revision=args.catalog_revision,
                catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
            )
            _emit_plan(classify_pair(
                server, client, source_sha=args.source_sha, catalog_revision=args.catalog_revision,
                catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
            ))
            return 0

        if not args.created or not UTC_PATTERN.fullmatch(args.created):
            raise CandidateStateError("verify mode requires the exact publication timestamp")
        server = probe_component(
            "server", source_sha=args.source_sha, catalog_revision=args.catalog_revision,
            catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
            expected_created=args.created,
        )
        client = probe_component(
            "client", source_sha=args.source_sha, catalog_revision=args.catalog_revision,
            catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
            expected_created=args.created,
        )
        plan = classify_pair(
            server, client, source_sha=args.source_sha, catalog_revision=args.catalog_revision,
            catalog_schema_version=args.catalog_schema_version, catalog_sha256=args.catalog_sha256,
        )
        if plan["action"] != "ALREADY_PUBLISHED" or not server.digest or not client.digest:
            raise CandidateStateError("both images were not verified after publication")
        print(f"CANDIDATE_TAG={plan['candidate_tag']}")
        print(f"SERVER_DIGEST={server.digest}")
        print(f"CLIENT_DIGEST={client.digest}")
        print(f"CREATED={args.created}")
        print("PUBLICATION_STATE=VERIFIED")
        return 0
    except CandidateStateError as exc:
        print(f"CANDIDATE_PUBLICATION=FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
