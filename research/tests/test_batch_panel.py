"""Batch eligibility of registry views: the batch-unit rule of the protocol, no detector."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch_panel as bp  # noqa: E402


def _frame(n=2000, columns=4, stamp="timestamp", seed=0):
    rng = np.random.default_rng(seed)
    data = {f"x{i}": rng.normal(size=n) for i in range(columns)}
    times = pd.date_range("2021-01-01", periods=n, freq="h").strftime("%Y-%m-%d %H:%M:%S")
    return pd.DataFrame({stamp: times, **data})


def test_the_restated_constants_and_helpers_equal_those_of_the_plumbing_pilot():
    ci = pytest.importorskip("chrono_injected")
    inj = pytest.importorskip("injection")
    assert (bp.MIN_ROWS, bp.MIN_COLUMNS, bp.TREND) == (ci.MIN_ROWS, ci.MIN_COLUMNS, ci.TREND)
    assert bp.MIN_DISTINCT == inj.MIN_DISTINCT
    frame = _frame(columns=5).assign(counter=np.arange(2000), flag=[True, False] * 1000)
    stamps = pd.to_datetime(frame["timestamp"])
    values = frame.drop(columns="timestamp")
    assert bp.trend_columns(values, stamps) == ci.trend_columns(values, stamps)
    assert bp.continuous_columns(frame) == inj.continuous_columns(frame)


def test_trend_columns_use_the_rank_correlation_strictly_above_the_threshold(monkeypatch):
    stamps = pd.to_datetime(_frame()["timestamp"])
    monotone = pd.Series(np.exp(np.arange(2000) / 100.0))  # Pearson well below 1, Spearman 1
    noise = pd.Series(np.sin(np.arange(2000)))
    assert bp.trend_columns(pd.DataFrame({"m": monotone, "n": noise}), stamps) == ["m"]
    monkeypatch.setattr(bp, "TREND", 1.0)
    assert bp.trend_columns(pd.DataFrame({"m": monotone}), stamps) == []  # 1.0 is not above 1.0
    monkeypatch.setattr(bp, "TREND", 0.99)
    assert bp.trend_columns(pd.DataFrame({"t": ["a"] * 2000}), stamps) == []


def test_continuous_columns_are_numeric_with_at_least_ten_distinct_values():
    frame = pd.DataFrame(
        {
            "ten": np.arange(30) % 10,
            "nine": np.arange(30) % 9,
            "text": [f"s{i}" for i in range(30)],
            "flag": [True, False] * 15,
        }
    )
    assert bp.continuous_columns(frame) == ["ten"]


def test_time_column_is_found_by_content_whatever_its_name():
    assert bp.time_column(_frame()) == "timestamp"
    assert bp.time_column(_frame(stamp="label")) == "label"  # the name is not consulted
    assert bp.time_column(_frame(stamp="Time_of_day")) == "Time_of_day"
    numeric = _frame().assign(timestamp=np.arange(2000))
    assert bp.time_column(numeric) is None  # epochs and counters are ambiguous
    broken = _frame()
    broken.loc[:100, "timestamp"] = "not a date"
    assert bp.time_column(broken) is None  # under 99 percent parsed


def test_time_column_skips_columns_that_do_not_qualify_and_keeps_looking():
    frame = _frame()
    frame.insert(0, "alpha", "x")  # text that is not a date
    frame.insert(0, "date_num", np.arange(2000))  # numeric, whatever its name
    frame.insert(0, "date_bad", "nope")  # unparseable
    assert bp.time_column(frame) == "timestamp"


def test_a_prefix_probe_rejects_a_column_before_the_full_parse(monkeypatch):
    late = _frame()
    late.loc[300:, "timestamp"] = "not a date"  # the first 200 rows are all dates
    assert bp.time_column(late) is None  # the full parse still decides
    early = _frame()
    early.loc[:100, "timestamp"] = "not a date"
    calls = []
    real = bp.parse_time
    monkeypatch.setattr(bp, "parse_time", lambda c: calls.append(len(c)) or real(c))
    assert bp.time_column(early) is None
    assert calls == [bp.PROBE]  # rejected by the probe: no full-length parse


def test_time_column_thresholds_are_inclusive_and_mixed_offsets_are_read(monkeypatch):
    two = _frame().assign(timestamp=["2021-01-01", "2021-01-02"] * 1000)
    assert bp.time_column(two) == "timestamp"  # exactly two distinct instants is varying
    assert bp.time_column(_frame().assign(timestamp="2021-01-01")) is None
    half = _frame().assign(timestamp=["2021-01-01", "2021-01-02", "bad", "bad"] * 500)
    assert bp.time_column(half) is None
    monkeypatch.setattr(bp, "MIN_PARSED", 0.5)
    assert bp.time_column(half) == "timestamp"  # exactly the share counts
    offsets = ["2021-01-01 00:00:00+01:00", "2021-01-01 05:00:00-02:00"] * 1000
    assert bp.time_column(_frame().assign(timestamp=offsets)) == "timestamp"


def test_eligible_table_reports_rows_columns_and_batch_size():
    assert bp.assess_table(_frame(2400)) == {
        "eligible": True,
        "reasons": [],
        "time_column": "timestamp",
        "columns": 4,
        "rows": 2400,
        "batch_rows": 24,
        "batches": 100,
    }
    big = bp.assess_table(_frame(5001))
    assert (big["batch_rows"], big["batches"]) == (50, 100)
    assert isinstance(big["batches"], int)


def test_the_row_threshold_is_inclusive():
    assert bp.assess_table(_frame(1500))["eligible"] is True
    assert bp.assess_table(_frame(1499))["reasons"] == ["only 1499 rows after cleaning"]


def test_ineligible_tables_report_their_reason_and_what_was_found():
    assert bp.assess_table(_frame(columns=3)) == {
        "eligible": False,
        "reasons": ["only 3 continuous columns"],
        "time_column": "timestamp",
        "columns": 3,
        "rows": 0,
    }
    assert bp.assess_table(_frame().assign(timestamp="no date")) == {
        "eligible": False,
        "reasons": ["no parseable time column"],
        "time_column": None,
        "columns": 0,
        "rows": 0,
    }


def test_rows_with_a_missing_value_or_a_duplicate_do_not_count():
    frame = _frame(1600)
    frame.loc[:99, "x0"] = np.nan
    frame.iloc[200:300, 1:] = frame.iloc[199, 1:].to_numpy()  # 100 repeated rows
    report = bp.assess_table(frame)
    assert report["rows"] == 1400
    assert report["reasons"] == ["only 1400 rows after cleaning"]


def test_rows_without_a_readable_time_do_not_count():
    frame = _frame(1600)
    frame.loc[:9, "timestamp"] = np.nan
    assert bp.assess_table(frame)["rows"] == 1590


def test_a_column_that_is_an_index_of_the_time_order_is_not_a_feature():
    frame = _frame(columns=4).assign(counter=np.arange(2000))
    assert bp.assess_table(frame)["columns"] == 4
    assert bp.assess_table(frame.iloc[::-1].reset_index(drop=True))["columns"] == 4


def test_view_tables_reads_a_directory_or_a_flat_file(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "b.csv").write_text("a\n1\n")
    (tmp_path / "d" / "a.csv").write_text("a\n1\n")
    (tmp_path / "d" / "c.txt").write_text("x")
    (tmp_path / "flat").mkdir()
    (tmp_path / "flat" / "f.csv").write_text("a\n1\n")
    assert [p.name for p in bp.view_tables(tmp_path, "d")] == ["a.csv", "b.csv"]
    assert [p.name for p in bp.view_tables(tmp_path, "f")] == ["f.csv"]
    assert bp.view_tables(tmp_path, "gone") is None


def test_audit_view_takes_the_first_eligible_table_in_name_order(tmp_path):
    (tmp_path / "v").mkdir()
    for name, n in (("a", 1000), ("b", 2000), ("c", 3000)):
        _frame(n).to_csv(tmp_path / "v" / f"{name}.csv", index=False)
    report = bp.audit_view(tmp_path, "v", "v", False)
    assert report["eligible"] is True and report["reasons"] == []
    assert report["table"]["file"] == "b.csv" and report["table"]["rows"] == 2000
    assert [t["file"] for t in report["tables"]] == ["a.csv", "b.csv", "c.csv"]


def test_audit_view_collects_the_reasons_of_every_ineligible_table(tmp_path):
    (tmp_path / "v").mkdir()
    _frame(1000).to_csv(tmp_path / "v" / "a.csv", index=False)
    _frame(columns=2).to_csv(tmp_path / "v" / "b.csv", index=False)
    report = bp.audit_view(tmp_path, "v", "v", False)
    assert report["eligible"] is False and report["table"] is None
    assert report["reasons"] == ["only 1000 rows after cleaning", "only 2 continuous columns"]


def test_audit_view_without_a_flat_table_is_not_defined_by_the_protocol(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "records.jsonl").write_text('{"a": 1}\n')
    assert bp.audit_view(tmp_path, "v", "v", False) == {
        "eligible": False,
        "reasons": ["no CSV table: the batch unit is not defined for this layout"],
        "table": None,
        "tables": [],
    }


def test_a_view_that_is_not_built_is_reported_as_such(tmp_path):
    assert bp.audit_view(tmp_path, "gone", "gone", False) == {
        "eligible": False,
        "reasons": ["view gone is not built locally"],
        "table": None,
        "tables": [],
    }


def test_a_flat_view_is_one_csv_under_the_flat_directory(tmp_path):
    (tmp_path / "flat").mkdir()
    _frame(2000).to_csv(tmp_path / "flat" / "series_C3.csv", index=False)
    report = bp.audit_view(tmp_path, "series_C3", "series_C3", False)
    assert report["eligible"] is True and report["table"]["file"] == "series_C3.csv"


def test_attribution_by_suffix_and_the_base_fact_of_a_shared_view():
    names = [Path("mhra.csv"), Path("nhsbsa.csv")]
    assert bp.attributed("ukspend_mhra", "ukspend", names, True) == [Path("mhra.csv")]
    assert bp.attributed("ukspend", "ukspend", names, True) == names
    assert bp.attributed("ukspend_mhra", "ukspend", names, False) == names
    assert bp.attributed("ukspend_hra", "ukspend", names, True) == []
    assert bp.attributed("UCI:560", "series", [Path("uci_560.csv")], True) == [Path("uci_560.csv")]


def test_a_shared_view_gives_each_fact_only_its_own_table(tmp_path):
    (tmp_path / "series").mkdir()
    _frame(2000).to_csv(tmp_path / "series" / "uci_560.csv", index=False)
    _frame(1000).to_csv(tmp_path / "series" / "uci_999.csv", index=False)
    facts = {
        "uci:560": {"independent_group": "bike", "view": "series"},
        "uci:999": {"independent_group": "small", "view": "series"},
        "uci:111": {"independent_group": "absent", "view": "series"},
    }
    out = bp.audit_groups(facts, tmp_path)
    assert out["bike"]["eligible"] is True and out["bike"]["table"]["file"] == "uci_560.csv"
    assert out["small"]["reasons"] == ["only 1000 rows after cleaning"]
    layout = ["no CSV table: the batch unit is not defined for this layout"]
    assert out["absent"]["reasons"] == layout


def test_audit_groups_is_eligible_when_any_of_its_facts_is(tmp_path):
    for name, n in (("v1", 1000), ("v2", 2000), ("v3", 1000)):
        (tmp_path / name).mkdir()
        _frame(n).to_csv(tmp_path / name / "t.csv", index=False)
    facts = {
        "g1": {"independent_group": "grp", "view": "v1"},
        "g2": {"independent_group": "grp", "view": "v2"},
        "g3": {"independent_group": "other", "view": "v3"},
        "g4": {"independent_group": "none", "view": None},
        "g5": {"independent_group": None, "view": "v4"},
    }
    out = bp.audit_groups(facts, tmp_path)
    assert out["grp"] == {
        "eligible": True,
        "view": "v2",
        "views": ["v1", "v2"],
        "reasons": [],
        "table": out["grp"]["table"],
    }
    assert out["grp"]["table"]["rows"] == 2000
    assert out["other"] == {
        "eligible": False,
        "view": None,
        "views": ["v3"],
        "reasons": ["only 1000 rows after cleaning"],
        "table": None,
    }
    assert out["none"] == {"eligible": False, "views": [], "reasons": ["no experimental view"]}
    assert set(out) == {"grp", "other", "none"}


def test_a_view_shared_by_exactly_two_facts_is_attributed_per_fact(tmp_path):
    (tmp_path / "v").mkdir()
    _frame(2000).to_csv(tmp_path / "v" / "one.csv", index=False)
    _frame(1000).to_csv(tmp_path / "v" / "two.csv", index=False)
    facts = {
        "v_one": {"independent_group": "a", "view": "v"},
        "v_two": {"independent_group": "b", "view": "v"},
    }
    out = bp.audit_groups(facts, tmp_path)
    assert out["a"]["eligible"] is True and out["a"]["table"]["file"] == "one.csv"
    assert out["b"]["eligible"] is False and out["b"]["reasons"] == [
        "only 1000 rows after cleaning"
    ]


def test_the_base_fact_of_a_shared_view_keeps_every_table(tmp_path):
    (tmp_path / "v").mkdir()
    _frame(1000).to_csv(tmp_path / "v" / "one.csv", index=False)
    _frame(2000).to_csv(tmp_path / "v" / "two.csv", index=False)
    report = bp.audit_view(tmp_path, "v", "v", True)
    assert [t["file"] for t in report["tables"]] == ["one.csv", "two.csv"]


def test_summary_counts_eligible_groups_per_category():
    audit = {
        "a": {"eligible": True},
        "b": {"eligible": False},
        "c": {"eligible": True},
        "extra": {"eligible": True},  # audited but not in any category
    }
    members = {"C1": ["a", "b"], "C2a": ["c"], "C3": ["b", "x"]}
    out = bp.summarise(audit, members)
    assert out["groups"] == {"audited": 3, "eligible": 2}
    assert out["per_category"] == {
        "C1": {"ready": 2, "eligible": 1},
        "C2a": {"ready": 1, "eligible": 1},
        "C3": {"ready": 2, "eligible": 0},
    }


def test_main_writes_a_deterministic_report_and_defaults_to_the_evidence_directory(
    tmp_path, monkeypatch, capsys
):
    evidence = tmp_path / "evidence"
    views = tmp_path / "views"
    (views / "v").mkdir(parents=True)
    _frame(2000).to_csv(views / "v" / "t.csv", index=False)
    evidence.mkdir()
    (evidence / "readiness_facts.json").write_text(
        json.dumps({"facts": {"g": {"independent_group": "grp", "view": "v"}}})
    )
    (evidence / "readiness.json").write_text(json.dumps({"ready_groups": {"C3": ["grp"]}}))
    monkeypatch.setattr(bp, "EVIDENCE", evidence)
    monkeypatch.setattr(bp, "VIEWS", views)
    assert bp.main([]) == 0
    out = evidence / "batch_eligibility.json"
    first = out.read_text()
    assert first.endswith("\n")
    printed = capsys.readouterr().out
    expected = {"groups": {"audited": 1, "eligible": 1}}
    expected["per_category"] = {"C3": {"eligible": 1, "ready": 1}}
    assert printed == json.dumps(expected, sort_keys=True) + "\n"
    assert first == json.dumps(json.loads(first), indent=1, sort_keys=True) + "\n"
    assert bp.main([]) == 0
    assert out.read_text() == first
    report = json.loads(first)
    assert report["protocol"] == "pipeline-batch-v1"
    assert report["rule"] == {
        "min_rows": 1500,
        "min_continuous_columns": 4,
        "probe_rows": 200,
        "min_parsed_share": 0.99,
    }
    assert list(report) == ["groups", "protocol", "rule", "summary"]
    assert report["groups"]["grp"]["table"]["rows"] == 2000
    other = tmp_path / "other.json"
    argv = ["--evidence", str(evidence), "--views", str(views), "--output", str(other)]
    assert bp.main(argv) == 0
    assert other.read_text() == first
