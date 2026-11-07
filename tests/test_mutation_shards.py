"""Sharded campaigns are accepted only when complete, consistent and current."""

from __future__ import annotations

import copy
import hashlib
import sys

import pytest

from tests.test_mutation_campaign import _fixture
from tests.test_mutation_risk_policy import _campaign, _policy
from verification import mutation_catalog, mutation_policy
from verification import mutation_shards as shards

CONTEXT = {
    "revision": "r" * 40,
    "tests_sha256": "t" * 64,
    "configuration_sha256": "c" * 64,
    "runtime": {"python": "3.11", "mutmut": "3.8.0", "pytest": "9.1.1"},
}


def _build(tmp_path, counts=((98, 100), (98, 100), (49, 50)), levels=("L4", "L4", "L4"), count=2):
    policy = _policy(tmp_path, levels)
    catalog, records = _campaign(policy, list(counts))
    weights = {name: len(catalog[name]) for name in policy["units"]}
    document = shards.plan(policy, weights, count)
    manifests = []
    for shard in document["shards"]:
        names = set(shard["modules"])
        manifests.append(
            {
                "format": 1,
                "plan_sha256": document["sha256"],
                "index": shard["index"],
                "context": copy.deepcopy(CONTEXT),
                "modules": list(shard["modules"]),
                "sources": {
                    name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
                    for name in names
                },
                "catalog": {name: catalog[name] for name in names},
                "records": [r for r in records if r["path"] in names],
                "missing": [],
                "native_exit_code": 0,
            }
        )
    return policy, document, manifests


def test_the_plan_is_deterministic_balanced_and_covers_every_module_once(tmp_path):
    policy = _policy(tmp_path, ("L4",) * 5)
    weights = dict(zip(sorted(policy["units"]), [50, 40, 30, 20, 10], strict=True))
    first = shards.plan(policy, weights, 2)
    assert first == shards.plan(policy, weights, 2)
    assigned = sorted(name for shard in first["shards"] for name in shard["modules"])
    assert assigned == sorted(policy["units"])
    assert sorted(shard["weight"] for shard in first["shards"]) == [70, 80]
    shards.validate_plan(first, policy)


@pytest.mark.parametrize("count", [0, -1, True, "2"])
def test_invalid_shard_counts_are_refused(tmp_path, count):
    policy = _policy(tmp_path, ("L4",))
    with pytest.raises(ValueError, match="positive integer"):
        shards.plan(policy, {"app/unit0.py": 1}, count)


def test_weights_must_cover_exactly_the_mutating_modules(tmp_path):
    policy = _policy(tmp_path, ("L4", "L4"))
    with pytest.raises(ValueError, match="weights"):
        shards.plan(policy, {"app/unit0.py": 1}, 1)
    with pytest.raises(ValueError, match="weights"):
        shards.plan(policy, {"app/unit0.py": 1, "app/unit1.py": -1}, 1)


def test_a_tampered_or_foreign_plan_is_rejected(tmp_path):
    policy, document, _ = _build(tmp_path)
    changed = copy.deepcopy(document)
    changed["shards"][0]["modules"] = []
    with pytest.raises(ValueError, match="digest"):
        shards.validate_plan(changed, policy)
    other = copy.deepcopy(policy)
    other["units"]["app/unit0.py"]["reason"] = "Edited reason"
    with pytest.raises(ValueError, match="different policy"):
        shards.validate_plan(document, other)
    body = {key: changed[key] for key in ("format", "policy_sha256", "shards")}
    body["shards"][0]["modules"] = body["shards"][1]["modules"][:]
    forged = {**body, "sha256": shards._digest(body)}
    with pytest.raises(ValueError, match="exactly once"):
        shards.validate_plan(forged, policy)


def test_complete_consistent_shards_give_the_per_module_verdict(tmp_path):
    policy, document, manifests = _build(tmp_path)
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert result["status"] == "PASS" and result["shards"] == 2
    assert result["analysis"]["modules"]["app/unit2.py"]["killed"] == 49


