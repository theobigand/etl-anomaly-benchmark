"""Job selection, loading, per-problem execution and the command of the two pool pipelines."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402
import pool_full as pf  # noqa: E402

NAME = "annthyroid"
FILE = "2_annthyroid.npz"
META = {
    "uci_id": 7,
    "name": "Toy",
    "tasks": ["Classification"],
    "target_col": ["cls"],
    "variables": [{"name": "cls", "role": "Target"}],
}


def _arrays(seed=0, n=300, anomalies=30):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 5
    return x, y


def _pool(tmp_path):
    registry, adbench, pool = (tmp_path / name for name in ("registry", "adbench", "pool"))
    for folder in (registry, adbench, pool):
        folder.mkdir()
    (registry / "adbench_normalisation_report.json").write_text(json.dumps({NAME: {}}))
    (registry / "uci_curated.json").write_text(json.dumps({"kept": [META]}))
    rows = [
        {"uci_id": 7, "roles": ["carrier", "labelled"]},
        {"uci_id": 8, "roles": ["carrier"]},
    ]
    (registry / "uci_pool.json").write_text(json.dumps({"rows": rows}))
    x, y = _arrays()
    np.savez(adbench / FILE, X=x, y=y)
    table = pd.DataFrame(_arrays(1)[0], columns=[f"f{i}" for i in range(4)])
    table["cls"] = np.where(np.arange(len(table)) < 30, "rare", "common")
    table.to_csv(pool / "7.csv", index=False)
    return registry, adbench, pool


@pytest.fixture(params=[lb, pf], ids=["labelled_benchmark", "pool_full"])
def module(request):
    return request.param


def test_jobs_list_the_adbench_files_then_only_the_labelled_uci_problems(tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    assert lb.jobs(registry, adbench, pool) == [
        {
            "problem": f"adbench:{NAME}",
            "source": "adbench",
            "name": NAME,
            "path": str(adbench / FILE),
        },
        {"problem": "uci:7", "source": "uci", "meta": META, "path": str(pool / "7.csv")},
    ]


def test_a_uci_table_is_labelled_by_its_rare_class_and_keeps_its_provenance(tmp_path):
    _, _, pool = _pool(tmp_path)
    x, y, report = lb.load_uci(META, pool / "7.csv")
    assert x.shape[1] == 4 and set(np.unique(y)) == {0, 1}
    assert int(y.sum()) == report["anomalies"] == 30
    assert report["anomaly_class"] == "rare" and report["classes"] == 2
    assert (report["source"], report["name"], report["uci_id"]) == ("uci", "Toy", 7)


def test_an_adbench_job_is_run_and_describes_its_population(module, tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    job = lb.jobs(registry, adbench, pool)[0]
    result = module.run_job(job, methods=["zscore", "iqr"])
    assert result["problem"] == f"adbench:{NAME}" and result["source"] == "adbench"
    assert result["name"] == NAME and result["rows"] == 300 and result["features"] == 4
    assert result["prevalence"] == pytest.approx(0.1)
    assert result["seeds"] == list(lb.config.BENCHMARK_SEEDS)
    assert result["errors"] == {} and "failed" not in result


def test_labelled_results_hold_one_metric_row_per_seed_and_the_cleaning_report(tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    result = lb.run_job(lb.jobs(registry, adbench, pool)[0], methods=["zscore"])
    assert len(result["metrics"]["zscore"]) == len(lb.config.BENCHMARK_SEEDS)
    assert result["report"]["source"] == "adbench" and result["report"]["name"] == NAME


def test_pool_results_hold_one_run_per_seed_with_the_label_free_tables(tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    result = pf.run_job(lb.jobs(registry, adbench, pool)[0], methods=["isolation_forest"])
    rows = result["runs"]["isolation_forest"]
    assert [row["seed"] for row in rows] == list(lb.config.BENCHMARK_SEEDS)
    assert all({"metrics", "fixed", "sweep"} <= set(row) for row in rows)
    assert [bool("curve" in row) for row in rows] == [seed == pf.CURVE_SEED for seed in
                                                      lb.config.BENCHMARK_SEEDS]  # fmt: skip


def test_a_uci_job_is_loaded_through_its_metadata(module, tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    result = module.run_job(lb.jobs(registry, adbench, pool)[1], methods=["zscore"])
    assert result["problem"] == "uci:7" and result["name"] == "Toy" and result["source"] == "uci"
    assert result["rows"] == 300 and result["prevalence"] == pytest.approx(0.1)


@pytest.mark.parametrize("broken", ["missing", "unknown_method"])
def test_a_failing_job_is_recorded_with_its_reason_and_never_raised(module, tmp_path, broken):
    registry, adbench, pool = _pool(tmp_path)
    job = dict(lb.jobs(registry, adbench, pool)[0])
    methods = ["zscore"]
    if broken == "missing":
        job["path"] = str(tmp_path / "absent.npz")
    else:
        methods = ["nonexistent_detector"]
    result = module.run_job(job, methods=methods)
    assert set(result) == {"problem", "source", "failed"}
    assert result["problem"] == job["problem"] and result["source"] == "adbench"
    assert result["failed"]


class _Serial:
    """Runs the jobs in process: the same job function, without worker processes."""

    created: list = []

    def __init__(self, max_workers):
        self.max_workers = max_workers
        _Serial.created.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        return [function(item) for item in items]


@pytest.fixture
def command(module, monkeypatch, tmp_path, capsys):
    registry, adbench, pool = _pool(tmp_path)
    _Serial.created = []
    monkeypatch.setattr(module, "ProcessPoolExecutor", _Serial)
    monkeypatch.setattr(lb, "METHODS", ["zscore"])
    monkeypatch.setattr(module, "DETECTOR_NAMES", ("zscore",), raising=False)
    monkeypatch.setattr(module, "DEEP_NAMES", ("iqr",))

    def run(*extra, output=tmp_path / "out"):
        arguments = ["--registry", str(registry), "--adbench", str(adbench), "--pool", str(pool),
                     "--output", str(output), *extra]  # fmt: skip
        code = module.main(arguments)
        return code, capsys.readouterr().out.splitlines(), output

    return run


def test_the_command_writes_one_json_per_problem_and_reports_the_count(command):
    code, lines, output = command("--workers", "3")
    assert code == 0 and _Serial.created == [3]
    assert sorted(path.name for path in output.iterdir()) == [
        "adbench_annthyroid.json",
        "uci_7.json",
    ]
    assert lines == ["adbench:annthyroid ok", "uci:7 ok", "2 problems, 0 failed"]
    payload = json.loads((output / "uci_7.json").read_text())
    assert payload["problem"] == "uci:7" and payload["name"] == "Toy"


def test_only_selects_the_named_problems(command):
    code, lines, output = command("--only", "uci:7")
    assert [path.name for path in output.iterdir()] == ["uci_7.json"]
    assert lines == ["uci:7 ok", "1 problems, 0 failed"]


def test_resume_skips_problems_whose_result_exists_and_keeps_them_untouched(command, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    (output / "adbench_annthyroid.json").write_text("kept\n")
    code, lines, _ = command("--resume")
    assert (output / "adbench_annthyroid.json").read_text() == "kept\n"
    assert lines == ["uci:7 ok", "1 problems, 0 failed"]


def test_without_resume_an_existing_result_is_replaced(command, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    (output / "adbench_annthyroid.json").write_text("stale\n")
    command()
    assert json.loads((output / "adbench_annthyroid.json").read_text())["problem"]


def test_a_failed_problem_is_counted_and_its_record_is_kept(command, module, tmp_path):
    (tmp_path / "adbench" / FILE).unlink()
    code, lines, output = command()
    assert code == 0 and lines[-1] == "2 problems, 1 failed"
    assert "failed" in json.loads((output / "adbench_annthyroid.json").read_text())
    assert lines[0].startswith("adbench:annthyroid ") and not lines[0].endswith(" ok")


def test_the_deep_selection_runs_the_neural_names_of_the_registry(command, module):
    code, lines, output = command("--methods", "deep", "--only", f"adbench:{NAME}")
    payload = json.loads((output / "adbench_annthyroid.json").read_text())
    assert code == 0 and payload.get("failed") is None
    runs = payload.get("metrics") or payload.get("runs")
    assert list(runs) == ["iqr"]


def test_the_classical_selection_runs_the_classical_names(command, module):
    code, lines, output = command("--only", f"adbench:{NAME}")
    payload = json.loads((output / "adbench_annthyroid.json").read_text())
    runs = payload.get("metrics") or payload.get("runs")
    assert list(runs) == ["zscore"]


def test_the_output_option_is_required(module, tmp_path, capsys):
    with pytest.raises(SystemExit) as caught:
        module.main(["--registry", str(tmp_path)])
    assert caught.value.code == 2 and "--output" in capsys.readouterr().err
