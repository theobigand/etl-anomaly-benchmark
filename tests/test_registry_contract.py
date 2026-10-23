"""Every registered detector, present or future, must satisfy the same contract."""

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import registry

pytestmark = pytest.mark.protocol

NAMES = [*registry.ALL_NAMES, *registry.DEEP_NAMES]

# A detector may leave a check only for a stated reason, and only from this list.
EXEMPT = {
    "drift": {
        "batch_independence": "scores a whole recent window against a time-ordered reference",
        "orientation": "silent no-op without a timestamp column",
    },
}


# The networks run in float32, so a row scored alone and in a batch differs by rounding.
FLOAT32 = {"vae", "deep_svdd", "dif", "ae1svm", "lunar"}


def _train(n=200, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=n)
    return pd.DataFrame(
        {
            "a": base,
            "b": 0.8 * base + rng.normal(0, 0.2, size=n),
            "c": rng.normal(size=n),
        }
    )


def _covered(check):
    return [name for name in NAMES if check not in EXEMPT.get(name, {})]


def test_exemptions_are_few_and_justified():
    assert set(EXEMPT) <= {"drift"}
    assert all(reason for checks in EXEMPT.values() for reason in checks.values())


@pytest.mark.parametrize("name", NAMES)
def test_registry_builds_a_named_unfitted_detector(name):
    detector = registry.get_detector(name)
    assert detector.name == name
    for method in (detector.predict, detector.score):
        with pytest.raises(RuntimeError, match="not fitted"):
            method(_train(20))


@pytest.mark.parametrize("name", NAMES)
def test_outputs_are_aligned_typed_and_finite(name):
    train = _train()
    probe = train.iloc[:25].set_axis(range(500, 525))
    detector = registry.get_detector(name, ml_contamination=0.1)
    assert detector.fit(train) is detector
    flags, scores = detector.predict(probe), detector.score(probe)
    assert flags.index.equals(probe.index) and scores.index.equals(probe.index)
    assert pd.api.types.is_bool_dtype(flags)
    assert pd.api.types.is_float_dtype(scores)
    assert np.isfinite(scores.to_numpy()).all()


@pytest.mark.parametrize("name", NAMES)
def test_two_fits_on_the_same_training_rows_agree(name):
    train, probe = _train(), _train(30, seed=5)
    first = registry.get_detector(name).fit(train).score(probe)
    second = registry.get_detector(name).fit(train).score(probe)
    pd.testing.assert_series_equal(first, second)


@pytest.mark.parametrize("name", _covered("batch_independence"))
def test_a_rows_score_does_not_depend_on_the_rest_of_the_batch(name):
    detector = registry.get_detector(name).fit(_train())
    batch = _train(12, seed=9) + 2.0
    together = detector.score(batch)
    alone = pd.concat([detector.score(batch.iloc[[i]]) for i in range(len(batch))])
    tolerance = {"rtol": 1e-4, "atol": 1e-5} if name in FLOAT32 else {"atol": 1e-9}
    np.testing.assert_allclose(together.to_numpy(), alone.to_numpy(), **tolerance)


@pytest.mark.parametrize("name", _covered("orientation"))
def test_an_obvious_outlier_scores_above_typical_rows(name):
    train = _train()
    detector = registry.get_detector(name).fit(train)
    typical = detector.score(train.iloc[:50]).median()
    outlier = detector.score(pd.DataFrame({"a": [9.0], "b": [-9.0], "c": [9.0]}))
    assert outlier.iloc[0] > typical


@pytest.mark.parametrize("name", NAMES)
def test_constant_and_missing_inputs_give_finite_scores(name):
    train = _train().assign(c=1.0)
    probe = _train(10, seed=3).assign(c=1.0)
    probe.loc[probe.index[0], "a"] = np.nan
    detector = registry.get_detector(name).fit(train)
    assert np.isfinite(detector.score(probe).to_numpy()).all()
    assert detector.predict(probe).dtype == bool
