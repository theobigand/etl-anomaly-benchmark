"""An existing execution binding must survive the checks used by release evidence."""

import copy
import json

import pytest

from tests.verifier.test_mutation_execution import RUNTIME, SOURCES, _baseline
from verification import mutation_cache


def _validate(root, runtime=None):
    return mutation_cache.validate_execution(root, SOURCES, runtime=runtime)


def test_unchanged_bound_inputs_and_native_artifacts_validate(tmp_path):
    cache = _baseline(tmp_path)
    proof = _validate(tmp_path, RUNTIME)
    assert proof == json.loads((cache / mutation_cache.EXECUTION_RECORD).read_text())
    assert proof["native_exit_code"] == 0 and proof["settled"] == 2


@pytest.mark.parametrize("changed", [SOURCES[0], "tests/test_a.py", "pyproject.toml"])
def test_changed_execution_inputs_cannot_validate_an_old_binding(tmp_path, changed):
    _baseline(tmp_path)
    path = tmp_path / changed
    path.write_text(path.read_text() + "\n# input changed\n")
    with pytest.raises(ValueError, match="inputs"):
        _validate(tmp_path)


def test_changed_observed_runtime_cannot_be_accepted_as_the_recorded_one(tmp_path):
    _baseline(tmp_path)
    runtime = copy.deepcopy(RUNTIME)
    runtime["python"] = "3.11.18"
    with pytest.raises(ValueError, match="inputs"):
        _validate(tmp_path, runtime)


@pytest.mark.parametrize(
    "change", ["metadata", "missing_metadata", "native_source", "index", "statistics"]
)
def test_changed_native_artifacts_cannot_validate_an_old_binding(tmp_path, change):
    cache = _baseline(tmp_path)
    if change in {"metadata", "missing_metadata"}:
        path = cache / (SOURCES[0] + ".meta")
        if change == "missing_metadata":
            path.unlink()
        else:
            data = json.loads(path.read_text())
            data["exit_code_by_key"]["pkg.a.x_compute__mutmut_1"] = 0
            path.write_text(json.dumps(data))
    elif change == "statistics":
        path = cache / "mutmut-stats.json"
        data = json.loads(path.read_text())
        data["function_dependencies"] = {}
        path.write_text(json.dumps(data))
    else:
        path = cache / (SOURCES[0] + (".spans" if change == "index" else ""))
        path.write_text("changed generation artifact\n")
    with pytest.raises(ValueError):
        _validate(tmp_path)


@pytest.mark.parametrize("state", ["pending", "missing"])
def test_unresolved_or_absent_execution_cannot_be_validated(tmp_path, state):
    cache = _baseline(tmp_path)
    if state == "pending":
        (cache / mutation_cache.PENDING_EXECUTION).write_text("{}\n")
    else:
        (cache / mutation_cache.EXECUTION_RECORD).unlink()
    with pytest.raises(ValueError):
        _validate(tmp_path)


def test_policy_only_edits_do_not_invalidate_unchanged_execution(tmp_path):
    _baseline(tmp_path)
    folder = tmp_path / "verification"
    folder.mkdir()
    (folder / "mutation_risk_policy.json").write_text('{"version": 2}\n')
    assert _validate(tmp_path)["settled"] == 2


def test_recorded_settled_count_must_match_the_native_metadata(tmp_path):
    cache = _baseline(tmp_path)
    path = cache / mutation_cache.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    proof["settled"] += 1
    proof["sha256"] = mutation_cache._digest(
        {key: value for key, value in proof.items() if key != "sha256"}
    )
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="settled verdict count"):
        _validate(tmp_path)


def test_consistent_partial_execution_still_reports_its_nonzero_exit(tmp_path):
    from tests.verifier.test_mutation_execution import _fill, _prepare, _record, _repository

    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache, second=None)
    _record(tmp_path, exit_code=2)
    proof = _validate(tmp_path)
    assert proof["native_exit_code"] == 2 and proof["settled"] == 1
    assert "status" not in proof
