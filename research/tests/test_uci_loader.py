"""Turn a UCI table into a carrier (features only) or a labelled anomaly set by a fixed rule."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dataset_registry as dr  # noqa: E402
import uci_loader as ul  # noqa: E402


def _meta(**over):
    base = {
        "uci_id": 7,
        "target_col": ["y"],
        "tasks": ["Classification"],
        "variables": [
            {"name": "id", "role": "ID", "type": "Integer"},
            {"name": "a", "role": "Feature", "type": "Continuous"},
            {"name": "b", "role": "Feature", "type": "Categorical"},
            {"name": "y", "role": "Target", "type": "Binary"},
        ],
    }
    return {**base, **over}


def _table(n=1000, rare=40):
    y = np.zeros(n, dtype=int)
    y[:rare] = 1
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {"id": range(n), "a": rng.normal(size=n), "b": rng.choice(list("xyz"), n), "y": y}
    )


def test_features_exclude_identifiers_and_the_target():
    features, target = ul.split_columns(_table(), _meta())
    assert list(features.columns) == ["a", "b"] and list(target) == list(_table()["y"])


def test_a_rare_class_is_the_anomaly_and_is_kept_as_is_below_ten_percent():
    features, labels, info = ul.derive_labels(_table(1000, 40), _meta())
    assert labels.sum() == 40 and len(labels) == 1000
    assert info["kind"] == "native_rare" and info["anomaly_class"] == "1"


def test_a_frequent_minority_is_downsampled_to_ten_percent_with_a_fixed_seed():
    features, labels, info = ul.derive_labels(_table(1000, 400), _meta())
    assert info["kind"] == "downsampled" and info["natural_rate"] == pytest.approx(0.4)
    assert labels.sum() == round(600 / 9) and len(labels) == 600 + round(600 / 9)
    again = ul.derive_labels(_table(1000, 400), _meta())[1]
    assert np.array_equal(labels, again)


def test_multiclass_uses_the_rarest_class_against_the_rest():
    df = _table(1000, 0)
    df["y"] = ["p"] * 600 + ["q"] * 380 + ["r"] * 20
    _, labels, info = ul.derive_labels(df, _meta())
    assert info["anomaly_class"] == "r" and info["classes"] == 3 and labels.sum() == 20


def test_sets_without_a_usable_label_are_carriers_only():
    with pytest.raises(ul.NoLabels, match="fewer than 20"):
        ul.derive_labels(_table(1000, 5), _meta())
    with pytest.raises(ul.NoLabels, match="classification"):
        ul.derive_labels(_table(), _meta(tasks=["Regression"]))


def test_download_is_limited_to_the_uci_host_and_returns_the_csv(tmp_path):
    csv = _table(50, 5).to_csv(index=False).encode()
    path, digest = dr.fetch_unpinned(
        "https://archive.ics.uci.edu/static/public/7/data.csv",
        tmp_path / "7.csv",
        opener=lambda url, limit: csv,
    )
    assert len(digest) == 64 and ul.read_table(path).shape == (50, 4)
    with pytest.raises(dr.RegistryError):
        dr.fetch_unpinned("https://example.org/data.csv", tmp_path / "x", opener=lambda u, n: csv)


def test_pool_row_records_roles_digest_and_the_normalisation_report(tmp_path):
    import build_pool as bp

    meta = _meta(uci_id=7, name="Toy", licence="CC BY 4.0")
    path = tmp_path / "7.csv"
    _table(1000, 400).to_csv(path, index=False)
    row = bp.pool_row(meta, path, "ab" * 32)
    assert row["roles"] == ["carrier", "labelled"] and row["sha256"] == "ab" * 32
    assert row["label"]["kind"] == "downsampled" and row["carrier"]["features_out"] == 4
    carrier_only = bp.pool_row(_meta(tasks=["Regression"]), path, "cd" * 32)
    assert carrier_only["roles"] == ["carrier"]
    assert "classification" in carrier_only["label_refused"]
