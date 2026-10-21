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
      the data;
    - :class:`ECODDetector` and :class:`COPODDetector` — empirical tail
      probabilities of each column, combined across columns (computed on the
      fit rows only, see :class:`TailProbabilityModel`);
    - :class:`HBOSDetector` — histogram of each column, scored by inverse
      density;
    - :class:`KNNDetector` — distance to the k-th nearest neighbour;
    - :class:`PCADetector` — reconstruction error after a linear projection
      that keeps 95% of the variance.

ECOD, COPOD and HBOS model each column separately, so they see no
dependency between columns; KNN and PCA look at the joint distribution. All
of them share the same preparation: non-numeric columns are dropped,
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
from scipy.stats import skew
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from etl_benchmark import config
from etl_benchmark.quality.base import Detector, numeric_features


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
        x = numeric_features(df, self.feature_names_, training=False).to_numpy(dtype=float)
        return self._scaler.transform(self._imputer.transform(x))

    def _fitted_model(self):
        if self._model is None:
            raise RuntimeError(f"{self.name} detector not fitted. Call fit() first.")
        return self._model

    def fit(self, df: pd.DataFrame) -> Self:
        self.feature_names_ = self._numeric_columns(df)
        x = numeric_features(df, self.feature_names_, training=True).to_numpy(dtype=float)

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


class TailProbabilityModel:
    """PyOD-style estimator for ECOD and COPOD that reads only the fit rows.

    Both methods turn each column into left and right empirical tail
    probabilities and sum their negative logarithms across columns. PyOD
    recomputes these distributions on the fit rows plus the rows being scored,
    so a row's score would depend on the other rows of its batch. Here the
    distributions are those of the fit rows alone: a row is ranked among the
    fit rows as if it were added to them, which is what PyOD computes for a
    batch of one row. The skew that picks the heavier tail is also fixed at fit.
    The flag threshold is the ``1 - contamination`` quantile of the training
    scores.
    """

    #: Combination of the two tails: ``"ecod"`` keeps the larger, ``"copod"`` their mean.
    method = "ecod"

    def __init__(self, contamination: float, method: str) -> None:
        self.contamination = contamination
        self.method = method
        self.sorted_: np.ndarray | None = None
        self.skew_sign_: np.ndarray | None = None
        self.threshold_: float | None = None

    def fit(self, x: np.ndarray) -> Self:
        self.sorted_ = np.sort(x, axis=0)
        # a constant column has no skew; it then counts both tails
        self.skew_sign_ = np.sign(np.nan_to_num(skew(x, axis=0)))
        self.threshold_ = float(np.quantile(self.decision_function(x), 1.0 - self.contamination))
        return self

    def decision_function(self, x: np.ndarray) -> np.ndarray:
        n = self.sorted_.shape[0]
        left = np.empty(x.shape)
        right = np.empty(x.shape)
        for j in range(x.shape[1]):
            column = self.sorted_[:, j]
            left[:, j] = np.searchsorted(column, x[:, j], side="right")
            right[:, j] = n - np.searchsorted(column, x[:, j], side="left")
        u_left = -np.log((left + 1) / (n + 1))
        u_right = -np.log((right + 1) / (n + 1))
        u_skew = u_left * -1 * np.sign(self.skew_sign_ - 1) + u_right * np.sign(self.skew_sign_ + 1)
        if self.method == "copod":
            combined = np.maximum(u_skew, (u_left + u_right) / 2)
        else:
            combined = np.maximum(u_skew, np.maximum(u_left, u_right))
        return combined.sum(axis=1)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.decision_function(x) > self.threshold_).astype(int)


class ECODDetector(PyODDetector):
    name = "ecod"

    def _build_estimator(self) -> TailProbabilityModel:
        return TailProbabilityModel(self.contamination, "ecod")


class COPODDetector(PyODDetector):
    name = "copod"

    def _build_estimator(self) -> TailProbabilityModel:
        return TailProbabilityModel(self.contamination, "copod")


class HBOSDetector(PyODDetector):
    name = "hbos"
    estimator_path = ("pyod.models.hbos", "HBOS")


class KNNDetector(PyODDetector):
    name = "knn"
    estimator_path = ("pyod.models.knn", "KNN")


class PCAReconstruction:
    """PyOD-style estimator: mean squared error of a PCA reconstruction.

    PyOD's own ``PCA`` scores a weighted distance to the eigenvectors, which
    is not a reconstruction error, so the projection comes from scikit-learn.
    The flag threshold is the ``1 - contamination`` quantile of the training
    scores.
    """

    #: Share of the variance the kept components must explain.
    variance = 0.95

    def __init__(self, contamination: float) -> None:
        self.contamination = contamination
        self.pca_: PCA | None = None
        self.threshold_: float | None = None

    def fit(self, x: np.ndarray) -> Self:
        self.pca_ = PCA(n_components=self.variance, svd_solver="full").fit(x)
        self.threshold_ = float(np.quantile(self.decision_function(x), 1.0 - self.contamination))
        return self

    def decision_function(self, x: np.ndarray) -> np.ndarray:
        reconstruction = self.pca_.inverse_transform(self.pca_.transform(x))
        return np.mean((x - reconstruction) ** 2, axis=1)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.decision_function(x) > self.threshold_).astype(int)


class PCADetector(PyODDetector):
    name = "pca"

    def _build_estimator(self) -> PCAReconstruction:
        return PCAReconstruction(self.contamination)
