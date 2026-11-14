"""Each validation reason, status rule, builder argument and command of the evidence envelope."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from experiments import check_mutation, verify_real
from verification import evidence_schema as es

SOURCE = {"revision": "a" * 40, "worktree_dirty": False, "scientific_fingerprint": "b" * 64}
ENVIRONMENT = {
    "python": "3.11.0",
    "platform": "test",
    "packages": {"pandas": "3.0.6", "numpy": None},
}
EXECUTION = {"ci": False, "run_id": None, "runner_environment": None, "runner_name": None}
FULL = {"coverable": 2, "covered": 2}
TOOLS_RESULT = {"coverage": {"line": dict(FULL), "branch": {"coverable": 1, "covered": 1}}}


def _doc(**over):
    doc = {
        "schema_version": 2,
        "kind": "tools",
        "status": "PASS",
        "captured_at": "2026-11-13T10:00:00+00:00",
        "source": copy.deepcopy(SOURCE),
        "environment": copy.deepcopy(ENVIRONMENT),
        "execution": copy.deepcopy(EXECUTION),
        "artifacts": {"a.json": "c" * 64},
        "result": copy.deepcopy(TOOLS_RESULT),
    }
    doc.update(over)
    return doc


def _with(path, value):
    doc = _doc()
    target = doc
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return doc


def test_a_well_formed_document_has_no_problem_and_a_non_dict_is_refused():
    assert es.validate(_doc()) == []
    assert es.validate([]) == ["evidence must be a JSON object"]


ENVELOPE_FAULTS = [
    (_with(["schema_version"], 1), "schema_version must be 2"),
    (_with(["schema_version"], True), "schema_version must be 2"),
    (_with(["schema_version"], "2"), "schema_version must be 2"),
    (_with(["schema_version"], KeyError), "schema_version must be 2"),
    (_with(["kind"], "other"), "kind must be one of " + ", ".join(es.KINDS)),
    (_with(["status"], "pass"), "status must be one of " + ", ".join(es.STATUSES)),
    (_with(["captured_at"], KeyError), "captured_at must be an ISO-8601 timestamp"),
    (_with(["captured_at"], 5), "captured_at must be an ISO-8601 timestamp"),
    (_with(["captured_at"], "yesterday"), "captured_at must be an ISO-8601 timestamp"),
    (_with(["captured_at"], "2026-11-13T10:00:00"), "captured_at has no timezone"),
    (_with(["source"], "x"), "source must be a mapping"),
    (_with(["source", "revision"], "abc"), "source.revision must be a 40-character commit hash"),
    (_with(["source", "revision"], 7), "source.revision must be a 40-character commit hash"),
    (_with(["source", "revision"], "A" * 40), "source.revision must be a 40-character commit hash"),
    (_with(["source", "worktree_dirty"], 1), "source.worktree_dirty must be a boolean"),
    (
        _with(["source", "scientific_fingerprint"], "b" * 63),
        "source.scientific_fingerprint must be a sha256 hex digest",
    ),
    (
        _with(["source", "scientific_fingerprint"], None),
        "source.scientific_fingerprint must be a sha256 hex digest",
    ),
    (_with(["environment"], []), "environment must be a mapping"),
    (_with(["environment", "python"], 3), "environment.python must be a string"),
    (_with(["environment", "platform"], None), "environment.platform must be a string"),
    (_with(["environment", "packages"], []), "environment.packages must map names to versions"),
    (
        _with(["environment", "packages"], {"pandas": 3}),
        "environment.packages must map names to versions",
    ),
    (_with(["artifacts"], []), "artifacts must be a mapping"),
    (_with(["artifacts"], {"a": "xyz"}), "artifacts must map paths to sha256 hex digests"),
    (_with(["artifacts"], {"a": 5}), "artifacts must map paths to sha256 hex digests"),
    (_with(["result"], []), "result must be a mapping"),
]
EXECUTION_MESSAGE = "execution must give ci (a boolean), run_id, runner_environment, runner_name"
EXECUTION_FAULTS = [
    _with(["execution"], "x"),
    _with(["execution", "ci"], KeyError),
    _with(["execution", "ci"], "yes"),
    _with(["execution", "run_id"], 5),
    _with(["execution", "runner_name"], 5),
    _with(["execution", "extra"], 1),
]


@pytest.mark.parametrize(("doc", "message"), ENVELOPE_FAULTS)
def test_each_envelope_fault_alone_is_reported_with_its_own_reason(doc, message):
    assert es.validate(doc) == [message]


@pytest.mark.parametrize("doc", EXECUTION_FAULTS)
def test_the_execution_block_must_have_exactly_its_four_typed_fields(doc):
    assert es.validate(doc) == [EXECUTION_MESSAGE]


def test_the_execution_block_may_be_absent_or_carry_text_in_its_three_text_fields():
    absent = _doc()
    del absent["execution"]
    assert es.validate(absent) == []
    full = _with(
        ["execution"],
        {"ci": True, "run_id": "1", "runner_environment": "github-hosted", "runner_name": "n"},
    )
    assert es.validate(full) == []


def test_a_package_version_may_be_unknown():
    doc = _with(["environment", "packages"], {"torch": None, "pandas": "3.0.6"})
    assert es.validate(doc) == []


def test_every_environment_fault_is_listed_together_with_the_others():
    doc = _doc(environment={"python": 1, "platform": 2, "packages": 3})
    assert es.validate(doc) == [
        "environment.python must be a string",
        "environment.platform must be a string",
        "environment.packages must map names to versions",
    ]


def test_the_result_is_only_read_when_the_envelope_is_sound():
    doc = _doc(kind="nonsense", result={})
    assert es.validate(doc) == ["kind must be one of " + ", ".join(es.KINDS)]


def test_a_result_missing_what_its_rule_reads_is_malformed_not_a_crash():
    doc = _doc(result={})
    assert es.validate(doc) == ["result is malformed for kind tools: KeyError('coverage')"]


def test_a_pass_must_be_supported_by_its_result_and_list_its_artifacts():
    failing = {"coverage": {"line": {"coverable": 2, "covered": 1}, "branch": dict(FULL)}}
    assert es.validate(_doc(result=failing)) == [
        "status PASS is not supported by the result (it gives FAIL)"
    ]
    assert es.validate(_doc(artifacts={})) == ["a PASS must list the artifacts it was derived from"]
    assert es.validate(_doc(status="FAIL", result=failing, artifacts={})) == []


def test_a_deep_status_must_equal_the_recomputed_one_for_a_versioned_result(monkeypatch):
    monkeypatch.setattr(es.mutation_campaign, "status", lambda result: "FAIL")
    doc = _doc(kind="deep", status="INCOMPLETE", result={"format_version": 2})
    assert es.validate(doc) == ["deep status INCOMPLETE differs from the recomputed result FAIL"]
    assert es.validate(_doc(kind="deep", status="FAIL", result={"format_version": 2})) == []


def test_a_legacy_deep_pass_needs_a_scope_and_integer_counts(monkeypatch):
    monkeypatch.setattr(check_mutation, "classify", lambda stats: ("PASS", 99.0))
    stats = {key: 1 for key in ("total", *es.OUTCOMES)}
    legacy = {"stats": stats, "scope": ["m"], "scope_files": ["m.py"], "mutated_files": []}
    assert es.validate(_doc(kind="deep", result=legacy)) == []
    empty = {**legacy, "scope": []}
    assert es.validate(_doc(kind="deep", result=empty)) == [
        "status PASS is not supported by the result (it gives INCOMPLETE)",
        "deep result has an empty mutation scope",
    ]
    bad = {**legacy, "stats": {**stats, "killed": 1.5}}
    assert es.validate(_doc(kind="deep", result=bad)) == [
        "result is malformed for kind deep: ValueError('stats.killed must be an integer')"
    ]
    flag = {**legacy, "stats": {**stats, "total": True}}
    assert "stats.total must be an integer" in es.validate(_doc(kind="deep", result=flag))[0]


def test_artifacts_are_checked_against_a_root_by_existence_and_hash(tmp_path):
    good = tmp_path / "a.json"
    good.write_text("{}")
    digest = es._sha256(good)
    assert es.validate(_doc(artifacts={"a.json": digest}), root=tmp_path) == []
    assert es.validate(_doc(artifacts={"a.json": "d" * 64}), root=tmp_path) == [
        "artifact a.json hash differs from the recorded one"
    ]
    assert es.validate(_doc(artifacts={"gone.json": digest}), root=tmp_path) == [
        "artifact gone.json is missing"
    ]


def _fast(total=1, failures=0, errors=0, skipped=0, line=(2, 2), branch=(1, 1)):
    return {
        "tests": {"total": total, "failures": failures, "errors": errors, "skipped": skipped},
        "coverage": {
            "line": {"coverable": line[0], "covered": line[1]},
            "branch": {"coverable": branch[0], "covered": branch[1]},
        },
    }


def test_a_fast_run_passes_only_with_tests_none_failing_or_skipped_and_full_coverage():
    assert es._fast_status(_fast()) == "PASS"
    assert es._fast_status(_fast(total=0)) == "FAIL"
    for field in ("failures", "errors", "skipped"):
        assert es._fast_status(_fast(**{field: 1})) == "FAIL"
    assert es._fast_status(_fast(line=(2, 1))) == "FAIL"
    assert es._fast_status(_fast(branch=(1, 0))) == "FAIL"
    assert es._fast_status(_fast(line=(0, 0))) == "FAIL"
    assert es._fast_status(_fast(line=(1, 1), branch=(1, 1))) == "PASS"


def test_the_tools_profile_needs_every_line_and_branch_covered_and_a_single_one_is_enough():
    assert es._tools_status(TOOLS_RESULT) == "PASS"
    one = {
        "coverage": {
            "line": {"coverable": 1, "covered": 1},
            "branch": {"coverable": 1, "covered": 1},
        }
    }
    assert es._tools_status(one) == "PASS"
    none = {
        "coverage": {
            "line": {"coverable": 0, "covered": 0},
            "branch": {"coverable": 1, "covered": 1},
        }
    }
    assert es._tools_status(none) == "FAIL"
    short = {"coverage": {"line": dict(FULL), "branch": {"coverable": 2, "covered": 1}}}
    assert es._tools_status(short) == "FAIL"


def _faults(defects, expected, control=True, detected=True):
    return {
        "faults": [{"defect": d, "detected": detected} for d in defects],
        "expected": expected,
        "control_passed": control,
    }


def test_the_fault_profile_is_incomplete_unless_every_expected_defect_ran_exactly_once():
    assert es._faults_status(_faults(["a", "b"], ["a", "b"])) == "PASS"
    assert es._faults_status(_faults([], [])) == "INCOMPLETE"
    assert es._faults_status(_faults(["a", "c"], ["a", "b"])) == "INCOMPLETE"
    assert es._faults_status(_faults(["a"], ["a", "b"])) == "INCOMPLETE"
    assert es._faults_status(_faults(["a", "a"], ["a", "a"])) == "PASS"
    assert es._faults_status(_faults(["a", "b", "b"], ["a", "b"])) == "INCOMPLETE"
    assert es._faults_status(_faults(["a", "b"], ["a", "b"], control=False)) == "FAIL"
    assert es._faults_status(_faults(["a", "b"], ["a", "b"], detected=False)) == "FAIL"


def _real(required, names, states):
    return {
        "required": list(required),
        "datasets": [{"dataset": n, "status": s} for n, s in zip(names, states, strict=True)],
    }


def test_the_real_profile_needs_the_required_datasets_and_reports_not_run_without_failures():
    req = verify_real.REQUIRED_DATASETS
    assert es._real_status(_real(req, req, ["PASS"] * 3)) == "PASS"
    assert es._real_status(_real(req, req, ["PASS", "NOT_RUN", "PASS"])) == "NOT_RUN"
    assert es._real_status(_real(req, req, ["NOT_RUN"] * 3)) == "NOT_RUN"
    assert es._real_status(_real(req, req, ["PASS", "FAIL", "NOT_RUN"])) == "FAIL"
    assert es._real_status(_real(req, req, ["PASS", "PASS", "INCOMPLETE"])) == "FAIL"
    assert es._real_status(_real([], [], [])) == "FAIL"
    assert es._real_status(_real(["credit_card"], ["credit_card"], ["PASS"])) == "FAIL"
    assert es._real_status(_real(req, [*req[:2], "other"], ["PASS"] * 3)) == "FAIL"
    assert es._real_status(_real(req, req[:2], ["PASS"] * 2)) == "FAIL"


def test_the_types_and_reproduction_profiles_follow_their_states():
    assert es._types_status({"state": "PASS", "problems": []}) == "PASS"
    assert es._types_status({"state": "PASS", "problems": ["x"]}) == "FAIL"
    assert es._types_status({"state": "FAIL", "problems": []}) == "FAIL"
    assert es._types_status({"state": "INCOMPLETE", "problems": []}) == "INCOMPLETE"
    levels = {n: "PASS" for n in es.REPRODUCTION_LEVELS}
    assert es._reproduction_status({"levels": levels}) == "PASS"
    assert es._reproduction_status({"levels": {**levels, "archive": "FAIL"}}) == "FAIL"
    assert (
        es._reproduction_status({"levels": {**levels, "archive": "FAIL", "same_environment": None}})
        == "FAIL"
    )
    assert es._reproduction_status({"levels": {"archive": "PASS"}}) == "INCOMPLETE"
    assert es._reproduction_status({"levels": {**levels, "version_sensitivity": "FAIL"}}) == "PASS"
    assert (
        es._reproduction_status({"levels": {**levels, "locked_environment": "NOT_RUN"}})
        == "INCOMPLETE"
    )


def test_the_deep_profile_is_incomplete_for_unreliable_counts_scope_or_mutated_files(monkeypatch):
    ok = {"stats": {"total": 1}, "scope": ["m"], "scope_files": ["m.py"], "mutated_files": ["m.py"]}
    monkeypatch.setattr(check_mutation, "classify", lambda stats: ("FAIL", 10.0))
    assert es._deep_status(ok) == "FAIL"
    assert es._deep_status({**ok, "scope": []}) == "INCOMPLETE"
    assert es._deep_status({**ok, "scope_files": []}) == "INCOMPLETE"
    assert es._deep_status({**ok, "scope_files": None}) == "INCOMPLETE"
    assert es._deep_status({**ok, "mutated_files": None}) == "INCOMPLETE"
    assert es._deep_status({k: v for k, v in ok.items() if k != "mutated_files"}) == "INCOMPLETE"

    def refuse(stats):
        raise ValueError("unreliable")

    monkeypatch.setattr(check_mutation, "classify", refuse)
    assert es._deep_status(ok) == "INCOMPLETE"
    monkeypatch.setattr(es.mutation_campaign, "status", lambda result: "PASS")
    assert es._deep_status({"format_version": 2}) == "PASS"


def test_the_envelope_copies_its_inputs_hashes_existing_artifacts_and_stamps_utc_time(tmp_path):
    (tmp_path / "sub").mkdir()
    present = tmp_path / "sub" / "a.json"
    present.write_text("{}")
    absent = tmp_path / "gone.json"
    source, environment, execution = (
        copy.deepcopy(SOURCE),
        copy.deepcopy(ENVIRONMENT),
        copy.deepcopy(EXECUTION),
    )
    doc = es._envelope(
        "tools", "PASS", TOOLS_RESULT, [present, absent], tmp_path, source, environment, execution
    )
    source["revision"] = "mutated"
    environment["packages"]["pandas"] = "0"
    execution["ci"] = True
    assert (
        doc["source"] == SOURCE
        and doc["environment"] == ENVIRONMENT
        and doc["execution"] == EXECUTION
    )
    assert doc["artifacts"] == {"sub/a.json": es._sha256(present)}
    assert doc["kind"] == "tools" and doc["status"] == "PASS" and doc["result"] == TOOLS_RESULT
    assert doc["schema_version"] == es.SCHEMA_VERSION
    assert es.validate(doc) == []
    assert str(doc["captured_at"]).endswith("+00:00")


def test_a_missing_source_environment_or_execution_is_collected_from_the_machine(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(es, "collect_source", lambda: SOURCE)
    monkeypatch.setattr(es, "collect_environment", lambda: ENVIRONMENT)
    monkeypatch.setattr(es, "collect_execution", lambda: EXECUTION)
    doc = es._envelope("tools", "FAIL", {}, [], tmp_path, None, None)
    assert (
        doc["source"] == SOURCE
        and doc["environment"] == ENVIRONMENT
        and doc["execution"] == EXECUTION
    )


def test_the_execution_context_reads_only_the_github_variables_and_ci_needs_the_value_true():
    assert es.collect_execution({}) == EXECUTION
    ci = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ID": "9",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_NAME": "r",
    }
    assert es.collect_execution(ci) == {
        "ci": True,
        "run_id": "9",
        "runner_environment": "github-hosted",
        "runner_name": "r",
    }
    assert es.collect_execution({"GITHUB_ACTIONS": "false"})["ci"] is False
    assert es.collect_execution({"GITHUB_ACTIONS": "True"})["ci"] is False


def test_the_environment_lists_each_tracked_package_with_none_for_an_absent_one(monkeypatch):
    def installed(name):
        if name == es.PACKAGES[0]:
            raise es.PackageNotFoundError(name)
        return "1.2.3"

    monkeypatch.setattr(es, "version", installed)
    env = es.collect_environment()
    assert set(env) == {"python", "platform", "packages"}
    assert list(env["packages"]) == list(es.PACKAGES)
    assert env["packages"][es.PACKAGES[0]] is None and env["packages"][es.PACKAGES[1]] == "1.2.3"
    assert es.validate(_doc(environment=env)) == []


def test_the_source_is_the_head_revision_and_whether_the_worktree_is_dirty(monkeypatch, tmp_path):
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *command], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=tmp_path, check=True)
    monkeypatch.setattr(es.provenance, "scientific_fingerprint", lambda: "f" * 64)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    clean = es.collect_source(tmp_path)
    assert clean == {"revision": head, "worktree_dirty": False, "scientific_fingerprint": "f" * 64}
    (tmp_path / "f.txt").write_text("b")
    assert es.collect_source(tmp_path)["worktree_dirty"] is True


def test_the_document_is_written_sorted_indented_and_reports_its_status(tmp_path, capsys):
    out = tmp_path / "new" / "dir" / "e.json"
    doc = {"kind": "fast", "status": "PASS", "b": 1, "a": 2}
    assert es._write(doc, out) == 0
    assert out.read_text() == json.dumps(doc, indent=2, sort_keys=True) + "\n"
    assert capsys.readouterr().out == "fast evidence: PASS\n"
    assert es._write({"kind": "deep", "status": "INCOMPLETE"}, out) == 1
    assert es._write({"kind": "deep", "status": "FAIL"}, out) == 1


BUILDERS = {
    "fast": (("coverage", "junit"), "build_fast"),
    "deep": (("stats", "results"), "build_deep"),
    "faults": (("matrix",), "build_faults"),
    "real": (("report",), "build_real"),
    "tools": (("coverage",), "build_tools"),
    "types": (("report",), "build_types"),
    "reproduction": (("report",), "build_reproduction"),
}


def _argv(name, tmp_path, *extra):
    inputs, _ = BUILDERS[name]
    argv = [name]
    for item in inputs:
        argv += [f"--{item}", str(tmp_path / f"{item}.json")]
    return [*argv, "--output", str(tmp_path / "out" / "e.json"), *extra]


@pytest.mark.parametrize("name", list(BUILDERS))
def test_each_builder_command_routes_its_inputs_and_root_and_writes_the_document(
    name, tmp_path, monkeypatch, capsys
):
    seen = {}
    function = BUILDERS[name][1]
    monkeypatch.setattr(
        es,
        function,
        lambda *a, **k: seen.update(args=a, kwargs=k) or {"kind": name, "status": "PASS"},
    )
    monkeypatch.setattr(es, "fault_names", lambda: ["x"])
    assert es.main(_argv(name, tmp_path)) == 0
    assert capsys.readouterr().out == f"{name} evidence: PASS\n"
    assert seen["kwargs"]["root"] == es.ROOT
    assert all(isinstance(a, Path) for a in seen["args"] if a not in (["x"], None))
    assert json.loads((tmp_path / "out" / "e.json").read_text()) == {"kind": name, "status": "PASS"}
    assert es.main(_argv(name, tmp_path, "--root", str(tmp_path))) == 0
    assert seen["kwargs"]["root"] == tmp_path


@pytest.mark.parametrize("name", list(BUILDERS))
def test_a_builder_failure_is_reported_as_invalid_and_exits_one(
    name, tmp_path, monkeypatch, capsys
):
    def refuse(*a, **k):
        raise ValueError("bad input")

    monkeypatch.setattr(es, BUILDERS[name][1], refuse)
    monkeypatch.setattr(es, "fault_names", lambda: [])
    assert es.main(_argv(name, tmp_path)) == 1
    assert capsys.readouterr().out == "INVALID: bad input\n"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", list(BUILDERS))
def test_each_builder_requires_its_inputs_and_its_output_and_describes_itself(
    name, tmp_path, capsys
):
    inputs, _ = BUILDERS[name]
    for missing in (*inputs, "output"):
        argv = [name]
        for item in (*inputs, "output"):
            if item != missing:
                argv += [f"--{item}", "x"]
        with pytest.raises(SystemExit) as stop:
            es.main(argv)
        assert stop.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        es.main(["--help"])
    assert f"wrap the raw {name} results in an envelope" in " ".join(
        capsys.readouterr().out.split()
    )


def test_the_real_and_deep_builders_take_their_optional_inputs_and_the_command_is_required(
    tmp_path, monkeypatch, capsys
):
    seen = {}
    monkeypatch.setattr(
        es,
        "build_real",
        lambda report, acquisition=None, root=None: (
            seen.update(real=acquisition) or {"kind": "real", "status": "PASS"}
        ),
    )
    monkeypatch.setattr(
        es,
        "build_deep",
        lambda stats, results, run_report=None, root=None: (
            seen.update(deep=run_report) or {"kind": "deep", "status": "PASS"}
        ),
    )
    assert es.main(_argv("real", tmp_path)) == 0 and seen["real"] is None
    assert es.main(_argv("real", tmp_path, "--acquisition", str(tmp_path / "a.json"))) == 0
    assert seen["real"] == tmp_path / "a.json"
    assert es.main(_argv("deep", tmp_path)) == 0 and seen["deep"] is None
    assert es.main(_argv("deep", tmp_path, "--run", str(tmp_path / "r.json"))) == 0
    assert seen["deep"] == tmp_path / "r.json"
    capsys.readouterr()
    with pytest.raises(SystemExit) as stop:
        es.main([])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        es.main(["deep", "--help"])
    assert "managed controller result" in " ".join(capsys.readouterr().out.split())


def test_the_shard_command_wraps_a_sharded_campaign_with_its_plan_and_manifests(
    tmp_path, monkeypatch, capsys
):
    seen = {}
    monkeypatch.setattr(
        es,
        "build_deep_shards",
        lambda plan, manifests, root=None: (
            seen.update(plan=plan, manifests=manifests, root=root)
            or {"kind": "deep", "status": "FAIL"}
        ),
    )
    argv = [
        "deep-shards",
        "--plan",
        "p.json",
        "--manifests",
        "m1.json",
        "m2.json",
        "--output",
        str(tmp_path / "o.json"),
    ]
    assert es.main(argv) == 1
    assert seen == {
        "plan": Path("p.json"),
        "manifests": [Path("m1.json"), Path("m2.json")],
        "root": es.ROOT,
    }
    assert capsys.readouterr().out == "deep evidence: FAIL\n"
    with pytest.raises(SystemExit) as stop:
        es.main(["deep-shards", "--plan", "p.json", "--output", "o"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        es.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "wrap a sharded mutation campaign" in text and "validate one evidence file" in text


def test_the_validate_command_reports_each_problem_and_the_valid_document(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_doc()))
    assert es.main(["validate", str(good)]) == 0
    assert capsys.readouterr().out == "valid tools evidence: PASS\n"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(_doc(kind="x", status="y")))
    assert es.main(["validate", str(bad)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "INVALID: kind must be one of " + ", ".join(es.KINDS),
        "INVALID: status must be one of " + ", ".join(es.STATUSES),
    ]
    missing = tmp_path / "none.json"
    assert es.main(["validate", str(missing)]) == 1
    assert capsys.readouterr().out.startswith(f"INVALID: cannot read {missing}: ")
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    assert es.main(["validate", str(broken)]) == 1
    assert capsys.readouterr().out.startswith(f"INVALID: cannot read {broken}: ")


def test_the_validate_command_can_verify_artifact_hashes_under_a_root(tmp_path, capsys):
    doc = _doc(artifacts={"a.json": "d" * 64})
    target = tmp_path / "e.json"
    target.write_text(json.dumps(doc))
    (tmp_path / "a.json").write_text("{}")
    assert es.main(["validate", str(target), "--root", str(tmp_path)]) == 1
    assert (
        capsys.readouterr().out == "INVALID: artifact a.json hash differs from the recorded one\n"
    )
    assert es.main(["validate", str(target)]) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit):
        es.main(["validate", "--help"])
    assert "verify artifact hashes here" in " ".join(capsys.readouterr().out.split())
