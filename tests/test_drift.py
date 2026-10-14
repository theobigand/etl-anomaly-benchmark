import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.drift import TemporalDriftDetector


def _timeline(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = np.sort(rng.integers(0, 1000, size=n))
    start = pd.Timestamp("2024-01-01")
    dates = [(start + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d") for d in days]
    value = rng.normal(100.0, 8.0, size=n)
    return pd.DataFrame({"ts": dates, "value": value, "other": rng.normal(0, 1, size=n)})


def test_flags_recent_rows_whose_distribution_shifted():
    df = _timeline()
    # a clear, several-sigma upward drift on the most recent 20% of rows
    recent = df.index[int(len(df) * 0.80) :]
    df.loc[recent, "value"] += 24.0
    df.loc[recent, "other"] += 3.0

    det = TemporalDriftDetector(time_column="ts", reference_frac=0.6).fit(df)
    flags = det.predict(df)

    assert flags.loc[recent].mean() > 0.5  # most drift rows caught
    assert flags.loc[df.index[:350]].mean() < 0.05  # old rows untouched


def test_recent_but_normal_rows_are_not_flagged():
    df = _timeline()
    det = TemporalDriftDetector(time_column="ts", reference_frac=0.6).fit(df)

    assert det.predict(df).mean() < 0.05  # no injected drift, almost nothing flagged


def test_no_time_column_is_a_silent_no_op():
    df = _timeline().drop(columns="ts")
    det = TemporalDriftDetector(time_column="ts").fit(df)

    assert not det.predict(df).any()
    assert (det.score(df) == 0.0).all()


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        TemporalDriftDetector().predict(_timeline())


def test_score_is_index_aligned_and_continuous():
    df = _timeline()
    df.index = df.index + 500
    det = TemporalDriftDetector(time_column="ts").fit(df)
    scores = det.score(df)

    assert scores.index.equals(df.index)
    assert scores.min() >= 0.0


def test_drift_score_requires_a_complete_recent_window():
    frame = _timeline(100)
    detector = TemporalDriftDetector(time_column="ts").fit(frame)
    assert detector.score(frame.tail(10)).eq(0.0).all()


def test_constant_reference_does_not_create_spurious_drift():
    frame = _timeline(100)
    frame["value"] = 2.0
    detector = TemporalDriftDetector(time_column="ts", columns=["value"]).fit(frame)
    assert detector.score(frame).eq(0.0).all()
