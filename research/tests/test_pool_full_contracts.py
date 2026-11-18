"""Threshold scores, strict flags, argument routing and the command of the whole-pool study."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402
import pool_full as pf  # noqa: E402


def test_the_threshold_scores_are_the_fit_scores_of_the_model_as_floats():
    model = SimpleNamespace(decision_scores_=[1, 2, 3])
    scores = pf.fit_scores(SimpleNamespace(_model=model), pd.DataFrame())
    assert scores.dtype == np.float64 and scores.tolist() == [1.0, 2.0, 3.0]
    assert pf.fit_scores(SimpleNamespace(_model=None), pd.DataFrame()) is None
    assert pf.fit_scores(SimpleNamespace(), pd.DataFrame()) is None


def test_an_estimator_without_stored_scores_is_thresholded_on_its_own_fit_row_scores():
    frame = pd.DataFrame({"a": [1.0, 2.0]})
    detector = SimpleNamespace(_model=SimpleNamespace(), score=lambda df: pd.Series([4, 5]))
    scores = pf.fit_scores(detector, frame)
    assert scores.dtype == np.float64 and scores.tolist() == [4.0, 5.0]


def test_a_score_equal_to_the_threshold_is_not_flagged_and_the_contamination_is_clipped():
    fit = np.arange(101, dtype=float)
    flags = pf.flags_at(fit, np.array([89.0, 90.0, 90.5, 100.0]), 0.1)
    assert flags.tolist() == [False, False, True, True]
    assert pf.flags_at(fit, np.array([50.0]), 0.1).dtype == np.bool_
    low, high = pf.config.ML_CONTAMINATION_BOUNDS
    assert pf.flags_at(fit, fit, 0.0).sum() == pf.flags_at(fit, fit, low).sum()
    assert pf.flags_at(fit, fit, 1.0).sum() == pf.flags_at(fit, fit, high).sum()


def _problem(n=300):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 3))
    y = np.zeros(n, dtype=int)
    y[::10] = 1
    x[y == 1] += 5
    return x, y


def test_each_seed_trains_on_named_columns_with_the_training_prevalence(monkeypatch):
    x, y = _problem()
    calls = []

    def run_method(method, train, test, y_test, seed, prevalence):
        calls.append(
            (method, list(train.columns), list(test.columns), seed, prevalence, len(y_test))
        )
        return {"seed": seed}

    monkeypatch.setattr(pf, "run_method", run_method)
    result = pf.run_problem(x, y, seeds=(1, 2), methods=["zscore", "iqr"])
    assert [c[:2] for c in calls] == [
        ("zscore", ["f0", "f1", "f2"]), ("iqr", ["f0", "f1", "f2"]),
    ] * 2  # fmt: skip
    for call, seed in zip(calls, (1, 1, 2, 2), strict=True):
        part = pf.nm.split(x, y, seed)
        assert call[2] == ["f0", "f1", "f2"] and call[3] == seed
        assert call[4] == float(part["y_train"].mean()) and call[5] == len(part["y_test"])
    assert result["seeds"] == [1, 2] and result["errors"] == {} and result["skipped"] == []
    assert result["runs"]["zscore"] == [{"seed": 1}, {"seed": 2}]


def test_a_failing_model_is_recorded_with_its_seed_and_does_not_stop_the_others(monkeypatch):
    x, y = _problem()

    def run_method(method, train, test, y_test, seed, prevalence):
        if method == "iqr":
            raise RuntimeError("boom")
        return {"seed": seed}

    monkeypatch.setattr(pf, "run_method", run_method)
    result = pf.run_problem(x, y, seeds=(1, 2), methods=["iqr", "zscore"])
    assert result["errors"] == {
        "iqr": [
            {"seed": 1, "error": "RuntimeError('boom')"},
            {"seed": 2, "error": "RuntimeError('boom')"},
        ]
    }
    assert len(result["runs"]["zscore"]) == 2 and "iqr" not in result["runs"]


def test_the_default_method_list_is_the_registry_and_no_seed_gives_empty_records(monkeypatch):
    x, y = _problem()
    seen = []
    monkeypatch.setattr(pf, "run_method", lambda method, *a: seen.append(method) or {})
    result = pf.run_problem(x, y, seeds=(1,))
    assert seen == [m for m in pf.DETECTOR_NAMES if m not in pf.nm.skipped_detectors(210)]
    empty = pf.run_problem(x, y, seeds=())
    assert empty == {"seeds": [], "runs": {}, "skipped": [], "errors": {}}
    assert result["skipped"] == [m for m in pf.DETECTOR_NAMES if m in pf.nm.skipped_detectors(210)]


def _jobs(names):
    return [{"problem": name, "source": "uci"} for name in names]


class _Pool:
    def __init__(self, max_workers):
        _Pool.workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        _Pool.methods = function.keywords["methods"]
        return [
            {"problem": job["problem"], **({"failed": "x"} if job["problem"] == "uci:2" else {})}
            for job in items
        ]


def _command(monkeypatch, names=("uci:1", "uci:2", "adbench:a")):
    seen = {}
    monkeypatch.setattr(
        lb,
        "jobs",
        lambda registry, adbench, pool: (
            seen.update(paths=(registry, adbench, pool)) or _jobs(names)
        ),
    )
    monkeypatch.setattr(pf, "ProcessPoolExecutor", _Pool)
    return seen


def test_the_command_writes_one_file_per_problem_prints_each_and_counts_failures(
    tmp_path, monkeypatch, capsys
):
    seen = _command(monkeypatch)
    out = tmp_path / "new" / "dir"
    assert pf.main(["--output", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["adbench_a.json", "uci_1.json", "uci_2.json"]
    text = (out / "uci_2.json").read_text()
    assert (
        text == json.dumps(json.loads(text), sort_keys=True) + "\n"
        and json.loads(text)["failed"] == "x"
    )
    assert capsys.readouterr().out.splitlines() == [
        "uci:1 ok",
        "uci:2 x",
        "adbench:a ok",
        "3 problems, 1 failed",
    ]
    root = Path(pf.__file__).resolve().parents[1]
    assert seen["paths"] == (
        root / "verification/evidence/dataset_registry",
        root / "data/adbench",
        root / "data/pool",
    )
    assert _Pool.workers == 4 and _Pool.methods == list(pf.DETECTOR_NAMES)


def test_the_only_resume_and_methods_options_choose_the_problems_and_the_detector_family(
    tmp_path, monkeypatch, capsys
):
    _command(monkeypatch)
    out = tmp_path / "o"
    out.mkdir()
    (out / "uci_1.json").write_text("{}")
    assert (
        pf.main(["--output", str(out), "--only", "uci:1", "uci:2", "--resume", "--workers", "2"])
        == 0
    )
    assert capsys.readouterr().out.splitlines() == ["uci:2 x", "1 problems, 1 failed"]
    assert _Pool.workers == 2
    assert json.loads((out / "uci_1.json").read_text()) == {}
    assert pf.main(["--output", str(tmp_path / "d"), "--methods", "deep"]) == 0
    assert _Pool.methods == list(pf.DEEP_NAMES)
    with pytest.raises(SystemExit) as stop:
        pf.main(["--output", str(tmp_path / "e"), "--methods", "other"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        pf.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "problem ids, for a quick check" in text and "skip the problems already written" in text


def test_the_classical_family_can_be_named_and_the_options_carry_their_exact_help(
    tmp_path, monkeypatch, capsys
):
    _command(monkeypatch)
    assert pf.main(["--output", str(tmp_path / "c"), "--methods", "classical"]) == 0
    assert _Pool.methods == list(pf.DETECTOR_NAMES)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        pf.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--only [ONLY ...] problem ids, for a quick check" in text
    assert "--resume skip the problems already written" in text
    assert "--methods {classical,deep}" in text


def test_each_finished_problem_is_printed_with_a_flush(tmp_path, monkeypatch):
    _command(monkeypatch)
    flushes = []
    monkeypatch.setattr(pf, "print", lambda *a, **k: flushes.append(k.get("flush")), raising=False)
    assert pf.main(["--output", str(tmp_path / "f")]) == 0
    assert flushes[:3] == [True, True, True] and flushes[3] is None
