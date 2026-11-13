"""What the deep evidence builders pass on, derive and refuse, with the collaborators replaced."""

import json
import subprocess
from pathlib import Path

import pytest

from verification import evidence_schema as es

SOURCE = {"revision": "a" * 40}
ENVIRONMENT = {"python": "3.11", "platform": "t", "packages": {}}
EXECUTION = {"ci": False}


@pytest.fixture
def envelope(monkeypatch):
    calls = []

    def fake(kind, status, result, artifacts, root, source, environment, execution):
        calls.append(
            {
                "kind": kind, "status": status, "result": result, "artifacts": artifacts,
                "root": root, "source": source, "environment": environment,
                "execution": execution,
            }
        )  # fmt: skip
        return calls[-1]

    monkeypatch.setattr(es, "_envelope", fake)
    return calls


def _stats(tmp_path, killed=3, total=4):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"killed": killed, "total": total}))
    return path


def _patch_legacy(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        es.mutation_scope, "configured_patterns", lambda path: seen.update(patterns=path) or ["p/*"]
    )
    monkeypatch.setattr(
        es.mutation_scope,
        "configured_exclusions",
        lambda path: seen.update(exclusions=path) or ["x"],
    )
    monkeypatch.setattr(
        es.mutation_scope,
        "resolve",
        lambda scope, root, exclude: seen.update(resolve=(scope, root, exclude)) or ["p/a.py"],
    )
    monkeypatch.setattr(es.check_mutation, "classify", lambda counts: None)
    monkeypatch.setattr(es, "_deep_status", lambda result: "PASS")
    return seen


def test_the_legacy_scope_comes_from_the_repository_configuration_when_none_is_given(
    monkeypatch, tmp_path, envelope
):
    seen = _patch_legacy(monkeypatch)
    es.build_legacy_deep(_stats(tmp_path), root=tmp_path)
    assert seen["patterns"] == es.ROOT / "pyproject.toml"
    assert seen["exclusions"] == es.ROOT / "pyproject.toml"
    assert seen["resolve"] == (["p/*"], tmp_path, ["x"])


def test_a_given_scope_is_used_as_it_is_and_excludes_nothing(monkeypatch, tmp_path, envelope):
    seen = _patch_legacy(monkeypatch)
    es.build_legacy_deep(_stats(tmp_path), root=tmp_path, scope=["only/*"])
    assert "patterns" not in seen and "exclusions" not in seen
    assert seen["resolve"] == (["only/*"], tmp_path, [])


def test_the_legacy_result_names_the_scope_its_files_the_threshold_the_counts_and_the_score(
    monkeypatch, tmp_path, envelope
):
    _patch_legacy(monkeypatch)
    stats = _stats(tmp_path, killed=3, total=4)
    es.build_legacy_deep(
        stats, root=tmp_path, scope=["p/*"], source=SOURCE, environment=ENVIRONMENT,
        execution=EXECUTION,
    )  # fmt: skip
    call = envelope[0]
    assert call["kind"] == "deep" and call["status"] == "PASS" and call["root"] == tmp_path
    assert call["result"] == {
        "scope": ["p/*"], "scope_files": ["p/a.py"], "mutated_files": None,
        "threshold": es.check_mutation.THRESHOLD, "stats": {"killed": 3, "total": 4},
        "score": 75.0,
    }  # fmt: skip
    assert call["artifacts"] == [stats]
    assert (call["source"], call["environment"], call["execution"]) == (
        SOURCE, ENVIRONMENT, EXECUTION,
    )  # fmt: skip


def test_the_legacy_listing_is_an_artifact_and_gives_the_mutated_files_or_the_read_error(
    monkeypatch, tmp_path, envelope
):
    _patch_legacy(monkeypatch)
    monkeypatch.setattr(es.mutation_scope, "mutated_files", lambda text, root: [text, str(root)])
    listing = tmp_path / "results.txt"
    listing.write_text("mutants")
    stats = _stats(tmp_path)
    es.build_legacy_deep(stats, listing, root=tmp_path, scope=["p/*"])
    assert envelope[0]["result"]["mutated_files"] == ["mutants", str(tmp_path)]
    assert envelope[0]["artifacts"] == [stats, listing]
    es.build_legacy_deep(stats, tmp_path / "absent.txt", root=tmp_path, scope=["p/*"])
    assert envelope[1]["result"]["mutated_files"] is None
    assert "absent.txt" in envelope[1]["result"]["reason"]


@pytest.mark.parametrize("content", ["not json", "[]", None])
def test_unreadable_or_unclassifiable_counts_make_the_legacy_evidence_incomplete(
    monkeypatch, tmp_path, envelope, content
):
    _patch_legacy(monkeypatch)

    def classify(counts):
        raise ValueError("counts do not add up")

    monkeypatch.setattr(es.check_mutation, "classify", classify)
    stats = tmp_path / "stats.json"
    if content is not None:
        stats.write_text(content)
    es.build_legacy_deep(
        stats, root=tmp_path, scope=["p/*"], source=SOURCE, environment=ENVIRONMENT,
        execution=EXECUTION,
    )  # fmt: skip
    call = envelope[0]
    assert call["status"] == "INCOMPLETE" and call["result"]["stats"] == {}
    assert call["result"]["reason"]
    assert "score" not in call["result"]
    assert (call["source"], call["environment"], call["execution"]) == (
        SOURCE, ENVIRONMENT, EXECUTION,
    )  # fmt: skip


def _campaign(monkeypatch, result, status="PASS"):
    seen = {}

    def load(root, stats, results, run_report):
        seen["load"] = (root, stats, results, run_report)
        return result, ["artifact"]

    monkeypatch.setattr(es.mutation_campaign, "load_campaign", load)
    monkeypatch.setattr(es.mutation_campaign, "status", lambda r: seen.update(judged=r) or status)
    return seen


