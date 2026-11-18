"""A shard is read from its own modules only, and the aggregate keeps the first native failure."""

import json

import pytest

from tests.test_mutation_campaign import _fixture
from tests.test_mutation_shards import CONTEXT, _build
from tests.verifier.test_mutation_run import SOURCE
from verification import mutation_shards as shards


@pytest.fixture(autouse=True)
def _tool_versions(monkeypatch):
    versions = {"mutmut": "3.8.0", "pytest": "9.1.1"}
    monkeypatch.setattr(shards, "version", lambda name: versions.get(name))


def test_a_shard_reads_only_its_own_modules_so_another_shards_cache_is_not_missing(tmp_path):
    _fixture(tmp_path, survived=False)
    other = "src/pkg/b.py"
    (tmp_path / other).write_text("def other():\n    return 1\n")
    policy_path = tmp_path / "verification/mutation_risk_policy.json"
    policy = json.loads(policy_path.read_text())
    policy["units"][other] = {"level": "L4", "reason": "Constructed second module"}
    policy_path.write_text(json.dumps(policy))
    document = shards.plan(policy, {SOURCE: 2, other: 2}, 2)
    index = next(s["index"] for s in document["shards"] if s["modules"] == [SOURCE])
    manifest = shards.build_shard(
        policy, tmp_path, tmp_path / "mutants", document, index, CONTEXT, 0
    )
    assert manifest["modules"] == [SOURCE]
    assert manifest["missing"] == []
    assert list(manifest["catalog"]) == [SOURCE]


def test_the_aggregate_reports_the_first_non_zero_native_exit_code(tmp_path):
    policy, document, manifests = _build(tmp_path)
    manifests[0]["native_exit_code"] = 0
    manifests[1]["native_exit_code"] = 3
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert result["native_exit_code"] == 3
    manifests[1]["native_exit_code"] = 0
    assert shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["native_exit_code"] == 0
    manifests[0]["native_exit_code"] = 1
    manifests[1]["native_exit_code"] = 2
    assert shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["native_exit_code"] == 1


@pytest.mark.parametrize("key", ["tests_sha256", "dependencies_sha256"])
def test_shards_that_ran_different_suites_or_dependencies_are_refused_with_their_reason(key):
    one = {"tests_sha256": "a", "dependencies_sha256": "d"}
    other = {**one, key: "z"}
    with pytest.raises(ValueError) as refused:
        shards._check_common_suite([one, None, other])
    assert str(refused.value) == "shards ran different test suites or dependencies"
    shards._check_common_suite([one, None, dict(one)])
    shards._check_common_suite([None, None])
