"""Exact reasons, counts, refusals and files of the mutation cache guard and its binding."""

import copy
import hashlib
import json

import pytest

from tests.verifier.test_mutation_execution import (
    RUNTIME,
    SOURCES,
    _baseline,
    _fill,
    _prepare,
    _record,
    _repository,
)
from verification import mutation_cache as mc


def _refused(call, message):
    with pytest.raises(ValueError) as refused:
        call()
    assert str(refused.value) == message


def test_a_function_is_the_key_without_its_mutant_number():
    assert mc.function_of("pkg.a.x_f__mutmut_12") == "pkg.a.x_f"
    assert mc.function_of("a__mutmut_1__mutmut_2") == "a__mutmut_1"
    assert mc.function_of("plain") == "plain"


def _stats(tests):
    return {"pkg.a.x_f": tests}


def test_nothing_is_reset_without_a_baseline_or_without_a_change():
    verdicts = {"pkg.a.x_f__mutmut_1": 1}
    assert mc.keys_to_reset(None, {"t.py": "1"}, _stats(["t.py::a"]), verdicts) == []
    assert mc.keys_to_reset({"t.py": "1"}, {"t.py": "1"}, _stats(["t.py::a"]), verdicts) == []


def test_a_modified_test_reopens_the_kills_it_covers_and_every_non_final_verdict():
    verdicts = {
        "pkg.a.x_f__mutmut_1": 1,
        "pkg.a.x_g__mutmut_1": 1,
        "pkg.a.x_f__mutmut_2": 0,
        "pkg.a.x_f__mutmut_3": 37,
    }
    tests = {"pkg.a.x_f": ["t.py::a"], "pkg.a.x_g": ["u.py::b"]}
    old, new = {"t.py": "1", "u.py": "1"}, {"t.py": "2", "u.py": "1"}
    reset = mc.keys_to_reset(old, new, tests, verdicts)
    assert sorted(reset) == ["pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_2"]


def test_a_changed_or_new_support_file_reopens_every_verdict_except_the_type_checked_ones():
    verdicts = {"a__mutmut_1": 1, "b__mutmut_1": 0, "c__mutmut_1": 37, "d__mutmut_1": None}
    tests = {"a": ["t.py::x"]}
    support_changed = mc.keys_to_reset(
        {"conftest.py": "1", "t.py": "1"}, {"conftest.py": "2", "t.py": "1"}, tests, verdicts
    )
    assert sorted(support_changed) == ["a__mutmut_1", "b__mutmut_1", "d__mutmut_1"]
    support_added = mc.keys_to_reset(
        {"t.py": "1"}, {"t.py": "1", "helper.py": "1"}, tests, verdicts
    )
    assert sorted(support_added) == ["a__mutmut_1", "b__mutmut_1", "d__mutmut_1"]
    test_added = mc.keys_to_reset({"t.py": "1"}, {"t.py": "1", "test_new.py": "1"}, tests, verdicts)
    assert sorted(test_added) == ["b__mutmut_1", "d__mutmut_1"]
    removed = mc.keys_to_reset({"t.py": "1", "u.py": "1"}, {"t.py": "1"}, tests, verdicts)
    assert sorted(removed) == ["a__mutmut_1", "b__mutmut_1", "d__mutmut_1"] or sorted(removed) == [
        "b__mutmut_1",
        "d__mutmut_1",
    ]


def test_a_test_prefix_only_matches_the_same_file_not_a_longer_name():
    verdicts = {"a__mutmut_1": 1}
    tests = {"a": ["test_ab.py::x"]}
    old, new = {"test_ab.py": "1", "test_a.py": "1"}, {"test_ab.py": "1", "test_a.py": "2"}
    assert mc.keys_to_reset(old, new, {**tests, "z": ["test_a.py::y"]}, verdicts) == []


def test_the_tests_are_hashed_with_the_root_conftest_and_both_test_trees(tmp_path):
    (tmp_path / "conftest.py").write_text("c")
    (tmp_path / "tests" / "sub").mkdir(parents=True)
    (tmp_path / "tests" / "sub" / "test_a.py").write_text("a")
    (tmp_path / "research" / "tests").mkdir(parents=True)
    (tmp_path / "research" / "tests" / "test_r.py").write_text("r")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "test_x.py").write_text("x")
    (tmp_path / "tests" / "data.txt").write_text("not python")
    hashed = mc.hash_tests(tmp_path)
    assert hashed == {
        "conftest.py": hashlib.sha256(b"c").hexdigest(),
        "research/tests/test_r.py": hashlib.sha256(b"r").hexdigest(),
        "tests/sub/test_a.py": hashlib.sha256(b"a").hexdigest(),
    }
    assert list(hashed) == sorted(hashed)


