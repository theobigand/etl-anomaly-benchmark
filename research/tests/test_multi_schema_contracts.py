"""Pinned generators, split, scoring routing, hypotheses and command of the multi-schema study.

The generated tables do not read Faker, so their digests do not depend on its version.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multi_schema as ms  # noqa: E402


def _digest(frame):
    h = hashlib.sha256()
    numeric = frame.select_dtypes("number").columns
    h.update(np.nan_to_num(frame[numeric].to_numpy(float), nan=-12345.678).round(9).tobytes())
    for column in frame.columns:
        if column not in numeric and column != "anomaly":
            h.update("|".join(map(str, frame[column])).encode())
    if "anomaly" in frame:
        h.update(frame["anomaly"].to_numpy().astype("int8").tobytes())
    return h.hexdigest()


def test_dates_are_the_reference_minus_days_and_hours_in_the_requested_format():
    out = ms._dates(4, np.random.default_rng(1), "%Y-%m-%d %H")
    assert out == ["2024-12-12 00", "2024-11-02 21", "2024-03-03 05", "2023-08-19 02"]
    assert pd.Timestamp("2026-06-30") == ms.REFERENCE


def test_the_two_clean_generators_are_pinned_for_a_fixed_generator():
    tx = ms._transactions(200, np.random.default_rng(5), None)
    assert _digest(tx) == "9dcdd7e96f1e67453971513b3200d93a4ad6d9e345ef69b327141a13eee1ffb4"
    assert list(tx.columns)[-3:] == ["txn_date", "reference", "currency"]
    se = ms._sensors(200, np.random.default_rng(5), None)
    assert _digest(se) == "c2a2226300d71463a57f688753d472dff24c219b19b6b39776bf9c8c8a154369"
    assert set(se["site"]) <= {"north", "south", "east", "west", "depot"}
    assert se["humidity_pct"].between(5, 95).all() and (tx["balance_after"] >= 0).all()


@pytest.mark.parametrize(
    ("name", "reference", "doubled"),
    [
        (
            "transactions",
            "54745b4b0aba8ee14ea5087439d5f5f89935f99fad08366c41a90efab883e045",
            "149756ef64238a739608358166da42e81b0224d530f7ab454772817bd65f7093",
        ),
        (
            "sensors",
            "a8e5ed68c1d44446ce26d8ab174dfa4098267c62ab718bc8cb3d2b4d1de41306",
            "c229e5722301411c0f30246437becc55aefb862cd379a54b6e16f4a6c1903f42",
        ),
    ],
)
def test_the_injected_table_is_pinned_at_the_reference_and_at_a_doubled_severity(
    name, reference, doubled
):
    spec = ms.SCHEMAS[name]
    assert _digest(ms.make(spec, 300, 3)) == reference
    assert _digest(ms.make(spec, 300, 3, severity=2.0)) == doubled


def test_invalid_generator_parameters_are_refused():
    spec = ms.SCHEMAS["transactions"]
    for arguments in (
        {"n_rows": 89},
        {"anomaly_rate": 0.0},
        {"anomaly_rate": 0.2},
        {"severity": 0.0},
    ):
        with pytest.raises(ValueError) as refused:
            ms.make(spec, **{"n_rows": 300, **arguments})
        assert str(refused.value) == "invalid generator parameters"
    with pytest.raises(ValueError) as refused:
        ms.make(spec, n_rows=100, anomaly_rate=1 / 6)
    assert str(refused.value) == "n_rows cannot hold six anomaly groups of the requested size"
    assert len(ms.make(spec, n_rows=90, anomaly_rate=0.01)) == 90 + 15


def test_the_split_keeps_each_identity_in_one_part_and_stratifies_on_duplicates():
    spec = ms.SCHEMAS["sensors"]
    df = ms.make(spec, 600, 2)
    train, val, test = ms._split(df, spec, 2)
    sets = [set(part[spec.id_col]) for part in (train, val, test)]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    assert sum(len(part) for part in (train, val, test)) == len(df)
    for part in (train, val, test):
        assert part.index.tolist() == list(range(len(part)))
        assert list(part.columns) == list(df.columns)


def test_per_type_scores_use_the_clean_rows_as_the_negative_class():
    types = pd.Series(["clean", "clean", "clean", "missing_value", "missing_value", "duplicate"])
    flags = pd.Series([True, False, False, True, False, True])
    recall, precision = ms._per_type(flags, types)
    assert recall["missing_value"] == 0.5 and precision["missing_value"] == pytest.approx(0.5)
    assert recall["duplicate"] == 1.0 and precision["duplicate"] == pytest.approx(0.5)
    assert np.isnan(recall["univariate_outlier"]) and np.isnan(precision["univariate_outlier"])
    assert set(recall) == set(ms.ANOMALY_TYPES)
    never = ms._per_type(
        pd.Series([False] * 4), pd.Series(["clean", "clean", "missing_value", "clean"])
    )
    assert never[1]["missing_value"] == 0.0


class _Detector:
    def __init__(self, tag):
        self.tag = tag


def _stub(monkeypatch, calls):
    monkeypatch.setattr(
        ms,
        "build",
        lambda name, contamination, seed: (
            calls.append(("build", name, contamination, seed)) or _Detector(name)
        ),
    )
    monkeypatch.setattr(
        ms, "capped", lambda frame, name, seed: calls.append(("capped", name, seed)) or frame
    )

    class Result:
        def __init__(self, flags):
            self.flags = flags

    def detect(test_x, detector, fit_df):
        calls.append(("detect", type(detector).__name__, list(test_x.columns), len(fit_df)))
        return Result(pd.Series([True, False] * (len(test_x) // 2) + [False] * (len(test_x) % 2)))

    monkeypatch.setattr(ms, "detect", detect)


def test_the_classical_sweep_builds_every_registry_detector_adds_drift_and_the_dedup_rule(
    monkeypatch,
):
    calls = []
    _stub(monkeypatch, calls)
    spec = ms.SCHEMAS["transactions"]
    df = ms.make(spec, 600, 4)
    out = ms.evaluate(df, spec, 4)
    train, _, test = ms._split(df, spec, 4)
    names = [*ms.DETECTOR_NAMES, "drift", "transform_dedup"]
    assert out["recall"].index.tolist() == names and out["precision"].index.tolist() == names
    assert list(out["recall"].columns) == ms.ANOMALY_TYPES
    assert out["fpr"].index.tolist() == names
    built = [c for c in calls if c[0] == "build"]
    contamination = float(train["anomaly"].mean())
    assert built == [("build", n, contamination, 4) for n in ms.DETECTOR_NAMES]
    detected = [c for c in calls if c[0] == "detect"]
    assert all(c[2] == ms.features(spec) and c[3] == len(train) for c in detected)
    dedup = test.duplicated(subset=ms.features(spec), keep=False)
    clean = test["anomaly_type"] == "clean"
    assert out["fpr"]["transform_dedup"] == float(dedup[clean].mean())
    assert out["recall"].loc["transform_dedup", "duplicate"] == 1.0


def test_the_neural_mode_builds_only_the_neural_detectors(monkeypatch):
    calls = []
    _stub(monkeypatch, calls)
    spec = ms.SCHEMAS["sensors"]
    out = ms.evaluate(ms.make(spec, 600, 4), spec, 4, deep=True)
    assert out["recall"].index.tolist() == list(ms.DEEP_NAMES)
    assert [c[1] for c in calls if c[0] == "build"] == list(ms.DEEP_NAMES)
    assert [c[1:] for c in calls if c[0] == "capped"] == [(n, 4) for n in ms.DEEP_NAMES]


def _matrix(**cells):
    methods = list(ms.CORE_ROWS) + ["ecod"]
    frame = pd.DataFrame(0.25, index=methods, columns=ms.ANOMALY_TYPES)
    for key, value in cells.items():
        method, kind = key.split("__")
        frame.loc[method, kind] = value
    return frame


def _good(**overrides):
    cells = {
        "great_expectations__missing_value": 0.9,
        "transform_dedup__duplicate": 0.9,
        "isolation_forest__multivariate_outlier": 0.5,
        "ocsvm__multivariate_outlier": 0.5,
        "zscore__multivariate_outlier": 0.125,
        "iqr__multivariate_outlier": 0.125,
    }
    return _matrix(**{**cells, **overrides})


def test_h1_and_h2_apply_their_inclusive_and_strict_limits_per_schema():
    out = ms.hypotheses({"a": _good(), "b": _good()})
    assert out["H1"] == {"supported": True, "by_schema": {"a": True, "b": True}}
    assert out["H2"] == {"supported": True, "by_schema": {"a": True, "b": True}}
    low = _good(great_expectations__missing_value=0.875)
    assert ms.hypotheses({"a": low, "b": _good()})["H1"]["by_schema"] == {"a": False, "b": True}
    dedup = _good(transform_dedup__duplicate=0.875)
    assert ms.hypotheses({"a": dedup})["H1"]["supported"] is False
    weak = _good(ocsvm__multivariate_outlier=0.4375)
    assert ms.hypotheses({"a": weak})["H2"]["supported"] is False
    rule = _good(iqr__multivariate_outlier=0.25)
    assert ms.hypotheses({"a": rule})["H2"]["supported"] is False
    edge_rule = _good(zscore__multivariate_outlier=0.1875)
    assert ms.hypotheses({"a": edge_rule})["H2"]["supported"] is True


def test_h3_looks_only_at_the_preregistered_rows_and_stays_below_six_tenths():
    base = _good(ecod__temporal_drift=0.9, drift__temporal_drift=0.5)
    out = ms.hypotheses({"a": base})["H3"]
    assert out == {"supported": True, "best_drift_recall": {"a": 0.5}}
    high = _good(zscore__temporal_drift=0.625)
    assert ms.hypotheses({"a": high})["H3"] == {
        "supported": False,
        "best_drift_recall": {"a": 0.625},
    }
    at = _good(zscore__temporal_drift=0.6)
    assert ms.hypotheses({"a": at})["H3"]["supported"] is False


def test_h4_is_the_mean_rank_agreement_over_pairs_without_the_drift_row():
    rng = np.random.default_rng(0)
    a, b = _good(), _good()
    values = rng.random((len(ms.CORE_ROWS) + 1, len(ms.ANOMALY_TYPES)))
    a.iloc[:, :] = values
    b.iloc[:, :] = values
    b.loc["drift"] = 0.0
    out = ms.hypotheses({"a": a, "b": b})["H4"]
    assert out["pairs"] == {"a|b": pytest.approx(1.0)}
    assert out["mean_spearman"] == pytest.approx(1.0) and out["supported"] is True
    c = a.copy()
    c.iloc[:, :] = values[::-1]
    anti = ms.hypotheses({"a": a, "c": c})["H4"]
    assert anti["supported"] is False and set(anti["pairs"]) == {"a|c"}


def test_the_published_customer_matrix_keeps_the_mean_columns_under_the_type_names():
    frame = ms.published_customer()
    assert list(frame.columns) == ms.ANOMALY_TYPES and "zscore" in frame.index


def _fake_run(seed, deep=False):
    recall = pd.DataFrame(0.25 * (seed % 4), index=["zscore", "iqr"], columns=ms.ANOMALY_TYPES)
    return {
        "recall": recall,
        "precision": recall + 0.5,
        "fpr": pd.Series({"zscore": 0.1, "iqr": 0.2}),
    }


def test_the_command_writes_each_seed_the_means_the_hypotheses_and_the_tables(
    tmp_path, monkeypatch, capsys
):
    seen = []
    monkeypatch.setattr(
        ms,
        "make",
        lambda spec, rows, seed: seen.append((spec.name, rows, seed)) or (spec.name, seed),
    )
    monkeypatch.setattr(ms, "evaluate", lambda df, spec, seed, deep: _fake_run(seed, deep))
    monkeypatch.setattr(ms, "published_customer", lambda: _fake_run(1)["recall"])
    monkeypatch.setattr(ms, "hypotheses", lambda matrices: {"names": list(matrices)})
    out = tmp_path / "new" / "o"
    assert ms.main(["--output", str(out), "--rows", "500"]) == 0
    assert seen[0] == ("transactions", 500, 42) and len(seen) == 2 * len(ms.SEEDS)
    assert capsys.readouterr().out.splitlines() == ["transactions", "sensors"]
    for name in ms.SCHEMAS:
        for seed in ms.SEEDS:
            payload = json.loads((out / f"{name}_seed_{seed}.json").read_text())
            assert set(payload) == {"recall", "precision", "fpr"}
    text = (out / "multi_schema_results.json").read_text()
    results = json.loads(text)
    assert text == json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert set(results) == {"mean", "std", "hypotheses"}
    assert results["hypotheses"] == {"names": ["customer", "transactions", "sensors"]}
    assert set(results["mean"]) == {"customer", "transactions", "sensors"}
    assert set(results["std"]) == {"transactions", "sensors"}
    lines = (out / "multi_schema_results.md").read_text().splitlines()
    assert lines[0] == "### customer" and lines[1] == ""
    assert lines[2] == "| method | " + " | ".join(ms.ANOMALY_TYPES) + " |"
    assert lines[3] == "|---|" + "---|" * len(ms.ANOMALY_TYPES)
    assert lines[4].startswith("| zscore | 0.25 |")


def test_the_neural_mode_skips_the_hypotheses_and_the_published_matrix(tmp_path, monkeypatch):
    flags = []
    monkeypatch.setattr(ms, "make", lambda spec, rows, seed: None)
    monkeypatch.setattr(
        ms, "evaluate", lambda df, spec, seed, deep: flags.append(deep) or _fake_run(seed)
    )
    monkeypatch.setattr(ms, "published_customer", lambda: pytest.fail("customer read"))
    assert ms.main(["--output", str(tmp_path), "--methods", "deep"]) == 0
    assert set(flags) == {True}
    results = json.loads((tmp_path / "multi_schema_results.json").read_text())
    assert set(results) == {"mean", "std"} and "customer" not in results["mean"]
    flags.clear()
    monkeypatch.setattr(ms, "published_customer", lambda: _fake_run(1)["recall"])
    monkeypatch.setattr(ms, "hypotheses", lambda matrices: {})
    ms.main(["--output", str(tmp_path / "c"), "--rows", "100"])
    assert set(flags) == {False}
    with pytest.raises(SystemExit) as stop:
        ms.main([])
    assert stop.value.code == 2
