"""Campaign evidence must combine current inventory, native records and execution bindings."""

import hashlib
import importlib
import json
import platform
import sys
from pathlib import Path

import pytest

from tests.verifier.test_mutation_run import SOURCE, _repository
from verification import mutation_cache, mutation_run


def _api():
    return importlib.import_module("verification.mutation_campaign")


def _fixture(root, *, survived=False, exit_code=0):
    cache = _repository(root)
    runtime = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {"mutmut": "3.8.0", "pytest": "9.1.1"},
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "environment_sha256": {
            key: hashlib.sha256(value.encode()).hexdigest()
            for key, value in mutation_run.FIXED_ENV.items()
        },
        "native_command": mutation_run._command(2),
    }
    admission = mutation_cache.prepare_execution(root, [SOURCE], runtime=runtime)
    keys = [f"pkg.a.x_compute__mutmut_{n}" for n in [1, 2]]
    folder = cache / "src/pkg"
    folder.mkdir(parents=True)
    (cache / SOURCE).write_text(
        "def x_compute__mutmut_orig(value):\n    return value + 1\n\n"
        "def x_compute__mutmut_1(value):\n    return value - 1\n\n"
        "def x_compute__mutmut_2(value):\n    return value + 2\n"
    )
    (cache / (SOURCE + ".spans")).write_text(
        json.dumps(
            {
                "version": 1,
                "spans": {
                    "x_compute__mutmut_orig": [1, 2],
                    "x_compute__mutmut_1": [4, 5],
                    "x_compute__mutmut_2": [7, 8],
                },
            }
        )
    )
    (cache / (SOURCE + ".meta")).write_text(
        json.dumps(
            {
                "exit_code_by_key": {keys[0]: 1, keys[1]: 0 if survived else 1},
                "hash_by_function_name": {"x_compute": "5d6e4cd023bc"},
                "durations_by_key": {},
                "estimated_durations_by_key": {},
                "type_check_error_by_key": {},
            }
        )
    )
    (cache / "mutmut-stats.json").write_text("{}\n")
    proof = mutation_cache.record_execution(
        root, [SOURCE], runtime=runtime, native_exit_code=exit_code
    )
    attempt = cache / "attempts" / ("a" * 32)
    attempt.mkdir(parents=True)
    log = attempt / "native.log"
    log.write_text("constructed campaign fixture; not an experimental run\n")
    log_name = log.relative_to(root).as_posix()
    record = attempt / "execution.json"
    record.write_text(
        json.dumps(
            {
                "native_pid": 1,
                "admission": admission,
                "proof": proof,
                "native_log": log_name,
                "native_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            }
        )
    )
    run_report = {
        "native_exit_code": exit_code,
        "admission": admission,
        "proof_sha256": proof["sha256"],
        "native_log": log_name,
        "attempt_record": record.relative_to(root).as_posix(),
    }
    run_path = cache / "controller-result.json"
    run_path.write_text(json.dumps(run_report))
    stats = {
        "total": 2,
        "killed": 1 if survived else 2,
        "survived": 1 if survived else 0,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "check_was_interrupted_by_user": 0,
        "segfault": 0,
    }
    stats_path = cache / "mutmut-cicd-stats.json"
    stats_path.write_text(json.dumps(stats))
    listing = cache / "results.txt"
    listing.write_text(f"{keys[0]}: killed\n{keys[1]}: {'survived' if survived else 'killed'}\n")
    return stats_path, listing, run_path


def _load(root, inputs):
    return _api().load_campaign(root, *inputs)


def test_complete_campaign_retains_per_module_counts_and_required_raw_artifacts(tmp_path):
    inputs = _fixture(tmp_path)
    result, artifacts = _load(tmp_path, inputs)
    assert result["format_version"] == 2
    assert _api().status(result) == "PASS"
    unit = result["analysis"]["modules"][SOURCE]
    assert (unit["killed"], unit["eligible"], unit["threshold"]) == (2, 2, 98)
    assert len(result["records"]) == 2
    assert all(path in artifacts for path in inputs)
    assert tmp_path / "mutants/execution-context.json" in artifacts
    assert tmp_path / ("mutants/" + SOURCE + ".meta") in artifacts
    assert tmp_path / ("mutants/" + SOURCE + ".spans") in artifacts
    assert tmp_path / ("mutants/" + SOURCE) in artifacts


def test_survivors_are_not_removed_to_obtain_a_passing_campaign(tmp_path):
    result, _ = _load(tmp_path, _fixture(tmp_path, survived=True))
    assert _api().status(result) == "FAIL"
    unit = result["analysis"]["modules"][SOURCE]
    assert unit["eligible"] == 2 and unit["survived"] == 1


def test_nonzero_native_exit_blocks_even_complete_killed_counts(tmp_path):
    result, _ = _load(tmp_path, _fixture(tmp_path, exit_code=2))
    assert result["analysis"]["status"] == "PASS"
    assert _api().status(result) == "INCOMPLETE"


def test_known_mutation_failure_remains_visible_after_a_nonzero_exit(tmp_path):
    result, _ = _load(tmp_path, _fixture(tmp_path, survived=True, exit_code=2))
    assert _api().status(result) == "FAIL"


@pytest.mark.parametrize("field", ["status", "killed", "threshold"])
def test_stored_summary_cannot_override_the_recomputed_counts(tmp_path, field):
    result, _ = _load(tmp_path, _fixture(tmp_path, survived=True))
    if field == "status":
        result["analysis"]["status"] = "PASS"
    else:
        result["analysis"]["modules"][SOURCE][field] = 100
    with pytest.raises(ValueError):
        _api().status(result)


def test_policy_changes_recompute_compliance_without_reexecuting_unchanged_mutants(tmp_path):
    inputs = _fixture(tmp_path)
    old, _ = _load(tmp_path, inputs)
    path = tmp_path / "verification/mutation_risk_policy.json"
    policy = json.loads(path.read_text())
    policy["units"][SOURCE]["level"] = "L3"
    path.write_text(json.dumps(policy))
    current, _ = _load(tmp_path, inputs)
    assert current["analysis"]["modules"][SOURCE]["threshold"] == 95
    assert old["analysis"]["policy_sha256"] != current["analysis"]["policy_sha256"]
    assert old["execution_proof_sha256"] == current["execution_proof_sha256"]
    with pytest.raises(ValueError):
        _api().validate_current(old, tmp_path)


def test_new_unclassified_source_blocks_reuse_of_an_old_complete_report(tmp_path):
    inputs = _fixture(tmp_path)
    result, _ = _load(tmp_path, inputs)
    (tmp_path / "src/pkg/new.py").write_text("def new():\n    return 1\n")
    with pytest.raises(ValueError, match="unclassified"):
        _api().validate_current(result, tmp_path)


@pytest.mark.parametrize(
    "changed", ["source", "test", "generation", "pending", "log", "proof_pointer"]
)
def test_stale_or_unresolved_inputs_cannot_produce_a_current_campaign(tmp_path, changed):
    inputs = _fixture(tmp_path)
    cache = tmp_path / "mutants"
    if changed in {"source", "test", "generation"}:
        name = {"source": SOURCE, "test": "tests/test_a.py", "generation": "mutants/" + SOURCE}[
            changed
        ]
        path = tmp_path / name
        path.write_text(path.read_text() + "\n# changed\n")
    elif changed == "pending":
        (cache / "execution-pending.json").write_text("{}\n")
    else:
        path = inputs[2]
        data = json.loads(path.read_text())
        if changed == "log":
            (tmp_path / data["native_log"]).write_text("changed log\n")
        else:
            data["proof_sha256"] = "b" * 64
            path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        _load(tmp_path, inputs)


def _rewrite_proof(root, inputs, change):
    proof_path = root / "mutants/execution-context.json"
    proof = json.loads(proof_path.read_text())
    change(proof)
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    proof_path.write_text(json.dumps(proof))
    run = json.loads(inputs[2].read_text())
    run["proof_sha256"] = proof["sha256"]
    run["admission"]["context_sha256"] = mutation_cache._digest(proof["context"])
    inputs[2].write_text(json.dumps(run))
    path = root / run["attempt_record"]
    record = json.loads(path.read_text())
    record["proof"] = proof
    record["admission"] = run["admission"]
    path.write_text(json.dumps(record))


def test_unknown_declared_dependency_versions_cannot_support_a_campaign(tmp_path):
    inputs = _fixture(tmp_path)
    _rewrite_proof(
        tmp_path,
        inputs,
        lambda proof: proof["context"]["runtime"]["packages"].update({"numpy": None}),
    )
    with pytest.raises(ValueError, match="version|runtime"):
        _load(tmp_path, inputs)


def test_non_string_attempt_paths_are_rejected_as_invalid_evidence(tmp_path):
    inputs = _fixture(tmp_path)
    run = json.loads(inputs[2].read_text())
    run["attempt_record"] = None
    inputs[2].write_text(json.dumps(run))
    with pytest.raises(ValueError, match="paths"):
        _load(tmp_path, inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("python", None),
        ("platform", ""),
        ("executable_sha256", "invalid"),
        ("environment_sha256", None),
        ("environment_sha256", {}),
        ("native_command", None),
        ("native_command", []),
        ("native_command", ["relative-python", "-P", "-m", "mutmut", "run", "--max-children", "2"]),
        ("native_command", ["/usr/bin/python", "-P", "-m", "mutmut", "run", "--max-children", "0"]),
        ("native_command", ["/usr/bin/python", "-P", "-m", "other", "run", "--max-children", "2"]),
    ],
)
def test_self_consistent_but_invalid_runtime_claims_are_rejected(tmp_path, field, value):
    inputs = _fixture(tmp_path)
    _rewrite_proof(
        tmp_path, inputs, lambda proof: proof["context"]["runtime"].update({field: value})
    )
    with pytest.raises(ValueError, match="runtime|interpreter|environment"):
        _load(tmp_path, inputs)


