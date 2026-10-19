"""CPU LSTM autoencoder over causal windows of a time-ordered stream (issue 52).

Protocol: verification/lstm_pilot.md. Statistics (median, scale) and the flag threshold come
from the training rows only; windows are built one partition at a time with
``quality.windows.causal_windows``; the score of an event is the reconstruction error of the
last row of the window that closes on it. Validation rows serve early stopping only, through an
unlabelled reconstruction loss. Lives outside the detector registry and the scientific
fingerprint; it needs PyTorch (research/requirements-lstm.txt).
"""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, Self

import numpy as np
import pandas as pd
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etl_benchmark.quality.windows import causal_windows, scores_to_events  # noqa: E402


class _Network(nn.Module):
    def __init__(self, features: int, hidden: int) -> None:
        super().__init__()
        self.encoder = nn.LSTM(features, hidden, batch_first=True)
        self.decoder = nn.LSTM(hidden, hidden, batch_first=True)
        self.output = nn.Linear(hidden, features)

    def forward(self, windows: torch.Tensor) -> torch.Tensor:
        _, (state, _) = self.encoder(windows)
        repeated = state[-1].unsqueeze(1).repeat(1, windows.shape[1], 1)
        decoded, _ = self.decoder(repeated)
        return self.output(decoded)


class LSTMAutoencoder:
    def __init__(
        self,
        columns: list[str],
        time_column: str,
        *,
        window: int = 10,
        hidden: int = 32,
        max_epochs: int = 20,
        patience: int = 3,
        batch_size: int = 256,
        learning_rate: float = 1e-3,
        fit_rows: int = 50_000,
        validation_rows: int = 20_000,
        seed: int = 42,
        threads: int = 1,
    ) -> None:
        if window < 1 or hidden < 1 or max_epochs < 1 or patience < 1:
            raise ValueError("window, hidden, max_epochs and patience must be positive")
        self.columns = list(columns)
        self.time_column = time_column
        self.window, self.hidden = window, hidden
        self.max_epochs, self.patience = max_epochs, patience
        self.batch_size, self.learning_rate = batch_size, learning_rate
        self.fit_rows, self.validation_rows = fit_rows, validation_rows
        self.seed, self.threads = seed, threads
        self.center_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.threshold_: float | None = None
        self._net: _Network | None = None
        self._history: dict[str, Any] = {}
        self._validation: torch.Tensor | None = None

    # -- data ---------------------------------------------------------------------------
    def _windows(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        values = frame[self.columns].astype(float).to_numpy()
        values = np.where(np.isnan(values), self.center_, values)
        scaled = pd.DataFrame((values - self.center_) / self.scale_, columns=self.columns)
        scaled[self.time_column] = frame[self.time_column].to_numpy()
        return causal_windows(scaled, self.time_column, self.columns, self.window)

    def _reconstruction_error(self, windows: np.ndarray, last_only: bool) -> np.ndarray:
        assert self._net is not None
        self._net.eval()
        out = []
        with torch.no_grad():
            for start in range(0, len(windows), 2048):
                batch = torch.as_tensor(windows[start : start + 2048], dtype=torch.float32)
                error = (self._net(batch) - batch) ** 2
                out.append(
                    (error[:, -1] if last_only else error).mean(dim=-1 if last_only else (1, 2))
                )
        return torch.cat(out).numpy().astype(float)

    # -- fitting ------------------------------------------------------------------------
    def fit(self, train: pd.DataFrame, validation: pd.DataFrame, contamination: float) -> Self:
        if not 0.0 < contamination < 0.5:
            raise ValueError("contamination must be in (0, 0.5)")
        if len(train) < self.window or len(validation) < self.window:
            raise ValueError("the training and validation rows must fill at least one window")
        values = train[self.columns].astype(float)
        self.center_ = values.median().to_numpy()
        spread = values.std(ddof=0).to_numpy()
        self.scale_ = np.where(spread > 0, spread, 1.0)
        torch.manual_seed(self.seed)
        torch.set_num_threads(self.threads)
        torch.use_deterministic_algorithms(True)
        rng = np.random.default_rng(self.seed)
        fit_windows, _ = self._windows(train)
        if len(fit_windows) > self.fit_rows:
            fit_windows = fit_windows[rng.choice(len(fit_windows), self.fit_rows, replace=False)]
        val_windows, _ = self._windows(validation)
        if len(val_windows) > self.validation_rows:
            keep = np.sort(rng.choice(len(val_windows), self.validation_rows, replace=False))
            val_windows = val_windows[keep]
        self._validation = torch.as_tensor(val_windows, dtype=torch.float32)
        self._net = _Network(len(self.columns), self.hidden)
        optimiser = torch.optim.Adam(self._net.parameters(), lr=self.learning_rate)
        data = torch.as_tensor(fit_windows, dtype=torch.float32)
        shuffler = torch.Generator().manual_seed(self.seed)
        train_loss: list[float] = []
        validation_loss: list[float] = []
        best, best_state, stale = np.inf, None, 0
        for _epoch in range(self.max_epochs):
            self._net.train()
            order = torch.randperm(len(data), generator=shuffler)
            total = 0.0
            for start in range(0, len(data), self.batch_size):
                batch = data[order[start : start + self.batch_size]]
                optimiser.zero_grad()
                loss = nn.functional.mse_loss(self._net(batch), batch)
                loss.backward()
                optimiser.step()
                total += float(loss.detach()) * len(batch)
            train_loss.append(total / len(data))
            validation_loss.append(self.validation_loss_now())
            if validation_loss[-1] < best:
                best, stale = validation_loss[-1], 0
                best_state = {k: v.clone() for k, v in self._net.state_dict().items()}
            else:
                stale += 1
                if stale >= self.patience:
                    break
        assert best_state is not None
        self._net.load_state_dict(best_state)
        scores = self._reconstruction_error(fit_windows, last_only=True)
        self.threshold_ = float(np.quantile(scores, 1.0 - contamination))
        self._history = {
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "epochs_run": len(train_loss),
            "best_epoch": int(np.argmin(validation_loss)) + 1,
        }
        return self

    def validation_loss_now(self) -> float:
        if self._net is None or self._validation is None:
            raise RuntimeError("the model is not fitted")
        self._net.eval()
        with torch.no_grad():
            return float(nn.functional.mse_loss(self._net(self._validation), self._validation))

    # -- scoring ------------------------------------------------------------------------
    def score(self, frame: pd.DataFrame) -> pd.Series:
        if self._net is None or self.center_ is None:
            raise RuntimeError("the model is not fitted")
        windows, order = self._windows(frame)
        return scores_to_events(self._reconstruction_error(windows, True), order, frame.index)

    def flags(self, frame: pd.DataFrame) -> pd.Series:
        return self.score(frame) > self.threshold_

    def settings(self) -> dict[str, Any]:
        if self._net is None:
            raise RuntimeError("the model is not fitted")
        return {
            **self._history,
            "converged": self._history["epochs_run"] < self.max_epochs,
            "window": self.window,
            "hidden": self.hidden,
            "max_epochs": self.max_epochs,
            "patience": self.patience,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "fit_rows": self.fit_rows,
            "seed": self.seed,
            "threads": self.threads,
            "device": "cpu",
            "deterministic_algorithms": True,
            "versions": {"torch": version("torch"), "numpy": version("numpy")},
        }
