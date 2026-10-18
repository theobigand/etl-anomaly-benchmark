"""Load stage: persist results to disk."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl_benchmark.atomic import atomic_path


def write_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(path) as partial:
        df.to_csv(partial, index=False)
    return path
