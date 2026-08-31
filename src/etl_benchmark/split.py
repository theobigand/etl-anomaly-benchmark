"""Stratified train / validation / test split.

The detectors are unsupervised: the label is never used to fit them. The
split still matters for an honest evaluation, so that a detector is fitted
on one part of the stream and scored on rows it has not seen. ``train`` is
used for fitting (and for reading off the anomaly prevalence that sets the
ML contamination), ``test`` carries the reported metrics, and ``val`` is
held back for hyper-parameter work.
"""

from __future__ import annotations

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
    if len(ratios) != 3 or abs(sum(ratios) - 1.0) > 1e-6 or any(r <= 0 for r in ratios):
        raise ValueError(f"ratios must be three positive fractions summing to 1, got {ratios}")

    strat = df[stratify_on] if isinstance(stratify_on, str) else stratify_on
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
