"""Sharded campaigns are accepted only when complete, consistent and current."""

from __future__ import annotations

import copy
import hashlib
import sys

import pytest

from tests import owner_review
from tests.test_mutation_campaign import _fixture
from tests.test_mutation_risk_policy import _campaign, _policy
from verification import mutation_catalog, mutation_policy
from verification import mutation_shards as shards


@pytest.fixture(autouse=True)
def _tool_versions(monkeypatch):
    """The unit tests must not depend on the mutation engine being installed."""
    versions = {"mutmut": "3.8.0", "pytest": "9.1.1"}
    monkeypatch.setattr(shards, "version", lambda name: versions.get(name))


CONTEXT = {
    "revision": "r" * 40,
    "tests_sha256": "t" * 64,
    "configuration_sha256": "c" * 64,
    "runtime": {
        "python": "3.11",
        "platform": "Linux-test",
        "packages": {"mutmut": "3.8.0", "pytest": "9.1.1"},
    },
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
    record = owner_review.record(
        survivor, path, source, mutation_policy.catalog_digest(catalog[path]),
        environment={"mutmut": "3.8.0", "pytest": "9.1.1"},
    )  # fmt: skip
    equivalence = owner_review.document(record)
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
    assert set(context["runtime"]) == {"python", "platform", "packages"}
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
    equivalence.write_text(json.dumps(owner_review.document()))
    assert shards.main([*arguments, "--equivalence", str(equivalence)]) == 0
    context = tmp_path / "context.json"
    assert shards.main(["context", "--root", str(tmp_path), "--output", str(context)]) == 0
    assert json.loads(context.read_text())["runtime"]["packages"]["mutmut"]
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


_REQUIRED = {
    "plan": ["--policy", "p", "--weights", "w", "--count", "1", "--output", "o"],
    "context": ["--output", "o"],
    "build": ["--plan", "p", "--index", "0", "--native-exit-code", "0", "--output", "o"],
    "names": ["--plan", "p", "--index", "0"],
    "aggregate": ["--plan", "p", "--manifests", "m", "--output", "o"],
}


@pytest.mark.parametrize(
    ("command", "flag"),
    [(command, flag) for command, args in _REQUIRED.items() for flag in args[::2]],
)
def test_every_command_line_argument_is_required(command, flag, capsys):
    arguments = list(_REQUIRED[command])
    index = arguments.index(flag)
    del arguments[index : index + 2]
    with pytest.raises(SystemExit) as caught:
        shards.main([command, *arguments])
    assert caught.value.code == 2 and flag in capsys.readouterr().err


def test_the_help_text_and_default_root_are_documented(capsys, tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        shards.main(["--help"])
    assert "Deterministic sharding of the mutation campaign" in capsys.readouterr().out
    _git_repository(tmp_path)
    monkeypatch.chdir(tmp_path)
    for command in ("build", "aggregate"):
        parsed = {
            "build": ["build", "--plan", "p", "--index", "0", "--native-exit-code", "0",
                      "--output", "o"],
            "aggregate": ["aggregate", "--plan", "p", "--manifests", "m", "--output", "o"],
        }[command]  # fmt: skip
        with pytest.raises((SystemExit, FileNotFoundError)):
            shards.main(parsed)
    shards.main(["context", "--output", str(tmp_path / "c.json")])
    assert (tmp_path / "c.json").exists()


def test_written_files_are_canonical_indented_json(tmp_path):
    import json

    policy_path = tmp_path / "policy.json"
    policy = _policy(tmp_path, ("L4", "L4"))
    policy_path.write_text(json.dumps(policy))
    weights = tmp_path / "weights.json"
    weights.write_text(json.dumps({"app/unit1.py": 3, "app/unit0.py": 3}))
    output = tmp_path / "plan.json"
    assert shards.main(
        ["plan", "--policy", str(policy_path), "--weights", str(weights), "--count", "2",
         "--output", str(output)]
    ) == 0  # fmt: skip
    text = output.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_zero_weights_are_allowed_and_equal_weights_keep_a_stable_name_order(tmp_path):
    policy = _policy(tmp_path, ("L4", "L4", "L4"))
    zero = dict.fromkeys(policy["units"], 0)
    document = shards.plan(policy, zero, 3)
    assert [shard["modules"] for shard in document["shards"]] == [
        ["app/unit0.py"], ["app/unit1.py"], ["app/unit2.py"],
    ]  # fmt: skip
    heavy = {"app/unit0.py": 1, "app/unit1.py": 5, "app/unit2.py": 5}
    document = shards.plan(policy, heavy, 2)
    assert document["shards"][0]["modules"] == ["app/unit0.py", "app/unit1.py"]
    assert document["shards"][1]["modules"] == ["app/unit2.py"]


def test_the_exact_refusal_for_a_shard_index_and_an_incomplete_flag(tmp_path):
    policy, document, manifests = _build(tmp_path)
    with pytest.raises(ValueError) as caught:
        shards.shard_patterns(document, -1)
    assert str(caught.value) == "shard index is outside the plan"
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert result["status"] == "PASS"
    manifests[0]["native_exit_code"] = "0"
    assert (
        shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)["status"] == "INCOMPLETE"
    )


def test_every_refusal_states_its_exact_reason(tmp_path):
    policy, document, manifests = _build(tmp_path)

    def message(call):
        with pytest.raises(ValueError) as caught:
            call()
        return str(caught.value)

    body = {key: document[key] for key in ("format", "policy_sha256", "shards")}
    assert message(lambda: shards.plan(policy, {}, 1)) == (
        "weights must cover exactly the mutating modules"
    )
    assert message(lambda: shards.plan(policy, dict.fromkeys(policy["units"], 1), 0)) == (
        "shard count must be a positive integer"
    )
    assert message(lambda: shards.validate_plan({}, policy)) == "invalid shard plan"
    assert message(lambda: shards.validate_plan({**document, "format": 9}, policy)) == (
        "invalid shard plan"
    )
    assert message(lambda: shards.validate_plan([], policy)) == "invalid shard plan"
    assert message(lambda: shards.validate_plan({**document, "sha256": "0" * 64}, policy)) == (
        "shard plan digest differs from its content"
    )
    other = copy.deepcopy(policy)
    other["units"]["app/unit0.py"]["reason"] = "Edited"
    assert message(lambda: shards.validate_plan(document, other)) == (
        "shard plan belongs to a different policy"
    )
    skewed = {**body, "shards": [{**s, "index": s["index"] + 1} for s in body["shards"]]}
    assert (
        message(lambda: shards.validate_plan({**skewed, "sha256": shards._digest(skewed)}, policy))
        == "shard indexes must be consecutive from zero"
    )
    empty = {**body, "shards": []}
    assert (
        message(lambda: shards.validate_plan({**empty, "sha256": shards._digest(empty)}, policy))
        == "shard indexes must be consecutive from zero"
    )
    dropped = {**body, "shards": [{**body["shards"][0], "modules": []}, *body["shards"][1:]]}
    assert (
        message(
            lambda: shards.validate_plan({**dropped, "sha256": shards._digest(dropped)}, policy)
        )
        == "shard plan must assign every mutating module exactly once"
    )
    assert message(lambda: shards.shard_patterns(document, 9)) == "shard index is outside the plan"
    assert message(
        lambda: shards.aggregate(document, manifests[:1], policy, tmp_path, CONTEXT)
    ) == ("shard evidence is missing or outside the plan")
    assert message(lambda: shards.aggregate(document, manifests, policy, tmp_path, {})) == (
        "shard context must bind revision, tests, configuration and runtime"
    )
    assert message(lambda: shards.aggregate(document, [{}], policy, tmp_path, CONTEXT)) == (
        "invalid shard manifest"
    )
    wrong_type = copy.deepcopy(manifests)
    wrong_type[0]["index"] = "0"
    assert message(lambda: shards.aggregate(document, wrong_type, policy, tmp_path, CONTEXT)) == (
        "invalid shard manifest"
    )
    wrong_format = copy.deepcopy(manifests)
    wrong_format[0]["format"] = 2
    assert message(lambda: shards.aggregate(document, wrong_format, policy, tmp_path, CONTEXT)) == (
        "invalid shard manifest"
    )


def test_the_digest_is_the_canonical_compact_sorted_json_hash():
    assert shards._digest({"b": [1, 2], "a": 1}) == hashlib.sha256(b'{"a":1,"b":[1,2]}').hexdigest()


def test_the_default_root_and_cache_are_the_working_directory_and_mutants(tmp_path, monkeypatch):
    import json

    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path, survived=False)
    _git_repository(tmp_path)
    monkeypatch.chdir(tmp_path)
    policy = json.loads((tmp_path / "verification/mutation_risk_policy.json").read_text())
    (tmp_path / "weights.json").write_text(json.dumps({SOURCE: 2}))
    shards.main(["plan", "--policy", "verification/mutation_risk_policy.json",
                 "--weights", "weights.json", "--count", "1", "--output", "plan.json"])  # fmt: skip
    shards.main(["build", "--plan", "plan.json", "--index", "0", "--native-exit-code", "0",
                 "--output", "shard.json"])  # fmt: skip
    assert shards.main(["aggregate", "--plan", "plan.json", "--manifests", "shard.json",
                        "--output", "campaign.json"]) == 0  # fmt: skip
    shard = json.loads((tmp_path / "shard.json").read_text())
    assert shard["context"]["tests_sha256"] and policy["units"]


