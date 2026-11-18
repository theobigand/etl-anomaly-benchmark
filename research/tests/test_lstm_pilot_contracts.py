"""Argument routing, gate rule, summaries and provenance of the LSTM pilot."""

import hashlib
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

STREAM_DIGEST = "235d58000e97f78d947bcea1a81cf7c6a7b9611f1719d4f6f62e599ac1ac4aaa"


def _digest(frame):
    h = hashlib.sha256()
    h.update(frame[[c for c in frame.columns if c.startswith("f")]].to_numpy().round(9).tobytes())
    h.update(frame[lp.ANOMALY_COLUMN].to_numpy().astype("int64").tobytes())
    h.update(frame["Time"].to_numpy().tobytes())
    return h.hexdigest()


def test_the_synthetic_stream_is_pinned_for_a_fixed_size_rate_and_seed():
    frame = lp.synthetic_sequence_stream(n=400, rate=0.05, seed=4)
    assert _digest(frame) == STREAM_DIGEST
    assert frame.shape == (400, 8) and int(frame[lp.ANOMALY_COLUMN].sum()) == 20
    assert frame[lp.ANOMALY_COLUMN].iloc[:20].sum() == 0
    assert frame["Time"].tolist() == [float(i) for i in range(400)]
    assert frame[lp.tp.TIME_UTC].is_monotonic_increasing
    assert (
        lp.synthetic_sequence_stream(n=400, rate=0.05, seed=5)["f0"].tolist()
        != frame["f0"].tolist()
    )


def test_anomalies_continue_the_previous_state_with_the_flipped_clipped_sign():
    frame = lp.synthetic_sequence_stream(n=400, rate=0.05, seed=4)
    features = frame[[f"f{i}" for i in range(5)]].to_numpy()
    sd = features.std(axis=0)
    hits = np.flatnonzero(frame[lp.ANOMALY_COLUMN].to_numpy() == 1)
    flipped = [t for t in hits if (t - 1) not in set(hits)]
    assert flipped
    for t in flipped:
        expected = np.clip(-features[t - 1] * 0.9, -1.5 * sd, 1.5 * sd)
        assert np.allclose(features[t], expected, atol=1.0)


def test_the_row_autoencoder_is_fitted_on_train_and_returns_float_scores_bool_flags_and_settings(
    monkeypatch,
):
    seen = {}

    class Detector:
        def __init__(self, contamination):
            seen["contamination"] = contamination

        def settings(self):
            return {"s": 1}

    def detect(test_x, detector, fit_df):
        seen.update(test=test_x, fit=fit_df)
        return SimpleNamespace(scores=[1, 2], flags=[1, 0])

    monkeypatch.setattr(lp, "AutoencoderDetector", Detector)
    monkeypatch.setattr(lp, "detect", detect)
    train, test = pd.DataFrame({"a": [1.0]}), pd.DataFrame({"a": [2.0, 3.0]})
    scores, flags, settings = lp._row_autoencoder(train, test, 0.25)
    assert seen["contamination"] == 0.25 and seen["test"] is test and seen["fit"] is train
    assert scores.dtype == np.float64 and flags.dtype == np.bool_ and settings == {"s": 1}


