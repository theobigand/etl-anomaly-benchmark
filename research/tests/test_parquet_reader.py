"""Exact tests of the bounded Parquet reader (schema, projection, row groups, limits)."""

import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parquet_reader as pr  # noqa: E402


@pytest.fixture
def table_file(tmp_path):
    when = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    table = pa.table(
        {
            "id": pa.array(range(10), type=pa.int32()),
            "when": pa.array(when.to_pydatetime(), type=pa.timestamp("ns", tz="UTC")),
            "value": pa.array([float(i) / 2 for i in range(10)], type=pa.float64()),
            "label": pa.array([f"r{i}" for i in range(10)], type=pa.string()),
        }
    )
    path = tmp_path / "t.parquet"
    pq.write_table(table, path, row_group_size=4)
    return path


def test_inspection_reads_metadata_only_and_reports_schema_and_row_groups(table_file):
    meta = pr.inspect(table_file)
    assert meta["rows"] == 10 and meta["row_groups"] == 3
    assert meta["row_group_rows"] == [4, 4, 2]
    assert meta["columns"] == [
        {"name": "id", "type": "int32"},
        {"name": "when", "type": "timestamp[ns, tz=UTC]"},
        {"name": "value", "type": "double"},
        {"name": "label", "type": "string"},
    ]
    assert meta["bytes"] == table_file.stat().st_size


def test_reading_projects_columns_and_preserves_types_and_timestamps(table_file):
    frame, record = pr.read_sample(table_file, columns=["when", "id"], max_rows=100)
    assert list(frame.columns) == ["when", "id"]
    assert str(frame["id"].dtype) == "int32" and str(frame["when"].dtype) == "datetime64[ns, UTC]"
    assert frame["when"].iloc[3] == pd.Timestamp("2024-01-01 03:00", tz="UTC")
    assert record == {
        "columns": ["when", "id"],
        "row_groups": [0, 1, 2],
        "rows_read": 10,
        "rows_kept": 10,
        "stride": 1,
        "max_rows": 100,
        "truncated": False,
        "source_rows": 10,
        "source_row_groups": 3,
    }


def test_row_groups_are_selected_in_the_requested_order_and_only_those_are_read(table_file):
    frame, record = pr.read_sample(table_file, columns=["id"], row_groups=[2, 0], max_rows=100)
    assert frame["id"].tolist() == [8, 9, 0, 1, 2, 3]
    assert record["row_groups"] == [2, 0] and record["rows_read"] == 6 and not record["truncated"]


def test_the_row_limit_stops_reading_exactly_and_marks_the_sample_truncated(table_file):
    frame, record = pr.read_sample(table_file, columns=["id"], max_rows=5, batch_rows=2)
    assert frame["id"].tolist() == [0, 1, 2, 3, 4]
    assert record["truncated"] is True and record["rows_kept"] == 5 and record["rows_read"] == 6


def test_a_stride_keeps_every_kth_row_by_global_position_whatever_the_batch_size(table_file):
    a, rec = pr.read_sample(table_file, columns=["id"], max_rows=100, stride=3, batch_rows=2)
    b, _ = pr.read_sample(table_file, columns=["id"], max_rows=100, stride=3, batch_rows=7)
    assert a["id"].tolist() == [0, 3, 6, 9] == b["id"].tolist()
    assert rec["stride"] == 3 and rec["rows_kept"] == 4 and rec["rows_read"] == 10
    again, _ = pr.read_sample(table_file, columns=["id"], max_rows=100, stride=3, batch_rows=2)
    pd.testing.assert_frame_equal(a, again)


def test_the_stride_counts_from_the_first_selected_row_group(table_file):
    frame, _ = pr.read_sample(table_file, columns=["id"], row_groups=[1], max_rows=100, stride=2)
    assert frame["id"].tolist() == [4, 6]


def test_invalid_requests_are_refused_explicitly(table_file):
    with pytest.raises(pr.ParquetError, match="column 'nope'"):
        pr.read_sample(table_file, columns=["nope"], max_rows=5)
    with pytest.raises(pr.ParquetError, match="row group 3"):
        pr.read_sample(table_file, columns=["id"], row_groups=[3], max_rows=5)
    with pytest.raises(pr.ParquetError, match="row group -1"):
        pr.read_sample(table_file, columns=["id"], row_groups=[-1], max_rows=5)
    for bad in ({"max_rows": 0}, {"stride": 0}, {"batch_rows": 0}):
        with pytest.raises(pr.ParquetError, match="positive"):
            pr.read_sample(table_file, columns=["id"], **{"max_rows": 5, **bad})


def test_the_memory_limit_is_checked_per_batch(table_file):
    with pytest.raises(pr.ParquetError, match="larger than 10 bytes"):
        pr.read_sample(
            table_file, columns=["label"], max_rows=100, batch_rows=4, max_batch_bytes=10
        )
    frame, _ = pr.read_sample(
        table_file, columns=["id"], max_rows=100, batch_rows=4, max_batch_bytes=10_000
    )
    assert len(frame) == 10


def test_a_file_larger_than_the_limit_is_refused_before_it_is_opened(table_file):
    size = table_file.stat().st_size
    with pytest.raises(pr.ParquetError, match=f"larger than {size - 1} bytes"):
        pr.inspect(table_file, max_file_bytes=size - 1)
    assert pr.inspect(table_file, max_file_bytes=size)["rows"] == 10


def test_malformed_truncated_and_missing_files_raise_the_module_error(tmp_path, table_file):
    junk = tmp_path / "junk.parquet"
    junk.write_bytes(b"this is not a parquet file at all")
    with pytest.raises(pr.ParquetError, match="not a readable Parquet file"):
        pr.inspect(junk)
    cut = tmp_path / "cut.parquet"
    cut.write_bytes(table_file.read_bytes()[:-20])  # an incomplete download loses the footer
    with pytest.raises(pr.ParquetError, match="not a readable Parquet file"):
        pr.read_sample(cut, columns=["id"], max_rows=5)
    with pytest.raises(pr.ParquetError, match="cannot read"):
        pr.inspect(tmp_path / "absent.parquet")


def test_row_group_statistics_expose_the_time_range_of_each_group(table_file):
    ranges = pr.row_group_ranges(table_file, "id")
    assert ranges == [(0, 3), (4, 7), (8, 9)]
    assert pr.row_group_ranges(table_file, "label") == [("r0", "r3"), ("r4", "r7"), ("r8", "r9")]
    with pytest.raises(pr.ParquetError, match="column 'zzz'"):
        pr.row_group_ranges(table_file, "zzz")
