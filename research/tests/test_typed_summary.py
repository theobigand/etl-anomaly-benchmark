"""Pooled summary of the typed heatmaps and the pre-registered hypothesis checks."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_summary as ts  # noqa: E402

METHODS = [
    "zscore",
    "iqr",
    "great_expectations",
    "isolation_forest",
    "lof",
    "ocsvm",
    "drift",
    "transform_dedup",
]
TYPES = [
    "missing_value",
    "duplicate",
    "univariate_outlier",
    "multivariate_outlier",
    "temporal_drift",
    "invalid_format",
]


def _matrix(**cells):
    m = pd.DataFrame(0.0, index=METHODS, columns=TYPES)
    for key, value in cells.items():
        method, kind = key.split("__")
        m.loc[method, kind] = value
    return m


def _pattern(shift=0.0):
    return _matrix(
        great_expectations__missing_value=1.0,
        transform_dedup__duplicate=1.0,
        zscore__univariate_outlier=0.9 - shift,
        iqr__univariate_outlier=0.95,
        isolation_forest__univariate_outlier=0.95,
        lof__univariate_outlier=0.8,
        ocsvm__univariate_outlier=0.95,
        isolation_forest__multivariate_outlier=0.8 - shift,
        ocsvm__multivariate_outlier=0.8,
        lof__temporal_drift=0.4,
        iqr__invalid_format=1.0,
    )


def test_median_matrix_and_interval_are_taken_over_datasets():
    data = {f"d{i}": _pattern(0.1 * i) for i in range(5)}
    out = ts.pooled(data, resamples=300)
    assert out["median"].loc["zscore", "univariate_outlier"] == 0.9 - 0.2
    low, high = out["low"], out["high"]
    assert (low <= out["median"] + 1e-12).all().all() and (
        out["median"] <= high + 1e-12
    ).all().all()


def test_identical_matrices_are_perfectly_stable_and_noise_lowers_the_score():
    same = {f"d{i}": _pattern() for i in range(4)}
    assert ts.stability(same)["overall"] == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    noisy = {
        f"d{i}": pd.DataFrame(rng.random((8, 6)), index=METHODS, columns=TYPES) for i in range(4)
    }
    assert ts.stability(noisy)["overall"] < 0.5


def test_per_type_stability_flags_a_type_whose_ranking_changes_between_datasets():
    a, b = _pattern(), _pattern()
    b["multivariate_outlier"] = b["multivariate_outlier"].iloc[::-1].to_numpy()
    out = ts.stability({"a": a, "b": b})
    assert out["per_type"]["missing_value"] == pytest.approx(1.0)
    assert out["per_type"]["multivariate_outlier"] < out["per_type"]["missing_value"]


def test_hypotheses_are_evaluated_against_the_preregistered_thresholds():
    data = {f"d{i}": _pattern() for i in range(5)}
    result = ts.hypotheses(data, n_columns={f"d{i}": 4 + i for i in range(5)})
    assert result["H1"]["holds"] is True  # zscore 0.9, iqr 0.95, ML above 0.7
    assert result["H3"]["holds"] is True  # best drift recall 0.4 < 0.5
    failing = {k: _pattern() for k in "abc"}
    for m in failing.values():
        m.loc["great_expectations", "missing_value"] = 0.5
    assert ts.hypotheses(failing, n_columns={"a": 4, "b": 5, "c": 6})["H1"]["holds"] is False


def test_the_summary_cli_reads_run_files_and_writes_results_and_a_table(tmp_path):
    import json

    runs = tmp_path / "runs"
    runs.mkdir()
    for i in range(3):
        m = _pattern(0.05 * i)
        (runs / f"{i}.json").write_text(
            json.dumps(
                {
                    "name": f"d{i}",
                    "carrier": {"columns": list("abcd")[: 4 + (i % 1)]},
                    "recall_mean": json.loads(m.to_json(orient="split")),
                    "fpr_mean": {"iqr": 0.2 + 0.1 * i, "zscore": 0.0},
                }
            )
        )
    out = tmp_path / "out"
    assert ts.main(["--runs", str(runs), "--output", str(out)]) == 0
    results = json.loads((out / "typed_results.json").read_text())
    assert set(results["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"} and results["datasets"] == 3
    assert results["fpr"]["iqr"] == {"median": pytest.approx(0.3), "max": pytest.approx(0.4)}
    text = (out / "typed_results.md").read_text()
    assert "great_expectations" in text and "false positive rate" in text


def test_the_figures_script_writes_the_pooled_and_the_small_multiples_png(tmp_path):
    import json

    import typed_figures as tf

    runs = tmp_path / "runs"
    runs.mkdir()
    for uci_id in range(1, 9):
        m = _pattern(0.01 * uci_id)
        (runs / f"{uci_id}.json").write_text(
            json.dumps(
                {
                    "uci_id": uci_id,
                    "name": f"d{uci_id}",
                    "carrier": {"columns": list("abcd")},
                    "recall_mean": json.loads(m.to_json(orient="split")),
                }
            )
        )
    out = tmp_path / "fig"
    assert tf.main(["--runs", str(runs), "--output", str(out), "--panels", "6"]) == 0
    assert (out / "typed_pooled.png").stat().st_size > 1000
    assert (out / "typed_panels.png").stat().st_size > 1000


def test_the_runs_of_several_folders_are_pooled_into_one_summary(tmp_path):
    import json

    def run(folder, name, value):
        folder.mkdir(exist_ok=True)
        frame = {"index": ["zscore"], "columns": ["univariate_outlier"], "data": [[value]]}
        payload = {"name": name, "recall_mean": frame, "carrier": {"columns": ["a", "b"]}}
        (folder / f"{name}.json").write_text(json.dumps(payload))

    run(tmp_path / "a", "first", 0.2)
    run(tmp_path / "b", "second", 0.6)
    data, columns, _ = ts._load([tmp_path / "a", tmp_path / "b"])
    assert sorted(data) == ["first", "second"] and columns == {"first": 2, "second": 2}
    assert len(ts._load(tmp_path / "a")[0]) == 1
