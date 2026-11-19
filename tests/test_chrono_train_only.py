# ruff: noqa: E501
"""Train-only schema of the chronological replay and its paired comparison with the archive."""

import json

import numpy as np
import pandas as pd
import pytest

from research import chrono_train_only as ct


def _times(n):
    return pd.Series(pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))


def test_schema_levels_and_constant_columns_come_from_the_training_rows_only():
    train = pd.DataFrame({"n": [1.0, 2.0, 3.0], "c": ["a", "b", "a"], "k": [1.0, 1.0, 1.0]})
    schema = ct.fit_schema(train)
    assert schema["columns"] == {"n": None, "c": ["a", "b"]}


def test_a_column_with_too_many_levels_in_training_is_dropped_unless_uncapped():
    train = pd.DataFrame({"w": [f"id{i}" for i in range(ct.pc.CATEGORY_CAP + 1)]})
    assert ct.fit_schema(train)["columns"] == {}
    assert ct.fit_schema(train, cap=None)["columns"]["w"] is not None


def test_constant_columns_are_kept_when_dropping_is_disabled():
    train = pd.DataFrame({"k": [1.0, 1.0]})
    assert ct.fit_schema(train, drop_constant=False)["columns"] == {"k": None}


def test_missing_values_of_a_text_column_become_a_nan_level_unless_an_indicator_is_requested():
    train = pd.DataFrame({"c": ["a", None, "b"]})
    assert ct.fit_schema(train)["columns"]["c"] == ["a", "b", "nan"]
    schema = ct.fit_schema(train, na_indicator=True)
    assert schema["columns"]["c"] == ["a", "b"] and schema["na_indicator"] is True


def test_boolean_columns_are_categorical_not_numeric():
    train = pd.DataFrame({"b": [True, False, True]})
    assert ct.fit_schema(train)["columns"]["b"] == ["False", "True"]


def test_unseen_levels_become_all_zero_rows_and_numbers_are_floats():
    schema = ct.fit_schema(pd.DataFrame({"n": [1, 2, 3], "c": ["a", "b", "a"]}))
    out = ct.apply_schema(pd.DataFrame({"n": [4, 5], "c": ["a", "z"]}), schema)
    assert list(out.columns) == ["n", "c_a", "c_b"]
    assert out["n"].dtype == float
    assert out["c_a"].tolist() == [1.0, 0.0] and out["c_b"].tolist() == [0.0, 0.0]


def test_the_nan_indicator_flags_missing_cells_only():
    schema = ct.fit_schema(pd.DataFrame({"c": ["a", None, "b"]}), na_indicator=True)
    out = ct.apply_schema(pd.DataFrame({"c": ["a", None]}), schema)
    assert out["c_nan"].tolist() == [0.0, 1.0] and out["c_a"].tolist() == [1.0, 0.0]


def test_a_missing_value_matches_the_nan_level_when_the_training_rows_have_one():
    schema = ct.fit_schema(pd.DataFrame({"c": ["a", None, "b"]}))
    out = ct.apply_schema(pd.DataFrame({"c": [None, "a"]}), schema)
    assert out["c_nan"].tolist() == [1.0, 0.0]


def test_the_schema_reads_the_oldest_seventy_percent_in_time_order_and_never_later_rows():
    n = 100
    level = np.where(np.arange(n) >= 70, "late", np.where(np.arange(n) % 2 == 0, "a", "b"))
    raw = pd.DataFrame({"c": level, "x": np.arange(n, dtype=float)})
    shuffle = raw.sample(frac=1.0, random_state=0)
    times = _times(n)[shuffle.index].reset_index(drop=True)
    features, order = ct.split_features(shuffle.reset_index(drop=True), times)
    assert set(features.columns) == {"x", "c_a", "c_b"}
    assert features["x"].is_monotonic_increasing and sorted(order) == list(range(n))
    assert features.loc[70:, ["c_a", "c_b"]].sum().sum() == 0  # the late rows are all unseen


def test_a_level_present_in_the_oldest_rows_is_kept():
    raw = pd.DataFrame({"c": ["early"] * 60 + ["mid"] * 10 + ["late"] * 30})
    features, _ = ct.split_features(raw, _times(100))
    assert set(features.columns) == {"c_early", "c_mid"}


