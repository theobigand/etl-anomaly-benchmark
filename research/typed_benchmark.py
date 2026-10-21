"""Per-type recall of every detector on a carrier with typed injection (issue #65).

Same protocol as the synthetic benchmark: identity-grouped 70/15/15 split stratified on the group
type, detectors fitted on train with the train anomaly prevalence as contamination, recall per type
on test against the clean rows only.
"""

from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")

import injection as inj  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_score, recall_score  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import TemporalDriftDetector  # noqa: E402
from etl_benchmark.registry import ALL_NAMES, get_detector  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402

DETECTORS = [n for n in ALL_NAMES if n != "drift"] + ["drift"]


def split(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    groups = (
        df.groupby("group_id", sort=False)["anomaly_type"]
        .agg(lambda types: "duplicate" if "duplicate" in types.values else types.iloc[0])
        .reset_index(name="stratum")
    )
    parts = stratified_split(groups, "stratum", config.SPLIT_RATIOS, seed)
    return tuple(df[df["group_id"].isin(p["group_id"])].reset_index(drop=True) for p in parts)


def _build(name: str, contamination: float, cols: list[str]):
    if name == "drift":
        return TemporalDriftDetector(time_column="t", columns=cols)
    return get_detector(name, contamination)


def _per_type(flags: pd.Series, types: pd.Series) -> tuple[dict, dict]:
    clean = types == "clean"
    recall, precision = {}, {}
    for name in inj.ANOMALY_TYPES:
        is_type = types == name
        if not is_type.any():
            recall[name] = precision[name] = np.nan
            continue
        keep = is_type | clean
        recall[name] = recall_score(is_type[keep].astype(int), flags[keep])
        precision[name] = precision_score(is_type[keep].astype(int), flags[keep], zero_division=0)
    return recall, precision


def evaluate(df: pd.DataFrame, cols: list[str], seed: int, names: list[str] | None = None):
    names = names or DETECTORS
    unknown = [n for n in names if n not in ALL_NAMES]
    if unknown:
        raise ValueError(f"unknown detector names: {unknown}")
    train, _val, test = split(df, seed)
    contamination = float(train["anomaly"].mean())
    features = [*cols, "t"]
    recall_rows, precision_rows = [], []
    for name in [*names, "transform_dedup"]:
        if name == "transform_dedup":
            flags = test.duplicated(subset=features, keep=False)
        else:
            flags = detect(
                test[features], _build(name, contamination, cols), fit_df=train[features]
            ).flags
        r, p = _per_type(pd.Series(np.asarray(flags), index=test.index), test["anomaly_type"])
        recall_rows.append({"method": name, **r})
        precision_rows.append({"method": name, **p})
    return {
        "recall": pd.DataFrame(recall_rows).set_index("method"),
        "precision": pd.DataFrame(precision_rows).set_index("method"),
    }
