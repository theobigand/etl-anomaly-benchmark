"""Registry of the real datasets the benchmark runs on.

Each :class:`DatasetSpec` says where the CSV is, which column is the label
and which value of it counts as the anomaly, and which detectors to run
(LOF and One-Class SVM only where the row count makes them tractable in
the pipeline).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from etl_benchmark import config
from etl_benchmark.pipeline import extract, transform
from etl_benchmark.registry import DETECTOR_NAMES, RULE_NAMES

ANOMALY_COLUMN = "is_anomaly"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    csv: Path
    label_column: str
    positive_value: int
    detector_names: list[str] = field(default_factory=lambda: list(DETECTOR_NAMES))
    note: str = ""

    def load(self) -> pd.DataFrame:
        """Extract, transform, and add a normalised ``is_anomaly`` column."""
        df = transform(extract(self.csv))
        df[ANOMALY_COLUMN] = (df[self.label_column] == self.positive_value).astype(int)
        return df

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop(columns=[self.label_column, ANOMALY_COLUMN])


DATASETS: dict[str, DatasetSpec] = {
    "credit_card": DatasetSpec(
        name="credit_card",
        csv=config.CREDIT_CARD_CSV,
        label_column="Class",
        positive_value=1,
        detector_names=[*RULE_NAMES, "isolation_forest"],
        note="284k rows, 0.17% fraud. LOF/OC-SVM omitted: they do not scale to this size.",
    ),
    "water_quality": DatasetSpec(
        name="water_quality",
        csv=config.WATER_QUALITY_CSV,
        label_column="Potability",
        positive_value=0,
        detector_names=list(DETECTOR_NAMES),
        note="3.3k rows, 61% not-potable. The target class is common, not rare: "
        "this tests the detectors outside their intended regime, on real missing data.",
    ),
    "cardio": DatasetSpec(
        name="cardio",
        csv=config.CARDIO_CSV,
        label_column="label",
        positive_value=1,
        detector_names=list(DETECTOR_NAMES),
        note="1.8k rows, 21 features, 9.6% anomalies. A genuinely imbalanced "
        "cardiotocography dataset: the regime the detectors are built for.",
    ),
}
