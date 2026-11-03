"""Training-fitted preparation for explicitly frozen pool partitions.

The historical normalise.clean/split path is unchanged. This version accepts
features only and never selects rows or learns a vocabulary from evaluation data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PARTITIONS = ("train", "validation", "test")
CATEGORY_CAP = 20
MAX_MISSING_SHARE = 0.5


def validate_partitions(partitions: dict, rows: int) -> None:
    """Require a complete ordered assignment; never invent or repair positions."""
    if set(partitions) != set(PARTITIONS):
        raise ValueError("partitions must contain train, validation and test")
    positions = []
    for name in PARTITIONS:
        values = partitions[name]
        if not isinstance(values, list) or not values:
            raise ValueError("each partition must be a nonempty position list")
        if any(type(value) is not int or not 0 <= value < rows for value in values):
            raise ValueError("partition positions must be in-range integers")
        positions.extend(values)
    if len(positions) != rows or len(set(positions)) != rows:
        raise ValueError("partitions must cover every row exactly once without overlap")


def _categorical(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    return np.column_stack(
        [frame[name].astype("string").to_numpy(dtype=object, na_value=np.nan) for name in columns]
    )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    if not columns:
        return np.empty((len(frame), 0))
    values = frame[columns].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("numeric feature values must be finite or missing")
    return values


def prepare_frozen(frame: pd.DataFrame, partitions: dict) -> dict:
    """Fit on supplied training positions; transform every fold without labels.

    Unknown categories have an all-zero one-hot block before training-fitted
    scaling. No row is dropped, including duplicates within a partition.
    """
    if (
        not len(frame.columns)
        or not frame.columns.is_unique
        or any(not isinstance(name, str) for name in frame.columns)
    ):
        raise ValueError("feature columns must be nonempty, unique strings")
    validate_partitions(partitions, len(frame))
    membership = np.empty(len(frame), dtype=int)
    for fold, name in enumerate(PARTITIONS):
        membership[partitions[name]] = fold
    keys = pd.util.hash_pandas_object(frame, index=False).to_numpy()
    groups = pd.DataFrame({"key": keys, "fold": membership}).groupby("key")["fold"].nunique()
    if (groups > 1).any():
        raise ValueError("duplicate feature rows cross partitions")

    train = frame.iloc[partitions["train"]]
    numeric, categorical = [], []
    dropped = {"missing": [], "constant": [], "cardinality": []}
    for name in train:
        column = train[name]
        if column.isna().mean() > MAX_MISSING_SHARE:
            dropped["missing"].append(name)
        elif column.nunique() <= 1:
            dropped["constant"].append(name)
        else:
            converted = pd.to_numeric(column, errors="coerce")
            if (
                not pd.api.types.is_bool_dtype(converted)
                and converted[column.notna()].notna().all()
            ):
                numeric.append(name)
            elif column.nunique() > CATEGORY_CAP:
                dropped["cardinality"].append(name)
            else:
                categorical.append(name)
    if not numeric and not categorical:
        raise ValueError("no usable training feature remains")

    values = _numeric(train, numeric)
    medians = np.nanmedian(values, axis=0) if numeric else np.empty(0)
    encoder = None
    if categorical:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        encoder.fit(_categorical(train, categorical))

    def matrix(part: pd.DataFrame) -> np.ndarray:
        values = _numeric(part, numeric)
        filled = np.where(np.isnan(values), medians, values)
        if encoder is not None:
            filled = np.column_stack([filled, encoder.transform(_categorical(part, categorical))])
        return filled

    scaler = StandardScaler().fit(matrix(train))
    columns = [f"f{i}" for i in range(scaler.n_features_in_)]
    report = {
        "input_columns": frame.columns.tolist(),
        "numeric_columns": numeric,
        "categorical_columns": categorical,
        "dropped": dropped,
        "medians": medians.tolist(),
        "categories": (
            [
                [None if pd.isna(value) else str(value) for value in group]
                for group in encoder.categories_
            ]
            if encoder is not None
            else []
        ),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "output_columns": columns,
        "category_cap": CATEGORY_CAP,
        "max_missing_share": MAX_MISSING_SHARE,
        "unknown_categories": "zero one-hot block before scaling",
    }
    result = {"fit": report}
    for name in PARTITIONS:
        positions = partitions[name]
        transformed = scaler.transform(matrix(frame.iloc[positions]))
        if not np.isfinite(transformed).all():
            raise ValueError("transformed features must be finite")
        result[name] = pd.DataFrame(transformed, index=positions, columns=columns)
    return result