RESULT = {
    "runtime": {
        "python": "3.11.17",
        "platform": "Linux",
        "packages": {"mutmut": "3.8.0", "pandas": "3.0.6", "other": "1"},
    }
}


def test_the_campaign_is_read_from_its_three_files_with_the_default_controller_report(
    monkeypatch, tmp_path, envelope
):
    seen = _campaign(monkeypatch, RESULT)
    stats, listing = tmp_path / "s.json", tmp_path / "r.txt"
    es.build_deep(stats, listing, root=tmp_path, source=SOURCE, execution=EXECUTION)
    assert seen["load"] == (tmp_path, stats, listing, tmp_path / "mutants/controller-result.json")
    assert seen["judged"] is RESULT
    call = envelope[0]
    assert (
        call["status"] == "PASS" and call["result"] is RESULT and call["artifacts"] == ["artifact"]
    )
    assert (call["source"], call["execution"]) == (SOURCE, EXECUTION)


def test_a_given_controller_report_is_used_and_the_environment_is_the_observed_runtime(
    monkeypatch, tmp_path, envelope
):
    seen = _campaign(monkeypatch, RESULT)
    report = tmp_path / "other.json"
    es.build_deep(tmp_path / "s.json", tmp_path / "r.txt", run_report=report, root=tmp_path)
    assert seen["load"][3] == report
    environment = envelope[0]["environment"]
    assert environment["python"] == "3.11.17" and environment["platform"] == "Linux"
    assert environment["packages"] == {
        name: RESULT["runtime"]["packages"].get(name) for name in es.PACKAGES
    }
    assert set(environment) == {"python", "platform", "packages"}


def test_a_given_environment_replaces_the_observed_one(monkeypatch, tmp_path, envelope):
    _campaign(monkeypatch, RESULT)
    es.build_deep(tmp_path / "s", tmp_path / "r", root=tmp_path, environment=ENVIRONMENT)
    assert envelope[0]["environment"] is ENVIRONMENT


@pytest.mark.parametrize(
    "error", [OSError("gone"), KeyError("runtime"), TypeError("x"), ValueError("bad")]
)
def test_a_campaign_that_cannot_be_read_is_incomplete_with_the_reason_of_the_failure(
    monkeypatch, tmp_path, envelope, error
):
    def load(*args):
        raise error

    monkeypatch.setattr(es.mutation_campaign, "load_campaign", load)
    stats, report = tmp_path / "s", tmp_path / "u"
    es.build_deep(stats, tmp_path / "r", run_report=report, root=tmp_path)
    call = envelope[0]
    assert call["status"] == "INCOMPLETE"
    assert call["result"] == {"format_version": 2, "reason": str(error)}
    assert call["artifacts"] == [stats, tmp_path / "r", report]


def test_the_native_listing_is_required_and_the_artifacts_skip_what_is_absent(tmp_path, envelope):
    stats = tmp_path / "s"
    es.build_deep(stats, None, run_report=None, root=tmp_path, source=SOURCE, execution=EXECUTION)
    call = envelope[0]
    assert call["result"] == {
        "format_version": 2,
        "reason": "the native mutant listing is required",
    }
    assert call["artifacts"] == [stats, tmp_path / "mutants/controller-result.json"]
    assert (call["source"], call["environment"], call["execution"]) == (SOURCE, None, EXECUTION)


def test_a_sharded_campaign_is_read_from_its_plan_and_manifests(monkeypatch, tmp_path, envelope):
    seen = {}

    def load(root, plan, manifests):
        seen["load"] = (root, plan, manifests)
        return RESULT, ["a1", "a2"]

    monkeypatch.setattr(es.mutation_campaign, "load_sharded", load)
    monkeypatch.setattr(es.mutation_campaign, "status", lambda r: "PASS")
    plan, manifests = tmp_path / "plan.json", [tmp_path / "m0.json"]
    es.build_deep_shards(plan, manifests, root=tmp_path, source=SOURCE, execution=EXECUTION)
    assert seen["load"] == (tmp_path, plan, manifests)
    call = envelope[0]
    assert call["kind"] == "deep" and call["status"] == "PASS" and call["artifacts"] == ["a1", "a2"]
    assert (
        call["environment"]["python"] == "3.11.17"
        and call["environment"]["packages"]["mutmut"] == "3.8.0"
    )
    assert (call["source"], call["execution"]) == (SOURCE, EXECUTION)


@pytest.mark.parametrize(
    "error",
    [
        OSError("a"),
        KeyError("b"),
        TypeError("c"),
        ValueError("d"),
        subprocess.CalledProcessError(2, "git"),
    ],
)
def test_a_sharded_campaign_that_cannot_be_read_is_incomplete_with_its_reason(
    monkeypatch, tmp_path, envelope, error
):
    def load(*args):
        raise error

    monkeypatch.setattr(es.mutation_campaign, "load_sharded", load)
    plan, manifests = tmp_path / "p", [tmp_path / "m"]
    es.build_deep_shards(plan, manifests, root=tmp_path, source=SOURCE, execution=EXECUTION)
    call = envelope[0]
    assert call["status"] == "INCOMPLETE"
    assert call["result"] == {"format_version": 2, "reason": str(error)}
    assert call["artifacts"] == [plan, *manifests]
    assert (call["source"], call["environment"], call["execution"]) == (SOURCE, None, EXECUTION)


def test_the_repository_root_is_the_parent_of_the_verification_folder():
    assert Path(es.__file__).resolve().parents[1] == es.ROOT
