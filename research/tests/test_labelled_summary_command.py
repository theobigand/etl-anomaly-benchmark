"""The labelled summary command: its help, its output structure and its ranking sentence."""

import json
import sys
from pathlib import Path

import pytest
from test_labelled_summary_contracts import _run, _suite, _write_runs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_summary as ls  # noqa: E402


def _both(tmp_path):
    _write_runs(tmp_path / "runs", _suite())
    deep = [
        _run(f"p{i}", "uci" if i < 2 else "adbench", 0.1, vae=[(0.3, 9.0)], dif=[(0.35, 9.0)])
        for i in range(4)
    ]
    _write_runs(tmp_path / "deep", deep)
    return ["--runs", str(tmp_path / "runs"), "--deep-runs", str(tmp_path / "deep")]


def test_the_help_describes_the_study_and_the_deep_runs(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        ls.main(["--help"])
    text = capsys.readouterr().out
    lines = [" ".join(line.split()) for line in text.splitlines()]
    assert "runs of the neural detectors, same problems" in lines
    assert any(line.startswith("Pooled summary of the labelled-pool benchmark") for line in lines)


def test_the_runs_folder_is_required_and_the_output_folder_may_already_exist(tmp_path):
    argv = _both(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    assert ls.main([*argv, "--output", str(out)]) == 0
    assert ls.main([*argv, "--output", str(out)]) == 0
    with pytest.raises(SystemExit) as stop:
        ls.main(["--output", str(out)])
    assert stop.value.code == 2


def test_each_pooled_table_is_stored_in_split_orientation(tmp_path):
    out = tmp_path / "out"
    ls.main([*_both(tmp_path), "--output", str(out)])
    results = json.loads((out / "labelled_results.json").read_text())
    for table in (
        results["pr_auc"],
        results["roc_auc"],
        results["deep"]["pr_auc"],
        results["deep"]["roc_auc"],
    ):
        assert set(table) == {"index", "columns", "data"}
        assert table["columns"] == ["median", "lo", "hi"]
        assert len(table["data"]) == len(table["index"])
    assert results["roc_auc"]["data"] != results["pr_auc"]["data"]
    assert results["deep"]["roc_auc"]["data"] != results["deep"]["pr_auc"]["data"]


def test_the_results_file_is_complete_after_the_neural_section_and_has_its_final_name(tmp_path):
    out = tmp_path / "out"
    ls.main([*_both(tmp_path), "--output", str(out)])
    assert sorted(p.name for p in out.iterdir()) == ["labelled_results.json", "labelled_results.md"]
    assert "median_rank_all" in json.loads((out / "labelled_results.json").read_text())


def test_the_closing_sentence_lists_the_methods_from_the_best_rank_to_the_worst_with_commas(
    tmp_path,
):
    out = tmp_path / "out"
    ls.main([*_both(tmp_path), "--output", str(out)])
    results = json.loads((out / "labelled_results.json").read_text())
    last = (out / "labelled_results.md").read_text().splitlines()[-1]
    ordered = sorted(results["median_rank_all"].items(), key=lambda item: item[1])
    assert last == "Median rank over all methods: " + ", ".join(f"{m} {v:.1f}" for m, v in ordered)
