import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.deep import AE1SVMDetector

pytestmark = pytest.mark.protocol


def _rows(n, seed=0):
    return pd.DataFrame(np.random.default_rng(seed).normal(size=(n, 3)), columns=list("abc"))


@pytest.mark.parametrize("n", [1, 33, 65])
def test_a_batch_that_leaves_one_row_in_the_last_pyod_batch_is_scored(n):
    # PyOD's AE1SVM fails when the last batch of 32 rows holds a single row.
    detector = AE1SVMDetector(contamination=0.05, epochs=2).fit(_rows(100))
    scores = detector.score(_rows(n, seed=4))
    assert len(scores) == n and np.isfinite(scores).all()


def test_the_padding_does_not_change_the_scores_of_the_other_rows():
    detector = AE1SVMDetector(contamination=0.05, epochs=2).fit(_rows(100))
    rows = _rows(40, seed=5)
    np.testing.assert_allclose(
        detector.score(rows.iloc[:33]).to_numpy(),
        detector.score(rows).iloc[:33],
        rtol=1e-4,
        atol=1e-5,
    )


def test_a_custom_batch_size_sets_the_length_that_needs_padding():
    detector = AE1SVMDetector(contamination=0.05, epochs=2, batch_size=10).fit(_rows(100))
    assert len(detector.score(_rows(21, seed=6))) == 21


@pytest.mark.parametrize("n", [33, 65])
def test_a_training_set_that_leaves_one_row_in_the_last_batch_can_be_fitted(n):
    # fit() scores the training rows through the same PyOD code path.
    detector = AE1SVMDetector(contamination=0.05, epochs=2).fit(_rows(n))
    assert len(detector.score(_rows(10, seed=8))) == 10


def test_a_fit_set_with_one_row_too_many_repeats_its_last_row_once():
    detector = AE1SVMDetector(contamination=0.05, epochs=2).fit(_rows(33))
    assert len(detector._model.decision_scores_) == 34
    assert (
        len(AE1SVMDetector(contamination=0.05, epochs=2).fit(_rows(34))._model.decision_scores_)
        == 34
    )
