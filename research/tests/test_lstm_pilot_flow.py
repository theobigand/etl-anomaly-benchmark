# ruff: noqa: E501
"""What the LSTM pilot hands to each step: the exact frames, arguments, log lines and written values."""

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lstm_pilot as lp  # noqa: E402


def test_the_default_stream_is_twenty_four_thousand_rows_one_percent_anomalies_from_seed_zero():
    frame = lp.synthetic_sequence_stream()
    assert len(frame) == 24_000 and int(frame[lp.ANOMALY_COLUMN].sum()) == 240
    assert frame[lp.ANOMALY_COLUMN].dtype == np.int64
    explicit = lp.synthetic_sequence_stream(n=24_000, rate=0.01, seed=0)
    pd.testing.assert_frame_equal(frame, explicit)


def test_an_isolated_anomaly_flips_the_sign_of_the_previous_state_when_the_flip_is_not_clipped():
    frame = lp.synthetic_sequence_stream(n=3000, rate=0.004, seed=3)
    cols = [c for c in frame.columns if c.startswith("f")]
    x, hit = frame[cols].to_numpy(), frame[lp.ANOMALY_COLUMN].to_numpy().astype(bool)
    checked = 0
    for t in np.flatnonzero(hit):
        if hit[t - 1] or (t + 1 < len(hit) and hit[t + 1]):
            continue
        small = np.abs(x[t - 1]) * 0.9 < 1.0
        assert np.array_equal(np.sign(x[t])[small], -np.sign(x[t - 1])[small])
        assert np.allclose(x[t][small], -0.9 * x[t - 1][small])
        checked += 1
    assert checked >= 3 and hit[:20].sum() == 0


def _frames():
    n = 60
    times = pd.Series(pd.date_range("2020-01-01", periods=n, freq="s", tz="UTC"))
    frame = pd.DataFrame({"f0": np.arange(n, dtype=float), "f1": np.arange(n, dtype=float) ** 2})
    frame[lp.ANOMALY_COLUMN] = ([0] * 8 + [1] * 2) * 6
    frame[lp.tp.TIME_UTC] = times
    return frame.iloc[:40], frame.iloc[40:50], frame.iloc[50:]


def test_the_row_autoencoder_sample_is_drawn_with_the_seed_and_ordered_by_time(monkeypatch):
    train, val, test = _frames()
    seen = {}
    monkeypatch.setattr(
        lp,
        "_row_autoencoder",
        lambda tx, sx, c: (
            seen.update(sample=tx.copy(), c=c) or (np.zeros(len(sx)), np.zeros(len(sx), bool), {})
        ),
    )

    class Model:
        def __init__(self, columns, time_column, **kwargs):
            seen["kwargs"] = kwargs

        def fit(self, *args):
            return self

        def score(self, frame):
            return pd.Series(np.zeros(len(frame)))

        def flags(self, frame):
            return pd.Series(np.zeros(len(frame), bool))

        def settings(self):
            return {}

    monkeypatch.setattr(lp, "LSTMAutoencoder", Model)
    monkeypatch.setattr(lp, "compute_metrics", lambda y, f, s: {})
    lp.compare(train, val, test, ["f0", "f1"], seed=5, fit_rows=12)
    expected = train.sample(n=12, random_state=5).sort_values(lp.tp.TIME_UTC)[["f0", "f1"]]
    pd.testing.assert_frame_equal(seen["sample"], expected)
    assert seen["c"] == float(train[lp.ANOMALY_COLUMN].mean())
    assert seen["kwargs"]["max_epochs"] == 20 and seen["kwargs"]["seed"] == 5
    assert seen["kwargs"]["fit_rows"] == 12 and seen["kwargs"]["window"] == lp.WINDOW
    assert seen["kwargs"]["hidden"] == lp.HIDDEN


def test_the_fit_time_of_the_lstm_is_the_difference_of_two_readings(monkeypatch):
    train, val, test = _frames()
    monkeypatch.setattr(
        lp, "_row_autoencoder", lambda tx, sx, c: (np.zeros(len(sx)), np.zeros(len(sx), bool), {})
    )
    monkeypatch.setattr(lp, "compute_metrics", lambda y, f, s: {})

    class Model:
        def __init__(self, *a, **k):
            pass

        def fit(self, *a):
            return self

        def score(self, frame):
            return pd.Series(np.zeros(len(frame)))

        def flags(self, frame):
            return pd.Series(np.zeros(len(frame), bool))

        def settings(self):
            return {}

    monkeypatch.setattr(lp, "LSTMAutoencoder", Model)
    readings = iter([100.0, 107.5])
    monkeypatch.setattr(lp.time, "perf_counter", lambda: next(readings))
    assert lp.compare(train, val, test, ["f0"], seed=1)["lstm"]["fit_seconds"] == 7.5


