"""Training-only statistics, thresholds, caps and reported settings of the LSTM autoencoder."""

import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "src"))
import lstm_detector as ld  # noqa: E402

COLUMNS = ["a", "b"]


def _frame(n=200, seed=0, start=0, constant=False):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(loc=3.0, scale=2.0, size=(n, 2)), columns=COLUMNS)
    if constant:
        frame["b"] = 5.0
    frame["t"] = pd.Timestamp("1970-01-01", tz="UTC") + pd.to_timedelta(
        np.arange(start, start + n), unit="s"
    )
    return frame


def _model(**kwargs):
    options = {"window": 3, "hidden": 4, "max_epochs": 3, "patience": 2, "fit_rows": 100, "seed": 5}
    return ld.LSTMAutoencoder(COLUMNS, "t", **{**options, **kwargs})


def _fit(model=None, train=None, validation=None, contamination=0.1):
    model = model or _model()
    train = _frame(150, 0) if train is None else train
    validation = _frame(60, 1, start=150) if validation is None else validation
    return model.fit(train, validation, contamination), train, validation


@pytest.mark.parametrize("name", ["window", "hidden", "max_epochs", "patience"])
def test_every_size_and_budget_must_be_positive(name):
    with pytest.raises(ValueError) as caught:
        _model(**{name: 0})
    assert str(caught.value) == "window, hidden, max_epochs and patience must be positive"
    assert _model(**{name: 1}).__getattribute__(name) == 1


def test_the_constructor_stores_every_option():
    model = ld.LSTMAutoencoder(
        ["a", "b"], "t", window=5, hidden=6, max_epochs=7, patience=8, batch_size=9,
        learning_rate=0.5, fit_rows=11, validation_rows=12, seed=13, threads=2,
    )  # fmt: skip
    assert (model.columns, model.time_column) == (["a", "b"], "t")
    assert (model.window, model.hidden, model.max_epochs, model.patience) == (5, 6, 7, 8)
    assert (model.batch_size, model.learning_rate) == (9, 0.5)
    assert (model.fit_rows, model.validation_rows, model.seed, model.threads) == (11, 12, 13, 2)
    assert model.center_ is None and model.scale_ is None and model.threshold_ is None
    defaults = ld.LSTMAutoencoder(["a"], "t")
    assert (defaults.window, defaults.hidden, defaults.max_epochs, defaults.patience) == (
        10,
        32,
        20,
        3,
    )
    assert (defaults.batch_size, defaults.learning_rate, defaults.seed, defaults.threads) == (
        256,
        1e-3,
        42,
        1,
    )  # noqa: E501
    assert (defaults.fit_rows, defaults.validation_rows) == (50_000, 20_000)


@pytest.mark.parametrize("contamination", [0.0, 0.5, -0.1, 0.9])
def test_the_contamination_must_lie_strictly_between_zero_and_one_half(contamination):
    with pytest.raises(ValueError) as caught:
        _model().fit(_frame(150), _frame(60, 1, 150), contamination)
    assert str(caught.value) == "contamination must be in (0, 0.5)"


def test_the_extreme_valid_contaminations_and_exact_window_sized_partitions_are_accepted():
    _fit(contamination=0.4999)
    _fit(contamination=0.0001)
    model = _model(window=3).fit(_frame(3), _frame(3, 1, 3), 0.1)
    assert model.threshold_ is not None


@pytest.mark.parametrize(("train", "validation"), [(2, 60), (150, 2)])
def test_a_partition_shorter_than_one_window_is_refused(train, validation):
    with pytest.raises(ValueError) as caught:
        _model(window=3).fit(_frame(train), _frame(validation, 1, 150), 0.1)
    assert str(caught.value) == "the training and validation rows must fill at least one window"


def test_the_statistics_come_from_the_training_rows_with_a_population_spread():
    train = _frame(150, 0)
    model, _, _ = _fit(train=train)
    values = train[COLUMNS].astype(float)
    assert np.allclose(model.center_, values.median().to_numpy())
    assert np.allclose(model.scale_, values.std(ddof=0).to_numpy())
    assert not np.allclose(model.scale_, values.std(ddof=1).to_numpy())


def test_a_constant_training_column_gets_unit_scale_and_finite_scores():
    model, train, validation = _fit(train=_frame(150, 0, constant=True))
    assert model.scale_[1] == 1.0 and model.scale_[0] > 0
    assert np.isfinite(model.score(_frame(40, 3, 200, constant=True)).to_numpy()).all()
    assert np.isfinite(model.threshold_)


def test_missing_values_are_replaced_by_the_training_median_before_scaling():
    model, train, _ = _fit()
    frame = _frame(30, 4, 300)
    holey = frame.copy()
    holey.loc[holey.index[5], "a"] = np.nan
    imputed = frame.copy()
    imputed.loc[imputed.index[5], "a"] = model.center_[0]
    assert np.array_equal(model._windows(holey)[0], model._windows(imputed)[0])


