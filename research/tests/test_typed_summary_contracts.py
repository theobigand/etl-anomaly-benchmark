"""Thresholds, exact outputs and the command of the typed pooled summary."""

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_typed_summary import METHODS, TYPES, _matrix, _pattern

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_summary as ts  # noqa: E402


def _data(*matrices):
    return {f"d{i}": m for i, m in enumerate(matrices)}


def _h(matrix):
    return ts.hypotheses(_data(matrix, matrix), {"d0": 4, "d1": 4})


def test_h1_thresholds_are_inclusive_for_expectations_and_strict_for_the_others():
    base = dict(
        great_expectations__missing_value=0.9,
        zscore__univariate_outlier=0.75, iqr__univariate_outlier=0.75,
        isolation_forest__univariate_outlier=0.75, lof__univariate_outlier=0.75,
        ocsvm__univariate_outlier=0.75,
    )  # fmt: skip
    out = _h(_matrix(**base))["H1"]
    assert out["holds"] is True and out["ge_missing_min"] == 0.9
    assert out["other_duplicate_max"] == 0.0
    assert out["univariate_median"] == {
        m: 0.75 for m in ("zscore", "iqr", "isolation_forest", "lof", "ocsvm")
    }
    assert (
        _h(_matrix(**{**base, "great_expectations__missing_value": 0.875}))["H1"]["holds"] is False
    )
    assert _h(_matrix(**base, zscore__duplicate=0.9))["H1"]["holds"] is False
    assert _h(_matrix(**base, transform_dedup__duplicate=1.0))["H1"]["holds"] is True
    assert _h(_matrix(**{**base, "lof__univariate_outlier": 0.7}))["H1"]["holds"] is False
    assert _h(_matrix(**base, zscore__duplicate=0.8))["H1"]["other_duplicate_max"] == 0.8


def test_h2_needs_a_gap_of_at_least_four_tenths_and_both_rules_below_two_tenths():
    base = dict(
        isolation_forest__multivariate_outlier=0.5, ocsvm__multivariate_outlier=0.5,
        zscore__multivariate_outlier=0.1, iqr__multivariate_outlier=0.1,
    )  # fmt: skip
    out = _h(_matrix(**base))["H2"]
    assert out["holds"] is True and out["gap"] == pytest.approx(0.4)
    assert out["median"] == {"isolation_forest": 0.5, "ocsvm": 0.5, "zscore": 0.1, "iqr": 0.1}
    weaker = {**base, "ocsvm__multivariate_outlier": 0.4375}
    assert _h(_matrix(**weaker))["H2"]["holds"] is False
    edge = {
        **base,
        "isolation_forest__multivariate_outlier": 0.75,
        "ocsvm__multivariate_outlier": 0.75,
    }
    assert _h(_matrix(**{**edge, "zscore__multivariate_outlier": 0.2}))["H2"]["holds"] is False
    assert _h(_matrix(**{**edge, "iqr__multivariate_outlier": 0.2}))["H2"]["holds"] is False
    assert _h(_matrix(**edge))["H2"]["holds"] is True


def test_h3_needs_every_method_strictly_below_one_half_on_drift():
    out = _h(_matrix(lof__temporal_drift=0.25))["H3"]
    assert out["holds"] is True and set(out["median"]) == set(METHODS)
    assert out["median"]["lof"] == 0.25
    assert _h(_matrix(lof__temporal_drift=0.5))["H3"]["holds"] is False


@pytest.mark.parametrize(
    ("overall", "hard", "easy", "holds"),
    [
        (0.7, 0.2, 0.5, True),
        (0.6875, 0.2, 0.5, False),
        (0.9, 0.5, 0.5, False),
        (0.9, 0.6, 0.5, False),
    ],
)
def test_h4_needs_overall_stability_of_seven_tenths_and_hard_types_below_easy_ones(
    monkeypatch, overall, hard, easy, holds
):
    per_type = {k: easy for k in ts.STRUCTURAL} | {
        "multivariate_outlier": hard,
        "temporal_drift": 0.0,
        "univariate_outlier": 0.0,
    }
    stability = {"overall": overall, "per_type": per_type}
    monkeypatch.setattr(ts, "stability", lambda data: stability)
    out = _h(_pattern())["H4"]
    assert out["holds"] is holds and out["stability"] is stability


def test_h5_is_a_negative_rank_correlation_between_columns_and_univariate_recall():
    matrices = {}
    for name, recall in (("a", 0.9), ("b", 0.6), ("c", 0.3), ("ignored", 0.0)):
        matrices[name] = _matrix(isolation_forest__univariate_outlier=recall)
    out = ts.hypotheses(matrices, {"a": 4, "b": 8, "c": 16})["H5"]
    assert out["holds"] is True and out["rho"] == pytest.approx(-1.0)
    up = ts.hypotheses(matrices, {"a": 16, "b": 8, "c": 4})["H5"]
    assert up["holds"] is False and up["rho"] == pytest.approx(1.0)


