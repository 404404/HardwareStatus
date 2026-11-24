#!/usr/bin/env python3
"""Fail-closed trust and CI gate for a manually requested 2.8 source SHA."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TRUSTED_REPOSITORY = "404404/HardwareStatus"
BASE_BRANCH = "2.0"
REQUIRED_CI_JOBS = frozenset(
    {"contracts", "go", "python", "frontend", "compose", "images", "security"}
)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class SourceValidationError(ValueError):
    pass


def validate_sha(source_sha: str) -> None:
    if not isinstance(source_sha, str) or not SHA_PATTERN.fullmatch(source_sha):
        raise SourceValidationError("source SHA must be a full lowercase 40-character Git SHA")


def select_trusted_pull_request(pulls: list[dict], source_sha: str) -> dict:
    matches = []
    for pull in pulls:
        head = pull.get("head") or {}
        base = pull.get("base") or {}
        head_repo = head.get("repo") or {}
        merged = bool(pull.get("merged_at")) or bool(pull.get("merged"))
        state = pull.get("state")
        if (
            head.get("sha") == source_sha
            and head_repo.get("full_name") == TRUSTED_REPOSITORY
            and base.get("ref") == BASE_BRANCH
            and ((state == "open" and not pull.get("draft")) or (state == "closed" and merged))
        ):
            matches.append(pull)
    if len(matches) != 1:
        raise SourceValidationError(
            "source must be the current, non-draft head of one same-repository PR to 2.0, or its merged head"
        )
    return matches[0]


def select_latest_ci_run(runs: list[dict], pull_number: int, source_sha: str) -> dict:
    matches = []
    for run in runs:
        pull_numbers = {
            item.get("number")
            for item in (run.get("pull_requests") or [])
            if isinstance(item, dict)
        }
        if (
            run.get("head_sha") == source_sha
            and run.get("event") == "pull_request"
            and pull_number in pull_numbers
        ):
            matches.append(run)
    if not matches:
        raise SourceValidationError("no pull_request CI run exists for the exact source SHA")
    latest = max(matches, key=lambda item: (item.get("run_number", 0), item.get("run_attempt", 0)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise SourceValidationError("latest full CI run for the exact source SHA is not successful")
    return latest


def validate_ci_jobs(jobs: list[dict]) -> None:
    successful = {
        job.get("name")
        for job in jobs
        if isinstance(job, dict) and job.get("conclusion") == "success"
    }
    missing = REQUIRED_CI_JOBS - successful
    if missing:
        raise SourceValidationError("full CI is incomplete or unsuccessful")


def _get_json(path: str, token: str, query: dict[str, str] | None = None):
    url = "https://api.github.com" + path
    if query:
        url += "?" + urlencode(query)
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "User-Agent": "HardwareStatus-candidate-source-verifier",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Never include request headers, response bodies, or the token in diagnostics.
        raise SourceValidationError("GitHub source/CI verification API is unavailable") from exc


def verify_source(source_sha: str, token: str) -> tuple[int, int]:
    validate_sha(source_sha)
    if not token:
        raise SourceValidationError("GitHub read token is unavailable")

    pulls = _get_json(
        f"/repos/{TRUSTED_REPOSITORY}/commits/{source_sha}/pulls",
        token,
        {"per_page": "100"},
    )
    if not isinstance(pulls, list):
        raise SourceValidationError("GitHub returned an invalid pull request response")
    pull = select_trusted_pull_request(pulls, source_sha)
    pull_number = pull.get("number")
    if not isinstance(pull_number, int):
        raise SourceValidationError("trusted pull request has no valid number")

    workflow_runs = _get_json(
        f"/repos/{TRUSTED_REPOSITORY}/actions/workflows/ci.yml/runs",
        token,
        {"head_sha": source_sha, "event": "pull_request", "per_page": "100"},
    )
    runs = workflow_runs.get("workflow_runs") if isinstance(workflow_runs, dict) else None
    if not isinstance(runs, list):
        raise SourceValidationError("GitHub returned an invalid CI runs response")
    run = select_latest_ci_run(runs, pull_number, source_sha)
    run_id = run.get("id")
    if not isinstance(run_id, int):
        raise SourceValidationError("successful CI run has no valid ID")

    jobs_response = _get_json(
        f"/repos/{TRUSTED_REPOSITORY}/actions/runs/{run_id}/jobs",
        token,
        {"per_page": "100"},
    )
    jobs = jobs_response.get("jobs") if isinstance(jobs_response, dict) else None
    if not isinstance(jobs, list):
        raise SourceValidationError("GitHub returned an invalid CI jobs response")
    validate_ci_jobs(jobs)
    return pull_number, run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if repository.lower() != TRUSTED_REPOSITORY.lower():
        print("SOURCE_VALIDATION=FAIL: unexpected repository", file=sys.stderr)
        return 1
    try:
        pull_number, run_id = verify_source(args.source_sha, os.environ.get("GITHUB_TOKEN", ""))
    except SourceValidationError as exc:
        print("SOURCE_VALIDATION=FAIL: " + str(exc), file=sys.stderr)
        return 1
    print(f"SOURCE_SHA={args.source_sha}")
    print(f"TRUSTED_PULL_REQUEST={pull_number}")
    print(f"FULL_CI_RUN_ID={run_id}")
    print("SOURCE_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
