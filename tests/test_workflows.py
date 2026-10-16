"""The CI definitions keep the failure semantics the release gate relies on."""

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _text(name):
    return (WORKFLOWS / name).read_text()


def test_normal_ci_runs_fast_and_faults_on_every_push_and_pull_request():
    text = _text("ci.yml")
    assert "pull_request:" in text and "branches: [main]" in text
    assert "make verify-fast" in text
    assert "make verify-faults" in text


def test_every_checkout_fetches_history_for_the_lineage_anchor():
    for name in ("ci.yml", "verify-release.yml"):
        text = _text(name)
        assert text.count("actions/checkout@") == text.count("fetch-depth: 0"), name


def test_no_workflow_hides_a_failure():
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        assert "continue-on-error" not in text, path.name
        assert "|| true" not in text, path.name


def test_evidence_is_uploaded_even_when_a_profile_fails():
    for name in ("ci.yml", "verify-release.yml"):
        text = _text(name)
        uploads = text.count("actions/upload-artifact@")
        assert uploads and text.count("if: always()") >= uploads, name
        assert "retention-days" in text


def test_release_workflow_is_manual_and_runs_every_profile():
    text = _text("verify-release.yml")
    assert "workflow_dispatch:" in text
    assert "push:" not in text and "pull_request:" not in text
    for target in (
        "make verify-fast",
        "make verify-faults",
        "make verify-deep",
        "make verify-real",
    ):
        assert target in text
    assert "make verify-release" in text


def test_real_runs_only_on_a_runner_the_operator_names():
    text = _text("verify-release.yml")
    assert "inputs.real_runner != ''" in text
    assert re.search(r"runs-on: \$\{\{ inputs\.real_runner \}\}", text)


def test_release_job_waits_for_all_profiles_and_fails_when_any_failed():
    text = _text("verify-release.yml")
    release = text[text.index("  release:") :]
    assert "needs: [fast, faults, deep, real]" in release
    assert "if: always()" in release
    assert "contains(needs.*.result, 'failure')" in release
    assert "make verify-release" in release


def test_workflows_request_read_only_permissions():
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        assert "permissions:\n  contents: read" in text, path.name


def test_verifier_coverage_is_enforced_and_reported_apart_from_fast():
    assert "make verify-tools" in _text("ci.yml")
    makefile = (WORKFLOWS.parents[1] / "Makefile").read_text()
    assert "--cov=verification" in makefile and "--cov-fail-under=100" in makefile
