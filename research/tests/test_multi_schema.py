"""Multi-schema generator and per-type evaluation (issue #67)."""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multi_schema as ms  # noqa: E402

TYPES = [
    "missing_value",
    "duplicate",
    "univariate_outlier",
    "multivariate_outlier",
    "temporal_drift",
    "invalid_format",
]


@pytest.fixture(params=sorted(ms.SCHEMAS))
def spec(request):
    return ms.SCHEMAS[request.param]


def test_the_registry_holds_the_two_new_schemas():
    assert sorted(ms.SCHEMAS) == ["sensors", "transactions"]


def test_a_schema_has_numeric_date_string_and_category_fields(spec):
    df = ms.make(spec, n_rows=600, seed=1)
    assert len(spec.numeric) >= 6
    for col in (*spec.numeric, spec.date_col, spec.string_col, spec.cat_col):
        assert col in df.columns
    assert df[spec.id_col].is_unique or df.duplicated(subset=ms.features(spec)).any()


def test_every_type_is_present_at_the_requested_rate(spec):
    df = ms.make(spec, n_rows=1200, seed=1, anomaly_rate=0.03)
    counts = df["anomaly_type"].value_counts()
    assert set(counts.index) == {"clean", *TYPES}
    for t in TYPES:
        assert counts[t] == 36
    assert len(df) == 1200 + 36
    assert (df["anomaly"] == (df["anomaly_type"] != "clean")).all()


def test_generation_is_deterministic_and_seed_sensitive(spec):
    a, b = ms.make(spec, n_rows=300, seed=3), ms.make(spec, n_rows=300, seed=3)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(ms.make(spec, n_rows=300, seed=4))


def test_clean_rows_are_valid_and_invalid_rows_are_not(spec):
    df = ms.make(spec, n_rows=900, seed=2)
    pattern = re.compile(spec.string_valid)
    clean = df[df["anomaly_type"] == "clean"]
    assert clean[spec.string_col].map(lambda s: bool(pattern.fullmatch(s))).all()
    assert clean[spec.cat_col].isin(spec.domain).all()
    bad = df[df["anomaly_type"] == "invalid_format"]
    assert not bad[spec.string_col].map(lambda s: bool(pattern.fullmatch(str(s)))).any()
    assert not bad[spec.cat_col].isin(spec.domain).any()


def test_missing_rows_have_a_null_and_duplicates_copy_a_clean_row(spec):
    df = ms.make(spec, n_rows=900, seed=2)
    feats = ms.features(spec)
    assert df[df["anomaly_type"] == "missing_value"][feats].isna().any(axis=1).all()
    dup = df[df["anomaly_type"] == "duplicate"][feats]
    clean = df[df["anomaly_type"] == "clean"][feats]
    merged = dup.merge(clean.drop_duplicates(), how="left", indicator=True)
    assert (merged["_merge"] == "both").all()


def test_drift_rows_are_recent_and_shifted_up(spec):
    df = ms.make(spec, n_rows=1500, seed=2)
    dates = pd.to_datetime(df[spec.date_col], format="mixed")
    drift = df["anomaly_type"] == "temporal_drift"
    clean = df["anomaly_type"] == "clean"
    assert dates[drift].min() > dates[clean].quantile(0.5)
    col = spec.drift_cols[0]
    assert np.sign(df.loc[drift, col].mean()) == np.sign(df.loc[clean, col].mean())
    assert abs(df.loc[drift, col].mean()) > abs(df.loc[clean, col].mean())


def test_multivariate_rows_stay_inside_the_marginal_range_but_break_the_pair(spec):
    df = ms.make(spec, n_rows=3000, seed=2)
    a, b = spec.pair
    clean = df[df["anomaly_type"] == "clean"]
    mv = df[df["anomaly_type"] == "multivariate_outlier"]
    assert mv[a].between(clean[a].min(), clean[a].max()).all()
    assert mv[b].between(clean[b].min(), clean[b].max()).all()
    corr = clean[a].corr(clean[b])
    mv_signs = np.sign((mv[a] - clean[a].median()) * (mv[b] - clean[b].median()))
    assert (mv_signs != np.sign(corr)).mean() > 0.9


def test_evaluate_gives_one_row_per_method_and_one_column_per_type(spec):
    df = ms.make(spec, n_rows=1500, seed=1)
    out = ms.evaluate(df, spec, seed=1)
    assert list(out["recall"].columns) == TYPES
    assert {"zscore", "great_expectations", "isolation_forest", "drift", "transform_dedup"} <= set(
        out["recall"].index
    )
    assert out["recall"].loc["transform_dedup", "duplicate"] == 1.0
    assert out["recall"].loc["great_expectations", "missing_value"] == 1.0


def test_hypotheses_follow_the_preregistered_rules():
    methods = [
        "zscore",
        "iqr",
        "great_expectations",
        "isolation_forest",
        "ocsvm",
        "transform_dedup",
    ]
    base = pd.DataFrame(0.1, index=methods, columns=TYPES)
    base.loc["great_expectations", "missing_value"] = 1.0
    base.loc["transform_dedup", "duplicate"] = 1.0
    base.loc[["isolation_forest", "ocsvm"], "multivariate_outlier"] = 0.8
    base.loc["zscore", "multivariate_outlier"] = 0.0
    base.loc["iqr", "multivariate_outlier"] = 0.05
    h = ms.hypotheses({"a": base, "b": base + 0.01, "c": base.copy()})
    assert h["H1"]["supported"] and h["H2"]["supported"] and h["H3"]["supported"]
    assert h["H4"]["supported"] and h["H4"]["mean_spearman"] > 0.9
    broken = base.copy()
    broken.loc["great_expectations", "missing_value"] = 0.2
    assert not ms.hypotheses({"a": base, "b": broken})["H1"]["supported"]


def test_the_neural_mode_returns_only_the_neural_rows(spec, monkeypatch):
    seen = {}
    real = ms.capped

    def spy(train, name, seed):
        seen[name] = seed
        return real(train, name, seed)

    monkeypatch.setattr(ms, "capped", spy)
    monkeypatch.setattr(ms, "DEEP_NAMES", ["deep_svdd", "lunar"])
    df = ms.make(spec, n_rows=1500, seed=1)
    out = ms.evaluate(df, spec, seed=1, deep=True)
    assert list(out["recall"].index) == ["deep_svdd", "lunar"]
    assert seen == {"deep_svdd": 1, "lunar": 1}


def test_later_detectors_do_not_change_the_preregistered_hypotheses():
    methods = [
        "zscore",
        "iqr",
        "great_expectations",
        "isolation_forest",
        "ocsvm",
        "transform_dedup",
    ]
    base = pd.DataFrame(0.1, index=methods, columns=TYPES)
    base.loc["great_expectations", "missing_value"] = 1.0
    base.loc["transform_dedup", "duplicate"] = 1.0
    base.loc[["isolation_forest", "ocsvm"], "multivariate_outlier"] = 0.8
    base.loc["zscore", "multivariate_outlier"] = 0.0
    base.loc["iqr", "multivariate_outlier"] = 0.05
    extended = base.copy()
    extended.loc["knn"] = [0.0, 0.0, 0.9, 0.9, 0.9, 0.9]  # a stronger row on drift, not a core row
    before = ms.hypotheses({"a": base, "b": base + 0.01})
    after = ms.hypotheses({"a": extended, "b": extended + 0.01})
    assert before == after
