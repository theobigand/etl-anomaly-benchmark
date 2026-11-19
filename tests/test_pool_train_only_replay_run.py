"""Raw loading, per-problem bookkeeping and the command of the train-only replay."""

import json

import numpy as np
import pandas as pd
import pytest

import research.pool_train_only_replay as replay
from etl_benchmark import config


def _adbench_file(path, rows=240, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(rows, 3))
    y = (rng.random(rows) < 0.2).astype(int)
    x[y == 1] += 3
    np.savez(path, X=x, y=y)
    return path


def test_adbench_tables_are_loaded_raw_as_strings_with_generated_column_names(tmp_path):
    file = tmp_path / "t.npz"
    np.savez(file, X=np.array([[1.0, 2.0], [1.0, 2.0], [3.0, 4.0]]), y=np.array([0.0, 1.0, 1.0]))
    frame, labels = replay.load_raw({"source": "adbench", "path": str(file)})
    assert list(frame.columns) == ["c0", "c1"]
    assert len(frame) == 3  # identical rows are kept: no cleaning, no row removal
    assert frame.dtypes.map(str).tolist() == ["string", "string"]
    assert labels.tolist() == [0, 1, 1] and labels.dtype.kind == "i"


def test_uci_tables_go_through_the_label_rule_and_keep_every_row(tmp_path, monkeypatch):
    seen = {}

    def read_table(path):
        seen["path"] = path
        return "table"

    def derive_labels(table, meta):
        seen["args"] = (table, meta)
        return pd.DataFrame({1: [5, 6], "b": [7, 8]}), np.array([True, False]), {}

    monkeypatch.setattr(replay.ul, "read_table", read_table)
    monkeypatch.setattr(replay.ul, "derive_labels", derive_labels)
    job = {"source": "uci", "path": str(tmp_path / "7.csv"), "meta": {"uci_id": 7}}
    frame, labels = replay.load_raw(job)
    assert seen["path"] == tmp_path / "7.csv"
    assert seen["args"] == ("table", {"uci_id": 7})
    assert list(frame.columns) == ["1", "b"]
    assert frame.dtypes.map(str).tolist() == ["string", "string"]
    assert labels.tolist() == [1, 0] and labels.dtype.kind == "i"


def test_the_split_is_70_15_15_over_groups_and_stratified(tmp_path):
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({"a": np.arange(1000), "b": rng.integers(0, 5, 1000)}).astype("string")
    labels = (np.arange(1000) % 5 == 0).astype(int)
    parts = replay.grouped_split(frame, labels, seed=0)
    sizes = {k: len(v) for k, v in parts.items()}
    assert sizes == {"train": 700, "validation": 150, "test": 150}
    assert {round(labels[v].mean(), 3) for v in parts.values()} == {0.2}


class _Stub:
    """evaluate_frozen replaced: records the calls and returns the documented structure."""

    def __init__(self):
        self.calls = []

    def __call__(self, frame, labels, parts, seed, methods):
        self.labels = labels
        self.calls.append((len(frame), seed, tuple(methods), sorted(parts)))
        return {
            "runs": {"m": {"metrics": {"pr_auc": 0.1 * seed}}},
            "errors": [{"method": "bad", "reason": "r"}],
            "skipped": [f"s{seed}"],
            "prevalence": 0.25,
            "preprocessing": {
                "numeric_columns": ["a", "b"],
                "categorical_columns": ["c"],
                "dropped": {"id": [1, 2], "text": [3]},
            },
        }


