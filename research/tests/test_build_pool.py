"""What build_pool records for each curated UCI set, and how download failures are kept."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_pool as bp  # noqa: E402
import dataset_registry as dr  # noqa: E402
import normalise as nm  # noqa: E402
import uci_loader as ul  # noqa: E402


def _meta(**over):
    base = {
        "uci_id": 7,
        "name": "Toy",
        "licence": "CC BY 4.0",
        "data_url": "https://archive.ics.uci.edu/static/public/7/data.csv",
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


@pytest.fixture
def csv(tmp_path):
    path = tmp_path / "7.csv"
    _table().to_csv(path, index=False)
    return path


def test_a_row_names_the_set_its_licence_its_source_and_its_digest(csv):
    row = bp.pool_row(_meta(), csv, "ab" * 32)
    assert row["uci_id"] == 7 and row["name"] == "Toy" and row["licence"] == "CC BY 4.0"
    assert row["url"] == "https://archive.ics.uci.edu/static/public/7/data.csv"
    assert row["sha256"] == "ab" * 32 and row["roles"] == ["carrier", "labelled"]


def test_a_row_carries_the_normalisation_report_of_the_features_and_of_the_labelled_set(csv):
    row = bp.pool_row(_meta(), csv, "00" * 32)
    features, _ = ul.split_columns(ul.read_table(csv), _meta())
    _, _, carrier = nm.clean(features, [0] * len(features))
    assert row["carrier"] == carrier
    _, labels, info = ul.derive_labels(ul.read_table(csv), _meta())
    assert row["label"]["anomalies"] == int(labels.sum()) == 40
    assert row["label"]["kind"] == "native_rare" and row["label"]["rows_out"] == 1000
    assert "label_refused" not in row and "carrier_refused" not in row


def test_a_set_without_usable_features_is_refused_as_a_carrier_with_the_reason(csv):
    only_ids = _meta(variables=[{"name": c, "role": "ID"} for c in ("id", "a", "b")])
    row = bp.pool_row(only_ids, csv, "11" * 32)
    assert row["carrier_refused"] == "no usable feature left"
    assert "carrier" not in row and "carrier" not in row["roles"]


def test_a_set_that_is_not_a_classification_task_keeps_the_carrier_role_and_says_why(csv):
    row = bp.pool_row(_meta(tasks=["Regression"]), csv, "22" * 32)
    assert row["roles"] == ["carrier"] and row["label_refused"] == "not a classification task"
    assert "label" not in row and "skipped_detectors" not in row


def test_detectors_too_costly_for_the_training_share_are_recorded_as_skipped(csv, monkeypatch):
    # 70% of 1000 rows is 700: LOF (600) is skipped, One-Class SVM (800) and KNN (900) are not
    monkeypatch.setattr(nm, "LOF_MAX_TRAIN", 600)
    monkeypatch.setattr(nm, "OCSVM_MAX_TRAIN", 800)
    monkeypatch.setattr(nm, "KNN_MAX_TRAIN", 900)
    assert bp.pool_row(_meta(), csv, "33" * 32)["skipped_detectors"] == ["lof"]
    monkeypatch.setattr(nm, "LOF_MAX_TRAIN", 1000)
    assert bp.pool_row(_meta(), csv, "33" * 32)["skipped_detectors"] == []


def _curated(tmp_path, kept):
    path = tmp_path / "curated.json"
    path.write_text(json.dumps({"kept": kept}))
    return path


def _run(tmp_path, monkeypatch, kept, fetch):
    sleeps = []
    monkeypatch.setattr(bp.dr, "fetch_unpinned", fetch)
    monkeypatch.setattr(bp.time, "sleep", sleeps.append)
    out = tmp_path / "pool.json"
    code = bp.main(
        [
            "--curated",
            str(_curated(tmp_path, kept)),
            "--destination",
            str(tmp_path / "pool"),
            "--output",
            str(out),
        ]
    )
    return code, out, sleeps


def test_main_records_each_set_keeps_failures_apart_and_pauses_between_downloads(
    tmp_path, monkeypatch, capsys
):
    seen = []

    def fetch(url, path):
        seen.append((url, Path(path)))
        if "bad" in url:
            raise dr.RegistryError("refused host")
        if "slow" in url:
            raise OSError("timeout")
        if "odd" in url:
            raise ValueError("not a csv")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _table().to_csv(path, index=False)
        return Path(path), "cd" * 32

    kept = [
        _meta(uci_id=7),
        _meta(uci_id=8, data_url="https://x/bad.csv"),
        _meta(uci_id=9, data_url="https://x/slow.csv"),
        _meta(uci_id=10, data_url="https://x/odd.csv"),
    ]
    code, out, sleeps = _run(tmp_path, monkeypatch, kept, fetch)
    assert code == 0
    assert capsys.readouterr().out == "1 recorded, 3 failed\n"
    assert [p for _, p in seen] == [tmp_path / "pool" / f"{i}.csv" for i in (7, 8, 9, 10)]
    assert sleeps == [0.3] * 4
    data = json.loads(out.read_text())
    assert [r["uci_id"] for r in data["rows"]] == [7] and data["rows"][0]["sha256"] == "cd" * 32
    assert data["failed"] == [
        {"uci_id": 8, "error": "refused host"},
        {"uci_id": 9, "error": "timeout"},
        {"uci_id": 10, "error": "not a csv"},
    ]
    assert out.read_text() == json.dumps(data, indent=1, sort_keys=True) + "\n"


@pytest.mark.parametrize("missing", ["--curated", "--output"])
def test_main_refuses_to_run_without_the_curated_list_or_the_output_path(tmp_path, missing, capsys):
    args = {"--curated": str(tmp_path / "c.json"), "--output": str(tmp_path / "o.json")}
    del args[missing]
    with pytest.raises(SystemExit) as refused:
        bp.main([x for pair in args.items() for x in pair])
    assert refused.value.code == 2
    assert missing in capsys.readouterr().err


def test_main_describes_itself_and_downloads_into_data_pool_by_default(
    tmp_path, monkeypatch, capsys
):
    with pytest.raises(SystemExit):
        bp.main(["--help"])
    assert "Download the curated UCI sets" in capsys.readouterr().out
    seen = []

    def fetch(url, path):
        seen.append(Path(path))
        raise dr.RegistryError("stop")

    monkeypatch.setattr(bp.dr, "fetch_unpinned", fetch)
    monkeypatch.setattr(bp.time, "sleep", lambda s: None)
    bp.main(["--curated", str(_curated(tmp_path, [_meta()])), "--output", str(tmp_path / "o.json")])
    assert seen == [dr.ROOT / "data" / "pool" / "7.csv"]


def test_the_eligibility_check_splits_with_the_fixed_seed_zero(csv, monkeypatch):
    seeds = []
    real = nm.split

    def spy(x, y, seed):
        seeds.append(seed)
        return real(x, y, seed)

    monkeypatch.setattr(nm, "split", spy)
    bp.pool_row(_meta(), csv, "44" * 32)
    assert seeds == [0]
