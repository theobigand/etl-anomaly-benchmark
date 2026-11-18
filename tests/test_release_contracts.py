"""Exact verdicts and reasons of the release decision, each condition acting alone."""

import json
import subprocess

import pytest

from verification import evidence_schema, release

REV = "a" * 40
OTHER = "b" * 40
FINGERPRINT = "c" * 64
PACKAGES = {name: "1.0" for name in release.RESULT_PACKAGES}
CURRENT = {"revision": REV, "scientific_fingerprint": FINGERPRINT, "worktree_dirty": False}


def _policy(**over):
    policy = {
        "version": 1,
        "required": ["fast", "types"],
        "optional": ["o"],
        "deferred": ["d"],
        "not_applicable": ["n"],
        "typing_pins": {"mypy": "1.0"},
    }
    policy.update(over)
    return policy


def _doc(kind, status="PASS", **over):
    result = {"types": {"mypy": "1.0"}}.get(kind, {})
    doc = {
        "kind": kind,
        "status": status,
        "source": {"revision": REV, "scientific_fingerprint": FINGERPRINT, "worktree_dirty": False},
        "environment": {"python": "3.11.2", "platform": "Linux-5", "packages": dict(PACKAGES)},
        "execution": {"ci": False, "run_id": None, "runner_environment": None, "runner_name": None},
        "artifacts": {},
        "result": result,
    }
    doc.update(over)
    return doc


@pytest.fixture(autouse=True)
def _valid_documents(monkeypatch):
    monkeypatch.setattr(evidence_schema, "validate", lambda doc, root=None: [])
    monkeypatch.setattr(release.mutation_scope, "check_evidence", lambda *a: [])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)


def _assess(docs=None, **kwargs):
    docs = docs if docs is not None else {k: _doc(k) for k in ("fast", "types")}
    kwargs.setdefault("current", dict(CURRENT))
    kwargs.setdefault("root", None)
    kwargs.setdefault("manifest", {})
    kwargs.setdefault("lineage", {"legacy": [], "problems": {}})
    kwargs.setdefault("locked", dict(PACKAGES))
    kwargs.setdefault("scope", {"inventory": [], "config": {}})
    kwargs.setdefault("policy", _policy())
    return release.assess(docs, **kwargs)


def test_consistent_evidence_is_certified_with_every_field_of_the_report():
    report = _assess()
    assert report["status"] == "CERTIFIED" and report["reasons"] == []
    assert report["schema_version"] == 1 and report["revision"] == REV
    assert report["profiles"] == {"fast": "PASS", "types": "PASS"}
    assert report["executions"] == {"fast": "local", "types": "local"}
    assert report["policy"] == {
        "version": 1, "required": ["fast", "types"], "optional": ["o"], "deferred": ["d"],
        "not_applicable": ["n"],
    }  # fmt: skip
    assert report["attestation"] == "local-unattested" and report["generated_at"].endswith("+00:00")
    assert report["performance"] == {} and report["environment"]["mode"] == "exact-environment"


def test_a_dirty_current_worktree_and_missing_or_invalid_profiles_have_their_own_reasons(
    monkeypatch,
):
    dirty = _assess(current={**CURRENT, "worktree_dirty": True})
    assert dirty["status"] == "REJECTED"
    assert dirty["reasons"] == ["the worktree is dirty: a release needs a clean source"]
    missing = _assess({"fast": _doc("fast")})
    assert missing["status"] == "INCOMPLETE" and missing["profiles"]["types"] == "MISSING"
    assert missing["reasons"] == ["types evidence is missing"]
    monkeypatch.setattr(evidence_schema, "validate", lambda doc, root=None: ["bad one", "bad two"])
    invalid = _assess({"fast": _doc("fast"), "types": _doc("types")})
    assert invalid["profiles"] == {"fast": "INVALID", "types": "INVALID"}
    assert invalid["reasons"] == [
        "fast: bad one", "fast: bad two", "types: bad one", "types: bad two",
    ]  # fmt: skip


