"""Execution bindings must precede verdict reuse, including partial campaigns."""

import copy
import json

import pytest

from verification import mutation_cache as mc

SOURCES = ["src/pkg/a.py", "src/pkg/b.py"]
RUNTIME = {"python": "3.11.17", "platform": "isolated-test", "packages": {"mutmut": "3.8.0"}}


def _repository(tmp_path):
    for name, source in [
        (SOURCES[0], "def compute(value):\n    return value + 1\n"),
        (SOURCES[1], "from .a import compute\ndef run(value):\n    return compute(value)\n"),
        ("tests/test_a.py", "def test_a():\n    assert True\n"),
        ("tests/test_b.py", "def test_b():\n    assert True\n"),
        ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-q"\n'),
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    cache = tmp_path / "mutants"
    for name, key, local, fingerprint in [
        (SOURCES[0], "pkg.a.x_compute__mutmut_1", "x_compute", "5d6e4cd023bc"),
        (SOURCES[1], "pkg.b.x_run__mutmut_1", "x_run", "39691ec67170"),
    ]:
        path = cache / (name + ".meta")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "exit_code_by_key": {key: 1},
                    "hash_by_function_name": {local: fingerprint},
                    "durations_by_key": {},
                    "estimated_durations_by_key": {},
                    "type_check_error_by_key": {},
                }
            )
        )
    (cache / "mutmut-stats.json").write_text(
        json.dumps(
            {
                "tests_by_mangled_function_name": {
                    "pkg.a.x_compute": ["tests/test_a.py::test_a"],
                    "pkg.b.x_run": ["tests/test_b.py::test_b"],
                },
                "function_dependencies": {"pkg.a.x_compute": ["pkg.b.x_run"]},
            }
        )
    )
    for name in SOURCES:
        generated = cache / name
        generated.write_text((tmp_path / name).read_text())
        (cache / (name + ".spans")).write_text("{}\n")
    return cache


def _prepare(root, *, runtime=None, sources=SOURCES):
    return mc.prepare_execution(root, sources, runtime=runtime or RUNTIME)


def _fill(cache, first=1, second=1):
    for path, code in zip(SOURCES, [first, second], strict=True):
        meta = cache / (path + ".meta")
        data = json.loads(meta.read_text())
        data["exit_code_by_key"] = {key: code for key in data["exit_code_by_key"]}
        meta.write_text(json.dumps(data))


def _record(root, exit_code=0):
    return mc.record_execution(root, SOURCES, runtime=RUNTIME, native_exit_code=exit_code)


def _baseline(root):
    cache = _repository(root)
    _prepare(root)
    _fill(cache)
    _record(root)
    return cache


def test_an_unbound_cache_cannot_be_backstamped_as_a_current_execution(tmp_path):
    cache = _repository(tmp_path)
    result = _prepare(tmp_path)
    assert result["reset"] == 2 and result["kept"] == 0
    for name in SOURCES:
        assert set(
            json.loads((cache / (name + ".meta")).read_text())["exit_code_by_key"].values()
        ) == {None}


def test_current_bound_verdicts_are_reused_without_resetting_them(tmp_path):
    _baseline(tmp_path)
    result = _prepare(tmp_path)
    assert result["kept"] == 2 and result["reset"] == 0


def test_a_changed_function_invalidates_its_transitive_callers(tmp_path):
    _baseline(tmp_path)
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = _prepare(tmp_path)
    assert result["reset"] == 2 and result["kept"] == 0


def test_changed_killer_tests_keep_unrelated_valid_kills(tmp_path):
    _baseline(tmp_path)
    (tmp_path / "tests/test_a.py").write_text("def test_a():\n    assert False\n")
    result = _prepare(tmp_path)
    assert result["reset"] == 1 and result["kept"] == 1


