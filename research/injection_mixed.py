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

MIN_ROWS, MAX_ROWS, MIN_COLUMNS = 200, 20_000, 3
NUM_MIN_DISTINCT = 10  # fewer distinct values: the column is a code, not a measurement
MAX_MISSING_SHARE = 0.05  # columns with more missing values are dropped, then complete cases kept


def column_kinds(frame: pd.DataFrame) -> dict[str, str]:
    """``num`` for measurements, ``cat`` for codes and text."""
    kinds = {}
    for name in frame.columns:
        col = frame[name]
        numeric = pd.api.types.is_numeric_dtype(
            col
        )  # a boolean has two values: never a measurement
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
        elif not pd.api.types.is_numeric_dtype(col) and col.nunique() > 0.5 * len(col):
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
        column = unique[name]
        unique[name] = np.asarray(column, dtype=float) if kind == "num" else column.astype(str)
    report.update(rows_out=len(unique), columns=list(unique.columns), kinds=kinds)
    return unique, kinds, report


RATE, SEVERITY, TIER_B_ROWS, TIER_B_K = 0.03, 1.0, 500, 8
ONE_HOT_MAX = 20
MIN_LEVEL_COUNT = 2  # a level seen in fewer training rows counts as unseen
_BASE = pd.Timestamp("2020-01-01")
HOUR = "h"
_SENTINEL, _SCALE = -999.0, 1000.0
# fixed order: the group layout, and hence the partitions, depend on the schema only
TYPE_ORDER = (
    "missing_value",
    "univariate_outlier",
    "multivariate_outlier",
    "distribution_shift",
    "invalid_format",
    "invalid_code",
    "cross_column_swap",
)
ANOMALY_TYPES = (*TYPE_ORDER, "duplicate")


def tier(n_rows: int) -> str:
    return "A" if n_rows >= TIER_B_ROWS else "B"


def group_size(n_rows: int, rate: float = RATE) -> int:
    return max(round(rate * n_rows), 15) if tier(n_rows) == "A" else TIER_B_K


def swap_pairs(table: pd.DataFrame, kinds: dict[str, str]) -> list[tuple[str, str, float]]:
    """Pairs of same-kind columns with distinct domains, best first (lowest overlap)."""
    numeric_pairs: list[tuple[str, str, float]] = []
    nums = [c for c in table.columns if kinds[c] == "num"]
    if len(nums) >= 2:
        q = table[nums].quantile([0.25, 0.5, 0.75])
        median, iqr = q.loc[0.5].to_numpy(), (q.loc[0.75] - q.loc[0.25]).to_numpy()
        gap = np.abs(median[:, None] - median[None, :])
        width = iqr[:, None] + iqr[None, :]
        hit = np.argwhere(np.triu((gap >= width) & (width > 0), k=1))
        numeric_pairs = [(nums[i], nums[j], 0.0) for i, j in hit]
    categorical_pairs: list[tuple[str, str, float]] = []
    cats = [c for c in table.columns if kinds[c] == "cat"]
    if len(cats) >= 2:
        levels = {c: frozenset(table[c].unique()) for c in cats}
        for i, a in enumerate(cats):
            for b in cats[i + 1 :]:
                union = len(levels[a] | levels[b])
                if (overlap := len(levels[a] & levels[b]) / union) <= 0.5:
                    categorical_pairs.append((a, b, overlap))
    return sorted([*numeric_pairs, *categorical_pairs], key=lambda p: (p[2], p[0], p[1]))


def supported_types(kinds: dict[str, str], table: pd.DataFrame | None = None) -> list[str]:
    """Fault types the schema can carry; with ``table`` the data conditions are checked too."""
    nums = [c for c, k in kinds.items() if k == "num"]
    cats = [c for c, k in kinds.items() if k == "cat"]
    ok = {
        "missing_value": True,
        "univariate_outlier": len(nums) >= 1,
        "multivariate_outlier": len(nums) >= 2,
        "distribution_shift": True,
        "invalid_format": len(nums) >= 1,
        "invalid_code": len(cats) >= 1,
        "cross_column_swap": len(nums) >= 2 or len(cats) >= 2,
    }
    if table is not None:
        ok["cross_column_swap"] = ok["cross_column_swap"] and bool(swap_pairs(table, kinds))
    return [*(t for t in TYPE_ORDER if ok[t]), "duplicate"]


