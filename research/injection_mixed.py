"""Mixed-schema carriers for the typed injection (issue 77): categorical and numeric columns.

``injection.py`` needs four continuous columns and 3,000 rows. Tables of mostly categorical,
binary or small content cannot carry it, so this module builds a carrier from every usable
column of the feature table and defines the faults that exist for each column kind. The rules are
written in verification/typed_mixed.md before any detector result of this protocol exists.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from injection import NotEligible

MIN_ROWS, MAX_ROWS, MIN_COLUMNS = 500, 20_000, 3
NUM_MIN_DISTINCT = 10  # fewer distinct values: the column is a code, not a measurement
MAX_MISSING_SHARE = 0.05  # columns with more missing values are dropped, then complete cases kept
ID_LIKE_LEVELS = 50  # a text column with more levels and mostly unique values is an identifier


def column_kinds(frame: pd.DataFrame) -> dict[str, str]:
    """``num`` for measurements, ``cat`` for codes and text."""
    kinds = {}
    for name in frame.columns:
        col = frame[name]
        numeric = pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_bool_dtype(col)
        kinds[name] = "num" if numeric and col.nunique() >= NUM_MIN_DISTINCT else "cat"
    return kinds


def prepare_mixed(
    frame: pd.DataFrame, seed: int, cap: int = MAX_ROWS
) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any]]:
    """Clean carrier, column kinds and a report of every removal."""
    report: dict[str, Any] = {"rows_in": len(frame), "columns_in": list(frame.columns)}
    dropped: dict[str, str] = {}
    keep = []
    for name in frame.columns:
        col = frame[name]
        if col.isna().all():
            dropped[name] = "all missing"
        elif col.isna().mean() > MAX_MISSING_SHARE:
            dropped[name] = f"{col.isna().mean():.0%} missing"
        elif col.nunique() < 2:
            dropped[name] = "constant"
        elif (
            not pd.api.types.is_numeric_dtype(col)
            and col.nunique() > ID_LIKE_LEVELS
            and col.nunique() > 0.5 * len(col)
        ):
            dropped[name] = "identifier-like text"
        else:
            keep.append(name)
    report["columns_dropped"] = dropped
    table = frame[keep]
    complete = table.dropna()
    report["rows_incomplete_dropped"] = len(table) - len(complete)
    unique = complete.drop_duplicates()
    report["duplicates_dropped"] = len(complete) - len(unique)
    if len(keep) < MIN_COLUMNS:
        raise NotEligible(f"only {len(keep)} usable columns")
    if len(unique) < MIN_ROWS:
        raise NotEligible(f"only {len(unique)} rows after cleaning")
    if len(unique) > cap:
        unique = unique.sample(n=cap, random_state=seed)
    unique = unique.reset_index(drop=True)
    kinds = column_kinds(unique)
    for name, kind in kinds.items():
        unique[name] = unique[name].astype(float) if kind == "num" else unique[name].astype(str)
    report.update(rows_out=len(unique), columns=list(unique.columns), kinds=kinds)
    return unique, kinds, report
