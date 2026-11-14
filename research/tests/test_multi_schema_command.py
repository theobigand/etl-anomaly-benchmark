# ruff: noqa: E501
"""The multi-schema command, the pass-through of the split and scoring, and the hypothesis limits."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multi_schema as ms  # noqa: E402

TYPES = list(ms.ANOMALY_TYPES)


def _run(seed, deep=False):
    value = 0.1 * (seed % 7) + 0.05
    recall = pd.DataFrame(value, index=["zscore", "iqr"], columns=TYPES)
    recall.loc["iqr"] = value / 2
    return {
        "recall": recall,
        "precision": recall + 0.5,
        "fpr": pd.Series({"zscore": 0.1, "iqr": 0.2}),
    }


@pytest.fixture
def stubbed(monkeypatch):
    seen = {"make": [], "evaluate": [], "printed": []}
    monkeypatch.setattr(
        ms,
        "make",
        lambda spec, rows, seed: seen["make"].append((spec.name, rows, seed)) or (spec.name, seed),
    )
    monkeypatch.setattr(
        ms,
        "evaluate",
        lambda df, spec, seed, deep: (
            seen["evaluate"].append((df, spec.name, seed, deep)) or _run(seed)
        ),
    )
    monkeypatch.setattr(ms, "published_customer", lambda: _run(1)["recall"])
    monkeypatch.setattr(ms, "hypotheses", lambda matrices: {"schemas": list(matrices)})
    monkeypatch.setattr(ms, "print", lambda *a, **k: seen["printed"].append((a, k)), raising=False)
    return seen


def test_the_defaults_are_twelve_thousand_rows_and_the_classical_sweep(tmp_path, stubbed):
    ms.main(["--output", str(tmp_path)])
    assert {rows for _, rows, _ in stubbed["make"]} == {12_000}
    assert {entry[3] for entry in stubbed["evaluate"]} == {False}
    assert "hypotheses" in json.loads((tmp_path / "multi_schema_results.json").read_text())


def test_each_schema_is_generated_and_evaluated_for_every_seed_with_the_table_it_made(
    tmp_path, stubbed
):
    ms.main(["--output", str(tmp_path), "--rows", "300"])
    assert stubbed["make"] == [(name, 300, seed) for name in ms.SCHEMAS for seed in ms.SEEDS]
    assert [(df, name, seed) for df, name, seed, _ in stubbed["evaluate"]] == [
        ((name, seed), name, seed) for name in ms.SCHEMAS for seed in ms.SEEDS
    ]


def test_every_seed_file_is_the_run_in_split_orientation_indented_by_one(tmp_path, stubbed):
    ms.main(["--output", str(tmp_path)])
    run = _run(42)
    expected = (
        json.dumps({k: json.loads(v.to_json(orient="split")) for k, v in run.items()}, indent=1)
        + "\n"
    )
    assert (tmp_path / "transactions_seed_42.json").read_text() == expected
    assert (tmp_path / "sensors_seed_1.json").read_text() == json.dumps(
        {k: json.loads(v.to_json(orient="split")) for k, v in _run(1).items()}, indent=1
    ) + "\n"


def test_the_mean_and_deviation_are_over_the_seeds_in_the_order_of_the_methods(tmp_path, stubbed):
    ms.main(["--output", str(tmp_path)])
    results = json.loads((tmp_path / "multi_schema_results.json").read_text())
    for table, key in (("mean", "transactions"), ("std", "transactions")):
        assert set(results[table][key]) == {"index", "columns", "data"}
        assert results[table][key]["index"] == ["zscore", "iqr"]
        assert results[table][key]["columns"] == TYPES
    zs = [_run(s)["recall"].loc["zscore", TYPES[0]] for s in ms.SEEDS]
    assert results["mean"]["transactions"]["data"][0][0] == pytest.approx(np.mean(zs))
    assert results["std"]["transactions"]["data"][0][0] == pytest.approx(np.std(zs, ddof=1))
    assert set(results["mean"]) == {"customer", "transactions", "sensors"}


def test_each_schema_name_is_printed_and_flushed(tmp_path, stubbed):
    ms.main(["--output", str(tmp_path)])
    assert stubbed["printed"] == [((name,), {"flush": True}) for name in ms.SCHEMAS]


def test_the_tables_are_in_markdown_with_two_decimals_closed_bars_and_a_blank_line_after_each(
    tmp_path, stubbed
):
    ms.main(["--output", str(tmp_path)])
    lines = (tmp_path / "multi_schema_results.md").read_text().split("\n")
    assert lines[0] == "### customer" and lines[1] == ""
    assert lines[2] == "| method | " + " | ".join(TYPES) + " |"
    assert lines[3] == "|---|" + "---|" * len(TYPES)
    first = _run(1)["recall"].loc["zscore"].iloc[0]
    assert lines[4] == "| zscore | " + " | ".join([f"{first:.2f}"] * len(TYPES)) + " |"
    assert lines[6] == "" and lines[7] == "### transactions"
    assert all(line.endswith(" |") for line in lines[4:6])


def test_the_method_choice_default_and_help_are_documented(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit) as stop:
        ms.main(["--output", "o", "--methods", "other"])
    assert stop.value.code == 2
    assert "invalid choice: 'other' (choose from 'classical', 'deep')" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        ms.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert (
        "--methods {classical,deep} the registry sweep with its hypotheses, or the neural detectors alone"
        in text
    )
    assert "--rows ROWS" in text


def test_the_deep_mode_hands_the_flag_to_every_evaluation(tmp_path, stubbed):
    ms.main(["--output", str(tmp_path), "--methods", "deep"])
    assert {entry[3] for entry in stubbed["evaluate"]} == {True}


def _matrices(multivariate_rule):
    base = pd.DataFrame(0.0, index=list(ms.CORE_ROWS), columns=TYPES)
    base.loc["great_expectations", "missing_value"] = 1.0
    base.loc["transform_dedup", "duplicate"] = 1.0
    base.loc[["isolation_forest", "ocsvm"], "multivariate_outlier"] = 0.5
    base.loc[["zscore", "iqr"], "multivariate_outlier"] = multivariate_rule
    return {"a": base.copy(), "b": base.copy()}


def test_h2_needs_the_rules_strictly_below_one_fifth_and_the_models_at_least_one_half():
    assert ms.hypotheses(_matrices(0.1))["H2"]["supported"] is True
    assert ms.hypotheses(_matrices(0.2))["H2"]["supported"] is False
    low = _matrices(0.1)
    low["a"].loc["isolation_forest", "multivariate_outlier"] = 0.49
    assert ms.hypotheses(low)["H2"]["by_schema"] == {"a": False, "b": True}


class _Scripted:
    """A generator that returns chosen values for the draws under test and delegates the others."""

    def __init__(self, temperature, noise):
        self._rng = np.random.default_rng(0)
        self._script = {4: np.array(temperature, float), 5: np.array(noise, float)}

    def normal(self, loc, scale, size=None):
        if scale in self._script:
            return self._script[scale]
        return self._rng.normal(loc, scale, size)

    def __getattr__(self, name):
        return getattr(self._rng, name)


def test_the_humidity_of_a_sensor_is_clipped_between_five_and_ninety_five_percent():
    rng = _Scripted([21 - 40, 21 + 60, 21, 21 - 10.6, 21 + 43.3], [0, 0, 0, 0, 0])
    frame = ms._sensors(5, rng, None)
    assert frame["humidity_pct"].tolist() == [95.0, 5.0, 70.0, 85.9, 5.05]


def test_a_default_table_is_twelve_thousand_rows_from_seed_forty_two():
    spec = ms.SCHEMAS["sensors"]
    default = ms.make(spec)
    explicit = ms.make(spec, 12_000, 42)
    pd.testing.assert_frame_equal(default, explicit)
    assert not default.equals(ms.make(spec, 12_000, 43))


def test_faker_is_seeded_with_the_seed_and_builds_the_american_english_locale(monkeypatch):
    import dataclasses

    seen = {}

    class Fake:
        def __init__(self, locale=None):
            seen["locale"] = locale

        @staticmethod
        def seed(value):
            seen["seed"] = value

    monkeypatch.setattr(ms, "Faker", Fake)
    spec = ms.SCHEMAS["sensors"]
    real = spec.clean

    def clean(n, rng, fake):
        seen["fake"] = fake
        return real(n, rng, fake)

    ms.make(dataclasses.replace(spec, clean=clean), 600, 7)
    assert seen["seed"] == 7 and seen["locale"] == "en_US" and isinstance(seen["fake"], Fake)


def test_the_strongest_severity_stops_at_the_ninety_nine_point_nine_quantile():
    spec = ms.SCHEMAS["sensors"]
    df = ms.make(spec, 600, 1, severity=100.0)
    a, b = spec.pair
    clean = df[df["anomaly_type"] == "clean"]
    top = max(clean[a].quantile(0.999), clean[b].quantile(0.999))
    values = df[df["anomaly_type"] == "multivariate_outlier"][[a, b]]
    assert values.max().max() == pytest.approx(top)


def test_a_group_is_a_duplicate_when_any_of_its_rows_is_and_strata_keep_first_appearance_order(
    monkeypatch,
):
    df = pd.DataFrame(
        {
            "customer_id": [9, 9, 3, 3, 5],
            "anomaly_type": ["clean", "duplicate", "missing_value", "clean", "temporal_drift"],
        }
    )
    spec = ms.SCHEMAS["transactions"]
    seen = {}

    def split(groups, column, ratios, seed):
        seen.update(groups=groups.copy(), column=column, ratios=ratios, seed=seed)
        return groups.iloc[:1], groups.iloc[1:2], groups.iloc[2:]

    monkeypatch.setattr(ms, "stratified_split", split)
    df = df.rename(columns={"customer_id": spec.id_col})
    ms._split(df, spec, 11)
    assert seen["groups"][spec.id_col].tolist() == [9, 3, 5]
    assert seen["groups"]["stratum"].tolist() == ["duplicate", "missing_value", "temporal_drift"]
    assert (
        seen["column"] == "stratum"
        and seen["ratios"] == ms.config.SPLIT_RATIOS
        and seen["seed"] == 11
    )


def test_recall_and_precision_count_clean_rows_as_the_only_negatives():
    types = pd.Series(["clean", "clean", "clean", "missing_value", "missing_value", "duplicate"])
    flags = pd.Series([False, True, False, True, False, True])
    recall, precision = ms._per_type(flags, types)
    assert recall["missing_value"] == pytest.approx(0.5)
    assert precision["missing_value"] == pytest.approx(0.5)
    assert recall["duplicate"] == 1.0 and precision["duplicate"] == pytest.approx(0.5)
    assert np.isnan(recall["univariate_outlier"]) and np.isnan(precision["univariate_outlier"])


def test_each_detector_is_built_with_the_training_prevalence_and_the_drift_monitor_with_its_columns(
    monkeypatch,
):
    spec = ms.SCHEMAS["sensors"]
    df = ms.make(spec, 600, 1)
    built, drift = [], {}
    monkeypatch.setattr(
        ms,
        "build",
        lambda name, contamination, seed: built.append((name, contamination, seed)) or name,
    )
    monkeypatch.setattr(ms, "capped", lambda frame, name, seed: frame)

    class Monitor:
        def __init__(self, **kwargs):
            drift.update(kwargs)

    monkeypatch.setattr(ms, "TemporalDriftDetector", Monitor)
    monkeypatch.setattr(
        ms,
        "detect",
        lambda frame, detector, fit_df: type("R", (), {"flags": np.zeros(len(frame), bool)})(),
    )
    train, _val, _test = ms._split(df, spec, 5)
    ms.evaluate(df, spec, 5)
    prevalence = float(train["anomaly"].mean())
    assert built and all(c == prevalence and s == 5 for _, c, s in built)
    assert [n for n, _, _ in built] == list(ms.DETECTOR_NAMES)
    assert drift == {"time_column": spec.date_col, "columns": spec.numeric}
