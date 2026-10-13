"""Check the isolation guarantees used by scientific protocol tests."""

import socket

import pandas as pd
import pytest

from etl_benchmark.pipeline import detect


def test_small_frames_are_independent_and_cover_edge_populations(small_frame):
    first = small_frame(positives=0, missing=True, duplicated=True)
    second = small_frame(positives=8, missing=True, duplicated=True)
    first.loc[100, "x"] = 999.0
    assert second.loc[100, "x"] == 0.0
    assert first.label.sum() == 0
    assert second.label.sum() == len(second)
    assert pd.isna(second.loc[102, "x"])
    assert second.loc[107, ["x", "y"]].tolist() == second.loc[100, ["x", "y"]].tolist()


def test_tracking_detector_sees_only_train_features(small_frame, tracking_detector):
    train = small_frame()[["x", "y"]]
    held_out = small_frame()[["x", "y"]].copy()
    held_out.index += 1000
    held_out["x"] += 1000
    result = detect(held_out, tracking_detector, fit_df=train)
    pd.testing.assert_frame_equal(tracking_detector.fit_input, train)
    pd.testing.assert_frame_equal(tracking_detector.predict_input, held_out)
    pd.testing.assert_frame_equal(tracking_detector.score_input, held_out)
    assert result.flags.index.equals(held_out.index)
    assert "label" not in tracking_detector.fit_input


def test_network_is_rejected_before_dns_or_connection():
    with pytest.raises(RuntimeError, match="network access is disabled"):
        socket.create_connection(("example.invalid", 443))
    with (
        socket.socket() as connection,
        pytest.raises(RuntimeError, match="network access is disabled"),
    ):
        connection.connect(("127.0.0.1", 1))
