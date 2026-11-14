"""The typed summary command: help, required options, stored shapes and a null rank correlation."""

import json
import sys
from pathlib import Path

import pytest
from test_typed_summary import _matrix, _pattern
from test_typed_summary_contracts import _write_run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_summary as ts  # noqa: E402


def _folders(tmp_path, names=("one", "two")):
    folders = []
    for i, name in enumerate(names):
        folder = tmp_path / name
        folder.mkdir()
        _write_run(folder, f"d{i}", _pattern(), list("abcd"), {"iqr": 0.25, "zscore": 0.0})
        folders.append(str(folder))
    return folders


def test_several_run_folders_are_read_together_and_each_option_is_required(tmp_path, capsys):
    one, two = _folders(tmp_path)
    out = tmp_path / "out"
    assert ts.main(["--runs", one, two, "--output", str(out)]) == 0
    assert capsys.readouterr().out == "2 datasets\n"
    for argv in (["--output", str(out)], ["--runs", one]):
        with pytest.raises(SystemExit) as stop:
            ts.main(argv)
        assert stop.value.code == 2


def test_the_output_folder_may_already_exist_and_holds_exactly_the_two_result_files(tmp_path):
    one, two = _folders(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    ts.main(["--runs", one, two, "--output", str(out)])
    ts.main(["--runs", one, two, "--output", str(out)])
    assert sorted(p.name for p in out.iterdir()) == ["typed_results.json", "typed_results.md"]


def test_the_pooled_tables_are_stored_in_split_orientation_and_the_table_rows_close_with_a_bar(
    tmp_path,
):
    one, two = _folders(tmp_path)
    out = tmp_path / "out"
    ts.main(["--runs", one, two, "--output", str(out)])
    results = json.loads((out / "typed_results.json").read_text())
    for key in ("median", "low", "high"):
        assert set(results[key]) == {"index", "columns", "data"}
    lines = (out / "typed_results.md").read_text().splitlines()
    assert all(line.endswith(" |") for line in lines[2:3] + lines[4:-5])


def test_the_help_describes_the_summary(capsys):
    with pytest.raises(SystemExit):
        ts.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "Pooled summary of the per-dataset typed heatmaps" in text
    assert "--runs RUNS [RUNS ...] --output OUTPUT" in text


def _by_columns(recalls, columns):
    matrices = {
        f"d{i}": _matrix(isolation_forest__univariate_outlier=recall)
        for i, recall in enumerate(recalls)
    }
    return matrices, {f"d{i}": count for i, count in enumerate(columns)}


def test_h5_does_not_hold_for_no_rank_correlation_nor_for_a_positive_one():
    flat, columns = _by_columns([0.1, 0.5, 0.4, 0.3, 0.2], [1, 2, 3, 4, 5])
    out = ts.hypotheses(flat, columns)["H5"]
    assert out["rho"] == pytest.approx(0.0) and out["holds"] is False
    mild, columns = _by_columns([0.2, 0.1, 0.4, 0.3, 0.5], [1, 2, 3, 4, 5])
    out = ts.hypotheses(mild, columns)["H5"]
    assert 0 < out["rho"] < 1 and out["holds"] is False
