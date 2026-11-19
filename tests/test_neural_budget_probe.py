"""The T055 budget probe: pre-declared problem selection and the wiring of the paired fits."""

import importlib
import inspect
import json

import numpy as np
import pandas as pd
import pytest

import research.neural_budget_probe as probe
from research.neural_budget_probe import select


def test_selection_is_sorted_bounded_and_evenly_spaced():
    sizes = [100, 400, 900, 6000, 1200, 2000, 3000, 4999, 5000, 5001]
    rows = {f"p{i:02d}": n for i, n in enumerate(sizes)}
    jobs = [{"problem": k} for k in reversed(list(rows))]
    chosen = [j["problem"] for j in select(jobs, rows, count=3)]
    assert chosen == ["p01", "p04", "p06"]
    assert all(300 <= rows[c] <= 5000 for c in chosen)
    assert chosen == [j["problem"] for j in select(jobs[::-1], rows, count=3)]


def test_selection_includes_both_size_bounds_and_never_exceeds_the_count():
    rows = {"a": 299, "b": 300, "c": 5000, "d": 5001}
    jobs = [{"problem": k} for k in rows]
    assert [j["problem"] for j in select(jobs, rows, count=8)] == ["b", "c"]
    many = {f"q{i:02d}": 400 for i in range(20)}
    assert len(select([{"problem": k} for k in many], many, count=8)) == 8
    assert len(select([{"problem": k} for k in many], many)) == 8  # the declared default


def test_the_declared_budgets_are_the_registry_defaults():
    for argument, default, cls in probe.BUDGETS.values():
        module, name = cls.estimator_path
        estimator = getattr(importlib.import_module(module), name)
        assert inspect.signature(estimator.__init__).parameters[argument].default == default
    assert probe.FACTOR == 3 and probe.SEEDS == (42, 1, 2)


class _Fit:
    """A detector stand-in whose scores depend on the epoch budget it was given."""

    name = "stub"
    created: list = []

    def __init__(self, contamination=None, random_state=None, **budget):
        self.contamination, self.random_state, self.budget = contamination, random_state, budget
        _Fit.created.append(self)

    def fit(self, frame):
        self.fit_frame = frame
        return self

    def predict(self, frame):
        return pd.Series(False, index=frame.index)

    def score(self, frame):
        epochs = next(iter(self.budget.values()), 1)
        return pd.Series(np.arange(len(frame), dtype=float) * epochs, index=frame.index)

    def settings(self):
        return {"seed": self.random_state}


def test_scores_are_returned_with_the_sorted_names_of_the_warnings_raised():
    import warnings

    class Noisy(_Fit):
        def fit(self, frame):
            warnings.warn("a", UserWarning, stacklevel=1)
            warnings.warn("b", RuntimeWarning, stacklevel=1)
            return super().fit(frame)

    train = pd.DataFrame({"x": range(30)})
    test = pd.DataFrame({"x": range(5)})
    scores, caught = probe._scores(Noisy(), train, test, seed=0)
    assert scores.tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert caught == ["RuntimeWarning", "UserWarning"]
    assert probe._scores(_Fit(), train, test, seed=0)[1] == []


@pytest.fixture
def toy(monkeypatch):
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({"a": rng.integers(0, 50, 300), "b": rng.normal(size=300)}).astype(
        "string"
    )
    labels = (rng.random(300) < 0.2).astype(int)
    monkeypatch.setattr(probe, "load_raw", lambda job: (frame, labels))
    built = []

    def get_detector(name, contamination):
        detector = _Fit(contamination=contamination)
        detector.name = name
        built.append((name, contamination))
        return detector

    monkeypatch.setattr(probe, "get_detector", get_detector)
    monkeypatch.setattr(
        probe,
        "BUDGETS",
        {name: (arg, default, _Fit) for name, (arg, default, _) in probe.BUDGETS.items()},
    )
    return frame, labels, built