@pytest.mark.parametrize("change", ["runtime", "configuration", "globals"])
def test_execution_affecting_changes_require_broader_invalidation(tmp_path, change):
    _baseline(tmp_path)
    runtime = copy.deepcopy(RUNTIME)
    if change == "runtime":
        runtime["python"] = "3.11.18"
    elif change == "configuration":
        (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-q -x"\n')
    else:
        path = tmp_path / SOURCES[0]
        path.write_text("GLOBAL_SCALE = 2\n" + path.read_text())
    result = _prepare(tmp_path, runtime=runtime)
    assert result["reset"] == 2


def test_documentation_edits_do_not_invalidate_execution(tmp_path):
    _baseline(tmp_path)
    (tmp_path / "README.md").write_text("Documentation update\n")
    result = _prepare(tmp_path)
    assert result["reset"] == 0 and result["kept"] == 2


def test_unrecorded_verdict_edits_cannot_gain_admissibility(tmp_path):
    cache = _baseline(tmp_path)
    _fill(cache, first=0)
    result = _prepare(tmp_path)
    assert result["reset"] == 1 and result["kept"] == 1


def test_an_unfinished_attempt_is_not_assumed_to_have_stopped(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    original = (cache / (SOURCES[0] + ".meta")).read_bytes()
    with pytest.raises(ValueError, match="pending"):
        _prepare(tmp_path)
    assert (cache / (SOURCES[0] + ".meta")).read_bytes() == original


def test_inputs_changed_during_execution_cannot_receive_a_current_binding(tmp_path):
    _repository(tmp_path)
    _prepare(tmp_path)
    (tmp_path / "tests/test_a.py").write_text("changed during attempt\n")
    with pytest.raises(ValueError, match="changed"):
        _record(tmp_path)


def test_recording_requires_a_preexisting_attempt(tmp_path):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="pending"):
        _record(tmp_path)


def test_a_partial_campaign_keeps_only_source_bound_settled_results(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache, first=1, second=None)
    record = _record(tmp_path, exit_code=2)
    assert record["native_exit_code"] == 2 and record["settled"] == 1
    result = _prepare(tmp_path)
    assert result["kept"] == 1 and result["reset"] == 0


def test_a_zero_exit_does_not_rebind_stale_generated_source(tmp_path):
    cache = _repository(tmp_path)
    (tmp_path / SOURCES[0]).write_text("def compute(value):\n    return value + 2\n")
    _prepare(tmp_path)
    _fill(cache)
    with pytest.raises(ValueError, match="source"):
        _record(tmp_path)


@pytest.mark.parametrize("change", ["tests", "source"])
def test_changed_inputs_after_partial_statistics_cannot_keep_unattributed_kills(tmp_path, change):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache)
    # An interrupted native attempt may save only part of its test/caller maps.
    (cache / "mutmut-stats.json").write_text(
        json.dumps(
            {
                "tests_by_mangled_function_name": {"pkg.b.x_run": ["tests/test_b.py::test_b"]},
                "function_dependencies": {"pkg.b.x_run": []},
            }
        )
    )
    _record(tmp_path, exit_code=2)
    path = tmp_path / ("tests/test_b.py" if change == "tests" else SOURCES[0])
    path.write_text(path.read_text().replace("assert True", "assert False").replace("+ 1", "+ 2"))
    result = _prepare(tmp_path)
    assert result["reset"] == 2 and result["kept"] == 0


def test_boolean_pending_version_cannot_authorize_recording(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    path = cache / mc.PENDING_EXECUTION
    pending = json.loads(path.read_text())
    pending["version"] = True
    path.write_text(json.dumps(pending))
    with pytest.raises(ValueError, match="inputs"):
        _record(tmp_path)


def test_duplicate_mutated_sources_are_rejected(tmp_path):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="mutated sources"):
        mc.capture_context(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=[SOURCES[0]] * 2)


@pytest.mark.parametrize("runtime", [{}, {"packages": {"mutmut": "3.9.0"}}])
def test_uninspected_native_versions_cannot_bind_execution(tmp_path, runtime):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="3.8.0"):
        mc.capture_context(tmp_path, SOURCES, runtime=runtime)


@pytest.mark.parametrize("sources", [[], [SOURCES[0]] * 2, ["missing.py"], ["pyproject.toml"]])
def test_context_requires_an_explicit_existing_python_inventory(tmp_path, sources):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="sources"):
        mc.capture_context(tmp_path, sources, runtime=RUNTIME)