def test_the_sort_is_stable_for_equal_times():
    raw = pd.DataFrame({"x": np.arange(10, dtype=float)})
    features, order = ct.split_features(raw, pd.Series([pd.Timestamp("2020-01-01", tz="UTC")] * 10))
    assert order.tolist() == list(range(10)) and features["x"].tolist() == list(range(10))


def test_an_ineligible_dataset_is_excluded_with_the_archived_reason():
    y = np.zeros(1000, dtype=int)
    result = ct.run_raw(pd.DataFrame({"a": np.arange(1000.0)}), y, _times(1000))
    assert result == {"excluded": ct.pc.eligible(y, _times(1000))[1]}


def test_run_raw_hands_time_ordered_features_labels_and_times_to_the_archived_runner(monkeypatch):
    seen = {}

    def fake(features, y, times, methods):
        seen.update(features=features, y=y, times=times, methods=methods)
        return {"chronological": {}}

    monkeypatch.setattr(ct.pc, "run_dataset", fake)
    n = 200
    y = np.zeros(n, dtype=int)
    y[:50] = 1  # the file lists the newest rows first
    times = _times(n).iloc[::-1].reset_index(drop=True)  # newest first in the file
    raw = pd.DataFrame({"x": np.arange(n, dtype=float)})
    result = ct.run_raw(raw, y, times, ["zscore"])
    assert seen["methods"] == ["zscore"] and seen["times"].is_monotonic_increasing
    assert seen["features"]["x"].tolist() == list(range(n - 1, -1, -1))
    assert seen["y"].tolist() == y[::-1].tolist() and seen["y"][-50:].sum() == 50
    assert result["protocol"] == ct.PROTOCOL and result["feature_count"] == 1


def _run(pr, roc, spr, partitions=None):
    methods = list(pr)
    return {
        "partitions": partitions or {"train": 1},
        "chronological": {m: {"pr_auc": pr[m], "roc_auc": roc[m]} for m in methods},
        "stratified": {m: {"pr_auc": spr[m]} for m in methods},
    }


def test_the_comparison_reports_replay_minus_archive_and_rank_agreement():
    a = _run(
        {"m1": 0.5, "m2": 0.3, "m3": 0.1},
        {"m1": 0.9, "m2": 0.8, "m3": 0.7},
        {"m1": 0.6, "m2": 0.4, "m3": 0.2},
    )
    r = _run(
        {"m1": 0.4, "m2": 0.3, "m3": 0.2},
        {"m1": 0.95, "m2": 0.8, "m3": 0.7},
        {"m1": 0.6, "m2": 0.5, "m3": 0.2},
    )
    out = ct.compare({"d": a}, {"d": r})["d"]
    row = out["methods"]["m1"]
    assert row["pr_auc_archive"] == 0.5 and row["pr_auc_replay"] == 0.4
    assert row["chronological_pr_auc_difference"] == pytest.approx(-0.1)
    assert row["chronological_roc_auc_difference"] == pytest.approx(0.05)
    assert out["methods"]["m2"]["stratified_pr_auc_difference"] == pytest.approx(0.1)
    assert out["median_chronological_difference"] == pytest.approx(0.0)
    assert out["spearman_of_chronological_pr_auc"] == pytest.approx(1.0)
    assert out["partitions_equal"] is True
    assert out["partitions"] == {"archive": {"train": 1}, "replay": {"train": 1}}


def test_the_comparison_flags_different_partitions_and_reversed_rankings():
    a = _run(
        {"m1": 0.5, "m2": 0.3, "m3": 0.1}, {"m1": 1, "m2": 1, "m3": 1}, {"m1": 0, "m2": 0, "m3": 0}
    )
    r = _run(
        {"m1": 0.1, "m2": 0.3, "m3": 0.5},
        {"m1": 1, "m2": 1, "m3": 1},
        {"m1": 0, "m2": 0, "m3": 0},
        {"train": 2},
    )
    out = ct.compare({"d": a}, {"d": r})["d"]
    assert out["partitions_equal"] is False
    assert out["spearman_of_chronological_pr_auc"] == pytest.approx(-1.0)


