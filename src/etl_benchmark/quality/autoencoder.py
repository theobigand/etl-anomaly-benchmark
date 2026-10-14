"""Reconstruction-error detector: a small autoencoder trained on the fit rows.

A multilayer perceptron is trained to reproduce the standardized features
through a bottleneck. A row that breaks the structure learned on the fit
data is reproduced badly, so its mean squared reconstruction error is the
anomaly score. The flag threshold is the ``1 - contamination`` quantile of
the training scores, which keeps every statistic tied to the fit rows.

The network is scikit-learn's ``MLPRegressor`` on CPU: it needs no
additional dependency and is deterministic for a given seed. It reuses the
imputation, scaling and input checks of :class:`PyODDetector`, so it follows
the same fit / predict / score contract as the other learned detectors. It is
registered as an opt-in detector and is not part of the default sweep.
"""

from __future__ import annotations

import warnings
from importlib.metadata import version
from typing import Self

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

from etl_benchmark import config
from etl_benchmark.quality.ml import PyODDetector


class ReconstructionModel:
    """PyOD-style estimator (``fit``, ``decision_function``, ``predict``)."""

    def __init__(self, contamination: float, random_state: int, max_iter: int) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self.max_iter = max_iter
        self.threshold_: float | None = None
        self.network_: MLPRegressor | None = None

    @staticmethod
    def layers(width: int) -> list[int]:
        return [max(width, 2), max(width // 2, 1), max(width, 2)]

    def fit(self, x: np.ndarray) -> Self:
        network = MLPRegressor(
            hidden_layer_sizes=tuple(self.layers(x.shape[1])),
            max_iter=self.max_iter,
            random_state=self.random_state,
        )
        with warnings.catch_warnings():
            # A fixed training budget is part of the protocol; whether it ran
            # out is reported through ``settings()`` instead of a warning.
            warnings.simplefilter("ignore", ConvergenceWarning)
            network.fit(x, x.ravel() if x.shape[1] == 1 else x)
        self.network_ = network
        self.threshold_ = float(np.quantile(self.decision_function(x), 1.0 - self.contamination))
        return self

    def decision_function(self, x: np.ndarray) -> np.ndarray:
        reconstruction = self.network_.predict(x).reshape(x.shape)
        return np.mean((x - reconstruction) ** 2, axis=1)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.decision_function(x) > self.threshold_).astype(int)


class AutoencoderDetector(PyODDetector):
    name = "autoencoder"

    def __init__(
        self,
        contamination: float = config.ML_CONTAMINATION,
        columns: list[str] | None = None,
        max_iter: int = 300,
        random_state: int = config.RANDOM_SEED,
    ) -> None:
        super().__init__(contamination=contamination, columns=columns)
        self.max_iter = max_iter
        self.random_state = random_state

    def _build_estimator(self) -> ReconstructionModel:
        return ReconstructionModel(self.contamination, self.random_state, self.max_iter)

    def settings(self) -> dict[str, object]:
        """Hyper-parameters, seed, budget and versions to store with a run."""
        network = self._fitted_model().network_
        return {
            "contamination": self.contamination,
            "hidden_layer_sizes": list(network.hidden_layer_sizes),
            "max_iter": self.max_iter,
            "n_iter": int(network.n_iter_),
            "converged": bool(network.n_iter_ < self.max_iter),
            "random_state": self.random_state,
            "device": "cpu",
            "versions": {
                "scikit-learn": version("scikit-learn"),
                "numpy": version("numpy"),
            },
        }
