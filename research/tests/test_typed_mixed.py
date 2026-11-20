"""Mixed-schema typed run: eligibility, train-only layout, per-type counts, pooled recall."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection_mixed as im  # noqa: E402
import typed_mixed as tm  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "typed_mixed"
NAMES = ["zscore", "iqr", "knn"]


def frame(n=320, seed=11):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "a": rng.normal(10, 2, n).round(3),
            "b": rng.normal(500, 30, n).round(3),
            "c": np.abs(rng.normal(5, 1, n)).round(3),
            "p": rng.choice(["x", "y", "z", "w"], n),
            "q": rng.choice(["m1", "m2", "m3"], n),
        }
    )


def job(tmp_path, n=320, name="Toy"):
    path = tmp_path / "toy.csv"
    frame(n).to_csv(path, index=False)
    return {"id": "uci:9999", "source": "uci", "name": name, "path": str(path), "meta": {}}


def test_seeds_depend_on_the_tier():
    assert tm.seeds_for(500) == (42, 1, 2, 3, 4)
    assert tm.seeds_for(499) == (42, *range(1, 20)) and len(tm.seeds_for(499)) == 20


def test_load_carrier_reports_tier_kinds_and_source_rows(tmp_path):
    table, kinds, report = tm.load_carrier(job(tmp_path))
    assert len(table) == 320 and report["tier"] == "B" and report["source_rows"] == 320
    assert report["normal_class_only"] is False
    assert kinds == {"a": "num", "b": "num", "c": "num", "p": "cat", "q": "cat"}


def test_adbench_carrier_keeps_only_the_normal_class(tmp_path):
    rng = np.random.default_rng(0)
    x = np.c_[rng.normal(size=(400, 3)), rng.integers(0, 2, 400)]
    y = np.r_[np.zeros(300), np.ones(100)]
    path = tmp_path / "t.npz"
    np.savez(path, X=x, y=y)
    adb = {"id": "adbench:t", "source": "adbench", "name": "t", "path": str(path)}
    table, _kinds, report = tm.load_carrier(adb)
    assert report["source_rows"] == 300 and report["normal_class_only"] is True
    assert list(table.columns)[:2] == ["f0", "f1"]


def test_eligibility_records_types_and_refusals(tmp_path):
    row = tm.eligibility(job(tmp_path))
    assert row["eligible"] is True and row["tier"] == "B" and row["rows"] == 320
    assert row["kinds"] == {"num": 3, "cat": 2} and "invalid_code" in row["types"]
    small = tm.eligibility(job(tmp_path, n=150))
    assert small["eligible"] is False and "rows after cleaning" in small["reason"]
    broken = tm.eligibility({**job(tmp_path), "path": str(tmp_path / "missing.csv")})
    assert broken["eligible"] is False and broken["reason"].startswith("load failed")
    assert {k: broken[k] for k in ("id", "name", "source")} == {
        "id": "uci:9999",
        "name": "Toy",
        "source": "uci",
    }


def test_the_layout_does_not_depend_on_the_reference(tmp_path):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    out = tm._seed_layout(clean, kinds, 5)
    plain = im.inject_mixed(clean, kinds, 5)
    assert out[["group_id", "anomaly_type"]].equals(plain[["group_id", "anomaly_type"]])
    assert not out[list(clean.columns)].equals(plain[list(clean.columns)])


def test_evaluation_of_one_seed_counts_every_test_row_once(tmp_path):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    result = tm.evaluate_seed(clean, kinds, 5, NAMES)
    assert set(result["hits"]) == {*NAMES, "transform_dedup"}
    assert set(result["counts"]) == set(im.ANOMALY_TYPES)
    total = sum(result["counts"].values()) + result["clean"]
    assert 0.1 < total / (len(clean) + im.TIER_B_K) < 0.2  # the 15 % test partition
    assert result["hits"]["transform_dedup"]["duplicate"] == result["counts"]["duplicate"]
    assert all(result["false_alarms"][m] <= result["clean"] for m in result["hits"])
    drift = tm.evaluate_seed(clean, kinds, 5, ["drift"])
    assert set(drift["hits"]) == {"drift", "transform_dedup"}


def test_the_run_pools_counts_over_the_tier_seeds_and_matches_the_snapshot(tmp_path):
    out = tm.run_one(job(tmp_path), names=NAMES)
    out["carrier"] = {k: out["carrier"][k] for k in ("tier", "rows_out", "kinds")}
    assert json.dumps(out, sort_keys=True, indent=1) + "\n" == (GOLDEN / "toy.json").read_text()
    assert out["seeds"] == list(tm.SEEDS_B) and out["protocol"] == tm.PROTOCOL
    assert out["recall_pooled"]["transform_dedup"]["duplicate"] == 1.0
    assert out["types"] == im.supported_types(out["carrier"]["kinds"], None) or out["types"]


def test_unsupported_types_are_absent_not_zero(tmp_path):
    rng = np.random.default_rng(3)
    levels = list("abcde")
    only_cat = pd.DataFrame({c: rng.choice(levels, 400) for c in "pqrs"})
    path = tmp_path / "cat.csv"
    only_cat.to_csv(path, index=False)
    cat_job = {"id": "uci:1", "source": "uci", "name": "Cat", "path": str(path), "meta": {}}
    out = tm.run_one(cat_job, names=["zscore"])
    assert "univariate_outlier" not in out["recall_pooled"]["zscore"]
    assert "invalid_code" in out["recall_pooled"]["zscore"]


# --- contracts of the loading, layout, evaluation and command plumbing -----------------------


def test_load_carrier_defaults_to_seed_zero_and_forwards_a_given_seed(tmp_path, monkeypatch):
    seen = []
    real = tm.im.prepare_mixed

    def spy(features, seed, cap=im.MAX_ROWS):
        seen.append((seed, list(features.index[:2])))
        return real(features, seed=seed)

    monkeypatch.setattr(tm.im, "prepare_mixed", spy)
    tm.load_carrier(job(tmp_path))
    tm.load_carrier(job(tmp_path), seed=7)
    assert [s for s, _ in seen] == [0, 7] and all(i == [0, 1] for _, i in seen)


def test_a_labelled_uci_table_keeps_only_normal_class_rows(tmp_path, monkeypatch):
    calls = []

    def fake_labels(frame, meta):
        calls.append((len(frame), meta))
        labels = np.arange(len(frame)) % 4 == 0  # a quarter of the rows are the anomaly class
        return frame, labels.astype(int), {}

    monkeypatch.setattr(tm.ul, "derive_labels", fake_labels)
    meta = {"tasks": ["Classification"]}
    table, _, report = tm.load_carrier({**job(tmp_path), "meta": meta})
    assert calls == [(320, meta)]
    assert report["normal_class_only"] is True and report["source_rows"] == 240
    assert len(table) == 240


def test_eligibility_checks_data_conditions_and_keeps_the_carrier_report(tmp_path):
    rng = np.random.default_rng(0)
    same = pd.DataFrame(
        {
            "a": rng.normal(0, 1, 300),
            "b": rng.normal(0.1, 1, 300),
            "p": rng.choice(["u", "v"], 300),
            "q": rng.choice(["u", "v"], 300),
        }
    )
    path = tmp_path / "same.csv"
    same.to_csv(path, index=False)
    row = tm.eligibility(
        {"id": "uci:5", "source": "uci", "name": "Same", "path": str(path), "meta": {}}
    )
    assert "cross_column_swap" not in row["types"] and "multivariate_outlier" in row["types"]
    assert row["report"]["rows_out"] == 300 and row["report"]["tier"] == "B"
    assert row["kinds"] == {"num": 2, "cat": 2}
    base_row = tm.eligibility(job(tmp_path))
    assert "cross_column_swap" in base_row["types"]


def test_the_training_reference_is_clean_rows_with_a_fresh_index(tmp_path, monkeypatch):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    real = tm.im.inject_mixed
    refs = []

    def spy(c, k, seed, **kw):
        refs.append(kw.get("reference"))
        return real(c, k, seed, **kw)

    monkeypatch.setattr(tm.im, "inject_mixed", spy)
    tm._seed_layout(clean, kinds, 3)
    assert refs[0] is None and list(refs[1].index) == list(range(len(refs[1])))
    assert list(refs[1].columns) == list(clean.columns)
    train, _v, _t = tm.tb.split(real(clean, kinds, 3), 3)
    assert len(refs[1]) == int((train["anomaly_type"] == "clean").sum())


def test_a_reference_that_moves_rows_between_groups_is_an_error(tmp_path, monkeypatch):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    real = tm.im.inject_mixed

    def moving(c, k, seed, **kw):
        out = real(c, k, seed, **kw)
        if kw.get("reference") is not None:
            out = out.assign(group_id=out["group_id"].iloc[::-1].to_numpy())
        return out

    monkeypatch.setattr(tm.im, "inject_mixed", moving)
    with pytest.raises(AssertionError, match="^the reference changed the group or type layout$"):
        tm._seed_layout(clean, kinds, 3)


class Spy:
    def __init__(self, store):
        self.store = store

    def __call__(self, *args, **kwargs):
        self.store.append((args, kwargs))
        return self


def test_each_detector_gets_the_training_contamination_the_seed_and_a_capped_fit(
    tmp_path, monkeypatch
):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    built, capped_calls, fits = [], [], []
    real_detect = tm.detect

    def fake_build(name, contamination, seed):
        built.append((name, round(contamination, 6), seed))
        return real_build(name, contamination, seed)

    real_build, real_capped = tm.build, tm.capped
    monkeypatch.setattr(tm, "build", fake_build)

    def fake_capped(frame, name, seed):
        capped_calls.append((name, seed, len(frame)))
        return real_capped(frame, name, seed)

    monkeypatch.setattr(tm, "capped", fake_capped)

    def fake_detect(x_test, detector, fit_df):
        fits.append((list(x_test.columns), len(fit_df)))
        return real_detect(x_test, detector, fit_df=fit_df)

    monkeypatch.setattr(tm, "detect", fake_detect)
    tm.evaluate_seed(clean, kinds, 5, ["zscore", "iqr"])
    layout = tm._seed_layout(clean, kinds, 5)
    train, _v, test = tm.tb.split(layout, 5)
    contamination = round(float(train["anomaly"].mean()), 6)
    assert built == [("zscore", contamination, 5), ("iqr", contamination, 5)]
    assert [c[:2] for c in capped_calls] == [("zscore", 5), ("iqr", 5)]
    assert all(c[2] == len(train) for c in capped_calls)
    expected = [
        c
        for c in tm.im.Encoder.fit(train[list(clean.columns)], kinds)
        .transform(test[list(clean.columns)])
        .columns
    ]
    assert all(cols == [*expected, "t"] for cols, _ in fits) and len(fits) == 2


def test_the_drift_detector_sees_the_encoded_numeric_columns_and_the_arrival_time(
    tmp_path, monkeypatch
):
    clean, kinds, _ = tm.load_carrier(job(tmp_path))
    seen = {}

    class FakeDrift:
        def __init__(self, time_column, columns):
            seen["init"] = (time_column, columns)

    def fake_detect(x_test, detector, fit_df):
        seen["frames"] = (
            list(x_test.columns),
            list(fit_df.columns),
            x_test["t"].is_monotonic_increasing,
            list(x_test["t"]),
        )
        return type("R", (), {"flags": pd.Series(False, index=x_test.index)})()

    monkeypatch.setattr(tm, "TemporalDriftDetector", FakeDrift)
    monkeypatch.setattr(tm, "detect", fake_detect)
    out = tm.evaluate_seed(clean, kinds, 5, ["drift"])
    layout = tm._seed_layout(clean, kinds, 5)
    _train, _val, test = tm.tb.split(layout, 5)
    assert seen["frames"][3] == list(test["t"])
    time_column, columns = seen["init"]
    assert time_column == "t" and "t" not in columns and columns[:3] == ["a", "b", "c"]
    assert seen["frames"][0][-1] == "t" and seen["frames"][1][-1] == "t"
    assert out["hits"]["drift"] == {t: 0 for t in im.ANOMALY_TYPES}


def test_run_one_defaults_to_the_classical_detectors_and_reports_missing_types_as_none(
    tmp_path, monkeypatch
):
    names_seen = []

    def fake_seed(clean, kinds, seed, names):
        names_seen.append((seed, list(names)))
        counts = {t: (0 if t == "duplicate" else 2) for t in im.ANOMALY_TYPES}
        hits = {m: {t: 1 for t in im.ANOMALY_TYPES} for m in [*names, "transform_dedup"]}
        return {"counts": counts, "clean": 10, "hits": hits, "false_alarms": {m: 5 for m in hits}}

    monkeypatch.setattr(tm, "evaluate_seed", fake_seed)
    out = tm.run_one(job(tmp_path))
    assert names_seen[0][1] == tm.tb.DETECTORS and len(names_seen) == 20
    assert out["recall_pooled"]["knn"]["duplicate"] is None
    assert out["recall_pooled"]["knn"]["missing_value"] == pytest.approx(20 / 40)
    assert out["fpr_pooled"]["knn"] == pytest.approx(100 / 200) and out["clean_test_rows"] == 200
    assert out["test_counts"]["duplicate"] == 0 and out["test_counts"]["invalid_code"] == 40
    assert set(out["fpr_pooled"]) == {*tm.tb.DETECTORS, "transform_dedup"}


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


@pytest.fixture
def command(tmp_path, monkeypatch):
    root = tmp_path / "root"
    numeric = root.joinpath(*tm.NUMERIC_ELIGIBILITY)
    numeric.parent.mkdir(parents=True)
    numeric.write_text(
        json.dumps(
            [
                {"id": "uci:1", "eligible": False},
                {"id": "uci:2", "eligible": False},
                {"id": "uci:3", "eligible": True},
            ]
        )
    )
    asked = []

    def jobs(registry, pool, adbench):
        asked.append((registry, pool, adbench))
        return [{"id": f"uci:{i}", "source": "uci", "name": f"T{i}"} for i in (1, 2, 3)]

    monkeypatch.setattr(tm, "ROOT", root)
    monkeypatch.setattr(tm.pt, "jobs", jobs)
    monkeypatch.setattr(tm, "ProcessPoolExecutor", SerialPool)
    monkeypatch.setattr(
        tm, "eligibility", lambda j: {"id": j["id"], "eligible": j["id"] != "uci:2"}
    )
    SerialPool.created.clear()
    return root, asked, tmp_path / "out"


def test_the_parser_defaults_and_choices():
    args = tm.PARSER.parse_args(["run", "--output", "o"])
    assert (args.command, args.workers, args.methods, args.resume, args.only, args.scope) == (
        "run", 4, "classical", False, None, "ineligible",
    )  # fmt: skip
    assert tm.PARSER.parse_args(
        ["eligibility", "--output", "o", "--only", "a", "b", "--scope", "all"]
    ).only == ["a", "b"]
    with pytest.raises(SystemExit):
        tm.PARSER.parse_args(["run"])
    with pytest.raises(SystemExit):
        tm.PARSER.parse_args(["bogus", "--output", "o"])


def test_eligibility_command_reads_the_registry_paths_and_prints_the_count(command, capsys):
    root, asked, out = command
    assert tm.main(["eligibility", "--output", str(out), "--workers", "3"]) == 0
    assert asked == [
        (root / "verification/evidence/dataset_registry", root / "data/pool", root / "data/adbench")
    ]
    assert SerialPool.created == [3] and capsys.readouterr().out == "1 eligible of 2\n"
    text = (out / "eligibility.json").read_text()
    assert (
        text
        == json.dumps(
            [{"id": "uci:1", "eligible": True}, {"id": "uci:2", "eligible": False}], indent=1
        )
        + "\n"
    )


def test_scope_all_and_only_select_the_tables(command):
    _, _, out = command
    tm.main(["eligibility", "--output", str(out), "--scope", "all"])
    assert [r["id"] for r in json.loads((out / "eligibility.json").read_text())] == [
        "uci:1",
        "uci:2",
        "uci:3",
    ]
    tm.main(["eligibility", "--output", str(out), "--scope", "all", "--only", "uci:3"])
    assert [r["id"] for r in json.loads((out / "eligibility.json").read_text())] == ["uci:3"]


def test_run_command_writes_sorted_json_per_table_and_resumes(command, monkeypatch, capsys):
    _, _, out = command
    tm.main(["eligibility", "--output", str(out)])
    capsys.readouterr()
    runs, printed = [], []
    monkeypatch.setattr(tm, "run_one", fake_run_named(runs))
    monkeypatch.setattr(tm, "print", lambda *a, **k: printed.append((a, k)), raising=False)
    assert tm.main(["run", "--output", str(out), "--workers", "2"]) == 0
    saved = out / "classical" / "uci_1.json"
    assert saved.read_text() == '{"id": "uci:1", "names": null, "zeta": 1}\n'
    assert runs == ["uci:1"] and printed == [(("uci:1",), {"flush": True})]
    assert SerialPool.created[-1] == 2
    runs.clear()
    tm.main(["run", "--output", str(out), "--resume"])
    assert runs == []
    tm.main(["run", "--output", str(out)])
    assert runs == ["uci:1"]
    assert tm.main(["run", "--output", str(out), "--methods", "deep"]) == 0
    assert json.loads((out / "deep" / "uci_1.json").read_text())["names"] == list(tm.DEEP_NAMES)
    assert (out / "classical").is_dir() and (out / "deep").is_dir()


def fake_run_named(log):
    def run(job, names=None):
        log.append(job["id"])
        return {"zeta": 1, "id": job["id"], "names": names}

    return run


def test_swap_is_left_out_of_the_reported_types_when_the_data_cannot_carry_it(
    tmp_path, monkeypatch
):
    rng = np.random.default_rng(0)
    same = pd.DataFrame(
        {
            "a": rng.normal(0, 1, 300),
            "b": rng.normal(0.1, 1, 300),
            "p": rng.choice(["u", "v"], 300),
            "q": rng.choice(["u", "v"], 300),
        }
    )
    path = tmp_path / "same.csv"
    same.to_csv(path, index=False)
    monkeypatch.setattr(tm, "evaluate_seed", lambda c, k, s, n: stub_seed(n))
    out = tm.run_one({"id": "uci:5", "source": "uci", "name": "S", "path": str(path), "meta": {}})
    assert "cross_column_swap" not in out["types"] and "multivariate_outlier" in out["types"]
    assert set(out["recall_pooled"]["knn"]) == set(out["types"])


def stub_seed(names):
    counts = dict.fromkeys(im.ANOMALY_TYPES, 2)
    hits = {m: dict.fromkeys(im.ANOMALY_TYPES, 1) for m in [*names, "transform_dedup"]}
    return {"counts": counts, "clean": 10, "hits": hits, "false_alarms": dict.fromkeys(hits, 1)}


def test_the_command_creates_missing_parent_directories(command):
    _, _, out = command
    nested = out / "a" / "b"
    assert tm.main(["eligibility", "--output", str(nested)]) == 0
    assert (nested / "eligibility.json").exists()
