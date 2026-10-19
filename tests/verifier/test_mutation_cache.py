"""Cached mutation verdicts are reused only for code and tests that did not change."""

import json
import runpy
import sys
from pathlib import Path

import pytest

from verification import mutation_cache as mc

KILLED, SURVIVED, TIMEOUT, TYPED = 1, 0, 36, 37
STATS = {
    "pkg.a.x_f": ["tests/test_a.py::t1", "tests/test_b.py::t2"],
    "pkg.a.x_g": ["tests/test_b.py::t2"],
    "pkg.b.x_h": ["tests/test_c.py::t3"],
}
VERDICTS = {
    "pkg.a.x_f__mutmut_1": KILLED,
    "pkg.a.x_f__mutmut_2": SURVIVED,
    "pkg.a.x_g__mutmut_1": KILLED,
    "pkg.b.x_h__mutmut_1": KILLED,
    "pkg.b.x_h__mutmut_2": TYPED,
    "pkg.b.x_h__mutmut_3": None,
}
SAME = {"tests/test_a.py": "1", "tests/test_b.py": "1", "tests/test_c.py": "1"}


def test_the_function_of_a_mutant_key_is_its_function_name():
    assert mc.function_of("pkg.a.x_f__mutmut_12") == "pkg.a.x_f"


def test_nothing_is_reset_when_no_test_changed():
    assert mc.keys_to_reset(SAME, dict(SAME), STATS, VERDICTS) == []


def test_without_a_baseline_nothing_is_reset_because_mutmut_runs_everything():
    assert mc.keys_to_reset(None, SAME, STATS, VERDICTS) == []


def test_a_modified_test_resets_the_functions_it_covers_and_every_unsettled_verdict():
    new = {**SAME, "tests/test_a.py": "2"}
    reset = mc.keys_to_reset(SAME, new, STATS, VERDICTS)
    # test_a covers x_f only: its killed mutant goes back to be checked, the other function's
    # killed mutants stay; survivors and unchecked mutants are rerun because the test may
    # now reach them
    assert set(reset) == {"pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_2", "pkg.b.x_h__mutmut_3"}


def test_a_shared_test_resets_every_function_it_covers():
    new = {**SAME, "tests/test_b.py": "2"}
    reset = set(mc.keys_to_reset(SAME, new, STATS, VERDICTS))
    assert {"pkg.a.x_f__mutmut_1", "pkg.a.x_g__mutmut_1"} <= reset
    assert "pkg.b.x_h__mutmut_1" not in reset


def test_a_removed_test_resets_what_it_covered():
    new = {k: v for k, v in SAME.items() if k != "tests/test_c.py"}
    reset = set(mc.keys_to_reset(SAME, new, STATS, VERDICTS))
    assert "pkg.b.x_h__mutmut_1" in reset and "pkg.a.x_g__mutmut_1" not in reset


def test_an_added_test_only_reopens_the_verdicts_it_could_still_change():
    new = {**SAME, "tests/test_d.py": "1"}
    reset = set(mc.keys_to_reset(SAME, new, STATS, VERDICTS))
    assert reset == {"pkg.a.x_f__mutmut_2", "pkg.b.x_h__mutmut_3"}


def test_a_type_checker_verdict_is_never_reset_by_a_test_change():
    new = {**SAME, "tests/test_c.py": "2"}
    assert "pkg.b.x_h__mutmut_2" not in mc.keys_to_reset(SAME, new, STATS, VERDICTS)


def test_the_hashes_follow_the_content_of_every_test_file(tmp_path):
    (tmp_path / "tests" / "sub").mkdir(parents=True)
    (tmp_path / "tests" / "test_a.py").write_text("x = 1\n")
    (tmp_path / "tests" / "sub" / "test_b.py").write_text("y = 2\n")
    (tmp_path / "tests" / "data.txt").write_text("not python\n")
    first = mc.hash_tests(tmp_path)
    assert set(first) == {"tests/test_a.py", "tests/sub/test_b.py"}
    (tmp_path / "tests" / "test_a.py").write_text("x = 2\n")
    assert mc.hash_tests(tmp_path)["tests/test_a.py"] != first["tests/test_a.py"]


def _mutants(tmp_path, verdicts=VERDICTS, stats=STATS):
    meta = tmp_path / "mutants" / "src" / "pkg" / "a.py.meta"
    meta.parent.mkdir(parents=True)
    meta.write_text(json.dumps({"exit_code_by_key": verdicts, "durations_by_key": {"k": 1}}))
    (tmp_path / "mutants" / "mutmut-stats.json").write_text(
        json.dumps({"tests_by_mangled_function_name": stats})
    )
    (tmp_path / "tests").mkdir()
    for name, text in {"test_a.py": "a", "test_b.py": "b", "test_c.py": "c"}.items():
        (tmp_path / "tests" / name).write_text(text)
    return meta


def test_record_then_prepare_with_unchanged_tests_keeps_every_verdict(tmp_path):
    meta = _mutants(tmp_path)
    mc.record(tmp_path)
    report = mc.prepare(tmp_path)
    assert report["reset"] == 0 and report["kept"] == 5
    assert json.loads(meta.read_text())["exit_code_by_key"] == VERDICTS


def test_prepare_resets_only_what_a_modified_test_covers_and_keeps_the_rest(tmp_path):
    meta = _mutants(tmp_path)
    mc.record(tmp_path)
    (tmp_path / "tests" / "test_c.py").write_text("changed")
    report = mc.prepare(tmp_path)
    saved = json.loads(meta.read_text())
    assert saved["exit_code_by_key"]["pkg.b.x_h__mutmut_1"] is None
    assert saved["exit_code_by_key"]["pkg.a.x_g__mutmut_1"] == KILLED
    assert saved["durations_by_key"] == {"k": 1}
    assert report["modified_tests"] == ["tests/test_c.py"] and report["reset"] >= 1


def test_prepare_without_a_cache_or_a_record_does_nothing(tmp_path):
    assert mc.prepare(tmp_path)["reset"] == 0
    _mutants(tmp_path)
    assert mc.prepare(tmp_path)["reset"] == 0  # no baseline recorded yet


def test_the_command_line_runs_both_steps(tmp_path, monkeypatch, capsys):
    _mutants(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert mc.main(["record"]) == 0
    assert mc.main(["prepare"]) == 0
    assert "mutation cache: kept 5, reset 0" in capsys.readouterr().out


def test_the_command_line_names_the_tests_that_changed(tmp_path, monkeypatch, capsys):
    _mutants(tmp_path)
    monkeypatch.chdir(tmp_path)
    mc.main(["record"])
    (tmp_path / "tests" / "test_c.py").write_text("changed")
    mc.main(["prepare"])
    assert "modified tests: tests/test_c.py" in capsys.readouterr().out


def test_the_module_runs_as_a_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["mutation_cache", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(Path(mc.__file__)), run_name="__main__")
    assert stop.value.code == 0
