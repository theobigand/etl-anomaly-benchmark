"""The release gate certifies only complete, consistent, clean evidence."""

import copy
import json
import subprocess
import sys

import pytest

from tests.test_evidence_schema import (
    ENVIRONMENT,
    RESULT_VERSIONS,
    SOURCE,
    _deep,
    _fast,
    _matrix,
    _real,
    _reproduction,
    _tools,
    _types,
)
from verification import evidence_schema, release

KINDS = tuple(release.load_policy()["required"])


@pytest.fixture(autouse=True)
def _two_required_datasets(monkeypatch):
    monkeypatch.setattr(evidence_schema, "REQUIRED_DATASETS", ("a", "b"))
    # the verdict must not depend on whether the suite itself runs under CI
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)


def _docs(tmp_path):
    return {
        "fast": _fast(tmp_path),
        "deep": _deep(tmp_path),
        "faults": _matrix(tmp_path),
        "real": _real(tmp_path),
        "tools": _tools(tmp_path),
        "types": _types(tmp_path),
        "reproduction": _reproduction(tmp_path),
    }


def _assess(tmp_path, docs=None, current=None, **kwargs):
    kwargs.setdefault("manifest", {"a": "1" * 64, "b": "2" * 64})
    kwargs.setdefault("lineage", {"legacy": [], "problems": {}})
    kwargs.setdefault("locked", dict(RESULT_VERSIONS))
    kwargs.setdefault("policy", release.load_policy())
    kwargs.setdefault("fresh", None)
    kwargs.setdefault("scope", {"inventory": ["src/x.py"], "config": {"no_mutants": {}}})
    return release.assess(
        docs if docs is not None else _docs(tmp_path),
        current=current or copy.deepcopy(SOURCE),
        root=tmp_path,
        **kwargs,
    )


def test_complete_consistent_evidence_is_certified_but_not_independently_attested(tmp_path):
    report = _assess(tmp_path)
    assert report["status"] == "CERTIFIED", report["reasons"]
    assert report["reasons"] == []
    assert report["attestation"] == "local-unattested"
    assert set(report["profiles"]) == set(KINDS)


def test_ci_run_is_recorded_but_never_called_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    report = _assess(tmp_path)
    assert report["attestation"] == "ci-run:42 (not independently attested)"


@pytest.mark.parametrize("kind", KINDS)
def test_missing_evidence_is_incomplete(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind] = None
    report = _assess(tmp_path, docs)
    assert report["status"] == "INCOMPLETE"
    assert any(kind in reason and "missing" in reason for reason in report["reasons"])


@pytest.mark.parametrize("kind", KINDS)
def test_a_malformed_document_is_rejected(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind]["status"] = "OK"
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any(kind in reason for reason in report["reasons"])


