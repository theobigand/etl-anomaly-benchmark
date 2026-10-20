"""Read a UCI table as a carrier (features only) or as a labelled anomaly set by a fixed rule.

The rule is set before any detector runs: the rarest class is the anomaly class (at least 20
rows), every other class is normal; when the anomaly class holds more than 10 percent of the
rows it is downsampled to 10 percent with seed 0, and the natural rate is recorded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MIN_ANOMALIES = 20
TARGET_RATE = 0.10
SEED = 0


class NoLabels(Exception):
    """The set can serve as a carrier but not as a labelled anomaly set."""


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def split_columns(frame: pd.DataFrame, meta: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    targets = [c for c in meta.get("target_col") or [] if c in frame.columns]
    roles = {v["name"]: v.get("role") for v in meta.get("variables") or []}
    drop = set(targets) | {c for c, role in roles.items() if role in {"ID", "Other"}}
    features = frame[[c for c in frame.columns if c not in drop]]
    target = frame[targets[0]] if len(targets) == 1 else pd.Series(np.nan, index=frame.index)
    return features, target


def derive_labels(
    frame: pd.DataFrame, meta: dict[str, Any]
) -> tuple[pd.DataFrame, np.ndarray, dict[str, Any]]:
    if "Classification" not in (meta.get("tasks") or []):
        raise NoLabels("not a classification task")
    features, target = split_columns(frame, meta)
    known = target.notna().to_numpy()
    features, target = features[known].reset_index(drop=True), target[known].reset_index(drop=True)
    counts = target.astype(str).value_counts()
    if len(counts) < 2:
        raise NoLabels("fewer than 2 classes")
    rare = str(counts.index[-1])
    if counts.iloc[-1] < MIN_ANOMALIES:
        raise NoLabels(f"fewer than {MIN_ANOMALIES} rows in the rarest class")
    is_rare = (target.astype(str) == rare).to_numpy()
    natural = float(is_rare.mean())
    info: dict[str, Any] = {
        "anomaly_class": rare,
        "classes": int(len(counts)),
        "natural_rate": natural,
        "kind": "native_rare",
    }
    keep = np.ones(len(target), dtype=bool)
    if natural > TARGET_RATE:
        n_normal = int((~is_rare).sum())
        k = round(n_normal * TARGET_RATE / (1 - TARGET_RATE))
        chosen = np.random.default_rng(SEED).choice(np.flatnonzero(is_rare), k, replace=False)
        keep = ~is_rare
        keep[chosen] = True
        info["kind"] = "downsampled"
    labels = is_rare[keep].astype(int)
    info.update(rows=int(keep.sum()), anomalies=int(labels.sum()))
    return features[keep].reset_index(drop=True), labels, info