def test_the_test_record_is_written_sorted_and_indented_inside_the_cache(tmp_path):
    (tmp_path / "mutants").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("a")
    target = mc.record(tmp_path)
    assert target == tmp_path / "mutants" / "test-hashes.json"
    assert (
        target.read_text() == json.dumps(mc.hash_tests(tmp_path), indent=2, sort_keys=True) + "\n"
    )


def test_a_cache_outside_its_root_or_with_aliased_metadata_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (root / "mutants").symlink_to(tmp_path / "elsewhere")
    _refused(lambda: mc.prepare(root), "mutation cache must remain inside its owning root")
    (root / "mutants").unlink()
    (root / "mutants").mkdir()
    outside = tmp_path / "outside.meta"
    outside.write_text(json.dumps({"exit_code_by_key": {}}))
    (root / "mutants" / "x.meta").symlink_to(outside)
    _refused(
        lambda: mc.prepare(root), "mutation cache metadata must not alias files outside the cache"
    )


def test_without_a_recorded_baseline_every_settled_verdict_is_kept_and_nothing_is_reset(tmp_path):
    cache = _repository(tmp_path)
    report = mc.prepare(tmp_path)
    assert report == {
        "kept": 2,
        "reset": 0,
        "modified_tests": [],
        "removed_tests": [],
        "added_tests": [],
    }
    (cache / "test-hashes.json").write_text("{}")
    (cache / "mutmut-stats.json").unlink()
    assert mc.prepare(tmp_path)["reset"] == 0
    assert mc.prepare(tmp_path)["kept"] == 2


def test_modified_removed_and_added_tests_are_listed_and_the_cleared_verdicts_are_counted(tmp_path):
    cache = _repository(tmp_path)
    mc.record(tmp_path)
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    (tmp_path / "tests" / "test_b.py").unlink()
    (tmp_path / "tests" / "test_c.py").write_text("new")
    report = mc.prepare(tmp_path)
    assert report["modified_tests"] == ["tests/test_a.py"]
    assert report["removed_tests"] == ["tests/test_b.py"]
    assert report["added_tests"] == ["tests/test_c.py"]
    assert report["reset"] == 2 and report["kept"] == 0
    for name in SOURCES:
        data = json.loads((cache / (name + ".meta")).read_text())
        assert set(data["exit_code_by_key"].values()) == {None}
    assert (cache / (SOURCES[0] + ".meta")).read_text().endswith("}\n")


def test_unchanged_tests_leave_every_verdict_alone(tmp_path):
    cache = _repository(tmp_path)
    mc.record(tmp_path)
    before = {name: (cache / (name + ".meta")).read_bytes() for name in SOURCES}
    report = mc.prepare(tmp_path)
    assert report == {
        "kept": 2,
        "reset": 0,
        "modified_tests": [],
        "removed_tests": [],
        "added_tests": [],
    }
    assert {name: (cache / (name + ".meta")).read_bytes() for name in SOURCES} == before