def test_the_context_counts_both_test_trees_and_the_tool_versions(tmp_path):
    _git_repository(tmp_path)
    base = shards.current_context(tmp_path)["tests_sha256"]
    (tmp_path / "research/tests/test_b.py").write_text("def test_b():\n    assert True\n")
    assert shards.current_context(tmp_path)["tests_sha256"] != base
    (tmp_path / "tests/test_a.py").write_text("def test_a():\n    assert 1\n")
    assert shards.current_context(tmp_path)["tests_sha256"] != base
    runtime = shards.current_context(tmp_path)["runtime"]
    assert runtime["packages"]["mutmut"] == "3.8.0" and runtime["packages"]["pytest"] == "9.1.1"
    assert runtime["packages"]["numpy"] is None and set(runtime["packages"]) == set(shards.PACKAGES)


def test_aggregation_messages_and_result_fields_are_exact(tmp_path):
    policy, document, manifests = _build(tmp_path)
    result = shards.aggregate(document, manifests, policy, tmp_path, CONTEXT)
    assert set(result) == {
        "format", "plan_sha256", "context", "shards", "catalog", "records", "native_exit_code",
        "execution_bound", "analysis", "status",
    }  # fmt: skip
    assert result["format"] == 1 and result["plan_sha256"] == document["sha256"]
    assert result["context"] == CONTEXT

    def message(items):
        with pytest.raises(ValueError) as caught:
            shards.aggregate(document, items, policy, tmp_path, CONTEXT)
        return str(caught.value)

    foreign = copy.deepcopy(manifests)
    foreign[1]["plan_sha256"] = "0" * 64
    assert message(foreign) == "shard 1 does not belong to this plan"
    context = copy.deepcopy(manifests)
    context[0]["context"]["tests_sha256"] = "x"
    assert message(context) == "shard 0 was produced in a different context"
    names = copy.deepcopy(manifests)
    names[0]["sources"]["app/extra.py"] = "0" * 64
    assert message(names) == "shard 0 reports modules outside its assignment"
    stale = copy.deepcopy(manifests)
    stale[0]["sources"][next(iter(stale[0]["sources"]))] = "0" * 64
    assert "is stale for app/unit" in message(stale)
    first = copy.deepcopy(manifests)
    first[0]["records"].append(dict(first[0]["records"][0]))
    assert message(first) == "shard 0 has an unknown or duplicate mutant record"
    bad = copy.deepcopy(manifests)
    bad[0]["records"].append("not a record")
    assert message(bad) == "shard 0 has an unknown or duplicate mutant record"
    wrong_path = copy.deepcopy(manifests)
    other = manifests[1]["modules"][0]
    wrong_path[0]["records"][0] = {**wrong_path[0]["records"][0], "path": other}
    assert message(wrong_path) == "shard 0 has an unknown or duplicate mutant record"
    cross = copy.deepcopy(manifests)
    cross[0]["records"].append(copy.deepcopy(manifests[1]["records"][0]))
    assert message(cross) == "shard 0 has an unknown or duplicate mutant record"
    twice = copy.deepcopy(manifests)
    twice[1]["records"][0] = copy.deepcopy(twice[0]["records"][0])
    assert message(twice) == "shard 1 has an unknown or duplicate mutant record"


