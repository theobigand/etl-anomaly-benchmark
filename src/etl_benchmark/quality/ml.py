"""Classical machine-learning anomaly detectors, wrapped from PyOD.

Where the rule-based detectors in :mod:`etl_benchmark.quality.rules` and
:mod:`etl_benchmark.quality.gx` define a per-column band of normal values,
these detectors learn a joint model of the feature space and score a row
by how poorly it fits that model. Three unsupervised estimators are
exposed, all wrapped from PyOD so the reference implementation is reused
rather than reimplemented:

    - :class:`IsolationForestDetector` — random-partition isolation depth;
    - :class:`LOFDetector` — local outlier factor (density relative to
      neighbours);
    - :class:`OneClassSVMDetector` — an SVM boundary around the bulk of
      the data.

All three share the same preparation: non-numeric columns are dropped,
missing values are median-imputed, and every feature is standardized
(LOF and One-Class SVM are distance-based and scale-sensitive). The
PyOD ``decision_function`` is used as the continuous anomaly score and
``predict`` as the boolean flag; the flag threshold is set by
``contamination``, the expected share of anomalies.

Tested against pyod 3.x.
"""

from __future__ import annotations

from typing import ClassVar, Self

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from etl_benchmark import config
from etl_benchmark.quality.base import Detector


class PyODDetector(Detector):
    """Adapt a PyOD ``BaseDetector`` to the project detector interface."""

    #: Import path of the wrapped PyOD estimator, ``("module", "class")``.
    estimator_path: ClassVar[tuple[str, str]]
    #: Whether the wrapped estimator accepts a ``random_state`` argument.
    supports_random_state: ClassVar[bool] = False

    def __init__(
        self,
        contamination: float = config.ML_CONTAMINATION,
        columns: list[str] | None = None,
        **estimator_kwargs: object,
    ) -> None:
        self.contamination = contamination
        self._user_columns = columns
        self._estimator_kwargs = estimator_kwargs
        self.feature_names_: list[str] | None = None
        self._imputer: SimpleImputer | None = None
        self._scaler: StandardScaler | None = None
        self._model: object | None = None

    def _build_estimator(self):
        module_name, class_name = self.estimator_path
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        kwargs: dict[str, object] = {
            "contamination": self.contamination,
            **self._estimator_kwargs,
        }
        if self.supports_random_state:
            kwargs.setdefault("random_state", config.RANDOM_SEED)
        return cls(**kwargs)

    def _numeric_columns(self, df: pd.DataFrame) -> list[str]:
        cols = self._user_columns or df.select_dtypes(include=np.number).columns.tolist()
        if not cols:
            raise ValueError(
                f"{self.name} detector needs at least one numeric column; got {list(df.columns)}"
            )
        return cols

    def _matrix(self, df: pd.DataFrame) -> np.ndarray:
        if self._model is None or self._imputer is None or self._scaler is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        x = df[self.feature_names_].to_numpy(dtype=float)
        return self._scaler.transform(self._imputer.transform(x))

    def _fitted_model(self):
        if self._model is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        return self._model

    def fit(self, df: pd.DataFrame) -> Self:
        self.feature_names_ = self._numeric_columns(df)
        x = df[self.feature_names_].to_numpy(dtype=float)

        self._imputer = SimpleImputer(strategy="median").fit(x)
        self._scaler = StandardScaler().fit(self._imputer.transform(x))

        self._model = self._build_estimator()
        self._model.fit(self._scaler.transform(self._imputer.transform(x)))
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        flags = self._fitted_model().predict(self._matrix(df)).astype(bool)
        return pd.Series(flags, index=df.index)

    def score(self, df: pd.DataFrame) -> pd.Series:
        scores = self._fitted_model().decision_function(self._matrix(df))
        return pd.Series(scores, index=df.index, dtype=float)


class IsolationForestDetector(PyODDetector):
    name = "isolation_forest"
    estimator_path = ("pyod.models.iforest", "IForest")
    supports_random_state = True


class LOFDetector(PyODDetector):
    name = "lof"
    estimator_path = ("pyod.models.lof", "LOF")


class OneClassSVMDetector(PyODDetector):
    name = "ocsvm"
    estimator_path = ("pyod.models.ocsvm", "OCSVM")
