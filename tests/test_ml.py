import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.ml import (
    COPODDetector,
    ECODDetector,
    HBOSDetector,
    IsolationForestDetector,
    KNNDetector,
    LOFDetector,
    OneClassSVMDetector,
    PCADetector,
)

ML_DETECTORS = [
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
    ECODDetector,
    COPODDetector,
    HBOSDetector,
    KNNDetector,
    PCADetector,
]
# A linear projection cannot flag a shift that stays inside the components it keeps, and
# the isotropic blob below needs all of them, so PCA has its own planted-outlier tests.
SHIFTED = [cls for cls in ML_DETECTORS if cls is not PCADetector]


def _blob_with_outliers(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, size=(n, 3))
    x[-5:] += 25.0  # five gross outliers
    return pd.DataFrame(x, columns=["a", "b", "c"])


@pytest.mark.parametrize("cls", SHIFTED)
def test_ml_detector_flags_planted_outliers(cls):
    df = _blob_with_outliers()

    det = cls(contamination=0.05).fit(df)
    flags = det.predict(df)

    assert flags.iloc[-5:].all()  # every planted outlier is caught
    assert flags.iloc[:-5].mean() < 0.10  # few false positives on the blob


@pytest.mark.parametrize("cls", SHIFTED)
def test_ml_detector_score_ranks_outliers_highest(cls):
    df = _blob_with_outliers()

    scores = cls(contamination=0.05).fit(df).score(df)

    assert scores.index.equals(df.index)
    assert scores.iloc[-5:].min() > scores.iloc[:-5].max()


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_predict_before_fit_raises(cls):
    with pytest.raises(RuntimeError):
        cls().predict(_blob_with_outliers())


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_score_before_fit_raises(cls):
    with pytest.raises(RuntimeError, match="not fitted"):
        cls().score(_blob_with_outliers())


def test_ml_detector_rejects_missing_preprocessing_state():
    frame = _blob_with_outliers()
    detector = IsolationForestDetector().fit(frame)
    detector._scaler = None
    with pytest.raises(RuntimeError, match="not fitted"):
        detector.score(frame)


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_ignores_non_numeric_and_imputes_nans(cls):
    df = _blob_with_outliers()
    df["label"] = "keep"  # non-numeric, must be dropped silently
    df.loc[3, "a"] = np.nan  # must be imputed, not crash

    det = cls(contamination=0.05).fit(df)
    flags = det.predict(df)

    assert det.feature_names_ == ["a", "b", "c"]
    assert len(flags) == len(df)


@pytest.mark.parametrize("cls", ML_DETECTORS)
def test_ml_detector_raises_without_numeric_columns(cls):
    df = pd.DataFrame({"city": ["paris", "lyon", "nice"]})

    with pytest.raises(ValueError):
        cls().fit(df)


def test_ml_detectors_have_distinct_names():
    names = {cls().name for cls in ML_DETECTORS}
    assert names == {
        "isolation_forest",
        "lof",
        "ocsvm",
        "ecod",
        "copod",
        "hbos",
        "knn",
        "pca",
    }


def test_none_of_the_new_detectors_takes_a_seed():
    for cls in (ECODDetector, COPODDetector, HBOSDetector, KNNDetector, PCADetector):
        assert not cls.supports_random_state


def test_pca_scores_the_squared_error_of_a_reconstruction_that_keeps_95_percent_of_the_variance():
    rng = np.random.default_rng(2)
    base = rng.normal(size=500)
    frame = pd.DataFrame({"a": base, "b": 2 * base, "c": base + rng.normal(0, 0.05, 500)})
    detector = PCADetector(contamination=0.05).fit(frame)
    pca = detector._model.pca_
    assert pca.n_components_ == 1 and pca.explained_variance_ratio_.sum() >= 0.95
    probe = frame.iloc[:3]
    x = detector._matrix(probe)
    expected = ((x - pca.inverse_transform(pca.transform(x))) ** 2).mean(axis=1)
    np.testing.assert_allclose(detector.score(probe), expected)


