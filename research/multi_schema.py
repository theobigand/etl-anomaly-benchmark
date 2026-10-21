"""Two further synthetic schemas with the six anomaly types of the customer table (issue #67).

Protocol: verification/multi_schema.md. The customer schema and its published results are
untouched; this module lives outside the detector registry and the scientific fingerprint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from faker import Faker  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.metrics import precision_score, recall_score  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / "src")]

from etl_benchmark import config  # noqa: E402
from etl_benchmark.pipeline import detect  # noqa: E402
from etl_benchmark.quality import TemporalDriftDetector  # noqa: E402
from etl_benchmark.registry import DETECTOR_NAMES, get_detector  # noqa: E402
from etl_benchmark.split import stratified_split  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES  # noqa: E402

SEEDS = (42, 1, 2, 3, 4)
REFERENCE = pd.Timestamp("2026-06-30")


@dataclass(frozen=True)
class Schema:
    name: str
    id_col: str
    numeric: list[str]
    date_col: str
    string_col: str
    string_valid: str
    bad_strings: list[str]
    cat_col: str
    domain: list[str]
    bad_cats: list[str]
    pair: tuple[str, str]
    drift_cols: list[str]
    bad_numeric: dict[str, list[float]]
    clean: Callable[[int, np.random.Generator, Faker], pd.DataFrame]
    date_format: str = "%Y-%m-%d"


def _dates(n: int, rng: np.random.Generator, fmt: str) -> list[str]:
    offsets = rng.integers(90, 3 * 365, n)
    hours = rng.integers(0, 24, n)
    return [
        (REFERENCE - pd.Timedelta(days=int(d), hours=int(h))).strftime(fmt)
        for d, h in zip(offsets, hours, strict=True)
    ]


def _transactions(n: int, rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    items = (rng.poisson(3, n) + 1).astype(float)
    unit = np.exp(rng.normal(3.0, 0.5, n))
    amount = items * unit * rng.uniform(0.9, 1.1, n)
    return pd.DataFrame(
        {
            "amount": amount.round(2),
            "n_items": items,
            "discount_pct": rng.uniform(0, 30, n).round(1),
            "merchant_risk": (rng.beta(2, 8, n) * 100).round(2),
            "account_age_days": rng.integers(30, 2000, n).astype(float),
            "balance_after": np.clip(
                amount * rng.uniform(2, 40, n) + rng.normal(0, 50, n), 0, None
            ).round(2),
            "txn_date": _dates(n, rng, "%Y-%m-%d"),
            "reference": [f"TX-{int(v):08d}" for v in rng.integers(0, 10**8, n)],
            "currency": rng.choice(["EUR", "USD", "GBP", "CHF"], n),
        }
    )


def _sensors(n: int, rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    temperature = rng.normal(21, 4, n)
    humidity = np.clip(70 - 1.5 * (temperature - 21) + rng.normal(0, 5, n), 5, 95)
    firmware = [f"v{a}.{b}.{c}" for a, b, c in rng.integers(0, 10, (n, 3))]
    return pd.DataFrame(
        {
            "temperature_c": temperature.round(2),
            "humidity_pct": humidity.round(2),
            "pressure_hpa": rng.normal(1013, 8, n).round(2),
            "vibration_mm_s": np.exp(rng.normal(0.2, 0.4, n)).round(3),
            "battery_v": rng.uniform(3.4, 4.2, n).round(3),
            "signal_dbm": rng.normal(-70, 8, n).round(1),
            "reading_time": _dates(n, rng, "%Y-%m-%d %H:00:00"),
            "firmware": firmware,
            "site": rng.choice(["north", "south", "east", "west", "depot"], n),
        }
    )


SCHEMAS: dict[str, Schema] = {
    "transactions": Schema(
        name="transactions",
        id_col="txn_id",
        numeric=[
            "amount",
            "n_items",
            "discount_pct",
            "merchant_risk",
            "account_age_days",
            "balance_after",
        ],
        date_col="txn_date",
        string_col="reference",
        string_valid=r"TX-\d{8}",
        bad_strings=["TX-12", "tx_00000001", "REF 99", "n/a", ""],
        cat_col="currency",
        domain=["EUR", "USD", "GBP", "CHF"],
        bad_cats=["EURO", "XXX", "??", "1"],
        pair=("amount", "n_items"),
        drift_cols=["amount", "balance_after", "merchant_risk"],
        bad_numeric={"amount": [-250.0, -1.0, 0.0, 99999.0], "n_items": [-3.0, 0.0, 500.0]},
        clean=_transactions,
    ),
    "sensors": Schema(
        name="sensors",
        id_col="reading_id",
        numeric=[
            "temperature_c",
            "humidity_pct",
            "pressure_hpa",
            "vibration_mm_s",
            "battery_v",
            "signal_dbm",
        ],
        date_col="reading_time",
        string_col="firmware",
        string_valid=r"v\d\.\d\.\d",
        bad_strings=["v1", "1.2.3", "firmware 2", "unknown", ""],
        cat_col="site",
        domain=["north", "south", "east", "west", "depot"],
        bad_cats=["nord", "??", "SITE-9", "0"],
        pair=("temperature_c", "humidity_pct"),
        drift_cols=["temperature_c", "vibration_mm_s", "signal_dbm"],
        bad_numeric={"humidity_pct": [-10.0, 0.0, 150.0, 999.0], "battery_v": [-1.0, 0.0, 99.0]},
        clean=_sensors,
        date_format="%Y-%m-%d %H:00:00",
    ),
}


def features(spec: Schema) -> list[str]:
    return [*spec.numeric, spec.date_col, spec.string_col, spec.cat_col]


def _set(block: pd.DataFrame, pos: int, col: str, value: Any) -> None:
    block.iloc[pos, block.columns.get_loc(col)] = value


def make(
    spec: Schema,
    n_rows: int = 12_000,
    seed: int = 42,
    anomaly_rate: float = config.SYNTHETIC_ANOMALY_RATE,
    severity: float = 1.0,
) -> pd.DataFrame:
    if n_rows < 90 or not 0 < anomaly_rate <= 1 / 6 or severity <= 0:
        raise ValueError("invalid generator parameters")
    k = max(int(round(anomaly_rate * n_rows)), 15)
    if 6 * k > n_rows:
        raise ValueError("n_rows cannot hold six anomaly groups of the requested size")
    rng = np.random.default_rng(seed)
    Faker.seed(seed)
    pop = spec.clean(n_rows, rng, Faker("en_US"))
    pop[spec.id_col] = np.arange(1, n_rows + 1)
    pop["anomaly_type"] = "clean"
    n_clean = n_rows - 5 * k
    clean = pop.iloc[:n_clean].copy()
    cursor = n_clean
    nullable = [*spec.numeric, spec.string_col, spec.cat_col]
    a, b = spec.pair
    sign = np.sign(clean[a].corr(clean[b]))
    q_hi, q_lo = min(1.0 - 0.03 / severity, 0.999), max(0.03 / severity, 0.001)
    parts = [clean]
    for name in (
        "missing_value",
        "univariate_outlier",
        "multivariate_outlier",
        "temporal_drift",
        "invalid_format",
    ):
        block = pop.iloc[cursor : cursor + k].copy()
        cursor += k
        for pos in range(len(block)):
            if name == "missing_value":
                for col in rng.choice(nullable, size=int(rng.integers(1, 3)), replace=False):
                    _set(block, pos, col, np.nan)
            elif name == "univariate_outlier":
                col = str(rng.choice(spec.numeric))
                factor = rng.uniform(15, 45) * severity
                _set(block, pos, col, float(block.iloc[pos][col]) * factor + factor)
            elif name == "multivariate_outlier":
                high_a = pos % 2 == 0
                high_b = high_a if sign < 0 else not high_a
                _set(block, pos, a, float(clean[a].quantile(q_hi if high_a else q_lo)))
                _set(block, pos, b, float(clean[b].quantile(q_hi if high_b else q_lo)))
            elif name == "temporal_drift":
                recent = REFERENCE - pd.Timedelta(days=int(rng.integers(1, 80)))
                _set(block, pos, spec.date_col, recent.strftime(spec.date_format))
                for col, base in zip(spec.drift_cols, (1.55, 1.6, 1.5), strict=True):
                    _set(
                        block,
                        pos,
                        col,
                        float(block.iloc[pos][col]) * (1.0 + (base - 1.0) * severity),
                    )
            else:
                col = str(rng.choice(list(spec.bad_numeric)))
                _set(block, pos, col, float(rng.choice(spec.bad_numeric[col])))
                _set(block, pos, spec.string_col, str(rng.choice(spec.bad_strings)))
                _set(block, pos, spec.cat_col, str(rng.choice(spec.bad_cats)))
        block["anomaly_type"] = name
        parts.append(block)
    dups = clean.drop(columns="anomaly_type").sample(n=k, random_state=seed).copy()
    dups["anomaly_type"] = "duplicate"
    parts.append(dups)
    df = pd.concat(parts)
    df["anomaly"] = df["anomaly_type"] != "clean"
    df = df.sample(frac=1.0, random_state=seed, ignore_index=True)
    return df[[spec.id_col, *features(spec), "anomaly", "anomaly_type"]]


def _split(df: pd.DataFrame, spec: Schema, seed: int):
    groups = (
        df.groupby(spec.id_col, sort=False)["anomaly_type"]
        .agg(lambda types: "duplicate" if "duplicate" in types.values else types.iloc[0])
        .reset_index(name="stratum")
    )
    parts = stratified_split(groups, "stratum", config.SPLIT_RATIOS, seed)
    return tuple(df[df[spec.id_col].isin(p[spec.id_col])].reset_index(drop=True) for p in parts)


def _per_type(flags: pd.Series, types: pd.Series) -> tuple[dict, dict]:
    clean = types == "clean"
    recall, precision = {}, {}
    for name in ANOMALY_TYPES:
        is_type = types == name
        if not is_type.any():
            recall[name] = precision[name] = np.nan
            continue
        keep = is_type | clean
        recall[name] = recall_score(is_type[keep].astype(int), flags[keep])
        precision[name] = precision_score(is_type[keep].astype(int), flags[keep], zero_division=0)
    return recall, precision


def evaluate(df: pd.DataFrame, spec: Schema, seed: int) -> dict[str, pd.DataFrame]:
    warnings.filterwarnings("ignore")
    train, _val, test = _split(df, spec, seed)
    contamination = float(train["anomaly"].mean())
    cols = features(spec)
    recall, precision, fpr = [], [], {}
    detectors = {
        **{n: get_detector(n, contamination) for n in DETECTOR_NAMES},
        "drift": TemporalDriftDetector(time_column=spec.date_col, columns=spec.numeric),
    }
    for name in [*detectors, "transform_dedup"]:
        if name == "transform_dedup":
            flags = test.duplicated(subset=cols, keep=False)
        else:
            flags = detect(test[cols], detectors[name], fit_df=train[cols]).flags
        flags = pd.Series(np.asarray(flags), index=test.index)
        fpr[name] = float(flags[test["anomaly_type"] == "clean"].mean())
        r, p = _per_type(flags, test["anomaly_type"])
        recall.append({"method": name, **r})
        precision.append({"method": name, **p})
    return {
        "recall": pd.DataFrame(recall).set_index("method")[ANOMALY_TYPES],
        "precision": pd.DataFrame(precision).set_index("method")[ANOMALY_TYPES],
        "fpr": pd.Series(fpr),
    }


def hypotheses(matrices: dict[str, pd.DataFrame]) -> dict[str, Any]:
    h1 = {
        name: bool(
            m.loc["great_expectations", "missing_value"] >= 0.9
            and m.loc["transform_dedup", "duplicate"] >= 0.9
        )
        for name, m in matrices.items()
    }
    h2 = {
        name: bool(
            m.loc[["isolation_forest", "ocsvm"], "multivariate_outlier"].min() >= 0.5
            and m.loc[["zscore", "iqr"], "multivariate_outlier"].max() < 0.2
        )
        for name, m in matrices.items()
    }
    h3 = {name: float(m["temporal_drift"].max()) for name, m in matrices.items()}
    rhos = {}
    for (a, ma), (b, mb) in combinations(matrices.items(), 2):
        common = [i for i in ma.index if i in mb.index and i != "drift"]
        rhos[f"{a}|{b}"] = float(
            spearmanr(
                ma.loc[common].to_numpy().ravel(), mb.loc[common].to_numpy().ravel()
            ).statistic
        )
    mean_rho = float(np.mean(list(rhos.values())))
    return {
        "H1": {"supported": all(h1.values()), "by_schema": h1},
        "H2": {"supported": all(h2.values()), "by_schema": h2},
        "H3": {"supported": all(v < 0.6 for v in h3.values()), "best_drift_recall": h3},
        "H4": {"supported": mean_rho >= 0.7, "mean_spearman": mean_rho, "pairs": rhos},
    }


def published_customer() -> pd.DataFrame:
    path = ROOT / "verification" / "evidence" / "synthetic_recall.csv"
    frame = pd.read_csv(path, index_col="method")
    out = frame[[f"{t}_mean" for t in ANOMALY_TYPES]]
    out.columns = ANOMALY_TYPES
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=12_000)
    args = parser.parse_args(argv)
    from etl_benchmark.atomic import atomic_path

    args.output.mkdir(parents=True, exist_ok=True)
    means: dict[str, pd.DataFrame] = {}
    stds: dict[str, pd.DataFrame] = {}
    for name, spec in SCHEMAS.items():
        runs = [evaluate(make(spec, args.rows, seed), spec, seed) for seed in SEEDS]
        for seed, run in zip(SEEDS, runs, strict=True):
            with atomic_path(args.output / f"{name}_seed_{seed}.json") as partial:
                partial.write_text(
                    json.dumps(
                        {k: json.loads(v.to_json(orient="split")) for k, v in run.items()}, indent=1
                    )
                    + "\n"
                )
        stack = pd.concat([r["recall"] for r in runs], keys=range(len(runs)))
        means[name] = stack.groupby(level=1, sort=False).mean()
        stds[name] = stack.groupby(level=1, sort=False).std()
        print(name, flush=True)
    matrices = {"customer": published_customer(), **means}
    results = {
        "mean": {k: json.loads(v.to_json(orient="split")) for k, v in matrices.items()},
        "std": {k: json.loads(v.to_json(orient="split")) for k, v in stds.items()},
        "hypotheses": hypotheses(matrices),
    }
    with atomic_path(args.output / "multi_schema_results.json") as partial:
        partial.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    lines = []
    for name, m in matrices.items():
        lines += [
            f"### {name}",
            "",
            "| method | " + " | ".join(m.columns) + " |",
            "|---|" + "---|" * len(m.columns),
        ]
        lines += [
            f"| {i} | " + " | ".join(f"{v:.2f}" for v in m.loc[i]) + " |" for i in m.index
        ] + [""]
    with atomic_path(args.output / "multi_schema_results.md") as partial:
        partial.write_text("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