def test_each_detector_is_fitted_at_the_registry_budget_and_at_three_times_it(toy):
    _, labels, _ = toy
    result = probe.probe_problem({"problem": "uci:toy"})
    assert result["problem"] == "uci:toy" and result["rows"] == 300
    runs = [r for r in result["runs"] if "budget" in r]
    assert len(runs) == len(probe.SEEDS) * len(probe.BUDGETS)
    expected = {"vae": 30, "deep_svdd": 100, "ae1svm": 50, "lunar": 200}
    for run in runs:
        assert run["budget"] == expected[run["detector"]]
        assert run["long_budget"] == 3 * run["budget"]
        # same ranking at both budgets: the stand-in scales its scores by the budget only
        assert run["spearman_budget_vs_long"] == pytest.approx(1.0)
        assert run["ap_budget"] == pytest.approx(run["ap_long"])
        assert 0.0 <= run["ap_budget"] <= 1.0
        assert (run["nonfinite"], run["warnings"]) == (0, [])
    assert {(r["detector"], r["seed"]) for r in runs} == {
        (d, s) for d in expected for s in probe.SEEDS
    }


def test_the_autoencoder_settings_are_recorded_once_per_seed_with_its_own_seed(toy):
    result = probe.probe_problem({"problem": "uci:toy"})
    ae = [r for r in result["runs"] if r["detector"] == "autoencoder"]
    assert [r["seed"] for r in ae] == list(probe.SEEDS)
    assert [r["settings"] for r in ae] == [{"seed": s} for s in probe.SEEDS]


def test_the_budget_argument_reaches_the_long_detector_only(toy, monkeypatch):
    seen = []

    class Spy(_Fit):
        def __init__(self, **kwargs):
            seen.append(kwargs)
            super().__init__(**kwargs)

    monkeypatch.setattr(probe, "BUDGETS", {"vae": ("epoch_num", 30, Spy)})
    probe.probe_problem({"problem": "uci:toy"})
    first = seen[:2]
    assert first[0].keys() == {"contamination", "random_state"}
    assert first[1]["epoch_num"] == 90 and first[1]["random_state"] == probe.SEEDS[0]
    assert first[0]["contamination"] == first[1]["contamination"]
    assert 0 < first[0]["contamination"] < 1


def test_dif_scores_are_compared_across_model_seeds_on_one_fixed_partition(toy, monkeypatch):
    frame, labels, built = toy

    class Seeded(_Fit):
        def score(self, frame):  # identical ranking for seeds 42 and 1, reversed for seed 2
            order = np.arange(len(frame), dtype=float)
            return pd.Series(-order if self.random_state == 2 else order, index=frame.index)

    monkeypatch.setattr(probe, "get_detector", lambda name, c: Seeded(contamination=c))
    pairs = probe.dif_seed_spearman(frame, labels)
    assert pairs == pytest.approx([1.0, -1.0, -1.0])


def test_the_command_probes_the_selected_problems_and_writes_the_protocol(tmp_path, monkeypatch):
    archive = (
        probe.Path(probe.__file__).resolve().parents[1] / "verification/evidence/labelled_pool/runs"
    )
    rows = {}
    for path in archive.glob("*.json"):
        d = json.loads(path.read_text())
        rows[d["problem"]] = d["rows"]
    jobs = [{"problem": name} for name in sorted(rows)] + [{"problem": "not:archived"}]
    monkeypatch.setattr(probe.lb, "jobs", lambda *_: jobs)
    monkeypatch.setattr(probe, "probe_problem", lambda job: {"problem": job["problem"]})
    out = tmp_path / "probe.json"
    assert probe.main(["--output", str(out)]) == 0
    body = json.loads(out.read_text())
    assert body["protocol"] == "neural-budget-probe-v1"
    chosen = [r["problem"] for r in body["results"]]
    assert chosen == [j["problem"] for j in select([j for j in jobs if j["problem"] in rows], rows)]
    assert len(chosen) == 8 and "not:archived" not in chosen


