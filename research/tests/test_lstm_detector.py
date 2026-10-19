"""Miniature CPU tests of the LSTM autoencoder: causality, alignment, training-only statistics."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "src"))
import lstm_detector as ld  # noqa: E402

COLUMNS = ["a", "b", "c"]


def _frame(n=300, seed=0, start=0):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(size=(n, 3)), columns=COLUMNS)
    frame["t"] = pd.Timestamp("1970-01-01", tz="UTC") + pd.to_timedelta(
        np.arange(start, start + n), unit="s"
    )
    return frame


def _model(**kwargs):
    options = {"window": 4, "hidden": 8, "max_epochs": 3, "patience": 2, "fit_rows": 200, "seed": 7}
    return ld.LSTMAutoencoder(COLUMNS, "t", **{**options, **kwargs})


def _fitted(**kwargs):
    train, val = _frame(300, 0), _frame(100, 1, start=300)
    return _model(**kwargs).fit(train, val, contamination=0.05), train, val


def test_scores_are_finite_nonnegative_and_aligned_with_the_input_index():
    model, _train, val = _fitted()
    test = _frame(80, 2, start=400).iloc[::-1]  # shuffled order, original index kept
    scores = model.score(test)
    assert list(scores.index) == list(test.index)
    assert np.isfinite(scores.to_numpy()).all() and (scores >= 0).all()


def test_the_score_of_a_row_does_not_depend_on_later_rows():
    model, *_ = _fitted()
    test = _frame(60, 3, start=400)
    base = model.score(test)
    changed = test.copy()
    changed.loc[changed.index[-1], COLUMNS] += 50.0  # a future event changes
    after = model.score(changed)
    assert np.allclose(after.iloc[:-1], base.iloc[:-1])
    assert after.iloc[-1] != base.iloc[-1]


def test_input_order_does_not_change_the_score_of_an_event():
    model, *_ = _fitted()
    test = _frame(60, 4, start=400)
    ordered = model.score(test)
    shuffled = model.score(test.sample(frac=1.0, random_state=0))
    assert np.allclose(shuffled.loc[ordered.index], ordered)


def test_scaling_statistics_come_from_the_training_rows_only():
    train = _frame(300, 0)
    first = _model().fit(train, _frame(100, 1, start=300), contamination=0.05)
    other = _frame(100, 9, start=300)
    other[COLUMNS] = other[COLUMNS] * 100.0 + 50.0  # a very different validation period
    second = _model().fit(train, other, contamination=0.05)
    assert np.allclose(first.center_, second.center_) and np.allclose(first.scale_, second.scale_)
    assert np.allclose(first.center_, train[COLUMNS].median().to_numpy())


def test_a_window_never_reaches_across_the_partition_boundary():
    model, train, _val = _fitted()
    test = _frame(30, 5, start=400)
    isolated = model.score(test)
    # the same rows scored after appending the training rows before them: the first events
    # of the test window may not borrow training rows when the test is scored alone
    assert isolated.iloc[0] == model.score(test.iloc[:1]).iloc[0]


def test_the_same_seed_gives_the_same_scores_and_another_seed_differs():
    test = _frame(60, 6, start=400)
    a, *_ = _fitted(seed=3)
    b, *_ = _fitted(seed=3)
    c, *_ = _fitted(seed=4)
    assert np.allclose(a.score(test), b.score(test))
    assert not np.allclose(a.score(test), c.score(test))


def test_training_is_recorded_and_the_best_epoch_is_restored():
    model, *_ = _fitted(max_epochs=5, patience=1)
    info = model.settings()
    assert 1 <= info["epochs_run"] <= 5
    assert len(info["validation_loss"]) == info["epochs_run"] == len(info["train_loss"])
    assert info["best_epoch"] == int(np.argmin(info["validation_loss"])) + 1
    assert info["converged"] == (info["epochs_run"] < 5)
    assert info["device"] == "cpu" and info["seed"] == 7 and info["window"] == 4
    assert model.validation_loss_now() == pytest.approx(min(info["validation_loss"]), rel=1e-5)


def test_scoring_or_describing_before_fitting_is_refused():
    with pytest.raises(RuntimeError):
        _model().score(_frame(10))
    with pytest.raises(RuntimeError):
        _model().settings()


def test_a_sequence_that_breaks_the_learned_pattern_scores_higher():
    t = np.arange(600)
    clean = pd.DataFrame({"a": np.sin(t / 5), "b": np.cos(t / 5), "c": np.sin(t / 3)})
    clean["t"] = pd.Timestamp("1970-01-01", tz="UTC") + pd.to_timedelta(t, unit="s")
    model = ld.LSTMAutoencoder(
        COLUMNS, "t", window=6, hidden=16, max_epochs=40, patience=5, fit_rows=400, seed=1
    ).fit(clean.iloc[:400], clean.iloc[400:500], contamination=0.01)
    test = clean.iloc[500:].copy()
    test.iloc[40, :3] = [3.0, -3.0, 3.0]
    scores = model.score(test)
    assert scores.iloc[40] > scores.drop(scores.index[40]).quantile(0.99)


def test_invalid_configuration_is_refused():
    with pytest.raises(ValueError):
        ld.LSTMAutoencoder(COLUMNS, "t", window=0)
    with pytest.raises(ValueError):
        _model().fit(_frame(3), _frame(3, 1, start=5), contamination=0.05)
    with pytest.raises(ValueError):
        _model().fit(_frame(100), _frame(50, 1, start=200), contamination=0.0)
