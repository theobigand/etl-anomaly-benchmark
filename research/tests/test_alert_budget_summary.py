"""Summary of the alert-budget runs (T165): exact denominators and the table that reports them."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alert_budget as ab  # noqa: E402
import alert_budget_summary as abs_  # noqa: E402


def _cell(rate):
    return {
        "nominal": 0.01, "tp": 1, "fp": 1, "fn": 1, "tn": 7, "precision": 0.5, "recall": 0.25,
        "f1": 0.3333, "fpr": 0.125, "test_alert_rate": rate, "fit_alert_rate": 0.01,
    }  # fmt: skip


def _problem(name, rate=0.03):
    return {
        "problem": name, "source": "adbench", "prevalence": 0.1, "seeds": [42],
        "runs": {"hbos": [{"seed": 42, "test_rows": 10, "budgets": {"0.01": _cell(rate)}}]},
        "errors": {"ecod": [{"seed": 42, "error": "boom"}]}, "skipped": ["knn"],
    }  # fmt: skip


def _write(folder, name, payload):
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps(payload))


def test_load_separates_evaluated_problems_from_problems_that_failed_to_load(tmp_path):
    _write(tmp_path, "b.json", {"problem": "adbench:b", "source": "adbench", "failed": "OSError()"})
    _write(tmp_path, "a.json", _problem("adbench:a"))
    _write(tmp_path, "c.json", _problem("adbench:c"))
    (tmp_path / "notes.txt").write_text("not a result")
    runs, failed = abs_.load(tmp_path)
    assert [r["problem"] for r in runs] == ["adbench:a", "adbench:c"]
    assert all(isinstance(r, dict) and "runs" in r for r in runs)
    assert failed == ["adbench:b"]


def test_load_keeps_a_failed_problem_that_comes_first_and_one_that_comes_last(tmp_path):
    _write(tmp_path, "a.json", {"problem": "adbench:a", "failed": "x"})
    _write(tmp_path, "b.json", _problem("adbench:b"))
    _write(tmp_path, "c.json", {"problem": "adbench:c", "failed": "y"})
    runs, failed = abs_.load(tmp_path)
    assert [r["problem"] for r in runs] == ["adbench:b"] and failed == ["adbench:a", "adbench:c"]


def test_markdown_states_every_denominator_and_one_exact_row_per_detector_budget():
    runs = [_problem("adbench:a", 0.03), _problem("adbench:b", 0.05)]
    table = ab.summarize(runs, budgets=(0.01,))
    accounting = ab.accounting(runs)
    text = abs_.markdown(table, accounting, ["uci:9"])
    assert text.splitlines() == [
        "Problems evaluated: 2; problems that failed to load: 1; failed seed runs: 2; "
        "skipped (problem, detector) pairs: 2.",
        "",
        "| Detector | Budget | Problems | Seed runs | Median alert rate | Alert/budget | "
        "Precision | Recall | F1 | FPR |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "| hbos | 0.010 | 2 | 2 | 0.0400 | 4.00 | 0.500 | 0.250 | 0.333 | 0.1250 |",
    ]
    assert text.endswith("|\n")


def test_markdown_without_any_evaluated_detector_still_reports_the_accounting():
    text = abs_.markdown({}, {"problems": 0, "failed_runs": 0, "skipped_detectors": 0}, [])
    lines = text.splitlines()
    assert lines[0].startswith("Problems evaluated: 0; problems that failed to load: 0;")
    assert len(lines) == 4


def test_main_writes_the_json_and_the_markdown_from_the_folder(tmp_path):
    folder = tmp_path / "runs"
    _write(folder, "a.json", _problem("adbench:a"))
    _write(folder, "b.json", {"problem": "adbench:b", "source": "adbench", "failed": "x"})
    out_json, out_md = tmp_path / "s.json", tmp_path / "s.md"
    assert abs_.main([str(folder), "--json", str(out_json), "--markdown", str(out_md)]) == 0
    text = out_json.read_text()
    data = json.loads(text)
    assert text == json.dumps(data, indent=1, sort_keys=True) + "\n"
    assert data["budgets"] == list(ab.BUDGETS)
    assert data["accounting"] == {"problems": 1, "failed_runs": 1, "skipped_detectors": 1}
    assert data["failed_problems"] == ["adbench:b"]
    assert data["rules"] == {} and set(data["table"]) == {"hbos"}
    assert data["table"]["hbos"]["0.01"]["problems"] == 1
    runs, failed = abs_.load(folder)
    assert out_md.read_text() == abs_.markdown(ab.summarize(runs), ab.accounting(runs), failed)


def test_main_requires_both_outputs_and_documents_itself(tmp_path, capsys):
    for argv in (
        [str(tmp_path)],
        [str(tmp_path), "--json", str(tmp_path / "j")],
        [str(tmp_path), "--markdown", str(tmp_path / "m")],
    ):
        with pytest.raises(SystemExit) as stop:
            abs_.main(argv)
        assert stop.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        abs_.main(["--help"])
    assert "exact denominators and a Markdown table" in " ".join(capsys.readouterr().out.split())
