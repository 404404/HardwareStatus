import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def job_block(workflow: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"missing workflow job: {name}")
    return match.group(1)


class PublishWorkflowSafetyTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_pull_request_ci_builds_only_local_images(self):
        workflow = self.read("ci.yml")
        self.assertIn("  pull_request:\n", workflow)
        self.assertNotIn("packages: write", workflow)
        self.assertNotIn("push: true", workflow)
        self.assertNotIn("publish_2_6_candidate:", workflow)

    def test_legacy_candidate_publishers_require_versioned_codex_branch(self):
        for version in ("2.5", "2.6"):
            workflow = self.read(f"publish-{version}-candidate-images.yml")
            publish = job_block(workflow, "publish")
            self.assertIn("workflow_dispatch:", workflow.split("jobs:", 1)[0])
            self.assertNotIn("pull_request:", workflow.split("jobs:", 1)[0])
            self.assertIn("github.repository == '404404/HardwareStatus'", publish)
            self.assertIn(f"startsWith(github.ref, 'refs/heads/codex/{version}-')", publish)
            self.assertIn("packages: write", publish)
            self.assertNotIn("packages: write", workflow.split(f"  publish:\n", 1)[0])
            self.assertNotRegex(publish, r"(?i)ghcr\.io/[^\s:]+:(?:latest|stable)(?:\s|$)")

    def test_2_7_pull_request_validation_cannot_enter_publish_job(self):
        workflow = self.read("publish-2.7-candidate-images.yml")
        publish = job_block(workflow, "publish")
        self.assertIn("  pull_request:\n", workflow)
        self.assertIn("github.event_name == 'push'", publish)
        self.assertIn("github.event_name == 'workflow_dispatch'", publish)
        self.assertIn("startsWith(github.ref, 'refs/heads/codex/2.7-')", publish)
        self.assertIn("packages: write", publish)
        self.assertNotIn("pull_request", publish)
        self.assertNotIn("packages: write", workflow.split("  publish:\n", 1)[0])

    def test_future_hardwarestatus_publisher_is_manual_and_immutable_sha_based(self):
        workflow = self.read("publish-hardwarestatus-candidate.yml")
        header, jobs = workflow.split("jobs:", 1)
        publish = job_block("jobs:\n" + jobs, "publish")
        self.assertIn("  workflow_dispatch:", header)
        self.assertNotIn("pull_request:", header)
        self.assertIn('[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]', workflow)
        # The workflow validates the requested full SHA first, then threads the
        # validated output through every checkout and the publish state machine.
        self.assertIn("ref: ${{ needs.source.outputs.source_sha }}", publish)
        self.assertIn('SOURCE_SHA: ${{ needs.source.outputs.source_sha }}', publish)
        self.assertIn('--source-sha "$SOURCE_SHA"', publish)
        self.assertIn('tags: ghcr.io/404404/hardwarestatus-server:${{ steps.plan.outputs.CANDIDATE_TAG }}', publish)
        self.assertIn('tags: ghcr.io/404404/hardwarestatus-client:${{ steps.plan.outputs.CANDIDATE_TAG }}', publish)
        self.assertNotRegex(publish, r"(?i)ghcr\.io/[^\s:]+:(?:latest|stable)(?:\s|$)")
        self.assertIn("refusing publication", publish)


if __name__ == "__main__":
    unittest.main()
