"""The public mutation gate must enforce current per-scope evidence."""

from experiments import check_mutation
from tests.test_mutation_campaign import _fixture


def _args(root, inputs):
    return [
        str(inputs[0]),
        "--root",
        str(root),
        "--results",
        str(inputs[1]),
        "--run",
        str(inputs[2]),
    ]


def test_current_mutation_cli_uses_bound_per_scope_results(tmp_path, capsys):
    inputs = _fixture(tmp_path)
    assert check_mutation.main(_args(tmp_path, inputs)) == 0
    out = capsys.readouterr().out
    assert "mutation gate: PASS" in out and "L4" in out and "98" in out


def test_counts_without_execution_data_cannot_pass_the_current_cli(tmp_path, capsys):
    inputs = _fixture(tmp_path)
    inputs[2].unlink()
    assert check_mutation.main(_args(tmp_path, inputs)) == 1
    assert "INVALID" in capsys.readouterr().out


def test_a_failed_critical_scope_returns_a_failed_gate(tmp_path, capsys):
    inputs = _fixture(tmp_path, survived=True)
    assert check_mutation.main(_args(tmp_path, inputs)) == 1
    assert "mutation gate: FAIL" in capsys.readouterr().out


def test_nonzero_native_exit_cannot_be_hidden_by_successful_counts(tmp_path, capsys):
    inputs = _fixture(tmp_path, exit_code=2)
    assert check_mutation.main(_args(tmp_path, inputs)) == 1
    assert "mutation gate: INCOMPLETE" in capsys.readouterr().out


def test_technical_no_mutant_modules_are_not_listed_as_scored(monkeypatch, capsys):
    from verification import mutation_campaign

    scored = {"level": "L4", "status": "PASS", "killed": 98, "eligible": 100, "threshold": 98}
    technical = {"level": "L2", "status": "NO_MUTANTS_TECHNICAL"}
    result = {
        "native_exit_code": 0,
        "analysis": {"modules": {"pkg/__init__.py": technical, "pkg/core.py": scored}},
    }
    monkeypatch.setattr(mutation_campaign, "load_campaign", lambda *args: (result, None))
    monkeypatch.setattr(mutation_campaign, "status", lambda value: "PASS")
    assert check_mutation.main(["stats.json"]) == 0
    out = capsys.readouterr().out
    assert "pkg/core.py: L4 PASS (98/100; required 98%)" in out
    assert "pkg/__init__.py" not in out
