"""Splits, scores, figure and sweep of run_curves.py."""

import json
import logging
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, precision_score, recall_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_curves  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DatasetSpec  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import IsolationForestDetector  # noqa: E402
from etl_benchmark.registry import DETECTOR_NAMES, clip_contamination  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import FEATURE_COLUMNS, make_synthetic  # noqa: E402

NAMES = ["zscore", "iqr", "isolation_forest"]


@pytest.fixture
def toy(tmp_path, monkeypatch):
    rng = np.random.default_rng(5)
    frame = pd.DataFrame(rng.normal(size=(500, 3)), columns=["a", "b", "c"])
    frame["Class"] = [1] * 40 + [0] * 460
    frame.loc[frame.Class == 1, "a"] += 4.0
    csv = tmp_path / "toy.csv"
    frame.sample(frac=1, random_state=2).to_csv(csv, index=False)
    spec = DatasetSpec("toy", csv, "Class", 1, detector_names=NAMES)
    monkeypatch.setitem(run_curves.DATASETS, "toy", spec)
    return spec


@pytest.fixture
def captured_figures(monkeypatch):
    figures = []
    original = plt.close

    def keep(fig=None):
        figures.append(fig)
        return original(fig)

    monkeypatch.setattr(plt, "close", keep)
    return figures


def _messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name.endswith("run_curves")]


def test_real_split_returns_features_labels_prevalence_and_detectors(toy):
    train_x, test_x, y, train_rate, names, base = run_curves._split_real("toy", 4)
    frame = toy.load()
    train, _, test = stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 4)
    pd.testing.assert_frame_equal(train_x, toy.features(train))
    pd.testing.assert_frame_equal(test_x, toy.features(test))
    assert y.tolist() == test[ANOMALY_COLUMN].tolist()
    assert train_rate == train[ANOMALY_COLUMN].mean()
    assert names == NAMES
    assert base == frame[ANOMALY_COLUMN].mean() == 0.08


def test_synthetic_split_returns_feature_columns_and_the_full_population_rate(monkeypatch):
    calls = []
    real = run_curves.make_synthetic

    def spy(**kwargs):
        calls.append(kwargs)
        return real(n_rows=300, seed=kwargs["seed"])

    monkeypatch.setattr(run_curves, "make_synthetic", spy)
    train_x, test_x, y, train_rate, names, base = run_curves._split_synth(3, None)
    run_curves._split_synth(4, 300)
    assert calls == [{"seed": 3}, {"seed": 4, "n_rows": 300}]
    frame = make_synthetic(n_rows=300, seed=3)
    train, _, test = run_curves._split_synthetic(frame, 3)
    pd.testing.assert_frame_equal(train_x, train[FEATURE_COLUMNS])
    pd.testing.assert_frame_equal(test_x, test[FEATURE_COLUMNS])
    assert y.tolist() == test["anomaly"].astype(int).tolist() and y.dtype.kind == "i"
    assert train_rate == train["anomaly"].mean() and base == frame["anomaly"].mean()
    assert names == DETECTOR_NAMES


def test_scores_come_from_detectors_fitted_on_train_with_the_train_prevalence(
    toy, monkeypatch, caplog
):
    seen = {}
    real = run_curves.all_detectors

    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(run_curves, "all_detectors", spy)
    with caplog.at_level(logging.INFO):
        out = run_curves.scores_for("toy", 4)
    train_x, test_x, y, rate, _, base = run_curves._split_real("toy", 4)
    assert seen == {"ml_contamination": rate, "names": NAMES}
    assert set(out) == {"y", "base_rate", "scores"}
    assert out["y"].tolist() == y.tolist() and out["base_rate"] == base
    assert list(out["scores"]) == NAMES
    assert all(v.dtype == float and len(v) == len(y) for v in out["scores"].values())
    assert _messages(caplog) == [f"toy: {name} scored" for name in NAMES]


def test_precision_recall_figure_labels_curves_with_their_average_precision(
    tmp_path, captured_figures
):
    rng = np.random.default_rng(1)
    y = np.array([0] * 40 + [1] * 10)
    results = {
        name: {
            "y": y,
            "base_rate": 0.2,
            "scores": {"m1": rng.random(50) + y, "m2": rng.random(50)},
        }
        for name in ("first", "second")
    }
    path = run_curves.render_pr(results, tmp_path / "x" / "y" / "pr.png")
    assert path.is_file()
    fig = captured_figures[-1]
    assert (
        fig._suptitle.get_text() == "Precision-recall curves on the test split (AP in the legend)"
    )
    assert fig.get_size_inches().tolist() == [10.0, 8.0]
    axes = [a for a in fig.axes][:2]
    assert [a.get_title() for a in axes] == ["first", "second"]
    for ax in axes:
        assert ax.get_xlabel() == "recall" and ax.get_ylabel() == "precision"
        assert ax.get_xlim() == (-0.02, 1.02) and ax.get_ylim() == (-0.02, 1.02)
        scores = results[ax.get_title()]["scores"]
        assert [t.get_text() for t in ax.get_legend().get_texts()] == [
            f"{method} ({average_precision_score(y, scores[method]):.2f})"
            for method in ("m1", "m2")
        ]
        dashed = [line for line in ax.get_lines() if line.get_linestyle() == "--"]
        assert len(dashed) == 1 and list(dashed[0].get_ydata()) == [0.2, 0.2]
        assert ax.get_legend()._loc == 1  # upper right


