"""Training-only statistics, thresholds, caps and reported settings of the LSTM autoencoder."""

import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")  # the locked REAL environment has no PyTorch

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


def _constant_losses(monkeypatch, train_value=2.0, validation_value=1.0):
    """Replace the loss by known constants so that the epoch arithmetic can be checked."""
    real = ld.nn.functional.mse_loss

    def loss(prediction, target):
        value = train_value if prediction.requires_grad else validation_value
        return real(prediction, target) * 0.0 + value

    monkeypatch.setattr(ld.nn.functional, "mse_loss", loss)


def test_the_epoch_loss_is_the_row_weighted_mean_of_the_batch_losses(monkeypatch):
    _constant_losses(monkeypatch)
    model = _fit(model=_model(batch_size=7, max_epochs=2, fit_rows=10_000))[0]
    assert model.settings()["train_loss"] == pytest.approx([2.0, 2.0])
    assert model.settings()["validation_loss"] == [1.0, 1.0]


def test_a_validation_loss_equal_to_the_best_counts_as_no_improvement(monkeypatch):
    monkeypatch.setattr(ld.LSTMAutoencoder, "validation_loss_now", lambda self: 1.0)
    settings = _fit(model=_model(max_epochs=9, patience=2))[0].settings()
    assert settings["epochs_run"] == 3 and settings["best_epoch"] == 1


def test_the_windows_are_centred_and_divided_by_the_training_scale():
    model, _, _ = _fit()
    frame = _frame(20, 9, 400)
    expected = (frame[COLUMNS].to_numpy() - model.center_) / model.scale_
    windows, order = model._windows(frame)
    assert np.allclose(windows[:, -1, :], expected[order])


def test_a_cap_equal_to_the_number_of_windows_keeps_every_window_in_order(monkeypatch):
    seen = {}
    real = ld.LSTMAutoencoder._reconstruction_error

    def spy(self, windows, last_only):
        seen["fit"] = windows
        return real(self, windows, last_only)

    monkeypatch.setattr(ld.LSTMAutoencoder, "_reconstruction_error", spy)
    train = _frame(150, 0)
    model, _, _ = _fit(model=_model(fit_rows=150, validation_rows=60), train=train)
    assert np.array_equal(seen["fit"], model._windows(train)[0])
    assert np.array_equal(
        model._validation.numpy(), model._windows(_frame(60, 1, start=150))[0].astype("float32")
    )


def test_capped_windows_are_distinct_rows_of_the_original_set(monkeypatch):
    seen = {}
    real = ld.LSTMAutoencoder._reconstruction_error

    def spy(self, windows, last_only):
        seen["fit"] = windows
        return real(self, windows, last_only)

    monkeypatch.setattr(ld.LSTMAutoencoder, "_reconstruction_error", spy)
    train = _frame(150, 0)
    model, _, _ = _fit(model=_model(fit_rows=120, validation_rows=50), train=train)
    full = model._windows(train)[0]
    chosen = seen["fit"]
    assert chosen.shape[0] == 120 and np.unique(chosen.reshape(120, -1), axis=0).shape[0] == 120
    assert all(any(np.array_equal(row, source) for source in full) for row in chosen[:5])
    kept = model._validation.numpy().reshape(50, -1)
    assert np.unique(kept, axis=0).shape[0] == 50


def test_the_optimiser_uses_the_configured_learning_rate_and_a_seeded_shuffler(monkeypatch):
    seen = {}
    real_adam, real_randperm = ld.torch.optim.Adam, ld.torch.randperm

    def adam(parameters, **kwargs):
        seen["lr"] = kwargs.get("lr")
        return real_adam(parameters, **kwargs)

    def randperm(n, generator=None):
        seen.setdefault("seed", generator.initial_seed() if generator is not None else None)
        return real_randperm(n, generator=generator)

    monkeypatch.setattr(ld.torch.optim, "Adam", adam)
    monkeypatch.setattr(ld.torch, "randperm", randperm)
    _fit(model=_model(learning_rate=0.05, seed=11))
    assert seen["lr"] == 0.05 and seen["seed"] == 11


def test_fitting_enables_deterministic_algorithms_and_the_configured_threads():
    _fit(model=_model(threads=2))
    assert torch.are_deterministic_algorithms_enabled() is True
    assert torch.get_num_threads() == 2
    torch.set_num_threads(1)


def test_an_event_scoring_exactly_the_threshold_is_not_flagged():
    model, _, _ = _fit()
    frame = _frame(30, 8, 300)
    scores = model.score(frame)
    model.threshold_ = float(scores.iloc[3])
    assert bool(model.flags(frame).iloc[3]) is False


def test_each_unfitted_component_alone_is_enough_to_refuse_scoring():
    model, _, _ = _fit()
    saved = model.center_
    model.center_ = None
    with pytest.raises(RuntimeError, match="not fitted"):
        model.score(_frame(10, 2, 300))
    model.center_ = saved
    model._validation = None
    with pytest.raises(RuntimeError, match="not fitted"):
        model.validation_loss_now()
    fresh = _model()
    assert fresh._history == {} and fresh._validation is None and fresh._net is None


def test_a_column_with_a_spread_below_one_is_scaled_by_that_spread_not_left_unscaled():
    train = _frame(150, 0)
    train["a"] = train["a"] * 0.15  # population spread well below one
    model, _, _ = _fit(train=train)
    spread = train[COLUMNS].astype(float).std(ddof=0).to_numpy()
    assert 0 < spread[0] < 0.5 and model.scale_[0] == pytest.approx(spread[0])
    assert model.scale_[0] != 1.0


def test_numeric_text_columns_are_converted_to_floats_when_fitting_and_scoring():
    train, validation = _frame(150, 0), _frame(60, 1, start=150)
    text_train = train.assign(**{c: train[c].map(repr) for c in COLUMNS})
    text_validation = validation.assign(**{c: validation[c].map(repr) for c in COLUMNS})
    numeric = _fit(train=train, validation=validation)[0]
    text = _fit(train=text_train, validation=text_validation)[0]
    assert np.allclose(text.center_, numeric.center_) and np.allclose(text.scale_, numeric.scale_)
    frame = _frame(20, 4, 300)
    as_text = frame.assign(**{c: frame[c].map(repr) for c in COLUMNS})
    assert np.allclose(text.score(as_text).to_numpy(), text.score(frame).to_numpy())


def test_a_non_improving_first_epoch_still_counts_towards_the_patience(monkeypatch):
    calls = []

    def nan_loss(self):
        calls.append(1)
        return float("nan")

    monkeypatch.setattr(ld.LSTMAutoencoder, "validation_loss_now", nan_loss)
    with pytest.raises(AssertionError):
        _model(max_epochs=9, patience=2).fit(_frame(150, 0), _frame(60, 1, 150), 0.1)
    assert len(calls) == 2
