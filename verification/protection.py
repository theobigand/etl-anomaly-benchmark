"""The proposed protection of ``main``: build it, check it, compare it. Never apply it.

The required status-check contexts are the display names of the jobs in
``ci.yml``. A context that two jobs share is ambiguous, so every job name must be
unique across workflows. ``check`` only reads (``gh api`` GET); applying the
protection is the owner's decision and is described in
``branch_protection_proposal.md``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REPO = "theobigand/etl-anomaly-benchmark"
REQUIRED_CONTEXTS = ("test", "faults")
_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_NAME = re.compile(r"^    name:\s*(.+?)\s*$")


def job_names(directory: Path = WORKFLOWS) -> dict[str, list[str]]:
    """Display name of every job, per workflow file: ``name:`` when given, else the key."""
    found: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.yml")):
        names: list[str] = []
        in_jobs = False
        for line in path.read_text().splitlines():
            if line.startswith("jobs:"):
                in_jobs = True
            elif in_jobs and (match := _JOB.match(line)):
                names.append(match.group(1))
            elif in_jobs and names and (match := _NAME.match(line)):
                names[-1] = match.group(1).strip("\"'")
        found[path.name] = names
    return found


def problems_for_contexts(directory: Path = WORKFLOWS) -> list[str]:
    everywhere = [n for listed in job_names(directory).values() for n in listed]
    problems = []
    for context in REQUIRED_CONTEXTS:
        count = everywhere.count(context)
        if count == 0:
            problems.append(f"required context {context!r}: no job provides it")
        elif count > 1:
            problems.append(f"required context {context!r} is provided by more than one job")
    return problems


def proposed_payload() -> dict:
    return {
        "required_status_checks": {"strict": True, "contexts": list(REQUIRED_CONTEXTS)},
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": True,
        },
        "restrictions": None,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }


def validate_payload(payload: dict) -> list[str]:
    """Reasons the REST API would refuse a branch-protection payload."""
    problems = [
        f"{key} is required"
        for key in (
            "required_status_checks",
            "enforce_admins",
            "required_pull_request_reviews",
            "restrictions",
        )
        if key not in payload
    ]
    checks = payload.get("required_status_checks")
    if isinstance(checks, dict):
        contexts = checks.get("contexts")
        if not isinstance(contexts, list) or not contexts:
            problems.append("required_status_checks.contexts must be a non-empty list")
        if not isinstance(checks.get("strict"), bool):
            problems.append("required_status_checks.strict must be a boolean")
    if "enforce_admins" in payload and not isinstance(payload["enforce_admins"], bool):
        problems.append("enforce_admins must be a boolean (null is refused)")
    reviews = payload.get("required_pull_request_reviews")
    if isinstance(reviews, dict):
        count = reviews.get("required_approving_review_count")
        if not isinstance(count, int) or not 0 <= count <= 6:
            problems.append("required_approving_review_count must be between 0 and 6")
    return problems


def compare(actual: dict, payload: dict) -> list[str]:
    """Differences between the protection GitHub reports and the proposal."""
    problems = []
    checks = actual.get("required_status_checks", {})
    wanted = payload["required_status_checks"]
    if sorted(checks.get("contexts", [])) != sorted(wanted["contexts"]):
        problems.append(f"required contexts are {checks.get('contexts')}, not {wanted['contexts']}")
    if checks.get("strict") != wanted["strict"]:
        problems.append("required_status_checks.strict differs")
    count = actual.get("required_pull_request_reviews", {}).get("required_approving_review_count")
    if count != payload["required_pull_request_reviews"]["required_approving_review_count"]:
        problems.append(f"required_approving_review_count is {count}")
    for key in ("allow_force_pushes", "allow_deletions", "required_conversation_resolution"):
        if actual.get(key, {}).get("enabled") != payload[key]:
            problems.append(f"{key} is {actual.get(key, {}).get('enabled')}, not {payload[key]}")
    if actual.get("enforce_admins", {}).get("enabled") != payload["enforce_admins"]:
        problems.append("enforce_admins differs")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("print", help="print the proposed payload")
    check = sub.add_parser("check", help="read the protection of main and compare it (read-only)")
    check.add_argument("--repo", default=REPO)
    args = parser.parse_args(argv)
    if args.command == "print":
        print(json.dumps(proposed_payload(), indent=2))
        return 0
    done = subprocess.run(
        ["gh", "api", f"repos/{args.repo}/branches/main/protection"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        print(f"main is not protected, or the API refused the read: {done.stderr.strip()}")
        return 1
    problems = compare(json.loads(done.stdout), proposed_payload())
    for problem in problems:
        print(f"protection: {problem}")
    if not problems:
        print("protection: the applied protection matches the proposal")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
