"""Central registry of detectors with their default hyperparameters.

Both the pipeline demo (``python -m etl_benchmark --detector <name>``) and
the benchmarks build detectors from here, so adding a new detector (e.g. a
PyOD wrapper) is a single entry that every entry point picks up.

The ML detectors take a ``contamination`` (the expected anomaly share used
for the flag threshold). The benchmarks pass the train-set prevalence;
:func:`get_detector` / :func:`all_detectors` fall back to
``config.ML_CONTAMINATION`` when none is given.
"""

from __future__ import annotations

from collections.abc import Callable

from etl_benchmark import config
from etl_benchmark.quality import (
    Detector,
    GreatExpectationsDetector,
    IQRDetector,
    IsolationForestDetector,
    LOFDetector,
    OneClassSVMDetector,
    ZScoreDetector,
)

# Each factory takes the ML contamination to use (rule-based detectors ignore it).
_FACTORIES: dict[str, Callable[[float], Detector]] = {
    "zscore": lambda c: ZScoreDetector(threshold=config.ZSCORE_THRESHOLD),
    "iqr": lambda c: IQRDetector(multiplier=config.IQR_MULTIPLIER),
    "great_expectations": lambda c: GreatExpectationsDetector(),
    "isolation_forest": lambda c: IsolationForestDetector(contamination=c),
    "lof": lambda c: LOFDetector(contamination=c),
    "ocsvm": lambda c: OneClassSVMDetector(contamination=c),
}

DETECTOR_NAMES: list[str] = list(_FACTORIES)
RULE_NAMES: list[str] = ["zscore", "iqr", "great_expectations"]
ML_NAMES: list[str] = ["isolation_forest", "lof", "ocsvm"]


def clip_contamination(prevalence: float | None) -> float:
    """Clamp a prevalence into the range PyOD accepts for ``contamination``."""
    if prevalence is None:
        prevalence = config.ML_CONTAMINATION
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    return float(min(max(prevalence, lo), hi))


def get_detector(name: str, ml_contamination: float | None = None) -> Detector:
    """Build a fresh detector by name.

    ``ml_contamination`` sets the flag threshold of the ML detectors; it is
    ignored by the rule-based ones.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(f"unknown detector {name!r}; choose from {DETECTOR_NAMES}") from None
    return factory(clip_contamination(ml_contamination))


def all_detectors(
    ml_contamination: float | None = None,
    names: list[str] | None = None,
) -> list[Detector]:
    """Build one fresh instance of every registered detector (or ``names``)."""
    wanted = names or DETECTOR_NAMES
    return [get_detector(name, ml_contamination) for name in wanted]