@pytest.mark.parametrize("scope", [[], ["unknown.py"]])
def test_mutated_scope_cannot_escape_the_captured_inventory(tmp_path, scope):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="mutated sources"):
        mc.capture_context(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)


def test_execution_binding_rejects_an_external_cache_alias(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "mutants").symlink_to(outside, target_is_directory=True)
    for name in SOURCES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def f():\n    return 1\n")
    with pytest.raises(ValueError, match="owning root"):
        _prepare(root)
    assert not list(outside.iterdir())


def test_absent_native_metadata_is_not_invented_as_a_settled_result(tmp_path):
    cache = _repository(tmp_path)
    (cache / (SOURCES[0] + ".meta")).unlink()
    result = _prepare(tmp_path)
    assert result["kept"] == 0 and result["reset"] == 1
    proof = _record(tmp_path)
    assert proof["settled"] == 0
    assert SOURCES[0] + ".meta" not in proof["metadata_sha256"]


@pytest.mark.parametrize("change", ["shape", "verdict"])
def test_malformed_native_metadata_is_rejected_before_cache_mutation(tmp_path, change):
    cache = _repository(tmp_path)
    path = cache / (SOURCES[0] + ".meta")
    data = json.loads(path.read_text())
    if change == "shape":
        data.pop("hash_by_function_name")
    else:
        data["exit_code_by_key"]["pkg.a.x_compute__mutmut_1"] = True
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="native execution"):
        _prepare(tmp_path)
    assert path.read_bytes() == before
    assert not (cache / mc.PENDING_EXECUTION).exists()


def test_malformed_native_statistics_cannot_be_bound(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    (cache / "mutmut-stats.json").write_text(json.dumps({"function_dependencies": {"fn": 2}}))
    with pytest.raises(ValueError, match="dependency or test map"):
        _record(tmp_path)
    assert not (cache / mc.EXECUTION_RECORD).exists()
    assert (cache / mc.PENDING_EXECUTION).exists()


def test_damaged_execution_proof_cannot_admit_cached_verdicts(tmp_path):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    proof["native_exit_code"] = 2
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="execution proof"):
        _prepare(tmp_path)


@pytest.mark.parametrize("support", [True, False])
def test_support_changes_or_missing_dependency_graph_reopen_all_verdicts(tmp_path, support):
    cache = _repository(tmp_path)
    scope = [SOURCES[1]] if support else SOURCES
    (cache / "mutmut-stats.json").unlink()
    mc.prepare_execution(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)
    _fill(cache)
    mc.record_execution(
        tmp_path, SOURCES, runtime=RUNTIME, native_exit_code=0, mutated_sources=scope
    )
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = mc.prepare_execution(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)
    assert result["reset"] == len(scope) and result["kept"] == 0


def test_cyclic_dependency_graph_terminates_and_reopens_each_caller(tmp_path):
    cache = _repository(tmp_path)
    path = cache / "mutmut-stats.json"
    data = json.loads(path.read_text())
    data["function_dependencies"]["pkg.b.x_run"] = ["pkg.a.x_compute"]
    path.write_text(json.dumps(data))
    _prepare(tmp_path)
    _fill(cache)
    _record(tmp_path)
    source = tmp_path / SOURCES[0]
    source.write_text(source.read_text().replace("+ 1", "+ 2"))
    result = _prepare(tmp_path)
    assert result["reset"] == 2


def test_boolean_exit_code_cannot_be_recorded_as_success(tmp_path):
    _repository(tmp_path)
    _prepare(tmp_path)
    with pytest.raises(ValueError, match="integer"):
        _record(tmp_path, exit_code=False)


def test_compliance_policy_changes_do_not_repeat_unchanged_execution(tmp_path):
    _baseline(tmp_path)
    folder = tmp_path / "verification"
    folder.mkdir()
    (folder / "mutation_risk_policy.json").write_text('{"thresholds": {"L4": 98}}\n')
    (folder / "release_policy.json").write_text('{"version": 2}\n')
    result = _prepare(tmp_path)
    assert result["kept"] == 2 and result["reset"] == 0