def test_a_failed_profile_rejects_and_an_unfinished_one_is_incomplete():
    failed = _assess({"fast": _doc("fast", "FAIL"), "types": _doc("types")})
    assert failed["status"] == "REJECTED" and failed["reasons"] == ["fast profile failed"]
    unfinished = _assess({"fast": _doc("fast", "INCOMPLETE"), "types": _doc("types", "NOT_RUN")})
    assert unfinished["status"] == "INCOMPLETE"
    assert unfinished["reasons"] == ["fast profile is INCOMPLETE", "types profile is NOT_RUN"]
    both = _assess({"fast": _doc("fast", "FAIL"), "types": _doc("types", "INCOMPLETE")})
    assert both["reasons"] == ["fast profile failed", "types profile is INCOMPLETE"]
    assert both["status"] == "REJECTED"


def _moved(**doc_source):
    docs = {k: _doc(k) for k in ("fast", "types")}
    docs["fast"]["source"].update(doc_source)
    return docs


def test_evidence_from_another_revision_is_rejected_unless_the_freshness_check_says_true():
    docs = _moved(revision=OTHER)
    plain = _assess(docs)
    assert plain["reasons"] == [
        f"fast: revision {OTHER[:8]} is not the current one",
        "revision: the profiles were produced on different revisions",
    ]
    calls = []
    stale = _assess(_moved(revision=OTHER), fresh=lambda revision: calls.append(revision) or False)
    assert stale["reasons"][0] == (
        f"fast: revision {OTHER[:8]} is not the current one "
        "(not an ancestor, or code changed since)"
    )
    assert calls == [OTHER]
    fresh = _assess(_moved(revision=OTHER), fresh=lambda revision: True)
    assert fresh["reasons"] == ["revision: the profiles were produced on different revisions"]
    truthy = _assess(_moved(revision=OTHER), fresh=lambda revision: 1)
    assert truthy["reasons"][0].startswith(f"fast: revision {OTHER[:8]} is not the current one")


def test_a_fingerprint_difference_and_a_dirty_source_are_each_rejected_with_their_reason():
    fingerprint = _assess(_moved(scientific_fingerprint="d" * 64))
    assert fingerprint["reasons"] == [
        "fast: scientific fingerprint differs from the current source"
    ]
    dirty = _assess(_moved(worktree_dirty=True))
    assert dirty["reasons"] == ["fast: produced from a dirty worktree"]
    same = _assess(_moved())
    assert same["status"] == "CERTIFIED"


def test_the_typing_pins_and_the_hosted_mutation_platform_are_enforced():
    types = _doc("types")
    types["result"] = {"mypy": "2.0"}
    wrong = _assess({"fast": _doc("fast"), "types": types})
    assert wrong["reasons"] == ["types: mypy 2.0 is not the pinned 1.0"]
    policy = _policy(required=["deep"], deep_platform="Linux")
    deep = _doc("deep", result={"format_version": 2})
    deep["environment"]["platform"] = "macOS-27"
    refused = _assess({"deep": deep}, policy=policy)
    assert refused["reasons"] == [
        "deep: mutation evidence must come from a Linux environment (found macOS-27); "
        "local forked runs on other platforms gave unreliable verdicts"
    ]
    deep["environment"]["platform"] = "Linux-5.15"
    assert _assess({"deep": deep}, policy=policy)["status"] == "CERTIFIED"
    legacy = _doc("deep", result={})
    legacy["environment"]["platform"] = "macOS-27"
    assert _assess({"deep": legacy}, policy=policy)["status"] == "CERTIFIED"


def test_a_current_policy_refuses_deep_evidence_without_the_risk_tiered_format(monkeypatch):
    policy = _policy(required=["deep"], version=2)
    refused = _assess({"deep": _doc("deep", result={})}, policy=policy)
    assert refused["profiles"] == {"deep": "INVALID"}
    assert refused["reasons"] == ["deep: current release requires risk-tiered campaign evidence"]
    accepted = _assess({"deep": _doc("deep", result={"format_version": 2})}, policy=policy)
    assert accepted["status"] == "CERTIFIED"
    assert (
        _assess({"deep": _doc("deep", result={})}, policy=_policy(required=["deep"]))["status"]
        == "CERTIFIED"
    )


