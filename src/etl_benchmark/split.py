"""Stratified train / validation / test split.

The detectors are unsupervised: the label is never used to fit them. The
split still matters for an honest evaluation, so that a detector is fitted
on one part of the stream and scored on rows it has not seen. ``train`` is
used for fitting (and for reading off the anomaly prevalence that sets the
ML contamination), ``test`` carries the reported metrics, and ``val`` is
held back for hyper-parameter work.
"""

from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from etl_benchmark import config


def stratified_split(
    df: pd.DataFrame,
    stratify_on: str | pd.Series,
    ratios: tuple[float, float, float] = config.SPLIT_RATIOS,
    seed: int = config.RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split ``df`` into train / val / test, keeping the class balance.

    ``stratify_on`` is a column name or an index-aligned Series. ``ratios``
    must be three positive fractions that sum to one. Each returned frame
    has a fresh 0..n-1 index.
    """
    if (
        len(ratios) != 3
        or any(not isfinite(r) or r <= 0 for r in ratios)
        or abs(sum(ratios) - 1.0) > 1e-6
    ):
        raise ValueError(f"ratios must be three positive fractions summing to 1, got {ratios}")

    if not df.index.is_unique:
        raise ValueError("input index must be unique so rows can be aligned")
    if isinstance(stratify_on, str):
        strat = df[stratify_on]
    else:
        if not stratify_on.index.is_unique or set(stratify_on.index) != set(df.index):
            raise ValueError("stratification Series index must match the input index")
        strat = stratify_on.reindex(df.index)
    train_frac, val_frac, test_frac = ratios

    train_df, rest_df = train_test_split(
        df,
        train_size=train_frac,
        random_state=seed,
        stratify=strat,
    )
    rest_strat = strat.loc[rest_df.index]
    val_df, test_df = train_test_split(
        rest_df,
        test_size=test_frac / (val_frac + test_frac),
        random_state=seed,
        stratify=rest_strat,
    )
    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def chronological_split(
    df: pd.DataFrame,
    time_column: str,
    ratios: tuple[float, float, float] = config.SPLIT_RATIOS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by event time, keeping equal timestamps in the same partition."""
    if (
        len(ratios) != 3
        or any(not isfinite(r) or r <= 0 for r in ratios)
        or abs(sum(ratios) - 1.0) > 1e-6
    ):
        raise ValueError("ratios must be three positive fractions summing to 1")
    if time_column not in df:
        raise ValueError(f"missing timestamp column {time_column!r}")
    try:
        times = pd.to_datetime(df[time_column], errors="raise", utc=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    if times.isna().any():
        raise ValueError("missing timestamp")

    positions = np.argsort(times.to_numpy(), kind="stable")
    sorted_times = times.iloc[positions].to_numpy()
    boundaries = np.flatnonzero(sorted_times[1:] != sorted_times[:-1]) + 1
    if len(boundaries) < 2:
        raise ValueError("three distinct timestamp groups are required")

    target_train = len(df) * ratios[0]
    first = int(boundaries[:-1][np.abs(boundaries[:-1] - target_train).argmin()])
    later = boundaries[boundaries > first]
    target_val = len(df) * (ratios[0] + ratios[1])
    second = int(later[np.abs(later - target_val).argmin()])
    ordered = df.iloc[positions]
    return tuple(
        part.reset_index(drop=True)
        for part in (ordered.iloc[:first], ordered.iloc[first:second], ordered.iloc[second:])
    )
