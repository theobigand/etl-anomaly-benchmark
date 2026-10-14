import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_curves  # noqa: E402

from etl_benchmark.datasets import DatasetSpec  # noqa: E402


def test_curves_use_identity_disjoint_synthetic_split(monkeypatch):
    seen = []
    original = run_curves._split_synthetic

    def observe(frame, seed):
        parts = original(frame, seed)
        seen.append(parts)
        return parts

    monkeypatch.setattr(run_curves, "_split_synthetic", observe)
    run_curves._split_synth(42)
    assert len(seen) == 1
    train, val, test = seen[0]
    assert set(train.customer_id).isdisjoint(val.customer_id)
    assert set(train.customer_id).isdisjoint(test.customer_id)


def test_real_curves_fit_on_train_and_score_only_held_out_rows(tmp_path, monkeypatch):
    csv = tmp_path / "toy.csv"
    pd.DataFrame({"measure": np.arange(200, dtype=float), "Class": [0] * 180 + [1] * 20}).to_csv(
        csv, index=False
    )
    monkeypatch.setitem(
        run_curves.DATASETS,
        "toy",
        DatasetSpec("toy", csv, "Class", 1, detector_names=["zscore"]),
    )
    train, test, y, contamination, names, prevalence = run_curves._split_real("toy", 3)
    assert train.columns.tolist() == test.columns.tolist() == ["measure"]
    assert len(train) == 140 and len(test) == len(y) == 30
    assert contamination == prevalence == 0.1
    assert names == ["zscore"]
    result = run_curves.scores_for("toy", 3)
    assert len(result["scores"]["zscore"]) == len(y)
    assert result["base_rate"] == 0.1


def test_contamination_sweep_skips_only_absent_real_dataset(tmp_path, monkeypatch):
    csv = tmp_path / "toy.csv"
    pd.DataFrame({"measure": np.arange(200, dtype=float), "Class": [0] * 180 + [1] * 20}).to_csv(
        csv, index=False
    )
    monkeypatch.setitem(run_curves.DATASETS, "toy", DatasetSpec("toy", csv, "Class", 1))
    monkeypatch.setitem(
        run_curves.DATASETS,
        "missing",
        DatasetSpec("missing", tmp_path / "absent.csv", "Class", 1),
    )
    sweep = run_curves.contamination_sweep(3, datasets=["missing", "toy"])
    assert set(sweep.dataset) == {"toy"}
    assert sweep.is_prevalence.sum() == 2  # 0.10 is also a grid value
    assert sweep["precision"].between(0, 1).all()


def test_curves_command_rejects_all_datasets_absent(tmp_path, monkeypatch):
    monkeypatch.setitem(
        run_curves.DATASETS,
        "credit_card",
        DatasetSpec("credit_card", tmp_path / "absent.csv", "Class", 1),
    )
    figure = tmp_path / "curves.png"
    output = tmp_path / "results"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_curves",
            "--datasets",
            "credit_card",
            "--figure",
            str(figure),
            "--results-dir",
            str(output),
        ],
    )
    with pytest.raises(RuntimeError, match="no datasets available"):
        run_curves.main()
    assert not figure.exists()
    assert not output.exists()