def test_a_legacy_deep_result_is_checked_against_the_mutation_scope(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        release.mutation_scope,
        "check_evidence",
        lambda result, inventory, config: (
            seen.update(args=(result, inventory, config)) or ["a", "b"]
        ),
    )
    scope = {"inventory": ["x.py"], "config": {"c": 1}}
    report = _assess(
        {"deep": _doc("deep", result={"r": 1})}, policy=_policy(required=["deep"]), scope=scope
    )
    assert report["reasons"] == ["deep scope: a", "deep scope: b"]
    assert seen["args"] == ({"r": 1}, ["x.py"], {"c": 1})


def test_the_profiles_of_different_revisions_are_reported_even_when_each_is_fresh():
    docs = {k: _doc(k) for k in ("fast", "types")}
    docs["types"]["source"]["revision"] = OTHER
    report = _assess(docs, fresh=lambda revision: True)
    assert report["reasons"] == ["revision: the profiles were produced on different revisions"]
    one = _assess({"fast": _doc("fast")}, policy=_policy(required=["fast"]))
    assert one["status"] == "CERTIFIED"


def test_each_execution_context_is_labelled_unrecorded_ci_runner_or_local():
    docs = {k: _doc(k) for k in ("fast", "types")}
    del docs["fast"]["execution"]
    docs["types"]["execution"] = {
        "ci": True,
        "run_id": "1",
        "runner_environment": "github-hosted",
        "runner_name": "r",
    }
    labelled = _assess(docs)
    assert labelled["executions"] == {"fast": "unrecorded", "types": "github-hosted"}
    docs["types"]["execution"]["runner_environment"] = None
    assert _assess(docs)["executions"]["types"] == "ci"


def _env(python="3.11.2", platform="Linux-5", **packages):
    return {"python": python, "platform": platform, "packages": {**PACKAGES, **packages}}


def test_a_missing_result_version_is_rejected_for_each_profile_that_lacks_it():
    docs = {
        "a": {"environment": _env(numpy=None)},
        "b": {"environment": _env(pandas="")},
        "c": None,
    }
    rejected, incomplete, environment = release.check_environments(docs, PACKAGES)
    assert rejected == [
        "a: the numpy version is not recorded",
        "b: the pandas version is not recorded",
    ]
    assert incomplete == [] and environment["mode"] == "exact-environment"


def test_different_versions_and_python_minors_are_listed_and_patch_levels_may_differ():
    docs = {
        "a": {"environment": _env(python="3.11.2", numpy="1.0")},
        "b": {"environment": _env(python="3.12.0", numpy="2.0")},
    }
    rejected, _, _ = release.check_environments(docs, PACKAGES)
    assert "numpy: the profiles ran different versions (a=1.0, b=2.0)" in rejected
    assert "python: the profiles ran different minor versions (a=3.11, b=3.12)" in rejected
    same = {
        "a": {"environment": _env(python="3.11.2")},
        "b": {"environment": _env(python="3.11.9")},
    }
    assert release.check_environments(same, PACKAGES)[0] == []
    assert release._minor("3.11.9") == "3.11" and release._minor("3") == "3"


def test_a_drift_from_the_lock_or_a_missing_lock_makes_the_environment_incomplete_not_rejected():
    docs = {"a": {"environment": _env(numpy="1.5")}}
    rejected, incomplete, environment = release.check_environments(docs, PACKAGES)
    assert rejected == [] and incomplete == [
        "the environment differs from the recorded lock: numpy 1.5 (lock 1.0)"
    ]
    assert environment["mode"] == "cross-platform" and environment["locked"] == PACKAGES
    assert environment["packages"]["numpy"] == "1.5" and environment["platforms"] == ["Linux-5"]
    _, none, _ = release.check_environments({"a": {"environment": _env()}}, {})
    assert none == ["no environment lock is recorded for " + ", ".join(release.RESULT_PACKAGES)]


