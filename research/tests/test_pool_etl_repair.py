"""ETL readers: stray header lines, sparse cells, all-missing and categorical columns (issue 79)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_etl as pe  # noqa: E402


def _text(**cols):
    return pd.DataFrame({k: pd.Series(v, dtype="string") for k, v in cols.items()})


def test_repeated_header_lines_are_removed_and_the_column_becomes_numeric():
    df = _text(id=["1", "id", "2"], temp=["20.5", "temp", "21.0"])
    out, report = pe.repair_frame(df)
    assert list(out["temp"]) == [20.5, 21.0]
    assert report["header_rows_removed"] == 1


def test_a_row_of_missing_values_is_data_not_a_header_line():
    df = _text(a=["x", None, "y"], b=["p", None, "q"])
    out, report = pe.repair_frame(df)
    assert len(out) == 3 and report["header_rows_removed"] == 0


def test_sparse_index_value_cells_are_parsed_to_numbers():
    df = _text(f1=["1:15.5", "1:-2.0", "1:3"], cls=["1;10.0", "1;20.0", "2;5.0"])
    out, report = pe.repair_frame(df)
    assert list(out["f1"]) == [15.5, -2.0, 3.0]
    assert report["sparse_columns"] == ["f1"]


def test_all_missing_columns_are_dropped_and_reported():
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [np.nan, np.nan]})
    out, report = pe.repair_frame(df)
    assert list(out.columns) == ["a"] and report["all_missing_dropped"] == ["b"]


def test_categorical_only_tables_get_numeric_features_without_using_the_label():
    df = _text(shape=["a", "b", "a", "c"], colour=["r", "r", "g", "b"])
    out, report = pe.repair_frame(df)
    assert out.shape[0] == 4 and all(pd.api.types.is_numeric_dtype(t) for t in out.dtypes)
    assert report["encoded"] == ["colour", "shape"]


def test_numeric_tables_pass_through_unchanged():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [3, 2, 1]})
    out, report = pe.repair_frame(df)
    pd.testing.assert_frame_equal(out, df)
    assert not any(report.values())


def test_datetime_columns_become_epoch_seconds():
    df = _text(date=["2015-02-04 17:51:00", "2015-02-04 17:52:00"])
    out, report = pe.repair_frame(df)
    assert out["date"].diff().iloc[1] == 60.0 and report["datetime_columns"] == ["date"]
