import warnings

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import config
from etl_benchmark.pipeline import detect
from etl_benchmark.quality.autoencoder import AutoencoderDetector

pytestmark = pytest.mark.protocol


def _correlated(n=300, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=n)
    return pd.DataFrame({"a": base, "b": 2 * base + rng.normal(0, 0.1, n), "c": -base})


def test_rows_that_break_the_learned_correlation_have_larger_reconstruction_error():
    train = _correlated()
    detector = AutoencoderDetector(contamination=0.05).fit(train)
    consistent = pd.DataFrame({"a": [1.0], "b": [2.0], "c": [-1.0]})
    broken = pd.DataFrame({"a": [1.0], "b": [-2.0], "c": [1.0]})
    assert detector.score(broken).iloc[0] > 3 * detector.score(consistent).iloc[0]
    assert detector.predict(broken).iloc[0]
    assert not detector.predict(consistent).iloc[0]


def test_the_threshold_comes_from_training_scores_and_contamination():
    train = _correlated()
    detector = AutoencoderDetector(contamination=0.1).fit(train)
    assert detector.predict(train).mean() == pytest.approx(0.1, abs=0.02)


def test_normalisation_and_threshold_ignore_the_evaluated_rows_and_labels():
    train = _correlated()
    test = pd.DataFrame({"a": [1000.0, -1000.0], "b": [1.0, 1.0], "c": [0.0, 0.0], "label": [0, 1]})
    detector = AutoencoderDetector()
    detect(test, detector, label_column="label", fit_df=train.assign(label=0))
    assert detector.feature_names_ == ["a", "b", "c"]
    assert detector._scaler.mean_[0] == pytest.approx(train["a"].mean())
    assert detector._model.threshold_ == pytest.approx(np.quantile(detector.score(train), 0.9))


def test_the_fit_is_deterministic_for_a_seed_and_changes_with_it():
    train, probe = _correlated(), _correlated(20, seed=4)
    first = AutoencoderDetector(random_state=1).fit(train).score(probe)
    again = AutoencoderDetector(random_state=1).fit(train).score(probe)
    other = AutoencoderDetector(random_state=2).fit(train).score(probe)
    pd.testing.assert_series_equal(first, again)
    assert not np.allclose(first, other)


def test_the_default_seed_is_the_project_seed():
    assert AutoencoderDetector().random_state == config.RANDOM_SEED


def test_settings_record_the_seed_budget_and_library_versions():
    train = _correlated()
    detector = AutoencoderDetector(max_iter=150).fit(train)
    settings = detector.settings()
    assert settings["random_state"] == config.RANDOM_SEED
    assert settings["max_iter"] == 150
    assert settings["hidden_layer_sizes"] == [3, 1, 3]
    assert isinstance(settings["converged"], bool)
    assert settings["n_iter"] <= 150
    assert set(settings["versions"]) == {"scikit-learn", "numpy"}
    assert settings["device"] == "cpu"


def test_settings_are_unavailable_before_fitting():
    with pytest.raises(
        RuntimeError, match="^autoencoder detector not fitted. Call fit\\(\\) first.$"
    ):
        AutoencoderDetector().settings()


def test_an_exhausted_training_budget_is_reported_not_hidden():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        detector = AutoencoderDetector(max_iter=2).fit(_correlated())
    assert detector.settings()["converged"] is False


def test_hidden_layers_follow_the_feature_count():
    wide = pd.DataFrame(np.random.default_rng(0).normal(size=(60, 8)))
    wide.columns = [f"f{i}" for i in range(8)]
    assert AutoencoderDetector(max_iter=5).fit(wide).settings()["hidden_layer_sizes"] == [8, 4, 8]
    narrow = wide[["f0"]]
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a single feature must not trigger a shape warning
        fitted = AutoencoderDetector(max_iter=5).fit(narrow)
    assert fitted.settings()["hidden_layer_sizes"] == [2, 1, 2]
    assert fitted.score(narrow).shape == (60,)


def test_reconstruction_errors_are_non_negative_squared_errors():
    train = _correlated()
    detector = AutoencoderDetector().fit(train)
    assert (detector.score(train) >= 0).all()
    assert detector.score(train.iloc[[0]]).iloc[0] == pytest.approx(
        np.mean(
            (
                detector._matrix(train.iloc[[0]])
                - detector._model.network_.predict(detector._matrix(train.iloc[[0]]))
            )
            ** 2
        )
    )


def test_only_rows_strictly_above_the_training_quantile_are_flagged():
    train = _correlated(101)
    detector = AutoencoderDetector(contamination=0.1).fit(train)
    assert int(detector.predict(train).sum()) == 10


def test_explicit_columns_and_contamination_reach_the_model():
    train = _correlated()
    detector = AutoencoderDetector(contamination=0.3, columns=["a", "b"]).fit(train)
    assert detector.feature_names_ == ["a", "b"]
    assert detector.contamination == 0.3
    assert detector.predict(train).mean() == pytest.approx(0.3, abs=0.03)


def test_default_training_budget_and_reported_settings_keys():
    assert AutoencoderDetector().max_iter == 300
    settings = AutoencoderDetector(contamination=0.2).fit(_correlated()).settings()
    assert set(settings) == {
        "contamination",
        "hidden_layer_sizes",
        "max_iter",
        "n_iter",
        "converged",
        "random_state",
        "device",
        "versions",
    }
    assert settings["contamination"] == 0.2


def test_a_run_that_stops_before_the_budget_is_reported_as_converged():
    train = _correlated()
    assert AutoencoderDetector(max_iter=5000).fit(train).settings()["converged"] is True