def test_the_command_prints_the_counts_and_each_non_empty_test_list(tmp_path, monkeypatch, capsys):
    _repository(tmp_path)
    mc.record(tmp_path)
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    (tmp_path / "tests" / "test_new.py").write_text("n")
    monkeypatch.chdir(tmp_path)
    assert mc.main(["prepare"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "mutation cache: kept 1, reset 1",
        "  modified tests: tests/test_a.py",
        "  added tests: tests/test_new.py",
    ]
    assert mc.main(["record"]) == 0 and capsys.readouterr().out == ""
    with pytest.raises(SystemExit) as stop:
        mc.main(["other"])
    assert stop.value.code == 2


def test_the_digest_is_canonical_and_refuses_non_finite_numbers():
    assert mc._digest({"b": 1, "a": [1]}) == hashlib.sha256(b'{"a":[1],"b":1}').hexdigest()
    with pytest.raises(ValueError):
        mc._digest({"x": float("nan")})


def test_a_json_file_is_written_atomically_sorted_and_without_non_finite_numbers(tmp_path):
    target = tmp_path / "x.json"
    mc._write_json(target, {"b": 1, "a": 2})
    assert target.read_text() == json.dumps({"b": 1, "a": 2}, indent=2, sort_keys=True) + "\n"
    with pytest.raises(ValueError):
        mc._write_json(tmp_path / "y.json", {"x": float("inf")})
    assert not (tmp_path / "y.json").exists()


def test_the_globals_hash_ignores_function_bodies_and_notices_everything_else():
    base = mc._globals_hash("X = 1\n\ndef f():\n    return 1\n")
    assert mc._globals_hash("X = 1\n\ndef f():\n    return 2\n") == base
    assert mc._globals_hash("X = 1\n\nasync def f():\n    return 2\n") != base
    assert mc._globals_hash("X = 2\n\ndef f():\n    return 1\n") != base
    assert mc._globals_hash("X = 1\n\ndef g():\n    return 1\n") != base
    assert mc._globals_hash("async def f():\n    pass\n") == mc._globals_hash(
        "async def f():\n    return 9\n"
    )


def _context(root, **over):
    arguments = {"runtime": copy.deepcopy(RUNTIME)}
    arguments.update(over)
    sources = arguments.pop("sources", SOURCES)
    return mc.capture_context(root, sources, **arguments)


def test_the_context_binds_sources_tests_dependencies_scope_and_runtime(tmp_path):
    _repository(tmp_path)
    (tmp_path / "environment.yml").write_text("name: e\n")
    (tmp_path / "verification" / "environment").mkdir(parents=True)
    (tmp_path / "verification" / "environment" / "lock.txt").write_text("lock")
    context = _context(tmp_path)
    assert set(context) == {"sources", "mutation_scope", "tests", "dependencies", "runtime"}
    assert list(context["sources"]) == SOURCES and context["mutation_scope"] == SOURCES
    first = context["sources"][SOURCES[0]]
    assert first["sha256"] == hashlib.sha256((tmp_path / SOURCES[0]).read_bytes()).hexdigest()
    assert first["globals_sha256"] == mc._globals_hash((tmp_path / SOURCES[0]).read_text())
    assert list(first["functions"]) == ["x_compute"]
    assert list(context["dependencies"]) == [
        "environment.yml", "pyproject.toml", "verification/environment/lock.txt",
    ]  # fmt: skip
    assert context["tests"] == mc.hash_tests(tmp_path) and context["runtime"] == RUNTIME
    assert context["runtime"] is not RUNTIME
    narrowed = _context(tmp_path, mutated_sources=[SOURCES[1]])
    assert narrowed["mutation_scope"] == [SOURCES[1]] and list(narrowed["sources"]) == SOURCES


@pytest.mark.parametrize(
    "runtime",
    [None, {"packages": {}}, {"packages": {"mutmut": "3.9.0"}}, {"packages": []}, {}],
)
def test_the_inspected_mutmut_version_is_required(tmp_path, runtime):
    _repository(tmp_path)
    _refused(
        lambda: mc.capture_context(tmp_path, SOURCES, runtime=runtime),
        "execution binding requires the inspected mutmut 3.8.0 format",
    )


@pytest.mark.parametrize("sources", [[], [SOURCES[0], SOURCES[0]], "src/pkg/a.py", None])
def test_sources_must_be_an_explicit_unique_nonempty_list(tmp_path, sources):
    _repository(tmp_path)
    _refused(
        lambda: mc.capture_context(tmp_path, sources, runtime=RUNTIME),
        "execution sources must be explicit, unique and nonempty",
    )


@pytest.mark.parametrize("scope", [[], [SOURCES[0], SOURCES[0]], ["src/pkg/c.py"], "x"])
def test_the_mutated_sources_must_be_a_unique_nonempty_part_of_the_inventory(tmp_path, scope):
    _repository(tmp_path)
    _refused(
        lambda: mc.capture_context(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope),
        "mutated sources must belong to the captured source inventory",
    )


def test_a_source_must_be_an_existing_python_file(tmp_path):
    _repository(tmp_path)
    (tmp_path / "src" / "pkg" / "c.txt").write_text("x")
    for name in ("src/pkg/missing.py", "src/pkg/c.txt"):
        _refused(
            lambda n=name: mc.capture_context(tmp_path, [n], runtime=RUNTIME),
            "execution sources must be existing Python files",
        )


def test_the_native_dependency_and_test_maps_are_read_and_validated(tmp_path):
    cache = _repository(tmp_path)
    assert mc._statistics(tmp_path) == {
        "tests_by_mangled_function_name": {
            "pkg.a.x_compute": ["tests/test_a.py::test_a"],
            "pkg.b.x_run": ["tests/test_b.py::test_b"],
        },
        "function_dependencies": {"pkg.a.x_compute": ["pkg.b.x_run"]},
    }
    (cache / "mutmut-stats.json").write_text(
        json.dumps({"tests_by_mangled_function_name": {"a": "x"}})
    )
    _refused(lambda: mc._statistics(tmp_path), "invalid native dependency or test map")
    (cache / "mutmut-stats.json").write_text(json.dumps({"function_dependencies": {"a": [1]}}))
    _refused(lambda: mc._statistics(tmp_path), "invalid native dependency or test map")
    (cache / "mutmut-stats.json").write_text(json.dumps({"function_dependencies": []}))
    _refused(lambda: mc._statistics(tmp_path), "invalid native dependency or test map")
    (cache / "mutmut-stats.json").unlink()
    assert mc._statistics(tmp_path) == {
        "tests_by_mangled_function_name": {},
        "function_dependencies": {},
    }


def test_native_metadata_must_have_the_inspected_shape_and_integer_verdicts(tmp_path):
    cache = _repository(tmp_path)
    meta = cache / (SOURCES[0] + ".meta")
    good = json.loads(meta.read_text())
    meta.write_text(json.dumps({**good, "extra": {}}))
    _refused(
        lambda: mc._execution_documents(tmp_path, SOURCES), "invalid native execution metadata"
    )
    meta.write_text(json.dumps({**good, "durations_by_key": []}))
    _refused(
        lambda: mc._execution_documents(tmp_path, SOURCES), "invalid native execution metadata"
    )
    meta.write_text(json.dumps({**good, "exit_code_by_key": {"pkg.a.x_compute__mutmut_1": 1.0}}))
    _refused(lambda: mc._execution_documents(tmp_path, SOURCES), "invalid native execution verdict")
    meta.write_text(json.dumps({**good, "exit_code_by_key": {"pkg.a.x_compute__mutmut_1": True}}))
    _refused(lambda: mc._execution_documents(tmp_path, SOURCES), "invalid native execution verdict")
    meta.write_text(json.dumps({**good, "exit_code_by_key": {"pkg.a.x_compute__mutmut_1": None}}))
    assert list(mc._execution_documents(tmp_path, SOURCES)) == [
        meta,
        cache / (SOURCES[1] + ".meta"),
    ]
    meta.unlink()
    assert list(mc._execution_documents(tmp_path, SOURCES)) == [cache / (SOURCES[1] + ".meta")]


def test_the_first_binding_resets_every_verdict_for_the_stated_reason(tmp_path):
    _repository(tmp_path)
    result = _prepare(tmp_path)
    assert result["reasons"] == ["no previous execution proof; bootstrap reconciliation"]
    assert result["kept"] == 0 and result["reset"] == 2
    assert len(result["context_sha256"]) == 64
    pending = json.loads((tmp_path / "mutants" / mc.PENDING_EXECUTION).read_text())
    assert pending["version"] == mc.EXECUTION_VERSION and result["context_sha256"] == mc._digest(
        pending["context"]
    )


def test_an_unchanged_bound_cache_gives_no_reason_and_keeps_everything(tmp_path):
    _baseline(tmp_path)
    result = _prepare(tmp_path)
    assert result["reasons"] == [] and result["kept"] == 2 and result["reset"] == 0


def test_a_pending_attempt_blocks_a_new_preparation_with_its_own_reason(tmp_path):
    _repository(tmp_path)
    _prepare(tmp_path)
    _refused(
        lambda: _prepare(tmp_path),
        "pending execution requires checking its process before recovery",
    )


@pytest.mark.parametrize("change", ["runtime", "dependency", "global"])
def test_a_changed_runtime_dependency_or_source_global_reports_the_global_reason(tmp_path, change):
    _baseline(tmp_path)
    runtime = copy.deepcopy(RUNTIME)
    if change == "runtime":
        runtime["python"] = "3.11.18"
    elif change == "dependency":
        (tmp_path / "pyproject.toml").write_text("[x]\n")
    else:
        path = tmp_path / SOURCES[0]
        path.write_text("SCALE = 2\n" + path.read_text())
    result = _prepare(tmp_path, runtime=runtime)
    assert "runtime, dependency, source-global or inventory inputs changed" in result["reasons"]
    assert result["reset"] == 2 and result["kept"] == 0


def test_a_changed_function_resets_it_and_its_callers_and_says_so(tmp_path):
    _baseline(tmp_path)
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = _prepare(tmp_path)
    assert result["reasons"] == ["changed source functions and transitive callers"]
    assert result["reset"] == 2


def test_a_change_to_the_caller_alone_leaves_the_callee_verdict(tmp_path):
    _baseline(tmp_path)
    path = tmp_path / SOURCES[1]
    path.write_text(path.read_text().replace("compute(value)", "compute(value) + 0"))
    result = _prepare(tmp_path)
    assert result["reasons"] == ["changed source functions and transitive callers"]
    assert result["reset"] == 1 and result["kept"] == 1


def test_an_unavailable_dependency_graph_after_a_partial_attempt_resets_everything(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache)
    _record(tmp_path, exit_code=3)
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = _prepare(tmp_path)
    assert result["reasons"] == ["changed uninstrumented support or unavailable dependency graph"]
    assert result["reset"] == 2


def test_a_change_in_a_support_source_outside_the_mutated_scope_resets_everything(tmp_path):
    cache = _repository(tmp_path)
    extra = tmp_path / "src" / "pkg" / "c.py"
    extra.write_text("def helper():\n    return 1\n")
    scope = SOURCES
    mc_sources = [*SOURCES, "src/pkg/c.py"]
    mc.prepare_execution(tmp_path, mc_sources, runtime=RUNTIME, mutated_sources=scope)
    _fill(cache)
    mc.record_execution(
        tmp_path, mc_sources, runtime=RUNTIME, native_exit_code=0, mutated_sources=scope
    )
    extra.write_text("def helper():\n    return 2\n")
    result = mc.prepare_execution(tmp_path, mc_sources, runtime=RUNTIME, mutated_sources=scope)
    assert result["reasons"] == ["changed uninstrumented support or unavailable dependency graph"]
    assert result["reset"] == 2


def test_a_test_change_after_an_incomplete_attempt_resets_every_verdict(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache)
    _record(tmp_path, exit_code=2)
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    result = _prepare(tmp_path)
    assert "test inputs changed after an incomplete native attempt" in result["reasons"]
    assert result["reset"] == 2


def test_native_artifacts_changed_outside_the_recorded_attempt_reset_everything(tmp_path):
    cache = _baseline(tmp_path)
    (cache / SOURCES[0]).write_text("tampered\n")
    result = _prepare(tmp_path)
    assert result["reasons"] == ["native generation artifacts changed outside the recorded attempt"]
    assert result["reset"] == 2


def test_an_unbound_edit_of_one_metadata_file_resets_only_its_verdicts_and_names_it(tmp_path):
    cache = _baseline(tmp_path)
    _fill(cache, first=0)
    result = _prepare(tmp_path)
    assert result["reasons"] == [f"unbound metadata change: {SOURCES[0]}.meta"]
    assert result["reset"] == 1 and result["kept"] == 1


def test_recording_requires_a_pending_attempt_matching_the_inputs_and_an_integer_exit(tmp_path):
    cache = _repository(tmp_path)
    _refused(lambda: _record(tmp_path), "no pending execution to bind")
    _prepare(tmp_path)
    _fill(cache)
    for bad in (True, 1.0, "0", None):
        _refused(
            lambda b=bad: _record(tmp_path, exit_code=b), "native exit code must be an integer"
        )
    pending = cache / mc.PENDING_EXECUTION
    document = json.loads(pending.read_text())
    pending.write_text(json.dumps({**document, "version": 1}))
    _refused(
        lambda: _record(tmp_path), "execution inputs changed during the attempt; do not promote"
    )
    pending.write_text(json.dumps({**document, "version": True}))
    _refused(
        lambda: _record(tmp_path), "execution inputs changed during the attempt; do not promote"
    )
    pending.write_text(json.dumps(document))
    assert _record(tmp_path)["version"] == mc.EXECUTION_VERSION


def test_settled_verdicts_need_their_generated_sources_and_must_match_the_current_functions(
    tmp_path,
):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache)
    (cache / SOURCES[0]).unlink()
    _refused(lambda: _record(tmp_path), "settled verdicts lack native generation artifacts")
    (cache / SOURCES[0]).write_text("x")
    (cache / (SOURCES[0] + ".spans")).unlink()
    _refused(lambda: _record(tmp_path), "settled verdicts lack native generation artifacts")
    (cache / (SOURCES[0] + ".spans")).write_text("{}")
    meta = cache / (SOURCES[0] + ".meta")
    data = json.loads(meta.read_text())
    data["hash_by_function_name"] = {"x_compute": "stale"}
    meta.write_text(json.dumps(data))
    _refused(lambda: _record(tmp_path), "settled native verdicts do not match current source")
    data["hash_by_function_name"] = {}
    meta.write_text(json.dumps(data))
    _refused(lambda: _record(tmp_path), "settled native verdicts do not match current source")


