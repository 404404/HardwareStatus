import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate_candidate_source.py"
SPEC = importlib.util.spec_from_file_location("candidate_source_validation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


SHA = "a" * 40
PR = {
    "number": 40,
    "state": "open",
    "draft": False,
    "merged_at": None,
    "head": {
        "sha": SHA,
        "ref": "codex/runtime-compatibility-hotfix",
        "repo": {"full_name": MODULE.TRUSTED_REPOSITORY},
    },
    "base": {"ref": "2.0"},
}


class CandidateSourceValidationTests(unittest.TestCase):
    def test_python38_client_runtime_gate_is_required_for_source_trust(self):
        self.assertIn("client-runtime", MODULE.REQUIRED_CI_JOBS)
        jobs_without_runtime = [
            {"name": name, "conclusion": "success"}
            for name in MODULE.REQUIRED_CI_JOBS
            if name != "client-runtime"
        ]
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.validate_ci_jobs(jobs_without_runtime)
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("client-runtime:", workflow)
        self.assertIn('python-version: "3.8"', workflow)
        images_job = workflow.split("  images:", 1)[1].split("  security:", 1)[0]
        self.assertIn("client-runtime", images_job)

    def test_exact_same_repository_ready_pr_head_is_trusted(self):
        selected = MODULE.select_trusted_pull_request([PR], SHA)
        self.assertEqual(selected["number"], 40)

    def test_merged_trusted_pr_head_is_trusted(self):
        merged = {**PR, "state": "closed", "draft": False, "merged_at": "2026-11-24T00:00:00Z"}
        self.assertEqual(MODULE.select_trusted_pull_request([merged], SHA)["number"], 40)

    def test_fork_wrong_base_draft_and_non_head_sources_fail_closed(self):
        variants = (
            {**PR, "head": {"sha": SHA, "repo": {"full_name": "fork/HardwareStatus"}}},
            {**PR, "base": {"ref": "main"}},
            {**PR, "draft": True},
            {**PR, "head": {"sha": "b" * 40, "repo": {"full_name": MODULE.TRUSTED_REPOSITORY}}},
        )
        for pull in variants:
            with self.subTest(pull=pull), self.assertRaises(MODULE.SourceValidationError):
                MODULE.select_trusted_pull_request([pull], SHA)

    def test_ambiguous_trusted_prs_fail_closed(self):
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.select_trusted_pull_request([PR, {**PR, "number": 41}], SHA)

    def test_sha_must_be_full_lowercase(self):
        for invalid in ("a" * 39, "A" * 40, "a" * 40 + "0", "not-a-sha"):
            with self.subTest(invalid=invalid), self.assertRaises(MODULE.SourceValidationError):
                MODULE.validate_sha(invalid)

    def test_exact_full_ci_jobs_are_required(self):
        jobs = [{"name": name, "conclusion": "success"} for name in MODULE.REQUIRED_CI_JOBS]
        MODULE.validate_ci_jobs(jobs)
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.validate_ci_jobs(jobs[:-1])
        without_python38_runtime = [
            job for job in jobs if job["name"] != "client-runtime"
        ]
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.validate_ci_jobs(without_python38_runtime)
        failed = [dict(job) for job in jobs]
        failed[0]["conclusion"] = "failure"
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.validate_ci_jobs(failed)

    def test_latest_run_must_be_successful_for_same_pr_and_sha(self):
        good = {
            "id": 101,
            "run_number": 10,
            "run_attempt": 1,
            "head_sha": SHA,
            "event": "pull_request",
            "pull_requests": [{"number": 40}],
            "status": "completed",
            "conclusion": "success",
        }
        head_ref = PR["head"]["ref"]
        self.assertEqual(MODULE.select_latest_ci_run([good], 40, SHA, head_ref)["id"], 101)
        newer_pending = {**good, "id": 102, "run_number": 11, "status": "in_progress", "conclusion": None}
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.select_latest_ci_run([good, newer_pending], 40, SHA, head_ref)

    def test_manual_full_ci_for_exact_trusted_pr_head_is_accepted(self):
        run = {
            "id": 103,
            "run_number": 12,
            "run_attempt": 1,
            "head_sha": SHA,
            "event": "workflow_dispatch",
            "head_branch": PR["head"]["ref"],
            "status": "completed",
            "conclusion": "success",
        }
        self.assertEqual(
            MODULE.select_latest_ci_run([run], 40, SHA, PR["head"]["ref"])["id"],
            103,
        )

    def test_runs_for_wrong_pr_branch_sha_or_event_do_not_qualify(self):
        run = {
            "head_sha": SHA,
            "event": "workflow_dispatch",
            "head_branch": "codex/unrelated",
            "status": "completed",
            "conclusion": "success",
        }
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.select_latest_ci_run([run], 40, SHA, PR["head"]["ref"])

        run["head_branch"] = PR["head"]["ref"]
        run["head_sha"] = "b" * 40
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.select_latest_ci_run([run], 40, SHA, PR["head"]["ref"])

        run["head_sha"] = SHA
        run["event"] = "push"
        with self.assertRaises(MODULE.SourceValidationError):
            MODULE.select_latest_ci_run([run], 40, SHA, PR["head"]["ref"])


if __name__ == "__main__":
    unittest.main()

