"""Controlled synthetic dataset with six labelled anomaly types.

The real datasets in this benchmark (Credit Card Fraud, later UCI Water
Quality) carry a single binary label and mix every kind of defect
together. To measure *which detector catches which kind of problem* we
need a dataset where the anomaly category of every bad row is known. This
module builds one.

A base population of plausible customer records is generated with Faker
and NumPy (income correlated with balance and transaction size, tenure
spread over three years). Six anomaly types are then injected at a
controlled rate each, every injected row tagged in ``anomaly_type``:

    - ``missing_value``       — one or two feature cells nulled out;
    - ``duplicate``           — an exact copy of a clean row (appended);
    - ``univariate_outlier``  — one numeric field pushed far out of range;
    - ``multivariate_outlier``— each field in range, the combination not
      (e.g. an 18-year-old with a top-percentile balance and income);
    - ``temporal_drift``      — recent-signup rows whose income and
      balance distribution has shifted upward by ~50%;
    - ``invalid_format``      — malformed email, out-of-domain country
      code, impossible age.

:func:`make_synthetic` returns a single DataFrame; ``anomaly`` is the
binary ground truth and ``anomaly_type`` the fine-grained one.
:data:`FEATURE_COLUMNS` lists the columns a detector may look at (the
ground-truth columns and the id are excluded).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

from etl_benchmark import config

ANOMALY_TYPES: list[str] = [
    "missing_value",
    "duplicate",
    "univariate_outlier",
    "multivariate_outlier",
    "temporal_drift",
    "invalid_format",
]

FEATURE_COLUMNS: list[str] = [
    "age",
    "annual_income",
    "account_balance",
    "n_transactions_30d",
    "avg_transaction_amount",
    "tenure_days",
    "signup_date",
    "email",
    "country",
]

NUMERIC_FEATURES: list[str] = [
    "age",
    "annual_income",
    "account_balance",
    "n_transactions_30d",
    "avg_transaction_amount",
    "tenure_days",
]

_COUNTRIES = ["FR", "DE", "ES", "IT", "BE", "NL", "PT"]
_REFERENCE_DATE = pd.Timestamp("2026-06-30")


def _clean_population(n: int, rng: np.random.Generator, fake: Faker) -> pd.DataFrame:
    age = np.clip(rng.normal(42, 13, n), 18, 88).round()
    annual_income = np.exp(rng.normal(10.6, 0.45, n)) + (age - 42) * 350
    annual_income = np.clip(annual_income, 6_000, None)
    account_balance = annual_income * rng.uniform(0.03, 0.55, n) + rng.normal(0, 800, n)
    account_balance = np.clip(account_balance, 0, None)
    n_transactions_30d = rng.poisson(np.clip(annual_income / 4_000, 2, 90)).astype(float)
    avg_transaction_amount = np.clip(annual_income / 1_200 * rng.uniform(0.5, 1.6, n), 1, None)
    tenure_days = rng.integers(30, 3 * 365, n).astype(float)
    offsets = rng.integers(90, 3 * 365, n)
    signup_date = [
        (_REFERENCE_DATE - pd.Timedelta(days=int(d))).strftime("%Y-%m-%d") for d in offsets
    ]
    email = [fake.email() for _ in range(n)]
    country = rng.choice(_COUNTRIES, size=n)

    return pd.DataFrame(
        {
            "age": age,
            "annual_income": annual_income.round(2),
            "account_balance": account_balance.round(2),
            "n_transactions_30d": n_transactions_30d,
            "avg_transaction_amount": avg_transaction_amount.round(2),
            "tenure_days": tenure_days,
            "signup_date": signup_date,
            "email": email,
            "country": country,
        }
    )


def _inject_missing_value(block: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    nullable = [
        "annual_income",
        "account_balance",
        "avg_transaction_amount",
        "tenure_days",
        "n_transactions_30d",
        "email",
        "country",
    ]
    for pos in range(len(block)):
        cols = rng.choice(nullable, size=int(rng.integers(1, 3)), replace=False)
        for col in cols:
            block.iloc[pos, block.columns.get_loc(col)] = np.nan if col != "email" else None
    return block


def _inject_univariate_outlier(block: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    for pos in range(len(block)):
        col = rng.choice(NUMERIC_FEATURES)
        factor = rng.uniform(15, 45)
        block.iloc[pos, block.columns.get_loc(col)] = (
            float(block.iloc[pos, block.columns.get_loc(col)]) * factor + factor
        )
    return block


def _inject_multivariate_outlier(
    block: pd.DataFrame, rng: np.random.Generator, clean: pd.DataFrame
) -> pd.DataFrame:
    hi_income = clean["annual_income"].quantile(0.97)
    hi_balance = clean["account_balance"].quantile(0.97)
    hi_txn = clean["n_transactions_30d"].quantile(0.97)
    lo_amount = clean["avg_transaction_amount"].quantile(0.03)
    for pos in range(len(block)):
        if pos % 2 == 0:
            # young but top-percentile wealth: each value seen in clean data
            block.iloc[pos, block.columns.get_loc("age")] = float(rng.integers(18, 23))
            block.iloc[pos, block.columns.get_loc("annual_income")] = float(hi_income)
            block.iloc[pos, block.columns.get_loc("account_balance")] = float(hi_balance)
        else:
            # very active account with near-zero average ticket
            block.iloc[pos, block.columns.get_loc("n_transactions_30d")] = float(hi_txn)
            block.iloc[pos, block.columns.get_loc("avg_transaction_amount")] = float(lo_amount)
    return block


def _inject_temporal_drift(block: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    for pos in range(len(block)):
        recent = _REFERENCE_DATE - pd.Timedelta(days=int(rng.integers(1, 80)))
        block.iloc[pos, block.columns.get_loc("signup_date")] = recent.strftime("%Y-%m-%d")
        for col, mult in (
            ("annual_income", 1.55),
            ("account_balance", 1.6),
            ("avg_transaction_amount", 1.5),
        ):
            block.iloc[pos, block.columns.get_loc(col)] = (
                float(block.iloc[pos, block.columns.get_loc(col)]) * mult
            )
    return block


def _inject_invalid_format(block: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    bad_emails = ["not-an-email", "missing.at.sign.com", "john doe@example", "@nodomain.com", "n/a"]
    bad_ages = [-5.0, -1.0, 0.0, 240.0, 999.0]
    bad_countries = ["ZZ", "XX", "??", "1"]
    for pos in range(len(block)):
        block.iloc[pos, block.columns.get_loc("email")] = str(rng.choice(bad_emails))
        block.iloc[pos, block.columns.get_loc("age")] = float(rng.choice(bad_ages))
        block.iloc[pos, block.columns.get_loc("country")] = str(rng.choice(bad_countries))
    return block


def make_synthetic(
    n_rows: int = config.SYNTHETIC_ROWS,
    anomaly_rate: float = config.SYNTHETIC_ANOMALY_RATE,
    seed: int = config.RANDOM_SEED,
) -> pd.DataFrame:
    """Build the labelled synthetic dataset.

    ``anomaly_rate`` is applied per anomaly type. The five in-place types
    replace clean rows (the total stays ``n_rows``); ``duplicate`` rows
    are appended, so the frame has about ``n_rows * (1 + anomaly_rate)``
    rows in the end.
    """
    rng = np.random.default_rng(seed)
    Faker.seed(seed)
    fake = Faker("en_US")

    k = max(int(round(anomaly_rate * n_rows)), 15)
    n_clean = max(n_rows - 5 * k, k)

    pop = _clean_population(n_rows, rng, fake)
    pop.insert(0, "customer_id", np.arange(1, n_rows + 1))
    pop["anomaly_type"] = "clean"

    clean = pop.iloc[:n_clean].copy()
    cursor = n_clean
    injectors = {
        "missing_value": lambda b: _inject_missing_value(b, rng),
        "univariate_outlier": lambda b: _inject_univariate_outlier(b, rng),
        "multivariate_outlier": lambda b: _inject_multivariate_outlier(b, rng, clean),
        "temporal_drift": lambda b: _inject_temporal_drift(b, rng),
        "invalid_format": lambda b: _inject_invalid_format(b, rng),
    }

    parts = [clean]
    for name, fn in injectors.items():
        block = pop.iloc[cursor : cursor + k].copy()
        cursor += k
        block = fn(block)
        block["anomaly_type"] = name
        parts.append(block)

    dups = clean.drop(columns="anomaly_type").sample(n=k, random_state=seed).copy()
    dups["anomaly_type"] = "duplicate"
    parts.append(dups)

    df = pd.concat(parts, ignore_index=True)
    df["anomaly"] = df["anomaly_type"] != "clean"

    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df[["customer_id", *FEATURE_COLUMNS, "anomaly", "anomaly_type"]]
