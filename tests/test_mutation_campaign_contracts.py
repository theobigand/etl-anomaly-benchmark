"""Exact reasons for every way a stored campaign, its runtime claim or its bindings can be wrong."""

import copy
import hashlib
import json

import pytest

from tests.test_mutation_campaign import _api, _fixture, _load
from verification import mutation_run


def _refused(call, message):
    with pytest.raises(ValueError) as refused:
        call()
    assert str(refused.value) == message


def _runtime_proof():
    return {
        "context": {
            "runtime": {
                "python": "3.11.1",
                "platform": "Linux-test",
                "executable_sha256": "a" * 64,
                "packages": {"mutmut": "3.8.0", "pytest": "9.1.1"},
                "environment_sha256": {
                    key: hashlib.sha256(value.encode()).hexdigest()
                    for key, value in mutation_run.FIXED_ENV.items()
                },
                "native_command": [
                    "/usr/bin/python",
                    "-P",
                    "-m",
                    "mutmut",
                    "run",
                    "--max-children",
                    "2",
                ],
            }
        }
    }


def _runtime(edit):
    proof = _runtime_proof()
    edit(proof["context"]["runtime"])
    return proof


RUNNER = "execution runtime does not identify the supported native runner"
COMMAND = "/usr/bin/python", "-P", "-m", "mutmut", "run", "--max-children"


def test_a_complete_runtime_claim_is_accepted_even_with_a_single_native_child():
    assert _api()._runtime(_runtime_proof()) is None
    one = _runtime(lambda r: r.update(native_command=[*COMMAND, "1"]))
    assert _api()._runtime(one) is None
    many = _runtime(lambda r: r.update(native_command=[*COMMAND, "12"]))
    assert _api()._runtime(many) is None


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r.update(native_command="python"),
        lambda r: r.update(native_command=None),
        lambda r: r.update(native_command=[*COMMAND]),
        lambda r: r.update(native_command=[*COMMAND, "2", "x"]),
        lambda r: r.update(
            native_command=["/usr/bin/python", "-m", "mutmut", "run", "-x", "2", "3"]
        ),
        lambda r: r.update(native_command=[5, *COMMAND[1:], "2"]),
        lambda r: r.update(native_command=["python", *COMMAND[1:], "2"]),
        lambda r: r.update(native_command=[*COMMAND, 2]),
        lambda r: r.update(native_command=[*COMMAND, "two"]),
        lambda r: r.update(native_command=[*COMMAND, "0"]),
        lambda r: r.update(packages={"mutmut": "3.9.0", "pytest": "9"}),
        lambda r: r.update(packages={"mutmut": "3.8.0"}),
        lambda r: r.update(packages={"mutmut": "3.8.0", "pytest": 9}),
        lambda r: r.update(packages={"mutmut": "3.8.0", "pytest": ""}),
        lambda r: r.update(packages={"mutmut": "3.8.0", "pytest": "9", "numpy": ""}),
        lambda r: r.update(packages={"mutmut": "3.8.0", "pytest": "9", "numpy": 5}),
    ],
)
def test_a_runtime_that_does_not_identify_the_native_runner_is_refused_for_each_fault(edit):
    _refused(lambda: _api()._runtime(_runtime(edit)), RUNNER)


@pytest.mark.parametrize("name", ["python", "platform", "executable_sha256"])
@pytest.mark.parametrize("value", [None, "", 5])
def test_a_runtime_missing_one_identity_field_is_refused_as_incomplete(name, value):
    proof = _runtime(lambda r: r.update({name: value}))
    _refused(lambda: _api()._runtime(proof), "execution runtime identity is incomplete")


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "a" * 65, "g" * 64])
def test_an_interpreter_hash_must_be_a_lowercase_sha256(digest):
    proof = _runtime(lambda r: r.update(executable_sha256=digest))
    _refused(lambda: _api()._runtime(proof), "execution interpreter hash is invalid")


@pytest.mark.parametrize("environment", [None, [], {}, {"OMP_NUM_THREADS": "0"}])
def test_an_environment_that_differs_from_the_launch_settings_is_refused(environment):
    proof = _runtime(lambda r: r.update(environment_sha256=environment))
    _refused(
        lambda: _api()._runtime(proof),
        "execution environment does not match the native launch settings",
    )