def test_every_fit_reads_the_prepared_training_rows_of_its_own_seed(toy, monkeypatch):
    frame, labels, built = toy
    _Fit.created.clear()
    jobs, splits = [], []
    real_split = probe.grouped_split
    monkeypatch.setattr(probe, "load_raw", lambda job: (jobs.append(job), (frame, labels))[1])
    monkeypatch.setattr(
        probe, "grouped_split", lambda f, y, seed: (splits.append(seed), real_split(f, y, seed))[1]
    )
    result = probe.probe_problem({"problem": "uci:toy"})
    assert jobs == [{"problem": "uci:toy"}]
    assert splits == [*probe.SEEDS, probe.SEEDS[0]]  # one split per seed, one fixed for DIF
    per_seed = len(probe.BUDGETS) * 2 + 1  # a pair per gradient detector and the autoencoder
    for k, seed in enumerate(probe.SEEDS):
        parts = real_split(frame, labels, seed)
        prepared = probe.prepare_frozen(frame, parts)
        contamination = probe.clip_contamination(float(labels[parts["train"]].mean()))
        for detector in _Fit.created[k * per_seed : (k + 1) * per_seed]:
            assert list(detector.fit_frame.columns) == [
                f"f{i}" for i in range(prepared["train"].shape[1])
            ]
            assert len(detector.fit_frame) == len(parts["train"])
            assert detector.random_state in (seed, None)
            assert detector.contamination == contamination
    assert [name for name, _ in built] == ["autoencoder"] * 3 + ["dif"] * 3
    assert len(result["dif_seed_spearman"]) == 3


def test_the_dif_check_uses_the_first_seed_split_and_the_dif_detector(toy, monkeypatch):
    frame, labels, built = toy
    built.clear()
    _Fit.created.clear()
    seen = []
    real_split = probe.grouped_split
    monkeypatch.setattr(
        probe, "grouped_split", lambda f, y, seed: (seen.append(seed), real_split(f, y, seed))[1]
    )
    probe.dif_seed_spearman(frame, labels)
    assert seen == [probe.SEEDS[0]]
    assert [name for name, _ in built] == ["dif"] * 3
    assert [d.random_state for d in _Fit.created] == list(probe.SEEDS)
    parts = real_split(frame, labels, probe.SEEDS[0])
    expected = probe.clip_contamination(float(labels[parts["train"]].mean()))
    assert {d.contamination for d in _Fit.created} == {expected}
    prepared = probe.prepare_frozen(frame, parts)
    assert all(
        list(d.fit_frame.columns) == [f"f{i}" for i in range(prepared["train"].shape[1])]
        for d in _Fit.created
    )


def test_a_neural_detector_is_fitted_on_a_seeded_sample_above_the_cap():
    train = pd.DataFrame({"x": np.arange(20_500.0)})
    test = pd.DataFrame({"x": np.arange(5.0)})
    detector = _Fit()
    detector.name = "vae"
    scores, _ = probe._scores(detector, train, test, seed=7)
    assert scores.dtype == np.float64
    expected = train.sample(n=20_000, random_state=7)
    assert detector.fit_frame.index.equals(expected.index)


def test_scores_are_floats_even_when_the_detector_returns_integers():
    class Ints(_Fit):
        def score(self, frame):
            return pd.Series(np.arange(len(frame)), index=frame.index)

    scores, _ = probe._scores(
        Ints(), pd.DataFrame({"x": range(30)}), pd.DataFrame({"x": range(4)}), 0
    )
    assert scores.dtype == np.float64


def test_the_command_reads_the_repository_data_and_writes_an_indented_file(
    tmp_path, monkeypatch, capsys
):
    root = probe.Path(probe.__file__).resolve().parents[1]
    seen = {}
    monkeypatch.setattr(
        probe.lb, "jobs", lambda *args: (seen.update(args=args), [{"problem": "x"}])[1]
    )
    monkeypatch.setattr(probe, "probe_problem", lambda job: {"problem": job["problem"]})
    out = tmp_path / "probe.json"
    probe.main(["--output", str(out)])
    assert seen["args"] == (
        root / "verification/evidence/dataset_registry",
        root / "data/adbench",
        root / "data/pool",
    )
    assert out.read_text().startswith('{\n "protocol"')
    with pytest.raises(SystemExit):
        probe.main([])
    with pytest.raises(SystemExit):
        probe.main(["--help"])
    assert "Bounded prospective convergence probe" in capsys.readouterr().out
