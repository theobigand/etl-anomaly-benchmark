"""ETL pipeline: composable stages shared by the demo and the benchmark.

The stages are:
    - ``extract``   — load raw data into a DataFrame;
    - ``transform`` — light cleaning (drop exact duplicates);
    - ``detect``    — the quality stage: fit/predict/score a detector,
      timed, with the ground-truth label excluded from the features.

:func:`run_pipeline` chains all three (and optionally dumps the sorted
clean/anomaly CSVs) for the single-detector demo run with
``python -m etl_benchmark``. The benchmark reuses ``extract``/``transform``
once and calls :func:`detect` per detector, so every method is scored on
the exact same pipeline path and its in-pipeline latency is measured.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from etl_benchmark import config
from etl_benchmark.extract import read_csv
from etl_benchmark.load import write_csv
from etl_benchmark.quality import Detector, ZScoreDetector
from etl_benchmark.transform import clean

log = logging.getLogger(__name__)

# Stage aliases so callers speak the pipeline vocabulary.
extract = read_csv
transform = clean


@dataclass
class DetectionResult:
    """Output of the quality stage for one detector."""

    flags: pd.Series  # boolean per row: True where anomalous
    scores: pd.Series  # continuous anomaly score per row
    fit_s: float
    predict_s: float
    score_s: float

    @property
    def detect_s(self) -> float:
        """In-pipeline detector latency (fit + predict + score)."""
        return self.fit_s + self.predict_s + self.score_s


def detect(
    df: pd.DataFrame,
    detector: Detector,
    label_column: str | None = None,
) -> DetectionResult:
    """Run the quality stage: fit, predict and score ``detector`` on ``df``.

    ``label_column`` (the ground-truth label) is dropped from the features
    so it never leaks into detection.
    """
    features = df.drop(columns=[label_column]) if label_column in df.columns else df

    t0 = time.perf_counter()
    detector.fit(features)
    t1 = time.perf_counter()
    flags = detector.predict(features)
    t2 = time.perf_counter()
    scores = detector.score(features)
    t3 = time.perf_counter()

    return DetectionResult(flags, scores, t1 - t0, t2 - t1, t3 - t2)


def run_pipeline(
    input_path: Path = config.CREDIT_CARD_CSV,
    detector: Detector | None = None,
    label_column: str | None = "Class",
    dump_dir: Path | None = None,
) -> tuple[pd.DataFrame, DetectionResult]:
    """Chain extract -> transform -> detect for a single detector.

    When ``dump_dir`` is given, the sorted rows are written to
    ``pipeline_clean.csv`` and ``pipeline_anomalies.csv`` (the load stage);
    otherwise nothing is persisted.
    """
    detector = detector or ZScoreDetector(threshold=config.ZSCORE_THRESHOLD)

    log.info("extract: loading %s", input_path)
    df = extract(input_path)
    log.info("extract: %d rows x %d cols", len(df), df.shape[1])

    df = transform(df)
    log.info("transform: %d rows after cleaning", len(df))

    log.info("quality: fitting detector %s", detector.name)
    result = detect(df, detector, label_column=label_column)
    n = int(result.flags.sum())
    log.info(
        "quality: %d anomalies flagged (%.2f%%) in %.2fs",
        n,
        100 * n / len(df),
        result.detect_s,
    )

    if dump_dir is not None:
        dump_dir = Path(dump_dir)
        clean_path = write_csv(df[~result.flags], dump_dir / "pipeline_clean.csv")
        anom_path = write_csv(df[result.flags], dump_dir / "pipeline_anomalies.csv")
        log.info("load: clean -> %s", clean_path)
        log.info("load: anomalies -> %s", anom_path)

    return df, result
