"""Sharded campaigns pass only with a verified, shard-specific execution proof."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from tests.test_evidence_schema import EXECUTION, SOURCE
from tests.test_mutation_campaign import _fixture
from tests.test_mutation_shards import _git_repository
from tests.verifier.test_mutation_run import SOURCE as MODULE
from verification import evidence_schema, mutation_cache, mutation_campaign
from verification import mutation_shards as shards


@pytest.fixture(autouse=True)
def _tool_versions(monkeypatch):
    versions = {"mutmut": "3.8.0", "pytest": "9.1.1"}
    monkeypatch.setattr(shards, "version", lambda name: versions.get(name))


def _rewrite_attempt(root, mutate=None, names=("pkg.a.*",)):
    """Re-seal the fixture's proof the way the controller would for this command."""
    path = next((root / "mutants/attempts").glob("*/execution.json"))
    record = json.loads(path.read_text())
    proof = record["proof"]
    proof["context"]["runtime"]["native_command"] = [
        *proof["context"]["runtime"]["native_command"],
        *names,
    ]
    if mutate:
        mutate(record, proof)
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    record["admission"]["context_sha256"] = mutation_cache._digest(proof["context"])
    path.write_text(json.dumps(record))
    return path


def _setup(root, survived=False, mutate=None, names=("pkg.a.*",)):
    _fixture(root, survived=survived)
    _git_repository(root)
    policy = json.loads((root / "verification/mutation_risk_policy.json").read_text())
    document = shards.plan(policy, {MODULE: 2}, 1)
    (root / "plan.json").write_text(json.dumps(document))
    attempt = _rewrite_attempt(root, mutate, names)
    return policy, document, attempt


def _build(root, policy, document, attempt, exit_code=0):
    return shards.build_shard(
        policy,
        root,
        root / "mutants",
        document,
        0,
        shards.current_context(root),
        exit_code,
        attempt,
    )


def _write(root, manifest):
    path = root / "evidence-shard-0.json"
    path.write_text(json.dumps(manifest))
    return path


def test_a_shard_with_a_verified_execution_proof_lets_the_campaign_pass(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    assert set(manifest["execution"]) == shards.EXECUTION_KEYS
    assert manifest["execution"]["native_command"][-1] == "pkg.a.*"
    path = _write(tmp_path, manifest)
    doc = evidence_schema.build_deep_shards(
        tmp_path / "plan.json", [path], root=tmp_path, source=SOURCE, execution=EXECUTION
    )
    assert doc["result"]["execution_binding"] == "controller-proof"
    assert doc["status"] == "PASS" and evidence_schema.validate(doc, root=tmp_path) == []


def test_a_shard_without_a_proof_leaves_the_campaign_incomplete(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    manifest = shards.build_shard(
        policy, tmp_path, tmp_path / "mutants", document, 0, shards.current_context(tmp_path), 0
    )
    assert "execution" not in manifest
    path = _write(tmp_path, manifest)
    result, _ = mutation_campaign.load_sharded(tmp_path, tmp_path / "plan.json", [path])
    assert result["execution_binding"] == "unbound"
    assert mutation_campaign.status(result) == "INCOMPLETE"


def test_a_trustworthy_campaign_below_threshold_still_fails(tmp_path):
    policy, document, attempt = _setup(tmp_path, survived=True)
    path = _write(tmp_path, _build(tmp_path, policy, document, attempt))
    doc = evidence_schema.build_deep_shards(
        tmp_path / "plan.json", [path], root=tmp_path, source=SOURCE, execution=EXECUTION
    )
    assert doc["result"]["execution_binding"] == "controller-proof" and doc["status"] == "FAIL"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r, p: p.__setitem__("native_exit_code", 7), "does not describe"),
        (lambda r, p: r["admission"].__setitem__("context_sha256", "0" * 64), "admission"),
        (lambda r, p: r.__setitem__("native_log_sha256", "0" * 64), "native log"),
        (
            lambda r, p: p["context"]["sources"][MODULE].__setitem__("sha256", "0" * 64),
            "stale",
        ),
    ],
)
def test_attempts_that_do_not_prove_this_shard_are_refused(tmp_path, mutate, message):
    policy, document, attempt = _setup(tmp_path)
    record = json.loads(attempt.read_text())
    proof = record["proof"]

    def reseal(skip_admission=False):
        proof["sha256"] = mutation_cache._digest(
            {key: value for key, value in proof.items() if key != "sha256"}
        )
        if not skip_admission:
            record["admission"]["context_sha256"] = mutation_cache._digest(proof["context"])

    mutate(record, proof)
    reseal(skip_admission="admission" in message)
    attempt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match=message):
        _build(tmp_path, policy, document, attempt)


