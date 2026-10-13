"""Small independent data and detector fixtures for protocol tests."""

from __future__ import annotations

import socket

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def forbid_network_connections(monkeypatch):
    """Keep in-process tests offline, including accidental library calls."""

    def denied(*_args, **_kwargs):
        raise RuntimeError("network access is disabled during pytest")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def small_frame():
    """Return a fresh frame per call so consumers cannot share mutations."""

    def make(*, positives: int = 2, missing: bool = False, duplicated: bool = False):
        if not 0 <= positives <= 8:
            raise ValueError("positives must be between 0 and 8")
        frame = pd.DataFrame(
            {
                "row_id": range(8),
                "x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
                "y": [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0],
                "label": [0] * (8 - positives) + [1] * positives,
            },
            index=range(100, 108),
        )
        if missing:
            frame.loc[102, "x"] = float("nan")
        if duplicated:
            frame.loc[107, ["x", "y"]] = frame.loc[100, ["x", "y"]].to_numpy()
        return frame

    return make


@pytest.fixture
def tracking_detector():
    """Record real fit and evaluation inputs without replacing detect logic."""

    class TrackingDetector:
        name = "tracking"

        def __init__(self):
            self.fit_input = None
            self.predict_input = None
            self.score_input = None

        def fit(self, frame):
            self.fit_input = frame.copy(deep=True)
            return self

        def predict(self, frame):
            self.predict_input = frame.copy(deep=True)
            return pd.Series(False, index=frame.index)

        def score(self, frame):
            self.score_input = frame.copy(deep=True)
            return pd.Series(0.0, index=frame.index)

    return TrackingDetector()
