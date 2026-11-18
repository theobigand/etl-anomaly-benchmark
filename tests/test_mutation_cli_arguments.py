"""How the mutation gate command resolves its inputs, shown without running a campaign."""

import sys
from pathlib import Path

import pytest

from experiments import check_mutation
from verification import mutation_campaign


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def load(root, stats, results, run):
        calls.append((root, stats, results, run))
        return {"native_exit_code": 0, "analysis": {"modules": {}}}, None

    monkeypatch.setattr(mutation_campaign, "load_campaign", load)
    monkeypatch.setattr(mutation_campaign, "status", lambda result: "PASS")
    return calls


def test_the_inputs_default_to_the_files_under_the_root(captured, tmp_path):
    assert check_mutation.main(["stats.json", "--root", str(tmp_path)]) == 0
    root, stats, results, run = captured[0]
    assert root == tmp_path and stats == Path("stats.json")
    assert results == tmp_path / "mutants/results.txt"
    assert run == tmp_path / "mutants/controller-result.json"


def test_explicit_inputs_are_paths_and_are_used_as_given(captured, tmp_path):
    argv = ["s.json", "--root", str(tmp_path), "--results", "r.txt", "--run", "c.json"]
    assert check_mutation.main(argv) == 0
    _, stats, results, run = captured[0]
    assert (stats, results, run) == (Path("s.json"), Path("r.txt"), Path("c.json"))
    assert all(isinstance(item, Path) for item in (stats, results, run))


def test_only_the_results_default_is_replaced_when_only_the_run_is_given(captured, tmp_path):
    assert check_mutation.main(["s.json", "--root", str(tmp_path), "--run", "c.json"]) == 0
    _, _, results, run = captured[0]
    assert results == tmp_path / "mutants/results.txt" and run == Path("c.json")
    check_mutation.main(["s.json", "--root", str(tmp_path), "--results", "r.txt"])
    _, _, results, run = captured[1]
    assert results == Path("r.txt") and run == tmp_path / "mutants/controller-result.json"


def test_the_root_defaults_to_the_repository_and_leads_the_import_path(captured, monkeypatch):
    monkeypatch.setattr(sys, "path", ["elsewhere"])
    assert check_mutation.main(["s.json"]) == 0
    assert captured[0][0] == check_mutation.ROOT
    assert sys.path[0] == str(check_mutation.ROOT)


def test_the_stats_file_is_required_and_the_help_names_the_run_result(capsys):
    with pytest.raises(SystemExit) as stop:
        check_mutation.main([])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        check_mutation.main(["--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "managed native controller result" in out
