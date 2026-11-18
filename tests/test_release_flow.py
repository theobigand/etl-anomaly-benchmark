"""Release decision details: invalid profiles stay out of later checks; freshness; the command."""

import json
import subprocess

import pytest

from tests.test_release_contracts import (
    CURRENT,
    _assess,
    _doc,
    _policy,
    _valid_documents,  # noqa: F401  (autouse fixture of the contracts file)
)
from verification import evidence_schema, release


def _only_invalid(monkeypatch, kinds):
    def validate(doc, root=None):
        return ["bad"] if doc["kind"] in kinds else []

    monkeypatch.setattr(evidence_schema, "validate", validate)


def test_an_invalid_typing_report_is_not_checked_against_the_typing_pins(monkeypatch):
    _only_invalid(monkeypatch, {"types"})
    docs = {"fast": _doc("fast"), "types": _doc("types", result={"mypy": "9.9"})}
    assert _assess(docs)["reasons"] == ["types: bad"]


def test_an_invalid_real_report_gets_no_further_reasons_about_its_execution(monkeypatch):
    _only_invalid(monkeypatch, {"real"})
    docs = {"fast": _doc("fast"), "real": _doc("real", result={"required": [], "datasets": []})}
    del docs["real"]["execution"]
    report = _assess(docs, policy=_policy(required=["fast", "real"]))
    assert report["reasons"] == ["real: bad"]


def test_an_invalid_profile_does_not_stop_the_listing_of_the_executions_that_follow_it(monkeypatch):
    _only_invalid(monkeypatch, {"fast"})
    docs = {"fast": _doc("fast"), "types": _doc("types")}
    assert _assess(docs)["executions"] == {"types": "local"}


def test_a_deep_report_without_a_result_is_refused_as_not_risk_tiered():
    docs = {"fast": _doc("fast"), "deep": _doc("deep")}
    del docs["deep"]["result"]
    report = _assess(docs, policy=_policy(version=2, required=["fast", "deep"]))
    assert report["reasons"] == ["deep: current release requires risk-tiered campaign evidence"]
    assert report["profiles"]["deep"] == "INVALID"


def test_every_reason_is_kept_when_a_hosted_real_run_and_lineage_problems_come_with_others():
    real = _doc(
        "real",
        result={"required": ["cardio"], "datasets": [], "acquisition": None},
        execution={
            "ci": True,
            "run_id": "1",
            "runner_environment": "github-hosted",
            "runner_name": "r",
        },
    )
    current = {**CURRENT, "worktree_dirty": True}
    lineage = {"legacy": [], "problems": {"run_x": ["stale", "odd"]}}
    report = _assess(
        {"fast": _doc("fast"), "real": real},
        policy=_policy(required=["fast", "real"]),
        current=current,
        lineage=lineage,
    )
    reasons = report["reasons"]
    assert reasons[0] == "the worktree is dirty: a release needs a clean source"
    assert any(r.startswith("real: produced by a CI run on a hosted runner") for r in reasons)
    assert reasons[-2:] == ["lineage run_x: stale", "lineage run_x: odd"]


def test_two_packages_that_drift_from_the_lock_are_listed_together_with_a_comma():
    locked = {name: "0.0" for name in release.RESULT_PACKAGES}
    report = _assess(locked=locked)
    reason = report["reasons"][0]
    assert reason.startswith("the environment differs from the recorded lock: ")
    listed = reason.removeprefix("the environment differs from the recorded lock: ")
    assert ", " in listed and listed.count("(lock 0.0)") == len(release.RESULT_PACKAGES)


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit(root, name, text, message):
    (root / name).write_text(text)
    _git(root, "add", name)
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_revision_on_another_branch_is_not_fresh_even_when_only_documents_differ(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    base = _commit(tmp_path, "notes.md", "base", "base")
    _git(tmp_path, "checkout", "-q", "-b", "side")
    side = _commit(tmp_path, "side.md", "side", "side")
    _git(tmp_path, "checkout", "-q", "main")
    _commit(tmp_path, "other.md", "other", "other")
    fresh = release.freshness(tmp_path)
    assert fresh(base) is True
    assert fresh(side) is False


def test_freshness_compares_commits_not_the_working_tree(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    head = _commit(tmp_path, "script.py", "x = 1\n", "code")
    (tmp_path / "script.py").write_text("x = 2\n")
    assert release.freshness(tmp_path)(head) is True


def test_freshness_runs_git_in_the_given_root_and_reads_its_output_as_text(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="docs/a.md\n", stderr="")

    monkeypatch.setattr(release.subprocess, "run", run)
    assert release.freshness(tmp_path)("abc") is True
    assert [c for c, _ in calls] == [
        ["git", "merge-base", "--is-ancestor", "abc", "HEAD"],
        ["git", "diff", "--name-only", "abc", "HEAD"],
    ]
    for _, kwargs in calls:
        assert kwargs == {"cwd": tmp_path, "capture_output": True, "text": True, "check": False}


def test_the_command_checks_the_paper_against_the_published_claims_and_writes_the_report(
    monkeypatch, tmp_path, capsys
):
    seen = {}
    config = {"roots": []}
    monkeypatch.setattr(release.mutation_scope, "load", lambda: config)
    monkeypatch.setattr(
        release.mutation_scope, "inventory", lambda root, cfg: seen.update(inv=(root, cfg)) or ["f"]
    )
    monkeypatch.setattr(release, "load_policy", lambda: {"required": ["fast"], "version": 1})
    monkeypatch.setattr(evidence_schema, "collect_source", lambda: CURRENT)
    monkeypatch.setattr(release.claims, "load", lambda: "published")
    monkeypatch.setattr(release.claims, "check_run", lambda *a, **k: ["run problem"])
    monkeypatch.setattr(
        release.claims,
        "check_paper",
        lambda published, text: seen.update(paper=(published, text)) or [],
    )
    for name, value in (("reference_hashes", {}), ("archive_lineage", {}), ("locked_versions", {})):
        monkeypatch.setattr(release, name, lambda value=value: value)
    monkeypatch.setattr(release, "freshness", lambda: None)
    monkeypatch.setattr(release, "load_docs", lambda directory, kinds: {})
    report = {"status": "CERTIFIED", "attestation": "x", "reasons": ["why"], "b": 1, "a": 2}
    monkeypatch.setattr(release, "assess", lambda *a, **k: seen.update(kwargs=k) or report)
    out = tmp_path / "deeper" / "release.json"
    assert release.main(["--output", str(out)]) == 0
    assert seen["paper"] == ("published", (release.ROOT / "paper" / "main.tex").read_text())
    assert seen["inv"] == (release.ROOT, config)
    assert seen["kwargs"]["scope"] == {"inventory": ["f"], "config": config}
    assert seen["kwargs"]["claims"] == ["run problem"]
    assert out.read_text() == json.dumps(report, indent=2, sort_keys=True) + "\n"
    assert capsys.readouterr().out == "release: CERTIFIED (x)\n  - why\n"


def test_the_command_help_describes_the_release_decision(capsys):
    with pytest.raises(SystemExit):
        release.main(["--help"])
    assert release.__doc__.strip().splitlines()[0] in " ".join(capsys.readouterr().out.split())