def _frames(n_train=10, n_val=4, n_test=6):
    def part(n, offset):
        frame = pd.DataFrame(
            {"f0": np.arange(n, dtype=float), lp.ANOMALY_COLUMN: [0, 1] * (n // 2)}
        )
        frame[lp.tp.TIME_UTC] = pd.date_range(
            "2020-01-01", periods=n, freq="h", tz="UTC"
        ) + pd.Timedelta(days=offset)
        return frame

    return part(n_train, 0), part(n_val, 1), part(n_test, 2)


def test_the_comparison_fits_both_models_on_the_same_rows_with_the_given_budget(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        lp,
        "_row_autoencoder",
        lambda a, b, c: (
            seen.update(sample=a.copy(), contamination=c)
            or (np.array([0.1] * 6), np.array([True] * 6), {"ae": 1})
        ),
    )

    class Lstm:
        def __init__(self, columns, time, **kw):
            seen.update(columns=list(columns), time=time, kw=kw)

        def fit(self, train, val, contamination):
            seen.update(fit=(len(train), len(val), contamination))
            return self

        def score(self, test):
            return pd.Series([0.2] * 6)

        def flags(self, test):
            return pd.Series([True, False] * 3)

        def settings(self):
            return {"lstm": 1}

    monkeypatch.setattr(lp, "LSTMAutoencoder", Lstm)
    train, val, test = _frames()
    out = lp.compare(train, val, test, ["f0"], 7, fit_rows=6, window=3, hidden=5, max_epochs=2)
    assert seen["columns"] == ["f0"] and seen["time"] == lp.tp.TIME_UTC
    assert seen["kw"] == {"window": 3, "hidden": 5, "max_epochs": 2, "fit_rows": 6, "seed": 7}
    assert seen["fit"] == (10, 4, 0.5) and seen["contamination"] == 0.5
    assert len(seen["sample"]) == 6 and seen["sample"].index.is_monotonic_increasing
    assert set(out) == {"y", "autoencoder", "lstm"}
    assert out["y"].tolist() == test[lp.ANOMALY_COLUMN].tolist()
    assert out["autoencoder"]["settings"] == {"ae": 1} and out["lstm"]["settings"] == {"lstm": 1}
    assert set(out["lstm"]) == {"scores", "metrics", "settings", "fit_seconds"}
    assert out["lstm"]["fit_seconds"] >= 0 and "pr_auc" in out["lstm"]["metrics"]
    assert out["autoencoder"]["metrics"] != out["lstm"]["metrics"]


def test_the_fit_sample_never_exceeds_the_training_rows(monkeypatch):
    sizes = []
    monkeypatch.setattr(
        lp, "_row_autoencoder",
        lambda a, b, c: sizes.append(len(a)) or (np.zeros(6), np.zeros(6, dtype=bool), {}),
    )  # fmt: skip
    monkeypatch.setattr(
        lp, "LSTMAutoencoder",
        lambda *a, **k: SimpleNamespace(
            fit=lambda *x: SimpleNamespace(
                score=lambda t: pd.Series([0.0] * 6), flags=lambda t: pd.Series([False] * 6),
                settings=lambda: {},
            )
        ),
    )  # fmt: skip
    train, val, test = _frames()
    lp.compare(train, val, test, ["f0"], 1, fit_rows=1000)
    assert sizes == [10]


def test_the_summary_pairs_the_two_score_vectors_over_the_recorded_blocks(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        lp, "paired_block_bootstrap", lambda *a: seen.update(args=a) or {"ci_low": 0.1}
    )
    result = {
        "y": np.array([0, 1]),
        "autoencoder": {
            "scores": np.array([0.3, 0.4]),
            "metrics": {"m": 1},
            "settings": {"s": 1},
            "extra": 9,
        },
        "lstm": {"scores": np.array([0.5, 0.6]), "metrics": {"m": 2}, "settings": {"s": 2},
                 "fit_seconds": 3.0, "extra": 9},
    }  # fmt: skip
    times = pd.Series([1, 2])
    out = lp._summary(result, times)
    y, first, second, t, block, resamples, seed = seen["args"]
    assert (
        y is result["y"]
        and first is result["lstm"]["scores"]
        and second is result["autoencoder"]["scores"]
    )
    assert t is times and (block, resamples, seed) == (1800, 1000, 42)
    assert out == {
        "autoencoder": {"metrics": {"m": 1}, "settings": {"s": 1}},
        "lstm": {"metrics": {"m": 2}, "settings": {"s": 2}, "fit_seconds": 3.0},
        "lstm_minus_autoencoder": {"ci_low": 0.1},
    }


@pytest.mark.parametrize(("ci_low", "passes"), [(0.01, True), (0.0, False), (-0.2, False)])
def test_the_synthetic_gate_needs_a_strictly_positive_lower_bound(monkeypatch, ci_low, passes):
    train, val, test = _frames()
    called = {}
    monkeypatch.setattr(
        lp, "synthetic_sequence_stream", lambda: pd.DataFrame({"f0": [1.0], "f1": [2.0], "x": [3]})
    )
    monkeypatch.setattr(lp.tp, "chronological_partitions", lambda frame: (train, val, test))
    monkeypatch.setattr(
        lp, "compare",
        lambda *a, **k: called.update(a=a, k=k) or {"result": 1},
    )  # fmt: skip
    monkeypatch.setattr(
        lp,
        "_summary",
        lambda result, times: {"lstm_minus_autoencoder": {"ci_low": ci_low}, "t": times},
    )
    out = lp.run_synthetic()
    assert out["passes_gate"] is passes
    assert out["rows"] == {"train": 10, "validation": 4, "test": 6}
    assert called["a"][3] == ["f0", "f1"]
    assert called["k"] == {"seed": 42, "fit_rows": 10, "max_epochs": 20}
    assert out["t"].equals(test[lp.tp.TIME_UTC])


def test_credit_card_runs_each_seed_and_adds_the_reference_only_when_given(monkeypatch, caplog):
    train, val, test = _frames()
    spec = object()
    calls = []
    monkeypatch.setattr(lp.tp, "load", lambda s: "frame" if s is spec else None)
    monkeypatch.setattr(lp.tp, "chronological_partitions", lambda frame: (train, val, test))
    monkeypatch.setattr(lp.tp, "features", lambda s, f: pd.DataFrame({"a": [1], "b": [2]}))
    monkeypatch.setattr(lp.tp, "describe", lambda part: {"rows": len(part)})
    monkeypatch.setattr(lp, "compare", lambda *a: calls.append(a) or {"r": a[-1]})
    monkeypatch.setattr(lp, "_summary", lambda result, times: {"seed": result["r"]})
    with caplog.at_level(logging.INFO):
        out = lp.run_credit_card(spec, None)
    assert [call[4] for call in calls] == list(lp.SEEDS) and calls[0][3] == ["a", "b"]
    assert list(out["by_seed"]) == [str(s) for s in lp.SEEDS]
    assert out["by_seed"]["42"] == {"seed": 42}
    assert out["partitions"] == {
        "train": {"rows": 10},
        "validation": {"rows": 4},
        "test": {"rows": 6},
    }
    assert "reference_pilot_51" not in out and set(out) == {"by_seed", "partitions"}
    assert "credit card, seed 42" in caplog.text
    reference = {"chronological": {"zscore": {"pr_auc": 0.5}, "lof": {"pr_auc": 0.25}}}
    out = lp.run_credit_card(spec, reference)
    assert out["reference_pilot_51"] == {"zscore": 0.5, "lof": 0.25}


def test_the_command_writes_the_result_with_provenance_and_a_run_record(
    tmp_path, monkeypatch, capsys, caplog
):
    import provenance

    dataset = tmp_path / "cc.csv"
    dataset.write_text("a\n1\n")
    monkeypatch.setitem(lp.DATASETS, "credit_card", SimpleNamespace(csv=dataset))
    monkeypatch.setattr(lp, "run_synthetic", lambda: {"passes_gate": False})
    monkeypatch.setattr(lp, "run_credit_card", lambda spec, reference: {"reference": reference})
    records = []
    monkeypatch.setattr(provenance, "write_record", lambda path, **kw: records.append((path, kw)))
    out = tmp_path / "sub" / "lstm.json"
    out.parent.mkdir()
    with caplog.at_level(logging.INFO):
        assert lp.main(["--output", str(out)]) == 0
    result = json.loads(out.read_text())
    assert set(result) == {"synthetic_control", "credit_card", "provenance"}
    reference_file = lp.ROOT / "verification/evidence/temporal_pilot/temporal_pilot.json"
    expected = json.loads(reference_file.read_text()) if reference_file.is_file() else None
    assert result["credit_card"] == {"reference": expected}
    prov = result["provenance"]
    assert prov["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert prov["script_sha256"] == hashlib.sha256(Path(lp.__file__).read_bytes()).hexdigest()
    detector = Path(lp.__file__).with_name("lstm_detector.py")
    assert prov["detector_sha256"] == hashlib.sha256(detector.read_bytes()).hexdigest()
    assert prov["protocol"] == "verification/lstm_pilot.md"
    assert set(prov["versions"]) == {"torch", "numpy", "pandas", "scikit-learn"}
    assert set(prov) >= {"python", "platform", "machine", "cpu_count"}
    assert out.read_text() == json.dumps(result, indent=2, sort_keys=True, default=float) + "\n"
    path, kw = records[0]
    assert path == out.with_name("run_lstm_pilot.json")
    assert kw["experiment"] == "lstm_pilot" and kw["seeds"] == list(lp.SEEDS)
    assert (
        kw["dataset"] == "credit_card"
        and kw["data_path"] is None
        and kw["outputs"] == ["lstm.json"]
    )
    assert kw["settings"]["window"] == lp.WINDOW and kw["settings"]["hidden"] == lp.HIDDEN
    assert (
        kw["settings"]["fit_rows"] == lp.FIT_ROWS and kw["settings"]["protocol"] == prov["protocol"]
    )
    assert capsys.readouterr().out == f"wrote {out}\n"
    assert "synthetic control gate passed: False" in caplog.text
    assert "the synthetic gate failed" in caplog.text


def test_the_synthetic_only_option_skips_credit_card_and_a_passing_gate_is_not_warned(
    tmp_path, monkeypatch, caplog
):
    import provenance

    dataset = tmp_path / "cc.csv"
    dataset.write_text("a\n1\n")
    monkeypatch.setitem(lp.DATASETS, "credit_card", SimpleNamespace(csv=dataset))
    monkeypatch.setattr(lp, "run_synthetic", lambda: {"passes_gate": True})
    monkeypatch.setattr(lp, "run_credit_card", lambda *a: pytest.fail("credit card was run"))
    monkeypatch.setattr(provenance, "write_record", lambda *a, **k: None)
    out = tmp_path / "lstm.json"
    with caplog.at_level(logging.INFO):
        assert lp.main(["--output", str(out), "--synthetic-only"]) == 0
    assert set(json.loads(out.read_text())) == {"synthetic_control", "provenance"}
    assert "the synthetic gate failed" not in caplog.text


def test_the_reference_pilot_is_read_when_its_file_exists_and_the_default_output_is_the_results_dir(
    tmp_path, monkeypatch
):
    import provenance

    dataset = tmp_path / "cc.csv"
    dataset.write_text("a\n1\n")
    monkeypatch.setitem(lp.DATASETS, "credit_card", SimpleNamespace(csv=dataset))
    monkeypatch.setattr(lp, "run_synthetic", lambda: {"passes_gate": True})
    seen = {}
    monkeypatch.setattr(
        lp, "run_credit_card", lambda spec, reference: seen.update(ref=reference) or {}
    )
    monkeypatch.setattr(provenance, "write_record", lambda *a, **k: None)
    monkeypatch.setattr(lp.config, "RESULTS_DIR", tmp_path)
    reference = lp.ROOT / "verification" / "evidence" / "temporal_pilot" / "temporal_pilot.json"
    assert lp.main([]) == 0
    assert (tmp_path / "lstm_pilot.json").is_file()
    expected = json.loads(reference.read_text()) if reference.is_file() else None
    assert seen["ref"] == expected
