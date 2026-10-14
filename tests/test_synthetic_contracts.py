import hashlib
import re

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import synthetic
from etl_benchmark.synthetic import FEATURE_COLUMNS, NUMERIC_FEATURES, make_synthetic

REFERENCE = pd.Timestamp("2026-06-30")


class _FixedEmails:
    def email(self):
        return "someone@example.org"


def _message(text):
    return f"^{re.escape(text)}$"


def _population(n=50_000, seed=3):
    return synthetic._clean_population(n, np.random.default_rng(seed), _FixedEmails())


def test_row_count_rate_and_severity_bounds_are_inclusive():
    assert len(make_synthetic(n_rows=90, anomaly_rate=0.0)) == 90
    assert len(make_synthetic(n_rows=90, anomaly_rate=1 / 6)) == 90 + 15
    with pytest.raises(ValueError, match=_message("n_rows must be an integer of at least 90")):
        make_synthetic(n_rows=89, anomaly_rate=0.0)
    with pytest.raises(ValueError, match=_message("n_rows must be an integer of at least 90")):
        make_synthetic(n_rows=100.0)
    with pytest.raises(
        ValueError, match=_message("anomaly_rate must be finite and between 0 and 1/6")
    ):
        make_synthetic(n_rows=1_000, anomaly_rate=0.2)
    with pytest.raises(
        ValueError, match=_message("anomaly_rate must be finite and between 0 and 1/6")
    ):
        make_synthetic(n_rows=1_000, anomaly_rate=float("nan"))
    for severity in (0.0, float("inf")):
        with pytest.raises(ValueError, match=_message("severity must be finite and positive")):
            make_synthetic(n_rows=1_000, severity=severity)
    with pytest.raises(
        ValueError, match=_message("n_rows cannot hold six anomaly groups of the requested size")
    ):
        make_synthetic(n_rows=94, anomaly_rate=1 / 6)


def test_output_has_a_fresh_index_and_the_documented_columns():
    df = make_synthetic(n_rows=600, seed=4)
    assert df.index.equals(pd.RangeIndex(len(df)))
    assert df.columns.tolist() == [
        "customer_id",
        *FEATURE_COLUMNS,
        "anomaly",
        "anomaly_type",
    ]
    assert df["customer_id"].min() == 1
    assert df["customer_id"].max() == 600


def test_clean_population_stays_inside_its_documented_domain():
    pop = _population()
    assert pop["age"].min() == 18
    assert pop["age"].max() <= 88
    assert (pop["age"] == pop["age"].round()).all()
    assert pop["annual_income"].min() >= 6_000
    assert pop["account_balance"].min() == 0
    assert pop["n_transactions_30d"].min() >= 0
    assert (pop["n_transactions_30d"] == pop["n_transactions_30d"].round()).all()
    assert pop["avg_transaction_amount"].min() >= 1
    assert pop["tenure_days"].between(30, 3 * 365 - 1).all()
    for column in ("annual_income", "account_balance", "avg_transaction_amount"):
        assert (pop[column] == pop[column].round(2)).all()
    assert set(pop["country"]) == {"FR", "DE", "ES", "IT", "BE", "NL", "PT"}
    assert (pop["email"] == "someone@example.org").all()


