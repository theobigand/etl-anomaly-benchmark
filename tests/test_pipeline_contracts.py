import itertools
import logging
import re

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import config, pipeline
from etl_benchmark.load import write_csv
from etl_benchmark.pipeline import detect, run_pipeline
from etl_benchmark.quality import ZScoreDetector

pytestmark = pytest.mark.integration


def _message(text):
    return f"^{re.escape(text)}$"


class _Detector:
    """Detector whose outputs are chosen by the test; the checks are the pipeline's own."""

    name = "scripted"

    def __init__(self, flags=None, scores=None):
        self._flags = flags
        self._scores = scores

    def fit(self, frame):
        return self

    def predict(self, frame):
        return pd.Series(False, index=frame.index) if self._flags is None else self._flags

    def score(self, frame):
        return pd.Series(0.0, index=frame.index) if self._scores is None else self._scores


def _frame(n=3):
    return pd.DataFrame({"x": np.arange(float(n))}, index=range(10, 10 + n))


def test_detect_names_the_failed_output_contract():
    frame = _frame()
    wrong_index = pd.Series([False] * 3, index=[0, 1, 2])
    with pytest.raises(
        ValueError, match=_message("detector flags must be a Series with the input index")
    ):
        detect(frame, _Detector(flags=wrong_index))
    with pytest.raises(
        ValueError, match=_message("detector flags must be a Series with the input index")
    ):
        detect(frame, _Detector(flags=[False, False, False]))
    with pytest.raises(
        ValueError, match=_message("detector scores must be a Series with the input index")
    ):
        detect(frame, _Detector(scores=pd.Series([0.0] * 3, index=[0, 1, 2])))
    with pytest.raises(
        ValueError, match=_message("detector scores must be a Series with the input index")
    ):
        detect(frame, _Detector(scores=[0.0, 0.0, 0.0]))
    with pytest.raises(ValueError, match=_message("detector flags must be boolean")):
        detect(frame, _Detector(flags=pd.Series([0, 1, 0], index=frame.index)))
    with pytest.raises(ValueError, match=_message("detector scores must be finite")):
        detect(frame, _Detector(scores=pd.Series([0.0, np.nan, 1.0], index=frame.index)))
    with pytest.raises(
        ValueError, match=_message("fit and evaluation feature schema must match in order")
    ):
        detect(frame, _Detector(), fit_df=frame.assign(y=1.0))


def test_detect_keeps_the_graded_scores_of_the_detector():
    frame = _frame()
    flags = pd.Series([False, False, True], index=frame.index)
    scores = pd.Series([0.1, 0.5, 0.9], index=frame.index)
    result = detect(frame, _Detector(flags=flags, scores=scores))
    assert result.scores.tolist() == [0.1, 0.5, 0.9]
    assert result.flags.tolist() == [False, False, True]


def test_detect_rejects_non_numeric_scores():
    frame = _frame()
    with pytest.raises(ValueError):
        detect(frame, _Detector(scores=pd.Series(["a", "b", "c"], index=frame.index)))


def test_detect_times_each_stage_separately(monkeypatch):
    ticks = itertools.chain([1.0, 2.0, 4.0, 7.0])
    monkeypatch.setattr(pipeline.time, "perf_counter", lambda: next(ticks))
    result = detect(_frame(), _Detector())
    assert (result.fit_s, result.predict_s, result.score_s) == (1.0, 2.0, 3.0)
    assert result.detect_s == 6.0


def test_pipeline_logs_each_stage_with_its_counts(tmp_path, caplog, monkeypatch):
    ticks = itertools.count(0, 2)
    monkeypatch.setattr(pipeline.time, "perf_counter", lambda: next(ticks))
    source = tmp_path / "input.csv"
    rows = [float(i) for i in range(20)] + [100.0, 0.0]
    pd.DataFrame({"x": rows, "Class": [0] * 20 + [1, 0]}).to_csv(source, index=False)
    with caplog.at_level(logging.INFO, logger="etl_benchmark.pipeline"):
        run_pipeline(source, ZScoreDetector(threshold=3), dump_dir=tmp_path / "out")
    assert [record.getMessage() for record in caplog.records] == [
        f"extract: loading {source}",
        "extract: 22 rows x 2 cols",
        "transform: 21 rows after cleaning",
        "quality: fitting detector zscore",
        "quality: 1 anomalies flagged (4.76%) in 6.00s",
        f"load: clean -> {tmp_path / 'out' / 'pipeline_clean.csv'}",
        f"load: anomalies -> {tmp_path / 'out' / 'pipeline_anomalies.csv'}",
    ]
    assert sorted(path.name for path in (tmp_path / "out").iterdir()) == [
        "pipeline_anomalies.csv",
        "pipeline_clean.csv",
    ]


def test_pipeline_defaults_drop_the_class_label_and_use_the_configured_zscore(
    tmp_path, tracking_detector, monkeypatch
):
    source = tmp_path / "input.csv"
    pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0], "Class": [0, 0, 0, 1]}).to_csv(source, index=False)
    run_pipeline(source, tracking_detector)
    assert tracking_detector.fit_input.columns.tolist() == ["x"]

    created = {}
    original = pipeline.ZScoreDetector

    def spy(threshold):
        created["threshold"] = threshold
        return original(threshold=threshold)

    monkeypatch.setattr(pipeline, "ZScoreDetector", spy)
    _, result = run_pipeline(source)
    assert created == {"threshold": config.ZSCORE_THRESHOLD}
    assert result.flags.index.equals(pd.RangeIndex(4))


def test_write_csv_creates_missing_parents_and_omits_the_index(tmp_path):
    frame = pd.DataFrame({"x": [1.0, 2.0]}, index=[7, 8])
    path = write_csv(frame, tmp_path / "a" / "b" / "out.csv")
    assert path.read_text() == "x\n1.0\n2.0\n"