def test_failed_profiles_reject_and_unfinished_ones_are_incomplete(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"] = _deep(tmp_path, killed=90, survived=10)
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs["deep"] = _deep(tmp_path, killed=99, survived=0, check_was_interrupted_by_user=1)
    assert _assess(tmp_path, docs)["status"] == "INCOMPLETE"
    docs = _docs(tmp_path)
    docs["faults"] = _matrix(tmp_path, names=["f1"])
    assert _assess(tmp_path, docs)["status"] == "INCOMPLETE"


def test_evidence_from_another_revision_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"]["source"]["revision"] = "c" * 40
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("revision" in reason for reason in report["reasons"])


def test_evidence_must_match_the_current_head_and_science(tmp_path):
    other = {**SOURCE, "revision": "d" * 40}
    assert _assess(tmp_path, current=other)["status"] == "REJECTED"
    other = {**SOURCE, "scientific_fingerprint": "e" * 64}
    report = _assess(tmp_path, current=other)
    assert report["status"] == "REJECTED"
    assert any("fingerprint" in reason for reason in report["reasons"])


def test_a_dirty_worktree_rejects_certification(tmp_path):
    report = _assess(tmp_path, current={**SOURCE, "worktree_dirty": True})
    assert report["status"] == "REJECTED"
    assert any("dirty" in reason for reason in report["reasons"])
    docs = _docs(tmp_path)
    docs["fast"]["source"]["worktree_dirty"] = True
    assert any("dirty" in r for r in _assess(tmp_path, docs)["reasons"])


def test_a_changed_artifact_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    (tmp_path / "coverage.json").write_text("{}")
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("hash" in reason for reason in report["reasons"])


def test_dataset_hashes_must_match_the_reference_manifest(tmp_path):
    report = _assess(tmp_path, manifest={"a": "1" * 64, "b": "9" * 64})
    assert report["status"] == "REJECTED"
    assert any("dataset b" in reason for reason in report["reasons"])
    assert _assess(tmp_path, manifest={"a": "1" * 64})["status"] == "REJECTED"


def test_legacy_experiment_records_keep_the_release_incomplete(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": ["run_synthetic"], "problems": {}})
    assert report["status"] == "INCOMPLETE"
    assert any("clean replay" in reason for reason in report["reasons"])


def test_broken_lineage_rejects(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": [], "problems": {"run_curves": ["stale"]}})
    assert report["status"] == "REJECTED"
    assert any("run_curves" in reason for reason in report["reasons"])


def test_rejection_outranks_incomplete(tmp_path):
    docs = _docs(tmp_path)
    docs["faults"] = None
    docs["deep"]["status"] = "OK"
    assert _assess(tmp_path, docs)["status"] == "REJECTED"


def test_command_writes_a_report_and_fails_unless_certified(tmp_path):
    out = tmp_path / "release.json"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "verification.release",
            "--evidence",
            str(tmp_path / "none"),
            "--output",
            str(out),
        ],
        cwd=release.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    report = json.loads(out.read_text())
    assert report["status"] in ("INCOMPLETE", "REJECTED")
    assert "release: " in done.stdout
    assert ENVIRONMENT  # fixtures imported for the shared builders


def test_dirty_worktree_runs_are_kept_as_history_but_block_certification(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": [], "dirty": ["run_curves"], "problems": {}})
    assert report["status"] == "INCOMPLETE"
    assert any(
        "dirty worktree" in reason and "run_curves" in reason for reason in report["reasons"]
    )


# --- scientific environment compatibility (#40) ---


def _retarget(docs, kind, **changes):
    environment = docs[kind]["environment"]
    for key, value in changes.items():
        if key in ("python", "platform"):
            environment[key] = value
        else:
            environment["packages"][key] = value


def test_every_profile_must_record_each_result_affecting_version(tmp_path):
    docs = _docs(tmp_path)
    _retarget(docs, "faults", pyod=None)
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("faults" in r and "pyod" in r and "version" in r for r in report["reasons"])


def test_profiles_with_different_result_versions_are_not_aggregated(tmp_path):
    docs = _docs(tmp_path)
    _retarget(docs, "deep", **{"scikit-learn": "1.8"})
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    reason = next(r for r in report["reasons"] if "scikit-learn" in r)
    assert "deep=1.8" in reason and "fast=1.9" in reason


def test_python_minor_versions_must_agree_but_patch_levels_may_differ(tmp_path):
    docs = _docs(tmp_path)
    _retarget(docs, "real", python="3.11.9")
    assert _assess(tmp_path, docs)["status"] == "CERTIFIED"
    _retarget(docs, "real", python="3.12.1")
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("python" in r and "3.12" in r for r in report["reasons"])


def test_cross_platform_evidence_is_accepted_and_labelled(tmp_path):
    docs = _docs(tmp_path)
    _retarget(docs, "deep", platform="Linux-6.17")
    report = _assess(tmp_path, docs)
    assert report["status"] == "CERTIFIED", report["reasons"]
    assert report["environment"]["mode"] == "cross-platform"
    assert sorted(report["environment"]["platforms"]) == ["Linux-6.17", "test"]


def test_one_platform_with_locked_versions_is_an_exact_environment(tmp_path):
    report = _assess(tmp_path)
    assert report["environment"]["mode"] == "exact-environment"
    assert report["environment"]["packages"]["numpy"] == "2.0"


def test_versions_that_differ_from_the_recorded_lock_are_incomplete(tmp_path):
    report = _assess(tmp_path, locked={**RESULT_VERSIONS, "numpy": "2.4.6"})
    assert report["status"] == "INCOMPLETE"
    assert any("numpy" in r and "2.0" in r and "2.4.6" in r for r in report["reasons"])


def test_a_missing_lock_is_incomplete_not_ignored(tmp_path):
    report = _assess(tmp_path, locked={})
    assert report["status"] == "INCOMPLETE"
    assert any("lock" in r and "pandas" in r for r in report["reasons"])


def test_the_lock_versions_are_read_from_the_recorded_files(tmp_path):
    (tmp_path / "conda-test.explicit.txt").write_text(
        "@EXPLICIT\n"
        "https://conda.anaconda.org/conda-forge/osx-arm64/numpy-2.4.6-py311hbd_0.conda#abc\n"
        "https://conda.anaconda.org/conda-forge/osx-arm64/scikit-learn-1.9.1-np2py311_1.conda#d\n"
    )
    (tmp_path / "pip-freeze.txt").write_text("# comment\npyod==3.6.7\nrich==1.0\n")
    found = release.locked_versions(tmp_path)
    assert found == {"numpy": "2.4.6", "scikit-learn": "1.9.1", "pyod": "3.6.7"}
    assert release.locked_versions(tmp_path / "none") == {}


def test_the_recorded_lock_covers_every_result_affecting_package():
    assert set(release.locked_versions()) >= set(release.RESULT_PACKAGES)


# --- mutation scope completeness (#41) ---


def test_a_mutation_scope_that_shrank_is_rejected_whatever_the_score(tmp_path):
    scope = {"inventory": ["src/x.py", "src/y.py"], "config": {"no_mutants": {}}}
    report = _assess(tmp_path, scope=scope)
    assert report["status"] == "REJECTED"
    assert any("src/y.py" in r and "not mutated" in r for r in report["reasons"])


def test_a_mutated_file_outside_the_recorded_scope_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"]["result"]["mutated_files"] = ["src/x.py", "src/z.py"]
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("src/z.py" in r for r in report["reasons"])


def test_a_file_without_mutant_needs_a_declared_reason(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"]["result"]["mutated_files"] = []
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    scope = {"inventory": ["src/x.py"], "config": {"no_mutants": {"src/x.py": "re-exports"}}}
    assert _assess(tmp_path, docs, scope=scope)["status"] == "CERTIFIED"


# --- performance evidence follows the measurement fingerprint (#43) ---


def _performance(state, reasons=()):
    return {"legacy": [], "problems": {}, "performance": {"scaling": (state, list(reasons))}}


def test_stale_performance_evidence_blocks_certification_but_not_through_the_science(tmp_path):
    report = _assess(tmp_path, lineage=_performance("STALE", ["the measurement method changed"]))
    assert report["status"] == "INCOMPLETE"
    assert any("scaling" in r and "measurement method changed" in r for r in report["reasons"])


def test_bound_and_legacy_performance_evidence_do_not_block(tmp_path):
    assert _assess(tmp_path, lineage=_performance("BOUND"))["status"] == "CERTIFIED"
    report = _assess(tmp_path, lineage=_performance("LEGACY"))
    assert report["status"] == "CERTIFIED"
    assert report["performance"] == {"scaling": "LEGACY"}


def test_a_gate_only_change_leaves_the_scientific_lineage_untouched(tmp_path):
    report = _assess(tmp_path, lineage=_performance("STALE", ["x"]))
    assert not any("lineage" in r for r in report["reasons"])


# --- the complete certification contract (#39) ---

NEW_KINDS = ("tools", "types", "reproduction")


def test_the_contract_requires_the_seven_evidence_kinds_and_not_performance():
    policy = release.load_policy()
    assert set(policy["required"]) == {"fast", "deep", "faults", "real", *NEW_KINDS}
    assert "performance" in policy["optional"] and "performance" not in policy["required"]
    assert set(policy["required"]) == set(evidence_schema.KINDS)


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_omitting_a_newly_mandatory_check_is_incomplete(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind] = None
    report = _assess(tmp_path, docs)
    assert report["status"] == "INCOMPLETE"
    assert any(kind in r and "missing" in r for r in report["reasons"])
    assert report["profiles"][kind] == "MISSING"


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_a_tampered_newly_mandatory_document_is_rejected(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind]["status"] = "OK"
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs[kind]["source"]["revision"] = "c" * 40
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs[kind]["source"]["scientific_fingerprint"] = "e" * 64
    assert _assess(tmp_path, docs)["status"] == "REJECTED"


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_a_changed_artifact_of_a_newly_mandatory_check_is_rejected(tmp_path, kind):
    docs = _docs(tmp_path)
    name = next(iter(docs[kind]["artifacts"]))
    (tmp_path / name).write_text("{}")
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any(kind in r and "hash" in r for r in report["reasons"])


def test_failed_typing_or_verifier_coverage_rejects(tmp_path):
    docs = _docs(tmp_path)
    docs["types"] = _types(tmp_path, status="FAIL", problems=["new typing error: x"])
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs["tools"] = _tools(tmp_path, covered_lines=9)
    assert _assess(tmp_path, docs)["status"] == "REJECTED"


def test_an_unrun_locked_reproduction_keeps_the_release_incomplete(tmp_path):
    docs = _docs(tmp_path)
    levels = {"archive": "PASS", "same_environment": "PASS", "locked_environment": "NOT_RUN"}
    docs["reproduction"] = _reproduction(tmp_path, levels, outcome="INCOMPLETE")
    report = _assess(tmp_path, docs)
    assert report["status"] == "INCOMPLETE"
    assert any("reproduction profile is INCOMPLETE" in r for r in report["reasons"])


def test_typing_evidence_from_other_tool_versions_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    docs["types"] = _types(tmp_path, mypy="1.0.0")
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("mypy" in r and "1.0.0" in r and "2.4.0" in r for r in report["reasons"])
    docs["types"] = _types(tmp_path, **{"pandas-stubs": None})
    assert any("pandas-stubs" in r for r in _assess(tmp_path, docs)["reasons"])


def test_typing_evidence_does_not_need_the_scientific_package_versions(tmp_path):
    docs = _docs(tmp_path)
    for package in release.RESULT_PACKAGES:
        docs["types"]["environment"]["packages"][package] = None
    assert _assess(tmp_path, docs)["status"] == "CERTIFIED"


def test_the_report_states_the_policy_it_applied(tmp_path):
    report = _assess(tmp_path)
    assert report["policy"]["version"] == 1
    assert set(report["policy"]["required"]) == set(KINDS)
    assert "independent_attestation" in report["policy"]["deferred"]


def test_an_unknown_policy_version_is_refused(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"version": 7, "required": {}}))
    with pytest.raises(ValueError, match="version"):
        release.load_policy(path)


# --- the trust boundary of REAL evidence (#44) ---

SELF_HOSTED = {"ci": True, "run_id": "5", "runner_environment": "self-hosted", "runner_name": "lab"}
HOSTED = {"ci": True, "run_id": "6", "runner_environment": "github-hosted", "runner_name": "gh"}


def test_real_evidence_from_an_authorized_self_hosted_runner_is_accepted(tmp_path):
    docs = _docs(tmp_path)
    docs["real"] = _real(tmp_path, execution=SELF_HOSTED)
    report = _assess(tmp_path, docs)
    assert report["status"] == "CERTIFIED", report["reasons"]
    assert report["executions"]["real"] == "self-hosted"


def test_real_evidence_claiming_a_hosted_runner_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    docs["real"] = _real(tmp_path, execution=HOSTED)
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("real" in r and "hosted" in r for r in report["reasons"])


def test_real_evidence_that_does_not_say_where_it_ran_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    del docs["real"]["execution"]
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("real" in r and "execution context" in r for r in report["reasons"])


def test_a_local_real_run_is_accepted_but_stays_unattested(tmp_path):
    report = _assess(tmp_path)
    assert report["status"] == "CERTIFIED"
    assert report["executions"]["real"] == "local"
    assert report["attestation"] == "local-unattested"


def test_other_profiles_may_run_on_hosted_runners(tmp_path):
    docs = _docs(tmp_path)
    docs["fast"]["execution"] = HOSTED
    assert _assess(tmp_path, docs)["status"] == "CERTIFIED"


def test_forged_real_evidence_is_refused(tmp_path):
    docs = _docs(tmp_path)
    docs["real"]["result"]["datasets"][0]["sha256"] = "9" * 64
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("dataset a" in r for r in report["reasons"])
    docs = _docs(tmp_path)
    docs["real"]["result"]["datasets"][0]["status"] = "NOT_RUN"
    docs["real"]["status"] = "PASS"
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs["real"]["source"]["revision"] = "c" * 40
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs["real"] = None
    assert _assess(tmp_path, docs)["status"] == "INCOMPLETE"


# --- evidence stays current across documentation-only commits ---


def _git_repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src/m.py").write_text("x = 1\n")
    (root / "README.md").write_text("doc\n")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t"}
    env |= {"GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"}

    def git(*args):
        done = subprocess.run(
            ["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True
        )
        return done.stdout.strip()

    git("init", "-q")
    git("add", ".")
    git("commit", "-q", "-m", "first")
    return root, git


def test_the_evidence_revision_may_be_an_ancestor_when_only_documentation_changed(tmp_path):
    root, git = _git_repo(tmp_path)
    old = git("rev-parse", "HEAD")
    (root / "README.md").write_text("more\n")
    git("commit", "-qam", "docs")
    fresh = release.freshness(root)
    assert fresh(old) is True
    assert fresh(git("rev-parse", "HEAD")) is True
    (root / "src/m.py").write_text("x = 2\n")
    git("commit", "-qam", "code")
    assert fresh(old) is False
    assert fresh("d" * 40) is False


def test_documentation_commits_after_the_run_keep_the_release_certifiable(tmp_path):
    ancestor = "c" * 40
    docs = _docs(tmp_path)
    for doc in docs.values():
        doc["source"]["revision"] = ancestor
    stale = _assess(tmp_path, docs)
    assert stale["status"] == "REJECTED"
    assert any("not the current one" in r for r in stale["reasons"])
    report = _assess(tmp_path, docs, fresh=lambda revision: revision == ancestor)
    assert report["status"] == "CERTIFIED", report["reasons"]
    still = _assess(tmp_path, docs, fresh=lambda revision: False)
    assert still["status"] == "REJECTED"
    assert any("code changed since" in r for r in still["reasons"])


def test_a_different_scientific_fingerprint_is_rejected_even_when_the_revision_is_fresh(tmp_path):
    docs = _docs(tmp_path)
    for doc in docs.values():
        doc["source"]["revision"] = "c" * 40
    other = {**SOURCE, "scientific_fingerprint": "e" * 64}
    report = _assess(tmp_path, docs, current=other, fresh=lambda revision: True)
    assert report["status"] == "REJECTED"
    assert any("fingerprint" in r for r in report["reasons"])