def test_building_a_shard_states_its_context_and_binds_every_field(tmp_path):
    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path, survived=True)
    policy = __import__("json").loads(
        (tmp_path / "verification/mutation_risk_policy.json").read_text()
    )
    document = shards.plan(policy, {SOURCE: 2}, 1)
    manifest = shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, 0, CONTEXT, 3)
    assert set(manifest) == shards.MANIFEST_KEYS
    assert manifest["format"] == 1 and manifest["plan_sha256"] == document["sha256"]
    assert manifest["index"] == 0 and manifest["context"] == CONTEXT
    assert manifest["modules"] == [SOURCE] and manifest["native_exit_code"] == 3
    assert manifest["sources"] == {
        SOURCE: hashlib.sha256((tmp_path / SOURCE).read_bytes()).hexdigest()
    }
    assert [r["outcome"] for r in manifest["records"]] == ["killed", "survived"]
    with pytest.raises(ValueError) as caught:
        shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, -1, CONTEXT, 0)
    assert str(caught.value) == "shard index is outside the plan"
    with pytest.raises(ValueError) as caught:
        shards.build_shard(policy, tmp_path, tmp_path / "mutants", document, 0, {}, 0)
    assert str(caught.value) == "shard context must bind revision, tests, configuration and runtime"
    stale = {**document, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="digest"):
        shards.build_shard(policy, tmp_path, tmp_path / "mutants", stale, 0, CONTEXT, 0)