def inject_mixed(
    clean: pd.DataFrame,
    kinds: dict[str, str],
    seed: int,
    rate: float = RATE,
    severity: float = SEVERITY,
    reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Inject the supported fault types; magnitudes and domains come from ``reference``.

    The group layout (which rows carry which type) depends on the schema, the table and the seed
    only, so a training-only reference changes magnitudes without moving a row between partitions.
    """
    n, cols = len(clean), list(clean.columns)
    nums = [c for c in cols if kinds[c] == "num"]
    cats = [c for c in cols if kinds[c] == "cat"]
    types = [t for t in supported_types(kinds, clean) if t != "duplicate"]
    k = group_size(n, rate)
    if (len(types) + 1) * k > n:
        raise NotEligible("too few rows for the fault groups")
    ref = clean if reference is None else reference[cols]
    rng = np.random.default_rng(seed)
    mean, std = ref[nums].mean(), ref[nums].std().replace(0, 1.0)
    pop = clean.sample(frac=1.0, random_state=seed)
    pop["group_id"] = np.arange(n)
    pop["anomaly_type"] = "clean"
    pop["t"] = _BASE + pd.to_timedelta(rng.permutation(n), unit=HOUR)
    n_clean = n - len(types) * k
    blocks = {
        name: pop.iloc[n_clean + i * k : n_clean + (i + 1) * k].copy()
        for i, name in enumerate(types)
    }
    for name, block in blocks.items():
        _apply(name, block, cols, nums, cats, ref, mean, std, severity, rng, n, kinds)
        block["anomaly_type"] = name
    parts = [pop.iloc[:n_clean], *blocks.values()]
    source = pop.iloc[:n_clean].sample(n=k, random_state=seed).copy()
    source["anomaly_type"] = "duplicate"
    parts.append(source)
    out = pd.concat(parts)
    out["anomaly"] = out["anomaly_type"] != "clean"
    out = out.sample(frac=1.0, random_state=seed, ignore_index=True)
    return out[[*cols, "t", "group_id", "anomaly", "anomaly_type"]]


def _apply(name, block, cols, nums, cats, ref, mean, std, severity, rng, n, kinds) -> None:  # noqa: PLR0913
    k = len(block)
    at = block.columns.get_loc
    if name == "missing_value":
        for pos in range(k):
            for col in rng.choice(cols, size=int(rng.integers(1, 3)), replace=False):
                block.iloc[pos, at(col)] = np.nan
    elif name == "univariate_outlier":
        for pos in range(k):
            col = rng.choice(nums)
            sign = rng.choice([-1.0, 1.0])
            block.iloc[pos, at(col)] = mean[col] + sign * rng.uniform(6, 12) * severity * std[col]
    elif name == "multivariate_outlier":
        corr = ref[nums].corr().abs().to_numpy(copy=True)
        np.fill_diagonal(corr, -1)
        i, j = np.unravel_index(np.argmax(corr), corr.shape)
        a, b = nums[i], nums[j]
        sign = float(ref[[a, b]].corr().iloc[0, 1])
        hi_q, lo_q = min(1 - 0.03 / severity, 0.999), max(0.03 / severity, 0.001)
        for pos in range(k):
            up_first = (pos % 2 == 0) == (sign > 0)
            block.iloc[pos, at(a)] = ref[a].quantile(hi_q if up_first else lo_q)
            block.iloc[pos, at(b)] = ref[b].quantile(lo_q if up_first else hi_q)
    elif name == "distribution_shift":
        for col in rng.choice(nums, size=min(3, len(nums)), replace=False) if nums else []:
            block[col] = block[col] + 1.5 * severity * std[col]
        for col in rng.choice(cats, size=min(3, len(cats)), replace=False) if cats else []:
            levels = sorted(ref[col].unique())
            block[col] = rng.choice(levels, size=k)
        block["t"] = _BASE + pd.to_timedelta(rng.uniform(0.9 * n, n, size=k), unit=HOUR)
    elif name == "invalid_format":
        positive = [c for c in nums if ref[c].min() >= 0]
        for pos in range(k):
            kind = rng.choice(["sign", "sentinel", "scale"] if positive else ["scale"])
            col = rng.choice(positive if kind != "scale" else nums)
            value = block.iloc[pos, at(col)]
            block.iloc[pos, at(col)] = (
                -abs(value) - 1e-9
                if kind == "sign"
                else _SENTINEL
                if kind == "sentinel"
                else value * _SCALE
            )
    elif name == "invalid_code":
        for pos in range(k):
            col = rng.choice(cats)
            block.iloc[pos, at(col)] = f"__INVALID_{int(rng.integers(1, 1000))}__"
    elif name == "cross_column_swap":
        a, b, _ = swap_pairs(ref, kinds)[0]
        block[[a, b]] = block[[b, a]].to_numpy()


class Encoder:
    """Numeric view of a mixed table, fitted on training rows only."""

    def __init__(self, kinds: dict[str, str], levels: dict[str, list[str]], freq: dict[str, dict]):
        self.kinds, self.levels, self.freq = kinds, levels, freq

    @classmethod
    def fit(cls, train: pd.DataFrame, kinds: dict[str, str]) -> Encoder:
        levels: dict[str, list[str]] = {}
        freq: dict[str, dict] = {}
        for col, kind in kinds.items():
            if kind != "cat":
                continue
            counts = train[col].value_counts()
            share = counts[counts >= MIN_LEVEL_COUNT] / len(train)
            if len(share) <= ONE_HOT_MAX:
                levels[col] = sorted(share.index)
            else:
                freq[col] = share.to_dict()
        return cls(kinds, levels, freq)

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        parts: dict[str, pd.Series] = {}
        for col, kind in self.kinds.items():
            if kind == "num":
                parts[col] = np.asarray(frame[col], dtype=float)
            elif col in self.levels:
                for level in self.levels[col]:
                    parts[f"{col}={level}"] = np.asarray(frame[col] == level, dtype=float)
            else:
                parts[col] = frame[col].map(self.freq[col]).fillna(0.0).to_numpy()
        return pd.DataFrame(parts, index=frame.index)
