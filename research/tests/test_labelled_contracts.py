"""labelled_benchmark: what each call receives, what is recorded, and the command line (stubbed)."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES, clip_contamination  # noqa: E402


def _problem(n=600, anomalies=40, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[:anomalies] = 1
    x[:anomalies] += 6
    return x, y


class _Result:
    def __init__(self, n, tag):
        self.flags = pd.Series(np.arange(n) % 2 == 0)
        self.scores = pd.Series(np.arange(n, dtype=float) + tag)


@pytest.fixture
def spied(monkeypatch):
    calls = {"build": [], "capped": [], "detect": [], "metrics": []}

    def build(method, contamination, seed):
        calls["build"].append((method, contamination, seed))
        return ("model", method, seed)

    def capped(train, method, seed):
        calls["capped"].append((train, method, seed))
        return ("fit", method, seed)

    def detect(test, model, fit_df):
        calls["detect"].append((test, model, fit_df))
        return _Result(len(test), 100 * len(calls["detect"]))

    def compute_metrics(y_true, flags, scores):
        calls["metrics"].append((y_true, flags, scores))
        return {"n": float(len(y_true)), "k": float(len(calls["metrics"]))}

    monkeypatch.setattr(lb, "build", build)
    monkeypatch.setattr(lb, "capped", capped)
    monkeypatch.setattr(lb, "detect", detect)
    monkeypatch.setattr(lb, "compute_metrics", compute_metrics)
    return calls


def test_every_method_is_fitted_on_the_train_part_and_scored_on_the_test_part(spied):
    x, y = _problem()
    out = lb.run_problem(x, y, seeds=(3, 4), methods=["zscore", "iqr"])
    parts = {s: nm.split(x, y, s) for s in (3, 4)}
    names = [f"f{i}" for i in range(4)]
    assert out["seeds"] == [3, 4] and out["skipped"] == [] and out["errors"] == {}
    assert [(b[0], b[2]) for b in spied["build"]] == [
        ("zscore", 3),
        ("iqr", 3),
        ("zscore", 4),
        ("iqr", 4),
    ]
    for (method, contamination, _seed), part in zip(
        [spied["build"][0], spied["build"][2]], parts.values(), strict=True
    ):
        assert (
            contamination == clip_contamination(float(part["y_train"].mean()))
            and method == "zscore"
        )
    train0 = spied["capped"][0][0]
    assert list(train0.columns) == names
    np.testing.assert_allclose(train0.to_numpy(), parts[3]["x_train"])
    assert [(c[1], c[2]) for c in spied["capped"]] == [
        ("zscore", 3),
        ("iqr", 3),
        ("zscore", 4),
        ("iqr", 4),
    ]
    test0, model0, fit0 = spied["detect"][0]
    assert (
        list(test0.columns) == names
        and model0 == ("model", "zscore", 3)
        and fit0 == ("fit", "zscore", 3)
    )
    np.testing.assert_allclose(test0.to_numpy(), parts[3]["x_test"])
    y_true, flags, scores = spied["metrics"][0]
    np.testing.assert_array_equal(y_true, parts[3]["y_test"])
    assert isinstance(flags, np.ndarray) and isinstance(scores, np.ndarray)
    assert flags[0] and not flags[1] and scores[0] == 100.0
    assert sorted(out["metrics"]) == ["iqr", "zscore"] and all(
        len(v) == 2 for v in out["metrics"].values()
    )


def test_the_default_methods_are_the_registry_and_the_default_seeds_the_benchmark_seeds(spied):
    x, y = _problem()
    out = lb.run_problem(x, y)
    assert out["seeds"] == list(config.BENCHMARK_SEEDS)
    assert list(DETECTOR_NAMES) == lb.METHODS and [*DETECTOR_NAMES, *DEEP_NAMES] == lb.KNOWN
    assert sorted(out["metrics"]) == sorted(DETECTOR_NAMES)


def test_skipped_methods_are_not_run_and_are_listed(spied, monkeypatch):
    monkeypatch.setattr(nm, "OCSVM_MAX_TRAIN", 10)
    x, y = _problem()
    out = lb.run_problem(x, y, seeds=(1,), methods=["zscore", "ocsvm"])
    assert out["skipped"] == ["ocsvm"] and "ocsvm" not in out["metrics"]
    assert [b[0] for b in spied["build"]] == ["zscore"]


def test_failures_are_recorded_with_the_repr_the_seed_and_later_seeds_still_run(spied, monkeypatch):
    def detect(test, model, fit_df):
        if model[1] == "iqr":
            raise KeyError("boom")
        return _Result(len(test), 0)

    monkeypatch.setattr(lb, "detect", detect)
    x, y = _problem()
    out = lb.run_problem(x, y, seeds=(1, 2), methods=["iqr", "zscore"])
    assert out["errors"] == {
        "iqr": [{"seed": 1, "error": "KeyError('boom')"}, {"seed": 2, "error": "KeyError('boom')"}]
    }
    assert len(out["metrics"]["zscore"]) == 2 and "iqr" not in out["metrics"]


def test_an_unknown_method_message_lists_the_names():
    with pytest.raises(ValueError, match=r"^unknown detector names: \['nope'\]$"):
        lb.run_problem(*_problem(), methods=["zscore", "nope"])


def test_uci_problem_is_cleaned_and_reported_with_its_origin(tmp_path):
    rng = np.random.default_rng(0)
    table = pd.DataFrame(
        {"a": rng.normal(size=1000), "b": rng.normal(size=1000), "y": [1] * 60 + [0] * 940}
    )
    path = tmp_path / "7.csv"
    table.to_csv(path, index=False)
    meta = {
        "uci_id": 7,
        "name": "Toy",
        "tasks": ["Classification"],
        "target_col": ["y"],
        "variables": [],
    }
    x, y, report = lb.load_uci(meta, path)
    assert report["source"] == "uci" and report["name"] == "Toy" and report["uci_id"] == 7
    assert report["kind"] == "native_rare" and report["rows_out"] == len(y) == x.shape[0] == 1000
    a_x, a_y, a_report = lb.load_adbench("toy", _npz(tmp_path))
    assert a_report["name"] == "toy" and a_report["source"] == "adbench" and a_x.shape[1] == 4


def _npz(tmp_path):
    x, y = _problem()
    path = tmp_path / "9_toy.npz"
    np.savez(path, X=x, y=y)
    return path


def test_run_job_describes_a_solved_problem_and_a_failed_one(tmp_path, monkeypatch, spied):
    path = _npz(tmp_path)
    job = {"problem": "adbench:toy", "source": "adbench", "name": "toy", "path": str(path)}
    out = lb.run_job(job, methods=["zscore"])
    assert out["problem"] == "adbench:toy" and out["source"] == "adbench" and out["name"] == "toy"
    assert (
        out["prevalence"] == pytest.approx(40 / 600, abs=0.02)
        and out["rows"] == 600
        and out["features"] == 4
    )
    assert out["report"]["source"] == "adbench" and out["seeds"] == list(config.BENCHMARK_SEEDS)
    assert "failed" not in out
    broken = lb.run_job({**job, "path": str(tmp_path / "missing.npz")})
    assert broken["problem"] == "adbench:toy" and broken["source"] == "adbench"
    assert broken["failed"].startswith("FileNotFoundError(") and set(broken) == {
        "problem",
        "source",
        "failed",
    }
    uci = lb.run_job(
        {"problem": "uci:7", "source": "uci", "meta": {"uci_id": 7}, "path": "nope.csv"}
    )
    assert uci["problem"] == "uci:7" and "failed" in uci


def _registry(tmp_path):
    reg = tmp_path / "reg"
    reg.mkdir()
    names = [t["name"] for t in lb.dr.ADBENCH_TABULAR][:2]
    (reg / "adbench_normalisation_report.json").write_text(json.dumps({names[1]: {}, names[0]: {}}))
    metas = [{"uci_id": i, "name": f"u{i}"} for i in (1, 2, 3)]
    (reg / "uci_curated.json").write_text(json.dumps({"kept": metas}))
    rows = [
        {"uci_id": 1, "roles": ["carrier"]},
        {"uci_id": 3, "roles": ["carrier", "labelled"]},
        {"uci_id": 2, "roles": ["labelled"]},
    ]
    (reg / "uci_pool.json").write_text(json.dumps({"rows": rows}))
    return reg, metas, names


def test_jobs_list_the_adbench_sets_sorted_then_the_labelled_uci_sets_in_pool_order(tmp_path):
    reg, metas, names = _registry(tmp_path)
    files = {t["name"]: t["file"] for t in lb.dr.ADBENCH_TABULAR}
    out = lb.jobs(reg, tmp_path / "ad", tmp_path / "pool")
    assert out == [
        *[
            {
                "problem": f"adbench:{n}",
                "source": "adbench",
                "name": n,
                "path": str(tmp_path / "ad" / files[n]),
            }
            for n in sorted(names)
        ],
        {
            "problem": "uci:3",
            "source": "uci",
            "meta": metas[2],
            "path": str(tmp_path / "pool" / "3.csv"),
        },
        {
            "problem": "uci:2",
            "source": "uci",
            "meta": metas[1],
            "path": str(tmp_path / "pool" / "2.csv"),
        },
    ]


class _Serial:
    workers = []

    def __init__(self, max_workers):
        _Serial.workers.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        return [fn(i) for i in items]


@pytest.fixture
def cli(tmp_path, monkeypatch):
    reg, metas, names = _registry(tmp_path)
    ran = []

    def run_job(job, methods=None):
        ran.append((job["problem"], methods))
        return {
            "problem": job["problem"],
            "z": 1,
            "a": 2,
            **({"failed": "boom"} if job["problem"] == "uci:2" else {}),
        }

    monkeypatch.setattr(lb, "ProcessPoolExecutor", _Serial)
    monkeypatch.setattr(lb, "run_job", run_job)
    _Serial.workers = []
    out = tmp_path / "o" / "x"

    def invoke(*extra):
        return lb.main(
            [
                "--registry",
                str(reg),
                "--adbench",
                str(tmp_path / "ad"),
                "--pool",
                str(tmp_path / "pool"),
                "--output",
                str(out),
                *extra,
            ]
        )

    return invoke, ran, out, names


def test_main_writes_every_problem_counts_the_failures_and_flushes_progress(cli, capsys):
    invoke, ran, out, names = cli
    assert invoke() == 0
    assert [r[0] for r in ran] == [*(f"adbench:{n}" for n in sorted(names)), "uci:3", "uci:2"]
    assert all(r[1] == list(lb.METHODS) for r in ran)
    first = out / f"adbench_{sorted(names)[0]}.json"
    assert (
        first.read_text()
        == json.dumps(
            {"problem": f"adbench:{sorted(names)[0]}", "z": 1, "a": 2}, indent=1, sort_keys=True
        )
        + "\n"
    )
    lines = capsys.readouterr().out.splitlines()
    assert lines[-3:] == ["uci:3 ok", "uci:2 boom", "4 problems, 1 failed"]
    assert _Serial.workers == [4]


def test_main_options_only_resume_workers_and_deep_methods(cli, capsys):
    invoke, ran, out, names = cli
    assert invoke("--only", "uci:3", "--workers", "2", "--methods", "deep") == 0
    assert ran == [("uci:3", list(DEEP_NAMES))] and _Serial.workers == [2]
    ran.clear()
    invoke("--only", "uci:3", "uci:2", "--resume")
    assert ran == [("uci:2", list(lb.METHODS))]
    capsys.readouterr()


def test_main_defaults_help_and_required_output(monkeypatch, tmp_path, capsys):
    seen = []
    monkeypatch.setattr(lb, "jobs", lambda r, a, p: seen.append((r, a, p)) or [])
    monkeypatch.setattr(lb, "ProcessPoolExecutor", _Serial)
    lb.main(["--output", str(tmp_path / "o")])
    root = Path(lb.__file__).resolve().parents[1]
    assert seen == [
        (
            root / "verification/evidence/dataset_registry",
            root / "data" / "adbench",
            root / "data" / "pool",
        )
    ]
    assert capsys.readouterr().out == "0 problems, 0 failed\n"
    with pytest.raises(SystemExit):
        lb.main([])
    assert "--output" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        lb.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    for phrase in (
        "problem ids, for a quick check",
        "skip the problems whose result is already written",
        "the detectors of the registry sweep, or the neural ones (fit rows capped)",
    ):
        assert phrase in text and "XX" + phrase not in text


def test_with_no_seeds_nothing_is_skipped_and_nothing_is_recorded(spied):
    out = lb.run_problem(*_problem(), seeds=(), methods=["zscore"])
    assert out == {"seeds": [], "metrics": {}, "skipped": [], "errors": {}}


def test_the_registry_files_are_read_by_their_exact_names(tmp_path, monkeypatch):
    reg, _, _ = _registry(tmp_path)
    reads = []
    real = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: reads.append(self.name) or real(self, *a, **k)
    )
    lb.jobs(reg, tmp_path / "a", tmp_path / "p")
    assert reads == ["adbench_normalisation_report.json", "uci_curated.json", "uci_pool.json"]


def test_progress_is_flushed_and_classical_is_an_accepted_choice(cli, monkeypatch):
    invoke, ran, out, names = cli
    flushes = []
    monkeypatch.setattr(lb, "print", lambda *a, **k: flushes.append(k.get("flush")), raising=False)
    assert invoke("--only", "uci:3", "--methods", "classical") == 0
    assert flushes == [True, None] and ran == [("uci:3", list(lb.METHODS))]