def test_the_execution_proof_lists_what_it_binds_and_is_sealed_by_its_own_digest(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache, first=1, second=None)
    proof = _record(tmp_path, exit_code=2)
    assert set(proof) == {
        "version", "context", "statistics", "metadata_sha256", "native_artifacts_sha256",
        "native_exit_code", "settled", "captured_at", "sha256",
    }  # fmt: skip
    assert proof["native_exit_code"] == 2 and proof["settled"] == 1
    assert proof["sha256"] == mc._digest({k: v for k, v in proof.items() if k != "sha256"})
    assert list(proof["metadata_sha256"]) == [f"{name}.meta" for name in SOURCES]
    assert set(proof["native_artifacts_sha256"]) == {*SOURCES, *(f"{n}.spans" for n in SOURCES)}
    assert proof["statistics"] == mc._statistics(tmp_path) and proof["captured_at"].endswith(
        "+00:00"
    )
    assert json.loads((cache / mc.EXECUTION_RECORD).read_text()) == proof
    assert (cache / mc.HASHES).exists() and not (cache / mc.PENDING_EXECUTION).exists()


def test_a_native_artifact_that_does_not_exist_is_recorded_as_absent(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    (cache / (SOURCES[1] + ".spans")).unlink()
    proof = _record(tmp_path, exit_code=1)
    assert proof["native_artifacts_sha256"][SOURCES[1] + ".spans"] is None
    assert proof["native_artifacts_sha256"][SOURCES[0]] is not None


def test_a_recorded_binding_validates_and_each_drift_is_refused_with_its_own_reason(tmp_path):
    cache = _baseline(tmp_path)
    assert mc.validate_execution(tmp_path, SOURCES)["settled"] == 2
    other = copy.deepcopy(RUNTIME)
    other["python"] = "9.9"
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES, runtime=other),
        "execution inputs differ from the recorded binding",
    )
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "execution inputs differ from the recorded binding",
    )
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    _fill(cache, first=0)
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "native verdict metadata differs from the recorded binding",
    )
    _fill(cache, first=1)
    (cache / SOURCES[0]).write_text("tampered")
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "native generation artifacts differ from the recorded binding",
    )
    (cache / SOURCES[0]).write_text((tmp_path / SOURCES[0]).read_text())
    stats = json.loads((cache / "mutmut-stats.json").read_text())
    stats["function_dependencies"] = {}
    (cache / "mutmut-stats.json").write_text(json.dumps(stats))
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "native dependency/test maps differ from the recorded binding",
    )


