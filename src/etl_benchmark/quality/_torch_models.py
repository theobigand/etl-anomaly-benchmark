"""PyOD neural estimators with scoring that depends on the fit rows only.

Imported when a deep detector is fitted, because it needs PyTorch. Two PyOD
models score a row with information from the rows scored with it, which breaks
the contract that a fitted detector maps a row to a score:

    - ``VAE`` draws a random latent code when it scores;
    - ``DIF`` standardizes the learned representation of the scored rows with
      their own mean and variance;
    - ``AE1SVM`` fails when the last batch of a pass holds a single row: batch normalization
      cannot train on one row, and the scoring code cannot assign one score.

The subclasses below change only that step.
"""

from __future__ import annotations

import numpy as np
import torch
from pyod.models.ae1svm import AE1SVM
from pyod.models.dif import DIF
from pyod.models.vae import VAE
from pyod.utils.stat_models import pairwise_distances_no_broadcast
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader


class MeanVAE(VAE):
    """VAE scored with the mean of the latent code instead of a random draw."""

    def evaluating_forward(self, batch_data):
        mu, _ = self.model.encode(batch_data.to(self.device))
        reconstruction = self.model.decode(mu).cpu().numpy()
        return pairwise_distances_no_broadcast(batch_data.numpy(), reconstruction)


class FitScalerDIF(DIF):
    """DIF whose representations are standardized with the fit rows' statistics."""

    def _deep_representation(self, net, X):
        reduced = []
        with torch.no_grad():
            for batch in DataLoader(X, batch_size=self.batch_size, drop_last=False, shuffle=False):
                reduced.append(net(batch.float().to(self.device)))
        reduced = torch.cat(reduced).cpu().numpy()
        scalers = self.__dict__.setdefault("_representation_scalers", {})
        # PyOD builds every network's representation of the fit rows first, in fit().
        if id(net) not in scalers:
            scalers[id(net)] = StandardScaler().fit(reduced)
        return np.tanh(scalers[id(net)].transform(reduced))


class PaddedAE1SVM(AE1SVM):
    """AE1SVM that adds a row to a pass whose last batch would hold a single one."""

    def fit(self, X, y=None):
        X = np.asarray(X)
        if len(X) % self.batch_size == 1:
            # the last fit row is repeated once, so no training batch holds a single row
            X = np.vstack([X, X[-1:]])
        return super().fit(X, y)

    def decision_function(self, X):
        X = np.asarray(X)
        if len(X) % self.batch_size == 1:
            # a row's score does not depend on the others, so the added row is dropped again
            return super().decision_function(np.vstack([X, X[-1:]]))[:-1]
        return super().decision_function(X)