def test_only_methods_and_datasets_present_in_both_are_compared_and_exclusions_are_kept():
    a = _run({"m1": 0.5, "m2": 0.3}, {"m1": 1, "m2": 1}, {"m1": 0, "m2": 0})
    r = _run({"m1": 0.5}, {"m1": 1}, {"m1": 0})
    out = ct.compare(
        {"d": a, "e": {"excluded": "few"}, "only_archive": a},
        {"d": r, "e": r, "only_replay": r},
    )
    assert set(out) == {"d", "e"} and list(out["d"]["methods"]) == ["m1"]
    assert out["e"] == {"excluded_archive": "few", "excluded_replay": None}


def test_the_command_writes_runs_and_a_comparison_for_the_selected_datasets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ct,
        "credit_card_raw",
        lambda: (
            pd.DataFrame({"x": np.arange(200.0)}),
            np.r_[np.zeros(150), np.ones(50)].astype(int),
            _times(200),
        ),
    )
    monkeypatch.setattr(
        ct.pc, "run_dataset", lambda f, y, t, m: {"chronological": {}, "partitions": {}}
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "credit_card.json").write_text(json.dumps({"excluded": "few"}))
    out = tmp_path / "out"
    assert ct.main(["--output", str(out), "--only", "credit_card", "--archive", str(archive)]) == 0
    assert json.loads((out / "credit_card.json").read_text())["protocol"] == ct.PROTOCOL
    report = json.loads((out / "comparison.json").read_text())
    assert report["protocol"] == ct.PROTOCOL
    assert report["datasets"]["credit_card"]["excluded_archive"] == "few"


def test_the_credit_card_file_is_read_raw_with_elapsed_seconds_as_times(monkeypatch):
    import etl_benchmark.config as config
    import etl_benchmark.extract as extract

    frame = pd.DataFrame({"Time": [0.0, 10.0, 5.0], "V1": [1.0, 2.0, 3.0], "Class": [0, 1, 0]})
    monkeypatch.setattr(
        extract, "read_csv", lambda path: frame if path == config.CREDIT_CARD_CSV else None
    )
    raw, y, times = ct.credit_card_raw()
    assert list(raw.columns) == ["V1"] and raw["V1"].tolist() == [1.0, 2.0, 3.0]
    assert y.tolist() == [0, 1, 0] and y.dtype == int
    assert times.tolist() == [
        pd.Timestamp("1970-01-01", tz="UTC") + pd.Timedelta(seconds=s) for s in (0, 10, 5)
    ]


def test_bank_marketing_months_roll_over_into_the_next_year_and_keep_file_order_inside_a_month(
    monkeypatch, tmp_path
):
    frame = pd.DataFrame(
        {
            "month": ["may", "may", "jun", "jan", "jan", "feb"],
            "y": ["no", "yes", "no", "yes", "no", "no"],
            "age": [30, 31, 32, 33, 34, 35],
        }
    )
    monkeypatch.setattr(
        ct.ul, "read_table", lambda path: frame if path == tmp_path / "b.csv" else None
    )
    raw, y, times = ct.bank_raw(tmp_path / "b.csv")
    assert list(raw.columns) == ["age"] and y.tolist() == [0, 1, 0, 1, 0, 0]
    stamps = [pd.Timestamp(t) for t in times]
    assert stamps[0] == pd.Timestamp("2008-05-01", tz="UTC") and stamps[1] == pd.Timestamp(
        "2008-05-01 00:01", tz="UTC"
    )
    assert stamps[2] == pd.Timestamp("2008-06-01", tz="UTC")
    assert stamps[3] == pd.Timestamp("2009-01-01", tz="UTC") and stamps[4] == pd.Timestamp(
        "2009-01-01 00:01", tz="UTC"
    )
    assert stamps[5] == pd.Timestamp("2009-02-01", tz="UTC")