def test_internally_checksummed_but_malformed_proof_fails_before_cache_writes(tmp_path):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    del proof["context"]["sources"][SOURCES[0]]["functions"]
    proof["sha256"] = mc._digest({key: value for key, value in proof.items() if key != "sha256"})
    path.write_text(json.dumps(proof))
    before = (cache / (SOURCES[0] + ".meta")).read_bytes()
    with pytest.raises(ValueError, match="execution proof"):
        _prepare(tmp_path)
    assert (cache / (SOURCES[0] + ".meta")).read_bytes() == before


@pytest.mark.parametrize(
    "case",
    [
        "context-extra",
        "runtime",
        "empty-sources",
        "sources-list",
        "empty-scope",
        "foreign-scope",
        "scope-object",
        "boolean-exit",
        "negative-settled",
        "boolean-settled",
        "source-fields",
        "source-hash-type",
        "function-map",
        "test-map",
        "test-hash",
        "missing-statistics",
        "statistics-map",
        "statistics-values",
        "statistics-value-type",
    ],
)
def test_malformed_proof_fields_fail_closed_even_with_a_matching_checksum(tmp_path, case):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    context = proof["context"]
    if case == "context-extra":
        context["extra"] = None
    elif case == "runtime":
        context["runtime"] = None
    elif case == "empty-sources":
        context["sources"] = {}
    elif case == "sources-list":
        context["sources"] = []
    elif case == "empty-scope":
        context["mutation_scope"] = []
    elif case == "foreign-scope":
        context["mutation_scope"] = ["missing.py"]
    elif case == "scope-object":
        context["mutation_scope"] = None
    elif case == "boolean-exit":
        proof["native_exit_code"] = True
    elif case == "negative-settled":
        proof["settled"] = -1
    elif case == "boolean-settled":
        proof["settled"] = True
    elif case == "source-fields":
        del context["sources"][SOURCES[0]]["functions"]
    elif case == "source-hash-type":
        context["sources"][SOURCES[0]]["sha256"] = None
    elif case == "function-map":
        context["sources"][SOURCES[0]]["functions"] = []
    elif case == "test-map":
        context["tests"] = []
    elif case == "test-hash":
        context["tests"]["tests/test_a.py"] = None
    elif case == "missing-statistics":
        del proof["statistics"]
    elif case == "statistics-map":
        proof["statistics"]["function_dependencies"] = []
    elif case == "statistics-values":
        proof["statistics"]["function_dependencies"] = {"pkg.a.x_compute": None}
    else:
        proof["statistics"]["function_dependencies"] = {"pkg.a.x_compute": [2]}
    proof["sha256"] = mc._digest({key: value for key, value in proof.items() if key != "sha256"})
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="execution proof"):
        _prepare(tmp_path)
    assert not (cache / mc.PENDING_EXECUTION).exists()


@pytest.mark.parametrize("artifact", [SOURCES[0], SOURCES[0] + ".spans"])
def test_changed_native_generation_artifacts_cannot_keep_bound_verdicts(tmp_path, artifact):
    cache = _baseline(tmp_path)
    (cache / artifact).write_text("changed native generation artifact\n")
    result = _prepare(tmp_path)
    assert result["kept"] == 0 and result["reset"] == 2


def test_settled_verdicts_require_their_native_generation_artifacts(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache)
    (cache / SOURCES[0]).unlink()
    with pytest.raises(ValueError, match="generation artifacts"):
        _record(tmp_path)


@pytest.mark.parametrize("value", [[], {"src/pkg/a.py": 3}])
def test_malformed_native_artifact_binding_cannot_admit_cache(tmp_path, value):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    proof["native_artifacts_sha256"] = value
    proof["sha256"] = mc._digest({key: item for key, item in proof.items() if key != "sha256"})
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="execution proof native artifacts"):
        _prepare(tmp_path)


def test_previous_prototype_proofs_cannot_be_restamped_under_the_new_binding_format(tmp_path):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    proof["version"] = 1
    proof["sha256"] = mc._digest({key: item for key, item in proof.items() if key != "sha256"})
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="execution proof"):
        _prepare(tmp_path)