def test_marginal_detectors_miss_a_pair_that_only_the_joint_distribution_reveals():
    # Each coordinate is ordinary on its own; only the pair (3, -3) breaks the correlation.
    rng = np.random.default_rng(1)
    base = rng.normal(size=400)
    frame = pd.DataFrame({"a": base, "b": base + rng.normal(0, 0.1, 400)})
    frame.loc[len(frame)] = [2.5, -2.5]
    last = len(frame) - 1
    for cls in (ECODDetector, COPODDetector, HBOSDetector):
        scores = cls(contamination=0.02).fit(frame).score(frame)
        assert scores.rank(ascending=False)[last] > 3  # not among the top rows
    for cls in (KNNDetector, PCADetector):
        scores = cls(contamination=0.02).fit(frame).score(frame)
        assert scores.rank(ascending=False)[last] <= 3  # a joint model sees it


def test_pca_flags_rows_that_break_the_correlation_it_kept():
    rng = np.random.default_rng(3)
    base = rng.normal(size=400)
    frame = pd.DataFrame({"a": base, "b": 2 * base + rng.normal(0, 0.05, 400), "c": -base})
    broken = pd.DataFrame({"a": [1.0, -2.0], "b": [-2.0, 4.0], "c": [-1.0, 0.0]})
    detector = PCADetector(contamination=0.05).fit(frame)
    scores = detector.score(broken)
    assert scores.min() > detector.score(frame).max()
    assert detector.predict(broken).all()


def _correlated_train(n=200, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=n)
    return pd.DataFrame(
        {"a": base, "b": 0.8 * base + rng.normal(0, 0.2, n), "c": rng.exponential(size=n)}
    )


@pytest.mark.parametrize("cls", [ECODDetector, COPODDetector])
def test_tail_probability_scores_match_pyod_for_one_row_at_a_time(cls):
    # PyOD ranks a batch of one row among the fit rows plus that row; the detector does the same.
    from pyod.models.copod import COPOD
    from pyod.models.ecod import ECOD

    train = _correlated_train()
    reference = (ECOD if cls is ECODDetector else COPOD)(contamination=0.05)
    detector = cls(contamination=0.05).fit(train)
    x = detector._matrix(train)
    reference.fit(x)
    probe = detector._matrix(
        pd.DataFrame({"a": [0.1, 3.0, -2.0], "b": [0.0, -3.0, 2.5], "c": [0.5, 9.0, 0.1]})
    )
    expected = [reference.decision_function(row[None, :])[0] for row in probe]
    got = detector._fitted_model().decision_function(probe)
    np.testing.assert_allclose(got, expected)


@pytest.mark.parametrize("cls", [ECODDetector, COPODDetector])
def test_tail_probability_scores_do_not_move_with_the_scored_batch(cls):
    train = _correlated_train()
    detector = cls(contamination=0.05).fit(train)
    batch = _correlated_train(40, seed=9) + 1.0
    together = detector.score(batch)
    pd.testing.assert_series_equal(together.iloc[:5], detector.score(batch.iloc[:5]))


def test_ecod_keeps_the_larger_tail_and_copod_their_mean():
    train = pd.DataFrame({"a": -(np.arange(100.0) ** 2)})  # negative skew: the left tail decides
    ecod = ECODDetector(contamination=0.05).fit(train)
    copod = COPODDetector(contamination=0.05).fit(train)
    extreme = pd.DataFrame({"a": [1000.0]})  # beyond the maximum: right tail 1/101, left tail 1
    assert ecod.score(extreme).iloc[0] == pytest.approx(np.log(101))
    assert copod.score(extreme).iloc[0] == pytest.approx(np.log(101) / 2)


def test_a_row_tied_with_fit_rows_counts_them_in_both_tails():
    from etl_benchmark.quality.ml import TailProbabilityModel

    model = TailProbabilityModel(0.25, "ecod").fit(np.array([[1.0], [2.0], [2.0], [3.0]]))
    tail = -np.log(4 / 5)  # three of the four fit rows are on each side of the tied value
    assert model.decision_function(np.array([[2.0]]))[0] == pytest.approx(2 * tail)


def test_a_score_equal_to_the_threshold_is_not_flagged():
    from etl_benchmark.quality.ml import PCAReconstruction, TailProbabilityModel

    x = np.array([[1.0, 0.0], [2.0, 0.1], [3.0, 0.0], [4.0, 0.3], [5.0, 0.0]])
    for model in (TailProbabilityModel(0.0, "ecod"), PCAReconstruction(0.0)):
        flags = model.fit(x).predict(x)  # contamination 0: the threshold is the largest fit score
        assert flags.dtype.kind == "i" and flags.sum() == 0
