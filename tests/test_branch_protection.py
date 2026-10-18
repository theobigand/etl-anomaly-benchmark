"""The proposed protection of main is checked against the workflows and the GitHub schema."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from verification import protection

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PROPOSAL = ROOT / "verification" / "branch_protection_proposal.md"


def _write(directory, name, text):
    (directory / name).write_text(text)


def test_check_names_are_the_job_display_names_of_every_workflow(tmp_path):
    _write(tmp_path, "a.yml", "name: a\njobs:\n  one:\n    runs-on: x\n  two:\n    name: Second\n")
    _write(tmp_path, "b.yml", "name: b\njobs:\n  three:\n    runs-on: x\n")
    names = protection.job_names(tmp_path)
    assert names == {"a.yml": ["one", "Second"], "b.yml": ["three"]}


def test_the_repository_check_names_are_unique_across_workflows():
    names = [n for listed in protection.job_names(WORKFLOWS).values() for n in listed]
    assert len(names) == len(set(names)), "two jobs share a status-check context"


def test_the_required_contexts_exist_in_the_pull_request_workflow():
    names = protection.job_names(WORKFLOWS)
    assert set(protection.REQUIRED_CONTEXTS) <= set(names["ci.yml"])
    assert protection.REQUIRED_CONTEXTS == ("test", "faults")


def test_the_long_release_jobs_are_never_required():
    release = set(protection.job_names(WORKFLOWS)["verify-release.yml"])
    assert not release & set(protection.REQUIRED_CONTEXTS)
    assert protection.problems_for_contexts(WORKFLOWS) == []


def test_a_required_context_that_no_job_provides_is_reported(tmp_path):
    _write(tmp_path, "ci.yml", "name: ci\njobs:\n  test:\n    runs-on: x\n")
    problems = protection.problems_for_contexts(tmp_path)
    assert any("faults" in p and "no job" in p for p in problems)


def test_a_context_provided_by_two_jobs_is_ambiguous(tmp_path):
    _write(
        tmp_path, "ci.yml", "name: ci\njobs:\n  test:\n    runs-on: x\n  faults:\n    runs-on: x\n"
    )
    _write(tmp_path, "r.yml", "name: r\njobs:\n  faults:\n    runs-on: x\n")
    problems = protection.problems_for_contexts(tmp_path)
    assert any("faults" in p and "more than one" in p for p in problems)


def test_the_payload_satisfies_the_github_schema():
    payload = protection.proposed_payload()
    assert protection.validate_payload(payload) == []
    assert payload["required_status_checks"] == {"strict": True, "contexts": ["test", "faults"]}
    assert payload["allow_force_pushes"] is False and payload["allow_deletions"] is False
    assert payload["restrictions"] is None


@pytest.mark.parametrize(
    "edit",
    [
        lambda p: p.pop("enforce_admins"),
        lambda p: p.pop("restrictions"),
        lambda p: p["required_status_checks"].update(contexts="test"),
        lambda p: p.update(enforce_admins=None),
        lambda p: p["required_pull_request_reviews"].update(required_approving_review_count=-1),
        lambda p: p["required_status_checks"].update(contexts=[]),
    ],
)
def test_a_payload_the_api_would_refuse_is_reported(edit):
    payload = protection.proposed_payload()
    edit(payload)
    assert protection.validate_payload(payload)


def test_the_payload_in_the_proposal_is_the_one_the_code_builds():
    text = PROPOSAL.read_text()
    block = re.search(r"```json\n(.*?)\n```", text, flags=re.S).group(1)
    assert json.loads(block) == protection.proposed_payload()


def test_the_proposal_keeps_release_certification_apart_from_mergeability():
    text = PROPOSAL.read_text()
    assert "verify-release" in text and "AWAITING_OWNER_APPROVAL" in text
    assert "retour arrière" in text.lower() and "DELETE" in text


def _applied(payload):
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": list(payload["required_status_checks"]["contexts"]),
        },
        "enforce_admins": {"enabled": False},
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": True,
        },
        "required_conversation_resolution": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }


def test_an_applied_protection_is_compared_with_the_proposal():
    payload = protection.proposed_payload()
    assert protection.compare(_applied(payload), payload) == []
    drifted = _applied(payload)
    drifted["allow_force_pushes"]["enabled"] = True
    drifted["required_status_checks"]["contexts"] = ["test"]
    drifted["required_pull_request_reviews"]["required_approving_review_count"] = 1
    problems = protection.compare(drifted, payload)
    assert len(problems) == 3
    assert any("allow_force_pushes" in p for p in problems)
    assert any("contexts" in p for p in problems)


def test_the_check_command_reports_an_unprotected_branch_without_changing_anything(
    monkeypatch, capsys
):
    calls = []

    def fake(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "", "gh: Branch not protected (HTTP 404)")

    monkeypatch.setattr(protection.subprocess, "run", fake)
    assert protection.main(["check", "--repo", "o/r"]) == 1
    assert "not protected" in capsys.readouterr().out
    assert all("PUT" not in c and "DELETE" not in c and "POST" not in c for c in calls[0])
    assert calls[0][:2] == ["gh", "api"]


def test_the_check_command_compares_a_protected_branch(monkeypatch, capsys):
    payload = protection.proposed_payload()
    answer = json.dumps(_applied(payload))
    monkeypatch.setattr(
        protection.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, answer, ""),
    )
    assert protection.main(["check", "--repo", "o/r"]) == 0
    assert "matches the proposal" in capsys.readouterr().out


def test_the_print_command_emits_the_payload(capsys):
    assert protection.main(["print"]) == 0
    assert json.loads(capsys.readouterr().out) == protection.proposed_payload()


def test_the_module_prints_usage():
    done = subprocess.run(
        [sys.executable, "-m", "verification.protection", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "usage:" in done.stdout


def test_every_field_of_the_payload_is_checked_for_type_and_range():
    payload = protection.proposed_payload()
    payload["required_status_checks"]["strict"] = "yes"
    assert any("strict" in p for p in protection.validate_payload(payload))
    payload = protection.proposed_payload()
    payload["enforce_admins"] = None
    assert any("enforce_admins" in p for p in protection.validate_payload(payload))
    payload = protection.proposed_payload()
    payload["required_pull_request_reviews"]["required_approving_review_count"] = 9
    assert any("approving" in p for p in protection.validate_payload(payload))
    assert protection.validate_payload({}) != []


def test_every_drift_from_the_proposal_is_named():
    payload = protection.proposed_payload()
    drifted = _applied(payload)
    drifted["required_status_checks"]["strict"] = False
    drifted["enforce_admins"]["enabled"] = True
    drifted["required_conversation_resolution"]["enabled"] = False
    drifted["allow_deletions"]["enabled"] = True
    problems = protection.compare(drifted, payload)
    assert any("strict" in p for p in problems)
    assert any("enforce_admins" in p for p in problems)
    assert any("required_conversation_resolution" in p for p in problems)
    assert any("allow_deletions" in p for p in problems)


def test_the_check_command_exits_nonzero_on_drift(monkeypatch, capsys):
    payload = protection.proposed_payload()
    drifted = _applied(payload)
    drifted["allow_force_pushes"]["enabled"] = True
    monkeypatch.setattr(
        protection.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, json.dumps(drifted), ""),
    )
    assert protection.main(["check"]) == 1
    assert "protection: allow_force_pushes" in capsys.readouterr().out