def test_a_pending_or_missing_proof_cannot_validate(tmp_path):
    cache = _repository(tmp_path)
    _refused(lambda: mc.validate_execution(tmp_path, SOURCES), "execution proof is missing")
    _prepare(tmp_path)
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "pending native execution cannot validate a settled binding",
    )
    assert (cache / mc.PENDING_EXECUTION).exists()


def _rewrite_proof(cache, edit):
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    edit(proof)
    payload = {k: v for k, v in proof.items() if k != "sha256"}
    proof["sha256"] = mc._digest(payload)
    path.write_text(json.dumps(proof))


PROOF_FAULTS = [
    (lambda p: p.update(version=1), "invalid execution proof"),
    (lambda p: p.update(version=True), "invalid execution proof"),
    (lambda p: p.update(context="x"), "invalid execution proof"),
    (lambda p: p["context"].update(extra=1), "invalid execution proof shape"),
    (lambda p: p["context"].update(runtime="x"), "invalid execution proof shape"),
    (lambda p: p["context"].update(sources={}), "invalid execution proof shape"),
    (lambda p: p["context"].update(mutation_scope=[]), "invalid execution proof shape"),
    (
        lambda p: p["context"].update(mutation_scope=["src/pkg/zz.py"]),
        "invalid execution proof shape",
    ),
    (lambda p: p.update(native_exit_code=True), "invalid execution proof shape"),
    (lambda p: p.update(settled=-1), "invalid execution proof shape"),
    (lambda p: p.update(settled="1"), "invalid execution proof shape"),
    (lambda p: p.update(native_artifacts_sha256=[]), "invalid execution proof native artifacts"),
    (
        lambda p: p["native_artifacts_sha256"].update({"x": 5}),
        "invalid execution proof native artifacts",
    ),
    (
        lambda p: p["context"]["sources"][SOURCES[0]].update(extra="x"),
        "invalid execution proof source",
    ),
    (
        lambda p: p["context"]["sources"][SOURCES[0]].update(sha256=5),
        "invalid execution proof mapping",
    ),
    (lambda p: p["context"]["tests"].update({"t": 1}), "invalid execution proof mapping"),
    (lambda p: p["metadata_sha256"].update({"m": None}), "invalid execution proof mapping"),
    (
        lambda p: p["statistics"].update(function_dependencies={"a": "x"}),
        "invalid execution proof statistics",
    ),
    (lambda p: p["statistics"].pop("function_dependencies"), "invalid execution proof shape"),
]