@pytest.mark.parametrize("version", [None, 1, True])
def test_legacy_or_ambiguous_formats_cannot_be_used_as_current_campaigns(tmp_path, version):
    result, _ = _load(tmp_path, _fixture(tmp_path))
    result["format_version"] = version
    with pytest.raises(ValueError, match="format"):
        _api().status(result)


@pytest.mark.parametrize("paths", [None, {}, {"stats": "mutants/stats.json"}])
def test_current_validation_requires_all_raw_input_paths(tmp_path, paths):
    result, _ = _load(tmp_path, _fixture(tmp_path))
    result["paths"] = paths
    with pytest.raises(ValueError, match="paths"):
        _api().validate_current(result, tmp_path)


def test_current_validation_reloads_the_unmodified_campaign(tmp_path):
    result, _ = _load(tmp_path, _fixture(tmp_path))
    assert _api().validate_current(result, tmp_path)


def test_current_validation_returns_the_artifacts_that_the_envelope_must_bind(tmp_path):
    result, artifacts = _load(tmp_path, _fixture(tmp_path))
    assert set(_api().validate_current(result, tmp_path)) == set(artifacts)


def test_a_recorded_input_failure_remains_incomplete_without_a_passing_summary():
    assert (
        _api().status({"format_version": 2, "reason": "native execution proof is missing"})
        == "INCOMPLETE"
    )