def test_the_mode_is_exact_only_with_one_platform_one_python_minor_and_no_drift():
    one = {"a": {"environment": _env()}, "b": {"environment": _env()}}
    assert release.check_environments(one, PACKAGES)[2]["mode"] == "exact-environment"
    two = {"a": {"environment": _env()}, "b": {"environment": _env(platform="Darwin-1")}}
    mixed = release.check_environments(two, PACKAGES)[2]
    assert mixed["mode"] == "cross-platform" and mixed["platforms"] == ["Darwin-1", "Linux-5"]


def test_a_hosted_run_must_record_a_public_download_of_every_required_dataset():
    manifest = {"a": "1" * 64, "b": "2" * 64}
    missing = release._hosted_download_problems({"required": ["a"]}, manifest)
    assert missing == [
        "produced by a CI run on a hosted runner without a record of where the datasets came from"
    ]
    wrong = release._hosted_download_problems(
        {"required": ["a"], "acquisition": {"method": "x"}}, manifest
    )
    assert wrong == ["the datasets on a hosted runner must come from a public-download"]
    acquisition = {
        "method": "public-download",
        "datasets": {"a": {"url": "http://x", "sha256": "9" * 64}, "b": "text"},
    }
    problems = release._hosted_download_problems(
        {"required": ["a", "b", "c"], "acquisition": acquisition}, manifest
    )
    assert problems == [
        "dataset a: the source must be an https URL",
        "dataset a: the downloaded file differs from the manifest",
        "dataset b: no download is recorded",
        "dataset c: no download is recorded",
    ]
    good = {
        "method": "public-download",
        "datasets": {"a": {"url": "https://x", "sha256": "1" * 64}},
    }
    assert (
        release._hosted_download_problems({"required": ["a"], "acquisition": good}, manifest) == []
    )
    no_url = {"method": "public-download", "datasets": {"a": {"sha256": "1" * 64}}}
    assert release._hosted_download_problems(
        {"required": ["a"], "acquisition": no_url}, manifest
    ) == ["dataset a: the source must be an https URL"]
    assert release._hosted_download_problems(
        {"required": ["a"], "acquisition": {"method": "public-download"}}, manifest
    ) == ["dataset a: no download is recorded"]


def _real(execution=None, status="PASS", sha="1" * 64, acquisition=None):
    doc = _doc("real", status)
    result = {"required": ["a"], "datasets": [{"dataset": "a", "sha256": sha, "status": "PASS"}]}
    if acquisition is not None:
        result["acquisition"] = acquisition
    doc["result"] = result
    if execution is None:
        del doc["execution"]
    else:
        doc["execution"] = execution
    return doc


REAL_POLICY = _policy(required=["real"])
HOSTED = {"ci": True, "run_id": "1", "runner_environment": "github-hosted", "runner_name": "r"}


def test_the_real_profile_needs_its_execution_context_and_hosted_runs_their_download_record():
    assert _assess({"real": _real()}, policy=REAL_POLICY, manifest={"a": "1" * 64})["reasons"] == [
        "real: the execution context is not recorded"
    ]
    hosted = _assess({"real": _real(HOSTED)}, policy=REAL_POLICY, manifest={"a": "1" * 64})
    assert hosted["reasons"] == [
        "real: produced by a CI run on a hosted runner without a record of where the "
        "datasets came from"
    ]
    own = {**HOSTED, "runner_environment": "self-hosted"}
    assert (
        _assess({"real": _real(own)}, policy=REAL_POLICY, manifest={"a": "1" * 64})["status"]
        == "CERTIFIED"
    )
    local = {**HOSTED, "ci": False}
    assert (
        _assess({"real": _real(local)}, policy=REAL_POLICY, manifest={"a": "1" * 64})["status"]
        == "CERTIFIED"
    )