def test_contamination_sweep_covers_the_grid_and_the_train_prevalence(toy):
    sweep = run_curves.contamination_sweep(4, datasets=["toy"])
    assert sweep.columns.tolist() == [
        "dataset",
        "contamination",
        "is_prevalence",
        "precision",
        "recall",
        "flagged_pct",
    ]
    train_x, test_x, y, rate, _, _ = run_curves._split_real("toy", 4)
    grid = [*run_curves.CONTAMINATION_GRID, rate]
    assert sweep.contamination.tolist() == [round(clip_contamination(c), 4) for c in grid]
    assert sweep.is_prevalence.tolist() == [False] * 5 + [True]
    assert set(sweep.dataset) == {"toy"}
    for c, row in zip(grid, sweep.itertuples(), strict=True):
        detector = IsolationForestDetector(contamination=clip_contamination(c))
        flags = detect(test_x, detector, fit_df=train_x).flags
        assert row.precision == pytest.approx(precision_score(y, flags, zero_division=0))
        assert row.recall == pytest.approx(recall_score(y, flags, zero_division=0))
        assert row.flagged_pct == pytest.approx(100.0 * flags.mean())


def test_a_sweep_point_that_flags_nothing_has_zero_precision(toy):
    sweep = run_curves.contamination_sweep(4, datasets=["toy"])
    empty = sweep[sweep.flagged_pct == 0]
    assert (empty.precision == 0.0).all()


def test_main_writes_the_sweep_the_figure_and_the_record(
    toy, tmp_path, monkeypatch, capsys, caplog
):
    out, figure = tmp_path / "r" / "s", tmp_path / "f" / "pr.png"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_curves", "--datasets", "toy", "--seed", "4", "--figure", str(figure)]
        + ["--results-dir", str(out)],
    )
    with caplog.at_level(logging.INFO):
        run_curves.main()
    csv = next(out.glob("contamination_sweep_*.csv"))
    assert re.fullmatch(r"contamination_sweep_\d{8}_\d{6}\.csv", csv.name)
    sweep = run_curves.contamination_sweep(4, datasets=["toy"])
    written = pd.read_csv(csv)
    assert written.columns.tolist() == sweep.columns.tolist()
    pd.testing.assert_frame_equal(written, sweep)
    record = json.loads(next(out.glob("run_curves_*.json")).read_text())
    assert record["experiment"] == "precision_recall_and_contamination"
    assert record["seeds"] == [4] and record["dataset"]["identity"] == "toy"
    assert record["settings"] == {
        "datasets": ["toy"],
        "skipped_datasets": [],
        "synthetic_rows": None,
        "split_ratios": [0.7, 0.15, 0.15],
        "synthetic_split_strategy": "customer_identity_grouped_stratified",
        "real_split_strategy": "stratified",
        "calibration": "train_label_prevalence",
        "contamination_grid": run_curves.CONTAMINATION_GRID,
        "pr_auc_definition": "average_precision",
    }
    assert record["outputs"] == [csv.name, str(figure)]
    printed = capsys.readouterr().out
    assert printed == (
        "\nIsolation Forest, contamination sweep (test split):\n\n"
        + sweep.to_string(index=False)
        + "\n"
    )
    assert _messages(caplog)[-1] == f"figure -> {figure}"
    assert figure.is_file()


def test_main_help_and_defaults(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["run_curves", "--help"])
    with pytest.raises(SystemExit):
        run_curves.main()
    out = " ".join(capsys.readouterr().out.split())
    assert "Precision-recall curves and a contamination-sensitivity table." in out
    assert "synthetic row count for an offline smoke run" in out
    assert "{credit_card,water_quality,cardio,synthetic}" in out or "credit_card" in out
    seen = {}

    def stop(dataset, seed, rows):
        seen.setdefault("calls", []).append((dataset, seed, rows))
        raise FileNotFoundError(dataset)

    monkeypatch.setattr(run_curves, "scores_for", stop)
    monkeypatch.setattr(sys, "argv", ["run_curves"])
    with pytest.raises(RuntimeError, match="^no datasets available for curve evaluation$"):
        run_curves.main()
    assert seen["calls"] == [
        (name, config.RANDOM_SEED, None)
        for name in ("credit_card", "water_quality", "cardio", "synthetic")
    ]
