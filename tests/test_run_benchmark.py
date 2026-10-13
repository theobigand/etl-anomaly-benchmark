import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_benchmark import METRIC_COLUMNS, evaluate, run, to_markdown  # noqa: E402

from etl_benchmark.datasets import DatasetSpec  # noqa: E402


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