def test_signup_dates_are_iso_days_before_the_reference_date():
    pop = _population()
    assert pop["signup_date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    age_in_days = (REFERENCE - pd.to_datetime(pop["signup_date"])).dt.days
    assert age_in_days.min() == 90
    assert age_in_days.max() == 3 * 365 - 1


def test_clean_population_follows_the_documented_marginals():
    # Clipping at 18 and 88 pulls the age moments slightly inside N(42, 13).
    pop = _population(200_000, seed=5)
    assert pop["age"].mean() == pytest.approx(42.17, abs=0.15)
    assert pop["age"].std() == pytest.approx(12.65, abs=0.15)
    slope = np.polyfit(pop["age"], pop["annual_income"], 1)[0]
    assert slope == pytest.approx(347, abs=25)
    assert np.log(pop["annual_income"]).std() == pytest.approx(0.477, abs=0.01)
    balance_share = pop["account_balance"] / pop["annual_income"]
    assert balance_share.mean() == pytest.approx(0.29, abs=0.005)
    ticket = pop["avg_transaction_amount"] / (pop["annual_income"] / 1_200)
    assert ticket.mean() == pytest.approx(1.05, abs=0.01)
    expected_rate = (pop["annual_income"] / 4_000).clip(2, 90).mean()
    assert pop["n_transactions_30d"].mean() == pytest.approx(expected_rate, rel=0.01)


def _by_type(df, kind):
    return df[df["anomaly_type"] == kind]


def test_missing_value_rows_null_one_or_two_distinct_cells_of_nullable_columns():
    df = make_synthetic(n_rows=3_000, seed=6)
    rows = _by_type(df, "missing_value")
    nulls = rows[FEATURE_COLUMNS].isna()
    assert nulls.sum(axis=1).isin([1, 2]).all()
    assert set(nulls.sum(axis=1)) == {1, 2}
    assert not nulls[["age", "signup_date"]].any().any()
    clean = _by_type(df, "clean")
    assert not clean[FEATURE_COLUMNS].isna().any().any()


def test_univariate_outliers_push_one_numeric_field_beyond_the_clean_range():
    df = make_synthetic(n_rows=3_000, seed=6)
    clean = _by_type(df, "clean")
    rows = _by_type(df, "univariate_outlier")
    beyond = (rows[NUMERIC_FEATURES] > clean[NUMERIC_FEATURES].quantile(0.999)).any(axis=1)
    assert beyond.mean() > 0.8
    assert (rows[NUMERIC_FEATURES] >= 0).all().all()


@pytest.mark.parametrize(
    ("severity", "high_quantile", "low_quantile"),
    [(1.0, 0.97, 0.03), (2.0, 0.985, 0.015), (50.0, 0.999, 0.001)],
)
def test_multivariate_outliers_reuse_clean_marginal_quantiles(
    severity, high_quantile, low_quantile
):
    df = make_synthetic(n_rows=6_000, seed=8, severity=severity)
    clean = _by_type(df, "clean")
    rows = _by_type(df, "multivariate_outlier")
    income = clean["annual_income"].quantile(high_quantile)
    wealthy = rows[rows["annual_income"] == income]
    assert 0.4 < len(wealthy) / len(rows) < 0.6
    assert wealthy["age"].between(18, 22).all()
    assert (wealthy["account_balance"] == clean["account_balance"].quantile(high_quantile)).all()
    active = rows.drop(wealthy.index)
    assert (
        active["n_transactions_30d"] == clean["n_transactions_30d"].quantile(high_quantile)
    ).all()
    assert (
        active["avg_transaction_amount"] == clean["avg_transaction_amount"].quantile(low_quantile)
    ).all()


def test_temporal_drift_rows_are_recent_signups_with_inflated_amounts():
    base = make_synthetic(n_rows=6_000, seed=9, anomaly_rate=0.0)
    df = make_synthetic(n_rows=6_000, seed=9)
    rows = _by_type(df, "temporal_drift")
    days_before = (REFERENCE - pd.to_datetime(rows["signup_date"])).dt.days
    assert days_before.between(1, 79).all()
    for column, ratio in (
        ("annual_income", 1.55),
        ("account_balance", 1.6),
        ("avg_transaction_amount", 1.5),
    ):
        assert rows[column].mean() / base[column].mean() == pytest.approx(ratio, rel=0.15)
    doubled = _by_type(make_synthetic(n_rows=6_000, seed=9, severity=2.0), "temporal_drift")
    assert doubled["annual_income"].mean() / base["annual_income"].mean() == pytest.approx(
        2.1, rel=0.15
    )


def test_invalid_format_rows_draw_from_the_documented_bad_values():
    rows = _by_type(make_synthetic(n_rows=6_000, seed=10), "invalid_format")
    assert set(rows["email"]) == {
        "not-an-email",
        "missing.at.sign.com",
        "john doe@example",
        "@nodomain.com",
        "n/a",
    }
    assert set(rows["age"]) == {-5.0, -1.0, 0.0, 240.0, 999.0}
    assert set(rows["country"]) == {"ZZ", "XX", "??", "1"}


def test_reference_dataset_is_pinned_for_published_tables():
    # The thesis tables are computed from this exact dataset. A change to the
    # generator must be deliberate: update the digest together with the replay.
    df = make_synthetic(n_rows=2_000, seed=42).drop(columns="email")
    text = df.round(2).to_csv(index=False)
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert digest == "fa4803391a5e2c4e141508b4b2cb0d2b9ad9caacce232254c67868a8aeed8603"


def _block(n=40):
    pop = _population(n, seed=11)
    pop["customer_id"] = np.arange(n)
    return pop


_NULLABLE = {
    "annual_income",
    "account_balance",
    "avg_transaction_amount",
    "tenure_days",
    "n_transactions_30d",
    "email",
    "country",
}


@pytest.mark.parametrize(
    ("inject", "allowed"),
    [
        (lambda b, rng, clean: synthetic._inject_missing_value(b, rng), _NULLABLE),
        (
            lambda b, rng, clean: synthetic._inject_univariate_outlier(b, rng, 1.0),
            set(NUMERIC_FEATURES),
        ),
        (
            lambda b, rng, clean: synthetic._inject_multivariate_outlier(b, rng, clean, 1.0),
            {"age", "annual_income", "account_balance", "n_transactions_30d"}
            | {"avg_transaction_amount"},
        ),
        (
            lambda b, rng, clean: synthetic._inject_temporal_drift(b, rng, 1.0),
            {"signup_date", "annual_income", "account_balance", "avg_transaction_amount"},
        ),
        (
            lambda b, rng, clean: synthetic._inject_invalid_format(b, rng),
            {"email", "age", "country"},
        ),
    ],
    ids=["missing", "univariate", "multivariate", "drift", "invalid"],
)
def test_each_injector_leaves_the_columns_outside_its_scope_untouched(inject, allowed):
    original = _block()
    changed = inject(original.copy(), np.random.default_rng(5), original)
    differing = {
        column
        for column in original.columns
        if not original[column].equals(changed[column])
        and not (original[column].isna() & changed[column].isna()).all()
    }
    assert differing, "the injector changed nothing"
    assert differing <= allowed
    assert original["customer_id"].equals(changed["customer_id"])
