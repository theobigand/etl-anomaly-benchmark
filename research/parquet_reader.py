"""Bounded reading of Parquet files for the acquisition pipeline.

Only metadata is read to inspect a file. Rows are read row group by row group in record batches of
a fixed size under explicit limits (file size, rows kept, bytes per batch), and every sample states
the columns, row groups, stride and truncation it used, so a sample is never mistaken for the
whole file. A stride keeps every k-th row by global position among the selected row groups, which
is deterministic whatever the batch size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

MAX_FILE_BYTES = 2 * 1024**3
MAX_BATCH_BYTES = 256 * 1024**2
BATCH_ROWS = 65_536


class ParquetError(Exception):
    """A Parquet file is unreadable, too large, or a request does not match it."""


def _open(path: Path, max_file_bytes: int) -> pq.ParquetFile:
    try:
        size = Path(path).stat().st_size
    except OSError as error:
        raise ParquetError(f"cannot read {path} ({error})") from error
    if size > max_file_bytes:
        raise ParquetError(f"{path}: larger than {max_file_bytes} bytes")
    try:
        return pq.ParquetFile(path)
    except (pa.ArrowInvalid, pa.ArrowIOError, OSError) as error:
        raise ParquetError(f"{path}: not a readable Parquet file ({error})") from error


def inspect(path: Path, max_file_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    """Row count, row groups and column types from the footer, without reading any row."""
    handle = _open(path, max_file_bytes)
    meta = handle.metadata
    return {
        "bytes": Path(path).stat().st_size,
        "rows": meta.num_rows,
        "row_groups": meta.num_row_groups,
        "row_group_rows": [meta.row_group(i).num_rows for i in range(meta.num_row_groups)],
        "columns": [{"name": f.name, "type": str(f.type)} for f in handle.schema_arrow],
    }


def row_group_ranges(
    path: Path, column: str, max_file_bytes: int = MAX_FILE_BYTES
) -> list[tuple[Any, Any]]:
    """Minimum and maximum of a column in each row group, from the footer statistics."""
    handle = _open(path, max_file_bytes)
    names = handle.schema_arrow.names
    if column not in names:
        raise ParquetError(f"column {column!r} not in the file")
    index = names.index(column)
    out = []
    for i in range(handle.metadata.num_row_groups):
        stats = handle.metadata.row_group(i).column(index).statistics
        if stats is None or not stats.has_min_max:
            raise ParquetError(f"row group {i}: no statistics for column {column!r}")
        out.append((stats.min, stats.max))
    return out


def read_sample(
    path: Path,
    columns: list[str],
    max_rows: int,
    row_groups: list[int] | None = None,
    stride: int = 1,
    batch_rows: int = BATCH_ROWS,
    max_batch_bytes: int = MAX_BATCH_BYTES,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Selected columns of the selected row groups, at most ``max_rows`` rows, and what was done."""
    if min(max_rows, stride, batch_rows) < 1:
        raise ParquetError("max_rows, stride and batch_rows must be positive")
    handle = _open(path, max_file_bytes)
    total_groups = handle.metadata.num_row_groups
    names = handle.schema_arrow.names
    for name in columns:
        if name not in names:
            raise ParquetError(f"column {name!r} not in the file")
    chosen = list(range(total_groups)) if row_groups is None else list(row_groups)
    for group in chosen:
        if not 0 <= group < total_groups:
            raise ParquetError(f"row group {group} not in the file ({total_groups} groups)")
    pieces: list[pd.DataFrame] = []
    position = kept = 0
    truncated = False
    try:
        for batch in handle.iter_batches(batch_size=batch_rows, row_groups=chosen, columns=columns):
            if batch.nbytes > max_batch_bytes:
                raise ParquetError(f"a batch is larger than {max_batch_bytes} bytes")
            frame = batch.to_pandas()
            first = (-position) % stride  # offset of the next kept row inside this batch
            frame = frame.iloc[first::stride]
            position += batch.num_rows
            room = max_rows - kept
            if len(frame) > room:
                frame, truncated = frame.iloc[:room], True
            pieces.append(frame)
            kept += len(frame)
            if truncated or kept >= max_rows:
                truncated = truncated or position < _selected_rows(handle, chosen)
                break
    except (pa.ArrowInvalid, pa.ArrowIOError, OSError) as error:
        raise ParquetError(f"{path}: not a readable Parquet file ({error})") from error
    out = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=columns)
    return out, {
        "columns": list(columns),
        "row_groups": chosen,
        "rows_read": position,
        "rows_kept": kept,
        "stride": stride,
        "max_rows": max_rows,
        "truncated": truncated,
        "source_rows": handle.metadata.num_rows,
        "source_row_groups": total_groups,
    }


def _selected_rows(handle: pq.ParquetFile, groups: list[int]) -> int:
    return sum(handle.metadata.row_group(g).num_rows for g in groups)
