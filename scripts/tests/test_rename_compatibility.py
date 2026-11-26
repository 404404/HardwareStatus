from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RenameCompatibilityTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_new_root_compose_defaults_are_canonical(self):
        server = self.read("docker-compose-server.yml")
        client = self.read("docker-compose-client.yml")
        self.assertIn("hardwarestatus-server:", server)
        self.assertIn("container_name: hardwarestatus-server", server)
        self.assertIn("ghcr.io/404404/hardwarestatus-server:local", server)
        self.assertIn("hardwarestatus-network:", server)
        self.assertIn('${HARDWARESTATUS_ADMIN_TOKEN-${ADMIN_TOKEN-}}', server)
        self.assertIn('${ADMIN_TOKEN-${HARDWARESTATUS_ADMIN_TOKEN-}}', server)
        self.assertNotIn("cppla/serverstatus", server)
        self.assertNotIn("serverstatus-server:", server)
        self.assertIn("hardwarestatus-client:", client)
        self.assertIn("container_name: hardwarestatus-client", client)
        self.assertIn("ghcr.io/404404/hardwarestatus-client:local", client)
        self.assertIn("/var/lib/hardwarestatus-client", client)
        self.assertNotIn("serverstatus-client:", client)

    def test_existing_paths_and_protocol_aliases_are_retained(self):
        client = self.read("deploy/compose/client-synology.example.yml")
        self.assertIn("HARDWARESTATUS_CONFIG_FILE:", client)
        self.assertIn("/run/secrets/hardwarestatus/client-config.json", client)
        self.assertIn("/run/secrets/hardwarestatus-device-token", client)
        self.assertIn("/run/hardwarestatus:size=", client)
        self.assertIn("/var/lib/hardwarestatus-client", client)
        # Existing host mounts and container aliases remain available for old configs.
        self.assertIn("/run/secrets/hermesstatus/client-config.json", client)
        self.assertIn("/run/secrets/hermesstatus-device-token", client)
        self.assertIn("/run/hermesstatus:size=", client)
        self.assertIn("/var/lib/serverstatus-client", client)
        self.assertIn("/volume1/docker/status/config/client-config.json:/run/secrets/hardwarestatus/client-config.json:ro", client)
        self.assertIn("/volume1/docker/status/config/client-config.json:/run/secrets/hermesstatus/client-config.json:ro", client)
        contracts = self.read("clients/multi_device_contracts.py")
        self.assertIn('"HERMESSTATUS_SERVER_URL"', contracts)
        self.assertIn('key.replace("HERMESSTATUS_", "HARDWARESTATUS_", 1)', contracts)
        self.assertIn('"X-HermesStatus-Device-ID"', self.read("server/device_http_adapter.go"))

    def test_server_executable_and_old_invocation_are_both_packaged(self):
        dockerfile = self.read("Dockerfile.server")
        self.assertIn("/usr/local/bin/hardwarestatus-server", dockerfile)
        self.assertIn("ln -s /usr/local/bin/hardwarestatus-server /usr/local/bin/serverstatus", dockerfile)
        self.assertIn('ENTRYPOINT ["/usr/local/bin/hardwarestatus-server"]', dockerfile)
        verifier = self.read("scripts/validate_image_provenance.py")
        self.assertIn("/usr/local/bin/hardwarestatus-server", verifier)
        self.assertIn("/usr/local/bin/serverstatus", verifier)

    def test_future_candidate_workflow_uses_new_packages_without_retagging_legacy(self):
        workflow = self.read(".github/workflows/publish-hardwarestatus-candidate.yml")
        self.assertIn("hardwarestatus-server:${{ steps.plan.outputs.CANDIDATE_TAG }}", workflow)
        self.assertIn("hardwarestatus-client:${{ steps.plan.outputs.CANDIDATE_TAG }}", workflow)
        self.assertIn("SOURCE_SHA", workflow)
        self.assertIn("io.hardwarestatus.component=server", workflow)
        self.assertIn("io.hardwarestatus.component=client", workflow)
        self.assertIn("group: hardwarestatus-2.8-candidate-${{ inputs.source_sha }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        state_machine = self.read("scripts/candidate_publish_state.py")
        self.assertIn("registry query failed; state is unknown", state_machine)
        self.assertIn('Observation("UNKNOWN")', state_machine)
        self.assertNotIn("tags: ghcr.io/${{ github.repository_owner }}/hermesstatus-", workflow)
        self.assertNotIn("io.hermesstatus.", workflow)

    def test_cutover_document_preserves_single_writer_and_state_rollback(self):
        document = self.read("docs/RENAME_COMPATIBILITY.md")
        self.assertIn("zero writers", document)
        self.assertIn("pre-upgrade state", document)
        self.assertIn("does not execute this procedure on GK50 or RS820", document)
        stop_old = document.index("Stop the old Client")
        verify_zero = document.index("zero\n   active writers")
        replace_client = document.index("Replace only the Client image/name")
        stop_new = document.index("stop the new Client first")
        restore_old = document.index("matching old Server/Client images")
        self.assertLess(stop_old, verify_zero)
        self.assertLess(verify_zero, replace_client)
        self.assertLess(stop_new, restore_old)


if __name__ == "__main__":
    unittest.main()