def test_a_pool_table_keeps_readable_rows_aligns_labels_and_times_and_drops_the_time_columns(
    monkeypatch, tmp_path
):
    frame = pd.DataFrame(
        {"date": ["a", "b", "c", "d"], "x": [1.0, 2.0, 3.0, 4.0], "z": list("pqrs")}
    )
    stamps = pd.Series(
        [
            pd.Timestamp("2020-01-01", tz="UTC"),
            pd.NaT,
            pd.Timestamp("2020-01-03", tz="UTC"),
            pd.Timestamp("2020-01-04", tz="UTC"),
        ]
    )
    monkeypatch.setattr(ct.ul, "read_table", lambda path: frame)
    monkeypatch.setattr(
        ct.pc, "read_times", lambda f, uci_id: stamps if (f is frame and uci_id == 357) else None
    )
    seen = {}

    def derive(marked, meta):
        seen["columns"], seen["meta"] = list(marked.columns), meta
        return marked[marked["x"] != 3.0], np.array([0, 1]), {}  # the label rule drops one more row

    monkeypatch.setattr(ct.ul, "derive_labels", derive)
    raw, y, times, unreadable = ct.pool_raw({"name": "m"}, tmp_path / "357.csv", 357)
    assert unreadable == 1 and seen["meta"] == {"name": "m"} and seen["columns"][-1] == "__row__"
    assert (
        list(raw.columns) == ["x", "z"]
        and raw["x"].tolist() == [1.0, 4.0]
        and raw["z"].tolist() == ["p", "s"]
    )
    assert list(raw.index) == [0, 1] and list(times.index) == [0, 1] and y.tolist() == [0, 1]
    assert times.tolist() == [
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2020-01-04", tz="UTC"),
    ]


def test_a_schema_keeps_a_column_at_exactly_the_cap_and_drops_one_above_it():
    cap = ct.pc.CATEGORY_CAP
    at = pd.DataFrame({"c": [f"l{i}" for i in range(cap)]})
    above = pd.DataFrame({"c": [f"l{i}" for i in range(cap + 1)]})
    assert list(ct.fit_schema(at)["columns"]) == ["c"] and ct.fit_schema(above)["columns"] == {}
    assert ct.fit_schema(pd.DataFrame({"k": [1.0, 2.0]}))["columns"] == {"k": None}
    assert (
        ct.fit_schema(pd.DataFrame({"k": [1.0, None]}))["columns"] == {}
    )  # one distinct value is constant


def test_levels_are_sorted_and_columns_follow_the_training_order():
    schema = ct.fit_schema(pd.DataFrame({"b": ["z", "a", "m"], "a": [3.0, 1.0, 2.0]}))
    assert list(schema["columns"]) == ["b", "a"] and schema["columns"]["b"] == ["a", "m", "z"]
    out = ct.apply_schema(pd.DataFrame({"b": ["m"], "a": [5]}), schema)
    assert list(out.columns) == ["b_a", "b_m", "b_z", "a"] and out.iloc[0].tolist() == [
        0.0,
        1.0,
        0.0,
        5.0,
    ]


def _fake_jobs(monkeypatch, tmp_path):
    uci = tmp_path / "reg"
    uci.mkdir()
    return uci


