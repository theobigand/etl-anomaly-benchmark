import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

import run_benchmark  # noqa: E402
from run_benchmark import METRIC_COLUMNS, evaluate, run, to_markdown  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import ANOMALY_COLUMN, DatasetSpec  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402


def _toy_spec(tmp_path: Path) -> DatasetSpec:
    rng = np.random.default_rng(0)
    n = 800
    x = rng.normal(size=(n, 5))
    y = np.zeros(n, dtype=int)
    y[:64] = 1  # 8% positives
    x[y == 1] += rng.normal(4.0, 1.0, size=(64, 5))  # make them separable-ish
    df = pd.DataFrame(x, columns=[f"f{i}" for i in range(5)])
    df["y"] = y
    csv = tmp_path / "toy.csv"
    df.sample(frac=1.0, random_state=1).to_csv(csv, index=False)
    return DatasetSpec(
        name="toy",
        csv=csv,
        label_column="y",
        positive_value=1,
        detector_names=["zscore", "iqr", "isolation_forest"],
    )


def test_run_returns_mean_and_std_over_seeds(tmp_path):
    spec = _toy_spec(tmp_path)
    mean, std = run(spec, seeds=[0, 1, 2])

    assert list(mean.index) == spec.detector_names
    assert set(METRIC_COLUMNS) <= set(mean.columns)
    for col in ("precision", "recall", "f1", "roc_auc", "pr_auc"):
        assert mean[col].between(-1e-9, 1.0 + 1e-9).all()
    assert (std.to_numpy() >= 0).all()


def test_every_requested_detector_appears_in_the_results(tmp_path):
    spec = _toy_spec(tmp_path)
    per_split = evaluate(spec, spec.load(), 0, None)
    assert per_split.index.tolist() == spec.detector_names
    assert not per_split.isna().any().any()


def test_isolation_forest_separates_the_planted_positives(tmp_path):
    spec = _toy_spec(tmp_path)
    mean, _std = run(spec, seeds=[0, 1])

    # the positives are shifted by ~4 sigma, so the ranking metric should be strong
    assert mean.loc["isolation_forest", "roc_auc"] > 0.9


def test_to_markdown_has_one_row_per_detector(tmp_path):
    spec = _toy_spec(tmp_path)
    mean, std = run(spec, seeds=[0])
    md = to_markdown(mean, std)

    for name in spec.detector_names:
        assert f"| {name} |" in md
    assert md.count(" ± ") == len(spec.detector_names) * len(METRIC_COLUMNS)


def test_one_seed_does_not_claim_zero_uncertainty(tmp_path):
    spec = _toy_spec(tmp_path)
    _mean, std = run(spec, seeds=[0])
    assert std["precision"].isna().all()
    assert "n/a" in to_markdown(_mean, std)


def test_two_seed_mean_and_sample_standard_deviation(tmp_path):
    spec = _toy_spec(tmp_path)
    frame = spec.load()
    a = evaluate(spec, frame, 0, None).loc["zscore", "recall"]
    b = evaluate(spec, frame, 1, None).loc["zscore", "recall"]
    mean, std = run(spec, seeds=[0, 1])
    assert mean.loc["zscore", "recall"] == (a + b) / 2
    assert std.loc["zscore", "recall"] == pytest.approx(abs(a - b) / np.sqrt(2))


def test_calibration_uses_train_only_and_ignores_fit_sample(tmp_path, monkeypatch):
    spec = _toy_spec(tmp_path)
    frame = spec.load()
    observed = []
    build = run_benchmark.all_detectors

    def capture(*, ml_contamination, names):
        observed.append(ml_contamination)
        return build(ml_contamination=ml_contamination, names=["zscore"])

    monkeypatch.setattr(run_benchmark, "all_detectors", capture)
    train, _, _ = stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 0)
    expected = train[ANOMALY_COLUMN].mean()
    evaluate(spec, frame, 0, 20)
    assert observed[-1] == pytest.approx(expected)
    evaluate(spec, frame, 0, 20, calibration="fixed", fixed_contamination=0.02)
    assert observed[-1] == 0.02


def test_test_labels_cannot_change_detector_calibration(tmp_path, monkeypatch):
    spec = _toy_spec(tmp_path)
    frame = spec.load()
    train, val, test = stratified_split(frame, ANOMALY_COLUMN, config.SPLIT_RATIOS, 0)
    labels = test[ANOMALY_COLUMN].copy()
    observed = []
    build = run_benchmark.all_detectors

    def capture(*, ml_contamination, names):
        observed.append(ml_contamination)
        return build(ml_contamination=ml_contamination, names=["zscore"])

    def fixed_partitions(_frame, _label, _ratios, _seed):
        return train.copy(), val.copy(), test.assign(**{ANOMALY_COLUMN: labels})

    monkeypatch.setattr(run_benchmark, "all_detectors", capture)
    monkeypatch.setattr(run_benchmark, "stratified_split", fixed_partitions)
    evaluate(spec, frame, 0, None)
    labels = 1 - labels
    evaluate(spec, frame, 0, None)
    assert observed == [pytest.approx(train[ANOMALY_COLUMN].mean())] * 2