@pytest.mark.parametrize("version", [None, 1, True, 3])
def test_a_stored_campaign_of_another_format_is_refused_with_its_reason(version):
    _refused(
        lambda: _api().status({"format_version": version}), "mutation campaign format must be 2"
    )


def test_an_incomplete_campaign_is_reported_incomplete_only_with_exactly_a_reason():
    assert _api().status({"format_version": 2, "reason": "inputs missing"}) == "INCOMPLETE"
    for result in (
        {"format_version": 2, "reason": "x", "extra": 1},
        {"format_version": 2, "reason": 5},
        {"format_version": 2, "reason": ""},
        {"format_version": 2, "reason": None},
    ):
        _refused(
            lambda r=result: _api().status(r), "incomplete campaign must state its input failure"
        )


def test_stored_arithmetic_that_differs_from_the_recomputation_is_refused_with_its_reason(
    tmp_path, monkeypatch
):
    result, _ = _load(tmp_path, _fixture(tmp_path))
    assert _api().status(result) == "PASS"
    stored = copy.deepcopy(result)
    stored["analysis"]["status"] = "FAIL"
    _refused(
        lambda: _api().status(stored),
        "stored mutation arithmetic differs from the recomputed result",
    )
    odd = {**result, "native_exit_code": True}
    _refused(
        lambda: _api().status(odd), "stored mutation arithmetic differs from the recomputed result"
    )


def test_a_stored_result_that_no_longer_matches_the_current_files_is_refused_with_its_reason(
    monkeypatch, tmp_path
):
    api = _api()
    monkeypatch.setattr(api, "load_sharded", lambda root, plan, manifests: ({"fresh": 1}, []))
    monkeypatch.setattr(api, "load_campaign", lambda root, *inputs: ({"fresh": 1}, []))
    _refused(
        lambda: api.validate_current(
            {"mode": "sharded", "paths": {"plan": "p", "manifests": []}}, tmp_path
        ),
        "stored campaign differs from current policy, source or evidence",
    )
    _refused(
        lambda: api.validate_current(
            {"paths": {"stats": "mutants/s", "results": "mutants/r", "run": "mutants/u"}}, tmp_path
        ),
        "stored campaign differs from current policy, source or execution",
    )


@pytest.mark.parametrize("paths", [None, {}, {"plan": "p"}, {"plan": "p", "manifests": [], "x": 1}])
def test_a_sharded_result_must_name_its_plan_and_manifests_and_nothing_else(paths):
    _refused(
        lambda: _api().validate_current({"mode": "sharded", "paths": paths}, None),
        "sharded campaign artifact paths are incomplete",
    )


@pytest.mark.parametrize(
    "paths", [None, {}, {"stats": "s"}, {"stats": "s", "results": "r", "run": "u", "x": 1}]
)
def test_a_monolithic_result_must_name_its_three_raw_inputs_and_nothing_else(paths):
    _refused(
        lambda: _api().validate_current({"paths": paths}, None),
        "campaign artifact paths are incomplete",
    )


def _tamper(tmp_path, inputs, edit_run=None, edit_record=None):
    run_path = inputs[2]
    run = json.loads(run_path.read_text())
    record_path = tmp_path / run["attempt_record"]
    record = json.loads(record_path.read_text())
    if edit_run:
        edit_run(run)
    if edit_record:
        edit_record(record)
    run_path.write_text(json.dumps(run))
    record_path.write_text(json.dumps(record))


def test_a_controller_result_that_differs_from_the_proof_is_refused_with_its_reason(tmp_path):
    inputs = _fixture(tmp_path)
    _tamper(tmp_path, inputs, lambda run: run.update(proof_sha256="0" * 64))
    _refused(lambda: _load(tmp_path, inputs), "controller result differs from the execution proof")


@pytest.mark.parametrize("code", [False, "0", None, 1])
def test_a_controller_exit_code_must_be_the_integer_of_the_proof(tmp_path, code):
    inputs = _fixture(tmp_path)
    _tamper(tmp_path, inputs, lambda run: run.update(native_exit_code=code))
    _refused(lambda: _load(tmp_path, inputs), "controller result differs from the execution proof")