def test_a_failing_module_fails_the_campaign_despite_passing_shards(tmp_path):
    policy, document, manifests = _build(tmp_path, counts=((100, 100), (96, 100), (50, 50)))
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert result["status"] == "FAIL"
    assert result["analysis"]["modules"]["app/unit0.py"]["status"] == "PASS"


def test_a_missing_or_duplicated_shard_is_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    with pytest.raises(ValueError, match="missing"):
        shards.aggregate(document, manifests[:1], policy, tmp_path, CONTEXT)
    with pytest.raises(ValueError, match="more than once"):
        shards.aggregate(
            document, [*manifests, copy.deepcopy(manifests[0])], policy, tmp_path, CONTEXT
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m["context"].__setitem__("revision", "x" * 40),
        lambda m: m["context"]["runtime"].__setitem__("pytest", "9.2.0"),
        lambda m: m.__setitem__("plan_sha256", "0" * 64),
        lambda m: m.__setitem__("modules", []),
    ],
)
def test_incompatible_or_foreign_shards_are_rejected(tmp_path, mutate):
    policy, document, manifests = _build(tmp_path)
    mutate(manifests[0])
    with pytest.raises(ValueError):
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)


def test_a_stale_source_is_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    (tmp_path / "app/unit0.py").write_text("def compute(value):\n    return value + 5\n")
    with pytest.raises(ValueError, match="stale"):
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)


def test_corrupted_or_conflicting_records_are_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    broken = copy.deepcopy(manifests)
    broken[0]["records"].append(dict(broken[0]["records"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        shards.aggregate(document, broken, policy, tmp_path, CONTEXT)
    foreign = copy.deepcopy(manifests)
    foreign[0]["records"][0] = {**foreign[0]["records"][0], "id": "app.unit9.x_compute__mutmut_1"}
    with pytest.raises(ValueError, match="unknown"):
        shards.aggregate(document, foreign, policy, tmp_path, CONTEXT)
    cross = copy.deepcopy(manifests)
    cross[1]["records"].append(copy.deepcopy(manifests[0]["records"][0]))
    with pytest.raises(ValueError, match="unknown"):
        shards.aggregate(document, cross, policy, tmp_path, CONTEXT)


def test_an_unrecorded_expected_mutant_leaves_the_campaign_incomplete(tmp_path):
    policy, document, manifests = _build(tmp_path)
    manifests[0]["records"].pop()
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert result["status"] == "INCOMPLETE"


def test_a_native_failure_or_missing_module_never_passes(tmp_path):
    policy, document, manifests = _build(tmp_path)
    manifests[1]["native_exit_code"] = 2
    assert (
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["status"] == "INCOMPLETE"
    )
    policy, document, manifests = _build(tmp_path)
    manifests[0]["missing"] = ["app/unit0.py"]
    assert (
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["status"] == "INCOMPLETE"
    )


def test_malformed_manifests_and_contexts_are_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    with pytest.raises(ValueError, match="invalid shard manifest"):
        shards.aggregate(document, [{"format": 1}, manifests[1]], policy, tmp_path, CONTEXT)
    with pytest.raises(ValueError, match="context"):
        shards.aggregate(document, manifests, policy, tmp_path, {"revision": "x"})


def test_a_failing_shard_keeps_its_evidence_apart_from_execution_failure(tmp_path):
    policy, document, manifests = _build(tmp_path, counts=((50, 100), (98, 100), (49, 50)))
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert (
        result["status"] == "FAIL"
        and result["analysis"]["modules"]["app/unit0.py"]["survived"] == 50
    )


def test_reviewed_equivalents_pass_through_the_aggregation(tmp_path):
    policy, document, manifests = _build(tmp_path, counts=((97, 99), (100, 100), (50, 50)))
    catalog = {n: k for m in manifests for n, k in m["catalog"].items()}
    survivor = next(r["id"] for m in manifests for r in m["records"] if r["outcome"] == "survived")
    path = next(r["path"] for m in manifests for r in m["records"] if r["id"] == survivor)
    assert shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["status"] == "FAIL"
    source = hashlib.sha256((tmp_path / path).read_bytes()).hexdigest()
    record = {
        "id": survivor, "path": path, "function": "compute", "diff": "d", "original_behavior": "o",
        "mutated_behavior": "m", "risk": "L4", "reason": "r", "evidence": ["e"],
        "source_sha256": source, "catalog_sha256": mutation_policy.catalog_digest(catalog[path]),
        "author": "a", "reviewer": "b", "approved": True, "review_date": "2026-11-08",
        "policy_version": 2,
    }  # fmt: skip
    equivalence = {"version": 1, "records": [record]}
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT, equivalence)
    assert result["status"] == "PASS" and result["analysis"]["accepted_equivalents"] == {
        path: [survivor]
    }


def test_a_shard_is_built_from_a_native_cache_and_aggregates_end_to_end(tmp_path):
    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path, survived=False)
    policy = __import__("json").loads(
        (tmp_path / "verification/mutation_risk_policy.json").read_text()
    )
    document = shards.plan(policy, {SOURCE: 2}, 1)
    manifest = shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, 0, CONTEXT, 0)
    assert manifest["catalog"][SOURCE] == ["pkg.a.x_compute__mutmut_1", "pkg.a.x_compute__mutmut_2"]
    assert [r["outcome"] for r in manifest["records"]] == ["killed", "killed"]
    result = shards.aggregate(document, [manifest], policy, tmp_path, CONTEXT)
    assert result["status"] == "PASS"
    assert mutation_catalog.read_modules(policy, tmp_path, tmp_path / "mutants", {SOURCE})[3] == []
    with pytest.raises(ValueError, match="outside the plan"):
        shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, 1, CONTEXT, 0)
    with pytest.raises(ValueError, match="context"):
        shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, 0, {}, 0)