def test_the_threshold_is_the_training_quantile_of_the_last_row_errors():
    model, train, _ = _fit(model=_model(fit_rows=10_000), contamination=0.2)
    errors = model._reconstruction_error(model._windows(train)[0], last_only=True)
    assert model.threshold_ == pytest.approx(float(np.quantile(errors, 0.8)))


def test_flags_are_scores_strictly_above_the_threshold():
    model, _, _ = _fit()
    frame = _frame(50, 6, 300)
    scores = model.score(frame)
    model.threshold_ = float(scores.median())
    assert (model.flags(frame) == (scores > model.threshold_)).all()
    assert not model.flags(frame).all() and model.flags(frame).any()


def test_the_fit_and_validation_windows_are_capped_by_their_budgets(monkeypatch):
    seen = {}
    real = ld.LSTMAutoencoder._reconstruction_error

    def spy(self, windows, last_only):
        seen.setdefault("fit", len(windows)) if last_only else None
        return real(self, windows, last_only)

    monkeypatch.setattr(ld.LSTMAutoencoder, "_reconstruction_error", spy)
    model, _, _ = _fit(model=_model(fit_rows=40, validation_rows=7))
    assert seen["fit"] == 40 and len(model._validation) == 7


def test_the_uncapped_windows_are_all_used_when_within_the_budget(monkeypatch):
    model, _, _ = _fit(model=_model(fit_rows=10_000, validation_rows=10_000))
    assert len(model._validation) == 60


def test_the_history_and_settings_report_what_was_run():
    model, _, _ = _fit(model=_model(max_epochs=4, patience=2, batch_size=16, learning_rate=0.01))
    settings = model.settings()
    epochs = settings["epochs_run"]
    assert 1 <= epochs <= 4
    assert len(settings["train_loss"]) == len(settings["validation_loss"]) == epochs
    assert settings["best_epoch"] == int(np.argmin(settings["validation_loss"])) + 1
    assert settings["converged"] is (epochs < 4)
    keys = ("window", "hidden", "max_epochs", "patience", "batch_size")
    assert {k: settings[k] for k in keys} == {
        "window": 3, "hidden": 4, "max_epochs": 4, "patience": 2, "batch_size": 16,
    }  # fmt: skip
    assert settings["learning_rate"] == 0.01 and settings["fit_rows"] == 100
    assert (settings["seed"], settings["threads"], settings["device"]) == (5, 1, "cpu")
    assert settings["deterministic_algorithms"] is True
    assert settings["versions"] == {"torch": version("torch"), "numpy": version("numpy")}


def test_a_single_epoch_budget_is_reported_as_not_converged():
    settings = _fit(model=_model(max_epochs=1))[0].settings()
    assert settings["epochs_run"] == 1 and settings["converged"] is False
    assert settings["best_epoch"] == 1


def test_early_stopping_waits_for_the_patience(monkeypatch):
    values = iter([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    monkeypatch.setattr(ld.LSTMAutoencoder, "validation_loss_now", lambda self: next(values))
    model = _fit(model=_model(max_epochs=6, patience=2))[0]
    assert model.settings()["epochs_run"] == 3 and model.settings()["best_epoch"] == 1
    values = iter([3.0, 2.0, 1.0, 1.5, 1.6, 1.7, 1.8])
    monkeypatch.setattr(ld.LSTMAutoencoder, "validation_loss_now", lambda self: next(values))
    model = _fit(model=_model(max_epochs=7, patience=3))[0]
    assert model.settings()["epochs_run"] == 6 and model.settings()["best_epoch"] == 3


def test_unfitted_use_is_refused_with_the_exact_reason():
    model = _model()
    for call in (model.settings, model.validation_loss_now, lambda: model.score(_frame(10))):
        with pytest.raises(RuntimeError) as caught:
            call()
        assert str(caught.value) == "the model is not fitted"


def test_errors_are_the_mean_squared_reconstruction_error_in_batches_of_2048():
    model, train, _ = _fit()
    rng = np.random.default_rng(0)
    windows = rng.normal(size=(2100, 3, 2)).astype(np.float32)
    batch = torch.as_tensor(windows)
    model._net.eval()
    with torch.no_grad():
        error = (model._net(batch) - batch) ** 2
    assert np.allclose(model._reconstruction_error(windows, True), error[:, -1].mean(-1).numpy())
    assert np.allclose(model._reconstruction_error(windows, False), error.mean((1, 2)).numpy())
    assert model._reconstruction_error(windows, True).shape == (2100,)
    assert model._reconstruction_error(windows, True).dtype == np.float64


def test_the_validation_loss_matches_an_independent_computation():
    model, _, _ = _fit()
    val = model._validation
    with torch.no_grad():
        expected = float(((model._net.eval()(val) - val) ** 2).mean())
    assert model.validation_loss_now() == pytest.approx(expected)


def test_the_same_seed_reproduces_the_fitted_model_exactly():
    one, _, _ = _fit()
    two, _, _ = _fit()
    assert one.threshold_ == two.threshold_
    assert one.settings()["train_loss"] == two.settings()["train_loss"]
    assert _fit(model=_model(seed=6))[0].threshold_ != one.threshold_