def test_the_synthetic_control_partitions_the_stream_and_hands_the_same_frames_to_the_comparison(
    monkeypatch,
):
    train, val, test = _frames()
    seen = {}
    stream = pd.concat([train, val, test])
    monkeypatch.setattr(lp, "synthetic_sequence_stream", lambda: stream)
    monkeypatch.setattr(
        lp.tp,
        "chronological_partitions",
        lambda frame: seen.update(frame=frame) or (train, val, test),
    )

    def compare(a, b, c, columns, **kwargs):
        seen["compare"] = (a, b, c, columns, kwargs)
        return {"result": 1}

    monkeypatch.setattr(lp, "compare", compare)
    monkeypatch.setattr(
        lp,
        "_summary",
        lambda result, times: (
            seen.update(summary=(result, times)) or {"lstm_minus_autoencoder": {"ci_low": 1.0}}
        ),
    )
    lp.run_synthetic()
    assert seen["frame"] is stream
    a, b, c, columns, kwargs = seen["compare"]
    assert a is train and b is val and c is test and columns == ["f0", "f1"]
    assert kwargs == {"seed": 42, "fit_rows": 40, "max_epochs": 20}
    assert seen["summary"][0] == {"result": 1} and seen["summary"][1].equals(test[lp.tp.TIME_UTC])


def test_credit_card_loads_partitions_and_lists_the_columns_from_the_frames_it_was_given(
    monkeypatch, caplog
):
    train, val, test = _frames()
    spec, loaded = object(), object()
    seen = {"compare": [], "summary": []}
    monkeypatch.setattr(lp.tp, "load", lambda s: loaded if s is spec else None)
    monkeypatch.setattr(
        lp.tp,
        "chronological_partitions",
        lambda frame: (train, val, test) if frame is loaded else None,
    )
    monkeypatch.setattr(
        lp.tp,
        "features",
        lambda s, f: pd.DataFrame({"a": [1]}) if s is spec and f is loaded else None,
    )
    monkeypatch.setattr(lp.tp, "describe", lambda part: {"rows": len(part)})
    monkeypatch.setattr(lp, "compare", lambda *a: seen["compare"].append(a) or {"r": a[-1]})
    monkeypatch.setattr(
        lp, "_summary", lambda result, times: seen["summary"].append(times) or {"seed": result["r"]}
    )
    with caplog.at_level(logging.INFO):
        lp.run_credit_card(spec, None)
    first = seen["compare"][0]
    assert first[0] is train and first[1] is val and first[2] is test and first[3] == ["a"]
    assert all(times.equals(test[lp.tp.TIME_UTC]) for times in seen["summary"])
    assert [r.getMessage() for r in caplog.records] == [f"credit card, seed {s}" for s in lp.SEEDS]


def _main_stubs(monkeypatch, tmp_path, *, gate=True, reference=None):
    import provenance

    dataset = tmp_path / "cc.csv"
    dataset.write_text("a\n1\n")
    monkeypatch.setitem(lp.DATASETS, "credit_card", SimpleNamespace(csv=dataset))
    monkeypatch.setattr(lp, "run_synthetic", lambda: {"passes_gate": gate, "count": np.int64(3)})
    seen = {}
    monkeypatch.setattr(
        lp,
        "run_credit_card",
        lambda spec, ref: seen.update(spec=spec, ref=ref) or {"n": np.int64(7)},
    )
    monkeypatch.setattr(provenance, "write_record", lambda *a, **k: None)
    return seen


def test_numpy_integers_in_the_result_are_written_as_floats(monkeypatch, tmp_path):
    _main_stubs(monkeypatch, tmp_path)
    out = tmp_path / "o.json"
    lp.main(["--output", str(out)])
    result = json.loads(out.read_text())
    assert result["synthetic_control"]["count"] == 3.0 and result["credit_card"]["n"] == 7.0


def test_logging_is_set_up_at_info_with_time_name_and_message(monkeypatch, tmp_path):
    _main_stubs(monkeypatch, tmp_path)
    seen = {}
    monkeypatch.setattr(lp.logging, "basicConfig", lambda **kw: seen.update(kw))
    lp.main(["--output", str(tmp_path / "o.json")])
    assert seen == {"level": logging.INFO, "format": "%(asctime)s %(name)s %(message)s"}


def test_the_gate_and_its_failure_are_logged_in_plain_words(monkeypatch, tmp_path, caplog):
    _main_stubs(monkeypatch, tmp_path, gate=False)
    with caplog.at_level(logging.INFO):
        lp.main(["--output", str(tmp_path / "o.json")])
    messages = [r.getMessage() for r in caplog.records if r.name.endswith("lstm_pilot")]
    assert messages == [
        "synthetic control gate passed: False",
        "the synthetic gate failed: Credit Card is run but must not be interpreted",
    ]


def test_the_archived_reference_is_read_only_when_it_exists(monkeypatch, tmp_path):
    seen = _main_stubs(monkeypatch, tmp_path)
    missing = tmp_path / "none.json"
    monkeypatch.setattr(lp, "ROOT", tmp_path)
    lp.main(["--output", str(tmp_path / "a.json")])
    assert seen["ref"] is None
    reference = tmp_path / "verification" / "evidence" / "temporal_pilot" / "temporal_pilot.json"
    reference.parent.mkdir(parents=True)
    reference.write_text('{"chronological": {"x": {"pr_auc": 1}}}')
    lp.main(["--output", str(tmp_path / "b.json")])
    assert seen["ref"] == {"chronological": {"x": {"pr_auc": 1}}} and not missing.exists()
    assert seen["spec"] is lp.DATASETS["credit_card"]


def test_the_help_describes_the_pilot_and_the_output_default(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        lp.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--synthetic-only" in text and "--output OUTPUT" in text
    assert lp.__doc__.strip().splitlines()[0] in text