@pytest.mark.parametrize(("edit", "message"), PROOF_FAULTS)
def test_each_malformed_part_of_a_proof_is_refused_with_its_own_reason(tmp_path, edit, message):
    cache = _baseline(tmp_path)
    _rewrite_proof(cache, edit)
    _refused(lambda: mc.validate_execution(tmp_path, SOURCES), message)


def test_a_proof_whose_digest_does_not_match_its_content_is_invalid(tmp_path):
    cache = _baseline(tmp_path)
    path = cache / mc.EXECUTION_RECORD
    proof = json.loads(path.read_text())
    proof["settled"] = 0
    path.write_text(json.dumps(proof))
    _refused(lambda: mc.validate_execution(tmp_path, SOURCES), "invalid execution proof")


def test_a_modified_test_file_is_matched_by_its_path_even_when_a_test_node_sits_in_a_class():
    verdicts = {"pkg.a.x_f__mutmut_1": 1, "pkg.a.x_g__mutmut_1": 1}
    tests = {"pkg.a.x_f": ["t.py::Suite::test_a"], "pkg.a.x_g": ["u.py::test_b"]}
    reset = mc.keys_to_reset(
        {"t.py": "1", "u.py": "1"}, {"t.py": "2", "u.py": "1"}, tests, verdicts
    )
    assert reset == ["pkg.a.x_f__mutmut_1"]


