import pandas as pd
import pytest

from etl_benchmark.datasets import ANOMALY_COLUMN, DATASETS, DatasetSpec
from etl_benchmark.registry import DETECTOR_NAMES


def test_registry_specs_are_well_formed():
    for key, spec in DATASETS.items():
        assert spec.name == key
        assert spec.positive_value in (0, 1)
        assert set(spec.detector_names) <= set(DETECTOR_NAMES)


def test_features_drops_label_and_anomaly_columns(tmp_path):
    csv = tmp_path / "toy.csv"
    pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "y": [0, 1, 0]}).to_csv(csv, index=False)
    spec = DatasetSpec(name="toy", csv=csv, label_column="y", positive_value=1)

    df = spec.load()
    assert ANOMALY_COLUMN in df.columns
    assert list(df[ANOMALY_COLUMN]) == [0, 1, 0]
    assert list(spec.features(df).columns) == ["a", "b"]


@pytest.mark.real
def test_water_quality_loads_when_present():
    spec = DATASETS["water_quality"]
    if not spec.csv.exists():
        pytest.skip("water_quality.csv not downloaded")

    df = spec.load()
    assert ANOMALY_COLUMN in df.columns
    assert df[ANOMALY_COLUMN].isin((0, 1)).all()
    assert 0.3 < df[ANOMALY_COLUMN].mean() < 0.8  # "not potable" is the common class
    assert "Potability" not in spec.features(df).columns


@pytest.mark.real
def test_cardio_is_the_imbalanced_dataset():
    spec = DATASETS["cardio"]
    if not spec.csv.exists():
        pytest.skip("cardio.csv not downloaded (run experiments/fetch_cardio.py)")

    df = spec.load()
    assert df[ANOMALY_COLUMN].isin((0, 1)).all()
    assert 0.03 < df[ANOMALY_COLUMN].mean() < 0.20  # genuinely rare
    assert "label" not in spec.features(df).columns
    assert spec.features(df).shape[1] == 21