def test_native_outcomes_cannot_change_between_binding_check_and_report_assembly(
    tmp_path, monkeypatch
):
    inputs = _fixture(tmp_path, survived=True)
    original = mutation_cache.validate_execution
    changed = False

    def checked_then_changed(*args, **kwargs):
        nonlocal changed
        proof = original(*args, **kwargs)
        if not changed:
            changed = True
            path = tmp_path / ("mutants/" + SOURCE + ".meta")
            data = json.loads(path.read_text())
            data["exit_code_by_key"]["pkg.a.x_compute__mutmut_2"] = 1
            path.write_text(json.dumps(data))
            stats = json.loads(inputs[0].read_text())
            stats.update(killed=2, survived=0)
            inputs[0].write_text(json.dumps(stats))
            inputs[1].write_text(
                "pkg.a.x_compute__mutmut_1: killed\npkg.a.x_compute__mutmut_2: killed\n"
            )
        return proof

    monkeypatch.setattr(mutation_cache, "validate_execution", checked_then_changed)
    with pytest.raises(ValueError, match="metadata|binding"):
        _load(tmp_path, inputs)


def test_reported_artifacts_suffice_to_validate_a_transferred_campaign(tmp_path):
    import shutil

    original = tmp_path / "original"
    original.mkdir()
    inputs = _fixture(original)
    graph = original / "mutants/mutmut-stats.json"
    graph.write_text(
        json.dumps(
            {
                "tests_by_mangled_function_name": {"pkg.a.x_compute": ["tests/test_a.py::test_a"]},
                "function_dependencies": {},
            }
        )
    )
    _rewrite_proof(
        original,
        inputs,
        lambda proof: proof.update({"statistics": mutation_cache._statistics(original)}),
    )
    result, artifacts = _load(original, inputs)
    transferred = tmp_path / "transferred"
    for path in [
        original / SOURCE,
        original / "tests/test_a.py",
        original / "pyproject.toml",
        original / "verification/mutation_risk_policy.json",
        *artifacts,
    ]:
        target = transferred / path.relative_to(original)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    assert _api().validate_current(result, transferred)
