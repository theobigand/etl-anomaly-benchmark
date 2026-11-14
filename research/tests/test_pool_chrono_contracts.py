"""Exact times, thresholds, feature rules and the command of the chronological pool study."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_chrono as pc  # noqa: E402


def test_month_only_times_are_utc_first_of_the_month_plus_the_row_order_within_it():
    frame = pd.DataFrame({"Month": ["Mar", "Feb", "Mar", "Feb", "Feb"]})
    times = pc.read_times(frame, 468)
    assert str(times.dt.tz) == "UTC"
    expected = ["2017-03-01 00:00", "2017-02-01 00:00", "2017-03-01 00:01",
                "2017-02-01 00:01", "2017-02-01 00:02"]  # fmt: skip
    assert [t.strftime("%Y-%m-%d %H:%M") for t in times] == expected


def test_only_the_month_table_uses_the_month_rule_and_unreadable_values_become_missing():
    other = pd.DataFrame({"date": ["2015-02-04 17:51:00", "not a time"]})
    times = pc.read_times(other, 357)
    assert times.iloc[0] == pd.Timestamp("2015-02-04 17:51:00", tz="UTC")
    assert pd.isna(times.iloc[1])
    clock = pd.DataFrame({"Date": ["2017/12/22", "x"], "Time": ["10:49:41", "y"]})
    joined = pc.read_times(clock, 864)
    assert joined.iloc[0] == pd.Timestamp("2017-12-22 10:49:41", tz="UTC")
    assert pd.isna(joined.iloc[1])


def _hours(n):
    return pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))


def test_the_anomaly_count_is_taken_in_time_order_from_the_last_fifteen_percent():
    y = np.zeros(100, dtype=int)
    y[85:] = 1
    assert pc.eligible(y, _hours(100)) == (
        False,
        "15 anomalies in the test partition (at least 20)",
    )
    for positives, expected in ((20, True), (19, False)):
        y = np.zeros(200, dtype=int)
        y[200 - positives :] = 1
        assert pc.eligible(y, _hours(200))[0] is expected
    y = np.zeros(200, dtype=int)
    y[170:] = 1
    order = np.random.default_rng(1).permutation(200)
    assert pc.eligible(y[order], _hours(200)[order].reset_index(drop=True)) == (True, "")
    reversed_times = _hours(200)[::-1].reset_index(drop=True)
    assert pc.eligible(y, reversed_times)[0] is False


def test_feature_rules_at_their_boundaries():
    cap = pc.CATEGORY_CAP
    frame = pd.DataFrame(
        {
            "two": [0.0, 1.0] * 10,
            "single": [5.0] * 20,
            "single_with_gaps": [5.0, None] * 10,
            "flag": [True, False] * 10,
            "ints": list(range(20)),
        }
    )
    out = pc.to_features(frame)
    assert out["two"].dtype == np.float64 and out["ints"].dtype == np.float64
    assert "single" not in out and "single_with_gaps" not in out
    assert {"flag_True", "flag_False"} <= set(out.columns)
    assert "flag" not in out
    assert out["flag_True"].dtype == np.float64
    wide = pd.DataFrame({"w": [f"v{i}" for i in range(cap + 1)] * 2, "n": range(2 * (cap + 1))})
    assert [c for c in pc.to_features(wide).columns] == ["n"]
    exact = pd.DataFrame({"w": [f"v{i}" for i in range(cap)] * 2, "n": range(2 * cap)})
    assert len([c for c in pc.to_features(exact).columns if c.startswith("w_")]) == cap
    assert pc.to_features(exact).shape[0] == 2 * cap


def test_a_column_whose_number_of_distinct_values_is_two_is_kept_not_dropped():
    out = pc.to_features(pd.DataFrame({"a": ["x", "y"] * 5, "b": [1.0, 2.0] * 5}))
    assert set(out.columns) == {"a_x", "a_y", "b"}
    assert pc.to_features(
        pd.DataFrame({"k": [1.0] * 4, "b": [1.0, 2.0, 3.0, 4.0]})
    ).columns.tolist() == ["b"]


def test_methods_are_split_by_the_training_size_taken_as_seventy_percent_of_the_rows(monkeypatch):
    seen = []
    monkeypatch.setattr(pc, "methods_for", lambda n, wanted: seen.append(n) or (list(wanted), []))
    monkeypatch.setattr(pc.td, "run_frame", lambda x, y, t, methods: {"methods": methods})
    y = np.zeros(1000, dtype=int)
    y[900:] = 1
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    result = pc.run_dataset(pd.DataFrame({"a": range(1000)}), y, times, methods=["zscore"])
    assert seen == [700]
    assert result == {"methods": ["zscore"], "skipped": []}


def test_the_command_writes_one_file_per_dataset_and_reports_each_outcome(
    tmp_path, monkeypatch, capsys
):
    registry = tmp_path / "verification" / "evidence" / "dataset_registry"
    registry.mkdir(parents=True)
    kept = [
        {"uci_id": 357, "name": "Occupancy Detection "},
        {"uci_id": 864, "name": "Room Occupancy Estimation"},
        {"uci_id": 468, "name": "Online Shoppers"},
    ]
    (registry / "uci_curated.json").write_text(json.dumps({"kept": kept}))
    monkeypatch.setattr(pc, "ROOT", tmp_path)
    data = (pd.DataFrame({"a": [1.0]}), np.array([0]), pd.Series([pd.Timestamp("2020", tz="UTC")]))
    loads = []
    monkeypatch.setattr(pc.td, "credit_card", lambda: data)
    monkeypatch.setattr(pc.td, "bank_marketing", lambda path: loads.append(("bank", path)) or data)
    monkeypatch.setattr(
        pc,
        "load_pool_dataset",
        lambda meta, path, uci_id: loads.append((uci_id, meta["uci_id"], path)) or (*data, 7),
    )
    monkeypatch.setattr(
        pc,
        "run_dataset",
        lambda x, y, times: {"excluded": "few"} if len(x) == 1 and len(loads) % 2 else {"ok": 1},
    )
    output = tmp_path / "out" / "nested"
    assert pc.main(["--output", str(output)]) == 0
    names = sorted(p.name for p in output.iterdir())
    assert names == [
        "bank_marketing.json", "credit_card.json", "occupancy_detection.json",
        "online_shoppers.json", "room_occupancy_estimation.json",
    ]  # fmt: skip
    assert ("bank", tmp_path / "data" / "pool" / "222.csv") in loads
    assert (357, 357, tmp_path / "data" / "pool" / "357.csv") in loads
    text = (output / "occupancy_detection.json").read_text()
    document = json.loads(text)
    assert document["rows_without_a_readable_time"] == 7
    assert text == json.dumps(document, indent=1, sort_keys=True) + "\n"
    assert "rows_without_a_readable_time" not in json.loads(
        (output / "credit_card.json").read_text()
    )
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == [
        "credit_card", "bank_marketing", "occupancy_detection",
        "room_occupancy_estimation", "online_shoppers",
    ]  # fmt: skip


def test_the_only_option_limits_the_run_and_the_output_directory_is_required(
    tmp_path, monkeypatch, capsys
):
    registry = tmp_path / "verification" / "evidence" / "dataset_registry"
    registry.mkdir(parents=True)
    kept = [{"uci_id": u, "name": f"n{u}"} for u in (357, 864, 468)]
    (registry / "uci_curated.json").write_text(json.dumps({"kept": kept}))
    monkeypatch.setattr(pc, "ROOT", tmp_path)
    data = (pd.DataFrame({"a": [1.0]}), np.array([0]), pd.Series([pd.Timestamp("2020", tz="UTC")]))
    monkeypatch.setattr(pc.td, "credit_card", lambda: data)
    monkeypatch.setattr(pc, "run_dataset", lambda x, y, times: {})
    assert pc.main(["--output", str(tmp_path / "o"), "--only", "credit_card"]) == 0
    assert [p.name for p in (tmp_path / "o").iterdir()] == ["credit_card.json"]
    assert capsys.readouterr().out == "credit_card ok\n"
    with pytest.raises(SystemExit) as stop:
        pc.main([])
    assert stop.value.code == 2