def test_a_forged_proof_digest_and_wrong_command_are_refused(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    forged = json.loads(attempt.read_text())
    forged["proof"]["native_exit_code"] = 0
    forged["proof"]["settled"] = 99
    attempt.write_text(json.dumps(forged))
    with pytest.raises(ValueError, match="digest differs"):
        _build(tmp_path, policy, document, attempt)


def test_a_proof_for_other_modules_is_refused(tmp_path):
    policy, document, attempt = _setup(tmp_path, names=("pkg.other.*",))
    with pytest.raises(ValueError, match="does not describe this shard"):
        _build(tmp_path, policy, document, attempt)


def test_an_invalid_attempt_shape_is_refused(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    attempt.write_text(json.dumps({"proof": {}}))
    with pytest.raises(ValueError, match="invalid attempt record"):
        _build(tmp_path, policy, document, attempt)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.__setitem__("native_exit_code", 3),
        lambda e: e["sources"].__setitem__(MODULE, "0" * 64),
        lambda e: e["runtime"].__setitem__("python", "2.7"),
        lambda e: e["native_command"].__setitem__(-1, "pkg.other.*"),
    ],
)
def test_a_manifest_whose_summary_contradicts_it_is_rejected(tmp_path, mutate):
    policy, document, attempt = _setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    mutate(manifest["execution"])
    path = _write(tmp_path, manifest)
    with pytest.raises(ValueError, match="contradicts"):
        mutation_campaign.load_sharded(tmp_path, tmp_path / "plan.json", [path])


def test_a_summary_with_missing_or_extra_fields_is_rejected(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    manifest["execution"]["note"] = "extra"
    path = _write(tmp_path, manifest)
    with pytest.raises(ValueError, match="invalid execution proof"):
        mutation_campaign.load_sharded(tmp_path, tmp_path / "plan.json", [path])


def test_shards_that_ran_different_suites_are_rejected_together():
    one = {"tests_sha256": "a", "dependencies_sha256": "d"}
    two = {"tests_sha256": "b", "dependencies_sha256": "d"}
    shards._check_common_suite([one, None, copy.deepcopy(one)])
    with pytest.raises(ValueError, match="different test suites"):
        shards._check_common_suite([one, two])
    with pytest.raises(ValueError, match="different test suites"):
        shards._check_common_suite([one, {**one, "dependencies_sha256": "x"}])


def test_a_forged_binding_or_edited_manifest_never_validates(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    manifest.pop("execution")
    path = _write(tmp_path, manifest)
    doc = evidence_schema.build_deep_shards(
        tmp_path / "plan.json", [path], root=tmp_path, source=SOURCE, execution=EXECUTION
    )
    doc["result"]["execution_binding"] = "controller-proof"
    doc["status"] = "PASS"
    assert any("current inputs" in p for p in evidence_schema.validate(doc, root=tmp_path))
    edited = json.loads(path.read_text())
    edited["records"][0]["outcome"] = "survived"
    path.write_text(json.dumps(edited))
    assert evidence_schema.validate(doc, root=tmp_path)


def test_the_command_line_carries_the_attempt_record_into_the_manifest(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    output = tmp_path / "evidence-shard-0.json"
    code = shards.main(
        ["build", "--root", str(tmp_path), "--plan", str(tmp_path / "plan.json"), "--index", "0",
         "--native-exit-code", "0", "--attempt", str(attempt), "--output", str(output)]
    )  # fmt: skip
    assert code == 0 and "execution" in json.loads(output.read_text())
    assert (
        hashlib.sha256(attempt.read_bytes()).hexdigest()
        == json.loads(output.read_text())["execution"]["attempt_sha256"]
    )
