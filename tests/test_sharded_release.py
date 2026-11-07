"""Sharded mutation evidence follows the same release contract as a monolithic campaign."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from tests.test_evidence_schema import EXECUTION, SOURCE
from tests.test_mutation_shards import _git_repository
from tests.test_release_gate import _assess, _docs
from tests.verifier.test_mutation_run import SOURCE as MODULE
from tests.verifier.test_mutation_run import _repository
from verification import evidence_schema, mutation_campaign, release
from verification import mutation_shards as shards


@pytest.fixture(autouse=True)
def _tool_versions(monkeypatch):
    versions = {"mutmut": "3.8.0", "pytest": "9.1.1"}
    monkeypatch.setattr(shards, "version", lambda name: versions.get(name))
    monkeypatch.setattr(evidence_schema, "REQUIRED_DATASETS", ("a", "b"))


def _campaign(root, outcomes=("killed", "killed"), exit_code=0, count=1):
    _repository(root)
    _git_repository(root)
    policy = json.loads((root / "verification/mutation_risk_policy.json").read_text())
    document = shards.plan(policy, {MODULE: 2}, count)
    (root / "plan.json").write_text(json.dumps(document))
    context = shards.current_context(root)
    keys = [f"pkg.a.x_compute__mutmut_{n}" for n in (1, 2)]
    manifests = []
    for shard in document["shards"]:
        names = set(shard["modules"])
        manifest = {
            "format": 1,
            "plan_sha256": document["sha256"],
            "index": shard["index"],
            "context": context,
            "modules": shard["modules"],
            "sources": {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in names},
            "catalog": {n: keys for n in names},
            "records": [
                {"id": key, "path": MODULE, "outcome": outcome}
                for key, outcome in zip(keys, outcomes, strict=True)
            ]
            if names
            else [],
            "missing": [],
            "native_exit_code": exit_code,
        }
        path = root / f"evidence-shard-{shard['index']}.json"
        path.write_text(json.dumps(manifest))
        manifests.append(path)
    return document, manifests


def _doc(root, manifests):
    return evidence_schema.build_deep_shards(
        root / "plan.json", manifests, root=root, source=SOURCE, execution=EXECUTION
    )


def test_a_complete_passing_sharded_campaign_is_valid_but_cannot_pass_without_execution_binding(
    tmp_path,
):
    _, manifests = _campaign(tmp_path)
    doc = _doc(tmp_path, manifests)
    assert doc["result"]["mode"] == "sharded" and doc["result"]["analysis"]["status"] == "PASS"
    assert doc["result"]["execution_binding"] == "unbound"
    assert doc["status"] == "INCOMPLETE"
    assert evidence_schema.validate(doc, root=tmp_path) == []


def test_a_failing_sharded_campaign_is_a_failed_profile_with_its_evidence_bound(tmp_path):
    _, manifests = _campaign(tmp_path, outcomes=("killed", "survived"))
    doc = _doc(tmp_path, manifests)
    assert doc["status"] == "FAIL" and evidence_schema.validate(doc, root=tmp_path) == []
    assert set(doc["artifacts"]) >= {"plan.json", "evidence-shard-0.json"}


def _release(tmp_path, doc):
    docs = _docs(tmp_path)
    docs["deep"] = doc
    return _assess(tmp_path, docs, policy=release.load_policy())


@pytest.mark.parametrize("outcomes", [("killed", "killed"), ("killed", "survived")])
def test_sharded_evidence_never_produces_a_certification_here(tmp_path, outcomes):
    _, manifests = _campaign(tmp_path, outcomes=outcomes)
    report = _release(tmp_path, _doc(tmp_path, manifests))
    assert report["status"] != "CERTIFIED"
    assert report["profiles"]["deep"] in {"INCOMPLETE", "FAIL"}


def test_a_forged_pass_status_is_rejected_by_recomputation(tmp_path):
    _, manifests = _campaign(tmp_path)
    doc = _doc(tmp_path, manifests)
    doc["status"] = "PASS"
    problems = evidence_schema.validate(doc, root=tmp_path)
    assert any("differs from the recomputed result" in p or "not supported" in p for p in problems)
    report = _release(tmp_path, doc)
    assert report["status"] == "REJECTED" and report["profiles"]["deep"] == "INVALID"


def test_a_tampered_manifest_or_plan_is_detected_by_the_bound_hashes(tmp_path):
    _, manifests = _campaign(tmp_path)
    doc = _doc(tmp_path, manifests)
    manifest = json.loads(manifests[0].read_text())
    manifest["records"][0]["outcome"] = "survived"
    manifests[0].write_text(json.dumps(manifest))
    assert any("hash differs" in p for p in evidence_schema.validate(doc, root=tmp_path))


def test_a_source_change_after_the_campaign_makes_it_stale(tmp_path):
    _, manifests = _campaign(tmp_path)
    doc = _doc(tmp_path, manifests)
    (tmp_path / MODULE).write_text("def compute(value):\n    return value + 9\n")
    problems = evidence_schema.validate(doc, root=tmp_path)
    assert any("does not match current inputs" in p for p in problems)


def test_missing_duplicate_or_foreign_shards_give_incomplete_evidence(tmp_path):
    _, manifests = _campaign(tmp_path, count=2)
    missing = _doc(tmp_path, manifests[:1])
    assert missing["status"] == "INCOMPLETE" and "reason" in missing["result"]
    assert "missing" in missing["result"]["reason"]
    twice = _doc(tmp_path, [manifests[0], manifests[0], manifests[1]])
    assert twice["status"] == "INCOMPLETE" and "more than once" in twice["result"]["reason"]
    foreign = json.loads(manifests[1].read_text())
    foreign["plan_sha256"] = "0" * 64
    manifests[1].write_text(json.dumps(foreign))
    other = _doc(tmp_path, manifests)
    assert other["status"] == "INCOMPLETE" and "plan" in other["result"]["reason"]


def test_a_shard_from_a_different_context_gives_incomplete_evidence(tmp_path):
    _, manifests = _campaign(tmp_path)
    manifest = json.loads(manifests[0].read_text())
    manifest["context"]["runtime"]["packages"]["pytest"] = "9.2.0"
    manifests[0].write_text(json.dumps(manifest))
    doc = _doc(tmp_path, manifests)
    assert doc["status"] == "INCOMPLETE" and "context" in doc["result"]["reason"]


def test_a_nonzero_native_exit_or_foreign_mutmut_keeps_the_campaign_incomplete(
    tmp_path, monkeypatch
):
    _, manifests = _campaign(tmp_path, exit_code=2)
    assert _doc(tmp_path, manifests)["status"] == "INCOMPLETE"
    monkeypatch.setattr(shards, "version", lambda name: "9.9" if name == "mutmut" else "9.1.1")
    doc = _doc(tmp_path, manifests)
    assert doc["status"] == "INCOMPLETE" and "3.8.0" in doc["result"]["reason"]


def test_historical_global_evidence_cannot_satisfy_the_current_policy(tmp_path):
    docs = _docs(tmp_path)
    report = _assess(tmp_path, docs, policy=release.load_policy())
    assert report["status"] == "REJECTED"
    assert "risk-tiered campaign evidence" in " ".join(report["reasons"])


def test_the_reviewed_equivalence_file_is_bound_into_the_sharded_campaign(tmp_path):
    _, manifests = _campaign(tmp_path, outcomes=("killed", "survived"))
    (tmp_path / "verification/mutation_equivalence.json").write_text(
        json.dumps({"version": 1, "records": []})
    )
    result, artifacts = mutation_campaign.load_sharded(tmp_path, tmp_path / "plan.json", manifests)
    assert tmp_path / "verification/mutation_equivalence.json" in artifacts
    assert result["equivalence"] == {"version": 1, "records": []}
    forged = copy.deepcopy(result)
    forged["equivalence"]["records"].append({"id": "x"})
    with pytest.raises(ValueError):
        mutation_campaign.status(forged)


def test_the_sharded_status_rule_requires_a_controller_proof_to_pass(tmp_path):
    _, manifests = _campaign(tmp_path)
    result, _ = mutation_campaign.load_sharded(tmp_path, tmp_path / "plan.json", manifests)
    assert mutation_campaign.status(result) == "INCOMPLETE"
    bound = {**result, "execution_binding": "controller-proof"}
    assert mutation_campaign.status(bound) == "PASS"
    with pytest.raises(ValueError, match="paths are incomplete"):
        mutation_campaign.validate_current({**result, "paths": {"plan": "plan.json"}}, tmp_path)


def test_a_forged_execution_binding_is_rejected_by_current_input_recomputation(tmp_path):
    _, manifests = _campaign(tmp_path)
    doc = _doc(tmp_path, manifests)
    doc["result"]["execution_binding"] = "controller-proof"
    doc["status"] = "PASS"
    problems = evidence_schema.validate(doc, root=tmp_path)
    assert any("does not match current inputs" in p for p in problems)
    report = _release(tmp_path, doc)
    assert report["status"] == "REJECTED" and report["profiles"]["deep"] == "INVALID"


def test_the_evidence_command_wraps_a_sharded_campaign(tmp_path, capsys):
    _, manifests = _campaign(tmp_path)
    output = tmp_path / "deep.json"
    code = evidence_schema.main(
        ["deep-shards", "--plan", str(tmp_path / "plan.json"), "--manifests",
         *map(str, manifests), "--output", str(output), "--root", str(tmp_path)]
    )  # fmt: skip
    doc = json.loads(output.read_text())
    assert code == 1 and doc["kind"] == "deep" and doc["status"] == "INCOMPLETE"
    assert "deep evidence: INCOMPLETE" in capsys.readouterr().out


def test_a_caller_supplied_environment_is_kept_unchanged(tmp_path):
    _, manifests = _campaign(tmp_path)
    environment = {"python": "x", "platform": "y", "packages": {}}
    doc = evidence_schema.build_deep_shards(
        tmp_path / "plan.json", manifests, root=tmp_path, source=SOURCE,
        environment=environment, execution=EXECUTION,
    )  # fmt: skip
    assert doc["environment"] == environment
    assert any("environment differs" in p for p in evidence_schema.validate(doc, root=tmp_path))
