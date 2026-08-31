"""Project-wide paths and default parameters."""

from __future__ import annotations

from pathlib import Path

#   src/etl_benchmark/config.py -> parents[0]=etl_benchmark, parents[1]=src, parents[2]=repo root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = PROJECT_ROOT / "data"
RESULTS_DIR: Path = PROJECT_ROOT / "experiments" / "results"

CREDIT_CARD_CSV: Path = DATA_DIR / "creditcard.csv"
SYNTHETIC_CSV: Path = DATA_DIR / "synthetic.csv"
WATER_QUALITY_CSV: Path = DATA_DIR / "water_quality.csv"

RANDOM_SEED: int = 42
ZSCORE_THRESHOLD: float = 3.0
IQR_MULTIPLIER: float = 1.5

# Evaluation protocol: stratified train / val / test, and the seeds each
# benchmark repeats over (mean and standard deviation are reported).
SPLIT_RATIOS: tuple[float, float, float] = (0.7, 0.15, 0.15)
BENCHMARK_SEEDS: tuple[int, ...] = (42, 1, 2, 3, 4)

# Classical ML detectors (PyOD). ``contamination`` is the expected share of
# anomalies; it only sets the flag threshold, not the continuous score used
# for ROC-AUC / PR-AUC. The benchmarks override it with the train-set
# prevalence; this is the fallback for a bare ``all_detectors()`` call.
ML_CONTAMINATION: float = 0.1
ML_CONTAMINATION_BOUNDS: tuple[float, float] = (1e-4, 0.5)

# Per-anomaly-type synthetic dataset.
SYNTHETIC_ROWS: int = 12_000
SYNTHETIC_ANOMALY_RATE: float = 0.03  # applied per anomaly type