def test_the_context_matches_the_checkout_and_the_interpreter(tmp_path):
    import subprocess
    import sys

    _git_repository(tmp_path)
    context = shards.current_context(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert context["revision"] == head
    assert context["runtime"]["python"] == "{}.{}.{}".format(*sys.version_info[:3])
    with pytest.raises(subprocess.CalledProcessError):
        shards.current_context(tmp_path.parent)


def test_the_command_line_reads_the_equivalence_file_and_names_use_spaces(tmp_path, capsys):
    import json

    from tests.verifier.test_mutation_run import SOURCE

    _fixture(tmp_path, survived=True)
    _git_repository(tmp_path)
    policy = json.loads((tmp_path / "verification/mutation_risk_policy.json").read_text())
    document = shards.plan({**policy, "units": policy["units"]}, {SOURCE: 2}, 1)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(document))
    manifest = tmp_path / "shard.json"
    shards.main(["build", "--root", str(tmp_path), "--plan", str(plan_path), "--index", "0",
                 "--native-exit-code", "0", "--output", str(manifest)])  # fmt: skip
    mutation_run = json.loads(manifest.read_text())
    survivor = mutation_run["records"][1]["id"]
    from verification import mutation_policy

    record = owner_review.record(
        survivor, SOURCE, mutation_run["sources"][SOURCE],
        mutation_policy.catalog_digest(mutation_run["catalog"][SOURCE]),
    )  # fmt: skip
    equivalence = tmp_path / "eq.json"
    equivalence.write_text(json.dumps(owner_review.document(record)))
    base = ["aggregate", "--root", str(tmp_path), "--plan", str(plan_path), "--manifests",
            str(manifest), "--output", str(tmp_path / "r.json")]  # fmt: skip
    assert shards.main(base) == 1
    assert shards.main([*base, "--equivalence", str(equivalence)]) == 0
    assert json.loads((tmp_path / "r.json").read_text())["analysis"]["accepted_equivalents"]
    two = {"shards": [{"index": 0, "modules": ["a/b.py", "c/d.py"]}]}
    plan_path.write_text(json.dumps(two))
    capsys.readouterr()
    shards.main(["names", "--plan", str(plan_path), "--index", "0"])
    assert capsys.readouterr().out.strip() == "a.b.* c.d.*"