@pytest.mark.parametrize("name", [None, 5, "mutants/attempts/x/execution.json"])
def test_the_attempt_record_path_must_be_canonical(tmp_path, name):
    inputs = _fixture(tmp_path)
    _tamper(tmp_path, inputs, lambda run: run.update(attempt_record=name))
    _refused(lambda: _load(tmp_path, inputs), "controller attempt paths are not canonical")


def test_the_native_log_path_must_belong_to_the_same_attempt(tmp_path):
    inputs = _fixture(tmp_path)
    _tamper(
        tmp_path,
        inputs,
        lambda run: run.update(native_log="mutants/attempts/" + "b" * 32 + "/native.log"),
    )
    _refused(lambda: _load(tmp_path, inputs), "controller attempt paths are not canonical")


IMMUTABLE = "immutable attempt record or native log differs from its binding"


@pytest.mark.parametrize(
    "edit",
    [
        lambda run, record: record.update(proof={"other": 1}),
        lambda run, record: record.update(admission={"context_sha256": "x"}),
        lambda run, record: run.update(admission=None) or record.update(admission=None),
        lambda run, record: run.update(admission="x") or record.update(admission="x"),
        lambda run, record: (
            run["admission"].update(context_sha256="0" * 64)
            or record["admission"].update(context_sha256="0" * 64)
        ),
        lambda run, record: record.update(native_log="mutants/attempts/other/native.log"),
        lambda run, record: record.update(native_log_sha256="0" * 64),
        lambda run, record: record.update(native_pid="1"),
        lambda run, record: record.update(native_pid=True),
        lambda run, record: record.update(native_pid=0),
        lambda run, record: record.update(native_pid=-3),
    ],
)
def test_an_attempt_record_that_differs_from_its_binding_is_refused_for_each_fault(tmp_path, edit):
    inputs = _fixture(tmp_path)
    run = json.loads(inputs[2].read_text())
    record_path = tmp_path / run["attempt_record"]
    record = json.loads(record_path.read_text())
    edit(run, record)
    inputs[2].write_text(json.dumps(run))
    record_path.write_text(json.dumps(record))
    _refused(lambda: _load(tmp_path, inputs), IMMUTABLE)


def test_native_metadata_that_differs_from_the_binding_is_refused_with_its_reason(
    tmp_path, monkeypatch
):
    inputs = _fixture(tmp_path)
    api = _api()
    real = api.mutation_catalog.read_native

    def altered(*args, **kwargs):
        native = real(*args, **kwargs)
        return {**native, "metadata_sha256": {k: "0" * 64 for k in native["metadata_sha256"]}}

    monkeypatch.setattr(api.mutation_catalog, "read_native", altered)
    _refused(
        lambda: _load(tmp_path, inputs), "parsed native metadata differs from the execution binding"
    )


def test_an_execution_binding_that_changes_while_the_campaign_is_read_is_refused(
    tmp_path, monkeypatch
):
    inputs = _fixture(tmp_path)
    api = _api()
    original = api.mutation_cache.validate_execution
    calls = []

    def changed(*args, **kwargs):
        calls.append(kwargs)
        proof = original(*args, **kwargs)
        return proof if len(calls) == 1 else {**proof, "sha256": "f" * 64}

    monkeypatch.setattr(api.mutation_cache, "validate_execution", changed)
    _refused(
        lambda: _load(tmp_path, inputs), "execution binding changed while the campaign was read"
    )
    assert all(call.get("mutated_sources") for call in calls) and len(calls) == 2


def test_a_campaign_keeps_the_native_statistics_and_the_dependency_graph_among_its_inputs(tmp_path):
    inputs = _fixture(tmp_path)
    result, artifacts = _load(tmp_path, inputs)
    assert result["native_stats"] == json.loads(inputs[0].read_text())
    assert tmp_path / "mutants" / "mutmut-stats.json" in artifacts


def test_a_sharded_campaign_requires_the_inspected_mutmut(tmp_path, monkeypatch):
    api = _api()
    context = {"runtime": {"packages": {"mutmut": "3.9.0"}}}
    monkeypatch.setattr(api.mutation_shards, "current_context", lambda root: context)
    (tmp_path / "verification").mkdir()
    (tmp_path / "verification/mutation_risk_policy.json").write_text("{}")
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    _refused(
        lambda: api.load_sharded(tmp_path, plan, []),
        "sharded campaign requires the inspected mutmut 3.8.0",
    )
