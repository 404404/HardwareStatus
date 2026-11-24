import importlib.util
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/candidate_publish_state.py"
SPEC = importlib.util.spec_from_file_location("candidate_publish_state", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


SOURCE_SHA = "a" * 40
CATALOG_REVISION = "b" * 40
CATALOG_SHA = "c" * 64
CREATED = "2026-11-24T00:00:00Z"
DIGEST = "sha256:" + "d" * 64


def metadata(component, *, source_sha=SOURCE_SHA, catalog_revision=CATALOG_REVISION, catalog_sha=CATALOG_SHA):
    labels = {
        "org.opencontainers.image.title": f"HardwareStatus {component.title()}",
        "org.opencontainers.image.description": (
            "HardwareStatus Go server and read-only dashboard"
            if component == "server"
            else "HardwareStatus host and Hermes profile collector"
        ),
        "org.opencontainers.image.version": "2.8",
        "org.opencontainers.image.revision": source_sha,
        "org.opencontainers.image.created": CREATED,
        "org.opencontainers.image.source": MODULE.SOURCE_URL,
        "org.opencontainers.image.licenses": "MIT",
        "io.hardwarestatus.component": component,
        "io.hermesstatus.component": component,
    }
    for prefix in ("io.hardwarestatus", "io.hermesstatus"):
        labels[prefix + ".unifi.catalog.revision"] = catalog_revision
        labels[prefix + ".unifi.catalog.schema_version"] = "2"
        labels[prefix + ".unifi.catalog.sha256"] = catalog_sha
    env = []
    if component == "client":
        env = [
            "HERMESSTATUS_CLIENT_VERSION=2.8",
            "HERMESSTATUS_CLIENT_REVISION=" + source_sha,
            "HERMESSTATUS_CLIENT_BUILD_TIME=" + CREATED,
            "HERMESSTATUS_UNIFI_CATALOG_REVISION=" + catalog_revision,
            "HERMESSTATUS_UNIFI_CATALOG_SCHEMA_VERSION=2",
            "HERMESSTATUS_UNIFI_CATALOG_SHA256=" + catalog_sha,
        ]
    package = MODULE.IMAGE_REPOSITORIES[component]
    raw = [{
        "Os": "linux",
        "Architecture": "amd64",
        "RepoDigests": [package + "@" + DIGEST],
        "Config": {
            "Labels": labels,
            "Env": env,
            "Entrypoint": ["/usr/local/bin/serverstatus"] if component == "server" else ["/app/entrypoint.sh"],
        },
    }]
    return MODULE.safe_image_metadata(raw, component)


def present(component, value=None, created=CREATED):
    value = value or metadata(component)
    return MODULE.Observation(
        "PRESENT", metadata=value, valid=True, digest=DIGEST, created=created
    )


def classify(server, client):
    return MODULE.classify_pair(
        server,
        client,
        source_sha=SOURCE_SHA,
        catalog_revision=CATALOG_REVISION,
        catalog_schema_version=2,
        catalog_sha256=CATALOG_SHA,
    )


class CandidatePublishStateTests(unittest.TestCase):
    def test_candidate_tag_binds_full_source_sha(self):
        self.assertEqual(MODULE.candidate_tag(SOURCE_SHA), "2.8-" + SOURCE_SHA)
        with self.assertRaises(MODULE.CandidateStateError):
            MODULE.candidate_tag("a" * 12)

    def test_first_publish_builds_both_images(self):
        plan = classify(MODULE.Observation("ABSENT"), MODULE.Observation("ABSENT"))
        self.assertEqual(plan["action"], "PUBLISH_BOTH")
        self.assertTrue(plan["publish_server"])
        self.assertTrue(plan["publish_client"])
        self.assertEqual(plan["candidate_tag"], "2.8-" + SOURCE_SHA)

    def test_valid_server_only_partial_run_publishes_client_only(self):
        plan = classify(present("server"), MODULE.Observation("ABSENT"))
        self.assertEqual(plan["action"], "PUBLISH_CLIENT")
        self.assertFalse(plan["publish_server"])
        self.assertTrue(plan["publish_client"])
        self.assertEqual(plan["created"], CREATED)

    def test_valid_client_only_partial_run_publishes_server_only(self):
        plan = classify(MODULE.Observation("ABSENT"), present("client"))
        self.assertEqual(plan["action"], "PUBLISH_SERVER")
        self.assertTrue(plan["publish_server"])
        self.assertFalse(plan["publish_client"])
        self.assertEqual(plan["created"], CREATED)

    def test_duplicate_exact_pair_is_idempotent(self):
        plan = classify(present("server"), present("client"))
        self.assertEqual(plan["action"], "ALREADY_PUBLISHED")
        self.assertFalse(plan["publish_server"])
        self.assertFalse(plan["publish_client"])
        self.assertEqual(plan["server_digest"], DIGEST)
        self.assertEqual(plan["client_digest"], DIGEST)

    def test_existing_wrong_source_provenance_is_not_overwritten(self):
        wrong = metadata("server", source_sha="e" * 40)
        with self.assertRaisesRegex(MODULE.CandidateStateError, "provenance mismatch"):
            classify(present("server", wrong), MODULE.Observation("ABSENT"))

    def test_catalog_mismatch_is_not_overwritten_or_completed(self):
        wrong = metadata("client", catalog_sha="f" * 64)
        with self.assertRaisesRegex(MODULE.CandidateStateError, "provenance mismatch"):
            classify(MODULE.Observation("ABSENT"), present("client", wrong))

    def test_creation_timestamp_mismatch_fails_closed(self):
        with self.assertRaisesRegex(MODULE.CandidateStateError, "timestamps"):
            classify(present("server"), present("client", created="2026-11-24T00:00:01Z"))

    def test_unknown_or_unreadable_registry_state_fails_closed(self):
        with self.assertRaisesRegex(MODULE.CandidateStateError, "unknown"):
            classify(MODULE.Observation("UNKNOWN"), MODULE.Observation("ABSENT"))
        with self.assertRaisesRegex(MODULE.CandidateStateError, "unknown"):
            classify(MODULE.Observation("ABSENT"), MODULE.Observation("UNKNOWN"))

    def test_invalid_present_manifest_fails_closed(self):
        with self.assertRaisesRegex(MODULE.CandidateStateError, "invalid provenance"):
            classify(MODULE.Observation("PRESENT", valid=False), MODULE.Observation("ABSENT"))

    def test_registry_404_only_proves_absence_for_known_manifest_codes(self):
        absent = json.dumps({"errors": [{"code": "MANIFEST_UNKNOWN"}]}).encode()
        self.assertEqual(MODULE.interpret_manifest_response(404, {}, absent), ("ABSENT", None))
        unknown_name = json.dumps({"errors": [{"code": "NAME_UNKNOWN"}]}).encode()
        self.assertEqual(MODULE.interpret_manifest_response(404, {}, unknown_name), ("ABSENT", None))
        self.assertEqual(MODULE.interpret_manifest_response(404, {}, b"not-json"), ("UNKNOWN", None))
        self.assertEqual(MODULE.interpret_manifest_response(404, {}, b'{"errors":[{"code":"BLOB_UNKNOWN"}]}'), ("UNKNOWN", None))

    def test_registry_auth_failure_network_failure_and_missing_digest_are_unknown(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                self.assertEqual(MODULE.interpret_manifest_response(status, {}, b""), ("UNKNOWN", None))
        self.assertEqual(MODULE.interpret_manifest_response(200, {}, b"{}"), ("UNKNOWN", None))
        self.assertEqual(
            MODULE.interpret_manifest_response(200, {"Docker-Content-Digest": DIGEST}, b"{}"),
            ("PRESENT", DIGEST),
        )

    def test_registry_unreachable_stops_instead_of_assuming_absence(self):
        with patch.dict(os.environ, {"GITHUB_ACTOR": "ci-user", "GITHUB_TOKEN": "test-token"}), patch.object(
            MODULE, "_registry_manifest_state", side_effect=MODULE.CandidateStateError("registry query failed")
        ):
            with self.assertRaisesRegex(MODULE.CandidateStateError, "registry query failed"):
                MODULE.probe_component(
                    "server",
                    source_sha=SOURCE_SHA,
                    catalog_revision=CATALOG_REVISION,
                    catalog_schema_version=2,
                    catalog_sha256=CATALOG_SHA,
                )

    def test_image_metadata_allowlist_does_not_return_unselected_environment(self):
        raw = [{
            "Os": "linux",
            "Architecture": "amd64",
            "RepoDigests": [MODULE.IMAGE_REPOSITORIES["client"] + "@" + DIGEST],
            "Config": {
                "Labels": metadata("client")["labels"],
                "Entrypoint": ["/app/entrypoint.sh"],
                "Env": ["UNRELATED_SECRET=must-not-escape"] + [
                    "HERMESSTATUS_CLIENT_VERSION=2.8",
                    "HERMESSTATUS_CLIENT_REVISION=" + SOURCE_SHA,
                    "HERMESSTATUS_CLIENT_BUILD_TIME=" + CREATED,
                    "HERMESSTATUS_UNIFI_CATALOG_REVISION=" + CATALOG_REVISION,
                    "HERMESSTATUS_UNIFI_CATALOG_SCHEMA_VERSION=2",
                    "HERMESSTATUS_UNIFI_CATALOG_SHA256=" + CATALOG_SHA,
                ],
            },
        }]
        selected = MODULE.safe_image_metadata(raw, "client")
        self.assertNotIn("UNRELATED_SECRET", json.dumps(selected))

    def test_publish_concurrency_is_per_full_sha_and_does_not_cancel_active_run(self):
        workflow = (ROOT / ".github/workflows/publish-hardwarestatus-candidate.yml").read_text(encoding="utf-8")
        self.assertIn("group: hardwarestatus-2.8-candidate-${{ inputs.source_sha }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("if: ${{ steps.plan.outputs.PUBLISH_SERVER == 'true' }}", workflow)
        self.assertIn("if: ${{ steps.plan.outputs.PUBLISH_CLIENT == 'true' }}", workflow)

    def test_publish_permissions_and_legacy_release_boundaries(self):
        workflow = (ROOT / ".github/workflows/publish-hardwarestatus-candidate.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("packages: write"), 1)
        publish_section = workflow.split("\n  publish:\n", 1)[1]
        self.assertIn("environment:\n      name: hardwarestatus-2.8-candidate-publish", publish_section)
        self.assertNotIn(":latest", workflow)
        self.assertNotRegex(
            workflow,
            r"hardwarestatus-(?:server|client):(?:2\.5|2\.6|2\.7)(?:-|$)",
        )
        for filename in (
            "publish-2.5-candidate-images.yml",
            "publish-2.6-candidate-images.yml",
            "publish-2.7-candidate-images.yml",
        ):
            self.assertTrue((ROOT / ".github/workflows" / filename).is_file())


if __name__ == "__main__":
    unittest.main()
