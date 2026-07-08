"""Transform stage: light cleaning before quality checks."""

from __future__ import annotations

import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates().reset_index(drop=True)