def test_pooled_defaults_and_the_bootstrap_follow_their_definition():
    signature = inspect.signature(ts.pooled)
    assert signature.parameters["resamples"].default == 2000
    assert signature.parameters["seed"].default == 0
    frames = [
        pd.DataFrame([[v, 1.0 - v]], index=["m"], columns=["a", "b"]) for v in (0.0, 0.5, 1.0)
    ]
    data = {f"d{i}": f for i, f in enumerate(frames)}
    out = ts.pooled(data, resamples=40, seed=3)
    stack = np.stack([f.to_numpy() for f in frames])
    rng = np.random.default_rng(3)
    boot = np.stack([np.nanmedian(stack[rng.integers(0, 3, 3)], axis=0) for _ in range(40)])
    assert out["median"].to_numpy().tolist() == [[0.5, 0.5]]
    assert np.allclose(out["low"].to_numpy(), np.nanpercentile(boot, 2.5, axis=0))
    assert np.allclose(out["high"].to_numpy(), np.nanpercentile(boot, 97.5, axis=0))
    assert out["low"].index.tolist() == ["m"] and out["low"].columns.tolist() == ["a", "b"]
    assert set(out) == {"median", "low", "high"}


def test_missing_cells_do_not_pull_the_median_and_are_kept_as_nan_in_a_cell():
    first = pd.DataFrame([[np.nan, 0.2]], index=["m"], columns=["a", "b"])
    second = pd.DataFrame([[0.6, 0.4]], index=["m"], columns=["a", "b"])
    out = ts.pooled({"x": first, "y": second}, resamples=5)
    assert out["median"].loc["m", "a"] == 0.6
    cell = ts._cell({"x": first, "y": second}, "m", "a")
    assert cell.dtype == np.float64 and np.isnan(cell[0]) and cell[1] == 0.6


def test_mean_rank_correlation_skips_constant_vectors_and_averages_the_pairs():
    up, down, flat = np.arange(5.0), np.arange(5.0)[::-1], np.ones(5)
    assert ts._mean_rank_correlation([up, up]) == pytest.approx(1.0)
    assert ts._mean_rank_correlation([up, down]) == pytest.approx(-1.0)
    assert ts._mean_rank_correlation([up, up, down]) == pytest.approx((1 - 1 - 1) / 3)
    assert ts._mean_rank_correlation([up, flat, up]) == pytest.approx(1.0)
    assert np.isnan(ts._mean_rank_correlation([flat, flat]))
    assert np.isnan(ts._mean_rank_correlation([up]))
    assert np.isnan(ts._mean_rank_correlation([flat, up]))


def test_stability_reports_the_overall_and_per_type_rank_agreement():
    a = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=["m", "n"], columns=["t1", "t2"])
    b = pd.DataFrame([[2.0, 1.0], [4.0, 3.0]], index=["m", "n"], columns=["t1", "t2"])
    out = ts.stability({"a": a, "b": b})
    assert set(out) == {"overall", "per_type"} and list(out["per_type"]) == ["t1", "t2"]
    assert out["per_type"]["t1"] == pytest.approx(1.0)
    assert out["overall"] == pytest.approx(
        ts._mean_rank_correlation([a.to_numpy().ravel(), b.to_numpy().ravel()])
    )


def _write_run(folder, name, matrix, columns, fpr=None):
    payload = {
        "name": name,
        "carrier": {"columns": columns},
        "recall_mean": json.loads(matrix.to_json(orient="split")),
    }
    if fpr is not None:
        payload["fpr_mean"] = fpr
    (folder / f"{name}.json").write_text(json.dumps(payload))


def test_the_loader_reads_sorted_files_of_every_folder_and_tolerates_a_missing_rate(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    _write_run(one, "b", _matrix(), list("abc"), {"iqr": 0.1})
    _write_run(two, "a", _matrix(), list("ab"), {"iqr": 0.3, "zscore": 0.0})
    _write_run(two, "c", _matrix(), list("abcd"))
    data, columns, fpr = ts._load([one, two])
    assert list(data) == ["b", "a", "c"] and columns == {"b": 3, "a": 2, "c": 4}
    assert fpr == {"iqr": [0.1, 0.3], "zscore": [0.0]}
    assert list(data["b"].index) == METHODS and list(data["b"].columns) == TYPES
    single, _, _ = ts._load(one)
    assert list(single) == ["b"]


def test_the_command_writes_the_json_and_the_markdown_table_and_reports_the_dataset_count(
    tmp_path, capsys
):
    runs = tmp_path / "runs"
    runs.mkdir()
    for i in range(2):
        _write_run(runs, f"d{i}", _pattern(), list("abcd"), {"iqr": 0.25 * (i + 1), "zscore": 0.0})
    out = tmp_path / "new" / "out"
    assert ts.main(["--runs", str(runs), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "2 datasets\n"
    text = (out / "typed_results.json").read_text()
    results = json.loads(text)
    assert text == json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert set(results) == {"datasets", "median", "low", "high", "stability", "hypotheses", "fpr"}
    assert results["fpr"]["iqr"] == {"median": 0.375, "max": 0.5}
    lines = (out / "typed_results.md").read_text().splitlines()
    assert (
        lines[0] == "Median recall over 2 datasets (95% interval over datasets)" and lines[1] == ""
    )
    assert lines[2] == "| method | " + " | ".join(TYPES) + " |"
    assert lines[3] == "|---|" + "---|" * len(TYPES)
    ge = next(line for line in lines if line.startswith("| great_expectations |"))
    assert ge.startswith("| great_expectations | 1.00 [1.00, 1.00] |")
    assert lines[-5:] == [
        "",
        "Clean-row false positive rate (median and maximum over datasets)",
        "",
        "- iqr: 0.375 (max 0.500)",
        "- zscore: 0.000 (max 0.000)",
    ]
    with pytest.raises(SystemExit) as stop:
        ts.main([])
    assert stop.value.code == 2