def test_a_passing_real_profile_must_carry_the_reference_hash_of_every_required_dataset():
    own = {**HOSTED, "runner_environment": "self-hosted"}
    differs = _assess(
        {"real": _real(own, sha="2" * 64)}, policy=REAL_POLICY, manifest={"a": "1" * 64}
    )
    assert differs["reasons"] == ["dataset a: hash differs from the reference manifest"]
    absent = _assess({"real": _real(own)}, policy=REAL_POLICY, manifest={})
    assert absent["reasons"] == ["dataset a: hash differs from the reference manifest"]
    not_run = _assess(
        {"real": _real(own, status="NOT_RUN", sha="2" * 64)},
        policy=REAL_POLICY,
        manifest={"a": "1" * 64},
    )
    assert not_run["reasons"] == ["real profile is NOT_RUN"]


def test_lineage_problems_legacy_dirty_stale_performance_and_published_figures_have_exact_reasons():
    lineage = {
        "problems": {"run_x": ["p1", "p2"]},
        "legacy": ["run_b", "run_a"],
        "dirty": ["run_d", "run_c"],
        "performance": {"scaling": ("STALE", ["r1", "r2"]), "other": ("BOUND", [])},
    }
    report = _assess(lineage=lineage, claims=["c1"])
    assert report["status"] == "REJECTED"
    assert report["reasons"] == [
        "lineage run_x: p1",
        "lineage run_x: p2",
        "experiment records predate the scientific fingerprint (run_a, run_b); "
        "a clean replay is required",
        "performance evidence scaling is stale: r1; r2; "
        "re-measure it or withdraw it from the publication",
        "published figures: c1",
        "archived runs were made on a dirty worktree (run_c, run_d); "
        "kept as labelled history, a clean replay is required",
    ]
    assert report["performance"] == {"other": "BOUND", "scaling": "STALE"}
    quiet = _assess(
        lineage={"legacy": [], "problems": {}, "dirty": [], "performance": {"s": ("LEGACY", [])}}
    )
    assert quiet["status"] == "CERTIFIED" and quiet["performance"] == {"s": "LEGACY"}


def test_the_attestation_names_a_ci_run_without_claiming_independence(monkeypatch):
    assert release.attestation() == "local-unattested"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert release.attestation() == "ci-run:unknown (not independently attested)"
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    assert release.attestation() == "ci-run:42 (not independently attested)"
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    assert release.attestation() == "local-unattested"


def test_the_locked_versions_come_from_the_conda_lock_first_then_the_pip_freeze(tmp_path):
    (tmp_path / "conda-linux-x86_64.explicit.txt").write_text(
        "@EXPLICIT\nhttps://h/numpy-1.26.0-py311_0.conda#abc\nnot a url\n"
        "https://h/pandas-2.2.0-py311_1.tar.bz2#def\nhttps://h/other-9.9.9-0.conda#x\n"
    )
    (tmp_path / "pip-freeze.txt").write_text(
        "PyOD==2.0.1\nnumpy==9.9.9\nscikit-learn == 1.5.0\n# c\nplain\n"
    )
    assert release.locked_versions(tmp_path) == {
        "numpy": "1.26.0", "pandas": "2.2.0", "scikit-learn": "1.5.0", "pyod": "2.0.1",
    }  # fmt: skip
    assert list(release.locked_versions(tmp_path)) == list(release.RESULT_PACKAGES)
    assert release.locked_versions(tmp_path / "empty") == {}


def test_the_typing_check_lists_each_pin_that_is_not_met():
    doc = {"result": {"mypy": "2", "stubs": "1"}}
    assert release.check_typing(doc, {"mypy": "1", "stubs": "1", "gone": "3"}) == [
        "types: mypy 2 is not the pinned 1",
        "types: gone None is not the pinned 3",
    ]


def _git(tmp_path, *args):
    return subprocess.run(
        ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_evidence_stays_fresh_across_documentation_changes_but_not_code_changes(tmp_path):
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        _git(tmp_path, *command)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "one")
    first = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "docs" / "a.md").write_text("b")
    _git(tmp_path, "commit", "-qam", "docs")
    fresh = release.freshness(tmp_path)
    assert fresh(first) is True
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "code")
    assert release.freshness(tmp_path)(first) is False
    assert release.freshness(tmp_path)("f" * 40) is False
    assert release.freshness(tmp_path)(_git(tmp_path, "rev-parse", "HEAD")) is True


