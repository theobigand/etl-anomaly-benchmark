"""Offline experiment entry points write only inside an explicit result directory."""

import gzip
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
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
    split_archive = next(output.glob("split_ids_*.json.gz"))
    with gzip.open(split_archive, "rt") as stream:
        splits = json.load(stream)
    assert splits["row_count"] == len(values)
    assert sorted(sum(splits["seeds"]["1"].values(), [])) == list(range(len(values)))
    assert split_archive.name in record["outputs"]


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
