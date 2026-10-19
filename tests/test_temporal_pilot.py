"""Invariants of the chronological pilot: no future information, honest time, bounded control."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "experiments"))
import temporal_pilot as tp  # noqa: E402

from etl_benchmark.datasets import ANOMALY_COLUMN, DatasetSpec  # noqa: E402


def _csv(tmp_path, n=600, seed=0):
    rng = np.random.default_rng(seed)
    times = np.sort(rng.integers(0, 3000, size=n)).astype(float)  # many ties, as in the data
    frame = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"V{i}" for i in range(1, 7)])
    frame.insert(0, "Time", times)
    frame["Amount"] = rng.gamma(2.0, 20.0, size=n)
    frame["Class"] = 0
    frame.loc[rng.choice(n, size=30, replace=False), "Class"] = 1
    path = tmp_path / "toy.csv"
    frame.to_csv(path, index=False)
    return DatasetSpec("toy", path, "Class", 1, detector_names=["zscore", "iqr"])


def test_relative_seconds_become_utc_timestamps_without_inventing_a_date():
    stamps = tp.to_timestamps(pd.Series([0.0, 1.0, 1.0, 3600.0]))
    assert str(stamps.dt.tz) == "UTC"
    assert stamps.iloc[0] == tp.ORIGIN and stamps.iloc[3] - stamps.iloc[0] == pd.Timedelta("1h")
    assert stamps.iloc[1] == stamps.iloc[2]


@pytest.mark.parametrize("bad", [[-1.0, 2.0], [np.nan, 1.0], ["a", "b"]])
def test_invalid_elapsed_times_are_refused(bad):
    with pytest.raises(ValueError):
        tp.to_timestamps(pd.Series(bad))


def test_the_chronological_arm_never_trains_on_the_future_nor_splits_a_timestamp(tmp_path):
    frame = tp.load(_csv(tmp_path))
    train, val, test = tp.chronological_partitions(frame)
    assert train[tp.TIME_UTC].max() < val[tp.TIME_UTC].min()
    assert val[tp.TIME_UTC].max() < test[tp.TIME_UTC].min()
    assert len(train) + len(val) + len(test) == len(frame)


def test_detector_inputs_exclude_time_and_the_label(tmp_path):
    spec = _csv(tmp_path)
    frame = tp.load(spec)
    columns = set(tp.features(spec, frame).columns)
    assert not columns & {"Time", tp.TIME_UTC, "Class", ANOMALY_COLUMN}
    assert {"V1", "Amount"} <= columns


def test_the_stratified_arm_keeps_the_same_rows_and_features(tmp_path):
    spec = _csv(tmp_path)
    frame = tp.load(spec)
    train, _val, test = tp.stratified_partitions(frame, seed=1)
    assert len(train) + len(test) < len(frame)
    assert list(tp.features(spec, train).columns) == list(tp.features(spec, frame).columns)


def test_scoring_fits_on_the_past_only(tmp_path, monkeypatch):
    spec = _csv(tmp_path)
    frame = tp.load(spec)
    train, _val, test = tp.chronological_partitions(frame)
    seen = []
    original = tp.detect

    def spy(test_x, detector, fit_df):
        seen.append((len(fit_df), len(test_x)))
        return original(test_x, detector, fit_df=fit_df)

    monkeypatch.setattr(tp, "detect", spy)
    scored = tp.score_partition(spec, train, test)
    assert seen and all(fit == len(train) and n == len(test) for fit, n in seen)
    assert set(scored["scores"]) == {"zscore", "iqr"} and len(scored["y"]) == len(test)


def test_blocks_are_whole_intervals_of_time():
    times = pd.Series(pd.to_datetime([0, 10, 20, 700, 710, 1900], unit="s", utc=True))
    blocks = tp.time_blocks(times, 600)
    assert blocks.tolist() == [0, 0, 0, 1, 1, 3]


def test_block_bootstrap_is_deterministic_and_brackets_the_estimate():
    rng = np.random.default_rng(3)
    n = 4000
    times = pd.Series(pd.to_datetime(np.sort(rng.integers(0, 40000, n)), unit="s", utc=True))
    y = (rng.random(n) < 0.05).astype(int)
    score = y * 1.0 + rng.normal(size=n)
    first = tp.block_bootstrap_ci(y, score, times, block_seconds=1800, resamples=200, seed=42)
    again = tp.block_bootstrap_ci(y, score, times, block_seconds=1800, resamples=200, seed=42)
    assert first == again
    low, high = first["ci_low"], first["ci_high"]
    assert low <= first["estimate"] <= high and 0 < low < high < 1


def test_block_bootstrap_rejects_degenerate_inputs():
    times = pd.Series(pd.to_datetime([0, 1, 2], unit="s", utc=True))
    with pytest.raises(ValueError):
        tp.block_bootstrap_ci(np.array([0, 0, 0]), np.array([1.0, 2.0, 3.0]), times, 60, 10, 1)
    with pytest.raises(ValueError):
        tp.block_bootstrap_ci(np.array([0, 1]), np.array([1.0, 2.0, 3.0]), times, 60, 10, 1)


def test_the_shift_touches_only_rows_at_or_after_the_change_and_leaves_the_input_intact():
    times = tp.to_timestamps(pd.Series([0.0, 10.0, 20.0, 30.0]))
    frame = pd.DataFrame({tp.TIME_UTC: times, "V1": [0.0] * 4, "V2": [1.0] * 4, "other": [5.0] * 4})
    before = frame.copy()
    shifted = tp.inject_shift(
        frame, ["V1", "V2"], times.iloc[2], delta=2.0, scale=pd.Series({"V1": 3.0, "V2": 0.5})
    )
    pd.testing.assert_frame_equal(frame, before)
    assert shifted["V1"].tolist() == [0.0, 0.0, 6.0, 6.0]
    assert shifted["V2"].tolist() == [1.0, 1.0, 2.0, 2.0]
    assert shifted["other"].tolist() == [5.0] * 4


def _stream(n=13000, seed=0):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.normal(size=(n, 3)), columns=["V1", "V2", "V3"])
    frame[tp.TIME_UTC] = tp.to_timestamps(pd.Series(np.arange(n, dtype=float)))
    return frame


def test_the_monitor_control_detects_a_large_shift_and_keeps_validation_clean():
    frame = _stream()
    train, val, test = frame.iloc[:5000], frame.iloc[5000:11000], frame.iloc[11000:]
    out = tp.monitor_control(
        train, val, test, ["V1", "V2", "V3"], deltas=(0.0, 3.0), window_size=200
    )
    assert out["threshold"] > 0
    assert out["validation_false_alarms"] == 0
    flat, big = out["controls"]["0.0"], out["controls"]["3.0"]
    # a max-of-validation threshold can be crossed by chance after the change: only the
    # pre-change false-alarm rate is an invariant for the no-shift control
    assert flat["false_alarm_rate"] == 0.0 and isinstance(flat["detected"], bool)
    assert big["detected"] is True and big["false_alarm_rate"] == 0.0
    assert big["delay_windows"] <= 2 and big["delay_seconds"] >= 0


def test_the_monitor_threshold_comes_from_validation_never_from_test():
    frame = _stream()
    train, val, test = frame.iloc[:5000], frame.iloc[5000:11000], frame.iloc[11000:]
    noisy = test.copy()
    noisy[["V1", "V2", "V3"]] += 10.0  # a test period that would raise any test-derived threshold
    a = tp.monitor_control(train, val, test, ["V1", "V2", "V3"], deltas=(0.0,), window_size=200)
    b = tp.monitor_control(train, val, noisy, ["V1", "V2", "V3"], deltas=(0.0,), window_size=200)
    assert a["threshold"] == b["threshold"]


def test_the_archived_pilot_record_identifies_this_implementation():
    import hashlib
    import json
    import subprocess

    import provenance

    archive = ROOT / "verification" / "evidence" / "temporal_pilot"
    record = json.loads((archive / "run_temporal_pilot.json").read_text())
    sha = lambda data: hashlib.sha256(data).hexdigest()  # noqa: E731
    assert record["worktree_dirty"] is False
    assert record["output_sha256"] == {
        "temporal_pilot.json": sha((archive / "temporal_pilot.json").read_bytes())
    }
    manifest = json.loads((ROOT / "verification/evidence/manifest.json").read_text())["datasets"]
    assert record["settings"]["dataset_sha256"] == manifest["credit_card"]["sha256"]
    script = (ROOT / "research" / "temporal_pilot.py").read_bytes()
    assert record["settings"]["script_sha256"] == sha(script)
    committed = subprocess.run(
        ["git", "show", f"{record['source_revision']}:research/temporal_pilot.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    assert sha(committed) == record["settings"]["script_sha256"]
    # research/ is outside the scientific fingerprint: it identifies the detector, split and
    # monitor code the pilot used, and the script itself is identified by script_sha256.
    assert record["scientific_fingerprint"] == provenance.scientific_fingerprint()