def test_a_job_is_evaluated_once_per_seed_and_each_result_is_tagged(monkeypatch):
    frame = pd.DataFrame({"a": range(40)}).astype("string")
    labels = np.array([0, 1] * 20)
    stub = _Stub()
    jobs, seeds = [], []
    real_split = replay.grouped_split
    monkeypatch.setattr(replay, "load_raw", lambda job: (jobs.append(job), (frame, labels))[1])
    monkeypatch.setattr(
        replay, "grouped_split", lambda f, y, seed: (seeds.append(seed), real_split(f, y, seed))[1]
    )
    monkeypatch.setattr(replay, "evaluate_frozen", stub)
    job = {"problem": "adbench:t", "source": "adbench"}
    result = replay.run_job(job, ["m1", "m2"])
    assert jobs == [job] and seeds == list(config.BENCHMARK_SEEDS)
    assert stub.labels is labels
    seeds = list(config.BENCHMARK_SEEDS)
    assert [c[1] for c in stub.calls] == seeds
    assert all(c[0] == 40 and c[2] == ("m1", "m2") for c in stub.calls)
    assert all(c[3] == ["test", "train", "validation"] for c in stub.calls)
    assert result["protocol"] == replay.PROTOCOL == "pool-train-only-replay-v1"
    assert (result["problem"], result["source"]) == ("adbench:t", "adbench")
    assert result["rows"] == 40 and result["prevalence"] == 0.5
    assert result["metrics"] == {"m": [{"seed": s, "pr_auc": 0.1 * s} for s in seeds]}
    assert result["errors"] == [{"seed": s, "method": "bad", "reason": "r"} for s in seeds]
    assert result["skipped"] == [f"s{seeds[-1]}"]
    first = result["preparation"][0]
    assert first["seed"] == seeds[0]
    assert sum(first["rows"].values()) == 40 and set(first["rows"]) == {
        "train",
        "validation",
        "test",
    }
    assert (first["prevalence"], first["numeric"], first["categorical"]) == (0.25, 2, 1)
    assert first["dropped"] == {"id": 2, "text": 1}
    assert len(result["preparation"]) == len(seeds)


def test_a_failing_job_is_recorded_with_its_reason_and_never_dropped(monkeypatch):
    def broken(job):
        raise ValueError("unreadable")

    monkeypatch.setattr(replay, "load_raw", broken)
    result = replay.run_job({"problem": "uci:9", "source": "uci"}, ["m"])
    assert result == {"problem": "uci:9", "source": "uci", "failed": "ValueError('unreadable')"}


@pytest.fixture
def one_problem(tmp_path, monkeypatch):
    file = _adbench_file(tmp_path / "toy.npz")
    job = {"problem": "adbench:toy", "source": "adbench", "name": "toy", "path": str(file)}
    monkeypatch.setattr(replay.lb, "jobs", lambda *_: [job])
    return tmp_path / "out"


def test_the_command_replays_a_problem_end_to_end_and_writes_one_file(one_problem, capsys):
    argv = ["--output", str(one_problem), "--workers", "1"]
    assert replay.main(argv) == 0
    assert capsys.readouterr().out.strip() == "1 problems, 0 failed"
    body = json.loads((one_problem / "adbench_toy.json").read_text())
    assert body["protocol"] == replay.PROTOCOL
    assert "isolation_forest" in body["metrics"]
    assert set(body["metrics"]) | set(body["skipped"]) | {
        e["method"] for e in body["errors"]
    } == set(replay.lb.METHODS)
    assert all(len(runs) == len(config.BENCHMARK_SEEDS) for runs in body["metrics"].values())


def test_resume_skips_a_problem_whose_file_exists_and_only_selects_by_name(one_problem, capsys):
    one_problem.mkdir()
    (one_problem / "adbench_toy.json").write_text("{}")
    replay.main(["--output", str(one_problem), "--workers", "1", "--resume"])
    assert capsys.readouterr().out.strip() == "0 problems, 0 failed"
    replay.main(["--output", str(one_problem), "--workers", "1", "--only", "adbench:other"])
    assert capsys.readouterr().out.strip() == "0 problems, 0 failed"


def test_the_command_counts_failed_problems(tmp_path, monkeypatch, capsys):
    job = {"problem": "adbench:gone", "source": "adbench", "path": str(tmp_path / "missing.npz")}
    monkeypatch.setattr(replay.lb, "jobs", lambda *_: [job])
    out = tmp_path / "out"
    assert replay.main(["--output", str(out), "--workers", "1"]) == 0
    assert capsys.readouterr().out.strip() == "1 problems, 1 failed"
    assert "failed" in json.loads((out / "adbench_gone.json").read_text())
