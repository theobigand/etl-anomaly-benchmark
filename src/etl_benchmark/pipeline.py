"""ETL pipeline orchestrator.

Run with::

    python -m etl_benchmark
"""

from __future__ import annotations

import logging
from pathlib import Path

from etl_benchmark import config
from etl_benchmark.extract import read_csv
from etl_benchmark.load import write_csv
from etl_benchmark.quality import Detector, ZScoreDetector
from etl_benchmark.transform import clean

log = logging.getLogger(__name__)


def run(
    input_path: Path = config.CREDIT_CARD_CSV,
    output_dir: Path = config.RESULTS_DIR,
    detector: Detector | None = None,
) -> None:
    detector = detector or ZScoreDetector(threshold=config.ZSCORE_THRESHOLD)

    log.info("extract: loading %s", input_path)
    df = read_csv(input_path)
    log.info("extract: %d rows x %d cols", len(df), df.shape[1])

    log.info("transform: cleaning")
    df = clean(df)
    log.info("transform: %d rows after cleaning", len(df))

    log.info("quality: fitting detector %s", detector.name)
    flags = detector.fit_predict(df)
    n = int(flags.sum())
    log.info("quality: %d anomalies flagged (%.2f%%)", n, 100 * n / len(df))

    clean_path = write_csv(df[~flags], output_dir / "pipeline_clean.csv")
    anom_path = write_csv(df[flags], output_dir / "pipeline_anomalies.csv")
    log.info("load: clean -> %s", clean_path)
    log.info("load: anomalies -> %s", anom_path)
