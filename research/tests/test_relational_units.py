"""Declared keys, their verification and the provisional relational load unit (synthetic)."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relational_faults as rf  # noqa: E402
import relational_units as ru  # noqa: E402


def _relation(child, parent, checked, orphans):
    return {"child": child, "parent": parent, "checked": checked, "orphans": orphans}


MANIFEST = {
    "v": {
        "files": {},
        "relations": [
            _relation("orders.cid", "customers.cid", 1200, 0),
            _relation("orders.note where a=1", "customers.cid", 3, 0),
            _relation("pas2.OTHER_ID", "cm.id", 5, 1),
        ],
    },
    "w": {"files": {}},
    "fec_federal_campaign_finance_2024": {
        "relations": [
            _relation("pas2.OTHER_ID", "cm.CMTE_ID", 9, 4),
            _relation("cm.a", "cn.a", 1, 0),
        ]
    },
}


def test_only_plain_table_column_references_become_keys_and_the_rest_are_listed():
    keys = ru.declared_keys(MANIFEST)
    assert sorted(keys) == ["fec_federal_campaign_finance_2024", "v"]
    (fk, recorded), *others = keys["v"]
    assert [k.child for k, _ in others] == ["pas2"]
    assert (fk.child, fk.columns, fk.parent, fk.parent_columns) == (
        "orders", ("cid",), "customers", ("cid",),
    )  # fmt: skip
    assert recorded["checked"] == 1200
    assert [k.child for k, _ in keys["fec_federal_campaign_finance_2024"]] == ["cm"]  # OTHER_ID out


def _tables(n=1200):
    customers = pd.DataFrame({"cid": [str(i) for i in range(50)]})
    orders = pd.DataFrame({"oid": range(n), "cid": [str(i % 50) for i in range(n)]})
    return {"customers": customers, "orders": orders}


FK = rf.ForeignKey("orders", ("cid",), "customers", ("cid",))


def test_verify_compares_recorded_and_recomputed_counts():
    tables = _tables()
    ok = ru.verify([(FK, _relation("orders.cid", "customers.cid", 1200, 0))], tables)
    assert ok == [
        {
            "key": "orders.cid -> customers.cid",
            "recorded": {"checked": 1200, "orphans": 0},
            "found": {"checked": 1200, "orphans": 0},
            "match": True,
        }
    ]
    tables["orders"].loc[0, "cid"] = "zzz"
    bad = ru.verify([(FK, _relation("orders.cid", "customers.cid", 1200, 0))], tables)
    assert not bad[0]["match"] and bad[0]["found"]["orphans"] == 1


def test_tables_are_read_as_text_and_only_an_empty_field_is_missing(tmp_path):
    folder = tmp_path / "v"
    folder.mkdir()
    (folder / "t.csv").write_text("a,b\n007,NA\n,x\n")
    table = ru.read_tables(tmp_path, "v", {"t"})["t"]
    assert table["a"].tolist()[0] == "007" and pd.isna(table["a"].iloc[1])
    assert table["b"].tolist() == ["NA", "x"]  # Namibia is not a missing value


def test_a_load_with_broken_references_alerts_and_the_rule_is_deterministic():
    tables = _tables(2400)
    high = ru.relational_cells(tables, FK, 2, 5)
    assert high["recall"] == 1.0 and high["false_alert_rate"] == 0.0
    assert high == ru.relational_cells(tables, FK, 2, 5)


def test_natural_orphans_raise_the_threshold_and_are_never_counted_as_faults():
    tables = _tables(2400)
    tables["orders"].loc[::7, "cid"] = "gone"  # a steady natural orphan share
    low = ru.relational_cells(tables, FK, 0, 1)
    assert low["threshold"] > 0.1  # the clean validation loads already carry orphans
    assert 0.0 <= low["recall"] <= 1.0
    high = ru.relational_cells(tables, FK, 2, 1)
    assert high["recall"] > low["recall"] or high["recall"] == 1.0


def test_main_verifies_every_declared_view_and_names_what_it_did_not_model(tmp_path, capsys):
    views = tmp_path / "views"
    (views / "v").mkdir(parents=True)
    tables = _tables()
    for name, frame in tables.items():
        frame.to_csv(views / "v" / f"{name}.csv", index=False)
    manifest = tmp_path / "m.json"
    wrong = {"relations": [_relation("orders.cid", "customers.cid", 1200, 5)]}
    good = {"relations": MANIFEST["v"]["relations"][:2]}
    manifest.write_text(json.dumps({"v": good, "y": wrong, "x": wrong}))
    (views / "y").mkdir()
    for name, frame in tables.items():
        frame.to_csv(views / "y" / f"{name}.csv", index=False)
    out = tmp_path / "r.json"
    assert ru.main(["--manifest", str(manifest), "--views", str(views), "--output", str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["v"]["status"] == "ok" and report["y"]["status"] == "mismatch"
    assert report["x"] == {"status": "tables not built locally"}
    assert "v:orders.note where a=1" in report["_unmodelled"]


def test_loads_are_consecutive_child_rows_with_the_registered_split_and_fault_share():
    out = ru.relational_cells(_tables(2400), FK, 2, 5)  # 40 loads of 60 rows
    assert out["loads"]["validation"] == 8 and out["loads"]["test"] == 16
    assert len(out["loads"]["faulty"]) == 5 and out["loads"]["faulty"] == sorted(
        out["loads"]["faulty"]
    )
    assert set(out["loads"]["faulty"]) <= set(range(16))
    assert out["loads"]["faulty"] != ru.relational_cells(_tables(2400), FK, 2, 6)["loads"]["faulty"]
    assert out["loads"]["faulty"] != ru.relational_cells(_tables(2400), FK, 1, 5)["loads"]["faulty"]
    small = ru.relational_cells(_tables(600), FK, 2, 1)  # 15 rows would fall below the 24-row floor
    assert small["loads"]["validation"] + small["loads"]["test"] == 25 - 10


def test_the_threshold_is_the_95th_percentile_of_the_validation_loads_only():
    tables = _tables(2400)
    tables["orders"].loc[range(960, 1440, 10), "cid"] = "gone"  # one orphan in ten, validation only
    out = ru.relational_cells(tables, FK, 0, 1)
    assert out["threshold"] == pytest.approx(0.1)
    assert out["false_alert_rate"] == 0.0  # clean test loads carry no orphan, none alerts


def test_the_parser_defaults_and_printed_report_format(capsys):
    args = ru.build_parser().parse_args([])
    assert (args.manifest, args.views, args.output) == (
        ru.MANIFEST,
        ru.ROOT / "data/experimental",
        None,
    )
    assert ru.build_parser().description == ru.__doc__


def test_the_report_is_sorted_indented_json_printed_or_written(tmp_path, capsys):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"b": {}, "a": {"relations": []}}))
    argv = ["--manifest", str(manifest), "--views", str(tmp_path)]
    assert ru.main(argv) == 0
    printed = capsys.readouterr().out
    assert (
        printed
        == '{\n "_unmodelled": {\n  "fec_federal_campaign_finance_2024:pas2.OTHER_ID": '
        + json.dumps(ru.UNMODELLED[("fec_federal_campaign_finance_2024", "pas2.OTHER_ID")])
        + "\n }\n}\n"
    )
    out = tmp_path / "o.json"
    ru.main([*argv, "--output", str(out)])
    assert out.read_text() == printed and capsys.readouterr().out == ""


def test_keys_of_a_view_are_reported_under_keys(tmp_path):
    views = tmp_path / "views"
    (views / "v").mkdir(parents=True)
    for name, frame in _tables().items():
        frame.to_csv(views / "v" / f"{name}.csv", index=False)
    manifest = tmp_path / "m.json"
    relation = _relation("orders.cid", "customers.cid", 1200, 0)
    manifest.write_text(json.dumps({"v": {"relations": [relation]}}))
    out = tmp_path / "r.json"
    ru.main(["--manifest", str(manifest), "--views", str(views), "--output", str(out)])
    assert json.loads(out.read_text())["v"]["keys"][0]["match"] is True
    assert ru.read_tables(views, "v", {"orders", "customers"}).keys() == {"orders", "customers"}


def test_a_relation_with_a_conditional_column_is_listed_even_when_the_view_has_plain_ones():
    manifest = {"v": {"relations": [_relation("a.x where y=1", "b.x", 1, 0)]}}
    assert ru.declared_keys(manifest) == {}