def test_the_command_runs_each_dataset_with_its_own_schema_options(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(
        ct,
        "run_raw",
        lambda raw, y, times, methods=None, **opts: (
            calls.append((len(raw), methods, opts)) or {"chronological": {}, "partitions": {}}
        ),
    )
    small = (pd.DataFrame({"x": [1.0, 2.0]}), np.array([0, 1]), pd.Series([1, 2]))
    monkeypatch.setattr(ct, "credit_card_raw", lambda: small)
    monkeypatch.setattr(ct, "bank_raw", lambda path: small)
    monkeypatch.setattr(ct, "pool_raw", lambda meta, path, uci_id: (*small, 5))
    meta = {u: {"uci_id": u, "name": f"Name {u}"} for u in ct.pc.TIME_COLUMNS}
    monkeypatch.setattr(ct.json, "loads", ct.json.loads)
    out, archive = tmp_path / "out", tmp_path / "archive"
    archive.mkdir()
    registry = ct.ROOT / "verification" / "evidence" / "dataset_registry" / "uci_curated.json"
    real_read = type(registry).read_text
    monkeypatch.setattr(
        type(registry),
        "read_text",
        lambda self, *a, **k: (
            json.dumps({"kept": list(meta.values())})
            if self == registry
            else real_read(self, *a, **k)
        ),
    )
    assert ct.main(["--output", str(out), "--archive", str(archive), "--methods", "zscore"]) == 0
    names = sorted(p.stem for p in out.glob("*.json"))
    assert names == sorted(
        ["bank_marketing", "comparison", "credit_card", *[f"name_{u}" for u in ct.pc.TIME_COLUMNS]]
    )
    assert calls[0][1:] == (["zscore"], {"drop_constant": False, "cap": None})
    assert calls[1][2] == {"drop_constant": False, "cap": None, "na_indicator": True}
    assert all(c[2] == {} for c in calls[2:]) and len(calls) == 5
    assert json.loads((out / "name_357.json").read_text())["rows_without_a_readable_time"] == 5
    assert "rows_without_a_readable_time" not in json.loads((out / "credit_card.json").read_text())
    assert capsys.readouterr().out.splitlines()[0] == "credit_card ok"


def test_the_command_help_describes_the_options(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit) as stop:
        ct.main(["--help"])
    assert stop.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    for expected in (
        "Train-only replay of the chronological study",
        "--output OUTPUT",
        "--only [ONLY ...] dataset names, for a quick check",
        "--methods [METHODS ...] detector names (default: all 17)",
        "--archive ARCHIVE",
    ):
        assert expected in text, expected


def test_json_is_written_sorted_with_one_space_indent_and_a_final_newline(tmp_path):
    ct.write_json(tmp_path / "x.json", {"b": [1], "a": 2})
    assert (tmp_path / "x.json").read_text() == '{\n "a": 2,\n "b": [\n  1\n ]\n}\n'


def test_the_datasets_are_named_from_the_registry_and_load_the_files_of_the_archived_study(
    monkeypatch,
):
    got = []
    monkeypatch.setattr(ct, "bank_raw", lambda path: got.append(("bank", path)) or "bank")
    monkeypatch.setattr(
        ct, "pool_raw", lambda meta, path, uci_id: got.append((meta, path, uci_id)) or "pool"
    )
    meta = {u: {"uci_id": u, "name": f" Some Name {u} "} for u in ct.pc.TIME_COLUMNS}
    jobs = ct.datasets(meta)
    assert list(jobs)[:2] == ["credit_card", "bank_marketing"]
    assert [n for n in jobs][2:] == [f"some_name_{u}" for u in ct.pc.TIME_COLUMNS]
    assert jobs["credit_card"] == (ct.credit_card_raw, {"drop_constant": False, "cap": None})
    assert jobs["bank_marketing"][1] == {"drop_constant": False, "cap": None, "na_indicator": True}
    assert jobs["bank_marketing"][0]() == "bank" and got[0] == (
        "bank",
        ct.ROOT / "data" / "pool" / "222.csv",
    )
    for uci_id in ct.pc.TIME_COLUMNS:
        loader, options = jobs[f"some_name_{uci_id}"]
        assert options == {} and loader() == "pool"
        assert got[-1] == (meta[uci_id], ct.ROOT / "data" / "pool" / f"{uci_id}.csv", uci_id)


def test_the_command_with_no_selection_runs_every_dataset_and_requires_an_output(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        ct,
        "datasets",
        lambda meta: {
            "a": (lambda: (pd.DataFrame(), np.array([]), pd.Series(dtype=float)), {}),
            "b": (lambda: (pd.DataFrame(), np.array([]), pd.Series(dtype=float)), {}),
        },
    )
    monkeypatch.setattr(ct, "run_raw", lambda *a, **k: {"chronological": {}, "partitions": {}})
    assert ct.main(["--output", str(tmp_path / "n" / "m"), "--archive", str(tmp_path)]) == 0
    assert (tmp_path / "n" / "m" / "a.json").exists() and (tmp_path / "n" / "m" / "b.json").exists()
    with pytest.raises(SystemExit) as stop:
        ct.main([])
    assert stop.value.code == 2


def test_the_archive_is_a_path_and_defaults_to_the_pool_extension_archive(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(ct, "datasets", lambda meta: {})
    monkeypatch.setattr(ct, "compare", lambda a, r: seen.setdefault("n", len(a)) and {})
    (tmp_path / "ar").mkdir()
    (tmp_path / "ar" / "x.json").write_text("{}")
    ct.main(["--output", str(tmp_path / "o"), "--archive", str(tmp_path / "ar")])
    assert seen["n"] == 1
    from_default = []
    monkeypatch.setattr(ct, "compare", lambda a, r: from_default.append(sorted(a)) or {})
    ct.main(["--output", str(tmp_path / "o2")])
    assert from_default[0] == sorted(
        p.stem for p in (ct.ROOT / "verification/evidence/pool_extension/chrono").glob("*.json")
    )


def test_comparison_files_of_the_output_directory_are_never_read_back_as_runs(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(ct, "datasets", lambda meta: {})
    got = []
    monkeypatch.setattr(ct, "compare", lambda a, r: got.append(sorted(r)) or {})
    out = tmp_path / "o"
    out.mkdir()
    (out / "comparison.json").write_text("{}")
    (out / "real.json").write_text("{}")
    ct.main(["--output", str(out), "--archive", str(tmp_path)])
    assert got == [["real"]]


def test_an_excluded_dataset_does_not_stop_the_comparison_of_the_next_ones():
    ok = _run({"m1": 0.5, "m2": 0.3}, {"m1": 1, "m2": 1}, {"m1": 0, "m2": 0})
    out = ct.compare({"a": {"excluded": "x"}, "b": ok}, {"a": {"excluded": "y"}, "b": ok})
    assert out["a"] == {"excluded_archive": "x", "excluded_replay": "y"} and "methods" in out["b"]
    one_sided = ct.compare({"a": ok}, {"a": {"excluded": "y"}})["a"]
    assert one_sided == {"excluded_archive": None, "excluded_replay": "y"}


def test_the_rank_agreement_is_spearman_not_pearson():
    a = _run(
        {"m1": 0.1, "m2": 0.2, "m3": 0.9}, {"m1": 1, "m2": 1, "m3": 1}, {"m1": 0, "m2": 0, "m3": 0}
    )
    r = _run(
        {"m1": 0.1, "m2": 0.5, "m3": 0.6}, {"m1": 1, "m2": 1, "m3": 1}, {"m1": 0, "m2": 0, "m3": 0}
    )
    assert ct.compare({"d": a}, {"d": r})["d"]["spearman_of_chronological_pr_auc"] == pytest.approx(
        1.0
    )


def test_times_with_different_offsets_are_ordered_as_instants_and_ties_keep_file_order():
    raw = pd.DataFrame({"x": [0.0, 1.0, 2.0]})
    times = pd.Series(
        ["2024-01-01T02:00:00+02:00", "2024-01-01T00:30:00+00:00", "2024-01-01T00:10:00+00:00"]
    )
    features, order = ct.split_features(raw, times)
    assert order.tolist() == [0, 2, 1] or order.tolist() == [2, 0, 1]
    ties = pd.DataFrame({"x": np.arange(100.0)})
    _, order = ct.split_features(ties, pd.Series([pd.Timestamp("2020-01-01", tz="UTC")] * 100))
    assert order.tolist() == list(range(100))


def test_run_raw_hands_its_schema_options_to_the_feature_split(monkeypatch):
    seen = {}
    real = ct.split_features

    def spy(raw, times, **options):
        seen.update(options)
        return real(raw, times, **options)

    monkeypatch.setattr(ct, "split_features", spy)
    monkeypatch.setattr(ct.pc, "run_dataset", lambda f, y, t, m: {})
    n = 200
    y = np.zeros(n, dtype=int)
    y[-50:] = 1
    ct.run_raw(
        pd.DataFrame({"x": np.arange(n, dtype=float)}), y, _times(n), None, cap=3, na_indicator=True
    )
    assert seen == {"cap": 3, "na_indicator": True}
