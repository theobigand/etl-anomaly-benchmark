"""Exact refusals, files, forwarded names and report of the managed native mutation run."""

import json
import os
import subprocess
import types

import pytest

from tests.verifier.test_mutation_run import SOURCE, _api, _engine, _repository


def _refused(call, message):
    with pytest.raises(ValueError) as refused:
        call()
    assert str(refused.value) == message


def test_two_installed_versions_of_one_distribution_are_refused_by_name_of_the_conflict(
    monkeypatch,
):
    api = _api()

    def dist(name, version):
        return types.SimpleNamespace(metadata={"Name": name}, version=version)

    monkeypatch.setattr(api, "distributions", lambda: [dist("Pkg_X", "1"), dist("pkg-x", "2")])
    _refused(lambda: api.collect_runtime({}), "conflicting installed distribution versions")


def test_an_unlisted_exclusion_of_the_native_scope_is_applied_before_comparing_it(tmp_path):
    _repository(tmp_path)
    (tmp_path / "src/pkg/tests").mkdir()
    (tmp_path / "src/pkg/tests/t.py").write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths=["src/pkg"]\nonly_mutate=["src/pkg/*.py"]\n'
        'do_not_mutate=["src/pkg/tests/*"]\n'
    )
    assert _api()._scope(tmp_path) == ([SOURCE], [SOURCE])
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths=["src/pkg"]\nonly_mutate=["src/pkg/*.py"]\n'
    )
    _refused(
        lambda: _api()._scope(tmp_path),
        "native scope does not match the classified production inventory",
    )


def test_source_roots_that_do_not_cover_the_scope_are_refused_with_their_message(tmp_path):
    _repository(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths=["tests"]\nonly_mutate=["src/pkg/a.py"]\n'
    )
    _refused(
        lambda: _api()._scope(tmp_path), "native source roots do not cover the configured scope"
    )


def test_the_process_group_is_probed_with_the_null_signal_and_each_outcome_has_its_message(
    monkeypatch,
):
    api = _api()
    probes = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: probes.append((pid, sig)))
    _refused(
        lambda: api._require_terminal_group(77),
        "native process group still has workers; retain pending execution",
    )
    assert probes == [(77, 0)]

    def gone(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(os, "killpg", gone)
    assert api._require_terminal_group(77) is None

    def denied(pid, sig):
        raise PermissionError

    monkeypatch.setattr(os, "killpg", denied)
    _refused(
        lambda: api._require_terminal_group(77),
        "native process group cannot be inspected; retain pending execution",
    )


@pytest.mark.parametrize("children", [0, -1, True, 1.5, "2"])
def test_an_invalid_number_of_children_is_refused_with_its_message(tmp_path, children):
    _repository(tmp_path)
    _refused(
        lambda: _api().run(tmp_path, max_children=children),
        "max children must be a positive integer",
    )


def test_a_second_controller_is_refused_with_its_message(tmp_path, monkeypatch):
    import fcntl

    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    cache.mkdir()
    with (cache / "execution.lock").open("a+") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _refused(lambda: api.run(tmp_path), "mutation cache already has an active controller")


def test_a_scope_that_changes_during_the_native_run_is_refused_and_stays_pending(
    tmp_path, monkeypatch
):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    real = api._scope
    calls = []

    def scope(root):
        calls.append(1)
        return real(root) if len(calls) == 1 else (["other.py"], [])

    monkeypatch.setattr(api, "_scope", scope)
    _refused(
        lambda: api.run(tmp_path),
        "scope changed during native execution; retain pending execution",
    )
    assert (cache / "execution-pending.json").exists()


def test_an_attempt_keeps_the_native_log_and_the_execution_record_under_their_names(
    tmp_path, monkeypatch
):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    result = api.run(tmp_path)
    attempts = list((cache / "attempts").iterdir())
    assert len(attempts) == 1
    assert sorted(p.name for p in attempts[0].iterdir()) == ["execution.json", "native.log"]
    assert result["native_log"] == f"mutants/attempts/{attempts[0].name}/native.log"
    assert result["attempt_record"] == f"mutants/attempts/{attempts[0].name}/execution.json"
    record = json.loads((attempts[0] / "execution.json").read_text())
    assert set(record) == {"native_pid", "admission", "proof", "native_log", "native_log_sha256"}
    assert record["native_log"] == result["native_log"]


def test_the_name_patterns_are_appended_to_the_native_command(tmp_path, monkeypatch):
    _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    seen = []
    real = subprocess.Popen

    def popen(command, **kwargs):
        seen.append(command)
        return real(command, **kwargs)

    monkeypatch.setattr(api.subprocess, "Popen", popen)
    api.run(tmp_path, names=("pkg.a.*", "pkg.b.*"))
    assert seen[0][-2:] == ["pkg.a.*", "pkg.b.*"]


def test_the_command_line_forwards_its_names_and_prints_the_report_with_sorted_keys(
    tmp_path, monkeypatch, capsys
):
    api = _api()
    seen = {}

    def run(root, *, max_children, names):
        seen.update(root=root, max_children=max_children, names=names)
        return {"native_exit_code": 0, "b": 1, "a": 2}

    monkeypatch.setattr(api, "run", run)
    assert api.main(["--root", str(tmp_path), "--max-children", "4", "--names", "x*", "y*"]) == 0
    assert capsys.readouterr().out == '{"a": 2, "b": 1, "native_exit_code": 0}\n'
    assert seen == {"root": tmp_path, "max_children": 4, "names": ("x*", "y*")}
    api.main(["--root", str(tmp_path)])
    assert seen["names"] == () and seen["max_children"] == 2
    monkeypatch.setattr(api, "run", lambda *a, **k: {"native_exit_code": 3})
    assert api.main([]) == 1


def test_the_command_line_help_describes_the_run_and_the_names(capsys):
    with pytest.raises(SystemExit):
        _api().main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "Run native mutation in an owned POSIX process group" in text
    assert "--names [NAMES ...]" in text and "native mutant-name patterns" in text