def test_the_command_defaults_to_the_repository_evidence_folder_and_names_its_options(
    monkeypatch, tmp_path, capsys
):
    seen = {}
    monkeypatch.setattr(release.mutation_scope, "load", lambda: {})
    monkeypatch.setattr(release.mutation_scope, "inventory", lambda root, config: [])
    monkeypatch.setattr(release, "load_policy", lambda: {"required": ["fast"], "version": 1})
    monkeypatch.setattr(evidence_schema, "collect_source", lambda: CURRENT)
    monkeypatch.setattr(release.claims, "load", lambda: {})
    monkeypatch.setattr(release.claims, "check_run", lambda *a, **k: [])
    monkeypatch.setattr(release.claims, "check_paper", lambda *a: [])
    monkeypatch.setattr(release, "reference_hashes", lambda: {})
    monkeypatch.setattr(release, "archive_lineage", lambda: {})
    monkeypatch.setattr(release, "locked_versions", lambda: {})
    monkeypatch.setattr(release, "freshness", lambda: None)
    monkeypatch.setattr(
        release, "load_docs", lambda directory, kinds: seen.update(directory=directory) or {}
    )
    monkeypatch.setattr(
        release,
        "assess",
        lambda *a, **k: {"status": "CERTIFIED", "attestation": "x", "reasons": []},
    )
    written = []
    monkeypatch.setattr(release.Path, "write_text", lambda self, text: written.append(self))
    monkeypatch.setattr(release.Path, "mkdir", lambda self, **k: None)
    assert release.main([]) == 0
    assert seen["directory"] == release.EVIDENCE_DIR and written == [
        release.EVIDENCE_DIR / "release.json"
    ]
    assert capsys.readouterr().out == "release: CERTIFIED (x)\n"
    with pytest.raises(SystemExit):
        release.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--evidence EVIDENCE" in text and "--output OUTPUT" in text


def test_a_release_policy_of_another_version_is_refused_with_its_expected_version(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"version": 1}))
    with pytest.raises(ValueError) as refused:
        release.load_policy(path)
    assert str(refused.value) == "release policy version must be 2"
    path.write_text(json.dumps({"version": 2, "required": ["a"]}))
    assert release.load_policy(path)["required"] == ["a"]


def test_the_reference_hashes_map_each_manifest_dataset_to_its_digest_or_none(tmp_path):
    manifest = {"datasets": {"a": {"sha256": "1" * 64}, "b": {}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert release.reference_hashes(tmp_path) == {"a": "1" * 64, "b": None}


def test_the_archive_lineage_lists_legacy_dirty_and_broken_runs_and_the_scaling_measurement(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(release.lineage, "anchor_revision", lambda: "anchor")
    monkeypatch.setattr(release.lineage, "files_at", lambda revision: {"anchor": revision})
    monkeypatch.setattr(release.lineage, "worktree_files", lambda: {"now": 1})
    seen = []

    def check_record(record, anchor, current):
        seen.append((record.get("id"), anchor, current))
        return ["broken"] if record.get("id") == "bad" else []

    monkeypatch.setattr(release.lineage, "check_record", check_record)
    monkeypatch.setattr(
        release.lineage, "check_measurement", lambda record, current: ("STALE", ["why"])
    )
    (tmp_path / "run_old.json").write_text(json.dumps({"id": "old"}))
    (tmp_path / "run_new.json").write_text(
        json.dumps({"id": "bad", "fingerprint_recipe": 2, "worktree_dirty": True})
    )
    (tmp_path / "other.json").write_text("{not read")
    (tmp_path / "scaling.json").write_text("{}")
    found = release.archive_lineage(tmp_path)
    assert found == {
        "legacy": ["run_old"],
        "dirty": ["run_new"],
        "problems": {"run_new": ["broken"]},
        "performance": {"scaling": ("STALE", ["why"])},
    }
    assert seen == [
        ("bad", {"anchor": "anchor"}, {"now": 1}),
        ("old", {"anchor": "anchor"}, {"now": 1}),
    ]
    (tmp_path / "scaling.json").unlink()
    assert release.archive_lineage(tmp_path)["performance"] == {}