def test_malformed_plans_and_shard_indexes_are_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    with pytest.raises(ValueError, match="invalid shard plan"):
        shards.validate_plan({"format": 2}, policy)
    body = {key: document[key] for key in ("format", "policy_sha256", "shards")}
    body["shards"] = [{**shard, "index": shard["index"] + 1} for shard in body["shards"]]
    with pytest.raises(ValueError, match="consecutive"):
        shards.validate_plan({**body, "sha256": shards._digest(body)}, policy)


def test_a_shard_reporting_a_foreign_module_is_rejected(tmp_path):
    policy, document, manifests = _build(tmp_path)
    manifests[0]["catalog"]["app/unit_other.py"] = []
    with pytest.raises(ValueError, match="outside its assignment"):
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)


def test_a_module_subset_read_skips_the_other_modules(tmp_path):
    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path)
    policy = __import__("json").loads(
        (tmp_path / "verification/mutation_risk_policy.json").read_text()
    )
    policy["units"]["src/pkg/other.py"] = {"level": "L1", "reason": "Constructed unit"}
    (tmp_path / "src/pkg/other.py").write_text("def f():\n    return 1\n")
    catalog = mutation_catalog.read_modules(policy, tmp_path, tmp_path / "mutants", {SOURCE})[0]
    assert set(catalog) == {SOURCE}


