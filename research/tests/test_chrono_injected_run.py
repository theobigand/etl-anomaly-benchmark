"""Chronological injected study: loading, ordering, thinning, arms, pooled output, command."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrono_injected as ci  # noqa: E402
import injection as inj  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "chrono_injected"
NAMES = ["zscore", "iqr", "knn"]


def series(n=2400, shuffled=False, seed=4):
    rng = np.random.default_rng(seed)
    stamps = pd.date_range("2020-03-01", periods=n, freq="h")
    frame = pd.DataFrame(
        {
            "stamp": stamps.strftime("%d/%m/%Y %H:%M"),
            "counter": np.arange(n),
            "w": rng.normal(10, 2, n).round(3) + np.linspace(0, 3, n),
            "x": rng.normal(50, 5, n).round(3),
            "y": rng.normal(-5, 1, n).round(3),
            "z": rng.normal(0, 1, n).round(3),
        }
    )
    return frame.sample(frac=1.0, random_state=1).reset_index(drop=True) if shuffled else frame


SPEC = {"date": "stamp", "format": "%d/%m/%Y %H:%M"}


@pytest.fixture
def spec9999():
    ci.TIME_SPECS[9999] = SPEC
    yield 9999
    del ci.TIME_SPECS[9999]


def write(tmp_path, frame):
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    return path


def test_every_declared_time_format_reads_its_first_rows():
    heads = {
        247: pd.DataFrame({"date": ["5-Jan-09", "6-Jan-09"]}),
        275: pd.DataFrame({"dteday": ["2011-01-01", "2011-01-01"], "hr": [0, 1]}),
        360: pd.DataFrame({"Date": ["3/10/2004", "3/10/2004"], "Time": ["18:00:00", "19:00:00"]}),
        374: pd.DataFrame({"date": ["2016-01-1117:00:00", "2016-01-1117:10:00"]}),
        560: pd.DataFrame({"Date": ["1/12/2017", "1/12/2017"], "Hour": [0, 1]}),
        799: pd.DataFrame(
            {"timestamp": ["2019-11-06 11:37:13.038174+01:00", "2019-11-06 11:37:32+00:00"]}
        ),
        849: pd.DataFrame({"DateTime": ["1/1/2017 0:00", "1/1/2017 0:10"]}),
        851: pd.DataFrame({"date": ["01/01/2018 00:15", "01/01/2018 00:30"]}),
    }  # fmt: skip
    assert set(heads) == set(ci.TIME_SPECS)
    first = {i: ci.parse_time(f, ci.TIME_SPECS[i])[0].iloc[0] for i, f in heads.items()}
    assert first[247] == pd.Timestamp("2009-01-05") and first[374] == pd.Timestamp(
        "2016-01-11 17:00"
    )
    assert first[275] == pd.Timestamp("2011-01-01") and first[360] == pd.Timestamp(
        "2004-03-10 18:00"
    )
    assert first[560] == pd.Timestamp("2017-12-01") and first[849] == pd.Timestamp("2017-01-01")
    assert first[851] == pd.Timestamp("2018-01-01 00:15")
    assert first[799] == pd.Timestamp("2019-11-06 10:37:13.038174", tz="UTC")
    for i, f in heads.items():
        assert ci.parse_time(f, ci.TIME_SPECS[i])[0].notna().all(), i


def test_time_columns_are_reported_in_reading_order():
    f = pd.DataFrame({"Date": ["3/10/2004"], "Time": ["18:00:00"], "h": [2]})
    _, used = ci.parse_time(f, {**ci.TIME_SPECS[360], "hour": "h"})
    assert used == ["Date", "Time", "h"]


def test_trend_detection_uses_the_rank_correlation_threshold():
    stamps = pd.Series(pd.date_range("2020", periods=300, freq="h"))
    rng = np.random.default_rng(0)
    noisy = np.arange(300) + rng.normal(0, 60, 300)
    f = pd.DataFrame({"exact": np.arange(300), "down": -np.arange(300.0), "noisy": noisy})
    assert ci.trend_columns(f, stamps) == ["exact", "down"]
    assert ci.trend_columns(f.assign(text="a"), stamps) == ["exact", "down"]


def test_load_series_sorts_by_time_drops_counters_and_reports(tmp_path, spec9999):
    path = write(tmp_path, series(shuffled=True))
    table, report = ci.load_series(9999, {"name": "S"}, path)
    assert report["file_order_chronological"] is False
    assert report["time_columns"] == ["stamp"] and report["trend_columns_dropped"] == ["counter"]
    assert report["span"] == ["2020-03-01 00:00:00", "2020-06-08 23:00:00"]
    assert report["rows_in"] == 2400 and report["rows_out"] == len(table) == 2400
    assert report["columns"] == ["w", "x", "y", "z"] and list(table.columns) == report["columns"]
    assert (
        table["w"].iloc[:600].mean() < table["w"].iloc[-600:].mean()
    )  # the trend is in time order
    ordered = ci.load_series(9999, {"name": "S"}, write(tmp_path, series()))[1]
    assert ordered["file_order_chronological"] is True


def test_load_series_thins_long_tables_by_a_regular_stride(tmp_path, spec9999, monkeypatch):
    monkeypatch.setattr(ci, "MAX_ROWS", 1000)
    table, report = ci.load_series(9999, {"name": "S"}, write(tmp_path, series()))
    assert report["stride"] == 3 and len(table) == 800 and report["rows_out"] == 800


def test_load_series_refuses_unusable_tables(tmp_path, spec9999):
    few_rows = write(tmp_path, series(n=1000))
    with pytest.raises(inj.NotEligible, match="only 1000 rows after cleaning"):
        ci.load_series(9999, {"name": "S"}, few_rows)
    narrow = write(tmp_path, series().drop(columns=["y", "z"]))
    with pytest.raises(inj.NotEligible, match="only 2 continuous columns"):
        ci.load_series(9999, {"name": "S"}, narrow)
    bad = series().assign(stamp="nope")
    with pytest.raises(inj.NotEligible, match="2400 timestamps could not be read"):
        ci.load_series(9999, {"name": "S"}, write(tmp_path, bad))


def test_load_series_drops_rows_with_missing_values_and_duplicates(tmp_path, spec9999):
    f = series(n=2600)
    f.loc[:99, "x"] = np.nan
    f = pd.concat([f, f.iloc[200:300]], ignore_index=True)
    table, report = ci.load_series(9999, {"name": "S"}, write(tmp_path, f))
    assert len(table) == 2500 and report["rows_in"] == 2700


def test_arms_split_sixty_forty_and_the_random_arm_depends_on_the_seed():
    table = pd.DataFrame({"a": np.arange(100.0)})
    fit, test = ci.split_arm(table, "chronological", seed=1)
    assert list(fit["a"]) == list(range(60)) and list(test["a"]) == list(range(60, 100))
    a1, _ = ci.split_arm(table, "random", seed=1)
    a2, _ = ci.split_arm(table, "random", seed=2)
    assert list(a1["a"]) != list(a2["a"]) and list(a1["a"]) == list(
        ci.split_arm(table, "random", 1)[0]["a"]
    )


def test_arm_evaluation_counts_clean_and_typed_rows(tmp_path, spec9999):
    table, _ = ci.load_series(9999, {"name": "S"}, write(tmp_path, series()))
    out = ci.evaluate_arm(table, "chronological", 42, NAMES)
    assert set(out["hits"]) == set(NAMES) and out["counts"]["clean"] > 800
    assert set(out["counts"]) == {"clean", *inj.ANOMALY_TYPES}
    assert all(out["counts"][t] == 29 for t in inj.ANOMALY_TYPES)  # round(3 % of 960 test rows)
    assert all(0 <= out["false_alarms"][m] <= out["counts"]["clean"] for m in NAMES)


def test_run_one_pools_seeds_per_arm_and_matches_the_snapshot(tmp_path, spec9999, monkeypatch):
    data = tmp_path / "data" / "pool"
    data.mkdir(parents=True)
    write(data, series()).rename(data / "9999.csv")
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    out = ci.run_one((9999, {"name": "Toy"}), names=NAMES)
    out["carrier"] = {k: out["carrier"][k] for k in ("rows_out", "columns", "span")}
    assert json.dumps(out, sort_keys=True, indent=1) + "\n" == (GOLDEN / "toy.json").read_text()
    assert out["protocol"] == ci.PROTOCOL and out["contamination"] == ci.CONTAMINATION


# --- contracts -------------------------------------------------------------------------------


def test_monotone_but_nonlinear_counters_are_found_by_the_rank_correlation():
    stamps = pd.Series(pd.date_range("2020", periods=300, freq="h"))
    f = pd.DataFrame(
        {"power": np.arange(300.0) ** 6, "noise": np.random.default_rng(0).normal(size=300)}
    )
    assert (
        abs(f["power"].corr(f["noise"])) < 0.99
        and np.corrcoef(stamps.rank(), f["power"])[0, 1] < 0.99
    )
    assert ci.trend_columns(f, stamps) == ["power"]


def test_a_numeric_hour_column_is_a_time_column_not_a_feature(tmp_path):
    n = 2400
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {
            "day": np.repeat(pd.date_range("2020-01-01", periods=n // 24).strftime("%Y-%m-%d"), 24),
            "hr": np.tile(np.arange(24), n // 24),
            "x": rng.normal(0, 1, n),
            "y": rng.normal(5, 1, n),
            "z": rng.normal(-5, 1, n),
            "w": rng.normal(9, 2, n),
        }
    )
    ci.TIME_SPECS[9997] = {"date": "day", "hour": "hr", "format": "%Y-%m-%d"}
    try:
        table, report = ci.load_series(9997, {"name": "S"}, write(tmp_path, frame))
    finally:
        del ci.TIME_SPECS[9997]
    assert "hr" not in table.columns and report["columns"] == ["x", "y", "z", "w"]
    assert report["time_columns"] == ["day", "hr"]


def test_equal_timestamps_keep_their_file_order(tmp_path, spec9999):
    n = 3000
    rng = np.random.default_rng(2)
    f = series(n=n)
    f["stamp"] = (
        pd.Series(pd.date_range("2020-03-01", periods=30, freq="D"))
        .dt.strftime("%d/%m/%Y %H:%M")[np.repeat(np.arange(30), n // 30)]
        .to_numpy()
    )
    f = f.drop(columns="counter")
    f["w"] = rng.normal(0, 1, n)
    table, _ = ci.load_series(9999, {"name": "S"}, write(tmp_path, f))
    expected = f.assign(_t=pd.to_datetime(f["stamp"], format=SPEC["format"])).sort_values(
        "_t", kind="stable"
    )
    kept = expected.drop_duplicates(subset=["w", "x", "y", "z"])
    assert list(table["w"]) == pytest.approx(list(kept["w"]))


def test_rows_equal_in_value_at_different_times_are_duplicates(tmp_path, spec9999):
    f = series(n=2000)
    later = f.iloc[:100].copy()
    later["stamp"] = pd.date_range("2021-01-01", periods=100, freq="h").strftime("%d/%m/%Y %H:%M")
    later["counter"] = np.arange(2000, 2100)
    table, report = ci.load_series(9999, {"name": "S"}, write(tmp_path, pd.concat([f, later])))
    assert len(table) == 2000 and report["rows_in"] == 2100 and "stride" not in report


def test_row_count_boundaries_and_index_after_thinning(tmp_path, spec9999, monkeypatch):
    table, report = ci.load_series(9999, {"name": "S"}, write(tmp_path, series(n=1500)))
    assert len(table) == 1500 and report["rows_out"] == 1500
    monkeypatch.setattr(ci, "MAX_ROWS", 1500)
    same, rep = ci.load_series(9999, {"name": "S"}, write(tmp_path, series(n=1500)))
    assert len(same) == 1500 and "stride" not in rep
    monkeypatch.setattr(ci, "MAX_ROWS", 1600)
    thin, rep = ci.load_series(9999, {"name": "S"}, write(tmp_path, series(n=2400)))
    assert rep["stride"] == 2 and list(thin.index) == list(range(1200))
    assert list(thin.columns) == rep["columns"] == ["w", "x", "y", "z"]


def test_arm_evaluation_passes_seed_fit_rows_and_time_to_the_detectors(
    tmp_path, spec9999, monkeypatch
):
    table, _ = ci.load_series(9999, {"name": "S"}, write(tmp_path, series()))
    built, capped_calls, detected = [], [], []
    real_build, real_capped, real_detect = ci.build, ci.capped, ci.detect

    def build(name, contamination, seed):
        built.append((name, contamination, seed))
        return real_build(name, contamination, seed)

    def capped(frame, name, seed):
        capped_calls.append((name, seed, len(frame), set(frame["t"])))
        return real_capped(frame, name, seed)

    def detect(frame, detector, fit_df):
        detected.append((list(frame.columns), len(frame), list(fit_df.columns)))
        return real_detect(frame, detector, fit_df=fit_df)

    monkeypatch.setattr(ci, "build", build)
    monkeypatch.setattr(ci, "capped", capped)
    monkeypatch.setattr(ci, "detect", detect)
    out = ci.evaluate_arm(table, "random", 7, ["zscore", "knn"])
    assert built == [("zscore", ci.CONTAMINATION, 7), ("knn", ci.CONTAMINATION, 7)]
    assert capped_calls == [
        ("zscore", 7, 1440, {pd.Timestamp("2020-01-01")}),
        ("knn", 7, 1440, {pd.Timestamp("2020-01-01")}),
    ]
    cols = list(table.columns)
    assert all(d[0] == [*cols, "t"] and d[2] == [*cols, "t"] for d in detected)
    assert detected[0][1] == 960 + 29 and out["counts"]["clean"] == 960 - 5 * 29


def test_run_one_defaults_to_the_classical_detectors_and_pools_counts(
    tmp_path, spec9999, monkeypatch
):
    data = tmp_path / "data" / "pool"
    data.mkdir(parents=True)
    write(data, series()).rename(data / "9999.csv")
    monkeypatch.setattr(ci, "ROOT", tmp_path)
    calls = []

    def stub(table, arm, seed, names):
        calls.append((arm, seed, list(names)))
        counts = {t: 2 for t in ["clean", *inj.ANOMALY_TYPES]}
        return {
            "counts": counts,
            "hits": {m: {t: 1 for t in inj.ANOMALY_TYPES} for m in names},
            "false_alarms": {m: 3 for m in names},
        }

    monkeypatch.setattr(ci, "evaluate_arm", stub)
    out = ci.run_one((9999, {"name": "Toy"}))
    assert [c[:2] for c in calls] == [(a, s) for a in ("chronological", "random") for s in ci.SEEDS]
    assert calls[0][2] == ci.DETECTORS and "drift" not in ci.DETECTORS
    arm = out["arms"]["random"]
    assert arm["clean_rows"] == 10 and arm["test_counts"]["duplicate"] == 10
    assert arm["fpr"]["knn"] == pytest.approx(15 / 10) and arm["recall"]["knn"][
        "duplicate"
    ] == pytest.approx(0.5)
    assert out["id"] == "uci:9999" and out["name"] == "Toy" and out["seeds"] == list(ci.SEEDS)
    assert out["carrier"]["rows_out"] == 2400


class SerialPool:
    created = []

    def __init__(self, max_workers):
        SerialPool.created.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        return [fn(i) for i in items]


def test_the_parser_defaults_and_choices():
    args = ci.PARSER.parse_args(["--output", "o"])
    assert (args.methods, args.workers, args.only) == ("classical", 4, None)
    assert ci.PARSER.parse_args(["--output", "o", "--only", "1", "2"]).only == [1, 2]
    with pytest.raises(SystemExit):
        ci.PARSER.parse_args([])
    with pytest.raises(SystemExit):
        ci.PARSER.parse_args(["--output", "o", "--methods", "other"])


def test_main_reads_the_registry_and_pool_paths_and_prints_each_finished_table(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    curated = root.joinpath(*ci.CURATED)
    curated.parent.mkdir(parents=True)
    curated.write_text(
        json.dumps({"kept": [{"uci_id": 9999, "name": "Toy"}, {"uci_id": 9998, "name": "Short"}]})
    )
    pool = root.joinpath(*ci.POOL_DIR)
    pool.mkdir(parents=True)
    write(pool, series()).rename(pool / "9999.csv")
    write(pool, series(n=900)).rename(pool / "9998.csv")
    printed, runs = [], []
    monkeypatch.setattr(ci, "ROOT", root)
    monkeypatch.setattr(ci, "TIME_SPECS", {9999: SPEC, 9998: SPEC})
    monkeypatch.setattr(ci, "ProcessPoolExecutor", SerialPool)
    monkeypatch.setattr(ci, "run_one", fake_run_named(runs))
    monkeypatch.setattr(ci, "print", lambda *a, **k: printed.append((a, k)), raising=False)
    SerialPool.created.clear()
    out = tmp_path / "out"
    assert ci.main(["--output", str(out), "--workers", "3"]) == 0
    assert SerialPool.created == [3] and printed == [((9999,), {"flush": True})]
    status = json.loads((out / "eligibility.json").read_text())
    assert status == {"skipped": {"uci:9998": "only 900 rows after cleaning"}, "run": ["uci:9999"]}
    assert (out / "eligibility.json").read_text() == json.dumps(status)
    assert (
        out / "classical" / "uci_9999.json"
    ).read_text() == '{"id": "uci:9999", "names": null, "zeta": 1}\n'
    assert ci.main(["--output", str(out), "--methods", "deep", "--only", "9999"]) == 0
    deep = json.loads((out / "deep" / "uci_9999.json").read_text())
    assert deep["names"] == list(ci.DEEP_NAMES)
    assert ci.main(["--output", str(out), "--only", "9998"]) == 0
    assert json.loads((out / "eligibility.json").read_text())["run"] == []
    assert runs == ["uci:9999", "uci:9999"]


def fake_run_named(log):
    def run(item, names=None):
        log.append(f"uci:{item[0]}")
        return {"zeta": 1, "id": f"uci:{item[0]}", "names": names}

    return run
