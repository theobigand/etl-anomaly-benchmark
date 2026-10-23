"""Central registry of detectors with their default hyperparameters.

Both the pipeline demo (``python -m etl_benchmark --detector <name>``) and
the benchmarks build detectors from here, so adding a new detector (e.g. a
PyOD wrapper) is a single entry that every entry point picks up.

The ML detectors take a ``contamination`` (the expected anomaly share used
for the flag threshold). The benchmarks usually pass the train-set prevalence;
:func:`get_detector` / :func:`all_detectors` fall back to
``config.ML_CONTAMINATION`` when none is given.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from math import isfinite

from etl_benchmark import config
from etl_benchmark.quality import (
    AE1SVMDetector,
    AutoencoderDetector,
    COPODDetector,
    DeepSVDDDetector,
    Detector,
    DIFDetector,
    ECODDetector,
    GreatExpectationsDetector,
    HBOSDetector,
    IQRDetector,
    IsolationForestDetector,
    KNNDetector,
    LOFDetector,
    LUNARDetector,
    OneClassSVMDetector,
    PCADetector,
    TemporalDriftDetector,
    VAEDetector,
    ZScoreDetector,
)

# Each factory takes the ML contamination to use (other detectors ignore it).
_FACTORIES: dict[str, Callable[[float], Detector]] = {
    "zscore": lambda c: ZScoreDetector(threshold=config.ZSCORE_THRESHOLD),
    "iqr": lambda c: IQRDetector(multiplier=config.IQR_MULTIPLIER),
    "great_expectations": lambda c: GreatExpectationsDetector(),
    "isolation_forest": lambda c: IsolationForestDetector(contamination=c),
    "lof": lambda c: LOFDetector(contamination=c),
    "ocsvm": lambda c: OneClassSVMDetector(contamination=c),
    "ecod": lambda c: ECODDetector(contamination=c),
    "copod": lambda c: COPODDetector(contamination=c),
    "hbos": lambda c: HBOSDetector(contamination=c),
    "knn": lambda c: KNNDetector(contamination=c),
    "pca": lambda c: PCADetector(contamination=c),
    "drift": lambda c: TemporalDriftDetector(),
    "autoencoder": lambda c: AutoencoderDetector(contamination=c),
    "vae": lambda c: VAEDetector(contamination=c),
    "deep_svdd": lambda c: DeepSVDDDetector(contamination=c),
    "dif": lambda c: DIFDetector(contamination=c),
    "ae1svm": lambda c: AE1SVMDetector(contamination=c),
    "lunar": lambda c: LUNARDetector(contamination=c),
}

RULE_NAMES: list[str] = ["zscore", "iqr", "great_expectations"]
ML_NAMES: list[str] = ["isolation_forest", "lof", "ocsvm", "ecod", "copod", "hbos", "knn", "pca"]
# The core comparison set. ``drift`` needs a timestamp column, so it is opt-in
# (the synthetic benchmark adds it) rather than part of the default sweep.
DETECTOR_NAMES: list[str] = [*RULE_NAMES, *ML_NAMES]
DRIFT_NAME: str = "drift"
ALL_NAMES: list[str] = [*DETECTOR_NAMES, DRIFT_NAME]
# Neural models are opt-in too (they need PyTorch, except the MLP autoencoder):
# their results enter the thesis tables only after the protocol-parity checks in
# verification/deep_models.md and the protocol of verification/full_registry.md.
DEEP_NAMES: list[str] = ["autoencoder", "vae", "deep_svdd", "dif", "ae1svm", "lunar"]


def clip_contamination(prevalence: float | None) -> float:
    """Clamp a prevalence into the range PyOD accepts for ``contamination``."""
    if prevalence is None:
        prevalence = config.ML_CONTAMINATION
    if not isfinite(prevalence) or prevalence < 0 or prevalence > 1:
        raise ValueError("prevalence must be finite and between 0 and 1")
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    return float(min(max(prevalence, lo), hi))


def fixed_contamination(value: float | None) -> float:
    """Validate a contamination chosen before looking at any labels."""
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    if value is None or not isfinite(value) or not lo <= value <= hi:
        raise ValueError(f"fixed contamination must be between {lo} and {hi}")
    return float(value)


def calibrate_contamination(
    train_labels: Iterable[int],
    *,
    policy: str = "train_prevalence",
    fixed: float | None = None,
) -> float:
    """Choose the detector threshold without consulting validation or test labels."""
    if policy == "fixed":
        return fixed_contamination(fixed)
    if policy != "train_prevalence":
        raise ValueError(f"unknown calibration policy {policy!r}")
    labels = list(train_labels)
    if not labels or set(labels) - {0, 1}:
        raise ValueError("training labels must be nonempty and binary")
    return clip_contamination(sum(labels) / len(labels))


def get_detector(name: str, ml_contamination: float | None = None) -> Detector:
    """Build a fresh detector by name.

    ``ml_contamination`` sets the flag threshold of the ML detectors; it is
    ignored by the rule-based ones.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(
            f"unknown detector {name!r}; choose from {[*ALL_NAMES, *DEEP_NAMES]}"
        ) from None
    return factory(clip_contamination(ml_contamination))


def all_detectors(
    ml_contamination: float | None = None,
    names: list[str] | None = None,
) -> list[Detector]:
    """Build one fresh instance of every registered detector (or ``names``)."""
    wanted = names or DETECTOR_NAMES
    return [get_detector(name, ml_contamination) for name in wanted]
