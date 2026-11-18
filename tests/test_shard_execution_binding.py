"""Sharded campaigns pass only with a verified, shard-specific execution proof."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess

import pytest

from tests import owner_review
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


def _diagnostic_setup(tmp_path):
    from verification import mutation_policy

    policy, document, attempt = _setup(tmp_path, survived=True)
    attempt_data = json.loads(attempt.read_text())
    proof = attempt_data["proof"]
    old = proof["context"]
    proof["context"] = mutation_cache.capture_context(
        tmp_path, sorted(old["sources"]), runtime=old["runtime"],
        mutated_sources=old["mutation_scope"],
    )  # fmt: skip
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    attempt_data["admission"]["context_sha256"] = mutation_cache._digest(proof["context"])
    attempt.write_text(json.dumps(attempt_data))
    (tmp_path / "mutants/execution-context.json").write_text(json.dumps(proof))
    manifest = _build(tmp_path, policy, document, attempt)
    survivor = next(r["id"] for r in manifest["records"] if r["outcome"] == "survived")
    record = owner_review.record(
        survivor, MODULE, manifest["sources"][MODULE],
        mutation_policy.catalog_digest(manifest["catalog"][MODULE]),
    )  # fmt: skip
    equivalence = owner_review.document(record)
    (tmp_path / "verification/mutation_equivalence.json").write_text(json.dumps(equivalence))
    subprocess.run(
        ["git", "add", "src", "tests", "research/tests", "verification", "pyproject.toml"],
        cwd=tmp_path, check=True, capture_output=True,
    )  # fmt: skip
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture"],
        cwd=tmp_path, check=True, capture_output=True,
    )  # fmt: skip
    return policy, document, attempt, equivalence, survivor


def test_diagnostic_validates_owner_records_only_for_a_complete_bound_shard(tmp_path):
    policy, document, attempt, equivalence, survivor = _diagnostic_setup(tmp_path)
    probe = tmp_path / "CaseCheck"
    probe.write_text("probe")
    expected_case_sensitive = not (tmp_path / "casecheck").exists()
    probe.unlink()
    result = shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    assert result["scope"] == "single-shard diagnostic; not a campaign or certification"
    assert result["modules"][MODULE]["equivalent_accepted"] == 1
    assert result["modules"][MODULE]["score"] == 100.0
    assert result["accepted"][MODULE] == [survivor]
    assert result["filesystem_case_sensitive"] is expected_case_sensitive
    (tmp_path / "tests/test_a.py").write_text("changed since execution")
    with pytest.raises(ValueError, match="tracked files changed"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_a_foreign_policy_and_missing_document(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    foreign = copy.deepcopy(policy)
    foreign["units"][MODULE]["reason"] = "foreign"
    with pytest.raises(ValueError, match="checked-out policy"):
        shards.diagnostic_equivalences(document, foreign, tmp_path, 0, attempt, equivalence)
    with pytest.raises(ValueError, match="requires an equivalence document"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, None)
    foreign_document = copy.deepcopy(equivalence)
    foreign_document["owner"] = "different"
    with pytest.raises(ValueError, match="checked-out equivalence"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, foreign_document)


def test_diagnostic_rejects_untracked_test_inputs(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    (tmp_path / "tests/untracked.py").write_text("untracked input")
    with pytest.raises(ValueError, match="untracked test inputs"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_a_clean_commit_with_stale_execution_inputs(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    (tmp_path / "tests/test_a.py").write_text("changed since execution")
    subprocess.run(["git", "add", "tests/test_a.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "new tests"],
        cwd=tmp_path, check=True, capture_output=True,
    )  # fmt: skip
    with pytest.raises(ValueError, match="execution inputs differ"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_incompatible_owner_environment_and_changed_metadata(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    equivalence["records"][0]["environment"]["mutmut"] = "different"
    (tmp_path / "verification/mutation_equivalence.json").write_text(json.dumps(equivalence))
    subprocess.run(
        ["git", "add", "verification/mutation_equivalence.json"],
        cwd=tmp_path, check=True, capture_output=True,
    )  # fmt: skip
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "environment"],
        cwd=tmp_path, check=True, capture_output=True,
    )  # fmt: skip
    with pytest.raises(ValueError, match="incompatible with the campaign environment"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    meta = tmp_path / "mutants" / f"{MODULE}.meta"
    data = json.loads(meta.read_text())
    data["exit_code_by_key"][equivalence["records"][0]["id"]] = 1
    meta.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="bind the shard verdict metadata"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_an_incomplete_shard_even_with_a_matching_proof(tmp_path):
    from verification import mutation_catalog

    policy, document, attempt, equivalence, survivor = _diagnostic_setup(tmp_path)
    meta = tmp_path / "mutants" / f"{MODULE}.meta"
    data = json.loads(meta.read_text())
    data["exit_code_by_key"][survivor] = None
    meta.write_text(json.dumps(data))
    record = json.loads(attempt.read_text())
    proof = record["proof"]
    proof["metadata_sha256"][f"{MODULE}.meta"] = mutation_catalog.metadata_digest(data)
    proof["settled"] = 1
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    attempt.write_text(json.dumps(record))
    (tmp_path / "mutants/execution-context.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="incomplete mutant outcomes"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_missing_shard_metadata(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    (tmp_path / "mutants" / f"{MODULE}.meta").unlink()
    with pytest.raises(ValueError, match="incomplete mutant outcomes"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_changed_generated_mutant_source(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    generated = tmp_path / "mutants" / MODULE
    generated.write_text(generated.read_text() + "\n# changed after execution\n")
    with pytest.raises(ValueError, match="native generation artifacts differ"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_attempt_that_differs_from_saved_execution_proof(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    record = json.loads(attempt.read_text())
    proof = record["proof"]
    proof["settled"] += 1
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    attempt.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="differs from the current execution proof"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_rejects_an_empty_mutant_catalog(tmp_path):
    from verification import mutation_catalog

    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    meta = tmp_path / "mutants" / f"{MODULE}.meta"
    data = json.loads(meta.read_text())
    data["exit_code_by_key"] = {}
    data["hash_by_function_name"] = {}
    meta.write_text(json.dumps(data))
    spans = tmp_path / "mutants" / f"{MODULE}.spans"
    spans.write_text(json.dumps({"version": 1, "spans": {}}))
    record = json.loads(attempt.read_text())
    proof = record["proof"]
    proof["metadata_sha256"][f"{MODULE}.meta"] = mutation_catalog.metadata_digest(data)
    proof["native_artifacts_sha256"][f"{MODULE}.spans"] = hashlib.sha256(
        spans.read_bytes()
    ).hexdigest()
    proof["settled"] = 0
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    attempt.write_text(json.dumps(record))
    (tmp_path / "mutants/execution-context.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="incomplete mutant outcomes"):
        shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)


def test_diagnostic_command_records_the_exact_owner_document_digest(tmp_path):
    _, _, attempt, equivalence, survivor = _diagnostic_setup(tmp_path)
    eq_path = tmp_path / "verification/mutation_equivalence.json"
    output = tmp_path / "diagnostic.json"
    assert shards.main([
        "diagnostic-equivalences", "--root", str(tmp_path), "--plan", str(tmp_path / "plan.json"),
        "--index", "0", "--attempt", str(attempt), "--output", str(output),
    ]) == 0  # fmt: skip
    result = json.loads(output.read_text())
    assert result["accepted"][MODULE] == [survivor]
    assert result["equivalence_file_sha256"] == hashlib.sha256(eq_path.read_bytes()).hexdigest()


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
            lambda r, p: p["metadata_sha256"].__setitem__(f"{MODULE}.meta", "0" * 64),
            "verdict metadata",
        ),
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
