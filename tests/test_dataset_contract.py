import pandas as pd
import pytest

from etl_benchmark.datasets import DATASETS, DatasetSpec

pytestmark = pytest.mark.protocol


@pytest.mark.parametrize(
    ("name", "positive"),
    [("credit_card", 1), ("cardio", 1), ("water_quality", 0)],
)
def test_real_dataset_positive_class(name, positive, tmp_path):
    original = DATASETS[name]
    csv = tmp_path / "small.csv"
    pd.DataFrame({"measure": [1.0, 2.0], original.label_column: [0, 1]}).to_csv(csv, index=False)
    spec = DatasetSpec(name, csv, original.label_column, positive)
    frame = spec.load()
    assert frame.is_anomaly.tolist() == ([0, 1] if positive == 1 else [1, 0])


def test_missing_labels_are_not_silently_normalized(tmp_path):
    csv = tmp_path / "missing.csv"
    pd.DataFrame({"measure": [1.0, 2.0], "Class": [0, None]}).to_csv(csv, index=False)
    with pytest.raises(ValueError, match="label"):
        DatasetSpec("toy", csv, "Class", 1).load()


@pytest.mark.parametrize(
    ("columns", "message"),
    [
        ({"measure": [1.0, 2.0]}, "missing label column"),
        ({"measure": [1.0, 2.0], "Class": [0, 2]}, "only 0 and 1"),
    ],
)
def test_dataset_rejects_missing_or_nonbinary_ground_truth(tmp_path, columns, message):
    csv = tmp_path / "invalid.csv"
    pd.DataFrame(columns).to_csv(csv, index=False)
    with pytest.raises(ValueError, match=message):
        DatasetSpec("toy", csv, "Class", 1).load()


def test_features_exclude_every_ground_truth_and_identity_column(tmp_path):
    spec = DatasetSpec("toy", tmp_path / "irrelevant.csv", "Class", 1)
    frame = pd.DataFrame(
        {
            "measure": [1.0],
            "Class": [1],
            "is_anomaly": [1],
            "anomaly": [True],
            "anomaly_type": ["outlier"],
            "customer_id": [42],
        }
    )
    assert spec.features(frame).columns.tolist() == ["measure"]
