"""Merged tables and figures of the complete-registry study."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_registry_summary as fs  # noqa: E402


def _split(frame):
    return json.loads(frame.to_json(orient="split"))


def _matrix(names, value):
    return pd.DataFrame(value, index=names, columns=fs.TYPES)


def test_rows_follow_the_registry_order_with_unknown_names_last():
    frame = _matrix(["lunar", "zscore", "mystery", "ecod"], 0.5)
    assert list(fs.ordered(frame).index) == ["zscore", "ecod", "lunar", "mystery"]


def test_a_carrier_gets_the_neural_rows_of_the_same_dataset_and_not_a_second_dedup_row(tmp_path):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir()
    deep.mkdir()
    base = _matrix(["zscore", "transform_dedup"], 0.2)
    extra = _matrix(["vae", "transform_dedup"], 0.7)
    (classical / "1.json").write_text(json.dumps({"name": "A", "recall_mean": _split(base)}))
    (deep / "1.json").write_text(json.dumps({"name": "A", "recall_mean": _split(extra)}))
    merged = fs.merged_typed(classical, deep)
    assert list(merged["A"].index) == ["zscore", "vae", "transform_dedup"]
    assert merged["A"].loc["vae", "duplicate"] == 0.7


def test_a_carrier_without_neural_rows_keeps_its_classical_rows(tmp_path):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir()
    deep.mkdir()
    base = _matrix(["zscore"], 0.2)
    (classical / "1.json").write_text(json.dumps({"name": "A", "recall_mean": _split(base)}))
    assert list(fs.merged_typed(classical, deep)["A"].index) == ["zscore"]


def test_tables_print_values_and_optional_intervals():
    frame = _matrix(["zscore"], 0.25)
    assert "| zscore | 0.25 |" in fs.table_md(frame)
    text = fs.table_md(frame, frame - 0.1, frame + 0.1)
    assert "0.25 [0.15, 0.35]" in text


def test_the_deep_mean_averages_the_seeds(tmp_path):
    for seed, value in ((1, 0.2), (2, 0.6)):
        recall = _split(_matrix(["vae"], value))
        (tmp_path / f"synthetic_seed_{seed}.json").write_text(json.dumps({"recall": recall}))
    assert fs.deep_mean(tmp_path, "synthetic_seed_*.json").loc["vae", "duplicate"] == pytest.approx(
        0.4
    )


def test_the_real_table_joins_the_classical_means_with_the_neural_runs(tmp_path):
    cols = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"]
    csv = pd.DataFrame({f"{c}_mean": [0.5] for c in cols}, index=["zscore"])
    csv.to_csv(tmp_path / "b.csv")
    ok = dict.fromkeys(cols, 0.3)
    runs = [
        {"methods": {"vae": ok, "lunar": {"error": "x"}}},
        {"methods": {"vae": ok, "lunar": {"error": "y"}}},
    ]
    (tmp_path / "r.json").write_text(json.dumps({"runs": runs}))
    table = fs.real_table(tmp_path / "b.csv", tmp_path / "r.json")
    assert list(table.index) == ["zscore", "vae"] and table.loc["vae", "f1"] == pytest.approx(0.3)


def test_a_figure_is_written(tmp_path):
    fs.figure(_matrix(["zscore", "ecod"], 0.4), "title", tmp_path / "f.png")
    assert (tmp_path / "f.png").stat().st_size > 0
    assert not np.isnan(0.4)
