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
    assert "push:" not in text
    # the only automatic trigger is a change to this very file
    triggers = text[text.index("on:") : text.index("permissions:")]
    assert triggers.count("pull_request:") == 1
    assert triggers.count('- ".github/workflows/verify-release.yml"') == 1
    assert triggers.count("paths:") == 1
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
    assert "needs: [fast, static, reproduce, faults, deep, real]" in release
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


def test_the_release_job_keeps_downloaded_bundles_outside_the_checkout():
    # An untracked download folder inside the workspace made the worktree
    # look dirty, and the release gate rejects a dirty worktree.
    text = _text("verify-release.yml")
    release = text[text.index("  release:") :]
    assert "path: bundles" not in release
    assert "path: ${{ runner.temp }}/bundles" in release
    assert '"$RUNNER_TEMP"/bundles/*.tgz' in release


def test_the_deep_job_exports_its_surviving_mutants_for_inspection():
    text = _text("verify-release.yml")
    deep = text[text.index("  deep:") : text.index("  real:")]
    from verification import bundles

    assert "mutants/results.txt" in bundles.KINDS["deep"]
    assert "verification.bundles pack deep" in deep.split("Bundle deep evidence")[1]
    makefile = (WORKFLOWS.parents[1] / "Makefile").read_text()
    target = makefile[makefile.index("verify-deep:") : makefile.index("verify-faults:")]
    assert "mutmut results --all true > mutants/results.txt" in target
    assert "--results mutants/results.txt" in target


def test_the_release_workflow_produces_every_evidence_kind_the_policy_requires():
    import json

    policy = json.loads((WORKFLOWS.parents[1] / "verification" / "release_policy.json").read_text())
    text = _text("verify-release.yml")
    release = text[text.index("  release:") :]
    produced = {"fast", "deep", "faults", "real", "tools", "types", "reproduction"}
    from verification import bundles

    packed = {name for names in bundles.KINDS.values() for name in names}
    for kind in produced:
        assert f"experiments/results/evidence/{kind}.json" in packed, kind
    assert set(policy["required"]) <= produced
    assert "needs: [fast, static, reproduce, faults, deep, real]" in release
    assert "mypy==2.4.0" in text and "pandas-stubs==3.0.5.260914" in text
    assert policy["typing_pins"] == {"mypy": "2.4.0", "pandas-stubs": "3.0.5.260914"}


def test_the_certification_matrix_documents_every_policy_entry():
    import json

    root = WORKFLOWS.parents[1] / "verification"
    policy = json.loads((root / "release_policy.json").read_text())
    text = (root / "certification.md").read_text()
    for section in ("required", "optional", "deferred", "not_applicable"):
        for name in policy[section]:
            assert name in text, name
    assert "Ce que CERTIFIED ne prouve pas" in text
    assert "local-unattested" in text
    for reason in (*policy["deferred"].values(), *policy["optional"].values()):
        assert reason.strip()


def test_the_reproduction_job_replays_public_data_only_and_uses_the_locked_linux_environment():
    text = _text("verify-release.yml")
    job = text[text.index("  reproduce:") : text.index("  faults:")]
    assert "python experiments/fetch_cardio.py" in job
    assert "make verify-reproduce" in job
    assert "data/" not in job.replace("python experiments/fetch_cardio.py", "")
    lock = (WORKFLOWS.parents[1] / "verification/environment/linux-x86_64-py311.lock.txt").exists()
    assert lock and 'python-version: "3.11"' in job


def test_evidence_travels_only_in_allowlisted_bundles():
    from verification import bundles

    text = _text("verify-release.yml")
    assert "tar czf" not in text and "tar xzf" not in text
    for kind in bundles.KINDS:
        assert f"python -m verification.bundles pack {kind} --allow-missing" in text, kind
    assert text.count("python -m verification.bundles unpack") == 1


def test_the_real_job_refuses_a_hosted_runner_and_packs_only_the_real_reports():
    text = _text("verify-release.yml")
    job = text[text.index("  real:") : text.index("  release:")]
    assert 'test "$RUNNER_ENVIRONMENT" = self-hosted' in job
    assert job.index("RUNNER_ENVIRONMENT") < job.index("make verify-real")
    assert "verification.bundles pack real" in job
    assert "data/" not in job


def test_the_documented_real_procedure_matches_the_workflow():
    root = WORKFLOWS.parents[1] / "verification"
    text = (root / "real_evidence.md").read_text()
    for needle in ("real_runner", "self-hosted", "RUNNER_ENVIRONMENT", "verification.bundles"):
        assert needle in text, needle


def test_the_real_job_runs_only_a_reviewed_revision_from_the_default_branch():
    text = _text("verify-release.yml")
    job = text[text.index("  real:") : text.index("  release:")]
    # The private datasets are only exposed to code that is on the default branch
    # and whose commit the operator names in the dispatch.
    assert "approved_sha:" in text[: text.index("jobs:")]
    assert "github.event.repository.default_branch" in job
    assert job.index("approved_sha") < job.index("actions/checkout")
    assert "persist-credentials: false" in job
    assert "pull_request" not in job
    assert "real_preflight" in job
    assert job.index("python -m venv") < job.index("install -e") < job.index("real_preflight")


def test_the_real_job_links_the_datasets_from_the_runner_and_never_copies_them():
    text = _text("verify-release.yml")
    job = text[text.index("  real:") : text.index("  release:")]
    assert 'test -n "$THESIS_DATA_DIR"' in job
    assert "ln -s" in job and " cp " not in job and "rsync" not in job
    assert job.index("ln -s") < job.index("real_preflight") < job.index("make verify-real")


def test_the_runner_provisioning_script_is_safe_by_default_and_holds_no_secret(tmp_path):
    import subprocess

    script = WORKFLOWS.parents[1] / "verification" / "runner" / "provision_runner.sh"
    text = script.read_text()
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text
    assert "sudo " not in text.replace("run with sudo", "") and "curl" not in text
    assert "--token <token" in text and "ghp_" not in text and "AAAA" not in text
    assert "0400" in text and "0700" in text and "--ephemeral" in text
    archive = tmp_path / "runner.tgz"
    archive.write_bytes(b"x")
    done = subprocess.run(
        ["bash", str(script)],
        env={
            "PATH": "/usr/bin:/bin",
            "RUNNER_ARCHIVE": str(archive),
            "RUNNER_SHA256": "0" * 64,
            "DATA_SOURCE": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1 and "checksum differs" in done.stderr