def test_the_test_record_is_sorted_whatever_the_order_the_tests_were_hashed_in(
    tmp_path, monkeypatch
):
    (tmp_path / "mutants").mkdir()
    monkeypatch.setattr(mc, "hash_tests", lambda root: {"b.py": "2", "a.py": "1"})
    text = mc.record(tmp_path).read_text()
    assert text == '{\n  "a.py": "1",\n  "b.py": "2"\n}\n'


def test_a_symlinked_metadata_file_is_refused_even_when_it_points_inside_the_cache(tmp_path):
    (tmp_path / "mutants").mkdir()
    real = tmp_path / "mutants" / "real.meta"
    real.write_text(json.dumps({"exit_code_by_key": {}}))
    (tmp_path / "mutants" / "alias.meta").symlink_to(real)
    _refused(
        lambda: mc.prepare(tmp_path),
        "mutation cache metadata must not alias files outside the cache",
    )


def test_a_cleared_metadata_file_is_rewritten_indented_by_two_and_an_untouched_one_is_not(tmp_path):
    cache = _repository(tmp_path)
    mc.record(tmp_path)
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    untouched = (cache / (SOURCES[1] + ".meta")).read_bytes()
    mc.prepare(tmp_path)
    data = json.loads((cache / (SOURCES[0] + ".meta")).read_text())
    assert (cache / (SOURCES[0] + ".meta")).read_text() == json.dumps(data, indent=2) + "\n"
    assert (cache / (SOURCES[1] + ".meta")).read_bytes() == untouched


def test_the_scope_file_is_one_of_the_bound_dependencies(tmp_path):
    _repository(tmp_path)
    (tmp_path / "verification").mkdir()
    (tmp_path / "verification" / "mutation_scope.json").write_text("{}")
    context = mc.capture_context(tmp_path, SOURCES, runtime=RUNTIME)
    assert "verification/mutation_scope.json" in context["dependencies"]


def test_a_cache_symlinked_inside_its_root_is_refused_when_reading_execution_documents(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "mutants").symlink_to(tmp_path / "elsewhere")
    _refused(
        lambda: mc._execution_documents(tmp_path, SOURCES),
        "mutation cache must remain inside its owning root",
    )
    (tmp_path / "mutants").unlink()
    outside = tmp_path.parent / (tmp_path.name + "_outside")
    outside.mkdir()
    (tmp_path / "mutants").symlink_to(outside)
    _refused(
        lambda: mc._execution_documents(tmp_path, SOURCES),
        "mutation cache must remain inside its owning root",
    )


