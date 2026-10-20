"""One normalisation policy for every pooled dataset.

Steps, in this order and for every set: drop constant and mostly-missing columns, encode
categorical columns (one-hot up to a cap, otherwise drop), remove duplicate rows and rows whose
duplicates disagree on the label, split 70/15/15 stratified with a seed, then impute with the
training median and standardise with the training mean and standard deviation. Every decision is
counted in a report so that no set is changed silently.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

MAX_MISSING_SHARE = 0.5
CATEGORY_CAP = 20
MIN_CLASS_COUNT = 3  # needed so that train, validation and test each hold one anomaly
OCSVM_MAX_TRAIN, LOF_MAX_TRAIN = 20_000, 50_000  # from the cost study exponents, set before use


class NormaliseError(Exception):
    """The set cannot be split under the protocol."""


def clean(
    frame: pd.DataFrame, labels, category_cap: int = CATEGORY_CAP
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    frame = frame.reset_index(drop=True)
    y = np.asarray(labels).astype(int)
    report: dict[str, Any] = {
        "rows_in": len(frame),
        "dropped_constant": [],
        "dropped_missing": [],
        "dropped_high_cardinality": [],
        "encoded": [],
    }
    pieces = []
    for name in frame.columns:
        col = frame[name]
        if col.isna().mean() > MAX_MISSING_SHARE:
            report["dropped_missing"].append(name)
        elif col.dropna().nunique() <= 1:
            report["dropped_constant"].append(name)
        elif pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_bool_dtype(col):
            pieces.append(col.astype(float).rename(name))
        elif col.nunique() > category_cap:
            report["dropped_high_cardinality"].append(name)
        else:
            report["encoded"].append(name)
            pieces.append(pd.get_dummies(col.astype(str), prefix=str(name), dtype=float))
    if not pieces:
        raise NormaliseError("no usable feature left")
    table = pd.concat(pieces, axis=1)
    keys = pd.util.hash_pandas_object(table.fillna(np.inf), index=False)
    conflicting = pd.Series(y).groupby(keys.to_numpy()).transform("nunique").to_numpy() > 1
    report["conflicting_rows_removed"] = int(conflicting.sum())
    keep = ~conflicting
    first = ~pd.Series(keys.to_numpy()).duplicated().to_numpy()
    report["duplicates_removed"] = int((keep & ~first).sum())
    keep &= first
    report["rows_out"] = int(keep.sum())
    report["features_out"] = table.shape[1]
    return table.to_numpy()[keep], y[keep], report


def split(x: np.ndarray, y, seed: int) -> dict[str, np.ndarray]:
    x, y = np.asarray(x, dtype=float), np.asarray(y).astype(int)
    if min(y.sum(), len(y) - y.sum()) < MIN_CLASS_COUNT:
        raise NormaliseError(f"too few anomalies to split ({int(y.sum())})")
    idx = np.arange(len(y))
    train, rest = train_test_split(idx, train_size=0.70, stratify=y, random_state=seed)
    val, test = train_test_split(rest, train_size=0.5, stratify=y[rest], random_state=seed)
    median = np.nanmedian(x[train], axis=0)

    def fill(a: np.ndarray) -> np.ndarray:
        return np.where(np.isnan(a), median, a)

    filled = fill(x[train])
    mean, scale = filled.mean(axis=0), filled.std(axis=0)
    scale = np.where(scale == 0, 1.0, scale)
    out: dict[str, np.ndarray] = {"mean": mean, "scale": scale, "idx_train": train}
    for name, rows in (("train", train), ("val", val), ("test", test)):
        out[f"x_{name}"] = (fill(x[rows]) - mean) / scale
        out[f"y_{name}"] = y[rows]
    return out


def skipped_detectors(n_train: int) -> list[str]:
    """Quadratic detectors skipped on large training sets; the skip is recorded, never silent."""
    return [
        name
        for name, limit in (("lof", LOF_MAX_TRAIN), ("ocsvm", OCSVM_MAX_TRAIN))
        if n_train > limit
    ]
