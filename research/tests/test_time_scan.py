"""Time candidates among the pool tables: which columns, how they were read, what is reported."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import time_scan as ts  # noqa: E402


def _dates(n=12, prefix="2020-01-"):
    return [f"{prefix}{d + 1:02d}" for d in range(n)]


def test_a_date_text_column_is_read_as_a_datetime_with_its_distinct_count():
    frame = pd.DataFrame({"sign_date": _dates(), "other": [f"x{i}" for i in range(12)]})
    assert ts.candidate_columns(frame) == [
        {"column": "sign_date", "kind": "datetime", "distinct": 12}
    ]


def test_a_numeric_column_counts_only_when_its_name_says_time():
    frame = pd.DataFrame({"hour_of_day": np.arange(12), "price": np.arange(12.0)})
    assert ts.candidate_columns(frame) == [
        {"column": "hour_of_day", "kind": "numeric", "distinct": 12}
    ]


def test_columns_with_fewer_than_ten_distinct_values_are_never_candidates():
    nine = pd.DataFrame({"date": _dates(9) * 2, "month": [1, 2, 3, 4, 5, 6, 7, 8, 9] * 2})
    assert ts.candidate_columns(nine) == []
    ten = pd.DataFrame({"date": _dates(10), "month": list(range(10))})
    assert [c["column"] for c in ts.candidate_columns(ten)] == ["date", "month"]


def test_a_text_column_must_parse_for_at_least_ninety_five_percent_and_ten_distinct_dates():
    ok = _dates(19) + ["not a date"]
    assert [c["distinct"] for c in ts.candidate_columns(pd.DataFrame({"date": ok}))] == [19]
    bad = _dates(18) + ["no", "never"]
    assert ts.candidate_columns(pd.DataFrame({"date": bad})) == []
    words = pd.DataFrame({"date": [f"word{i}" for i in range(20)]})
    assert ts.candidate_columns(words) == []
    assert ts.MIN_PARSED == 0.95


def test_a_non_text_column_whose_name_is_not_about_time_is_skipped_without_being_read():
    frame = pd.DataFrame({"price": np.arange(20.0), "weekday_code": np.arange(20)})
    assert [c["column"] for c in ts.candidate_columns(frame)] == ["weekday_code"]


def test_the_name_rule_ignores_case_and_matches_inside_the_name():
    frame = pd.DataFrame(
        {"TimeStamp_utc": np.arange(12), "DAYS": np.arange(12), "label": np.arange(12)}
    )
    assert [c["column"] for c in ts.candidate_columns(frame)] == ["TimeStamp_utc", "DAYS"]


def _pool(tmp_path, tables, curated=None):
    registry = tmp_path / "registry"
    registry.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    curated_doc = {"kept": [{"uci_id": uid, **(curated or {}).get(uid, {})} for uid in tables]}
    pool_doc = {
        "rows": [
            {"uci_id": uid, "name": f"name{uid}", "roles": roles}
            for uid, (_frame, roles) in tables.items()
        ]
    }
    (registry / "curated.json").write_text(json.dumps(curated_doc))
    (registry / "pool.json").write_text(json.dumps(pool_doc))
    for uid, (frame, _roles) in tables.items():
        if frame is not None:
            frame.to_csv(data / f"{uid}.csv", index=False)
    return registry / "curated.json", registry / "pool.json", data


def test_the_scan_reports_each_table_with_its_label_status_row_count_and_candidates(tmp_path):
    frame = pd.DataFrame({"date": _dates(), "v": range(12)})
    paths = _pool(tmp_path, {1: (frame, ["labelled"]), 2: (frame, ["unlabelled"])})
    out = ts.scan(*paths)
    assert [r["uci_id"] for r in out] == [1, 2]
    assert out[0] == {
        "uci_id": 1, "name": "name1", "labelled": True, "rows": 12,
        "candidates": [{"column": "date", "kind": "datetime", "distinct": 12}],
    }  # fmt: skip
    assert out[1]["labelled"] is False


def test_a_declared_date_variable_is_added_once_and_only_when_the_column_exists(tmp_path):
    frame = pd.DataFrame({"stamp": [f"s{i}" for i in range(12)], "date": _dates()})
    variables = [
        {"name": "stamp", "type": "Date"},
        {"name": "date", "type": "Date"},
        {"name": "ghost", "type": "Date"},
        {"name": "v", "type": "Integer"},
    ]
    paths = _pool(tmp_path, {1: (frame, ["labelled"])}, curated={1: {"variables": variables}})
    [row] = ts.scan(*paths)
    assert row["candidates"] == [
        {"column": "date", "kind": "datetime", "distinct": 12},
        {"column": "stamp", "kind": "declared", "distinct": 12},
    ]


def test_a_table_without_declared_variables_still_scans(tmp_path):
    paths = _pool(
        tmp_path,
        {1: (pd.DataFrame({"date": _dates()}), ["labelled"])},
        curated={1: {"variables": None}},
    )
    assert len(ts.scan(*paths)[0]["candidates"]) == 1


def test_an_unreadable_table_is_recorded_with_its_error_and_the_scan_goes_on(tmp_path):
    good = pd.DataFrame({"date": _dates()})
    paths = _pool(tmp_path, {1: (None, ["labelled"]), 2: (good, ["labelled"])})
    out = ts.scan(*paths)
    assert out[0]["uci_id"] == 1 and set(out[0]) == {"uci_id", "error"}
    assert "FileNotFoundError" in out[0]["error"]
    assert out[1]["uci_id"] == 2 and out[1]["rows"] == 12


def test_a_text_column_of_dates_is_found_even_when_its_name_does_not_say_time():
    frame = pd.DataFrame({"created": _dates(), "other": [f"x{i}" for i in range(12)]})
    assert ts.candidate_columns(frame) == [
        {"column": "created", "kind": "datetime", "distinct": 12}
    ]


def test_a_text_column_is_found_whatever_dtype_the_installed_pandas_gives_text():
    for dtype in ("object", "string"):
        frame = pd.DataFrame({"created": pd.Series(_dates(), dtype=dtype)})
        assert [c["column"] for c in ts.candidate_columns(frame)] == ["created"], dtype
