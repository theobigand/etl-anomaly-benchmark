"""Central registry of detectors with their default hyperparameters.

Both the pipeline demo (``python -m etl_benchmark --detector <name>``) and
the benchmark build detectors from here, so adding a new detector (e.g. a
PyOD wrapper) is a single entry that both entry points pick up.
"""

from __future__ import annotations

from collections.abc import Callable

from etl_benchmark import config
from etl_benchmark.quality import (
    Detector,
    GreatExpectationsDetector,
    IQRDetector,
    ZScoreDetector,
)

_FACTORIES: dict[str, Callable[[], Detector]] = {
    "zscore": lambda: ZScoreDetector(threshold=config.ZSCORE_THRESHOLD),
    "iqr": lambda: IQRDetector(multiplier=config.IQR_MULTIPLIER),
    "great_expectations": lambda: GreatExpectationsDetector(),
}

DETECTOR_NAMES: list[str] = list(_FACTORIES)


def get_detector(name: str) -> Detector:
    """Build a fresh detector by name, with its default hyperparameters."""
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise ValueError(
            f"unknown detector {name!r}; choose from {DETECTOR_NAMES}"
        ) from None


def all_detectors() -> list[Detector]:
    """Build one fresh instance of every registered detector."""
    return [factory() for factory in _FACTORIES.values()]