def _git_repository(root):
    import subprocess

    (root / "tests").mkdir(exist_ok=True)
    (root / "research/tests").mkdir(parents=True, exist_ok=True)
    (root / "tests/test_a.py").write_text("def test_a():\n    pass\n")
    (root / "research/tests/test_b.py").write_text("def test_b():\n    pass\n")
    (root / "pyproject.toml").write_text('[tool.mutmut]\nsource_paths=["src"]\n')
    for command in (
        ["init", "-q"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x"],
    ):
        subprocess.run(["git", *command], cwd=root, check=True, capture_output=True)


def test_the_context_binds_revision_tests_configuration_and_tools(tmp_path):
    _git_repository(tmp_path)
    context = shards.current_context(tmp_path)
    assert set(context) == set(shards.CONTEXT_KEYS) and len(context["revision"]) == 40
    assert set(context["runtime"]) == {"python", "mutmut", "pytest"}
    (tmp_path / "tests/test_a.py").write_text("def test_a():\n    assert True\n")
    assert shards.current_context(tmp_path)["tests_sha256"] != context["tests_sha256"]
    (tmp_path / "pyproject.toml").write_text('[tool.mutmut]\nsource_paths=["lib"]\n')
    assert (
        shards.current_context(tmp_path)["configuration_sha256"] != context["configuration_sha256"]
    )


def test_the_command_line_plans_builds_and_aggregates_a_campaign(tmp_path, capsys):
    import json

    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path, survived=False)
    _git_repository(tmp_path)
    policy_path = tmp_path / "verification/mutation_risk_policy.json"
    weights = tmp_path / "weights.json"
    weights.write_text(json.dumps({SOURCE: 2}))
    plan_path = tmp_path / "plan.json"
    assert shards.main(
        ["plan", "--policy", str(policy_path), "--weights", str(weights), "--count", "1",
         "--output", str(plan_path)]
    ) == 0  # fmt: skip
    manifest = tmp_path / "shard.json"
    assert shards.main(
        ["build", "--root", str(tmp_path), "--plan", str(plan_path), "--index", "0",
         "--native-exit-code", "0", "--output", str(manifest)]
    ) == 0  # fmt: skip
    report = tmp_path / "campaign.json"
    arguments = ["aggregate", "--root", str(tmp_path), "--plan", str(plan_path),
                 "--manifests", str(manifest), "--output", str(report)]  # fmt: skip
    assert shards.main(arguments) == 0
    assert "mutation campaign: PASS (1 shards)" in capsys.readouterr().out
    equivalence = tmp_path / "eq.json"
    equivalence.write_text(json.dumps({"version": 1, "records": []}))
    assert shards.main([*arguments, "--equivalence", str(equivalence)]) == 0
    context = tmp_path / "context.json"
    assert shards.main(["context", "--root", str(tmp_path), "--output", str(context)]) == 0
    assert json.loads(context.read_text())["runtime"]["mutmut"]
    broken = json.loads(manifest.read_text())
    broken["records"][0]["outcome"] = "survived"
    manifest.write_text(json.dumps(broken))
    assert shards.main(arguments) == 1


def test_running_the_module_as_a_script_exits_with_the_command_status(tmp_path, monkeypatch):
    import runpy

    monkeypatch.setattr(
        sys, "argv", ["mutation_shards", "context", "--output", str(tmp_path / "c")]
    )
    monkeypatch.chdir(tmp_path)
    _git_repository(tmp_path)
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(shards.__file__, run_name="__main__")
    assert caught.value.code == 0


def test_native_name_patterns_select_the_modules_of_one_shard(tmp_path, capsys):
    import json

    policy, document, _ = _build(tmp_path)
    assert shards.shard_patterns(document, 0) == [
        name[:-3].replace("/", ".") + ".*" for name in document["shards"][0]["modules"]
    ]
    with pytest.raises(ValueError, match="outside the plan"):
        shards.shard_patterns(document, 2)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(document))
    assert shards.main(["names", "--plan", str(path), "--index", "1"]) == 0
    assert capsys.readouterr().out.split() == shards.shard_patterns(document, 1)


def test_the_committed_weights_cover_exactly_the_mutating_modules():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / "verification/mutation_risk_policy.json").read_text())
    weights = json.loads((root / "verification/mutation_shard_weights.json").read_text())
    document = shards.plan(policy, weights, 6)
    shards.validate_plan(document, policy)
    assert max(s["weight"] for s in document["shards"]) < 0.3 * sum(weights.values())
