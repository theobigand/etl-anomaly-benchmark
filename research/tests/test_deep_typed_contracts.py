"""Argument routing, hypothesis rules and the command of the deep typed matrix."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deep_typed as dt  # noqa: E402

TYPES = list(dt.ANOMALY_TYPES)


def test_the_window_order_key_is_the_utc_signup_date_and_an_unreadable_date_goes_first():
    part = pd.DataFrame(
        {"signup_date": ["2020-03-01", "garbage", "2020-01-05 10:00"], "v": [1, 2, 3]}
    )
    out = dt._with_time(part)
    assert str(out["t"].dt.tz) == "UTC"
    assert out["t"].tolist() == [
        pd.Timestamp("2020-03-01", tz="UTC"),
        pd.Timestamp("2020-01-05 10:00", tz="UTC"),
        pd.Timestamp("2020-01-05 10:00", tz="UTC"),
    ]
    assert "t" not in part.columns and out["v"].tolist() == [1, 2, 3]


def test_the_recall_frame_is_serialised_in_split_orientation():
    frame = pd.DataFrame([[0.5, 1.0]], index=["m"], columns=["a", "b"])
    assert dt._frame(frame) == {"columns": ["a", "b"], "index": ["m"], "data": [[0.5, 1.0]]}


class _Det:
    def __init__(self, tag, log):
        self.tag, self.log = tag, log

    def settings(self):
        return {"tag": self.tag, "converged": True}


def _stub_run(monkeypatch, log, rows_flag=None):
    n = 10
    anomaly_type = ["clean"] * 6 + ["missing_value"] * 2 + ["temporal_drift"] * 2

    def part(count, signup):
        frame = pd.DataFrame(
            {"signup_date": [signup] * count, "anomaly": [True, False] * (count // 2)}
        )
        for column in dt.FEATURE_COLUMNS:
            frame[column] = 1.0
        return frame

    train, val = part(4, "2020-01-01"), part(2, "2020-01-02")
    test = part(n, "2020-01-03").assign(anomaly_type=anomaly_type)

    monkeypatch.setattr(
        dt, "make_synthetic", lambda seed, **kw: log.append(("make", seed, kw)) or "df"
    )
    base = pd.DataFrame(0.0, index=["zscore"], columns=TYPES)
    monkeypatch.setattr(
        dt.rsb,
        "evaluate",
        lambda df, seed: (
            log.append(("evaluate", df, seed)) or {"recall": base, "precision": base + 1}
        ),
    )
    monkeypatch.setattr(dt.rsb, "_split_synthetic", lambda df, seed: (train, val, test))
    monkeypatch.setattr(
        dt.rsb,
        "_per_type",
        lambda series, types: (
            log.append(("per_type", series.dtype, len(series)))
            or (
                {t: 0.25 for t in TYPES},
                {t: 0.75 for t in TYPES},
            )
        ),
    )

    def ae(contamination, random_state):
        log.append(("ae", contamination, random_state))
        return _Det("ae", log)

    monkeypatch.setattr(dt, "AutoencoderDetector", ae)

    class Result:
        flags = pd.Series([1, 0] * 5)

    def detect(frame, detector, fit_df):
        log.append(("detect", list(frame.columns), list(fit_df.columns), len(frame), len(fit_df)))
        return Result()

    monkeypatch.setattr(dt, "detect", detect)

    class Lstm:
        def __init__(self, columns, time, **kw):
            log.append(("lstm", list(columns), time, kw))

        def fit(self, train_part, val_part, contamination):
            log.append(("fit", len(train_part), len(val_part), contamination, "t" in train_part))
            return self

        def flags(self, test_part):
            return pd.Series([0, 1] * 5)

        def settings(self):
            return {"converged": False}

    monkeypatch.setattr(dt, "LSTMAutoencoder", Lstm)


def test_a_seed_run_routes_data_sizes_and_contamination_to_both_deep_detectors(monkeypatch):
    log = []
    _stub_run(monkeypatch, log)
    out = dt.run_seed(7, rows=120, max_epochs=9)
    assert log[0] == ("make", 7, {"n_rows": 120}) and log[1] == ("evaluate", "df", 7)
    assert ("ae", 0.5, 7) in log
    detect = next(entry for entry in log if entry[0] == "detect")
    assert detect[1:] == (list(dt.FEATURE_COLUMNS), list(dt.FEATURE_COLUMNS), 10, 4)
    lstm = next(entry for entry in log if entry[0] == "lstm")
    assert lstm[1:3] == (list(dt.NUMERIC_FEATURES), "t")
    assert lstm[3] == {
        "max_epochs": 9, "patience": dt.PATIENCE, "fit_rows": 4, "validation_rows": 2, "seed": 7,
    }  # fmt: skip
    assert ("fit", 4, 2, 0.5, True) in log
    assert out["seed"] == 7 and out["rows"] == {"train": 4, "validation": 2, "test": 10}
    assert set(out["deep"]) == {"autoencoder", "lstm_autoencoder"}
    assert out["deep"]["autoencoder"]["settings"] == {"tag": "ae", "converged": True}
    assert out["deep"]["lstm_autoencoder"]["settings"] == {"converged": False}
    assert out["deep"]["autoencoder"]["fpr"] == pytest.approx(0.5)
    assert out["deep"]["lstm_autoencoder"]["fpr"] == pytest.approx(0.5)
    assert all(out["deep"][name]["seconds"] >= 0 for name in out["deep"])
    assert out["recall"]["index"] == ["zscore", "autoencoder", "lstm_autoencoder"]
    assert out["recall"]["columns"] == TYPES
    assert out["recall"]["data"][1] == [0.25] * 6 and out["precision"]["data"][2] == [0.75] * 6
    assert all(
        entry[1] is np.dtype(bool) and entry[2] == 10 for entry in log if entry[0] == "per_type"
    )


def test_without_a_row_count_the_default_synthetic_size_is_used(monkeypatch):
    log = []
    _stub_run(monkeypatch, log)
    dt.run_seed(3)
    assert log[0] == ("make", 3, {})
    assert next(e for e in log if e[0] == "lstm")[3]["max_epochs"] == dt.MAX_EPOCHS


def _means(cells=None):
    index = [
        "zscore",
        "iqr",
        "great_expectations",
        "isolation_forest",
        "autoencoder",
        "lstm_autoencoder",
    ]
    base = pd.DataFrame(0.25, index=index, columns=TYPES)
    for (method, column), value in (cells or {}).items():
        base.loc[method, column] = value
    return [base.copy() for _ in range(5)]


def _deep(ae=5, lstm=5):
    out = []
    for i in range(5):
        out.append(
            {
                "autoencoder": {"settings": {"converged": i < ae}},
                "lstm_autoencoder": {"settings": {"converged": i < lstm}},
            }
        )
    return out


def test_h1_h2_report_their_numbers_and_flip_with_the_stated_margins():
    frames = _means({("lstm_autoencoder", "temporal_drift"): 0.75, ("iqr", "temporal_drift"): 0.5})
    out = dt.hypotheses(frames, _deep())
    assert out["H1"] == {
        "supported": True,
        "lstm_drift_recall": 0.75,
        "best_row_level": {"method": "iqr", "recall": 0.5},
    }
    close = _means(
        {("lstm_autoencoder", "temporal_drift"): 0.625, ("iqr", "temporal_drift"): 0.5625}
    )
    assert dt.hypotheses(close, _deep())["H1"]["supported"] is False
    gap = out["H2"]["gap_to_best_row"]
    assert set(gap) == {"missing_value", "duplicate", "invalid_format"}
    assert gap["duplicate"] == 0.0 and out["H2"]["supported"] is True
    worse = _means({("lstm_autoencoder", "duplicate"): 0.5})
    assert dt.hypotheses(worse, _deep())["H2"]["supported"] is False
    just = _means({("lstm_autoencoder", "invalid_format"): 0.25, ("iqr", "invalid_format"): 0.3})
    assert dt.hypotheses(just, _deep())["H2"]["supported"] is True


def test_h3_needs_four_converged_seeds_for_both_detectors_and_h4_each_of_its_conditions():
    frames = _means()
    out = dt.hypotheses(frames, _deep(ae=4, lstm=4))
    assert out["H3"] == {"supported": True, "converged": {"autoencoder": 4, "lstm_autoencoder": 4}}
    assert dt.hypotheses(frames, _deep(ae=3, lstm=5))["H3"]["supported"] is False
    assert dt.hypotheses(frames, _deep(ae=5, lstm=3))["H3"]["supported"] is False
    t = "multivariate_outlier"
    good = _means({("autoencoder", t): 0.5, ("isolation_forest", t): 0.5, ("zscore", t): 0.5})
    h4 = dt.hypotheses(good, _deep())["H4"]
    assert h4["supported"] is True
    assert h4["recall"] == {"autoencoder": 0.5, "zscore": 0.5, "iqr": 0.25, "isolation_forest": 0.5}
    below_rule = _means({("autoencoder", t): 0.5, ("iqr", t): 0.625, ("isolation_forest", t): 0.5})
    assert dt.hypotheses(below_rule, _deep())["H4"]["supported"] is False
    ahead_of_forest = _means({("autoencoder", t): 0.5, ("isolation_forest", t): 0.4375})
    assert dt.hypotheses(ahead_of_forest, _deep())["H4"]["supported"] is False
    behind_forest = _means({("autoencoder", t): 0.5, ("isolation_forest", t): 0.5625})
    assert dt.hypotheses(behind_forest, _deep())["H4"]["supported"] is True


def test_the_mean_and_deviation_keep_the_method_order_of_the_input():
    first = pd.DataFrame({"a": [1.0, 3.0], "b": [2.0, 2.0]}, index=["zz", "aa"])
    second = pd.DataFrame({"a": [3.0, 5.0], "b": [2.0, 4.0]}, index=["zz", "aa"])
    mean, std = dt.mean_std([first, second])
    assert mean.index.tolist() == ["zz", "aa"]
    assert mean.loc["zz", "a"] == 2.0 and mean.loc["aa", "b"] == 3.0
    assert std.loc["zz", "a"] == pytest.approx(np.sqrt(2.0))


def _fake_run(seed, rows=None, max_epochs=0):
    methods = ["zscore", "iqr", "great_expectations", "isolation_forest"]
    methods += ["autoencoder", "lstm_autoencoder"]
    frame = pd.DataFrame(0.5 + seed / 100, index=methods, columns=TYPES)
    deep = {n: {"settings": {"converged": True}} for n in ("autoencoder", "lstm_autoencoder")}
    return {"seed": seed, "recall": dt._frame(frame), "deep": deep}


def test_the_command_runs_every_seed_and_writes_runs_results_and_a_markdown_table(
    tmp_path, monkeypatch, capsys
):
    calls = []
    monkeypatch.setattr(
        dt, "run_seed", lambda seed, max_epochs: calls.append((seed, max_epochs)) or _fake_run(seed)
    )
    out = tmp_path / "new" / "dir"
    assert dt.main(["--output", str(out)]) == 0
    assert calls == [(seed, dt.MAX_EPOCHS) for seed in dt.SEEDS]
    assert capsys.readouterr().out.splitlines() == [f"seed {seed}" for seed in dt.SEEDS]
    for seed in dt.SEEDS:
        text = (out / f"seed_{seed}.json").read_text()
        assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    results = json.loads((out / "deep_typed_results.json").read_text())
    assert set(results) == {"mean", "std", "hypotheses"} and set(results["hypotheses"]) == {
        "H1",
        "H2",
        "H3",
        "H4",
    }
    table = (out / "deep_typed_results.md").read_text().splitlines()
    assert table[0] == "| method | " + " | ".join(TYPES) + " |"
    assert table[1] == "|---|" + "---|" * len(TYPES)
    assert table[2].startswith("| zscore | 0.60 ± 0.18 |")
    assert len(table) == 2 + 6


def test_the_epoch_budget_is_a_command_option(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dt, "run_seed", lambda seed, max_epochs: calls.append(max_epochs) or _fake_run(seed)
    )
    dt.main(["--output", str(tmp_path), "--max-epochs", "4"])
    assert set(calls) == {4}
    with pytest.raises(SystemExit) as stop:
        dt.main([])
    assert stop.value.code == 2
