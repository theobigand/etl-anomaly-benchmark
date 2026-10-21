"""Deep anomaly detectors wrapped from PyOD (PyTorch, CPU).

These models learn a representation of the standardized features and score a
row by how badly it fits it:

    - :class:`VAEDetector` — variational autoencoder, reconstruction error;
    - :class:`DeepSVDDDetector` — network trained to map normal rows into a
      small hypersphere, distance to its centre;
    - :class:`DIFDetector` — isolation forest on random neural
      representations;
    - :class:`AE1SVMDetector` — autoencoder with a one-class SVM objective on
      the code;
    - :class:`LUNARDetector` — network on the distances to the nearest
      neighbours.

They reuse the preparation and the fit / predict / score contract of
:class:`PyODDetector`, keep the PyOD defaults, and only fix what the
protocol needs: no second standardization, no progress output, CPU, and a
seed. They are opt-in, like the MLP autoencoder: PyTorch is an optional
dependency, imported when a model is fitted.
"""

from __future__ import annotations

import contextlib
import io
from importlib.metadata import version
from typing import ClassVar, Self

import numpy as np
import pandas as pd

from etl_benchmark import config
from etl_benchmark.quality.ml import PyODDetector


def _default_device() -> str:
    """The device PyOD picks when none is passed: CUDA if present, else the CPU."""
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


class TorchDetector(PyODDetector):
    """A PyOD estimator that needs PyTorch and a seed."""

    #: Arguments fixed by the protocol, on top of the PyOD defaults.
    fixed_kwargs: ClassVar[dict[str, object]] = {}
    #: Name of the estimator argument that takes the seed, when it has one.
    seed_argument: ClassVar[str | None] = "random_state"

    def __init__(
        self,
        contamination: float = config.ML_CONTAMINATION,
        columns: list[str] | None = None,
        random_state: int = config.RANDOM_SEED,
        **estimator_kwargs: object,
    ) -> None:
        super().__init__(contamination=contamination, columns=columns, **estimator_kwargs)
        self.random_state = random_state

    def _extra_kwargs(self) -> dict[str, object]:
        """Arguments that depend on the fitted columns."""
        return {}

    def _build_estimator(self):
        module_name, class_name = self.estimator_path
        cls = getattr(__import__(module_name, fromlist=[class_name]), class_name)
        kwargs: dict[str, object] = {
            "contamination": self.contamination,
            **self.fixed_kwargs,
            **self._extra_kwargs(),
            **self._estimator_kwargs,
        }
        if self.seed_argument is not None:
            kwargs.setdefault(self.seed_argument, self.random_state)
        return cls(**kwargs)

    def fit(self, df: pd.DataFrame) -> Self:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                f"{self.name} detector needs torch; install it (see environment.yml)"
            ) from exc
        torch.manual_seed(self.random_state)
        # AE1SVM prints its loss every ten epochs and has no verbosity argument.
        with contextlib.redirect_stdout(io.StringIO()):
            return super().fit(df)

    def score(self, df: pd.DataFrame) -> pd.Series:
        if len(df) == 1:
            # PyOD's AE1SVM fails on a single row; a row's score does not depend on the others.
            return super().score(pd.concat([df, df])).iloc[:1]
        return super().score(df)

    def settings(self) -> dict[str, object]:
        """Hyper-parameters, seed and versions to store with a run."""
        return {
            "contamination": self.contamination,
            "random_state": self.random_state,
            "device": self.fixed_kwargs.get("device") or _default_device(),
            "arguments": {**self.fixed_kwargs, **self._estimator_kwargs},
            "versions": {
                "torch": version("torch"),
                "pyod": version("pyod"),
                "numpy": np.__version__,
            },
        }


class VAEDetector(TorchDetector):
    name = "vae"
    estimator_path = ("etl_benchmark.quality._torch_models", "MeanVAE")
    fixed_kwargs: ClassVar[dict[str, object]] = {
        "preprocessing": False,
        "verbose": 0,
        "device": "cpu",
    }


class DeepSVDDDetector(TorchDetector):
    name = "deep_svdd"
    estimator_path = ("pyod.models.deep_svdd", "DeepSVDD")
    fixed_kwargs: ClassVar[dict[str, object]] = {"preprocessing": False, "verbose": 0}

    def _extra_kwargs(self) -> dict[str, object]:
        return {"n_features": len(self.feature_names_ or [])}


class DIFDetector(TorchDetector):
    name = "dif"
    estimator_path = ("etl_benchmark.quality._torch_models", "FitScalerDIF")
    fixed_kwargs: ClassVar[dict[str, object]] = {"device": "cpu"}


class AE1SVMDetector(TorchDetector):
    name = "ae1svm"
    estimator_path = ("pyod.models.ae1svm", "AE1SVM")
    fixed_kwargs: ClassVar[dict[str, object]] = {"preprocessing": False}
    seed_argument = None


class LUNARDetector(TorchDetector):
    name = "lunar"
    estimator_path = ("pyod.models.lunar", "LUNAR")
    fixed_kwargs: ClassVar[dict[str, object]] = {"verbose": 0}
