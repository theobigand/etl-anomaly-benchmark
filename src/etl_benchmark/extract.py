"""Extract stage: load raw data into a DataFrame."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}. See data/README.md for download instructions."
        )
    return pd.read_csv(path)