def test_a_binding_with_no_settled_verdict_is_valid_and_records_zero(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    _fill(cache, first=None, second=None)
    assert _record(tmp_path)["settled"] == 0
    assert mc.validate_execution(tmp_path, SOURCES)["settled"] == 0


def test_a_verdict_not_yet_settled_does_not_hide_the_settled_ones_that_follow_it(tmp_path):
    cache = _repository(tmp_path)
    _prepare(tmp_path)
    meta = cache / (SOURCES[0] + ".meta")
    data = json.loads(meta.read_text())
    data["exit_code_by_key"] = {"pkg.a.x_compute__mutmut_1": None, "pkg.a.x_compute__mutmut_2": 1}
    meta.write_text(json.dumps(data))
    assert _record(tmp_path)["settled"] == 1


def test_a_changed_function_resets_the_callers_of_its_callers(tmp_path):
    cache = _repository(tmp_path)
    third = tmp_path / "src" / "pkg" / "c.py"
    third.write_text("from .b import run\ndef top(value):\n    return run(value)\n")
    sources = [*SOURCES, "src/pkg/c.py"]
    (cache / "src/pkg/c.py").write_text(third.read_text())
    (cache / "src/pkg/c.py.spans").write_text("{}\n")
    fingerprint = mc.mutation_catalog._function_hashes(third.read_text())["x_top"]
    (cache / "src/pkg/c.py.meta").write_text(
        json.dumps(
            {
                "exit_code_by_key": {"pkg.c.x_top__mutmut_1": 1},
                "hash_by_function_name": {"x_top": fingerprint},
                "durations_by_key": {},
                "estimated_durations_by_key": {},
                "type_check_error_by_key": {},
            }
        )
    )
    stats = json.loads((cache / "mutmut-stats.json").read_text())
    stats["function_dependencies"]["pkg.b.x_run"] = ["pkg.c.x_top"]
    (cache / "mutmut-stats.json").write_text(json.dumps(stats))
    mc.prepare_execution(tmp_path, sources, runtime=RUNTIME)
    _fill(cache)
    meta = cache / "src/pkg/c.py.meta"
    data = json.loads(meta.read_text())
    data["exit_code_by_key"] = {"pkg.c.x_top__mutmut_1": 1}
    meta.write_text(json.dumps(data))
    mc.record_execution(tmp_path, sources, runtime=RUNTIME, native_exit_code=0)
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = mc.prepare_execution(tmp_path, sources, runtime=RUNTIME)
    assert result["reset"] == 3 and result["kept"] == 0


def test_a_support_change_before_an_unchanged_scoped_source_still_counts_as_support(tmp_path):
    cache = _repository(tmp_path)
    scope = [SOURCES[1]]
    mc.prepare_execution(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)
    _fill(cache)
    mc.record_execution(
        tmp_path, SOURCES, runtime=RUNTIME, native_exit_code=0, mutated_sources=scope
    )
    path = tmp_path / SOURCES[0]
    path.write_text(path.read_text().replace("+ 1", "+ 2"))
    result = mc.prepare_execution(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)
    assert result["reasons"] == ["changed uninstrumented support or unavailable dependency graph"]


def test_an_untouched_metadata_file_is_left_byte_for_byte_when_nothing_is_reset(tmp_path):
    cache = _baseline(tmp_path)
    before = {n: (cache / (n + ".meta")).read_bytes() for n in SOURCES}
    assert _prepare(tmp_path)["reset"] == 0
    assert {n: (cache / (n + ".meta")).read_bytes() for n in SOURCES} == before


def test_a_binding_validates_against_the_same_mutated_part_it_was_recorded_for(tmp_path):
    cache = _repository(tmp_path)
    scope = [SOURCES[0]]
    mc.prepare_execution(tmp_path, SOURCES, runtime=RUNTIME, mutated_sources=scope)
    _fill(cache)
    mc.record_execution(
        tmp_path, SOURCES, runtime=RUNTIME, native_exit_code=0, mutated_sources=scope
    )
    assert mc.validate_execution(tmp_path, SOURCES, mutated_sources=scope)["settled"] == 1
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "execution inputs differ from the recorded binding",
    )


def test_a_proof_whose_settled_count_was_altered_is_refused_by_that_reason(tmp_path):
    cache = _baseline(tmp_path)
    _rewrite_proof(cache, lambda p: p.update(settled=5))
    _refused(
        lambda: mc.validate_execution(tmp_path, SOURCES),
        "settled verdict count differs from native metadata",
    )


def test_the_command_joins_several_test_names_with_a_comma_and_a_space(
    tmp_path, monkeypatch, capsys
):
    _repository(tmp_path)
    mc.record(tmp_path)
    (tmp_path / "tests" / "test_a.py").write_text("changed")
    (tmp_path / "tests" / "test_b.py").write_text("changed")
    monkeypatch.chdir(tmp_path)
    mc.main(["prepare"])
    assert "  modified tests: tests/test_a.py, tests/test_b.py" in capsys.readouterr().out


def test_the_command_help_carries_the_module_description(capsys):
    with pytest.raises(SystemExit):
        mc.main(["--help"])
    assert "Reuse cached mutation verdicts only for code and tests" in capsys.readouterr().out
