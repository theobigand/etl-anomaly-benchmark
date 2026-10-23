"""Offline experiment entry points write only inside an explicit result directory."""

import gzip
import io
import json
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl_benchmark.datasets import DATASETS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
pytestmark = pytest.mark.end_to_end


def _run(script, *args):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "experiments" / script), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-1500:]
    return completed


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--detectors", "unknown"), "detectors not eligible"),
        (("--fit-sample", "0"), "must be positive"),
        (("--calibration", "fixed"), "fixed contamination"),
        (("--calibration", "fixed", "--fixed-contamination", "0.9"), "fixed contamination"),
        (("--fixed-contamination", "0.02"), "requires --calibration fixed"),
    ],
)
def test_real_benchmark_cli_rejects_invalid_calibration_and_selection(args, message):
    result = subprocess.run(
        [sys.executable, str(ROOT / "experiments/run_benchmark.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert message in result.stderr


def test_real_benchmark_cli_on_tiny_local_csv(tmp_path):
    csv = tmp_path / "toy.csv"
    values = np.arange(200, dtype=float)
    pd.DataFrame({"V1": values, "Class": [0] * 180 + [1] * 20}).to_csv(csv, index=False)
    output = tmp_path / "out"
    _run(
        "run_benchmark.py",
        "--dataset",
        "credit_card",
        "--csv",
        csv,
        "--detectors",
        "zscore",
        "--seeds",
        1,
        "--results-dir",
        output,
    )
    table = pd.read_csv(next(output.glob("benchmark_*.csv")))
    assert table["detector"].tolist() == ["zscore"]
    assert (output / next(output.glob("benchmark_*.md")).name).is_file()
    record = json.loads(next(output.glob("run_benchmark_*.json")).read_text())
    assert record["seeds"] == [1]
    assert record["settings"]["detectors"] == ["zscore"]
    ineligible = f"ineligible: {DATASETS['credit_card'].note}"
    assert record["settings"]["not_run"] == {
        "iqr": "not requested",
        "great_expectations": "not requested",
        "isolation_forest": "not requested",
        "lof": ineligible,
        "ocsvm": ineligible,
        "ecod": "not requested",
        "copod": "not requested",
        "hbos": "not requested",
        "knn": ineligible,
        "pca": "not requested",
    }
    split_archive = next(output.glob("split_ids_*.json.gz"))
    with gzip.open(split_archive, "rt") as stream:
        splits = json.load(stream)
    assert splits["row_count"] == len(values)
    assert sorted(sum(splits["seeds"]["1"].values(), [])) == list(range(len(values)))
    assert split_archive.name in record["outputs"]


def test_real_benchmark_cli_records_fixed_calibration(tmp_path):
    csv = tmp_path / "toy.csv"
    pd.DataFrame({"V1": np.arange(200), "Class": [0] * 180 + [1] * 20}).to_csv(csv, index=False)
    output = tmp_path / "out"
    _run(
        "run_benchmark.py",
        "--dataset",
        "credit_card",
        "--csv",
        csv,
        "--detectors",
        "zscore",
        "--seeds",
        1,
        "--results-dir",
        output,
        "--calibration",
        "fixed",
        "--fixed-contamination",
        0.02,
    )
    settings = json.loads(next(output.glob("run_benchmark_*.json")).read_text())["settings"]
    assert settings["calibration"] == "fixed"
    assert settings["fixed_contamination"] == 0.02


def test_synthetic_generation_is_repeatable_and_has_declared_types(tmp_path):
    first = tmp_path / "first.csv"
    again = tmp_path / "again.csv"
    changed = tmp_path / "changed.csv"
    for output, seed in ((first, 7), (again, 7), (changed, 8)):
        _run("generate_synthetic.py", "--output", output, "--rows", 120, "--seed", seed)
    assert first.read_bytes() == again.read_bytes()
    assert first.read_bytes() != changed.read_bytes()
    frame = pd.read_csv(first)
    assert len(frame) >= 120
    assert {"clean", "univariate_outlier", "missing_value"} <= set(frame.anomaly_type)


def test_generation_commands_reject_impossible_population(tmp_path, monkeypatch):
    import generate_synthetic
    import run_severity

    output = tmp_path / "invalid.csv"
    monkeypatch.setattr(
        sys, "argv", ["generate_synthetic", "--rows", "10", "--output", str(output)]
    )
    with pytest.raises(ValueError, match="at least 90"):
        generate_synthetic.main()
    assert not output.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_severity",
            "--rows",
            "10",
            "--severities",
            "1",
            "--seeds",
            "1",
            "--results-dir",
            str(tmp_path / "results"),
        ],
    )
    with pytest.raises(ValueError, match="at least 90"):
        run_severity.main()
    assert not (tmp_path / "results").exists()


def test_pipeline_demo_writes_sorted_rows_to_configured_directory(tmp_path, monkeypatch):
    from etl_benchmark import config

    source = tmp_path / "input.csv"
    pd.DataFrame({"V1": [0.0, 1.0, 2.0, 100.0], "Class": [0, 0, 0, 1]}).to_csv(source, index=False)
    output = tmp_path / "out"
    monkeypatch.setattr(config, "RESULTS_DIR", output)
    monkeypatch.setattr(sys, "argv", ["etl-benchmark", "--input", str(source), "--detector", "iqr"])
    runpy.run_module("etl_benchmark", run_name="__main__")
    clean = pd.read_csv(output / "pipeline_clean.csv")
    anomalies = pd.read_csv(output / "pipeline_anomalies.csv")
    assert sorted(pd.concat([clean, anomalies]).V1.tolist()) == [0.0, 1.0, 2.0, 100.0]
    assert anomalies.V1.tolist() == [100.0]


def test_pipeline_demo_defaults_to_zscore(tmp_path, monkeypatch):
    from etl_benchmark import config
    from etl_benchmark.__main__ import main

    source = tmp_path / "input.csv"
    values = list(range(50)) + [1000]
    pd.DataFrame({"V1": values, "Class": [0] * 50 + [1]}).to_csv(source, index=False)
    output = tmp_path / "out"
    monkeypatch.setattr(config, "RESULTS_DIR", output)
    monkeypatch.setattr(sys, "argv", ["etl-benchmark", "--input", str(source)])
    main()
    anomalies = pd.read_csv(output / "pipeline_anomalies.csv")
    assert anomalies.V1.tolist() == [1000]


def test_cardio_fetch_converts_source_arrays_without_network(tmp_path, monkeypatch):
    import fetch_cardio

    from etl_benchmark import config

    payload = io.BytesIO()
    np.savez(payload, X=np.array([[1.0, 2.0], [3.0, 4.0]]), y=np.array([0, 1]))
    monkeypatch.setattr(
        fetch_cardio.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(payload.getvalue())
    )
    target = tmp_path / "cardio.csv"
    monkeypatch.setattr(config, "CARDIO_CSV", target)
    runpy.run_path(str(Path(fetch_cardio.__file__)), run_name="__main__")
    actual = pd.read_csv(target)
    assert actual.columns.tolist() == ["f00", "f01", "label"]
    assert actual.to_numpy().tolist() == [[1.0, 2.0, 0.0], [3.0, 4.0, 1.0]]


def test_synthetic_cli_writes_tables_and_heatmap(tmp_path):
    output = tmp_path / "out"
    figure = tmp_path / "heatmap.png"
    _run(
        "run_synthetic_benchmark.py",
        "--rows",
        300,
        "--seeds",
        1,
        "--results-dir",
        output,
        "--figure",
        figure,
    )
    assert figure.stat().st_size > 0
    assert {"metrics", "recall", "precision"} <= {
        path.name.split("_")[1] for path in output.glob("synthetic_*.csv")
    }
    record = json.loads(next(output.glob("run_synthetic_*.json")).read_text())
    assert record["settings"]["split_strategy"] == "customer_identity_grouped_stratified"


def test_severity_cli_writes_curve_and_table(tmp_path):
    output = tmp_path / "out"
    figure = tmp_path / "severity.png"
    _run(
        "run_severity.py",
        "--rows",
        300,
        "--severities",
        1,
        "--seeds",
        1,
        "--results-dir",
        output,
        "--figure",
        figure,
    )
    assert figure.stat().st_size > 0
    assert set(pd.read_csv(next(output.glob("severity_*.csv"))).anomaly_type)


def test_curves_cli_can_run_synthetic_only(tmp_path):
    output = tmp_path / "out"
    figure = tmp_path / "curves.png"
    _run(
        "run_curves.py",
        "--datasets",
        "synthetic",
        "--rows",
        300,
        "--seed",
        1,
        "--results-dir",
        output,
        "--figure",
        figure,
    )
    assert figure.stat().st_size > 0
    sweep = pd.read_csv(next(output.glob("contamination_sweep_*.csv")))
    assert set(sweep.dataset) == {"synthetic"}
